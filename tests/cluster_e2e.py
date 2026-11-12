#!/usr/bin/env python3
"""ClashGate cluster end-to-end test on one machine, as a normal user, everything in a temp dir.

  python3 tests/cluster_e2e.py            # needs openssl, ss, curl and the pinned core (tests/run.sh downloads it)

Starts panel A on 127.0.0.1 and panel B on 127.0.0.2 over HTTPS (certificates from a throw-away CA
that only these processes trust), each with its own real Mihomo core driven by a fake systemctl.
Adds B to A through A's own HTTP API, then sends traffic through A's cluster outbound with a third
core and checks the error paths (wrong password, old panel, bad certificate, unreachable, duplicate,
name clash, custom-server lock), draft isolation, rename, and removal on both sides.
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
PW = {"A": "pw-A-" + os.urandom(6).hex(), "B": "pw-B-" + os.urandom(6).hex()}
HOSTS = {"A": "127.0.0.1", "B": "127.0.0.2", "OLD": "127.0.0.3", "BAD": "127.0.0.4"}
PORTS = {"A": 28401, "B": 28402, "OLD": 28403, "BAD": 28404}
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
    for who in ("A", "B", "OLD"):
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
    p = subprocess.Popen([sys.executable, panel_dir + "/panel.py", "serve", "--config", cs + "/panel.json"],
                         env=env, stdout=open(root + "/panel.log", "w"), stderr=subprocess.STDOUT)
    PROCS.append(p)
    for _ in range(100):
        try:
            socket.create_connection((HOSTS[who], PORTS[who]), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    return root


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


def curl_via(proxy_dict, url):
    """Run a client core with only this outbound and fetch url through it."""
    d = tempfile.mkdtemp(dir=TMP)
    port = 27900 + len(os.listdir(TMP))
    with open(d + "/c.yaml", "w") as f:
        f.write(f"mixed-port: {port}\nmode: rule\nlog-level: warning\nproxies:\n  - {json.dumps(proxy_dict)}\n"
                f"rules:\n  - {json.dumps('MATCH,' + proxy_dict['name'], ensure_ascii=False)}\n")
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


def main():
    if not os.path.isfile(MIHOMO):
        sys.exit(f"core not found: {MIHOMO}")
    os.makedirs(TMP + "/bin")
    with open(TMP + "/bin/systemctl", "w") as f:
        f.write(FAKE_SYSTEMCTL)
    os.chmod(TMP + "/bin/systemctl", 0o755)
    pki = make_certs()
    panel_dir = os.path.join(REPO, "panel")
    root_a = setup_panel("A", panel_dir, pki)
    root_b = setup_panel("B", panel_dir, pki)
    old_dir = os.environ.get("CG_OLD_PANEL_DIR")
    if old_dir:
        setup_panel("OLD", old_dir, pki, init_state=False)
    bad_tls_server(pki)
    cs_a, cs_b = root_a + "/etc/clashgate", root_b + "/etc/clashgate"
    a, b = Client("A"), Client("B")
    url_b = f"https://{HOSTS['B']}:{PORTS['B']}"

    print("[name validation]")
    for bad in ("a,b", "x" * 21, "DIRECT", 'q"q', ""):
        r = a.post("/action/settings", node_name=bad)
        check(not r["ok"], f"rejects node name {bad!r}: {r['msg']}")
    r = a.post("/action/settings", node_name="A-Node")
    check(r["ok"] and r["state"]["cluster"]["node_name"] == "A-Node", "saves node name A-Node")

    print("[error paths]")
    r = a.post("/cluster/add", url="http://" + HOSTS["B"], password="x")
    check(not r["ok"] and "https://" in r["msg"], f"plain http refused: {r['msg']}")
    r = a.post("/cluster/add", url=url_b, password="wrong-password")
    check(not r["ok"] and "密码错误" in r["msg"], f"wrong password: {r['msg']}")
    r = a.post("/cluster/add", url=f"https://{HOSTS['A']}:1", password="x")
    check(not r["ok"] and "连接" in r["msg"], f"unreachable: {r['msg']}")
    r = a.post("/cluster/add", url=f"https://{HOSTS['BAD']}:{PORTS['BAD']}", password="x")
    check(not r["ok"] and "证书" in r["msg"], f"untrusted certificate: {r['msg']}")
    r = a.post("/cluster/add", url=f"https://{HOSTS['A']}:{PORTS['A']}", password=PW["A"])
    check(not r["ok"] and "本机" in r["msg"], f"self refused: {r['msg']}")
    if old_dir:
        r = a.post("/cluster/add", url=f"https://{HOSTS['OLD']}:{PORTS['OLD']}", password="x")
        check(not r["ok"] and "太旧" in r["msg"], f"old panel: {r['msg']}")
    r = b.post("/action/settings", custom_server_enabled="1")
    r = a.post("/cluster/add", url=url_b, password=PW["B"])
    check(not r["ok"] and "自定义服务端" in r["msg"], f"remote in custom-server mode: {r['msg']}")
    b.post("/action/settings", custom_server_enabled="0")
    a.post("/action/settings", custom_server_enabled="1")
    r = a.post("/cluster/add", url=url_b, password=PW["B"])
    check(not r["ok"] and "自定义服务端" in r["msg"], f"local custom-server lock: {r['msg']}")
    a.post("/action/settings", custom_server_enabled="0")

    print("[add with an unpublished draft on A]")
    r = a.post("/inbounds/add", kind="shadowsocks", name="DraftSS", port="30555")
    check(r["ok"] and r["state"]["pending_reload_count"] == 1, "draft inbound pending on A")
    t0 = time.time()
    r = a.post("/cluster/add", url=url_b, password=PW["B"])
    check(r["ok"], f"add B to A: {r['msg']} ({time.time() - t0:.1f}s)")
    st = r["state"]
    check([m["name"] for m in st["cluster"]["members"]] == ["B-Node"], "A lists member B-Node")
    check(all(p["name"] != "B-Node" for p in st["proxies"]), "member not in A's outbound list")
    check(st["pending_reload_count"] == 1, "draft still pending on A")
    conf_a = read(cs_a + "/config.yaml")
    check('"name": "B-Node"' in conf_a and "mlkem768x25519plus.native.0rtt." in conf_a, "A's live config has the B-Node outbound")
    check("DraftSS" not in conf_a, "A's draft inbound was not published")
    conf_b = read(cs_b + "/config.yaml")
    peer_port = st["cluster"]["members"][0]["port"]
    check("cg-cluster-" in conf_b and "mlkem768x25519plus.native.600s." in conf_b, "B's live config has the cluster listener")
    check(listening(peer_port), f"B's core listens on cluster port {peer_port}")
    b.state = b.get("/api/state")
    check([p["name"] for p in b.state["cluster"]["peers"]] == ["A-Node"], "B lists peer A-Node")
    check(all(i["port"] != peer_port for i in b.state["inbounds"]), "cluster inbound not in B's node list")
    for who, cl in (("A", a), ("B", b)):
        with cl.op.open(cl.base + f"/sub/{'t' * 24 + who}/mihomo.yaml", timeout=30) as resp:
            sub = resp.read().decode()
        check("B-Node" not in sub and "cg-cluster" not in sub and "mlkem768x25519plus.native.600s" not in sub,
              f"{who}'s subscription has no cluster entries")
    check("cluster" not in json.dumps(a.get("/api/status")).lower(), "/api/status lists no cluster entries")
    with open(cs_b + "/cluster.json") as f:
        check("pw-B" not in f.read(), "B stores no password")
    with open(cs_a + "/cluster.json") as f:
        check(PW["B"] not in f.read(), "A stores no remote password, only a token")

    print("[traffic through the cluster outbound]")
    proxy = json.loads(read(cs_a + "/proxies.cluster.yaml").strip()[2:])
    port_t = target_server()
    out = curl_via(proxy, f"http://127.0.0.1:{port_t}/")
    check(out.endswith("\n200") and "hello-through-cluster" in out, "HTTP via A's B-Node outbound reaches the target")
    broken = dict(proxy, encryption=re.sub(r"\.[A-Za-z0-9_-]{20}$", ".AAAAAAAAAAAAAAAAAAAA", proxy["encryption"]))
    broken["uuid"] = "00000000-0000-4000-8000-000000000000"
    out = curl_via(broken, f"http://127.0.0.1:{port_t}/")
    check(not out.endswith("\n200") and "did not start" not in out, "wrong uuid/key is rejected by B")
    out = curl_via(proxy, "http://www.gstatic.com/generate_204")
    print(f"  info internet generate_204 via cluster: HTTP {out.strip()[-3:] or 'none'}")

    print("[discard drafts / reload keep the cluster]")
    r = a.post("/action/discard-pending")
    check(r["ok"] and r["state"]["pending_reload_count"] == 0, "discard drafts")
    check('"name": "B-Node"' in read(cs_a + "/config.yaml"), "cluster outbound survives discard")
    r = a.post("/action/reload")
    check(r["ok"] and '"name": "B-Node"' in read(cs_a + "/config.yaml"), f"cluster outbound survives reload: {r['msg']}")

    print("[duplicates, name clash, rename]")
    r = a.post("/cluster/add", url=url_b, password=PW["B"])
    check(not r["ok"] and "已经添加过" in r["msg"], f"duplicate refused: {r['msg']}")
    r = a.post("/proxies/add", proxies_raw='- {"name":"B-Node","type":"socks5","server":"127.0.0.1","port":1080}')
    check(not r["ok"] and "集群" in r["msg"], f"server outbound cannot take a member name: {r['msg']}")
    a.post("/proxies/add", proxies_raw='- {"name":"Taken","type":"socks5","server":"127.0.0.1","port":1080}')
    a.post("/action/reload")
    b.post("/action/settings", node_name="Taken")
    mid = a.state["cluster"]["members"][0]["id"]
    r = a.post("/cluster/refresh", id=mid)
    check(not r["ok"] and "重名" in r["msg"], f"rename clash detected: {r['msg']}")
    b.post("/action/settings", node_name="B-东京")
    r = a.post("/cluster/refresh", id=mid)
    check(r["ok"] and a.state["cluster"]["members"][0]["name"] == "B-东京", f"rename picked up: {r['msg']}")
    check('"name": "B-东京"' in read(cs_a + "/config.yaml"), "A's config uses the new name")
    r = a.post("/cluster/refresh", id=mid)
    check(r["ok"] and "在线" in r["msg"], f"refresh: {r['msg']}")

    print("[remove from A]")
    r = a.post("/cluster/remove", id=mid)
    check(r["ok"] and "也已删除" in r["msg"], f"remove: {r['msg']}")
    check("B-东京" not in read(cs_a + "/config.yaml"), "outbound gone from A")
    check("cg-cluster-" not in read(cs_b + "/config.yaml"), "listener gone from B")
    time.sleep(0.5)
    check(not listening(peer_port), "B no longer listens on the cluster port")

    print("[remove from B's side first]")
    r = a.post("/cluster/add", url=url_b, password=PW["B"])
    check(r["ok"], f"re-add: {r['msg']}")
    b.state = b.get("/api/state")
    r = b.post("/cluster/peer-remove", id=b.state["cluster"]["peers"][0]["id"])
    check(r["ok"] and not r["state"]["cluster"]["peers"], f"B removes the peer: {r['msg']}")
    mid = a.state["cluster"]["members"][0]["id"]
    r = a.post("/cluster/refresh", id=mid)
    check(not r["ok"] and "不认" in r["msg"], f"A sees the link is gone: {r['msg']}")
    r = a.post("/cluster/remove", id=mid)
    check(r["ok"], f"A removes it (B already deleted its side): {r['msg']}")
    check(not a.state["cluster"]["members"], "A has no members")

    print("[remove while the remote panel is down]")
    r = a.post("/cluster/add", url=url_b, password=PW["B"])
    check(r["ok"], f"re-add: {r['msg']}")
    PROCS[1].terminate()
    PROCS[1].wait()
    r = a.post("/cluster/remove", id=a.state["cluster"]["members"][0]["id"])
    check(r["ok"] and "没能" in r["msg"] and not r["state"]["cluster"]["members"],
          f"local side removed, remote cleanup reported as failed: {r['msg']}")

    print("[mihomo -t on final configs]")
    for who, cs in (("A", cs_a), ("B", cs_b)):
        d = tempfile.mkdtemp(dir=TMP)
        rc = subprocess.run([MIHOMO, "-t", "-d", d, "-f", cs + "/config.yaml"], capture_output=True).returncode
        check(rc == 0, f"{who} config passes mihomo -t")

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
        for who in ("A", "B"):
            env = panel_env(f"{TMP}/{who}")
            subprocess.run([TMP + "/bin/systemctl", "stop", "mihomo"], env=env)
        if rc == 0:
            shutil.rmtree(TMP, ignore_errors=True)
        else:
            print("logs kept in", TMP)
    sys.exit(rc)
