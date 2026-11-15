"""Node, inbound, session, and config generation. Moved out of panel.py unchanged."""
import sys
import base64
import hashlib
import hmac
import json
import os
import random
import re
import secrets
import shutil
import socket
import subprocess
import tempfile
import threading
import time


def bind():
    """Copy path constants from the panel module. Imported after those exist."""
    mod = sys.modules.get("panel") or sys.modules.get("__main__")
    if mod is None:
        return
    g = globals()
    for key, val in mod.__dict__.items():
        if key.startswith("__") or key in g:
            continue
        g[key] = val


bind()


def pick_reality_sni() -> str:
    return random.choice(REALITY_SNI_POOL)


_SNI_HOST = re.compile(
    r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$"
)


def resolve_sni(form: dict) -> str:
    """Use the SNI typed on the add-node form, or a random built-in domain if blank."""
    raw = (form.get("sni") or "").strip().lower().rstrip(".")
    if not raw:
        return pick_reality_sni()
    if "://" in raw or "/" in raw:
        raise ValueError("SNI 无效，请填写域名，或留空从内置域名池随机抽取")
    if ":" in raw:
        host, _, port = raw.rpartition(":")
        if port.isdigit():
            raw = host
    if not _SNI_HOST.fullmatch(raw):
        raise ValueError("SNI 无效，请填写域名，或留空从内置域名池随机抽取")
    return raw

TYPES = (
    "vless-reality", "shadowsocks", "hysteria2", "snell",
    "anytls", "tuic", "trusttunnel", "shadowquic", "mieru", "sudoku", "http", "socks",
)
DEFAULT_NODE_NAMES = {
    "vless-reality": "VlessReality",
    "shadowsocks": "Shadowsocks",
    "hysteria2": "Hysteria2",
    "snell": "SnellV6",
    "anytls": "AnyTLS",
    "tuic": "TUICv5",
    "trusttunnel": "TrustTunnel",
    "shadowquic": "ShadowQUIC",
    "mieru": "Mieru",
    "sudoku": "Sudoku",
    "http": "HTTP",
    "socks": "SOCKS5",
}
PROTOCOL_DESCRIPTIONS = {
    "vless-reality": "免证书的新一代协议",
    "shadowsocks": "经典轻量级加密协议，默认锁定 aes-256-gcm",
    "hysteria2": "新一代 UDP 协议",
    "snell": "轻量高效的私有协议，内置基于 PSK 的流量整形",
    "anytls": "内置随机填充与随机指纹的新一代 TLS 协议",
    "tuic": "基于 QUIC 的低延迟零握手机制 UDP 协议",
    "trusttunnel": "基于标准 HTTP/2 与 HTTP/3 的高隐蔽 TLS 隧道协议",
    "shadowquic": "免证书的新一代 QUIC 协议，内置随机 JLS 伪装",
    "mieru": "抗深度包检测（DPI）的混淆传输代理协议",
    "sudoku": "基于数独流量特征变换与 chacha20 加密的抗审查协议",
    "http": "通用 HTTP / HTTPS 代理协议",
    "socks": "通用 SOCKS5 代理协议，支持 UDP 转发",
}
ANYTLS_FP_POOL = ("chrome", "safari", "firefox", "ios")
CERT_TYPES = ("hysteria2", "trusttunnel", "anytls", "tuic")


def random_anytls_padding() -> str:
    """Generate a randomized AnyTLS padding scheme internally."""
    stop = random.randint(6, 9)
    p0 = random.randint(30, 60)
    p1_lo = random.randint(100, 160)
    p1_hi = random.randint(320, 450)
    p2_a = f"{random.randint(300, 400)}-{random.randint(500, 600)}"
    p2_b = f"{random.randint(500, 600)}-{random.randint(950, 1150)}"
    p2_c = f"{random.randint(550, 650)}-{random.randint(1100, 1300)}"
    p2_d = f"{random.randint(450, 550)}-{random.randint(900, 1100)}"
    p3_fixed = random.randint(10, 18)
    p3_range = f"{random.randint(400, 500)}-{random.randint(850, 1050)}"
    lines = [
        f"stop={stop}",
        f"0={p0}-{p0}",
        f"1={p1_lo}-{p1_hi}",
        f"2={p2_a},c,{p2_b},c,{p2_c},c,{p2_d}",
        f"3={p3_fixed}-{p3_fixed},{p3_range}",
    ]
    for idx in range(4, stop):
        lo = random.randint(400, 550)
        hi = random.randint(950, 1250)
        lines.append(f"{idx}={lo}-{hi}")
    return "\n".join(lines)

LOCK = threading.Lock()


# ---------------------------------------------------------------- legacy migration & helpers
def resolve_mihomo_bin() -> str:
    env_bin = os.environ.get("MIHOMO_BIN")
    if env_bin:
        return env_bin
    if os.path.isfile(CS_ROOT + "/mihomo") and os.access(CS_ROOT + "/mihomo", os.X_OK):
        return CS_ROOT + "/mihomo"
    return "/usr/local/bin/mihomo"


def resolve_template_path(rel_path: str) -> str:
    p1 = CS_ROOT + "/" + rel_path
    if os.path.isfile(p1):
        return p1
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    p2 = os.path.join(here, rel_path)
    return p2 if os.path.isfile(p2) else p1


def resolve_certctl_path() -> str:
    if os.path.isfile(CERTCTL):
        return CERTCTL
    return resolve_template_path("scripts/certctl.sh")


_ROUTING = None


def _seed_dir() -> str:
    p1 = CS_ROOT + "/resources/routing"
    if os.path.isdir(p1):
        return p1
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    p2 = os.path.join(here, "resources", "routing")
    return p2 if os.path.isdir(p2) else p1


def _beginner_routing_state(st: dict) -> dict:
    """Hide system groups (Node Select / Final) and raw YAML from the beginner routing UI."""
    st = dict(st or {})
    st["groups"] = [
        {k: v for k, v in g.items() if k != "yaml"}
        for g in (st.get("groups") or [])
        if (g.get("role") or "policy") not in ("select", "final")
    ]
    return st


def _localize_fields(obj, keys, lang: str):
    """Translate Chinese status/error strings in a state dict for en/ru/fa clients."""
    if not isinstance(obj, dict) or lang not in ("en", "ru", "fa"):
        return obj
    out = dict(obj)
    for k in keys:
        if isinstance(out.get(k), str) and out[k]:
            out[k] = _tr_msg(out[k], lang)
    return out


def _localize_routing_state(st: dict, lang: str) -> dict:
    st = _localize_fields(st, ("error",), lang)
    if isinstance(st, dict) and lang in ("en", "ru", "fa"):
        st["groups"] = [_localize_fields(g, ("error",), lang) for g in (st.get("groups") or [])]
    return st


def get_routing() -> RoutingManager:
    global _ROUTING
    if _ROUTING is None:
        parse_doc = parse_yaml_document_factory(parse_yaml_lines, strip_yaml_comment)
        _ROUTING = RoutingManager(
            routing_json=ROUTING_JSON,
            routing_dir=ROUTING_DIR,
            frag_rule_providers=FRAG_RULE_PROVIDERS,
            frag_proxy_groups=FRAG_PROXY_GROUPS,
            frag_rules=FRAG_RULES,
            seed_dir=_seed_dir(),
            parse_yaml_document=parse_doc,
            dump_yaml_map=dump_yaml_map,
            yaml_scalar=yaml_scalar,
            atomic_write=atomic_write,
            extract_top_level_yaml_section=extract_top_level_yaml_section,
            replace_top_level_yaml_section=replace_top_level_yaml_section,
        )
    return _ROUTING


def ensure_unified_root():
    """Ensure /etc/clashgate and client directory exist."""
    os.makedirs(CS_ROOT, mode=0o775, exist_ok=True)
    os.makedirs(CLIENT_DIR, mode=0o700, exist_ok=True)
    # Mihomo (group mihomo) writes its caches here; the sticky bit stops it from renaming or
    # deleting root-owned files (binary, scripts, env, panel config) in this directory.
    try:
        st = os.stat(CS_ROOT)
        if st.st_mode & 0o020 and not st.st_mode & 0o1000:
            os.chmod(CS_ROOT, (st.st_mode & 0o7777) | 0o1000)
    except OSError:
        pass


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, PBKDF2_ITER)
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITER, base64.b64encode(salt).decode(), base64.b64encode(dk).decode())


def verify_password(pw: str, stored: str) -> bool:
    try:
        algo, it, salt, dk = stored.split("$")
        assert algo == "pbkdf2_sha256"
        calc = hashlib.pbkdf2_hmac("sha256", pw.encode(), base64.b64decode(salt), int(it))
        return hmac.compare_digest(calc, base64.b64decode(dk))
    except Exception:
        return False


def read_env() -> dict:
    env = {}
    try:
        with open(ENV_FILE) as f:
            for line in f:
                m = re.match(r"^([A-Z_]+)=(.*)$", line.strip())
                if m:
                    val = m.group(2).strip()
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    env[m.group(1)] = val
    except FileNotFoundError:
        pass
    return env


def run(cmd, timeout=30, env=None):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
        return p.returncode, (p.stdout + p.stderr).strip()
    except Exception as e:
        return 127, str(e)


def _clean_inbounds(items) -> list:
    out = []
    seen_names = set()
    for item in items if isinstance(items, list) else []:
        if isinstance(item, dict) and isinstance(item.get("client"), dict):
            item["client"].pop("skip-cert-verify", None)
            if item.get("name"):
                nm = str(item["name"])
                item["client"]["name"] = nm
                if nm in seen_names:
                    continue
                seen_names.add(nm)
            out.append(item)
    return out


def load_inbounds() -> list:
    try:
        with open(INBOUNDS) as f:
            return _clean_inbounds(json.load(f))
    except FileNotFoundError:
        return []


def load_server_proxies() -> list:
    try:
        with open(PROXIES_JSON) as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except FileNotFoundError:
        pass
    try:
        with open(FRAG_PROXIES) as f:
            raw = f.read().strip()
            if raw:
                return parse_mihomo_proxies("proxies:\n" + raw)
    except Exception:
        pass
    return []


def load_proxy_providers() -> dict:
    try:
        with open(PROVIDERS_JSON) as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except FileNotFoundError:
        pass
    return {}


def is_custom_config_mode() -> bool:
    try:
        return os.path.isfile(CUSTOM_CONF) and os.path.getsize(CUSTOM_CONF) > 0
    except OSError:
        return False


def _parse_nodes_tsv(text: str) -> list:
    rows = []
    for line in (text or "").splitlines():
        p = line.split("\t")
        if len(p) >= 7:
            rows.append({
                "name": p[0], "port": int(p[1]), "uuid": p[2],
                "priv": p[3], "pub": p[4], "sid": p[5], "sni": p[6],
                "dec": p[7] if len(p) >= 8 else "",
                "enc": p[8] if len(p) >= 9 else "",
            })
    return rows


def read_nodes() -> list:
    try:
        with open(NODES_TSV) as f:
            return _parse_nodes_tsv(f.read())
    except FileNotFoundError:
        return []


def live_nodes_and_inbounds() -> tuple:
    """(nodes, inbounds) as Mihomo is running them. With unsaved drafts the files on disk
    already hold the draft, so read the pre-draft baseline snapshot instead; the
    subscription must not hand out nodes / credentials the server is not serving yet."""
    try:
        if load_pending_reload()["items"] and os.path.isfile(PENDING_BASELINE_JSON):
            with open(PENDING_BASELINE_JSON) as f:
                files = json.load(f).get("files") or {}
            if NODES_TSV in files and INBOUNDS in files:
                inb_txt = files.get(INBOUNDS)
                return (_parse_nodes_tsv(files.get(NODES_TSV) or ""),
                        _clean_inbounds(json.loads(inb_txt) if inb_txt else []))
    except Exception as e:
        sys.stderr.write(f"live state from draft baseline failed, using current files: {e}\n")
    return read_nodes(), load_inbounds()


def get_controller_port(env: dict = None) -> int:
    if is_custom_config_mode():
        try:
            with open(CUSTOM_CONF) as f:
                txt = f.read()
            for pat in (
                r'^\s*external-controller-tls\s*:\s*["\']?[^"\':\s]+:(\d+)',
                r'^\s*external-controller\s*:\s*["\']?[^"\':\s]+:(\d+)',
            ):
                m = re.search(pat, txt, re.M)
                if m:
                    p = int(m.group(1))
                    if 1 <= p <= 65535:
                        return p
        except Exception:
            pass
    if env is None:
        env = read_env()
    try:
        p = int(env.get("CONTROLLER_PORT") or 0)
        if 1 <= p <= 65535:
            return p
    except ValueError:
        pass
    try:
        with open(CONF) as f:
            txt = f.read()
        for pat in (
            r'^\s*external-controller-tls\s*:\s*["\']?[^"\':\s]+:(\d+)',
            r'^\s*external-controller\s*:\s*["\']?[^"\':\s]+:(\d+)',
        ):
            m = re.search(pat, txt, re.M)
            if m:
                return int(m.group(1))
    except Exception:
        pass
    return 7896


def extract_yaml_secret(raw_yaml: str):
    """Extract top-level `secret:` scalar from raw YAML without truncating on `#` or `%` inside quotes."""
    for raw_line in raw_yaml.splitlines():
        expanded = raw_line.expandtabs(2)
        stripped = expanded.lstrip(" ")
        indent = len(expanded) - len(stripped)
        if indent != 0 or not stripped or stripped.startswith("#"):
            continue
        cleaned = strip_yaml_comment(stripped)
        k, sep, v = split_kv(cleaned)
        if sep and k == "secret":
            val = parse_scalar(v, "secret")
            return "" if val is None else str(val)
    return None


def get_mihomo_secret(env: dict = None) -> str:
    if is_custom_config_mode():
        try:
            with open(CUSTOM_CONF) as f:
                sec = extract_yaml_secret(f.read())
            if sec is not None:
                return sec
        except Exception:
            pass
    if env is None:
        env = read_env()
    return env.get("MIHOMO_SECRET", "")


def used_ports(env) -> set:
    ports = {80, 443, int(env.get("PANEL_PORT", "0") or 0), get_controller_port(env)}
    ports |= {n["port"] for n in read_nodes()}
    ports |= {i["port"] for i in load_inbounds()}
    ports |= cluster_ports() | set(_CLUSTER_PORT_HOLD)
    return ports


def pick_port(env) -> int:
    used = used_ports(env)
    for _ in range(1000):
        p = random.randint(20000, 39999)
        if p not in used:
            return p
    raise RuntimeError("没有可用的随机端口")


def reality_keypair():
    rc, out = run([resolve_mihomo_bin(), "generate", "reality-keypair"])
    priv = re.search(r"PrivateKey:\s*(\S+)", out)
    pub = re.search(r"PublicKey:\s*(\S+)", out)
    if rc != 0 or not priv or not pub:
        raise RuntimeError("Reality 密钥对生成失败：" + out)
    return priv.group(1), pub.group(1)


def sudoku_keypair():
    rc, out = run([resolve_mihomo_bin(), "generate", "sudoku-keypair"])
    priv = re.search(r"PrivateKey:\s*(\S+)", out)
    pub = re.search(r"PublicKey:\s*(\S+)", out)
    if rc == 0 and priv and pub:
        return priv.group(1), pub.group(1)
    u = str(uuidlib.uuid4())
    return u, u


def vless_x25519_keypair():
    rc, out = run([resolve_mihomo_bin(), "generate", "vless-x25519"])
    dec = re.search(r'\[Server\]\s*decryption:\s*"([^"]+)"', out)
    enc = re.search(r'\[Client\]\s*encryption:\s*"([^"]+)"', out)
    if rc != 0 or not dec or not enc:
        raise RuntimeError("VLESS 加密密钥生成失败：" + out)
    return dec.group(1), enc.group(1)


def certs_present() -> bool:
    for c, k in ((CERT, KEY), (ROOT + CERT, ROOT + KEY)):
        if os.path.isfile(c) and os.path.isfile(k):
            return True
    return False


def panel_base_url(env: dict, cfg: dict) -> str:
    host = env.get("DOMAIN", "").removeprefix("*.")
    if not host:
        return ""
    port = int(cfg.get("port") or env.get("PANEL_PORT") or 8443)
    return f"https://{host}" if port == 443 else f"https://{host}:{port}"


def zashboard_url(env: dict) -> str:
    """Return Zashboard HTTPS URL with fully URL-encoded API Secret appended for one-click direct login."""
    host = env.get("DOMAIN", "").removeprefix("*.") or env.get("SERVER_IP", "")
    if not host:
        return ""
    cport = get_controller_port(env)
    secret = get_mihomo_secret(env)
    if not secret:
        return f"https://{host}:{cport}/ui/"
    qs = f"hostname={quote(host, safe='')}&port={cport}&secret={quote(secret, safe='')}&https=true"
    return f"https://{host}:{cport}/ui/#/setup?{qs}"


def write_env_var(key: str, val: str):
    val = str(val)
    # One KEY="value" per line: a newline or quote would let a value inject another setting.
    if re.search(r'[\r\n"\\]', val):
        raise ValueError(f"{key} 含有不支持的字符")
    lines = []
    found = False
    try:
        with open(ENV_FILE) as f:
            for line in f:
                if line.startswith(f"{key}="):
                    lines.append(f'{key}="{val}"\n')
                    found = True
                else:
                    lines.append(line)
    except FileNotFoundError:
        pass
    if not found:
        lines.append(f'{key}="{val}"\n')
    atomic_write(ENV_FILE, "".join(lines), 0o600)


def render_controller_fragment(env: dict) -> str:
    if env.get("MODE") != "auto-cert":
        return "# controller disabled in no-cert mode\n"
    cport = get_controller_port(env)
    secret = env.get("MIHOMO_SECRET", "")
    return (
        f'external-controller-tls: "0.0.0.0:{cport}"\n'
        f"tls:\n  certificate: {CERT}\n  private-key: {KEY}\n"
        f"external-controller-cors:\n  allow-origins:\n    - '*'\n  allow-private-network: true\n"
        f'secret: "{secret}"\n'
        f"external-ui: ui\n"
        f'external-ui-url: "https://github.com/Zephyruso/zashboard/releases/latest/download/dist-cdn-fonts.zip"\n'
    )




def x25519_pub_from_priv(priv_b64: str) -> str:
    """Derive base64url X25519 public key from a 32-byte base64url/base64 X25519 private key via openssl."""
    s = (priv_b64 or "").strip()
    if not s:
        return ""
    try:
        pad = "=" * ((4 - len(s) % 4) % 4)
        raw_priv = base64.urlsafe_b64decode(s + pad) if ("-" in s or "_" in s) else base64.b64decode(s + pad)
        if len(raw_priv) != 32:
            return s
        der_priv = bytes.fromhex("302e020100300506032b656e04220420") + raw_priv
        p = subprocess.run(["openssl", "pkey", "-inform", "DER", "-pubout", "-outform", "DER"],
                           input=der_priv, capture_output=True, timeout=5)
        if p.returncode == 0 and len(p.stdout) >= 32:
            return base64.urlsafe_b64encode(p.stdout[-32:]).decode().rstrip("=")
    except Exception:
        pass
    return s


def derive_vless_encryption(dec_str: str) -> str:
    """Convert server VLESS `decryption` string into client `encryption` string."""
    s = (dec_str or "").strip()
    if not s or s == "none":
        return ""
    parts = s.split(".")
    out = []
    for seg in parts:
        if re.fullmatch(r"\d+s", seg):
            out.append("0rtt")
        elif len(seg) in (43, 44) and re.fullmatch(r"[A-Za-z0-9_+=-]+", seg):
            out.append(x25519_pub_from_priv(seg))
        else:
            out.append(seg)
    return ".".join(out)


def extract_top_level_yaml_section(raw_yaml: str, section_key: str):
    """Extract and parse a top-level YAML section (e.g. listeners, proxies, proxy-providers)."""
    lines = []
    in_sec = False
    for raw_line in raw_yaml.splitlines():
        cleaned = strip_yaml_comment(raw_line.expandtabs(2))
        if not cleaned.strip():
            continue
        stripped = cleaned.lstrip(" ")
        indent = len(cleaned) - len(stripped)
        if not in_sec:
            if indent == 0:
                k, sep, v = split_kv(stripped)
                if sep and k == section_key:
                    in_sec = True
                    lines.append((0, stripped))
        else:
            if indent == 0 and not (stripped == "-" or stripped.startswith("- ")):
                break
            lines.append((indent, stripped))
    if not lines:
        return None
    try:
        parsed, _ = parse_yaml_lines(lines, 0, 0)
        if isinstance(parsed, dict):
            return parsed.get(section_key)
    except Exception as e:
        sys.stderr.write(f"extract_top_level_yaml_section({section_key}) warning: {e}\n")
    return None


def _first_user_creds(users_val) -> tuple:
    """Extract (username, password, uuid, flow, alterId) from a listener's `users` field (list or dict)."""
    if isinstance(users_val, list) and users_val:
        u0 = users_val[0]
        if isinstance(u0, dict):
            return (
                str(u0.get("username", "user")),
                str(u0.get("password", "")),
                str(u0.get("uuid", "")),
                str(u0.get("flow", "")),
                int(u0.get("alterId", 0) or 0),
            )
    elif isinstance(users_val, dict) and users_val:
        k, v = next(iter(users_val.items()))
        return str(k), str(v), str(k), "", 0
    return "user", "", "", "", 0


SNELL_VERSION = 6
SNELL_V6_MIN_CORE = "1.19.34"            # MetaCubeX/mihomo#3410 (Snell v6 inbound + outbound)
SNELL_V6_PSK_LEN = (12, 255)             # transport/snell/v6.go V6MinPSKLength / V6MaxPSKLength (bytes)


def new_snell_psk() -> str:
    """Random PSK: base64 of 16 random bytes = 24 ASCII bytes (within Snell v6's 12..255)."""
    return base64.b64encode(secrets.token_bytes(16)).decode()


def snell_client_from_listener(lst: dict, name: str, server: str) -> dict:
    """Client proxy matching a Snell listener (version / mode / obfs-opts mirrored as configured).

    Mihomo inbound defaults: version 4 when omitted, udp true (listener/inbound/snell.go).
    """
    ver = int(lst.get("version") or 4)
    client = {"name": name, "type": "snell", "server": server, "port": int(lst.get("port") or 0),
              "psk": str(lst.get("psk", "")), "version": ver, "udp": lst.get("udp", True) is not False}
    if ver == 6 and lst.get("mode"):
        client["mode"] = str(lst["mode"])
    obfs = lst.get("obfs-opts")
    if ver != 6 and isinstance(obfs, dict) and obfs.get("mode"):
        client["obfs-opts"] = dict(obfs)
    return client


def listener_to_inbound(lst: dict, env: dict, existing_by_name: dict = None) -> dict:
    """Convert a Mihomo server listener dict into an inbound record with a complete client proxy dict."""
    if not isinstance(lst, dict):
        raise ValueError("Invalid listener entry")
    name = str(lst.get("name") or "").strip()
    ltype = str(lst.get("type") or "").strip().lower()
    port = int(lst.get("port") or 0)
    if not name or not ltype or not (1 <= port <= 65535):
        raise ValueError(f"Invalid listener name/type/port: {lst}")

    prev = (existing_by_name or {}).get(name)
    iid = prev["id"] if (prev and prev.get("id")) else secrets.token_hex(6)
    created = prev["created"] if (prev and prev.get("created")) else int(time.time())

    ip = env.get("SERVER_IP", "")
    domain = env.get("DOMAIN", "").removeprefix("*.") or ip
    label = name
    has_cert = bool(lst.get("certificate"))
    srv = domain if has_cert else ip
    user, pw, uid, flow, alter_id = _first_user_creds(lst.get("users"))

    if ltype == "vless" and isinstance(lst.get("reality-config"), dict):
        kind = "vless-reality"
        rcfg = lst["reality-config"]
        snames = rcfg.get("server-names")
        sni = (snames[0] if isinstance(snames, list) and snames else str(rcfg.get("dest", "")).split(":")[0]).strip() or pick_reality_sni()
        sids = rcfg.get("short-id")
        sid = str(sids[0] if isinstance(sids, list) and sids else (sids or "")).strip()
        priv = str(rcfg.get("private-key") or "").strip()
        pub = ""
        if prev and isinstance(prev.get("client"), dict):
            prev_ropts = prev["client"].get("reality-opts") or {}
            if prev.get("listener", {}).get("reality-config", {}).get("private-key") == priv:
                pub = prev_ropts.get("public-key", "")
        if not pub:
            pub = x25519_pub_from_priv(priv)
        client = {
            "name": label, "type": "vless", "server": ip, "port": port,
            "uuid": uid, "tls": True, "flow": flow or "xtls-rprx-vision",
            "client-fingerprint": "safari",
        }
        if lst.get("decryption") and str(lst.get("decryption")) != "none":
            enc = ""
            if prev and isinstance(prev.get("client"), dict) and prev.get("listener", {}).get("decryption") == lst.get("decryption"):
                enc = prev["client"].get("encryption", "")
            if not enc:
                enc = derive_vless_encryption(str(lst["decryption"]))
            if enc:
                client["encryption"] = enc
        client.update({
            "reality-opts": {"public-key": pub, "short-id": sid},
            "network": "tcp", "udp": True, "servername": sni,
        })
    elif ltype == "vless":
        kind = "vless"
        client = {
            "name": label, "type": "vless", "server": srv, "port": port,
            "uuid": uid, "tls": has_cert, "udp": True,
        }
        if has_cert:
            client["servername"] = domain
            client["client-fingerprint"] = "chrome"
        if isinstance(lst.get("xhttp-config"), dict):
            xcfg = lst["xhttp-config"]
            xopts = {"path": str(xcfg.get("path", "/")), "mode": str(xcfg.get("mode", "auto"))}
            if xcfg.get("x-padding-bytes"):
                xopts["x-padding-bytes"] = str(xcfg["x-padding-bytes"])
            client["network"] = "xhttp"
            client["xhttp-opts"] = xopts
        elif lst.get("ws-path"):
            wpath = str(lst["ws-path"])
            client["network"] = "ws"
            client["ws-opts"] = {"path": wpath, "headers": {"Host": srv}}
        elif lst.get("grpc-service-name"):
            client["network"] = "grpc"
            client["grpc-opts"] = {"grpc-service-name": str(lst["grpc-service-name"])}
        else:
            client["network"] = "tcp"
            if flow:
                client["flow"] = flow
        if lst.get("decryption") and str(lst.get("decryption")) != "none":
            enc = ""
            if prev and isinstance(prev.get("client"), dict) and prev.get("listener", {}).get("decryption") == lst.get("decryption"):
                enc = prev["client"].get("encryption", "")
            if not enc:
                enc = derive_vless_encryption(str(lst["decryption"]))
            if enc:
                client["encryption"] = enc
    elif ltype in ("shadowsocks", "ss"):
        kind = "shadowsocks"
        client = {
            "name": label, "type": "ss", "server": ip, "port": port,
            "cipher": str(lst.get("cipher", "aes-256-gcm")),
            "password": str(lst.get("password", pw)), "udp": True,
        }
    elif ltype == "hysteria2":
        kind = "hysteria2"
        alpn = lst.get("alpn") if isinstance(lst.get("alpn"), list) else ["h3"]
        client = {
            "name": label, "type": "hysteria2", "server": domain, "port": port,
            "password": str(lst.get("password") or pw), "sni": domain, "alpn": alpn,
            "udp": True,
        }
        if lst.get("obfs"):
            client["obfs"] = str(lst["obfs"])
            if lst.get("obfs-password"):
                client["obfs-password"] = str(lst["obfs-password"])
    elif ltype == "hysteria2-realm":
        kind = "hysteria2-realm"
        alpn = lst.get("alpn") if isinstance(lst.get("alpn"), list) else ["h2", "http/1.1"]
        client = {
            "name": label, "type": "hysteria2", "server": domain, "port": port,
            "password": str(lst.get("token") or pw), "sni": domain, "alpn": alpn,
            "udp": True,
        }
    elif ltype == "anytls":
        kind = "anytls"
        prev_fp = ""
        if prev and isinstance(prev.get("client"), dict):
            prev_fp = str(prev["client"].get("client-fingerprint") or "")
        fp = prev_fp if prev_fp in ANYTLS_FP_POOL else random.choice(ANYTLS_FP_POOL)
        client = {
            "name": label, "type": "anytls", "server": domain, "port": port,
            "password": str(lst.get("password") or pw), "sni": domain,
            "client-fingerprint": fp, "udp": True,
        }
    elif ltype == "vmess":
        kind = "vmess"
        client = {
            "name": label, "type": "vmess", "server": srv, "port": port,
            "uuid": uid, "alterId": alter_id, "cipher": "auto", "tls": has_cert, "udp": True,
        }
        if has_cert:
            client["servername"] = domain
            client["client-fingerprint"] = "chrome"
        if lst.get("ws-path"):
            wpath = str(lst["ws-path"])
            client["network"] = "ws"
            client["ws-opts"] = {"path": wpath, "headers": {"Host": srv}}
        elif lst.get("grpc-service-name"):
            client["network"] = "grpc"
            client["grpc-opts"] = {"grpc-service-name": str(lst["grpc-service-name"])}
    elif ltype == "trusttunnel":
        kind = "trusttunnel"
        client = {
            "name": label, "type": "trusttunnel", "server": domain,
            "port": port, "username": user, "password": pw, "sni": domain,
            "udp": True,
        }
    elif ltype == "snell":
        kind = "snell"
        client = snell_client_from_listener(lst, label, ip)
    elif ltype == "tuic":
        kind = "tuic"
        cc = str(lst.get("congestion-controller") or "bbr")
        alpn = lst.get("alpn") if isinstance(lst.get("alpn"), list) else ["h3"]
        client = {
            "name": label, "type": "tuic", "server": domain, "port": port,
            "uuid": uid, "password": pw, "sni": domain, "alpn": alpn,
            "congestion-controller": cc, "udp-relay-mode": "native",
            "reduce-rtt": True, "udp": True,
        }
    elif ltype in ("shadowquic", "shadowqiuc"):
        kind = "shadowquic"
        jls_up = lst.get("jls-upstream") if isinstance(lst.get("jls-upstream"), dict) else {}
        jls_addr = str(jls_up.get("addr") or f"{pick_reality_sni()}:443")
        jls_host = jls_addr.rsplit(":", 1)[0]
        cc = str(lst.get("congestion-controller") or "bbr")
        zrtt = bool(lst.get("zero-rtt", True))
        client = {
            "name": label, "type": "shadowquic", "server": ip, "port": port,
            "username": user, "password": pw, "sni": jls_host, "alpn": ["h3"],
            "congestion-controller": cc, "zero-rtt": zrtt, "udp": True,
        }
    elif ltype == "mieru":
        kind = "mieru"
        tr = str(lst.get("transport") or "TCP").upper()
        client = {
            "name": label, "type": "mieru", "server": ip, "port": port,
            "transport": tr, "username": user, "password": pw, "udp": True,
        }
    elif ltype in ("sudoku", "soduku"):
        kind = "sudoku"
        priv_k = str(lst.get("key", ""))
        if prev and isinstance(prev.get("client"), dict) and prev["client"].get("key"):
            priv_k = prev["client"]["key"]
        client = {
            "name": label, "type": "sudoku", "server": ip, "port": port,
            "key": priv_k, "aead-method": str(lst.get("aead-method", "chacha20-poly1305")),
            "padding-min": int(lst.get("padding-min", 2)), "padding-max": int(lst.get("padding-max", 7)),
            "table-type": str(lst.get("table-type", "prefer_ascii")),
            "enable-pure-downlink": bool(lst.get("enable-pure-downlink", True)), "udp": True,
        }
    elif ltype == "http":
        kind = "http"
        client = {
            "name": label, "type": "http", "server": srv, "port": port,
            "username": user, "password": pw, "tls": has_cert, "udp": True,
        }
        if has_cert:
            client["sni"] = domain
    else:  # socks, socks5, mixed
        kind = "mixed" if ltype == "mixed" else "socks"
        client = {
            "name": label, "type": "socks5", "server": srv, "port": port,
            "username": user, "password": pw, "tls": has_cert, "udp": True,
        }

    return {
        "id": iid, "kind": kind, "port": port, "name": name,
        "created": created, "listener": lst, "client": client,
    }


def parse_custom_config_state(raw_yaml: str, env: dict = None) -> tuple:
    """Parse listeners, proxies, and proxy-providers from a full server YAML config."""
    if env is None:
        env = read_env()
    existing_by_name = {}
    for n in read_nodes():
        rc_inb = {
            "id": secrets.token_hex(6), "kind": "vless-reality", "port": n["port"],
            "name": n["name"], "created": int(time.time()),
            "listener": {"reality-config": {"private-key": n["priv"]}, "decryption": n.get("dec", "")},
            "client": reality_client(n, env),
        }
        existing_by_name[n["name"]] = rc_inb
    for i in load_inbounds():
        existing_by_name[i["name"]] = i

    raw_listeners = extract_top_level_yaml_section(raw_yaml, "listeners")
    new_inbounds = []
    cluster_names = cluster_proxy_names()
    if isinstance(raw_listeners, list):
        for item in raw_listeners:
            if isinstance(item, dict) and str(item.get("name") or "").startswith(CLUSTER_LISTENER_PREFIX):
                continue   # cluster link: managed by cluster.json, never a user node
            if isinstance(item, dict):
                try:
                    new_inbounds.append(listener_to_inbound(item, env, existing_by_name))
                except Exception as e:
                    sys.stderr.write(f"listener_to_inbound warning: {e}\n")

    raw_proxies = extract_top_level_yaml_section(raw_yaml, "proxies")
    new_proxies = []
    if isinstance(raw_proxies, list):
        for p in raw_proxies:
            if isinstance(p, dict) and p.get("name") and p.get("type"):
                if str(p["name"]) in cluster_names:
                    continue   # cluster member outbound: managed by cluster.json
                node = dict(p)
                if "udp" not in node or node["udp"] is None:
                    node["udp"] = True
                new_proxies.append(node)

    raw_providers = extract_top_level_yaml_section(raw_yaml, "proxy-providers")
    new_providers = raw_providers if isinstance(raw_providers, dict) else {}
    return new_inbounds, new_proxies, new_providers


# ---------------------------------------------------------------- inbound model
def build_inbound(kind: str, form: dict, env: dict) -> dict:
    if kind == "shadowqiuc":
        kind = "shadowquic"
    elif kind == "soduku":
        kind = "sudoku"
    if kind not in TYPES:
        raise ValueError("未知的入站类型")
    need_cert = kind in CERT_TYPES
    if kind in ("http", "socks") and form.get(f"{kind}_tls") == "1":
        need_cert = True
    if need_cert and not certs_present():
        raise ValueError(f"{kind} 启用 TLS 需要域名证书，未找到 {CERT}（请先在服务器执行 clashgate cert）")

    port_s = form.get("port", "").strip()
    if port_s:
        if not port_s.isdigit() or not 1 <= int(port_s) <= 65535:
            raise ValueError("端口无效（1-65535）")
        port = int(port_s)
        if port in used_ports(env):
            raise ValueError(f"端口 {port} 已被占用")
    else:
        port = pick_port(env)
    existing_names = {n["name"] for n in read_nodes()} | {i["name"] for i in load_inbounds()}
    name = form.get("name", "").strip()
    default_base = DEFAULT_NODE_NAMES.get(kind, kind)
    if not name:
        name = default_base if default_base not in existing_names else f"{default_base}-{port}"
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,48}", name):
        raise ValueError("名称仅限 1-48 位字母、数字及 . _ -")
    if name in existing_names:
        raise ValueError(f"入站名称「{name}」已存在")
    ip = env.get("SERVER_IP", "")
    domain = env.get("DOMAIN", "").removeprefix("*.") or ip
    base = {"name": name, "port": port, "listen": "0.0.0.0"}
    label = name

    if kind == "vless-reality":
        sni = resolve_sni(form)
        priv, pub = reality_keypair()
        uid, sid = str(uuidlib.uuid4()), secrets.token_hex(4)
        dec, enc = vless_x25519_keypair()
        listener = {**base, "type": "vless", "udp": True,
                    "users": [{"username": "user", "uuid": uid, "flow": "xtls-rprx-vision"}],
                    "decryption": dec,
                    "reality-config": {"dest": f"{sni}:443", "private-key": priv,
                                       "short-id": [sid], "server-names": [sni]}}
        client = {"name": label, "type": "vless", "server": ip, "port": port,
                  "uuid": uid, "tls": True, "flow": "xtls-rprx-vision", "client-fingerprint": "safari",
                  "encryption": enc,
                  "reality-opts": {"public-key": pub, "short-id": sid},
                  "network": "tcp", "udp": True, "servername": sni}

    elif kind == "shadowsocks":
        cipher = "aes-256-gcm"
        pw = secrets.token_urlsafe(16)
        listener = {"name": name, "type": "shadowsocks", "udp": True, "port": port,
                    "listen": "0.0.0.0", "password": pw, "cipher": cipher}
        client = {"name": label, "type": "ss", "server": ip, "port": port,
                  "cipher": cipher, "password": pw, "udp": True}

    elif kind == "hysteria2":
        pw = secrets.token_urlsafe(18)
        obfs_pw = secrets.token_urlsafe(16)
        listener = {**base, "type": "hysteria2", "users": {"user": pw},
                    "certificate": CERT, "private-key": KEY, "alpn": ["h3"],
                    "ignore-client-bandwidth": False,
                    "obfs": "salamander", "obfs-password": obfs_pw}
        client = {"name": label, "type": "hysteria2", "server": domain, "port": port,
                  "password": pw, "sni": domain, "alpn": ["h3"],
                  "obfs": "salamander", "obfs-password": obfs_pw, "udp": True}

    elif kind == "snell":
        if not mihomo_supports_snell_v6():
            raise ValueError(f"Snell V6 需要 Mihomo 内核 v{SNELL_V6_MIN_CORE} 或更高版本，请先点击顶部「更新内核」")
        # Snell v6 (Mihomo v1.19.34+): PSK-derived traffic shaping replaces simple-obfs,
        # so no obfs-opts; mode omitted = "default" on both sides.
        psk = new_snell_psk()
        listener = {**base, "type": "snell", "psk": psk, "version": SNELL_VERSION, "udp": True}
        client = {"name": label, "type": "snell", "server": ip, "port": port,
                  "psk": psk, "version": SNELL_VERSION, "udp": True}

    elif kind == "trusttunnel":
        user = form.get("tt_user", "").strip() or "user"
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,32}", user):
            raise ValueError("TrustTunnel 用户名无效（1-32 位字母、数字及 . _ -）")
        cc = (form.get("tt_cc") or "bbr").strip()
        if cc not in ("bbr", "cubic"):
            cc = "bbr"
        pw = secrets.token_urlsafe(18)
        listener = {**base, "type": "trusttunnel", "users": [{"username": user, "password": pw}],
                    "certificate": CERT, "private-key": KEY, "network": ["tcp", "udp"],
                    "congestion-controller": cc}
        client = {"name": label, "type": "trusttunnel", "server": domain,
                  "port": port, "username": user, "password": pw, "sni": domain,
                  "udp": True}

    elif kind == "http":
        user = (form.get("http_user") or "user").strip()
        pw = secrets.token_urlsafe(14)
        use_tls = form.get("http_tls") == "1"
        listener = {**base, "type": "http", "users": [{"username": user, "password": pw}]}
        if use_tls:
            listener["certificate"] = CERT
            listener["private-key"] = KEY
        client = {"name": label, "type": "http",
                  "server": domain if use_tls else ip, "port": port,
                  "username": user, "password": pw, "tls": use_tls, "udp": True}
        if use_tls:
            client["sni"] = domain

    elif kind == "socks":
        user = (form.get("socks_user") or "user").strip()
        pw = secrets.token_urlsafe(14)
        use_tls = form.get("socks_tls") == "1"
        listener = {**base, "type": "socks", "udp": True, "users": [{"username": user, "password": pw}]}
        if use_tls:
            listener["certificate"] = CERT
            listener["private-key"] = KEY
        client = {"name": label, "type": "socks5",
                  "server": domain if use_tls else ip, "port": port,
                  "username": user, "password": pw, "tls": use_tls, "udp": True}

    elif kind == "anytls":
        user = (form.get("anytls_user") or "user").strip() or "user"
        fp = random.choice(ANYTLS_FP_POOL)
        pw = secrets.token_urlsafe(18)
        listener = {**base, "type": "anytls", "users": {user: pw},
                    "certificate": CERT, "private-key": KEY,
                    "padding-scheme": random_anytls_padding()}
        client = {"name": label, "type": "anytls", "server": domain, "port": port,
                  "password": pw, "sni": domain, "client-fingerprint": fp,
                  "udp": True}

    elif kind == "mieru":
        user = (form.get("mieru_user") or "user").strip() or "user"
        transport = (form.get("mieru_transport") or "TCP").strip().upper()
        if transport not in ("TCP", "UDP"):
            transport = "TCP"
        pw = secrets.token_urlsafe(16)
        listener = {**base, "type": "mieru", "transport": transport, "users": {user: pw}}
        client = {"name": label, "type": "mieru", "server": ip, "port": port,
                  "transport": transport, "username": user, "password": pw, "udp": True}

    elif kind == "sudoku":
        aead = "chacha20-poly1305"
        table = "prefer_ascii"
        pure_dl = True
        priv_k, pub_k = sudoku_keypair()
        listener = {**base, "type": "sudoku", "key": pub_k, "aead-method": aead,
                    "padding-min": 2, "padding-max": 7, "table-type": table,
                    "enable-pure-downlink": pure_dl}
        client = {"name": label, "type": "sudoku", "server": ip, "port": port,
                  "key": priv_k, "aead-method": aead, "padding-min": 2, "padding-max": 7,
                  "table-type": table, "enable-pure-downlink": pure_dl, "udp": True}

    elif kind == "tuic":
        uid = str(uuidlib.uuid4())
        pw = secrets.token_urlsafe(18)
        cc = (form.get("tuic_cc") or "bbr").strip()
        if cc not in ("bbr", "cubic", "new_reno"):
            cc = "bbr"
        udp_mode = "native"
        listener = {**base, "type": "tuic", "users": {uid: pw},
                    "certificate": CERT, "private-key": KEY,
                    "congestion-controller": cc, "alpn": ["h3"]}
        client = {"name": label, "type": "tuic", "server": domain, "port": port,
                  "uuid": uid, "password": pw, "sni": domain, "alpn": ["h3"],
                  "congestion-controller": cc, "udp-relay-mode": udp_mode,
                  "reduce-rtt": True, "udp": True}

    else:  # shadowquic
        user = (form.get("sq_user") or "user").strip() or "user"
        jls_host = resolve_sni(form)
        jls_addr = f"{jls_host}:443"
        cc = "bbr"
        zero_rtt = True
        pw = secrets.token_urlsafe(18)
        listener = {**base, "type": "shadowquic",
                    "users": [{"username": user, "password": pw}],
                    "jls-upstream": {"addr": jls_addr},
                    "congestion-controller": cc, "zero-rtt": zero_rtt,
                    "quic-version-probe": True, "max-idle-time": 30000,
                    "disable-mtu-discovery": False}
        client = {"name": label, "type": "shadowquic", "server": ip, "port": port,
                  "username": user, "password": pw, "sni": jls_host, "alpn": ["h3"],
                  "congestion-controller": cc, "zero-rtt": zero_rtt, "udp": True}

    return {"id": secrets.token_hex(6), "kind": kind, "port": port, "name": name,
            "created": int(time.time()), "listener": listener, "client": client}


def can_reset_inbound_password(inb: dict) -> bool:
    """Return True if the inbound has rotatable credentials; False for passwordless TLS listeners."""
    kind = str(inb.get("kind", "")).lower()
    lst = inb.get("listener") if isinstance(inb.get("listener"), dict) else {}
    cli = inb.get("client") if isinstance(inb.get("client"), dict) else {}
    if kind in ("vless-reality", "vless"):
        return True
    has_tls = bool(lst.get("certificate") or cli.get("tls"))
    has_pw = bool(
        cli.get("password") or cli.get("psk") or cli.get("key") or cli.get("uuid")
        or lst.get("password") or lst.get("psk") or lst.get("key") or lst.get("token")
        or lst.get("users")
    )
    if has_tls and not has_pw:
        return False
    return has_pw


def rotate_inbound_credentials(inb: dict) -> dict:
    """Rotate credentials in-place for an inbound dict (both server listener and client proxy)."""
    updated = json.loads(json.dumps(inb))
    kind = str(updated.get("kind", "")).lower()
    lst = updated.setdefault("listener", {})
    cli = updated.setdefault("client", {})

    if kind == "vless-reality" or (kind == "vless" and isinstance(lst.get("reality-config"), dict)):
        uid = str(uuidlib.uuid4())
        priv, pub = reality_keypair()
        sid = secrets.token_hex(4)
        dec, enc = vless_x25519_keypair()
        u_name = "user"
        if isinstance(lst.get("users"), list) and lst["users"] and isinstance(lst["users"][0], dict):
            u_name = str(lst["users"][0].get("username") or "user")
        lst["users"] = [{"username": u_name, "uuid": uid, "flow": "xtls-rprx-vision"}]
        lst["decryption"] = dec
        rcfg = lst.setdefault("reality-config", {})
        rcfg["private-key"] = priv
        rcfg["short-id"] = [sid]
        cli["uuid"] = uid
        cli["encryption"] = enc
        ropts = cli.setdefault("reality-opts", {})
        ropts["public-key"] = pub
        ropts["short-id"] = sid
    elif kind == "vless":
        uid = str(uuidlib.uuid4())
        dec, enc = vless_x25519_keypair()
        if isinstance(lst.get("users"), list) and lst["users"] and isinstance(lst["users"][0], dict):
            lst["users"][0]["uuid"] = uid
        else:
            lst["users"] = [{"username": "user", "uuid": uid}]
        lst["decryption"] = dec
        cli["uuid"] = uid
        cli["encryption"] = enc
    elif kind == "shadowsocks":
        pw = secrets.token_urlsafe(16)
        lst["password"] = pw
        cli["password"] = pw
    elif kind == "hysteria2":
        pw = secrets.token_urlsafe(18)
        obfs_pw = secrets.token_urlsafe(16)
        if isinstance(lst.get("users"), dict) and lst["users"]:
            u_key = next(iter(lst["users"].keys()))
            lst["users"] = {u_key: pw}
        else:
            lst["users"] = {"user": pw}
        lst["obfs"] = "salamander"
        lst["obfs-password"] = obfs_pw
        cli["password"] = pw
        cli["obfs"] = "salamander"
        cli["obfs-password"] = obfs_pw
    elif kind == "hysteria2-realm":
        tok = secrets.token_hex(16)
        lst["token"] = tok
        cli["password"] = tok
    elif kind == "snell":
        psk = new_snell_psk()
        lst["psk"] = psk
        cli["psk"] = psk
    elif kind == "anytls":
        pw = secrets.token_urlsafe(18)
        u_key = "user"
        if isinstance(lst.get("users"), dict) and lst["users"]:
            u_key = next(iter(lst["users"].keys()))
        lst["users"] = {u_key: pw}
        lst["padding-scheme"] = random_anytls_padding()
        cli["password"] = pw
    elif kind == "tuic":
        uid = str(uuidlib.uuid4())
        pw = secrets.token_urlsafe(18)
        lst["users"] = {uid: pw}
        cli["uuid"] = uid
        cli["password"] = pw
    elif kind == "sudoku":
        priv_k, pub_k = sudoku_keypair()
        lst["key"] = pub_k
        cli["key"] = priv_k
    elif kind == "vmess":
        uid = str(uuidlib.uuid4())
        if isinstance(lst.get("users"), list) and lst["users"] and isinstance(lst["users"][0], dict):
            lst["users"][0]["uuid"] = uid
        else:
            lst["users"] = [{"username": "user", "uuid": uid, "alterId": 0}]
        cli["uuid"] = uid
    elif kind == "mieru":
        pw = secrets.token_urlsafe(16)
        u_key = str(cli.get("username") or "user")
        if isinstance(lst.get("users"), dict) and lst["users"]:
            u_key = next(iter(lst["users"].keys()))
        lst["users"] = {u_key: pw}
        cli["password"] = pw
    else:  # trusttunnel, shadowquic, http, socks, mixed
        pw = secrets.token_urlsafe(18)
        u_name = str(cli.get("username") or "user")
        if isinstance(lst.get("users"), dict) and lst["users"]:
            u_key = next(iter(lst["users"].keys()))
            lst["users"] = {u_key: pw}
        else:
            if isinstance(lst.get("users"), list) and lst["users"] and isinstance(lst["users"][0], dict):
                u_name = str(lst["users"][0].get("username") or u_name)
            lst["users"] = [{"username": u_name, "password": pw}]
        cli["password"] = pw
    return updated


def render_nodes_tsv(nodes: list) -> str:
    out = []
    for n in nodes:
        dec = n.get("dec", "")
        enc = n.get("enc", "")
        if dec or enc:
            out.append(f"{n['name']}\t{n['port']}\t{n['uuid']}\t{n['priv']}\t{n['pub']}\t{n['sid']}\t{n['sni']}\t{dec}\t{enc}\n")
        else:
            out.append(f"{n['name']}\t{n['port']}\t{n['uuid']}\t{n['priv']}\t{n['pub']}\t{n['sid']}\t{n['sni']}\n")
    return "".join(out)


def render_reality(nodes: list) -> str:
    out = []
    for n in nodes:
        dec_line = f"    decryption: {n['dec']}\n" if n.get("dec") else ""
        out.append(
            f"  - name: {n['name']}\n"
            f"    type: vless\n"
            f"    udp: true\n"
            f"    port: {n['port']}\n"
            f"    listen: 0.0.0.0\n"
            f"    users:\n"
            f"      - username: user\n"
            f"        uuid: {n['uuid']}\n"
            f"        flow: xtls-rprx-vision\n"
            f"{dec_line}"
            f"    reality-config:\n"
            f"      dest: {n['sni']}:443\n"
            f"      private-key: {n['priv']}\n"
            f"      short-id:\n"
            f"        - {n['sid']}\n"
            f"      server-names:\n"
            f"        - {n['sni']}\n"
        )
    return "".join(out)


def render_extra(inbounds: list) -> str:
    return "".join("  - " + json.dumps(i["listener"], ensure_ascii=False) + "\n" for i in inbounds)


def assemble_config() -> str:
    """Same logic as core.sh assemble_config: custom_config.yaml if active, else template."""
    if is_custom_config_mode():
        with open(CUSTOM_CONF) as f:
            return f.read()
    ctrl = ""
    try:
        with open(FRAG_CONTROLLER) as f:
            ctrl = f.read()
    except FileNotFoundError:
        env = read_env()
        if env.get("MODE") == "auto-cert" and env.get("MIHOMO_SECRET"):
            ctrl = render_controller_fragment(env)

    providers_frag = ""
    try:
        with open(FRAG_PROVIDERS) as f:
            providers_frag = f.read()
    except FileNotFoundError:
        pass
    providers_lines = [l for l in providers_frag.splitlines() if l.strip()]
    providers_block = ("proxy-providers:\n" + "\n".join(providers_lines) + "\n") if providers_lines else ""

    proxies_frag = ""
    try:
        with open(FRAG_PROXIES) as f:
            proxies_frag = f.read()
    except FileNotFoundError:
        pass
    proxies_frag += "\n" + _read_frag(FRAG_CLUSTER_PROXIES)
    proxies_lines = [l for l in proxies_frag.splitlines() if l.strip()]
    proxies_block = ("proxies:\n" + "\n".join(proxies_lines) + "\n") if proxies_lines else "proxies: []\n"

    block = ""
    for frag in (FRAG_REALITY, FRAG_EXTRA, FRAG_CLUSTER_LISTENERS):
        try:
            with open(frag) as f:
                block += f.read()
        except FileNotFoundError:
            pass
    try:
        get_routing().ensure_seeded()
    except Exception as e:
        sys.stderr.write(f"routing seed warning: {e}\n")
    rp_block, pg_block, ru_block = get_routing().read_frags()

    out = []
    tpl_path = resolve_template_path("resources/server.yaml.tpl")
    with open(tpl_path) as f:
        for line in f:
            s = line.rstrip("\n")
            if s == "@@CONTROLLER@@":
                out.append(ctrl)
            elif s == "@@PROXY_PROVIDERS@@":
                if providers_block:
                    out.append(providers_block)
            elif s == "@@PROXIES@@":
                out.append(proxies_block)
            elif s == "@@RULE_PROVIDERS@@":
                if rp_block.strip():
                    out.append(rp_block if rp_block.endswith("\n") else rp_block + "\n")
            elif s == "@@PROXY_GROUPS@@":
                out.append(pg_block if pg_block.endswith("\n") else pg_block + "\n")
            elif s == "@@RULES@@":
                out.append(ru_block if ru_block.endswith("\n") else ru_block + "\n")
            elif s == "@@LISTENERS@@":
                out.append("listeners:\n" + block if block.strip() else "listeners: []\n")
            else:
                out.append(line)
    return "".join(out)


def _json_text(obj) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False)


def _snapshot_files(paths) -> dict:
    """Read the current contents of paths (None = file absent) for a later _restore_files."""
    backup = {}
    for p in paths:
        try:
            with open(p) as f:
                backup[p] = f.read()
        except FileNotFoundError:
            backup[p] = None
    return backup


def _restore_files(backup: dict):
    """Undo writes made after _snapshot_files: rewrite or remove each file (.json -> 0600)."""
    for p, data in backup.items():
        if data is None:
            if os.path.exists(p):
                os.remove(p)
        else:
            atomic_write(p, data, 0o600 if p.endswith(".json") else 0o640)


def atomic_write(path: str, data: str, mode=0o640):
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp-")
    with os.fdopen(fd, "w") as f:
        f.write(data)
    os.chmod(tmp, mode)
    try:
        st = os.stat(path)
        os.chown(tmp, st.st_uid, st.st_gid)
    except (FileNotFoundError, PermissionError):
        pass
    os.replace(tmp, path)


def _load_sessions_file() -> dict:
    now = time.time()
    try:
        with open(SESSIONS_JSON) as f:
            raw = json.load(f)
    except Exception:
        return {}
    out = {}
    if not isinstance(raw, dict):
        return out
    for tok, item in raw.items():
        if not isinstance(tok, str) or not isinstance(item, dict):
            continue
        csrf = item.get("csrf")
        try:
            exp = float(item.get("exp") or 0)
        except (TypeError, ValueError):
            continue
        if isinstance(csrf, str) and csrf and exp > now:
            out[tok] = {"csrf": csrf, "exp": exp}
    return out


def _save_sessions_file(sessions: dict):
    now = time.time()
    clean = {}
    for tok, item in sessions.items():
        if not isinstance(item, dict):
            continue
        csrf = item.get("csrf")
        try:
            exp = float(item.get("exp") or 0)
        except (TypeError, ValueError):
            continue
        if isinstance(csrf, str) and csrf and exp > now:
            clean[tok] = {"csrf": csrf, "exp": exp}
    try:
        atomic_write(SESSIONS_JSON, json.dumps(clean, ensure_ascii=False) + "\n", 0o600)
    except Exception as e:
        sys.stderr.write(f"session save failed: {e}\n")


def remember_session(tok: str, sess: dict):
    with _SESSION_LOCK:
        Panel.sessions[tok] = sess
        _save_sessions_file(Panel.sessions)


def revoke_other_sessions(keep_tok: str):
    """After a password change only the session that made it stays signed in."""
    with _SESSION_LOCK:
        for tok in [t for t in Panel.sessions if t != keep_tok]:
            Panel.sessions.pop(tok, None)
        _save_sessions_file(Panel.sessions)


def forget_session(tok: str):
    if not tok:
        return
    with _SESSION_LOCK:
        Panel.sessions.pop(tok, None)
        _save_sessions_file(Panel.sessions)


# ---------------------------------------------------------------- local node name (本机名称)
# Other panels in a cluster use this as the Mihomo proxy name of the link to this server. Any visible
# character is allowed: proxies are always written as JSON flow mappings (quoted, escaped), and cluster
# outbounds are never referenced from rule strings. Only invisible/unsafe characters are refused.
# Mirrored in App.vue (CG_NODE_NAME ... end node-name); tests compare both.
NODE_NAME_MAX = 15
# Names announced by other panels: older 1.14/1.15 builds allowed up to 20 characters.
NODE_NAME_PEER_MAX = 20
# Control characters, line/paragraph separators, zero-width and bidi-override characters.
_NODE_NAME_BAD = re.compile(r"[\x00-\x1f\x7f-\x9f\u200b-\u200f\u2028-\u202e\u2060-\u2064\u2066-\u2069\ufeff]")
RESERVED_PROXY_NAMES = {"DIRECT", "REJECT", "REJECT-DROP", "PASS", "COMPATIBLE", "GLOBAL"}


def validate_node_name(raw, max_len: int = NODE_NAME_MAX) -> str:
    """Return the cleaned 本机名称 or raise ValueError with a beginner-readable reason."""
    name = str(raw or "").strip()
    if not name:
        raise ValueError("本机名称不能为空")
    if len(name) > max_len:
        raise ValueError(f"本机名称最多 {max_len} 个字符")
    if _NODE_NAME_BAD.search(name):
        raise ValueError("本机名称不能包含换行、控制字符或不可见字符")
    if name.upper() in RESERVED_PROXY_NAMES:
        raise ValueError(f"「{name}」是内核保留名称，请换一个")
    return name


def validate_peer_name(raw) -> str:
    """A name another panel announced for itself (same rules, older builds' length limit)."""
    return validate_node_name(raw, NODE_NAME_PEER_MAX)


def default_node_name() -> str:
    """Suggested 本机名称 until the user sets one: the short host name, else ClashGate."""
    try:
        host = socket.gethostname().split(".")[0]
    except OSError:
        host = ""
    host = re.sub(r"[^A-Za-z0-9_-]+", "", host)[:NODE_NAME_MAX]
    try:
        return validate_node_name(host)
    except ValueError:
        return "ClashGate"


def local_node_name() -> str:
    return load_panel_settings().get("node_name") or default_node_name()


def load_panel_settings() -> dict:
    out = {"custom_server_enabled": False, "auto_update": False, "update_channel": "", "node_name": ""}
    try:
        with open(PANEL_SETTINGS) as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            out["custom_server_enabled"] = bool(raw.get("custom_server_enabled"))
            out["auto_update"] = bool(raw.get("auto_update"))
            ch = str(raw.get("update_channel") or "").strip().lower()
            if ch in ("stable", "test"):
                out["update_channel"] = ch
            try:
                # Names saved under the old 20-character limit are shortened, not dropped.
                out["node_name"] = validate_node_name(str(raw.get("node_name") or "").strip()[:NODE_NAME_MAX])
            except ValueError:
                pass
    except Exception:
        pass
    return out


def save_panel_settings(updates: dict):
    cur = load_panel_settings()
    for key in ("custom_server_enabled", "auto_update"):
        if key in updates:
            cur[key] = bool(updates[key])
    if "update_channel" in updates:
        ch = str(updates.get("update_channel") or "").strip().lower()
        if ch in ("stable", "test"):
            cur["update_channel"] = ch
    if "node_name" in updates:
        cur["node_name"] = validate_node_name(updates["node_name"])
    atomic_write(
        PANEL_SETTINGS,
        json.dumps(cur, indent=2) + "\n",
        0o600,
    )



def cert_failure_message(out: str, mode: str) -> str:
    text = out or ""
    low = text.lower()
    if ("80 端口被占用" in text or "address already in use" in low or "bind: permission denied" in low
            or "couldn't bind" in low or "port 80" in low and ("occup" in low or "busy" in low or "in use" in low)):
        return "重新生成证书失败：80 端口被占用。端口模式需要临时使用 80 端口，请释放该端口，或改用 Cloudflare DNS。"
    token_bad = mode == "dns" and (
        "api token" in low or "invalid api" in low or "authentication error" in low
        or "unauthorized" in low or "error code" in low and "token" in low
        or "dns 编辑权限" in text or "API Token" in text
    )
    if token_bad:
        tail = " | ".join(line.strip() for line in text.splitlines() if line.strip())[-360:]
        extra = f"（{tail}）" if tail else ""
        return "重新生成证书失败：Cloudflare API Token 无效，或没有该域名的 DNS 编辑权限。" + extra
    tail = " | ".join(line.strip() for line in text.splitlines() if line.strip())[-420:]
    if not tail:
        tail = "请检查域名解析、Token 权限或 80 端口是否被占用"
    return f"重新生成证书失败：{tail}"


def validate_config(path=CONF, bin_path: str = ""):
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, "ui"), exist_ok=True)
        cert_src = CS_ROOT + "/certs"
        if os.path.isdir(cert_src):
            try:
                os.symlink(cert_src, os.path.join(d, "certs"))
            except OSError:
                pass
        if os.path.isdir(CS_ROOT):
            for entry in os.listdir(CS_ROOT):
                if entry in ("ui", "certs", "config.yaml", "custom_config.yaml", "panel.json", "clashgate.env"):
                    continue
                src_p = os.path.join(CS_ROOT, entry)
                dst_p = os.path.join(d, entry)
                if (entry in ("ruleset", "zerotier", "tailscale")
                        or entry.endswith((".mmdb", ".dat", ".yaml", ".yml", ".mrs"))):
                    if not os.path.exists(dst_p):
                        try:
                            os.symlink(src_p, dst_p)
                        except OSError:
                            pass
        mmdb = CS_ROOT + "/country.mmdb"
        if os.path.isfile(mmdb) and not os.path.exists(os.path.join(d, "country.mmdb")):
            try:
                os.symlink(mmdb, os.path.join(d, "country.mmdb"))
            except OSError:
                pass
        safe = f"{CS_ROOT}:/etc/clashgate"
        test_path = path
        if ROOT and os.path.isfile(path):
            with open(path) as fp:
                txt = fp.read()
            if "/etc/clashgate/certs/" in txt and not os.path.isdir("/etc/clashgate/certs"):
                test_path = os.path.join(d, "test_config.yaml")
                with open(test_path, "w") as fp:
                    fp.write(txt.replace("/etc/clashgate/certs/", CS_ROOT + "/certs/"))
        env = dict(os.environ, SAFE_PATHS=safe)
        rc, out = run([bin_path or resolve_mihomo_bin(), "-t", "-d", d, "-f", test_path], env=env, timeout=90)
        if rc == 0 and os.path.isdir(CS_ROOT):
            for entry in os.listdir(d):
                if entry in ("ui", "certs", "test_config.yaml"):
                    continue
                src_p = os.path.join(d, entry)
                dst_p = os.path.join(CS_ROOT, entry)
                if os.path.islink(src_p) or os.path.exists(dst_p):
                    continue
                try:
                    shutil.move(src_p, dst_p)
                except Exception:
                    pass
        return rc, out


def ufw_specs_for_node(kind: str, port: int) -> set:
    p = int(port)
    if kind in ("vless-reality", "http"):
        return {f"{p}/tcp"}
    if kind in ("hysteria2", "tuic", "shadowquic"):
        return {f"{p}/udp"}
    return {f"{p}/tcp", f"{p}/udp"}


def collect_ufw_specs(nodes: list, inbounds: list) -> set:
    specs = set()
    for n in nodes:
        specs |= ufw_specs_for_node("vless-reality", n["port"])
    for i in inbounds:
        specs |= ufw_specs_for_node(i["kind"], i["port"])
    return specs


def sync_ufw(old_specs: set, new_specs: set):
    """When ufw or firewalld is active, allow newly added node ports and delete removed node ports (including UDP)."""
    env = read_env()
    cport = get_controller_port(env)
    protected = {"80/tcp", f"{env.get('PANEL_PORT') or 0}/tcp", f"{cport}/tcp"}
    # Ports of current cluster links (cluster.json is saved before this runs) are never closed here.
    protected |= cluster_ufw_specs()
    rc, out = run([UFW_BIN, "status"])
    if rc == 0 and "Status: active" in out:
        for spec in sorted(new_specs - old_specs):
            run([UFW_BIN, "allow", spec])
        for spec in sorted((old_specs - new_specs) - protected):
            run([UFW_BIN, "delete", "allow", spec])
        return
    rc, _ = run([FIREWALL_CMD_BIN, "--state"])
    if rc == 0:
        changed = False
        for spec in sorted(new_specs - old_specs):
            run([FIREWALL_CMD_BIN, "--permanent", f"--add-port={spec}"])
            changed = True
        for spec in sorted((old_specs - new_specs) - protected):
            run([FIREWALL_CMD_BIN, "--permanent", f"--remove-port={spec}"])
            changed = True
        if changed:
            run([FIREWALL_CMD_BIN, "--reload"])


def sync_client_files():
    """Keep /etc/clashgate/client/{mihomo-client,proxies}.yaml in sync with current nodes and inbounds."""
    try:
        env = read_env()
        proxies = [reality_client(n, env) for n in read_nodes()] + [i["client"] for i in load_inbounds()]
        os.makedirs(CLIENT_DIR, mode=0o700, exist_ok=True)
        atomic_write(CLIENT_DIR + "/mihomo-client.yaml", render_subscription(env, live=False), 0o600)
        p_body = "".join("  - " + json.dumps(p, ensure_ascii=False) + "\n" for p in proxies) if proxies else "  []\n"
        atomic_write(CLIENT_DIR + "/proxies.yaml", "proxies:\n" + p_body, 0o600)
    except Exception as e:
        sys.stderr.write(f"sync_client_files warning: {e}\n")


def replace_top_level_yaml_section(raw_yaml: str, section_key: str, new_block: str) -> str:
    """Replace or append a top-level YAML section in raw_yaml."""
    lines = raw_yaml.splitlines()
    out = []
    in_sec = False
    replaced = False
    for line in lines:
        cleaned = strip_yaml_comment(line.expandtabs(2))
        stripped = cleaned.lstrip(" ")
        indent = len(cleaned) - len(stripped)
        if not in_sec:
            if stripped and indent == 0:
                k, sep, _ = split_kv(stripped)
                if sep and k == section_key:
                    in_sec = True
                    replaced = True
                    if new_block.strip():
                        out.append(new_block.rstrip("\n"))
                    continue
            out.append(line)
        else:
            if stripped and indent == 0 and not (stripped == "-" or stripped.startswith("- ")):
                in_sec = False
                out.append(line)
    if not replaced and new_block.strip():
        if out and out[-1].strip():
            out.append("")
        out.append(new_block.rstrip("\n"))
    return "\n".join(out) + "\n"


def _sync_custom_conf_listeners(nodes: list, inbounds: list):
    """When in custom config mode, keep CUSTOM_CONF's `listeners:` block in sync with panel edits."""
    if not is_custom_config_mode():
        return
    try:
        with open(CUSTOM_CONF) as f:
            raw = f.read()
        st = load_cluster()
        l_body = (render_reality(nodes) + dump_yaml_proxies([i["listener"] for i in inbounds])
                  + dump_yaml_proxies([cluster_listener_from_link(l) for l in st["links"]]))
        new_block = ("listeners:\n" + l_body) if l_body.strip() else "listeners: []\n"
        updated = replace_top_level_yaml_section(raw, "listeners", new_block)
        atomic_write(CUSTOM_CONF, updated, 0o640)
    except Exception as e:
        sys.stderr.write(f"_sync_custom_conf_listeners warning: {e}\n")


def _sync_custom_conf_proxies(proxies: list):
    if not is_custom_config_mode():
        return
    try:
        with open(CUSTOM_CONF) as f:
            raw = f.read()
        st = load_cluster()
        p_body = dump_yaml_proxies(list(proxies) + [cluster_proxy_from_link(l) for l in st["links"]])
        new_block = ("proxies:\n" + p_body) if p_body.strip() else "proxies: []\n"
        updated = replace_top_level_yaml_section(raw, "proxies", new_block)
        atomic_write(CUSTOM_CONF, updated, 0o640)
    except Exception as e:
        sys.stderr.write(f"_sync_custom_conf_proxies warning: {e}\n")


def _sync_custom_conf_providers(providers: dict):
    if not is_custom_config_mode():
        return
    try:
        with open(CUSTOM_CONF) as f:
            raw = f.read()
        pv_body = dump_yaml_providers(providers)
        new_block = ("proxy-providers:\n" + pv_body) if pv_body.strip() else ""
        updated = replace_top_level_yaml_section(raw, "proxy-providers", new_block)
        atomic_write(CUSTOM_CONF, updated, 0o640)
    except Exception as e:
        sys.stderr.write(f"_sync_custom_conf_providers warning: {e}\n")


def wait_mihomo_ports(timeout=2.0):
    """Poll ss for up to ~2s so all expected ports are listening before responding."""
    expected = {int(n["port"]) for n in read_nodes()} | {int(i["port"]) for i in load_inbounds()}
    env = read_env()
    if env.get("MODE") == "auto-cert":
        expected.add(get_controller_port(env))
    if not expected:
        return
    deadline = time.monotonic() + timeout
    while True:
        st = mihomo_status()
        if st["active"] == "active" and expected.issubset(set(st["listening"])):
            return
        if time.monotonic() >= deadline:
            return
        time.sleep(0.15)


# ---------------------------------------------------------------- Pending Reload Log
def load_pending_reload() -> dict:
    default = {"items": [], "sub_token": "", "mihomo_secret": ""}
    try:
        with open(PENDING_RELOAD_JSON) as f:
            d = json.load(f)
            if isinstance(d, dict):
                items = d.get("items") if isinstance(d.get("items"), list) else []
                return {
                    "items": [it for it in items if isinstance(it, dict)],
                    "sub_token": str(d.get("sub_token") or ""),
                    "mihomo_secret": str(d.get("mihomo_secret") or ""),
                }
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return default


def save_pending_reload(state: dict):
    cleaned = {
        "items": [it for it in (state.get("items") or []) if isinstance(it, dict)],
        "sub_token": str(state.get("sub_token") or ""),
        "mihomo_secret": str(state.get("mihomo_secret") or ""),
    }
    atomic_write(PENDING_RELOAD_JSON, json.dumps(cleaned, indent=2, ensure_ascii=False) + "\n", 0o600)


_TRACKED_DRAFT_FILES = (
    NODES_TSV, INBOUNDS, PROXIES_JSON, PROVIDERS_JSON,
    FRAG_REALITY, FRAG_EXTRA, FRAG_PROXIES, FRAG_PROVIDERS,
    FRAG_CONTROLLER, CUSTOM_CONF,
    ROUTING_JSON, FRAG_RULE_PROVIDERS, FRAG_PROXY_GROUPS, FRAG_RULES,
)


def _all_tracked_draft_files() -> tuple:
    """Fixed tracked files plus any per-group routing YAML currently on disk."""
    extra = []
    try:
        for name in os.listdir(ROUTING_DIR):
            if name.endswith((".yaml", ".yml")):
                extra.append(os.path.join(ROUTING_DIR, name))
    except FileNotFoundError:
        pass
    return _TRACKED_DRAFT_FILES + tuple(extra)


def _is_tracked_draft_path(p: str) -> bool:
    if p in _TRACKED_DRAFT_FILES:
        return True
    try:
        return os.path.commonpath([p, ROUTING_DIR]) == ROUTING_DIR and p.endswith((".yaml", ".yml"))
    except ValueError:
        return False


def _conf_digest() -> str:
    try:
        with open(CONF, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return ""


def _ensure_pending_baseline():
    """Capture a snapshot of live draft files right before the first pending mutation."""
    st = load_pending_reload()
    has_pending = bool(st.get("items") or st.get("sub_token") or st.get("mihomo_secret"))
    if has_pending and os.path.isfile(PENDING_BASELINE_JSON):
        return
    files = {}
    for p in _all_tracked_draft_files():
        try:
            with open(p) as f:
                files[p] = f.read()
        except FileNotFoundError:
            files[p] = None
    snap = {"conf_sha256": _conf_digest(), "files": files}
    atomic_write(PENDING_BASELINE_JSON, json.dumps(snap, ensure_ascii=False) + "\n", 0o600)


def clear_pending_reload():
    for p in (PENDING_RELOAD_JSON, PENDING_BASELINE_JSON):
        try:
            if os.path.exists(p):
                os.remove(p)
        except OSError:
            pass


def _reconstruct_draft_from_live_conf():
    """Fallback reconstruction of draft files directly from live CONF + ENV_FILE + client/proxies.yaml."""
    env = read_env()
    atomic_write(FRAG_CONTROLLER, render_controller_fragment(env), 0o640)
    if not os.path.isfile(CONF):
        return
    with open(CONF) as f:
        conf_raw = f.read()
    live_clients_by_name = {}
    try:
        with open(CLIENT_DIR + "/proxies.yaml") as f:
            for cp in parse_mihomo_proxies(f.read()):
                if isinstance(cp, dict) and cp.get("name"):
                    live_clients_by_name[str(cp["name"])] = cp
    except Exception:
        pass
    new_inbounds, new_proxies, new_providers = parse_custom_config_state(conf_raw, env)
    for inb in new_inbounds:
        nm = inb.get("name")
        if nm in live_clients_by_name:
            inb["client"] = live_clients_by_name[nm]
    if is_custom_config_mode():
        atomic_write(CUSTOM_CONF, conf_raw, 0o640)
        atomic_write(NODES_TSV, "", 0o640)
        atomic_write(INBOUNDS, json.dumps(new_inbounds, indent=2, ensure_ascii=False), 0o600)
        atomic_write(PROXIES_JSON, json.dumps(new_proxies, indent=2, ensure_ascii=False), 0o600)
        atomic_write(PROVIDERS_JSON, json.dumps(new_providers, indent=2, ensure_ascii=False), 0o600)
        return
    reality_yaml_names = set(re.findall(r"^  - name:\s*(\S+)\s*$", conf_raw, re.M))
    restored_nodes = []
    restored_inbs = []
    for inb in new_inbounds:
        nm = inb.get("name", "")
        lst = inb.get("listener") or {}
        cli = inb.get("client") or {}
        rcfg = lst.get("reality-config") if isinstance(lst.get("reality-config"), dict) else None
        if nm in reality_yaml_names and rcfg:
            ropts = cli.get("reality-opts") if isinstance(cli.get("reality-opts"), dict) else {}
            sids = rcfg.get("short-id")
            sid = str(sids[0] if isinstance(sids, list) and sids else (sids or ropts.get("short-id") or ""))
            snames = rcfg.get("server-names")
            sni = str(snames[0] if isinstance(snames, list) and snames else cli.get("servername") or "")
            priv = str(rcfg.get("private-key") or "")
            pub = str(ropts.get("public-key") or x25519_pub_from_priv(priv))
            dec = str(lst.get("decryption") or "")
            enc = str(cli.get("encryption") or derive_vless_encryption(dec))
            restored_nodes.append({
                "name": nm,
                "port": int(inb["port"]),
                "uuid": str(cli.get("uuid") or ""),
                "priv": priv,
                "pub": pub,
                "sid": sid,
                "sni": sni,
                "dec": dec,
                "enc": enc,
            })
        else:
            restored_inbs.append(inb)
    cleaned_inbs = _dedup_inbounds(restored_inbs)
    atomic_write(NODES_TSV, render_nodes_tsv(restored_nodes), 0o640)
    atomic_write(FRAG_REALITY, render_reality(restored_nodes), 0o640)
    atomic_write(INBOUNDS, json.dumps(cleaned_inbs, indent=2, ensure_ascii=False), 0o600)
    atomic_write(FRAG_EXTRA, render_extra(cleaned_inbs), 0o640)
    atomic_write(PROXIES_JSON, json.dumps(new_proxies, indent=2, ensure_ascii=False), 0o600)
    atomic_write(FRAG_PROXIES, dump_yaml_proxies(new_proxies), 0o640)
    atomic_write(PROVIDERS_JSON, json.dumps(new_providers, indent=2, ensure_ascii=False), 0o600)
    atomic_write(FRAG_PROVIDERS, dump_yaml_providers(new_providers), 0o640)


    try:
        get_routing().ensure_seeded(force=False)
        get_routing().regenerate_frags()
    except Exception as e:
        sys.stderr.write(f"routing reconstruct warning: {e}\n")


def discard_pending_reload():
    """Roll back all draft files to match current live CONF without reloading Mihomo or touching CONF."""
    restored = False
    if os.path.isfile(PENDING_BASELINE_JSON):
        try:
            with open(PENDING_BASELINE_JSON) as f:
                snap = json.load(f)
            if isinstance(snap, dict) and isinstance(snap.get("files"), dict):
                cur_digest = _conf_digest()
                if not cur_digest or snap.get("conf_sha256") == cur_digest:
                    for p, data in snap["files"].items():
                        if not _is_tracked_draft_path(p):
                            continue
                        if data is None:
                            if os.path.exists(p):
                                os.remove(p)
                        else:
                            atomic_write(p, data, 0o600 if p.endswith(".json") else 0o640)
                    restored = True
        except Exception:
            restored = False
    if not restored:
        _reconstruct_draft_from_live_conf()
    else:
        # Ensure controller fragment also matches live env
        env = read_env()
        if os.path.exists(FRAG_CONTROLLER) or env.get("MODE") == "auto-cert":
            atomic_write(FRAG_CONTROLLER, render_controller_fragment(env), 0o640)
        # Drop routing group YAML files created after the baseline snapshot
        try:
            with open(PENDING_BASELINE_JSON) as f:
                snap2 = json.load(f)
            kept = set()
            if isinstance(snap2, dict) and isinstance(snap2.get("files"), dict):
                for p, data in snap2["files"].items():
                    if data is not None and _is_tracked_draft_path(p):
                        kept.add(p)
            if os.path.isdir(ROUTING_DIR):
                for name in os.listdir(ROUTING_DIR):
                    if not name.endswith((".yaml", ".yml")):
                        continue
                    fp = os.path.join(ROUTING_DIR, name)
                    if fp not in kept and os.path.isfile(fp):
                        os.remove(fp)
        except Exception:
            pass
    (sys.modules.get("panel") or sys.modules["__main__"])._PENDING_UFW_BASELINE = None
    _RECENT_ADD_REQS.clear()
    clear_pending_reload()


def record_pending_reload(op: str, name: str = "", port: int = None, kind: str = "", detail: str = "",
                          sub_token: str = None, mihomo_secret: str = None):
    st = load_pending_reload()
    items = list(st["items"])
    if sub_token is not None:
        st["sub_token"] = sub_token
    if mihomo_secret is not None:
        st["mihomo_secret"] = mihomo_secret

    if op in ("reset-secret", "reset-sub"):
        items = [it for it in items if it.get("op") != op]
        items.append({"op": op, "kind": kind or op, "name": name, "port": port, "detail": detail})
    elif op == "delete":
        had_add = any(it.get("op") == "add" and it.get("name") == name and (it.get("kind") == kind or not kind) for it in items)
        items = [it for it in items if not (it.get("name") == name and it.get("op") in ("add", "reset-password", "delete"))]
        if not had_add:
            items.append({"op": "delete", "kind": kind, "name": name, "port": port, "detail": detail})
    elif op == "reset-password":
        has_add_or_rst = any(it.get("name") == name and it.get("op") in ("add", "reset-password") for it in items)
        if not has_add_or_rst:
            items.append({"op": "reset-password", "kind": kind, "name": name, "port": port, "detail": detail})
        else:
            for it in items:
                if it.get("name") == name and it.get("op") == "reset-password":
                    it["detail"] = detail
    elif op == "add":
        items = [it for it in items if not (it.get("name") == name and it.get("op") in ("add", "delete"))]
        items.append({"op": "add", "kind": kind, "name": name, "port": port, "detail": detail})
    elif op in ("add-routing", "delete-routing", "rename-routing", "reorder-routing", "update-routing", "import-routing"):
        items = [it for it in items if not (it.get("op") == op and it.get("name") == name)]
        items.append({"op": op, "kind": "routing", "name": name, "port": port, "detail": detail})
    elif op in ("add-proxy", "delete-proxy", "add-provider", "delete-provider"):
        base_kind = "proxy" if "proxy" in op else "provider"
        if op.startswith("delete-"):
            had_add = any(it.get("op") == f"add-{base_kind}" and it.get("name") == name for it in items)
            items = [it for it in items if not (it.get("name") == name and it.get("op") in (f"add-{base_kind}", f"delete-{base_kind}"))]
            if not had_add:
                items.append({"op": op, "kind": base_kind, "name": name, "port": port, "detail": detail})
        else:
            items = [it for it in items if not (it.get("name") == name and it.get("op") in (f"add-{base_kind}", f"delete-{base_kind}"))]
            items.append({"op": op, "kind": base_kind, "name": name, "port": port, "detail": detail})
    else:
        items.append({"op": op, "kind": kind, "name": name, "port": port, "detail": detail})

    st["items"] = items
    save_pending_reload(st)


def _dedup_inbounds(items: list) -> list:
    out = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        nm = str(item.get("name") or "")
        if nm and nm in seen:
            continue
        if nm:
            seen.add(nm)
        if isinstance(item.get("client"), dict) and nm:
            item["client"]["name"] = nm
            item["client"].pop("skip-cert-verify", None)
        out.append(item)
    return out


def save_inbounds(new: list):
    """Persist inbounds.json and server/client config fragments to disk without reloading Mihomo."""
    _ensure_pending_baseline()
    cur_nodes = read_nodes()
    _panel = sys.modules.get("panel") or sys.modules["__main__"]
    if _panel._PENDING_UFW_BASELINE is None:
        _panel._PENDING_UFW_BASELINE = collect_ufw_specs(cur_nodes, load_inbounds())
    cleaned = _dedup_inbounds(new)
    atomic_write(INBOUNDS, json.dumps(cleaned, indent=2, ensure_ascii=False), 0o600)
    atomic_write(FRAG_EXTRA, render_extra(cleaned), 0o640)
    _sync_custom_conf_listeners(cur_nodes, cleaned)
    # 0.96: draft only. Live CONF / client sync / reload happen solely in do_action(reload|restart).


def save_nodes(new_nodes: list):
    """Persist install-time VLESS Reality nodes (nodes.tsv) and config fragments to disk without reloading Mihomo."""
    _ensure_pending_baseline()
    cur_inbs = load_inbounds()
    _panel = sys.modules.get("panel") or sys.modules["__main__"]
    if _panel._PENDING_UFW_BASELINE is None:
        _panel._PENDING_UFW_BASELINE = collect_ufw_specs(read_nodes(), cur_inbs)
    atomic_write(NODES_TSV, render_nodes_tsv(new_nodes), 0o640)
    atomic_write(FRAG_REALITY, render_reality(new_nodes), 0o640)
    _sync_custom_conf_listeners(new_nodes, cur_inbs)
    # 0.96: draft only. Live CONF / client sync / reload happen solely in do_action(reload|restart).


def save_server_proxies(new_proxies: list):
    """Persist server outbound proxies to disk ONLY (proxies.json + proxies.extra.yaml) without writing live CONF or reloading Mihomo."""
    _ensure_pending_baseline()
    files = (PROXIES_JSON, FRAG_PROXIES, CUSTOM_CONF) if is_custom_config_mode() else (PROXIES_JSON, FRAG_PROXIES)
    backup = _snapshot_files(files)
    try:
        atomic_write(PROXIES_JSON, json.dumps(new_proxies, indent=2, ensure_ascii=False), 0o600)
        atomic_write(FRAG_PROXIES, dump_yaml_proxies(new_proxies), 0o640)
        _sync_custom_conf_proxies(new_proxies)
    except Exception:
        _restore_files(backup)
        raise


def save_proxy_providers(new_providers: dict):
    """Persist server proxy-providers to disk ONLY (providers.json + providers.extra.yaml) without writing live CONF or reloading Mihomo."""
    _ensure_pending_baseline()
    files = (PROVIDERS_JSON, FRAG_PROVIDERS, CUSTOM_CONF) if is_custom_config_mode() else (PROVIDERS_JSON, FRAG_PROVIDERS)
    backup = _snapshot_files(files)
    try:
        atomic_write(PROVIDERS_JSON, json.dumps(new_providers, indent=2, ensure_ascii=False), 0o600)
        atomic_write(FRAG_PROVIDERS, dump_yaml_providers(new_providers), 0o640)
        _sync_custom_conf_providers(new_providers)
    except Exception:
        _restore_files(backup)
        raise



def apply_custom_config(raw_yaml: str):
    """Validate and apply user-supplied full server config, syncing listeners, outbounds, and client subscription."""
    s = (raw_yaml or "").strip()
    if not s:
        raise ValueError("请输入完整的 Mihomo 服务端配置内容")
    s = sanitize_doh_url_line(s) + "\n"
    # mihomo -t does not open TLS files, so a wrong path would "pass" and fail only at runtime.
    missing = missing_cert_files(s)
    if missing:
        raise ValueError("证书文件不存在或无法读取：" + ", ".join(missing))
    was_custom = is_custom_config_mode()
    old_specs = collect_ufw_specs(read_nodes(), load_inbounds())
    files = (CUSTOM_CONF, CONF, NODES_TSV, INBOUNDS, PROXIES_JSON, PROVIDERS_JSON)
    backup = _snapshot_files(files)
    try:
        if not was_custom:
            for p in (NODES_TSV, INBOUNDS, PROXIES_JSON, PROVIDERS_JSON):
                if backup[p] is not None:
                    atomic_write(p + ".tplbak", backup[p], 0o600)
        atomic_write(CUSTOM_CONF, s, 0o640)
        atomic_write(CONF, s, 0o640)
        rc, out = validate_config()
        if rc != 0:
            raise RuntimeError("配置校验失败（mihomo -t）：" + out[-800:])
        sync_env_from_custom_config(s)
        env = read_env()
        new_inbounds, new_proxies, new_providers = parse_custom_config_state(s, env)
        atomic_write(NODES_TSV, "", 0o640)
        atomic_write(INBOUNDS, json.dumps(new_inbounds, indent=2, ensure_ascii=False), 0o600)
        atomic_write(PROXIES_JSON, json.dumps(new_proxies, indent=2, ensure_ascii=False), 0o600)
        atomic_write(PROVIDERS_JSON, json.dumps(new_providers, indent=2, ensure_ascii=False), 0o600)
        rc, out = run([SYSTEMCTL, "restart", "mihomo"])
        if rc != 0:
            raise RuntimeError("重启失败：" + out[-800:])
    except Exception:
        _restore_files(backup)
        run([SYSTEMCTL, "restart", "mihomo"])
        raise
    sync_client_files()
    sync_ufw(old_specs, collect_ufw_specs([], new_inbounds))
    wait_mihomo_ports()


def new_default_reality_node(env: dict) -> dict:
    """A fresh install-style VlessReality node on a random free-looking port."""
    reserved = {80, 443, int(env.get("PANEL_PORT", "0") or 0), get_controller_port(env)}
    port = 28443
    for _ in range(1000):
        cand = random.randint(20000, 39999)
        if cand not in reserved:
            port = cand
            break
    priv, pub = reality_keypair()
    dec, enc = vless_x25519_keypair()
    return {
        "name": "VlessReality",
        "port": port,
        "uuid": str(uuidlib.uuid4()),
        "priv": priv,
        "pub": pub,
        "sid": secrets.token_hex(4),
        "sni": pick_reality_sni(),
        "dec": dec,
        "enc": enc,
    }


def _write_template_state(nodes: list, inbs: list, proxies: list, providers: dict, env: dict):
    """Write the panel state + template fragments and assemble CONF from them (no restart)."""
    atomic_write(NODES_TSV, render_nodes_tsv(nodes), 0o640)
    atomic_write(INBOUNDS, json.dumps(inbs, indent=2, ensure_ascii=False), 0o600)
    atomic_write(PROXIES_JSON, json.dumps(proxies, indent=2, ensure_ascii=False), 0o600)
    atomic_write(PROVIDERS_JSON, json.dumps(providers, indent=2, ensure_ascii=False), 0o600)
    atomic_write(FRAG_REALITY, render_reality(nodes), 0o640)
    atomic_write(FRAG_EXTRA, render_extra(inbs), 0o640)
    atomic_write(FRAG_PROXIES, dump_yaml_proxies(proxies), 0o640)
    atomic_write(FRAG_PROVIDERS, dump_yaml_providers(providers), 0o640)
    atomic_write(FRAG_CONTROLLER, render_controller_fragment(env), 0o640)
    get_routing().ensure_seeded()
    atomic_write(CONF, assemble_config(), 0o640)


def disable_custom_config() -> str:
    """Leave custom mode: keep the user's file as CUSTOM_SAVED, then rebuild the default template
    config, validate it and restart Mihomo. Node sources, first that passes `mihomo -t` wins:
      "restored" - the panel's nodes from before custom mode (*.tplbak);
      "kept"     - no (usable) backup, e.g. custom mode entered by an older version: the
                   nodes the panel tracked while in custom mode;
      "reset"    - neither validates: a fresh default VlessReality node, no outbounds.
    Returns which one was used. On any other failure everything is rolled back."""
    if not is_custom_config_mode():
        return ""
    env = read_env()
    old_specs = collect_ufw_specs(read_nodes(), load_inbounds())
    state_files = (NODES_TSV, INBOUNDS, PROXIES_JSON, PROVIDERS_JSON)
    files = (CUSTOM_CONF, CUSTOM_SAVED, CONF) + state_files + (
        FRAG_REALITY, FRAG_EXTRA, FRAG_PROXIES, FRAG_PROVIDERS, FRAG_CONTROLLER)
    backup = _snapshot_files(files)
    try:
        candidates = []
        if any(os.path.exists(p + ".tplbak") for p in state_files):
            def bak(p, empty):
                try:
                    with open(p + ".tplbak") as f:
                        raw = f.read()
                except FileNotFoundError:
                    return empty
                return raw
            nodes_bak = _parse_nodes_tsv(bak(NODES_TSV, ""))
            try:
                inbs_bak = _clean_inbounds(json.loads(bak(INBOUNDS, "[]") or "[]"))
                prox_bak = json.loads(bak(PROXIES_JSON, "[]") or "[]")
                prov_bak = json.loads(bak(PROVIDERS_JSON, "{}") or "{}")
                candidates.append(("restored", nodes_bak, inbs_bak, prox_bak, prov_bak))
            except (ValueError, TypeError):
                pass
        candidates.append(("kept", read_nodes(), load_inbounds(), load_server_proxies(), load_proxy_providers()))
        candidates.append(("reset", [new_default_reality_node(env)], [], [], {}))

        atomic_write(CUSTOM_SAVED, backup[CUSTOM_CONF], 0o640)
        os.remove(CUSTOM_CONF)
        used, last_err = "", ""
        for name, nodes, inbs, proxies, providers in candidates:
            if not nodes and not inbs:
                nodes = [new_default_reality_node(env)]
            _write_template_state(nodes, inbs, proxies, providers, env)
            rc, out = validate_config()
            if rc == 0:
                used = name
                break
            last_err = out[-800:]
            sys.stderr.write(f"disable_custom_config: {name} state failed mihomo -t, trying next\n")
        if not used:
            raise RuntimeError("配置校验失败（mihomo -t）：" + last_err)
        rc, out = run([SYSTEMCTL, "restart", "mihomo"])
        if rc != 0:
            raise RuntimeError("重启失败：" + out[-800:])
        for p in state_files:
            bak_p = p + ".tplbak"
            if os.path.exists(bak_p):
                os.remove(bak_p)
    except Exception:
        _restore_files(backup)
        run([SYSTEMCTL, "restart", "mihomo"])
        raise
    sync_client_files()
    sync_ufw(old_specs, collect_ufw_specs(read_nodes(), load_inbounds()))
    wait_mihomo_ports()
    return used


def reset_to_template_config():
    """Restore server config to clean default template and generate a default VlessReality node."""
    env = read_env()
    old_specs = collect_ufw_specs(read_nodes(), load_inbounds())
    files = (CUSTOM_CONF, CONF, NODES_TSV, INBOUNDS, PROXIES_JSON, PROVIDERS_JSON,
             FRAG_REALITY, FRAG_EXTRA, FRAG_PROXIES, FRAG_PROVIDERS, FRAG_CONTROLLER)
    backup = _snapshot_files(files)
    try:
        default_node = new_default_reality_node(env)
        if os.path.exists(CUSTOM_CONF):
            os.remove(CUSTOM_CONF)
        atomic_write(NODES_TSV, render_nodes_tsv([default_node]), 0o640)
        atomic_write(INBOUNDS, "[]\n", 0o600)
        atomic_write(PROXIES_JSON, "[]\n", 0o600)
        atomic_write(PROVIDERS_JSON, "{}\n", 0o600)
        atomic_write(FRAG_REALITY, render_reality([default_node]), 0o640)
        atomic_write(FRAG_EXTRA, "", 0o640)
        atomic_write(FRAG_PROXIES, "", 0o640)
        atomic_write(FRAG_PROVIDERS, "", 0o640)
        atomic_write(FRAG_CONTROLLER, render_controller_fragment(env), 0o640)
        get_routing().ensure_seeded(force=True)
        atomic_write(CONF, assemble_config(), 0o640)
        rc, out = validate_config()
        if rc != 0:
            raise RuntimeError("配置校验失败（mihomo -t）：" + out[-800:])
        rc, out = run([SYSTEMCTL, "restart", "mihomo"])
        if rc != 0:
            raise RuntimeError("重启失败：" + out[-800:])
        for p in (NODES_TSV, INBOUNDS, PROXIES_JSON, PROVIDERS_JSON):
            bak_p = p + ".tplbak"
            if os.path.exists(bak_p):
                os.remove(bak_p)
    except Exception:
        _restore_files(backup)
        run([SYSTEMCTL, "restart", "mihomo"])
        raise
    sync_client_files()
    sync_ufw(old_specs, collect_ufw_specs(read_nodes(), load_inbounds()))
    wait_mihomo_ports()


def reality_client(n: dict, env: dict) -> dict:
    """Client proxy for an install-time Reality node (same fields as core.sh proxy_line)."""
    d = {
        "name": n["name"], "type": "vless",
        "server": env.get("SERVER_IP", ""), "port": n["port"], "uuid": n["uuid"], "tls": True,
        "flow": "xtls-rprx-vision", "client-fingerprint": "safari",
    }
    if n.get("enc"):
        d["encryption"] = n["enc"]
    d.update({
        "reality-opts": {"public-key": n["pub"], "short-id": n["sid"]}, "network": "tcp",
        "udp": True, "servername": n["sni"],
    })
    return d


def sanitize_doh_url_line(line: str) -> str:
    """Strip invalid `#group-name&ecs=...` fragments from DoH URLs in DNS nameserver blocks."""
    return re.sub(r'(https?://[^\s"\'#]+/dns-query)#[^\s"\']*', r'\1', line)


def render_subscription(env: dict, live: bool = True) -> str:
    """Full mihomo client config: install Reality nodes + panel/custom inbounds, via client.yaml.tpl.

    live=True (subscription link) uses the running state, not unsaved drafts."""
    nodes, inbs = live_nodes_and_inbounds() if live else (read_nodes(), load_inbounds())
    raw_proxies = [reality_client(n, env) for n in nodes] + [i["client"] for i in inbs]
    proxies = [{k: v for k, v in p.items() if k != "skip-cert-verify"} for p in raw_proxies]
    p_lines = "\n".join("  - " + json.dumps(p, ensure_ascii=False) for p in proxies) if proxies else "  []"
    n_lines = "\n".join("      - " + json.dumps(p["name"], ensure_ascii=False) for p in proxies) if proxies else '      - "DIRECT"'
    out = []
    tpl_path = resolve_template_path("resources/client.yaml.tpl")
    with open(tpl_path) as f:
        for line in f:
            key = line.rstrip("\n")
            if key == "@@PROXIES@@":
                out.append(p_lines + "\n")
            elif key == "@@PROXY_NAMES@@":
                out.append(n_lines + "\n")
            else:
                out.append(sanitize_doh_url_line(line))
    return "".join(out)


def mihomo_status() -> dict:
    rc, active = run([SYSTEMCTL, "is-active", "mihomo"])
    active = (active or "").strip().splitlines()[-1] if active else ""
    if rc == 127 or active not in STATE_ZH:
        active = "unknown"
    _, show = run([SYSTEMCTL, "show", "mihomo", "-p", "ActiveEnterTimestamp,MainPID,NRestarts"])
    props = dict(l.split("=", 1) for l in show.splitlines() if "=" in l)
    _, ver = run([resolve_mihomo_bin(), "-v"])
    _, ss = run(["ss", "-Hltun"])
    listening = {int(m) for m in re.findall(r":(\d+)\s", ss + " ")}
    cert = {}
    if certs_present():
        crt_file = (ROOT + CERT) if os.path.isfile(ROOT + CERT) else CERT
        _, c = run(["openssl", "x509", "-noout", "-enddate", "-issuer", "-in", crt_file])
        cert = {"info": c}
    return {"active": active, "since": props.get("ActiveEnterTimestamp", ""),
            "pid": props.get("MainPID", ""), "restarts": props.get("NRestarts", ""),
            "version": ver.splitlines()[0] if ver else "", "listening": sorted(listening),
            "cert": cert}

