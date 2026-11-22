"""Cluster protocol between panels. Moved out of panel.py unchanged."""
import hashlib
import json
import os
import re
import secrets
import socket
import ssl
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid as uuidlib
from urllib.parse import urlparse


def bind():
    """Pull path constants and helpers from the loaded panel module.

    Called once panel.py has finished defining them. Running `python3 panel.py`
    aliases that module as `panel`, so this sees the same objects.
    """
    mod = sys.modules.get("panel") or sys.modules.get("__main__")
    g = globals()
    for key, val in mod.__dict__.items():
        if key.startswith("__") or key in g:
            continue
        g[key] = val


# ---------------------------------------------------------------- cluster (集群, 1.14)
# Panels that know each other form one cluster. Every pair of panels in the cluster has one *link*:
# each side runs a dedicated VLESS inbound with post-quantum VLESS Encryption (mlkem768x25519plus,
# ML-KEM-768 key) for the other side, and an outbound to the other side's inbound, named after the
# other side's 本机名称. Links live in cluster.json and their own fragments, never in inbounds.json /
# proxies.json, so they stay out of the node list, the outbound list and the client subscription.
# Changes are applied to the running core right away (the other side has nobody to click "reload").
#
# Pairing: the user adds one panel with its password; after that the panel that did the work brings
# the cluster to a full mesh with the links it already has (a member that knows both sides vouches
# with a one-time ticket, so no further passwords are needed). Requests between panels are HTTPS with
# normal certificate verification, and each side checks that the other's announced panel URL really
# reaches it (hello + instance id) before it writes an outbound for it.
CLUSTER_PROTOCOL = 2          # 2: two-way links and full mesh (1 was the one-way pre-release)
CLUSTER_MIN_VERSION = "1.15"
CLUSTER_LISTENER_PREFIX = "cg-cluster-"
CLUSTER_FLOW = "xtls-rprx-vision"
CLUSTER_TICKET_TTL = 300
CLUSTER_TOMBSTONE_TTL = 30 * 86400
_CLUSTER_OP_LOCK = threading.Lock()   # one user-started cluster job at a time (never held with LOCK while waiting on a remote)
_CLUSTER_TICKETS = {}                 # sha256(ticket) -> (instance allowed to join, expiry); in memory only
_CLUSTER_TICKETS_LOCK = threading.Lock()
_CLUSTER_PORT_HOLD = set()            # ports picked for a link that is still being negotiated
_INST_RE = re.compile(r"[0-9a-f]{32}")
_ENC_RE = re.compile(r"mlkem768x25519plus\.[A-Za-z0-9._=-]+")


def load_cluster() -> dict:
    out = {"instance": "", "links": [], "pending": [], "removed": {}}
    try:
        with open(CLUSTER_JSON) as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            out["instance"] = str(raw.get("instance") or "")
            out["links"] = [l for l in (raw.get("links") or []) if isinstance(l, dict) and l.get("id")
                            and isinstance(l.get("in"), dict) and isinstance(l.get("out"), dict)]
            out["pending"] = [p for p in (raw.get("pending") or []) if isinstance(p, dict)]
            now = time.time()
            out["removed"] = {k: v for k, v in (raw.get("removed") or {}).items()
                              if _INST_RE.fullmatch(str(k)) and isinstance(v, (int, float)) and now - v < CLUSTER_TOMBSTONE_TTL}
    except FileNotFoundError:
        pass
    except (ValueError, OSError) as e:
        sys.stderr.write(f"cluster.json unreadable: {e}\n")
    return out


def cluster_instance_id() -> str:
    """Random id of this panel, so a panel can recognise itself and a re-join replaces the old link."""
    with _CLUSTER_TICKETS_LOCK:
        st = load_cluster()
        if not _INST_RE.fullmatch(st["instance"]):
            st["instance"] = secrets.token_hex(16)
            save_cluster(st)
        return st["instance"]


def cluster_proxy_from_link(l: dict) -> dict:
    """Outbound to the other panel (Mihomo docs: config/proxies/vless, `encryption`)."""
    out = l.get("out") or {}
    return {
        "name": str(l.get("name") or ""),
        "type": "vless",
        "server": str(out.get("server") or ""),
        "port": int(out.get("port") or 0),
        "uuid": str(out.get("uuid") or ""),
        "flow": CLUSTER_FLOW,
        "packet-encoding": "xudp",
        "encryption": str(out.get("encryption") or ""),
        "network": "tcp",
        "udp": True,
    }


def cluster_listener_from_link(l: dict) -> dict:
    """Dedicated inbound for the other panel (Mihomo docs: config/inbound/listeners/vless, `decryption`)."""
    inb = l.get("in") or {}
    return {
        "name": CLUSTER_LISTENER_PREFIX + str(l["id"]),
        "type": "vless",
        "port": int(inb["port"]),
        "listen": "0.0.0.0",
        "users": [{"username": "cluster", "uuid": str(inb["uuid"]), "flow": CLUSTER_FLOW}],
        "decryption": str(inb["decryption"]),
    }


def render_cluster_proxies(st: dict) -> str:
    return "".join("  - " + json.dumps(cluster_proxy_from_link(l), ensure_ascii=False) + "\n"
                   for l in st.get("links") or [])


def render_cluster_listeners(st: dict) -> str:
    return "".join("  - " + json.dumps(cluster_listener_from_link(l), ensure_ascii=False) + "\n"
                   for l in st.get("links") or [])


def save_cluster(st: dict):
    """cluster.json (0600: holds link keys) plus both fragments; does not touch the running core."""
    data = {"instance": st.get("instance") or "", "links": st.get("links") or [],
            "pending": st.get("pending") or [], "removed": st.get("removed") or {}}
    atomic_write(CLUSTER_JSON, json.dumps(data, indent=2, ensure_ascii=False) + "\n", 0o600)
    atomic_write(FRAG_CLUSTER_PROXIES, render_cluster_proxies(data), 0o640)
    atomic_write(FRAG_CLUSTER_LISTENERS, render_cluster_listeners(data), 0o640)


def _read_frag(path: str, files: dict = None) -> str:
    if files is not None and path in files:
        return files[path] or ""
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        return ""


def cluster_proxy_names() -> set:
    return {str(l.get("name") or "") for l in load_cluster()["links"]}


def cluster_ports(st: dict = None) -> set:
    st = st or load_cluster()
    return {int(l["in"]["port"]) for l in st["links"] if (l.get("in") or {}).get("port")}


def cluster_ufw_specs(st: dict = None) -> set:
    return {f"{p}/tcp" for p in cluster_ports(st)}


def vless_mlkem768_pair() -> tuple:
    """(server decryption, client encryption) from `mihomo generate vless-mlkem768` (its Lazy-Config:
    mlkem768x25519plus.native.600s.<ML-KEM-768 seed> / mlkem768x25519plus.native.0rtt.<client key>)."""
    rc, out = run([resolve_mihomo_bin(), "generate", "vless-mlkem768"])
    dec = re.search(r'\[Server\]\s*decryption:\s*"([^"]+)"', out)
    enc = re.search(r'\[Client\]\s*encryption:\s*"([^"]+)"', out)
    if rc != 0 or not dec or not enc or not dec.group(1).startswith("mlkem768x25519plus."):
        raise RuntimeError("当前内核不支持 VLESS 后量子加密（vless-mlkem768），请先到「设置」页点「更新内核」")
    return dec.group(1), enc.group(1)


def used_proxy_names() -> set:
    """Names a new outbound must not take: server outbounds, cluster members, proxy groups, built-ins."""
    names = {str(p.get("name") or "") for p in load_server_proxies()} | cluster_proxy_names()
    names |= RESERVED_PROXY_NAMES
    try:
        _, pg_block, _ = get_routing().read_frags()
        for m in re.finditer(r"^\s*-\s*name:\s*(.+?)\s*$", pg_block, re.M):
            v = m.group(1)
            try:
                v = json.loads(v) if v.startswith('"') else v.strip("'")
            except ValueError:
                pass
            names.add(str(v))
    except Exception as e:
        sys.stderr.write(f"routing names unavailable: {e}\n")
    if is_custom_config_mode():   # the user's own proxy groups and outbounds
        try:
            with open(CUSTOM_CONF) as f:
                raw = f.read()
            for sec in ("proxy-groups", "proxies"):
                items = extract_top_level_yaml_section(raw, sec)
                for g in items if isinstance(items, list) else []:
                    if isinstance(g, dict) and g.get("name") and str(g["name"]) not in cluster_proxy_names():
                        names.add(str(g["name"]))
        except Exception as e:
            sys.stderr.write(f"custom config names unavailable: {e}\n")
    return {n for n in names if n}


def _live_conf_with_cluster() -> str:
    """The running config with only the cluster entries changed.

    No unsaved drafts: the fragments are the live state, so just assemble. With drafts: take the live
    config.yaml and rebuild only its listeners / proxies sections from the pre-draft baseline plus the
    current cluster fragments, so the user's unpublished edits stay unpublished."""
    pend = load_pending_reload()
    has_pending = bool(pend["items"] or pend["sub_token"] or pend["mihomo_secret"])
    if not has_pending or not os.path.isfile(PENDING_BASELINE_JSON) or not os.path.isfile(CONF):
        return assemble_config()
    with open(PENDING_BASELINE_JSON) as f:
        files = json.load(f).get("files") or {}
    with open(CONF) as f:
        live = f.read()
    lst = "".join(_read_frag(p, files) for p in (FRAG_REALITY, FRAG_EXTRA)) + _read_frag(FRAG_CLUSTER_LISTENERS)
    prox = "\n".join(l for l in (_read_frag(FRAG_PROXIES, files) + "\n" + _read_frag(FRAG_CLUSTER_PROXIES)).splitlines()
                     if l.strip())
    live = replace_top_level_yaml_section(live, "listeners", ("listeners:\n" + lst) if lst.strip() else "listeners: []\n")
    live = replace_top_level_yaml_section(live, "proxies", ("proxies:\n" + prox + "\n") if prox.strip() else "proxies: []\n")
    return live


def _cluster_ports_ready(want: set) -> bool:
    return not want or want.issubset(set(mihomo_status()["listening"]))


def _wait_cluster_ports(want: set, timeout: float = 8.0) -> bool:
    """Wait until every cluster inbound is actually listening, or timeout."""
    if not want:
        return True
    deadline = time.monotonic() + timeout
    while True:
        if _cluster_ports_ready(want):
            return True
        if time.monotonic() >= deadline:
            return _cluster_ports_ready(want)
        time.sleep(0.15)


def custom_conf_with_cluster(raw: str, old_names: set = None) -> str:
    """A user's full server config (custom mode) with the cluster entries replaced by cluster.json:
    cluster listeners (CLUSTER_LISTENER_PREFIX) and member outbounds (names in old_names, default the
    current members) are dropped, the current ones appended. The user's own entries and every other
    section stay as written; the user's proxy-groups choose whether to use the members (e.g. include-all)."""
    st = load_cluster()
    old = set(old_names if old_names is not None else cluster_proxy_names())
    lst = extract_top_level_yaml_section(raw, "listeners")
    prox = extract_top_level_yaml_section(raw, "proxies")
    lst = [x for x in (lst if isinstance(lst, list) else [])
           if not (isinstance(x, dict) and str(x.get("name") or "").startswith(CLUSTER_LISTENER_PREFIX))]
    prox = [p for p in (prox if isinstance(prox, list) else [])
            if not (isinstance(p, dict) and str(p.get("name") or "") in old)]
    l_body = dump_yaml_proxies(lst + [cluster_listener_from_link(l) for l in st["links"]])
    p_body = dump_yaml_proxies(prox + [cluster_proxy_from_link(l) for l in st["links"]])
    raw = replace_top_level_yaml_section(raw, "listeners", ("listeners:\n" + l_body) if l_body.strip() else "listeners: []\n")
    return replace_top_level_yaml_section(raw, "proxies", ("proxies:\n" + p_body) if p_body.strip() else "proxies: []\n")


def apply_cluster_live(old_specs: set, old_names: set = None):
    """Write the cluster change into config.yaml, validate, reload the core, update the firewall.
    In custom mode the user's file gets only the cluster entries replaced (custom_conf_with_cluster).
    Caller holds LOCK and has already saved cluster.json; raises (config restored) on failure."""
    custom = is_custom_config_mode()
    try:
        with open(CONF) as f:
            backup = f.read()
    except FileNotFoundError:
        backup = None
    custom_backup = None
    if custom:
        with open(CUSTOM_CONF) as f:
            custom_backup = f.read()
        new_conf = custom_conf_with_cluster(custom_backup, old_names)
        atomic_write(CUSTOM_CONF, new_conf, 0o640)
    else:
        new_conf = _live_conf_with_cluster()

    def restore():
        if backup is not None:
            atomic_write(CONF, backup, 0o640)
        if custom_backup is not None:
            atomic_write(CUSTOM_CONF, custom_backup, 0o640)

    atomic_write(CONF, new_conf, 0o640)
    rc, out = validate_config()
    if rc != 0:
        restore()
        raise RuntimeError("配置校验失败（mihomo -t）：" + out[-300:])
    st = load_cluster()
    rc, out = run([SYSTEMCTL, "reload", "mihomo"])
    if rc == 0:
        want = cluster_ports(st)
        if want and not _wait_cluster_ports(want):
            # Reload can return before the new inbound is bound, or bind can fail
            # (port already taken). Restart once, then fail rather than report success.
            rc, out = run([SYSTEMCTL, "restart", "mihomo"])
            if rc == 0 and not _wait_cluster_ports(want):
                rc = 1
                out = (out or "") + "集群入站端口未能在重载后开始监听"
    if rc != 0:
        restore()
        run([SYSTEMCTL, "restart", "mihomo"])
        raise RuntimeError("重载 Mihomo 失败：" + out[-300:])
    # Keep "discard drafts" working: the baseline must describe the config that is live now.
    if os.path.isfile(PENDING_BASELINE_JSON):
        try:
            with open(PENDING_BASELINE_JSON) as f:
                snap = json.load(f)
            snap["conf_sha256"] = _conf_digest()
            if custom and isinstance(snap.get("files"), dict) and CUSTOM_CONF in snap["files"]:
                snap["files"][CUSTOM_CONF] = new_conf
            atomic_write(PENDING_BASELINE_JSON, json.dumps(snap, ensure_ascii=False) + "\n", 0o600)
        except Exception as e:
            sys.stderr.write(f"pending baseline digest update failed: {e}\n")
    sync_ufw(old_specs, cluster_ufw_specs(st))


# -- outgoing requests to other panels (always HTTPS with normal certificate verification)
class ClusterError(Exception):
    """Error shown to the user as-is (Chinese source text, translated by i18n_en)."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def normalize_panel_url(raw: str) -> str:
    """'host:port' / 'https://host:port/whatever' -> 'https://host:port'. Plain HTTP is refused."""
    s = (raw or "").strip()
    if not s:
        raise ClusterError("请填写对方面板地址")
    if re.match(r"^http://", s, re.I):
        raise ClusterError("面板地址必须以 https:// 开头")
    if not re.match(r"^[a-z][a-z0-9+.-]*://", s, re.I):
        s = "https://" + s
    u = urlparse(s)
    if u.scheme.lower() != "https" or not u.hostname or u.username or u.password:
        raise ClusterError("面板地址格式不对，例如 https://example.com:8443")
    try:
        port = u.port
    except ValueError:
        raise ClusterError("面板地址格式不对，例如 https://example.com:8443")
    host = u.hostname.lower()
    if not (_SNI_HOST.fullmatch(host) or re.fullmatch(r"[0-9.]+", host) or ":" in host):
        raise ClusterError("面板地址格式不对，例如 https://example.com:8443")
    hp = f"[{host}]" if ":" in host else host
    return f"https://{hp}" + (f":{port}" if port and port != 443 else "")


def _cluster_ssl_context() -> ssl.SSLContext:
    # CLASHGATE_CLUSTER_CAFILE: extra trusted CA for local tests only; verification is never disabled.
    cafile = os.environ.get("CLASHGATE_CLUSTER_CAFILE") or None
    return ssl.create_default_context(cafile=cafile)


def cluster_http(base: str, path: str, data: dict = None, timeout: int = 15) -> tuple:
    """(status, json_or_None, server_header). Network / TLS problems raise ClusterError."""
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(base + path, data=body, method="POST" if data is not None else "GET",
                                 headers={"Accept": "application/json",
                                          "User-Agent": f"ClashGate/{VERSION} cluster",
                                          **({"Content-Type": "application/x-www-form-urlencoded"} if body else {})})
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=_cluster_ssl_context()), _NoRedirect)
    try:
        resp = opener.open(req, timeout=timeout)
        status, server, raw = resp.status, resp.headers.get("Server", ""), resp.read(1 << 20)
    except urllib.error.HTTPError as e:
        status, server = e.code, e.headers.get("Server", "") if e.headers else ""
        try:
            raw = e.read(1 << 20)
        except Exception:
            raw = b""
    except urllib.error.URLError as e:
        r = e.reason
        if isinstance(r, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in str(r):
            raise ClusterError("对方面板的 HTTPS 证书验证失败，请用对方证书上的域名访问（{}）".format(
                getattr(r, "verify_message", "") or str(r)[:120]))
        if isinstance(r, ssl.SSLError):
            raise ClusterError("和对方面板建立 HTTPS 连接失败（{}）".format(str(r)[:120]))
        if isinstance(r, (socket.timeout, TimeoutError)):
            raise ClusterError("连接对方面板超时，请检查地址、端口和对方防火墙")
        if isinstance(r, socket.gaierror):
            raise ClusterError("无法解析对方面板的域名，请检查地址")
        raise ClusterError("连接不上对方面板，请检查地址、端口和对方防火墙（{}）".format(str(r)[:120]))
    except (socket.timeout, TimeoutError):
        raise ClusterError("连接对方面板超时，请检查地址、端口和对方防火墙")
    except (ssl.SSLError, OSError) as e:
        raise ClusterError("连接不上对方面板，请检查地址、端口和对方防火墙（{}）".format(str(e)[:120]))
    try:
        obj = json.loads(raw.decode("utf-8"))
        if not isinstance(obj, dict):
            obj = None
    except (ValueError, UnicodeDecodeError):
        obj = None
    return status, obj, server


def cluster_hello(base: str) -> dict:
    status, obj, server = cluster_http(base, "/api/cluster/hello")
    if status == 200 and obj and obj.get("clashgate"):
        if int(obj.get("cluster") or 0) >= CLUSTER_PROTOCOL and _INST_RE.fullmatch(str(obj.get("instance") or "")):
            return obj
        raise ClusterError("对方面板的集群功能是旧的测试版，请先把对方面板更新到最新版本")
    m = re.match(r"clashgate/([0-9.]+)", server or "", re.I)
    if m:
        raise ClusterError(f"对方 ClashGate 版本是 {m.group(1)}，太旧了，请先把对方面板升级到 {CLUSTER_MIN_VERSION} 或更高")
    raise ClusterError("这个地址不是 ClashGate 面板，请检查地址和端口")


class ClusterRemoteError(ClusterError):
    def __init__(self, msg: str, code: str = ""):
        super().__init__(msg)
        self.code = code


def _remote_error(status: int, obj, fallback: str) -> ClusterError:
    code = str((obj or {}).get("code") or "")
    msg = str((obj or {}).get("msg") or "")[:300]
    if code == "bad_password":
        return ClusterRemoteError("对方面板密码错误", code)
    if code == "rate_limited" or status == 429:
        return ClusterRemoteError("对方面板尝试次数过多，请 10 分钟后再试", "rate_limited")
    if code == "custom_mode":
        return ClusterRemoteError("对方启用了自定义服务端配置，不能自动加入集群", code)
    if code == "bad_token":
        return ClusterRemoteError("对方面板已不认这条集群连接（可能已在对方那边删除）", code)
    if code == "bad_ticket":
        return ClusterRemoteError("集群邀请已失效，请点「检查」重试", code)
    if code in ("name_clash", "unreachable_back", "self", "bad_request", "left"):
        return ClusterRemoteError(msg or fallback, code)
    return ClusterRemoteError(f"{fallback}：{msg}" if msg else f"{fallback}（HTTP {status}）", code)


def local_cluster_url() -> str:
    """The HTTPS address other panels use to reach this panel: the domain, else the server IP."""
    env = read_env()
    cfg = getattr(Panel, "cfg", None) or {}
    url = panel_base_url(env, cfg)
    if not url and env.get("SERVER_IP"):
        port = int(cfg.get("port") or env.get("PANEL_PORT") or 8443)
        ip = env["SERVER_IP"]
        host = f"[{ip}]" if ":" in ip else ip
        url = f"https://{host}" if port == 443 else f"https://{host}:{port}"
    return url


def _link_by(st: dict, instance: str = "", lid: str = ""):
    for l in st["links"]:
        if (instance and l.get("instance") == instance) or (lid and l.get("id") == lid):
            return l
    return None


def cluster_members_view(st: dict, skip: str = "") -> list:
    """What this panel tells other members about the cluster (no secrets)."""
    return [{"instance": l["instance"], "name": l.get("name", ""), "url": l.get("url", ""), "since": l.get("created", 0)}
            for l in st["links"] if l.get("instance") != skip]


def _link_auth(l: dict) -> dict:
    return {"instance": cluster_instance_id(), "key": l.get("key", "")}


def cluster_call(l: dict, path: str, extra: dict = None, timeout: int = 30, fallback: str = "对方面板没有响应集群请求") -> dict:
    status, obj, _ = cluster_http(l["url"], path, {**_link_auth(l), **(extra or {})}, timeout=timeout)
    if status != 200 or not obj or not obj.get("ok"):
        raise _remote_error(status, obj, fallback)
    return obj


def _cluster_new_inbound() -> dict:
    """Keys and a free port for a new dedicated inbound (port held until the link is saved)."""
    dec, enc = vless_mlkem768_pair()
    with LOCK:
        port = pick_port(read_env())
        _CLUSTER_PORT_HOLD.add(port)
    return {"port": port, "uuid": str(uuidlib.uuid4()), "decryption": dec, "_enc": enc}


def _cluster_commit(mutate) -> dict:
    """Under LOCK: load, mutate(st) (may raise), save, apply live; restore everything on failure."""
    with LOCK:
        backup = _snapshot_files((CLUSTER_JSON, FRAG_CLUSTER_PROXIES, FRAG_CLUSTER_LISTENERS))
        st = load_cluster()
        old_specs = cluster_ufw_specs(st)
        old_names = {str(l.get("name") or "") for l in st["links"]}
        try:
            res = mutate(st)
            save_cluster(st)
            apply_cluster_live(old_specs, old_names)
        except Exception:
            _restore_files(backup)
            raise
        return res


def _parse_node(obj: dict, prefix: str = "") -> dict:
    try:
        port = int(obj.get(prefix + "port"))
        assert 1 <= port <= 65535
        uid = str(uuidlib.UUID(str(obj.get(prefix + "uuid"))))
        enc = str(obj.get(prefix + "encryption") or "")
        assert _ENC_RE.fullmatch(enc)
    except (AssertionError, TypeError, ValueError):
        raise ClusterError("对方面板返回的节点参数无效")
    return {"port": port, "uuid": uid, "encryption": enc}


def cluster_pair(base: str, auth: dict, expect_instance: str = "") -> tuple:
    """Create a two-way link with the panel at `base` (auth: password or one-time ticket).

    Returns (link, the other panel's member list). Raises ClusterError; nothing is left behind on failure."""
    hello = cluster_hello(base)
    r_inst = str(hello["instance"])
    if expect_instance and r_inst != expect_instance:
        raise ClusterError("对方面板的身份和集群记录不一致，请检查地址")
    my_inst = cluster_instance_id()
    if r_inst == my_inst:
        raise ClusterError("不能添加本机")
    try:
        rname = validate_peer_name(hello.get("name"))
    except ValueError:
        raise ClusterError("对方面板的本机名称无效，请先在对方面板的集群页重新填写")
    if _link_by(load_cluster(), instance=r_inst):
        raise ClusterError(f"「{rname}」已经在集群里了")
    if rname in used_proxy_names():
        raise ClusterError(f"对方的本机名称「{rname}」和本机已有的出站或分流组重名，请先在对方面板的集群页改个名字")
    self_url = local_cluster_url()
    if not self_url:
        raise ClusterError("本机没有可用的面板地址（域名或服务器 IP），其他面板无法连回本机")
    inb = _cluster_new_inbound()
    key = secrets.token_urlsafe(32)
    try:
        status, obj, _ = cluster_http(base, "/api/cluster/join", {
            **auth, "instance": my_inst, "name": local_node_name(), "url": self_url, "version": VERSION,
            "key": key, "port": inb["port"], "uuid": inb["uuid"], "encryption": inb["_enc"]}, timeout=120)
        if status != 200 or not obj or not obj.get("ok"):
            raise _remote_error(status, obj, "对方面板没能创建集群节点")
        node = _parse_node(obj.get("node") if isinstance(obj.get("node"), dict) else {})
        try:
            rname = validate_peer_name(obj.get("name") or rname)
        except ValueError:
            pass
        link = {"id": secrets.token_hex(6), "instance": r_inst, "name": rname, "url": base, "key": key,
                "version": str(obj.get("version") or hello.get("version") or ""), "created": int(time.time()),
                "seen": int(time.time()), "ok": True, "error": "", "missing": [],
                "in": {k: inb[k] for k in ("port", "uuid", "decryption")},
                "out": {"server": urlparse(base).hostname, **node}}

        def add(st):
            if _link_by(st, instance=r_inst):
                raise ClusterError(f"「{rname}」已经在集群里了")
            if rname in used_proxy_names():
                raise ClusterError(f"对方的本机名称「{rname}」和本机已有的出站或分流组重名，请先在对方面板的集群页改个名字")
            st["links"].append(link)
            st["pending"] = [p for p in st["pending"] if p.get("instance") != r_inst]
            st["removed"].pop(r_inst, None)
        try:
            _cluster_commit(add)
        except Exception as e:
            try:   # do not leave a half link on the other side
                cluster_http(base, "/api/cluster/leave", {"instance": my_inst, "key": key}, timeout=60)
            except ClusterError:
                pass
            if isinstance(e, ClusterError):
                raise
            raise ClusterError(f"添加失败：{e}")
    finally:
        _CLUSTER_PORT_HOLD.discard(inb["port"])
    members = [m for m in (obj.get("members") or []) if isinstance(m, dict) and _INST_RE.fullmatch(str(m.get("instance") or ""))]
    sys.stderr.write(f"cluster: linked with '{rname}' ({base})\n")
    return link, members


def cluster_issue_ticket(target: dict, joiner: dict) -> str:
    """Ask `target` (a linked panel) to accept one pairing from `joiner` (another link of ours); returns
    the ticket. `since` (when we linked with the joiner) lets target see that an old removal is over."""
    ticket = secrets.token_urlsafe(24)
    cluster_call(target, "/api/cluster/expect", {"from_instance": joiner["instance"], "since": int(joiner.get("created") or 0),
                                                  "ticket_hash": hashlib.sha256(ticket.encode()).hexdigest()})
    return ticket


def _drop_links(instances: set, tombstone: bool = False) -> list:
    """Remove the links to these panels here (both directions). Returns the removed links."""
    def drop(st):
        gone = [l for l in st["links"] if l.get("instance") in instances]
        st["links"] = [l for l in st["links"] if l.get("instance") not in instances]
        st["pending"] = [p for p in st["pending"] if p.get("instance") not in instances]
        if tombstone:
            for i in instances:
                st["removed"][i] = int(time.time())
        return gone
    if not any(l.get("instance") in instances for l in load_cluster()["links"]):
        if tombstone:
            with LOCK:
                st = load_cluster()
                for i in instances:
                    st["removed"][i] = int(time.time())
                save_cluster(st)
        return []
    return _cluster_commit(drop)


def cluster_leave_all(notify: bool = True) -> tuple:
    """This panel leaves the cluster: drop every link here, tell each member (best effort).
    Returns (number of links, names that could not be told)."""
    links = load_cluster()["links"]
    unreachable = []
    if notify:
        for l in links:
            try:
                cluster_call(l, "/api/cluster/leave", timeout=30)
            except ClusterError:
                unreachable.append(l.get("name", ""))
    _drop_links({l["instance"] for l in links})
    return len(links), unreachable


def _update_link(instance: str, **fields):
    """Store status fields on a link; a changed name is applied to the running config."""
    with LOCK:
        st = load_cluster()
        l = _link_by(st, instance=instance)
        if not l:
            return
        new_name = fields.pop("name", None)
        l.update(fields)
        rename = bool(new_name) and new_name != l.get("name") and new_name not in (used_proxy_names() - {l.get("name")})
        if not rename:
            save_cluster(st)
            return
    def ren(st2):
        x = _link_by(st2, instance=instance)
        if x:
            x.update(fields)
            x["name"] = new_name
    try:
        _cluster_commit(ren)
    except Exception as e:
        sys.stderr.write(f"cluster rename failed: {e}\n")


def cluster_sync() -> dict:
    """Check every member and bring the cluster to a full mesh. Call with _CLUSTER_OP_LOCK held.

    1. ask each member for its member list (also tells it our current name and URL);
    2. link this panel with every panel it does not know yet (a member that knows it issues a ticket);
    3. link members with each other where a link is missing (we issue the ticket, they connect).
    Members that are offline are left as they are and reported; a later 检查 retries."""
    rep = {"linked": [], "meshed": 0, "failed": [], "dropped": [], "offline": []}
    me = cluster_instance_id()
    views = {}
    st = load_cluster()
    removed = dict(st["removed"])
    for l in list(st["links"]):
        try:
            obj = cluster_call(l, "/api/cluster/status", {"name": local_node_name(), "url": local_cluster_url(), "version": VERSION}, timeout=20)
        except ClusterRemoteError as e:
            if e.code == "bad_token":   # the other side removed us: forget the link here too
                _drop_links({l["instance"]})
                rep["dropped"].append(l.get("name", ""))
                continue
            _update_link(l["instance"], ok=False, error=str(e))
            rep["offline"].append(l.get("name", ""))
            continue
        except ClusterError as e:
            _update_link(l["instance"], ok=False, error=str(e))
            rep["offline"].append(l.get("name", ""))
            continue
        try:
            name = validate_peer_name(obj.get("name"))
        except ValueError:
            name = None
        views[l["instance"]] = [m for m in (obj.get("members") or [])
                                if isinstance(m, dict) and _INST_RE.fullmatch(str(m.get("instance") or ""))]
        _update_link(l["instance"], ok=True, error="", seen=int(time.time()),
                     version=str(obj.get("version") or ""), **({"name": name} if name else {}))

    def is_removed(m) -> bool:
        ts = removed.get(m["instance"])
        return bool(ts) and float(m.get("since") or 0) <= ts

    # A removed panel still listed by a member that was offline at the time: tell that member now.
    for holder, mem in views.items():
        for m in mem:
            if is_removed(m):
                l = _link_by(load_cluster(), instance=holder)
                try:
                    cluster_call(l, "/api/cluster/forget", {"target": m["instance"]})
                except ClusterError:
                    pass
        views[holder] = [m for m in mem if not is_removed(m)]
    # A newer link to a removed panel means somebody added it back: the tombstone no longer applies.
    revived = {m["instance"] for mem in views.values() for m in mem if m["instance"] in removed}
    if revived:
        with LOCK:
            st = load_cluster()
            for i in revived:
                st["removed"].pop(i, None)
            save_cluster(st)

    # 2. link this panel with panels it does not know yet
    pending = {}
    for holder, mem in list(views.items()):
        for m in mem:
            inst = m["instance"]
            if inst == me or _link_by(load_cluster(), instance=inst) or inst in pending:
                continue
            name = str(m.get("name") or "")
            broker = _link_by(load_cluster(), instance=holder)
            if not broker:
                continue
            try:
                obj = cluster_call(broker, "/api/cluster/introduce", {"target": inst}, timeout=60)
                link, theirs = cluster_pair(normalize_panel_url(str(obj.get("url") or "")), {"ticket": str(obj.get("ticket") or "")},
                                            expect_instance=inst)
                views[inst] = theirs
                rep["linked"].append(link["name"])
            except ClusterError as e:
                pending[inst] = {"instance": inst, "name": name, "url": str(m.get("url") or ""), "error": str(e)}
                rep["failed"].append(name)

    # 3. link members with each other
    links = [l for l in load_cluster()["links"] if l["instance"] in views]
    missing = {l["instance"]: [] for l in links}
    for i, p in enumerate(links):
        for q in links[i + 1:]:
            p_knows = {m["instance"] for m in views.get(p["instance"], [])}
            q_knows = {m["instance"] for m in views.get(q["instance"], [])}
            if q["instance"] in p_knows or p["instance"] in q_knows:
                continue
            try:
                ticket = cluster_issue_ticket(q, p)
                cluster_call(p, "/api/cluster/connect", {"target_url": q["url"], "target_instance": q["instance"],
                                                         "ticket": ticket}, timeout=180, fallback="成员之间互联失败")
                views[p["instance"]].append({"instance": q["instance"]})
                rep["meshed"] += 1
            except ClusterError as e:
                missing[p["instance"]].append(q.get("name", ""))
                missing[q["instance"]].append(p.get("name", ""))
                rep["failed"].append(f"{p.get('name', '')} ↔ {q.get('name', '')}")
                sys.stderr.write(f"cluster: mesh {p.get('name')} <-> {q.get('name')} failed: {e}\n")
    with LOCK:
        st = load_cluster()
        for l in st["links"]:
            if l["instance"] in missing:
                l["missing"] = sorted(set(missing[l["instance"]]))
        st["pending"] = [v for k, v in pending.items() if not _link_by(st, instance=k)]
        save_cluster(st)
    return rep


def cluster_report_text(rep: dict) -> str:
    parts = []
    if rep["linked"]:
        parts.append("已自动和「{}」互联".format("、".join(rep["linked"])))
    if rep["meshed"]:
        parts.append(f"补上了 {rep['meshed']} 条成员之间的互联")
    if rep["dropped"]:
        parts.append("「{}」已把本机移出集群，本机这边也已删除".format("、".join(rep["dropped"])))
    if rep["offline"]:
        parts.append("「{}」暂时联系不上".format("、".join(rep["offline"])))
    if rep["failed"]:
        parts.append(f"有 {len(rep['failed'])} 条互联没有完成，原因见成员列表，恢复后点「检查」重试")
    return "；".join(parts)


def cluster_push_name_async():
    """After the 本机名称 changes: tell every member now (they rename our outbound)."""
    def run_push():
        with _CLUSTER_OP_LOCK:
            for l in load_cluster()["links"]:
                try:
                    cluster_call(l, "/api/cluster/status", {"name": local_node_name(), "url": local_cluster_url()}, timeout=20)
                except ClusterError as e:
                    sys.stderr.write(f"cluster: name push to '{l.get('name')}' failed: {e}\n")
    threading.Thread(target=run_push, name="cluster-name-push", daemon=True).start()

