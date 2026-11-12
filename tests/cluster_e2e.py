#!/usr/bin/env python3
"""ClashGate cluster end-to-end test on one machine, as a normal user, everything in a temp dir.

  python3 tests/cluster_e2e.py            # needs openssl, ss, curl and the pinned core (tests/run.sh downloads it)

Starts panels A, B, C and D on 127.0.0.x over HTTPS (certificates from a throw-away CA that only
these processes trust), each with its own real Mihomo core driven by a fake systemctl, and drives
them through their own HTTP APIs: A adds B (two-way link), C adds A (C is linked with A and B
automatically: full mesh), D joins while C is offline and completes the mesh with 检查 later.
Traffic is sent through every cluster outbound in both directions with an extra client core.
Also covers the error paths (wrong password, old panel, bad certificate, unreachable, address that
does not lead back, duplicate, name clash, custom-server lock), draft isolation, renames, removing a
member (also while it is offline), re-adding it, and leaving the cluster.
Set CG_OLD_PANEL_DIR to a ClashGate 1.13 checkout's panel/ to also test the "too old" message.
"""
import http.cookiejar
import http.server
import json
import os
import re
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
MIHOMO = os.path.abspath(os.environ.get("MIHOMO_BIN") or os.path.join(HERE, ".cache", "mihomo"))
TMP = tempfile.mkdtemp(prefix="cg-e2e-")
PW = {w: f"pw-{w}-" + os.urandom(6).hex() for w in ("A", "B", "C", "D")}
HOSTS = {"A": "127.0.0.1", "B": "127.0.0.2", "OLD": "127.0.0.3", "BAD": "127.0.0.4", "C": "127.0.0.6", "D": "127.0.0.7"}
PORTS = {"A": 28401, "B": 28402, "OLD": 28403, "BAD": 28404, "C": 28406, "D": 28407}
PANEL_PROCS = {}
PROCS = []
FAILS = []


def sh(*cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def check(cond, what):
    print(("  ok   " if cond else "  FAIL ") + what)
    if not cond:
        FAILS.append(what)


def make_certs():
    d = TMP + "/pki"
    os.makedirs(d)
    sh("openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256", "-nodes", "-days", "2",
       "-subj", "/CN=cg-e2e-ca", "-addext", "basicConstraints=critical,CA:TRUE",
       "-addext", "keyUsage=critical,keyCertSign,cRLSign", "-keyout", d + "/ca.key", "-out", d + "/ca.pem")
    for who in ("A", "B", "OLD", "C", "D"):
        sh("openssl", "req", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256", "-nodes", "-subj", f"/CN={who}",
           "-keyout", f"{d}/{who}.key", "-out", f"{d}/{who}.csr")
        with open(f"{d}/{who}.ext", "w") as f:
            f.write(f"subjectAltName=IP:{HOSTS[who]}\nbasicConstraints=CA:FALSE\nkeyUsage=critical,digitalSignature\n"
                    "extendedKeyUsage=serverAuth\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid\n")
        sh("openssl", "x509", "-req", "-in", f"{d}/{who}.csr", "-CA", d + "/ca.pem", "-CAkey", d + "/ca.key",
           "-CAcreateserial", "-days", "2", "-extfile", f"{d}/{who}.ext", "-out", f"{d}/{who}.pem")
    # BAD: self-signed, not from the test CA
    sh("openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256", "-nodes", "-days", "2",
       "-subj", "/CN=bad", "-addext", f"subjectAltName=IP:{HOSTS['BAD']}", "-keyout", d + "/BAD.key", "-out", d + "/BAD.pem")
    return d


FAKE_SYSTEMCTL = r"""#!/bin/sh
# Minimal systemctl stand-in: one Mihomo per CLASHGATE_ROOT.
R="$CLASHGATE_ROOT/etc/clashgate"; PIDF="$CLASHGATE_ROOT/mihomo.pid"
alive() { [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF")" 2>/dev/null; }
start() { SAFE_PATHS="$R" "$MIHOMO_BIN" -d "$R" -f "$R/config.yaml" >>"$CLASHGATE_ROOT/mihomo.log" 2>&1 & echo $! > "$PIDF"; sleep 0.6; }
stop() { if alive; then kill "$(cat "$PIDF")"; sleep 0.3; fi; }
case "$1" in
  is-active) if alive; then echo active; else echo inactive; exit 3; fi ;;
  show) echo "MainPID=$(cat "$PIDF" 2>/dev/null)" ;;
  reload) if alive; then kill -HUP "$(cat "$PIDF")"; sleep 0.6; else start; fi ;;
  restart|start) stop; start ;;
  stop) stop ;;
esac
exit 0
"""


def panel_env(root, extra=None):
    env = dict(os.environ, CLASHGATE_ROOT=root, MIHOMO_BIN=MIHOMO, SYSTEMCTL=TMP + "/bin/systemctl",
               UFW_BIN="false", FIREWALL_CMD_BIN="false", CLASHGATE_CLUSTER_CAFILE=TMP + "/pki/ca.pem",
               PYTHONDONTWRITEBYTECODE="1")
    env.update(extra or {})
    return env


def setup_panel(who, panel_dir, pki, init_state=True):
    root = f"{TMP}/{who}"
    cs = root + "/etc/clashgate"
    os.makedirs(cs + "/certs")
    shutil.copytree(os.path.join(REPO, "resources"), cs + "/resources")
    shutil.copy(f"{pki}/{who}.pem", cs + "/certs/fullchain.pem")
    shutil.copy(f"{pki}/{who}.key", cs + "/certs/privkey.pem")
    with open(cs + "/clashgate.env", "w") as f:
        f.write(f'MODE="no-cert"\nSERVER_IP="{HOSTS[who]}"\nPANEL_PORT="{PORTS[who]}"\nCONTROLLER_PORT="{PORTS[who] + 50}"\n')
    env = panel_env(root)
    h = subprocess.run([sys.executable, panel_dir + "/panel.py", "hash-password"], input=PW.get(who, "x" * 12) + "\n",
                       capture_output=True, text=True, env=env, check=True).stdout.strip()
    with open(cs + "/panel.json", "w") as f:
        json.dump({"username": "admin", "password_hash": h, "listen": HOSTS[who], "port": PORTS[who],
                   "tls_cert": "/etc/clashgate/certs/fullchain.pem", "tls_key": "/etc/clashgate/certs/privkey.pem",
                   "sub_token": "t" * 24 + who}, f)
    if init_state:
        code = ("import panel as P; e=P.read_env(); P._write_template_state([P.new_default_reality_node(e)],[],[],{},e);"
                f"P.save_panel_settings({{'node_name': {who + '-Node'!r}}})")
        subprocess.run([sys.executable, "-c", code], env=dict(env, PYTHONPATH=panel_dir), check=True)
        subprocess.run([TMP + "/bin/systemctl", "start", "mihomo"], env=env, check=True)
    start_panel(who, panel_dir)
    return root


def start_panel(who, panel_dir=os.path.join(REPO, "panel")):
    root = f"{TMP}/{who}"
    cs = root + "/etc/clashgate"
    p = subprocess.Popen([sys.executable, panel_dir + "/panel.py", "serve", "--config", cs + "/panel.json"],
                         env=panel_env(root), stdout=open(root + "/panel.log", "a"), stderr=subprocess.STDOUT)
    PROCS.append(p)
    PANEL_PROCS[who] = p
    for _ in range(100):
        try:
            socket.create_connection((HOSTS[who], PORTS[who]), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)


def stop_panel(who):
    p = PANEL_PROCS.pop(who)
    p.terminate()
    p.wait()


class Client:
    def __init__(self, who):
        self.base = f"https://{HOSTS[who]}:{PORTS[who]}"
        ctx = ssl.create_default_context(cafile=TMP + "/pki/ca.pem")
        self.op = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx),
                                              urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.op.open(self.base + "/login", urllib.parse.urlencode({"username": "admin", "password": PW[who]}).encode(), timeout=30)
        self.state = self.get("/api/state")
        assert self.state.get("csrf"), "login failed"

    def get(self, path):
        with self.op.open(urllib.request.Request(self.base + path, headers={"Accept": "application/json"}), timeout=60) as r:
            return json.loads(r.read())

    def post(self, path, **form):
        data = urllib.parse.urlencode({"csrf": self.state["csrf"], **form}).encode()
        req = urllib.request.Request(self.base + path, data=data,
                                     headers={"X-Requested-With": "fetch", "Accept": "application/json"})
        try:
            with self.op.open(req, timeout=150) as r:
                res = json.loads(r.read())
        except urllib.error.HTTPError as e:
            res = json.loads(e.read())
        if res.get("state"):
            self.state = res["state"]
        return res


def read(p):
    with open(p) as f:
        return f.read()


def listening(port):
    return f":{port} " in subprocess.run(["ss", "-Hltn"], capture_output=True, text=True).stdout + " "


def bad_tls_server(pki):
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200); self.end_headers(); self.wfile.write(b"{}")
        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer((HOSTS["BAD"], PORTS["BAD"]), H)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(pki + "/BAD.pem", pki + "/BAD.key")
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()


def target_server():
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = b"hello-through-cluster"
            self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers()
            self.wfile.write(body)
        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv.server_address[1]


def mihomo_t(conf_path):
    d = tempfile.mkdtemp(dir=TMP)
    r = subprocess.run([MIHOMO, "-t", "-d", d, "-f", conf_path], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def curl_via(proxy_dict, url):
    """Run a client core with only this outbound and fetch url through it."""
    d = tempfile.mkdtemp(dir=TMP)
    with socket.socket() as so:   # a free port (cluster inbounds take random ports too)
        so.bind(("127.0.0.1", 0))
        port = so.getsockname()[1]
    proxy_dict = {**proxy_dict, "name": "via"}   # node names may contain commas; keep the client rule simple
    with open(d + "/c.yaml", "w") as f:
        f.write(f"mixed-port: {port}\nmode: rule\nlog-level: warning\nproxies:\n  - {json.dumps(proxy_dict)}\n"
                f"rules:\n  - MATCH,via\n")
    p = subprocess.Popen([MIHOMO, "-d", d, "-f", d + "/c.yaml"], stdout=open(d + "/log", "w"), stderr=subprocess.STDOUT)
    try:
        for _ in range(50):
            if listening(port):
                break
            time.sleep(0.1)
        else:
            return "client core did not start: " + read(d + "/log")[-300:]
        r = subprocess.run(["curl", "-s", "-m", "10", "-o", "-", "-w", "\n%{http_code}", "-x", f"http://127.0.0.1:{port}", url],
                           capture_output=True, text=True)
        return r.stdout
    finally:
        p.terminate()
        p.wait()


def state(cl):
    cl.state = cl.get("/api/state")
    return cl.state


def member_names(cl):
    return sorted(m["name"] for m in state(cl)["cluster"]["members"])


def cluster_frags(cs):
    proxies = [json.loads(l.strip()[2:]) for l in read(cs + "/proxies.cluster.yaml").splitlines() if l.strip()]
    listeners = [json.loads(l.strip()[2:]) for l in read(cs + "/listeners.cluster.yaml").splitlines() if l.strip()]
    return proxies, listeners


def wait_for(fn, secs=8.0):
    end = time.time() + secs
    while time.time() < end:
        if fn():
            return True
        time.sleep(0.2)
    return fn()


def main():
    if not os.path.isfile(MIHOMO):
        sys.exit(f"core not found: {MIHOMO}")
    os.makedirs(TMP + "/bin")
    with open(TMP + "/bin/systemctl", "w") as f:
        f.write(FAKE_SYSTEMCTL)
    os.chmod(TMP + "/bin/systemctl", 0o755)
    pki = make_certs()
    panel_dir = os.path.join(REPO, "panel")
    roots = {w: setup_panel(w, panel_dir, pki) for w in ("A", "B", "C", "D")}
    cs = {w: r + "/etc/clashgate" for w, r in roots.items()}
    old_dir = os.environ.get("CG_OLD_PANEL_DIR")
    if old_dir:
        setup_panel("OLD", old_dir, pki, init_state=False)
    bad_tls_server(pki)
    cl = {w: Client(w) for w in ("A", "B", "C", "D")}
    a, b, c, d = cl["A"], cl["B"], cl["C"], cl["D"]
    url = {w: f"https://{HOSTS[w]}:{PORTS[w]}" for w in HOSTS}
    port_t = target_server()

    def traffic(src, dst_name):
        prox = [p for p in cluster_frags(cs[src])[0] if p["name"] == dst_name]
        if not prox:
            return f"no outbound {dst_name} on {src}"
        return curl_via(prox[0], f"http://127.0.0.1:{port_t}/")

    def mesh_ok(names):
        """Every panel in names has outbounds + inbounds for all the others, and traffic flows both ways."""
        for w in names:
            want = sorted(f"{o}-Node" for o in names if o != w)
            check(member_names(cl[w]) == want, f"{w} lists {want}")
            prox, lst = cluster_frags(cs[w])
            conf = read(cs[w] + "/config.yaml")
            check(sorted(p["name"] for p in prox) == want and len(lst) == len(want), f"{w} has {len(want)} outbounds and inbounds")
            check(all(f'"name": "{n}"' in conf for n in want) and conf.count("cg-cluster-") == len(want), f"{w}'s live config has them")
            check(all(listening(x["port"]) for x in lst), f"{w}'s core listens on its cluster ports")
            for o in names:
                if o != w:
                    out = traffic(w, f"{o}-Node")
                    check(out.endswith("\n200") and "hello-through-cluster" in out, f"traffic {w} -> {o}"
                          + ("" if out.endswith("\n200") else f" ({out[-200:]!r})"))

    print("[name validation]")
    for bad in ("x" * 16, "DIRECT", "a\nb", "a\u200bb", ""):
        r = a.post("/action/settings", node_name=bad)
        check(not r["ok"], f"rejects node name {bad!r}: {r['msg']}")
    r = a.post("/action/settings", node_name="A-Node")
    check(r["ok"] and r["state"]["cluster"]["node_name"] == "A-Node", "saves node name A-Node")
    check(a.state["cluster"]["self_url"] == url["A"], f"A announces {a.state['cluster']['self_url']}")

    print("[error paths]")
    r = a.post("/cluster/add", url="http://" + HOSTS["B"], password="x")
    check(not r["ok"] and "https://" in r["msg"], f"plain http refused: {r['msg']}")
    r = a.post("/cluster/add", url=url["B"], password="wrong-password")
    check(not r["ok"] and "密码错误" in r["msg"], f"wrong password: {r['msg']}")
    r = a.post("/cluster/add", url=f"https://{HOSTS['A']}:1", password="x")
    check(not r["ok"] and "连接" in r["msg"], f"unreachable: {r['msg']}")
    r = a.post("/cluster/add", url=url["BAD"], password="x")
    check(not r["ok"] and "证书" in r["msg"], f"untrusted certificate: {r['msg']}")
    r = a.post("/cluster/add", url=url["A"], password=PW["A"])
    check(not r["ok"] and "本机" in r["msg"], f"self refused: {r['msg']}")
    if old_dir:
        r = a.post("/cluster/add", url=url["OLD"], password="x")
        check(not r["ok"] and "太旧" in r["msg"], f"old panel: {r['msg']}")
    env_a = read(cs["A"] + "/clashgate.env")
    with open(cs["A"] + "/clashgate.env", "w") as f:
        f.write(env_a.replace(HOSTS["A"], "127.0.0.9"))
    r = a.post("/cluster/add", url=url["B"], password=PW["B"])
    check(not r["ok"] and "连回" in r["msg"], f"announced address that does not lead back: {r['msg']}")
    with open(cs["A"] + "/clashgate.env", "w") as f:
        f.write(env_a)
    check(not member_names(b), "B kept nothing from the failed attempt")
    b.post("/action/settings", custom_server_enabled="1")
    r = a.post("/cluster/add", url=url["B"], password=PW["B"])
    check(not r["ok"] and "自定义服务端" in r["msg"], f"remote in custom-server mode: {r['msg']}")
    b.post("/action/settings", custom_server_enabled="0")
    a.post("/action/settings", custom_server_enabled="1")
    r = a.post("/cluster/add", url=url["B"], password=PW["B"])
    check(not r["ok"] and "自定义服务端" in r["msg"], f"local custom-server lock: {r['msg']}")
    a.post("/action/settings", custom_server_enabled="0")

    print("[A adds B: two-way link, with an unpublished draft on A]")
    r = a.post("/inbounds/add", kind="shadowsocks", name="DraftSS", port="30555")
    check(r["ok"] and r["state"]["pending_reload_count"] == 1, "draft inbound pending on A")
    t0 = time.time()
    r = a.post("/cluster/add", url=url["B"], password=PW["B"])
    check(r["ok"] and "双向" in r["msg"], f"add B to A: {r['msg']} ({time.time() - t0:.1f}s)")
    st = r["state"]
    check(all(p["name"] != "B-Node" for p in st["proxies"]), "member not in A's outbound list")
    check(st["pending_reload_count"] == 1, "draft still pending on A")
    check("DraftSS" not in read(cs["A"] + "/config.yaml"), "A's draft inbound was not published")
    conf_a = read(cs["A"] + "/config.yaml")
    check("mlkem768x25519plus.native.0rtt." in conf_a and "mlkem768x25519plus.native.600s." in conf_a, "A has both PQ outbound and inbound")
    mesh_ok(["A", "B"])
    lst_b = cluster_frags(cs["B"])[1]
    check(all(i["port"] != lst_b[0]["port"] for i in state(b)["inbounds"]), "cluster inbound not in B's node list")
    check(all(p["name"] != "A-Node" for p in b.state["proxies"]), "cluster outbound not in B's outbound list")
    for who in ("A", "B"):
        with cl[who].op.open(cl[who].base + f"/sub/{'t' * 24 + who}/mihomo.yaml", timeout=30) as resp:
            sub = resp.read().decode()
        secrets_ = [p["encryption"] for p in cluster_frags(cs[who])[0]] + [x["decryption"] for x in cluster_frags(cs[who])[1]]
        check("A-Node" not in sub and "B-Node" not in sub and "cg-cluster" not in sub and not any(k in sub for k in secrets_),
              f"{who}'s subscription has no cluster entries")
    check("cluster" not in json.dumps(a.get("/api/status")).lower(), "/api/status lists no cluster entries")
    for w in ("A", "B"):
        raw = read(cs[w] + "/cluster.json")
        check(not any(pw in raw for pw in PW.values()), f"{w} stores no panel password")
    pub = json.dumps(a.state["cluster"])
    check("key" not in pub and "uuid" not in pub and "mlkem" not in pub, "browser state has no keys")
    proxy = [p for p in cluster_frags(cs["A"])[0] if p["name"] == "B-Node"][0]
    broken = dict(proxy, encryption=re.sub(r"\.[A-Za-z0-9_-]{20}$", ".AAAAAAAAAAAAAAAAAAAA", proxy["encryption"]),
                  uuid="00000000-0000-4000-8000-000000000000")
    out = curl_via(broken, f"http://127.0.0.1:{port_t}/")
    check(not out.endswith("\n200") and "did not start" not in out, "wrong uuid/key is rejected")
    out = curl_via(proxy, "http://www.gstatic.com/generate_204")
    print(f"  info internet generate_204 via cluster: HTTP {out.strip()[-3:] or 'none'}")

    print("[discard drafts / reload keep the cluster]")
    r = a.post("/action/discard-pending")
    check(r["ok"] and r["state"]["pending_reload_count"] == 0, "discard drafts")
    check('"name": "B-Node"' in read(cs["A"] + "/config.yaml"), "cluster outbound survives discard")
    r = a.post("/action/reload")
    check(r["ok"] and '"name": "B-Node"' in read(cs["A"] + "/config.yaml"), f"cluster outbound survives reload: {r['msg']}")

    print("[C adds A: C is linked with A and B automatically]")
    t0 = time.time()
    r = c.post("/cluster/add", url=url["A"], password=PW["A"])
    check(r["ok"] and "B-Node" in r["msg"], f"add A to C: {r['msg']} ({time.time() - t0:.1f}s)")
    mesh_ok(["A", "B", "C"])

    print("[duplicates, name clash, renames]")
    r = c.post("/cluster/add", url=url["B"], password=PW["B"])
    check(not r["ok"] and "已经在集群里" in r["msg"], f"duplicate refused: {r['msg']}")
    r = a.post("/proxies/add", proxies_raw='- {"name":"B-Node","type":"socks5","server":"127.0.0.1","port":1080}')
    check(not r["ok"] and "集群" in r["msg"], f"server outbound cannot take a member name: {r['msg']}")
    r = b.post("/action/settings", node_name="B-东京")
    check(r["ok"] and "通知" in r["msg"], f"B renames itself: {r['msg']}")
    check(wait_for(lambda: all('"name": "B-东京"' in read(cs[w] + "/config.yaml") for w in ("A", "C"))),
          "A and C renamed B's outbound")
    a.post("/proxies/add", proxies_raw='- {"name":"Taken","type":"socks5","server":"127.0.0.1","port":1080}')
    a.post("/action/reload")
    b.post("/action/settings", node_name="Taken")
    check(wait_for(lambda: '"name": "Taken"' in read(cs["C"] + "/config.yaml")), "C took the new name")
    check('"name": "B-东京"' in read(cs["A"] + "/config.yaml"), "A kept the old name (it clashes with A's own outbound)")
    for sym in ('B,"\'[]{}#|<>🚀', "B:&*!%@`~ $^ 1"):
        r = b.post("/action/settings", node_name=sym)
        check(r["ok"], f"B takes a name full of symbols {sym!r}: {r['msg']}")
        quoted = json.dumps(sym, ensure_ascii=False)
        check(wait_for(lambda: all(f'"name": {quoted}' in read(cs[w] + "/config.yaml") for w in ("A", "C"))),
              f"A and C write {sym!r} quoted into the live config")
        for w in ("A", "C"):
            check(member_names(cl[w]) == sorted([sym] + [f"{o}-Node" for o in ("A", "C") if o != w]), f"{w} lists {sym!r}")
            rc, out = mihomo_t(cs[w] + "/config.yaml")
            check(rc == 0, f"{w}'s config with {sym!r} passes mihomo -t" + ("" if rc == 0 else f": {out[-300:]}"))
            out = traffic(w, sym)
            check(out.endswith("\n200") and "hello-through-cluster" in out, f"traffic {w} -> {sym!r}")
    b.post("/action/settings", node_name="B-Node")
    check(wait_for(lambda: all('"name": "B-Node"' in read(cs[w] + "/config.yaml") for w in ("A", "C"))), "name back to B-Node")
    r = a.post("/cluster/sync")
    check(r["ok"] and "完整" in r["msg"], f"检查 on a healthy cluster: {r['msg']}")

    print("[D joins while C is offline, 检查 completes the mesh later]")
    stop_panel("C")
    r = d.post("/cluster/add", url=url["A"], password=PW["A"])
    check(r["ok"] and "没有完成" in r["msg"], f"add A to D: {r['msg']}")
    check(member_names(d) == ["A-Node", "B-Node"], "D is linked with A and B")
    check([p["name"] for p in d.state["cluster"]["pending"]] == ["C-Node"] and d.state["cluster"]["pending"][0]["error"],
          f"C shown as not linked yet: {d.state['cluster']['pending']}")
    r = a.post("/cluster/sync")
    check(r["ok"] and "C-Node" in r["msg"], f"检查 on A reports C offline: {r['msg']}")
    check([m for m in state(a)["cluster"]["members"] if m["name"] == "C-Node"][0]["ok"] is False, "A marks C offline")
    start_panel("C")
    r = d.post("/cluster/sync")
    check(r["ok"], f"检查 on D after C is back: {r['msg']}")
    check(not state(d)["cluster"]["pending"], "nothing pending on D")
    mesh_ok(["A", "B", "C", "D"])

    print("[remove D from the cluster on A]")
    r = a.post("/cluster/remove", id=[m for m in state(a)["cluster"]["members"] if m["name"] == "D-Node"][0]["id"])
    check(r["ok"] and "移出集群" in r["msg"], f"remove D: {r['msg']}")
    check(wait_for(lambda: all("D-Node" not in member_names(cl[w]) for w in ("A", "B", "C"))), "A, B and C dropped D")
    check(wait_for(lambda: not member_names(d)), "D dropped all its links")
    check(wait_for(lambda: "cg-cluster-" not in read(cs["D"] + "/config.yaml")), "D's config has no cluster entries")
    r = a.post("/cluster/sync")
    check(r["ok"] and "D-Node" not in member_names(a), f"检查 does not bring D back: {r['msg']}")

    print("[remove B while B is offline]")
    stop_panel("B")
    r = a.post("/cluster/remove", id=[m for m in state(a)["cluster"]["members"] if m["name"] == "B-Node"][0]["id"])
    check(r["ok"] and "联系不上" in r["msg"], f"remove offline B: {r['msg']}")
    check(member_names(a) == ["C-Node"] and member_names(c) == ["A-Node"], "A and C dropped B")
    start_panel("B")
    check(member_names(b) == ["A-Node", "C-Node"], "B still has its stale links while it was offline")
    r = b.post("/cluster/sync")
    check(r["ok"] and not member_names(b), f"B's 检查 learns it was removed: {r['msg']}")
    check("cg-cluster-" not in read(cs["B"] + "/config.yaml"), "B's config has no cluster entries")

    print("[re-add B with its password]")
    r = b.post("/cluster/add", url=url["A"], password=PW["A"])
    check(r["ok"], f"B adds A again: {r['msg']}")
    mesh_ok(["A", "B", "C"])

    print("[C leaves the cluster]")
    r = c.post("/cluster/leave")
    check(r["ok"] and "退出集群" in r["msg"], f"C leaves: {r['msg']}")
    check(not member_names(c) and member_names(a) == ["B-Node"] and member_names(b) == ["A-Node"], "C gone everywhere")
    mesh_ok(["A", "B"])

    print("[mihomo -t on final configs]")
    for who in ("A", "B", "C", "D"):
        check(mihomo_t(cs[who] + "/config.yaml")[0] == 0, f"{who} config passes mihomo -t")

    print()
    print("FAILED: %d" % len(FAILS) if FAILS else "all cluster e2e checks passed")
    return 1 if FAILS else 0


if __name__ == "__main__":
    rc = 2
    try:
        rc = main()
    finally:
        for p in PROCS:
            p.terminate()
        for who in ("A", "B", "C", "D"):
            env = panel_env(f"{TMP}/{who}")
            subprocess.run([TMP + "/bin/systemctl", "stop", "mihomo"], env=env)
        if rc == 0:
            shutil.rmtree(TMP, ignore_errors=True)
        else:
            print("logs kept in", TMP)
    sys.exit(rc)
