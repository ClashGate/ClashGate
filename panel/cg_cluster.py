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
# Panels that know each other form one cluster. Every pair of panels in the cluster has one *link*.
# Since 1.42 each panel runs ONE cluster inbound (`cg-cluster-in`, one port, VLESS with post-quantum
# VLESS Encryption mlkem768x25519plus) for all members; every member is one user (its own UUID) in it.
# Each side has an outbound to the other side's cluster inbound, named after the other side's 本机名称.
# Adding a member adds a user, removing one deletes that user: the port and the keys never change.
# Links made before 1.42 had a dedicated inbound each (link["in"] has a port); they keep it until
# cluster_migrate_links moves them over (the member must be 1.42 too). Links live in cluster.json and their own fragments, never in inbounds.json /
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
CLUSTER_SHARED_LISTENER = CLUSTER_LISTENER_PREFIX + "in"   # the one inbound for every member (1.42)
CLUSTER_FLOW = "xtls-rprx-vision"
CLUSTER_TICKET_TTL = 300
CLUSTER_TOMBSTONE_TTL = 30 * 86400
_CLUSTER_OP_LOCK = threading.Lock()   # one user-started cluster job at a time (never held with LOCK while waiting on a remote)
_CLUSTER_TICKETS = {}                 # sha256(ticket) -> (instance allowed to join, expiry); in memory only
_CLUSTER_TICKETS_LOCK = threading.Lock()
_CLUSTER_PORT_HOLD = set()            # kept for callers; the shared inbound's port is saved at once (1.42)
_INST_RE = re.compile(r"[0-9a-f]{32}")
_ENC_RE = re.compile(r"mlkem768x25519plus\.[A-Za-z0-9._=-]+")


def load_cluster() -> dict:
    out = {"instance": "", "links": [], "pending": [], "removed": {}, "inbound": None}
    try:
        with open(CLUSTER_JSON) as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            out["instance"] = str(raw.get("instance") or "")
            out["links"] = [l for l in (raw.get("links") or []) if isinstance(l, dict) and l.get("id")
                            and isinstance(l.get("in"), dict) and isinstance(l.get("out"), dict)]
            out["pending"] = [p for p in (raw.get("pending") or []) if isinstance(p, dict)]
            _prune_pending(out)
            inb = raw.get("inbound")
            if (isinstance(inb, dict) and isinstance(inb.get("port"), int) and 1 <= inb["port"] <= 65535
                    and _ENC_RE.fullmatch(str(inb.get("decryption") or "")) and _ENC_RE.fullmatch(str(inb.get("encryption") or ""))):
                out["inbound"] = {k: inb[k] for k in ("port", "decryption", "encryption")}
            now = time.time()
            out["removed"] = {k: v for k, v in (raw.get("removed") or {}).items()
                              if _INST_RE.fullmatch(str(k)) and isinstance(v, (int, float)) and now - v < CLUSTER_TOMBSTONE_TTL}
    except FileNotFoundError:
        pass
    except (ValueError, OSError) as e:
        sys.stderr.write(f"cluster.json unreadable: {e}\n")
    return out


def _prune_pending(st: dict):
    """A 等待互联 entry is a panel our members know but we could not link with yet. It goes away with
    the members that told us about it (`via`): once they are all removed it is no cluster of ours."""
    links = {l.get("instance") for l in st["links"]}
    keep = []
    for p in st["pending"]:
        via = p.get("via")
        if not links or p.get("instance") in links:
            continue
        if isinstance(via, list) and not links.intersection(via):
            continue
        keep.append(p)
    st["pending"] = keep


def cluster_pending_id(p: dict) -> str:
    """Id of a 等待互联 entry for the page (not the panel's instance id itself)."""
    return hashlib.sha256(("pending:" + str(p.get("instance") or "")).encode()).hexdigest()[:12]


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


def _link_legacy(l: dict) -> bool:
    """A link made before 1.42: it has its own inbound (port + keys) instead of a user in the shared one."""
    return "port" in (l.get("in") or {})


def cluster_listeners(st: dict) -> list:
    """The cluster inbounds of this panel: the shared one with a user per member (1.42), plus the
    dedicated inbound of every link not moved yet."""
    out = []
    users = [{"username": str(l["id"]), "uuid": str(l["in"]["uuid"]), "flow": CLUSTER_FLOW}
             for l in st.get("links") or [] if not _link_legacy(l) and (l.get("in") or {}).get("uuid")]
    inb = st.get("inbound")
    if users and inb:
        out.append({"name": CLUSTER_SHARED_LISTENER, "type": "vless", "port": int(inb["port"]), "listen": "0.0.0.0",
                    "users": users, "decryption": str(inb["decryption"]),
                    "proxy": "DIRECT"})   # exits only, see cluster_listener_from_link
    out += [cluster_listener_from_link(l) for l in st.get("links") or [] if _link_legacy(l)]
    return out


def cluster_listener_from_link(l: dict) -> dict:
    """Dedicated inbound of a link made before 1.42 (Mihomo docs: config/inbound/listeners/vless, `decryption`)."""
    inb = l.get("in") or {}
    return {
        "name": CLUSTER_LISTENER_PREFIX + str(l["id"]),
        "type": "vless",
        "port": int(inb["port"]),
        "listen": "0.0.0.0",
        "users": [{"username": "cluster", "uuid": str(inb["uuid"]), "flow": CLUSTER_FLOW}],
        "decryption": str(inb["decryption"]),
        # A member is an exit, never a relay: traffic from another panel leaves here directly instead of
        # following this server's rules, so a selection (Zashboard) that points back can never loop.
        # (Mihomo's own loopback detector only catches a core dialing itself, not A -> B -> A.)
        "proxy": "DIRECT",
    }


def render_cluster_proxies(st: dict) -> str:
    """Member outbounds as multi-line YAML (1.41; one JSON object per line before)."""
    return dump_yaml_proxies([cluster_proxy_from_link(l) for l in st.get("links") or []])


def render_cluster_listeners(st: dict) -> str:
    return dump_yaml_proxies(cluster_listeners(st))


def _frag_items(text: str) -> list:
    """The entries of a list fragment (`  - ...` lines, either format) as parsed dicts."""
    v = extract_top_level_yaml_section("x:\n" + (text or ""), "x")
    return v if isinstance(v, list) else []


def _conf_cluster_entries(raw: str) -> tuple:
    """(cluster listeners, member outbounds) as written in a full config, in file order."""
    names = cluster_proxy_names()
    lst = extract_top_level_yaml_section(raw, "listeners")
    prox = extract_top_level_yaml_section(raw, "proxies")
    return ([x for x in (lst if isinstance(lst, list) else [])
             if isinstance(x, dict) and str(x.get("name") or "").startswith(CLUSTER_LISTENER_PREFIX)],
            [p for p in (prox if isinstance(prox, list) else [])
             if isinstance(p, dict) and str(p.get("name") or "") in names])


def save_cluster(st: dict):
    """cluster.json (0600: holds link keys) plus both fragments; does not touch the running core."""
    data = {"instance": st.get("instance") or "", "links": st.get("links") or [],
            "pending": st.get("pending") or [], "removed": st.get("removed") or {}}
    if st.get("inbound"):
        data["inbound"] = st["inbound"]
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
    """Ports the core listens on for the cluster (shared inbound while it has members + old dedicated ones)."""
    st = st or load_cluster()
    return {int(x["port"]) for x in cluster_listeners(st)}


def cluster_reserved_ports() -> set:
    """cluster_ports plus the shared inbound's port while it has no member: it stays this panel's."""
    st = load_cluster()
    return cluster_ports(st) | ({int(st["inbound"]["port"])} if st.get("inbound") else set())


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
    l_body = dump_yaml_proxies(lst + cluster_listeners(st))
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
    # Hot reload; the cluster ports are awaited (reload returns before they are bound), and only if
    # they never come up the core is restarted once (reload_core).
    rc, out = reload_core(cluster_ports(st), wait=_wait_cluster_ports)
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


class ClusterTimeout(ClusterError):
    """The other panel did not answer in time (may be a passing network hiccup: safe calls retry once)."""


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
            raise ClusterTimeout("连接对方面板超时，请检查地址、端口和对方防火墙")
        if isinstance(r, socket.gaierror):
            raise ClusterError("无法解析对方面板的域名，请检查地址")
        raise ClusterError("连接不上对方面板，请检查地址、端口和对方防火墙（{}）".format(str(r)[:120]))
    except (socket.timeout, TimeoutError):
        raise ClusterTimeout("连接对方面板超时，请检查地址、端口和对方防火墙")
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
    def __init__(self, msg: str, code: str = "", remote_msg: str = ""):
        super().__init__(msg)
        self.code = code
        self.remote_msg = remote_msg   # the other panel's own text, without our prefix


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
    return ClusterRemoteError(f"{fallback}：{msg}" if msg else f"{fallback}（HTTP {status}）", code, msg)


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


def ensure_cluster_inbound() -> dict:
    """This panel's one cluster inbound (port + keys), created and saved the first time it is needed."""
    with LOCK:
        st = load_cluster()
        if not st.get("inbound"):
            dec, enc = vless_mlkem768_pair()
            st["inbound"] = {"port": pick_port(read_env()), "decryption": dec, "encryption": enc}
            save_cluster(st)   # no member uses it yet: the fragments do not change
        return dict(st["inbound"])


def _cluster_new_inbound() -> dict:
    """A new member's place in the shared inbound: its own UUID, the shared port and keys."""
    inb = ensure_cluster_inbound()
    return {"port": inb["port"], "uuid": str(uuidlib.uuid4()), "decryption": inb["decryption"], "_enc": inb["encryption"]}


# Two phases: exchange first, then make it live. An add / 检查 used to reload a core after every single
# link (this panel once per member, each other panel as soon as it accepted a link), so later requests
# reached panels that were busy reloading. Now, inside cluster_batch():
#   1. links are only saved: this panel and every panel it links with (join / connect with defer=1)
#      keep their changes staged, nothing reloads;
#   2. at the end this panel asks each panel it touched to apply its staged changes (/api/cluster/apply,
#      one reload each), then applies its own (one reload).
# A panel that never gets the apply call (the initiator went away) applies its staged changes by itself
# after CLUSTER_STAGE_TTL; on start the panel also applies links that are saved but not in the config.
CLUSTER_STAGE_TTL = 180
_STAGED = {"on": False}          # this panel's saved-but-not-live cluster changes (guarded by LOCK)
_CLUSTER_BATCH = threading.local()   # .defer: commits in this thread are staged; .new / .touch: see cluster_batch


def _deferring() -> bool:
    return bool(getattr(_CLUSTER_BATCH, "defer", 0))


_batching = _deferring


def _staged_timeout():
    try:
        if cluster_apply_staged():
            sys.stderr.write("cluster: applied staged links (no apply call arrived)\n")
    except Exception as e:
        sys.stderr.write(f"cluster: applying staged links failed: {e}\n")


def _arm_stage_timer():
    t = _STAGED.get("timer")
    if t:
        t.cancel()
    t = threading.Timer(CLUSTER_STAGE_TTL, _staged_timeout)
    t.daemon = True
    t.start()
    _STAGED["timer"] = t


def cluster_apply_staged() -> bool:
    """Make the staged cluster changes live with one reload. False when nothing was staged.
    On failure everything staged is undone here (files restored, config untouched) and it raises."""
    with LOCK:
        if not _STAGED["on"]:
            return False
        s = dict(_STAGED)
        _STAGED.clear()
        _STAGED["on"] = False
        if s.get("timer"):
            s["timer"].cancel()
        try:
            apply_cluster_live(s["specs"], s["names"])
        except Exception:
            _restore_files(s["backup"])
            raise
        return True


def _cluster_commit(mutate) -> dict:
    """Under LOCK: load, mutate(st) (may raise), save, apply live; restore everything on failure.
    While deferring (cluster_batch, or a join / connect with defer=1) the change is only saved and staged."""
    with LOCK:
        backup = _snapshot_files((CLUSTER_JSON, FRAG_CLUSTER_PROXIES, FRAG_CLUSTER_LISTENERS))
        st = load_cluster()
        if _STAGED["on"]:   # what is live is still what it was before the first staged change
            old_specs, old_names = _STAGED["specs"], _STAGED["names"]
        else:
            old_specs = cluster_ufw_specs(st)
            old_names = {str(l.get("name") or "") for l in st["links"]}
        try:
            res = mutate(st)
            save_cluster(st)
            if not _deferring():
                apply_cluster_live(old_specs, old_names)
        except Exception:
            _restore_files(backup)
            raise
        if _deferring():
            if not _STAGED["on"]:
                _STAGED.update(on=True, backup=backup, specs=old_specs, names=old_names)
            _arm_stage_timer()
        elif _STAGED["on"]:   # applied together with this change
            if _STAGED.get("timer"):
                _STAGED["timer"].cancel()
            _STAGED.clear()
            _STAGED["on"] = False
        return res


def _remote_apply(l: dict) -> tuple:
    """Ask a member to apply its staged cluster changes. ("ok"|"later"|"failed", message)."""
    try:
        status, obj, _ = cluster_http(l["url"], "/api/cluster/apply", _link_auth(l), timeout=120)
    except ClusterError as e:
        return "later", str(e)   # it applies by itself after CLUSTER_STAGE_TTL
    if status == 200 and obj and obj.get("ok"):
        return "ok", ""
    if status in (401, 404) and not (obj or {}).get("code"):
        return "ok", ""   # a panel older than 1.40 applied each link at once
    return "failed", str(_remote_error(status, obj, "对方面板没能让集群配置生效"))


class cluster_batch:
    """with cluster_batch() as b: exchange with every panel first, then each applies once.
    b.failed: panels that could not apply (links made with them this time are undone);
    b.later: panels that did not answer the apply call (they apply by themselves within minutes)."""

    def __enter__(self):
        self.failed, self.later = [], []
        self.outer = not _deferring()
        if self.outer:
            _CLUSTER_BATCH.defer = 1
            _CLUSTER_BATCH.new = {}       # instance -> (base, my instance, key) of links made now
            _CLUSTER_BATCH.touch = set()  # members that staged changes for this operation
        return self

    def __exit__(self, exc_type, exc, tb):
        if not self.outer:
            return False
        new = dict(getattr(_CLUSTER_BATCH, "new", {}) or {})
        touch = set(getattr(_CLUSTER_BATCH, "touch", set()) or set())
        try:
            if touch:
                cluster_stage("正在让各面板的新配置生效")
            for inst in sorted(touch):
                l = _link_by(load_cluster(), instance=inst)
                if not l:
                    continue
                res, msg = _remote_apply(l)
                if res == "later":
                    self.later.append(l.get("name", ""))
                elif res == "failed":
                    self.failed.append(l.get("name", ""))
                    sys.stderr.write(f"cluster: '{l.get('name')}' could not apply: {msg}\n")
                    if inst in new:   # it has undone its side already; undo ours (still staged)
                        try:
                            _drop_links({inst})
                        except Exception as e:
                            sys.stderr.write(f"cluster: undo link failed: {e}\n")
                        new.pop(inst, None)
        finally:
            _CLUSTER_BATCH.defer = 0
            _CLUSTER_BATCH.new, _CLUSTER_BATCH.touch = {}, set()
        try:
            if _STAGED["on"]:
                cluster_stage("本机正在让集群配置生效")
            cluster_apply_staged()
        except Exception as e:
            for base, my_inst, key in new.values():   # do not leave half links on the other panels
                try:
                    cluster_http(base, "/api/cluster/leave", {"instance": my_inst, "key": key}, timeout=60)
                except ClusterError:
                    pass
            if exc_type is None:
                raise ClusterError(f"集群配置没能生效，已撤销这次添加的互联：{e}")
        return False


def cluster_batch_text(b) -> str:
    parts = []
    if b.failed:
        parts.append("「{}」没能让新配置生效，已撤销这次和它的互联".format("、".join(b.failed)))
    if b.later:
        parts.append("「{}」暂时没有回应，它会在 3 分钟内自动让新配置生效".format("、".join(b.later)))
    return "；".join(parts)


def refresh_cluster_fragments() -> bool:
    """After an update or a restart, bring the running config in line with cluster.json: the current
    listener shape (1.38: exit only) and links saved but never applied (1.40: staged when the panel
    restarted). Compares the entries, not the text: fragments that only differ in format (1.41:
    multi-line YAML instead of one JSON object per line) are rewritten without reloading the core.
    True when the core was reloaded."""
    st = load_cluster()
    if not st["links"]:
        return False
    want = (cluster_listeners(st), [cluster_proxy_from_link(l) for l in st["links"]])
    stale = (_frag_items(_read_frag(FRAG_CLUSTER_LISTENERS)), _frag_items(_read_frag(FRAG_CLUSTER_PROXIES))) != want
    if not stale:
        if (_read_frag(FRAG_CLUSTER_LISTENERS), _read_frag(FRAG_CLUSTER_PROXIES)) != (
                render_cluster_listeners(st), render_cluster_proxies(st)):
            with LOCK:
                save_cluster(load_cluster())   # same entries in the new format: nothing to reload
        try:
            # Custom mode: the user's file holds the cluster entries; template mode: the live config,
            # where an IPv6-only server listens on "::" (assemble_config -> ipv6_listen).
            custom = is_custom_config_mode()
            live_want = want
            if not custom and ipv6_only():
                live_want = ([dict(x, listen="::") if x.get("listen") == "0.0.0.0" else x for x in want[0]], want[1])
            with open(CUSTOM_CONF if custom else CONF) as f:
                stale = _conf_cluster_entries(f.read()) != live_want
        except OSError:
            stale = True
    if not stale:
        return False
    _cluster_commit(lambda s: None)
    return True

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


# The running cluster operation started from this panel's page (one at a time, _CLUSTER_OP_LOCK).
# `stage` is a short Chinese line the page shows while it waits (translated when sent).
_CLUSTER_TASK = {"id": 0, "running": False, "kind": "", "ok": None, "msg": "", "stage": "", "started_at": 0.0, "finished_at": 0.0}
_CLUSTER_TASK_LOCK = threading.Lock()


def cluster_stage(text: str):
    """Report what the running cluster operation is doing now (a no-op outside a page task)."""
    with _CLUSTER_TASK_LOCK:
        if _CLUSTER_TASK["running"]:
            _CLUSTER_TASK["stage"] = text


def cluster_pair(base: str, auth: dict, expect_instance: str = "") -> tuple:
    """Create a two-way link with the panel at `base` (auth: password or one-time ticket).

    Returns (link, the other panel's member list). Raises ClusterError; nothing is left behind on failure."""
    cluster_stage(f"正在连接 {urlparse(base).hostname or base}")
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
        cluster_stage(f"正在和「{rname}」交换节点" if _deferring() else f"「{rname}」正在创建集群节点并让配置生效")
        status, obj, _ = cluster_http(base, "/api/cluster/join", {
            **auth, "instance": my_inst, "name": local_node_name(), "url": self_url, "version": VERSION,
            "key": key, "port": inb["port"], "uuid": inb["uuid"], "encryption": inb["_enc"],
            **({"defer": "1"} if _deferring() else {})}, timeout=120)
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
                "in": {"uuid": inb["uuid"]},   # a user in the shared cluster inbound (1.42)
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
            if not _deferring():
                cluster_stage("本机正在让集群配置生效")
            _cluster_commit(add)
            if _deferring():
                if isinstance(getattr(_CLUSTER_BATCH, "new", None), dict):
                    _CLUSTER_BATCH.new[r_inst] = (base, my_inst, key)
                if isinstance(getattr(_CLUSTER_BATCH, "touch", None), set):
                    _CLUSTER_BATCH.touch.add(r_inst)
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
    form = {"from_instance": joiner["instance"], "since": int(joiner.get("created") or 0),
            "ticket_hash": hashlib.sha256(ticket.encode()).hexdigest()}
    try:
        cluster_call(target, "/api/cluster/expect", form)
    except ClusterTimeout:   # the same ticket again is harmless: retry a passing timeout once
        cluster_call(target, "/api/cluster/expect", form)
    return ticket


def _drop_links(instances: set, tombstone: bool = False) -> list:
    """Remove the links to these panels here (both directions). Returns the removed links."""
    def drop(st):
        gone = [l for l in st["links"] if l.get("instance") in instances]
        st["links"] = [l for l in st["links"] if l.get("instance") not in instances]
        st["pending"] = [p for p in st["pending"] if p.get("instance") not in instances]
        _prune_pending(st)   # panels only the removed members knew about
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


def cluster_leave_all(notify: bool = True, background: bool = False) -> tuple:
    """This panel leaves the cluster: first drop every link here (one reload), then tell each member
    (best effort). background=True (the page, 1.41): the members are told from a thread and the call
    returns at once. A member that is not reached drops its link by itself at its next 检查 (this panel
    answers bad_token), or its owner removes it. Returns (number of links, names that could not be told;
    always empty in the background)."""
    links = load_cluster()["links"]
    if not links:
        return 0, []
    cluster_stage("本机正在删除互联")
    _drop_links({l["instance"] for l in links})

    def tell() -> list:
        missed = []
        for l in links:
            try:
                cluster_call(l, "/api/cluster/leave", timeout=30)
            except ClusterError as e:
                missed.append(l.get("name", ""))
                sys.stderr.write(f"cluster: could not tell '{l.get('name')}' that this panel left: {e}\n")
        return missed

    if not notify:
        return len(links), []
    if background:
        threading.Thread(target=tell, name="cluster-leave-notify", daemon=True).start()
        return len(links), []
    return len(links), tell()


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


def cluster_migrate_links(only: set = None) -> list:
    """1.42: move links made before 1.42 (a dedicated inbound each) to the shared cluster inbound: tell
    the member its new node (/api/cluster/node, staged inside cluster_batch), then drop the old inbound
    here. A member before 1.42 does not know that request (401/404): its link keeps its own inbound
    and is tried again later. only: instances to try (None: all). Returns the names moved."""
    moved = []
    for l in list(load_cluster()["links"]):
        if not _link_legacy(l) or (only is not None and l["instance"] not in only):
            continue
        inb = _cluster_new_inbound()
        try:
            status, obj, _ = cluster_http(l["url"], "/api/cluster/node", {
                **_link_auth(l), "port": inb["port"], "uuid": inb["uuid"], "encryption": inb["_enc"],
                **({"defer": "1"} if _deferring() else {})}, timeout=60)
        except ClusterError as e:
            sys.stderr.write(f"cluster: moving '{l.get('name')}' to the shared inbound failed: {e}\n")
            continue
        if status != 200 or not obj or not obj.get("ok"):
            continue   # a member before 1.42, or it refused: its link keeps its own inbound for now

        def switch(st, inst=l["instance"], uid=inb["uuid"]):
            x = _link_by(st, instance=inst)
            if x:
                x["in"] = {"uuid": uid}
        _cluster_commit(switch)
        if isinstance(getattr(_CLUSTER_BATCH, "touch", None), set):
            _CLUSTER_BATCH.touch.add(l["instance"])
        moved.append(l.get("name", ""))
    return moved


def start_cluster_migration(delay: float = 30, every: float = 900):
    """On panel start: while links made before 1.42 remain, move them (one batch, one reload per panel)
    whenever no other cluster job runs. Members that are still old are retried every 15 minutes."""
    if not any(_link_legacy(l) for l in load_cluster()["links"]):
        return None

    def loop():
        time.sleep(delay)
        while any(_link_legacy(l) for l in load_cluster()["links"]):
            if _CLUSTER_OP_LOCK.acquire(blocking=False):
                try:
                    with cluster_batch():
                        moved = cluster_migrate_links()
                    if moved:
                        sys.stderr.write("cluster: moved to the shared inbound: {}\n".format(", ".join(moved)))
                except Exception as e:
                    sys.stderr.write(f"cluster: migration failed: {e}\n")
                finally:
                    _CLUSTER_OP_LOCK.release()
            time.sleep(every)
    t = threading.Thread(target=loop, name="cluster-migrate", daemon=True)
    t.start()
    return t


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
        cluster_stage(f"正在检查「{l.get('name', '')}」")
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

    # 1.42: members that answered and still use a dedicated inbound here move to the shared one
    try:
        cluster_migrate_links(only=set(views))
    except Exception as e:
        sys.stderr.write(f"cluster: migration during 检查 failed: {e}\n")

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

    # 2. link this panel with panels it does not know yet. Every member that knows one can vouch for us:
    #    when the first cannot reach it (offline, firewall), the next one is asked.
    unknown = {}
    for holder, mem in views.items():
        for m in mem:
            inst = m["instance"]
            if inst == me or _link_by(load_cluster(), instance=inst):
                continue
            u = unknown.setdefault(inst, {"name": str(m.get("name") or ""), "url": str(m.get("url") or ""), "via": []})
            u["via"].append(holder)
    pending = {}
    for inst, u in unknown.items():
        if _link_by(load_cluster(), instance=inst):   # it linked with us meanwhile
            continue
        error, cut_off = "", []
        for holder in u["via"]:
            broker = _link_by(load_cluster(), instance=holder)
            if not broker:
                continue
            bname = broker.get("name", "")
            cluster_stage(f"正在通过「{bname}」和「{u['name']}」互联")
            try:
                obj = cluster_call(broker, "/api/cluster/introduce", {"target": inst}, timeout=60)
            except ClusterRemoteError as e:
                if e.code == "unreachable":   # the member we asked cannot reach it either
                    cut_off.append(bname)
                    error = "「{}」现在也连不上它：{}".format("、".join(cut_off), e.remote_msg or str(e))
                else:
                    error = str(e)
                continue
            except ClusterError as e:
                error = str(e)
                continue
            try:
                link, theirs = cluster_pair(normalize_panel_url(str(obj.get("url") or "")), {"ticket": str(obj.get("ticket") or "")},
                                            expect_instance=inst)
            except ClusterError as e:
                error = str(e)   # this panel cannot reach it: another member's ticket would not help
                break
            views[inst] = theirs
            rep["linked"].append(link["name"])
            error = ""
            break
        if error or not _link_by(load_cluster(), instance=inst):
            pending[inst] = {"instance": inst, "name": u["name"], "url": u["url"], "via": list(u["via"]),
                             "error": error or "集群成员不存在"}
            rep["failed"].append(u["name"])

    # 3. link members with each other
    links = [l for l in load_cluster()["links"] if l["instance"] in views]
    missing = {l["instance"]: [] for l in links}
    for i, p in enumerate(links):
        for q in links[i + 1:]:
            p_knows = {m["instance"] for m in views.get(p["instance"], [])}
            q_knows = {m["instance"] for m in views.get(q["instance"], [])}
            if q["instance"] in p_knows or p["instance"] in q_knows:
                continue
            cluster_stage(f"正在让「{p.get('name', '')}」和「{q.get('name', '')}」互联")
            try:
                ticket = cluster_issue_ticket(q, p)
                cluster_call(p, "/api/cluster/connect", {"target_url": q["url"], "target_instance": q["instance"],
                                                         "ticket": ticket, **({"defer": "1"} if _deferring() else {})},
                             timeout=180, fallback="成员之间互联失败")
                if isinstance(getattr(_CLUSTER_BATCH, "touch", None), set):   # both staged the new link
                    _CLUSTER_BATCH.touch.update({p["instance"], q["instance"]})
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
        parts.append("「{}」暂时连接失败".format("、".join(rep["offline"])))
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

