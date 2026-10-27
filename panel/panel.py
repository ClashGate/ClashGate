#!/usr/bin/env python3
"""ClashGate v0.95 - rebuilt admin console for ClashGate (Vue 3 + Tailwind CSS, light green SaaS theme).

Stdlib only (Python 3). Serves HTTPS itself with the same certificate
Mihomo uses (/etc/clashgate/certs); no reverse proxy.
Unified directory layout under /etc/clashgate.

Subcommands:
  panel.py hash-password            read password on stdin, print hash
  panel.py serve --config FILE      run the HTTP server
"""
import argparse
import base64
import calendar
import gzip
import hashlib
import hmac
import html
import json
import os
import random
import re
import secrets
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid as uuidlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse, quote

VERSION = "0.95"

# CLASHGATE_ROOT lets the panel run against a fake tree for local testing.
ROOT = os.environ.get("CLASHGATE_ROOT", "")
CS_ROOT = ROOT + "/etc/clashgate"
ENV_FILE = CS_ROOT + "/clashgate.env"
INBOUNDS = CS_ROOT + "/inbounds.json"
PROXIES_JSON = CS_ROOT + "/proxies.json"
PROVIDERS_JSON = CS_ROOT + "/providers.json"
TRAFFIC_JSON = CS_ROOT + "/traffic.json"
MIHOMO_DIR = CS_ROOT
CONF = MIHOMO_DIR + "/config.yaml"
CUSTOM_CONF = MIHOMO_DIR + "/custom_config.yaml"
NODES_TSV = MIHOMO_DIR + "/nodes.tsv"
FRAG_CONTROLLER = MIHOMO_DIR + "/controller.yaml"
FRAG_REALITY = MIHOMO_DIR + "/listeners.reality.yaml"
FRAG_EXTRA = MIHOMO_DIR + "/listeners.extra.yaml"
FRAG_PROXIES = MIHOMO_DIR + "/proxies.extra.yaml"
FRAG_PROVIDERS = MIHOMO_DIR + "/providers.extra.yaml"
TEMPLATE = CS_ROOT + "/resources/server.yaml.tpl"
CLIENT_TEMPLATE = CS_ROOT + "/resources/client.yaml.tpl"
CLIENT_DIR = CS_ROOT + "/client"
CERTCTL = CS_ROOT + "/scripts/certctl.sh"
CERT = "/etc/clashgate/certs/fullchain.pem"   # paths as seen by mihomo (not ROOT-prefixed)
KEY = "/etc/clashgate/certs/privkey.pem"
CERT_REL = "certs/fullchain.pem"
KEY_REL = "certs/privkey.pem"
MIHOMO_BIN = os.environ.get("MIHOMO_BIN", CS_ROOT + "/mihomo" if os.path.isfile(CS_ROOT + "/mihomo") else "/usr/local/bin/mihomo")
MIHOMO_REPO_API = os.environ.get("MIHOMO_REPO_API", "https://api.github.com/repos/MetaCubeX/mihomo/releases/latest")
REPO_OWNER = os.environ.get("REPO_OWNER", "ClashGate")
REPO_NAME = os.environ.get("REPO_NAME", "ClashGate")
REPO_SLUG = os.environ.get("REPO_SLUG", f"{REPO_OWNER}/{REPO_NAME}")
CLASHGATE_RAW_COMMON = os.environ.get(
    "CLASHGATE_RAW_COMMON",
    f"https://raw.githubusercontent.com/{REPO_SLUG}/main/scripts/lib/common.sh",
)
CLASHGATE_BIN = os.environ.get(
    "CLASHGATE_BIN",
    CS_ROOT + "/scripts/cmd/clashgate.sh"
    if os.path.isfile(CS_ROOT + "/scripts/cmd/clashgate.sh")
    else "/usr/local/bin/clashgate",
)
SYSTEMCTL = os.environ.get("SYSTEMCTL", "systemctl")
UFW_BIN = os.environ.get("UFW_BIN", "ufw")
FIREWALL_CMD_BIN = os.environ.get("FIREWALL_CMD_BIN", "firewall-cmd")
REALITY_SNI_POOL = (
    "www.microsoft.com",
    "www.apple.com",
    "addons.mozilla.org",
    "www.yahoo.com",
    "www.amd.com",
    "www.nvidia.com",
    "www.samsung.com",
    "www.cisco.com",
    "www.oracle.com",
    "www.lovelive-anime.jp",
)
PBKDF2_ITER = 600_000
SESSION_TTL = 12 * 3600


def pick_reality_sni() -> str:
    return random.choice(REALITY_SNI_POOL)

TYPES = (
    "vless-reality", "shadowsocks", "hysteria2", "snell",
    "anytls", "tuic", "trusttunnel", "shadowquic", "mieru", "sudoku", "http", "socks",
)
DEFAULT_NODE_NAMES = {
    "vless-reality": "VlessReality",
    "shadowsocks": "Shadowsocks",
    "hysteria2": "Hysteria2",
    "snell": "SnellV5",
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
    "snell": "轻量高效的私有协议，内置随机 TLS 伪装",
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
SS_CIPHERS = ("aes-256-gcm", "aes-128-gcm")
SS_CIPHER_LABELS = {
    "aes-256-gcm": "aes-256-gcm（默认）",
    "aes-128-gcm": "aes-128-gcm",
}
STR_KEYS = {
    "name", "type", "server", "uuid", "password", "psk", "public-key", "private-key",
    "short-id", "servername", "sni", "cipher", "flow", "client-fingerprint",
    "username", "network", "path", "host", "mode", "plugin", "obfs", "fingerprint",
    "network-name", "network-secret", "state-dir", "control-url", "auth-key", "hostname",
    "key", "aead-method", "table-type", "congestion-controller", "udp-relay-mode",
    "decryption", "encryption", "ws-path", "grpc-service-name", "transport",
}


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


def ensure_unified_root():
    """Ensure /etc/clashgate and client directory exist."""
    os.makedirs(CS_ROOT, mode=0o775, exist_ok=True)
    os.makedirs(CLIENT_DIR, mode=0o700, exist_ok=True)


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


def load_inbounds() -> list:
    try:
        with open(INBOUNDS) as f:
            items = json.load(f)
        out = []
        seen_names = set()
        for item in items:
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


def read_nodes() -> list:
    rows = []
    try:
        with open(NODES_TSV) as f:
            for line in f:
                p = line.rstrip("\n").split("\t")
                if len(p) >= 7:
                    rows.append({
                        "name": p[0], "port": int(p[1]), "uuid": p[2],
                        "priv": p[3], "pub": p[4], "sid": p[5], "sni": p[6],
                        "dec": p[7] if len(p) >= 8 else "",
                        "enc": p[8] if len(p) >= 9 else "",
                    })
    except FileNotFoundError:
        pass
    return rows


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


def server_config_url(env: dict, cfg: dict) -> str:
    base = panel_base_url(env, cfg)
    return f"{base}/config/server.yaml" if base else "/config/server.yaml"


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


def zashboard_connect_url(env: dict) -> str:
    return zashboard_url(env)


def write_env_var(key: str, val: str):
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


# ---------------------------------------------------------------- YAML / JSON proxy parser & serializer
def strip_yaml_comment(s: str) -> str:
    in_sq = in_dq = escaped = False
    for i, ch in enumerate(s):
        if escaped:
            escaped = False
            continue
        if ch == "\\" and in_dq:
            escaped = True
            continue
        if ch == "'" and not in_dq:
            in_sq = not in_sq
        elif ch == '"' and not in_sq:
            in_dq = not in_dq
        elif ch == "#" and not in_sq and not in_dq:
            if i == 0 or s[i - 1].isspace():
                return s[:i].rstrip()
    return s.rstrip()


def split_kv(line: str):
    in_sq = in_dq = escaped = False
    for i, ch in enumerate(line):
        if escaped:
            escaped = False
            continue
        if ch == "\\" and in_dq:
            escaped = True
            continue
        if ch == "'" and not in_dq:
            in_sq = not in_sq
        elif ch == '"' and not in_sq:
            in_dq = not in_dq
        elif ch == ":" and not in_sq and not in_dq:
            if i + 1 == len(line) or line[i + 1].isspace() or line[i + 1] in ('"', "'", "[", "{"):
                k = line[:i].strip()
                if (k.startswith('"') and k.endswith('"')) or (k.startswith("'") and k.endswith("'")):
                    k = k[1:-1]
                return k, ":", line[i + 1:].strip()
    return line, "", ""


def parse_scalar(val: str, key: str = ""):
    val = val.strip()
    if not val:
        return ""
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        if val.startswith('"'):
            try:
                return json.loads(val)
            except Exception:
                return val[1:-1]
        return val[1:-1].replace("''", "'")
    low = val.lower()
    if key not in STR_KEYS:
        if low == "true":
            return True
        if low == "false":
            return False
        if low in ("null", "~"):
            return None
        if re.fullmatch(r"-?(?:0|[1-9]\d*)", val):
            return int(val)
        if re.fullmatch(r"-?\d+\.\d+", val):
            return float(val)
    return val


def split_flow(s: str, sep: str = ",") -> list:
    parts, buf = [], []
    depth_c = depth_b = 0
    in_sq = in_dq = escaped = False
    for ch in s:
        if escaped:
            buf.append(ch)
            escaped = False
            continue
        if ch == "\\" and in_dq:
            buf.append(ch)
            escaped = True
            continue
        if ch == "'" and not in_dq:
            in_sq = not in_sq
        elif ch == '"' and not in_sq:
            in_dq = not in_dq
        elif not in_sq and not in_dq:
            if ch == "{":
                depth_c += 1
            elif ch == "}":
                depth_c -= 1
            elif ch == "[":
                depth_b += 1
            elif ch == "]":
                depth_b -= 1
            elif ch == sep and depth_c == 0 and depth_b == 0:
                parts.append("".join(buf).strip())
                buf = []
                continue
        buf.append(ch)
    if buf or s.endswith(sep):
        parts.append("".join(buf).strip())
    return [p for p in parts if p != ""]


def parse_flow_val(val: str, key: str = ""):
    val = val.strip()
    if val.startswith("{") and val.endswith("}"):
        try:
            obj = json.loads(val)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
        inner = val[1:-1].strip()
        if not inner:
            return {}
        out = {}
        for item in split_flow(inner, ","):
            if not item:
                continue
            k, sep, v = split_kv(item)
            if not sep:
                raise ValueError(f"无法解析字段：{item}")
            out[k] = parse_flow_val(v, k)
        return out
    if val.startswith("[") and val.endswith("]"):
        try:
            arr = json.loads(val)
            if isinstance(arr, list):
                return arr
        except Exception:
            pass
        inner = val[1:-1].strip()
        if not inner:
            return []
        return [parse_flow_val(x, key) for x in split_flow(inner, ",") if x != ""]
    return parse_scalar(val, key)


def parse_yaml_lines(lines: list, idx: int = 0, min_indent: int = 0):
    if idx >= len(lines):
        return None, idx
    ind0, txt0 = lines[idx]
    if ind0 < min_indent:
        return None, idx
    if txt0 == "-" or txt0.startswith("- "):
        arr = []
        seq_indent = ind0
        while idx < len(lines):
            ind, txt = lines[idx]
            if ind < seq_indent or not (txt == "-" or txt.startswith("- ")):
                break
            if ind != seq_indent:
                raise ValueError(f"YAML 列表缩进不一致：{txt}")
            rest = txt[1:].strip()
            idx += 1
            if not rest:
                sub, idx = parse_yaml_lines(lines, idx, seq_indent + 1)
                arr.append(sub)
            elif rest.startswith("{") and rest.endswith("}"):
                arr.append(parse_flow_val(rest))
            else:
                k, sep, v = split_kv(rest)
                if sep:
                    item_indent = ind + 2
                    virtual = [(item_indent, rest)]
                    while idx < len(lines) and lines[idx][0] >= item_indent:
                        virtual.append(lines[idx])
                        idx += 1
                    sub, _ = parse_yaml_lines(virtual, 0, item_indent)
                    arr.append(sub)
                else:
                    arr.append(parse_flow_val(rest))
        return arr, idx
    else:
        mapping = {}
        map_indent = ind0
        while idx < len(lines):
            ind, txt = lines[idx]
            if ind < map_indent:
                break
            if txt == "-" or txt.startswith("- "):
                break
            if ind != map_indent:
                raise ValueError(f"YAML 映射缩进不一致：{txt}")
            k, sep, v = split_kv(txt)
            if not sep:
                raise ValueError(f"无效的 YAML 行：{txt}")
            idx += 1
            if v in ("|", "|-", "|+", ">", ">-", ">+"):
                blk = []
                blk_indent = None
                while idx < len(lines) and lines[idx][0] > map_indent:
                    b_ind, b_txt = lines[idx]
                    if blk_indent is None:
                        blk_indent = b_ind
                    pad = " " * max(0, b_ind - blk_indent)
                    blk.append(pad + b_txt)
                    idx += 1
                mapping[k] = "\n".join(blk)
            elif v:
                mapping[k] = parse_flow_val(v, k)
            else:
                if idx < len(lines) and lines[idx][0] >= map_indent:
                    nxt_ind, nxt_txt = lines[idx]
                    if nxt_ind > map_indent or (nxt_ind == map_indent and (nxt_txt == "-" or nxt_txt.startswith("- "))):
                        sub, idx = parse_yaml_lines(lines, idx, map_indent)
                        mapping[k] = sub
                    else:
                        mapping[k] = ""
                else:
                    mapping[k] = ""
        return mapping, idx


def parse_mihomo_proxies(raw: str) -> list:
    """Parse single-line JSON/flow or multi-line YAML mihomo node configs; supports easytier/tailscale/etc."""
    s = (raw or "").strip()
    if not s:
        raise ValueError("请输入 mihomo 节点配置（单行 JSON 或多行 YAML）")
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", s):
        raise ValueError("不支持分享链接（如 vless://、ss://），请粘贴 mihomo 配置格式（JSON 或 YAML；若是订阅链接请在上方「导入外部订阅」中添加）")
    parsed = None
    if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
        try:
            parsed = json.loads(s)
        except Exception:
            if "\n" not in s or (s.startswith("[") and s.endswith("]")):
                try:
                    parsed = parse_flow_val(s)
                except Exception:
                    parsed = None
    if parsed is None:
        lines = []
        for raw_line in s.splitlines():
            cleaned = strip_yaml_comment(raw_line.expandtabs(2))
            if not cleaned.strip():
                continue
            ind = len(cleaned) - len(cleaned.lstrip(" "))
            lines.append((ind, cleaned.strip()))
        if not lines:
            raise ValueError("节点配置为空")
        flow_candidates = []
        all_flow = True
        for _, txt in lines:
            t = txt[1:].strip() if (txt == "-" or txt.startswith("- ")) else txt
            if t.endswith(","):
                t = t[:-1].strip()
            if t.startswith("{") and t.endswith("}"):
                flow_candidates.append(t)
            else:
                all_flow = False
                break
        if all_flow and flow_candidates:
            parsed = [parse_flow_val(t) for t in flow_candidates]
        else:
            parsed, end_idx = parse_yaml_lines(lines, 0, 0)
            if end_idx < len(lines):
                raise ValueError(f"无法解析第 {end_idx + 1} 行附近的配置：{lines[end_idx][1]}")
    if isinstance(parsed, dict) and "proxies" in parsed and isinstance(parsed["proxies"], list):
        items = parsed["proxies"]
    elif isinstance(parsed, dict):
        items = [parsed]
    elif isinstance(parsed, list):
        items = parsed
    else:
        raise ValueError("仅支持 mihomo 节点配置格式（单行 JSON 或多行 YAML）")
    if not items:
        raise ValueError("未找到任何节点配置")
    out = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("每个节点必须是键值对对象（需包含 name 与 type）")
        node = dict(item)
        for req in ("name", "type"):
            if req not in node or node[req] in ("", None):
                raise ValueError(f"节点缺少必填字段：{req}")
        node["name"] = str(node["name"]).strip()
        node["type"] = str(node["type"]).strip()
        if "server" in node and node["server"] not in ("", None):
            node["server"] = str(node["server"]).strip()
        if "port" in node and node["port"] not in ("", None):
            try:
                port = int(node["port"])
                if not 1 <= port <= 65535:
                    raise ValueError()
                node["port"] = port
            except Exception:
                nm, pt = node["name"], node["port"]
                raise ValueError(f"节点「{nm}」端口无效：{pt}")
        for k in list(node.keys()):
            if k in STR_KEYS and node[k] is not None and not isinstance(node[k], (dict, list)):
                node[k] = str(node[k])
        if "udp" not in node or node["udp"] is None:
            node["udp"] = True
        out.append(node)
    return out


def yaml_scalar(v, key: str = "") -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return "null"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if s == "":
        return '""'
    if (key in STR_KEYS and re.fullmatch(r"0\d+|-?\d+(\.\d+)?", s)) or s.lower() in (
        "true", "false", "null", "yes", "no", "on", "off", "~"
    ):
        return json.dumps(s, ensure_ascii=False)
    if re.fullmatch(r"[A-Za-z0-9._/+@-]+", s) and not s.startswith("-"):
        return s
    return json.dumps(s, ensure_ascii=False)


def dump_yaml_map(d: dict, indent: int = 4, first_dash: bool = False) -> list:
    priority = ("name", "type", "server", "port")
    keys = [k for k in priority if k in d] + [k for k in d if k not in priority]
    lines = []
    for idx, k in enumerate(keys):
        v = d[k]
        prefix = (" " * (indent - 2) + "- ") if (idx == 0 and first_dash) else (" " * indent)
        ks = k if re.fullmatch(r"[A-Za-z0-9._-]+", str(k)) else json.dumps(str(k), ensure_ascii=False)
        if isinstance(v, dict):
            if not v:
                lines.append(f"{prefix}{ks}: {{}}")
            else:
                lines.append(f"{prefix}{ks}:")
                lines.extend(dump_yaml_map(v, indent + 2, False))
        elif isinstance(v, list):
            if not v:
                lines.append(f"{prefix}{ks}: []")
            else:
                lines.append(f"{prefix}{ks}:")
                for elem in v:
                    if isinstance(elem, dict):
                        lines.extend(dump_yaml_map(elem, indent + 4, True))
                    else:
                        lines.append(" " * (indent + 2) + "- " + yaml_scalar(elem, k))
        else:
            lines.append(f"{prefix}{ks}: {yaml_scalar(v, k)}")
    return lines


def dump_yaml_proxies(proxies: list) -> str:
    """Render a list of proxy dicts as multi-line YAML items (2-space indented `- `)."""
    lines = []
    for p in proxies:
        lines.extend(dump_yaml_map(p, indent=4, first_dash=True))
    return "\n".join(lines) + ("\n" if lines else "")


def dump_yaml_providers(providers: dict) -> str:
    """Render proxy-providers dict as 2-space indented YAML mapping entries."""
    lines = []
    for name, cfg in providers.items():
        ks = name if re.fullmatch(r"[A-Za-z0-9._-]+", str(name)) else json.dumps(str(name), ensure_ascii=False)
        lines.append(f"  {ks}:")
        lines.extend(dump_yaml_map(cfg, indent=4, first_dash=False))
    return "\n".join(lines) + ("\n" if lines else "")


def build_proxy_provider(url: str, name: str = "", existing: dict = None) -> tuple:
    """Build a proxy-provider entry matching the 0.5 requirement structure."""
    u = (url or "").strip()
    if not re.match(r"^https?://\S+$", u):
        raise ValueError("请输入有效的 HTTP/HTTPS 订阅链接")
    raw_name = (name or "").strip()
    if not raw_name or raw_name.lower() == "default":
        # Note: Mihomo kernel forbids naming a proxy-provider literally 'default'
        # ("can not defined a provider called `default`"), while path ./default.yaml is valid.
        prov_name = "default-sub" if (existing and "sub" in existing and "default-sub" not in existing) else "sub"
        if raw_name.lower() == "default":
            prov_name = "default-sub"
        path = "./default.yaml" if not existing else f"./{prov_name}.yaml"
    else:
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,48}", raw_name):
            raise ValueError("订阅源名称仅限 1-48 位字母、数字及 . _ -")
        prov_name = raw_name
        path = f"./{prov_name}.yaml"
    entry = {
        "type": "http",
        "url": u,
        "path": path,
        "interval": 3600,
        "proxy": "DIRECT",
        "health-check": {
            "enable": True,
            "url": "https://www.gstatic.com/generate_204",
            "interval": 300,
            "timeout": 5000,
            "lazy": True,
        },
    }
    return prov_name, entry


# ---------------------------------------------------------------- custom server config helpers
def rewrite_cert_paths_in_yaml(raw_yaml: str, env: dict = None) -> tuple:
    """Automatically rewrite TLS certificate/private-key paths in user server config to /etc/clashgate/certs/*.
    Never modifies private-key inside reality-config blocks."""
    lines = raw_yaml.splitlines()
    out = []
    in_reality = False
    reality_indent = 0
    in_providers = False
    providers_indent = 0
    changed = 0

    for line in lines:
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        if stripped and not stripped.startswith("#"):
            if in_reality and indent <= reality_indent:
                in_reality = False
            if in_providers and indent <= providers_indent:
                in_providers = False
            if re.match(r"^reality-config\s*:", stripped):
                in_reality = True
                reality_indent = indent
                out.append(line)
                continue
            if re.match(r"^proxy-providers\s*:", stripped):
                in_providers = True
                providers_indent = indent
                out.append(line)
                continue
            # Rename reserved provider key `default:` under `proxy-providers:` so mihomo -t passes
            if in_providers and indent == providers_indent + 2 and re.match(r"^default\s*:\s*(#.*)?$", stripped):
                line = (" " * indent) + re.sub(r"^default(\s*:)", r"default-sub\1", stripped, count=1)
                changed += 1
                out.append(line)
                continue
            # Rewrite certificate:
            m_cert = re.match(r"^((?:-\s+)?certificate\s*:\s*)([^#\n]+?)(\s*(?:#.*)?)$", stripped)
            if m_cert:
                cur_val = m_cert.group(2).strip().strip("'\"")
                if cur_val != CERT:
                    changed += 1
                line = (" " * indent) + f"{m_cert.group(1)}{CERT}{m_cert.group(3)}"
                out.append(line)
                continue
            # Rewrite private-key: (ONLY when not inside reality-config)
            if not in_reality:
                m_key = re.match(r"^((?:-\s+)?private-key\s*:\s*)([^#\n]+?)(\s*(?:#.*)?)$", stripped)
                if m_key:
                    cur_val = m_key.group(2).strip().strip("'\"")
                    if "/" in cur_val or "." in cur_val or "key" in cur_val.lower() or "pem" in cur_val.lower():
                        if cur_val != KEY:
                            changed += 1
                        line = (" " * indent) + f"{m_key.group(1)}{KEY}{m_key.group(3)}"
                        out.append(line)
                        continue
        out.append(line)
    res = "\n".join(out) + ("\n" if raw_yaml.endswith("\n") else "")
    return res, changed


def sync_env_from_custom_config(raw_yaml: str):
    """Sync CONTROLLER_PORT and MIHOMO_SECRET from a custom server config if present."""
    for pat in (
        r'^\s*external-controller-tls\s*:\s*["\']?[^"\':\s]+:(\d+)["\']?',
        r'^\s*external-controller\s*:\s*["\']?[^"\':\s]+:(\d+)["\']?',
    ):
        m_port = re.search(pat, raw_yaml, re.M)
        if m_port:
            p = int(m_port.group(1))
            if 1 <= p <= 65535:
                write_env_var("CONTROLLER_PORT", str(p))
                break
    sec = extract_yaml_secret(raw_yaml)
    if sec:
        write_env_var("MIHOMO_SECRET", sec)


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
        ver = int(lst.get("version") or 5)
        obfs = lst.get("obfs-opts") if isinstance(lst.get("obfs-opts"), dict) else {"mode": "tls", "host": pick_reality_sni()}
        client = {
            "name": label, "type": "snell", "server": ip, "port": port,
            "psk": str(lst.get("psk", "")), "version": ver, "udp": True, "obfs-opts": obfs,
        }
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
    if isinstance(raw_listeners, list):
        for item in raw_listeners:
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
        sni = pick_reality_sni()
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
        version = 5
        obfs_mode = "tls"
        obfs_host = pick_reality_sni()
        psk = base64.b64encode(secrets.token_bytes(16)).decode()
        listener = {**base, "type": "snell", "psk": psk, "version": version, "udp": True,
                    "obfs-opts": {"mode": obfs_mode, "host": obfs_host}}
        client = {"name": label, "type": "snell", "server": ip, "port": port,
                  "psk": psk, "version": version, "udp": True,
                  "obfs-opts": {"mode": obfs_mode, "host": obfs_host}}

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
        jls_host = pick_reality_sni()
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
        psk = base64.b64encode(secrets.token_bytes(16)).decode()
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
    proxies_lines = [l for l in proxies_frag.splitlines() if l.strip()]
    proxies_block = ("proxies:\n" + "\n".join(proxies_lines) + "\n") if proxies_lines else "proxies: []\n"

    block = ""
    for frag in (FRAG_REALITY, FRAG_EXTRA):
        try:
            with open(frag) as f:
                block += f.read()
        except FileNotFoundError:
            pass
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
            elif s == "@@LISTENERS@@":
                out.append(block)
            else:
                out.append(line)
    return "".join(out)


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


def validate_config(path=CONF):
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
        rc, out = run([resolve_mihomo_bin(), "-t", "-d", d, "-f", test_path], env=env, timeout=90)
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
        atomic_write(CLIENT_DIR + "/mihomo-client.yaml", render_subscription(env), 0o600)
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
        l_body = render_reality(nodes) + dump_yaml_proxies([i["listener"] for i in inbounds])
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
        p_body = dump_yaml_proxies(proxies)
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


_PENDING_UFW_BASELINE = None
_RECENT_ADD_REQS = {}


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
    global _PENDING_UFW_BASELINE
    cur_nodes = read_nodes()
    if _PENDING_UFW_BASELINE is None:
        _PENDING_UFW_BASELINE = collect_ufw_specs(cur_nodes, load_inbounds())
    cleaned = _dedup_inbounds(new)
    atomic_write(INBOUNDS, json.dumps(cleaned, indent=2, ensure_ascii=False), 0o600)
    atomic_write(FRAG_EXTRA, render_extra(cleaned), 0o640)
    _sync_custom_conf_listeners(cur_nodes, cleaned)
    atomic_write(CONF, assemble_config(), 0o640)
    sync_client_files()


def save_nodes(new_nodes: list):
    """Persist install-time VLESS Reality nodes (nodes.tsv) and config fragments to disk without reloading Mihomo."""
    global _PENDING_UFW_BASELINE
    cur_inbs = load_inbounds()
    if _PENDING_UFW_BASELINE is None:
        _PENDING_UFW_BASELINE = collect_ufw_specs(read_nodes(), cur_inbs)
    atomic_write(NODES_TSV, render_nodes_tsv(new_nodes), 0o640)
    atomic_write(FRAG_REALITY, render_reality(new_nodes), 0o640)
    _sync_custom_conf_listeners(new_nodes, cur_inbs)
    atomic_write(CONF, assemble_config(), 0o640)
    sync_client_files()


def apply_inbounds(new: list):
    """Write inbounds + fragment + config, validate, restart; roll back on failure."""
    cur_nodes = read_nodes()
    old_specs = collect_ufw_specs(cur_nodes, load_inbounds())
    cleaned = _dedup_inbounds(new)
    files = (INBOUNDS, FRAG_EXTRA, CUSTOM_CONF, CONF) if is_custom_config_mode() else (INBOUNDS, FRAG_EXTRA, CONF)
    backup = {}
    for p in files:
        try:
            with open(p) as f:
                backup[p] = f.read()
        except FileNotFoundError:
            backup[p] = None
    try:
        atomic_write(INBOUNDS, json.dumps(cleaned, indent=2, ensure_ascii=False), 0o600)
        atomic_write(FRAG_EXTRA, render_extra(cleaned))
        _sync_custom_conf_listeners(cur_nodes, cleaned)
        atomic_write(CONF, assemble_config())
        rc, out = validate_config()
        if rc != 0:
            raise RuntimeError("配置校验失败（mihomo -t）：" + out[-800:])
        rc, out = run([SYSTEMCTL, "restart", "mihomo"])
        if rc != 0:
            raise RuntimeError("重启失败：" + out[-800:])
    except Exception:
        for p, data in backup.items():
            if data is None:
                if os.path.exists(p):
                    os.remove(p)
            else:
                atomic_write(p, data, 0o600 if p == INBOUNDS else 0o640)
        run([SYSTEMCTL, "restart", "mihomo"])
        raise
    sync_client_files()
    sync_ufw(old_specs, collect_ufw_specs(cur_nodes, cleaned))
    wait_mihomo_ports()


def apply_nodes(new_nodes: list):
    """Update install-time VLESS Reality nodes (nodes.tsv + listeners.reality.yaml + config.yaml), validate, restart."""
    cur_inbs = load_inbounds()
    old_specs = collect_ufw_specs(read_nodes(), cur_inbs)
    files = (NODES_TSV, FRAG_REALITY, CUSTOM_CONF, CONF) if is_custom_config_mode() else (NODES_TSV, FRAG_REALITY, CONF)
    backup = {}
    for p in files:
        try:
            with open(p) as f:
                backup[p] = f.read()
        except FileNotFoundError:
            backup[p] = None
    try:
        atomic_write(NODES_TSV, render_nodes_tsv(new_nodes), 0o640)
        atomic_write(FRAG_REALITY, render_reality(new_nodes), 0o640)
        _sync_custom_conf_listeners(new_nodes, cur_inbs)
        atomic_write(CONF, assemble_config(), 0o640)
        rc, out = validate_config()
        if rc != 0:
            raise RuntimeError("配置校验失败（mihomo -t）：" + out[-800:])
        rc, out = run([SYSTEMCTL, "restart", "mihomo"])
        if rc != 0:
            raise RuntimeError("重启失败：" + out[-800:])
    except Exception:
        for p, data in backup.items():
            if data is None:
                if os.path.exists(p):
                    os.remove(p)
            else:
                atomic_write(p, data, 0o640)
        run([SYSTEMCTL, "restart", "mihomo"])
        raise
    sync_client_files()
    sync_ufw(old_specs, collect_ufw_specs(new_nodes, cur_inbs))
    wait_mihomo_ports()


def save_server_proxies(new_proxies: list):
    """Persist server outbound proxies to disk ONLY (proxies.json + proxies.extra.yaml + config.yaml) without reloading Mihomo."""
    files = (PROXIES_JSON, FRAG_PROXIES, CUSTOM_CONF, CONF) if is_custom_config_mode() else (PROXIES_JSON, FRAG_PROXIES, CONF)
    backup = {}
    for p in files:
        try:
            with open(p) as f:
                backup[p] = f.read()
        except FileNotFoundError:
            backup[p] = None
    try:
        atomic_write(PROXIES_JSON, json.dumps(new_proxies, indent=2, ensure_ascii=False), 0o600)
        atomic_write(FRAG_PROXIES, dump_yaml_proxies(new_proxies), 0o640)
        _sync_custom_conf_proxies(new_proxies)
        atomic_write(CONF, assemble_config(), 0o640)
    except Exception:
        for p, data in backup.items():
            if data is None:
                if os.path.exists(p):
                    os.remove(p)
            else:
                atomic_write(p, data, 0o600 if p == PROXIES_JSON else 0o640)
        raise


def apply_server_proxies(new_proxies: list):
    """Write server outbound proxies (proxies.json + proxies.extra.yaml + config.yaml), validate, restart."""
    files = (PROXIES_JSON, FRAG_PROXIES, CUSTOM_CONF, CONF) if is_custom_config_mode() else (PROXIES_JSON, FRAG_PROXIES, CONF)
    backup = {}
    for p in files:
        try:
            with open(p) as f:
                backup[p] = f.read()
        except FileNotFoundError:
            backup[p] = None
    try:
        atomic_write(PROXIES_JSON, json.dumps(new_proxies, indent=2, ensure_ascii=False), 0o600)
        atomic_write(FRAG_PROXIES, dump_yaml_proxies(new_proxies), 0o640)
        _sync_custom_conf_proxies(new_proxies)
        atomic_write(CONF, assemble_config(), 0o640)
        rc, out = validate_config()
        if rc != 0:
            raise RuntimeError("配置校验失败（mihomo -t）：" + out[-800:])
        rc, out = run([SYSTEMCTL, "restart", "mihomo"])
        if rc != 0:
            raise RuntimeError("重启失败：" + out[-800:])
    except Exception:
        for p, data in backup.items():
            if data is None:
                if os.path.exists(p):
                    os.remove(p)
            else:
                atomic_write(p, data, 0o600 if p == PROXIES_JSON else 0o640)
        run([SYSTEMCTL, "restart", "mihomo"])
        raise
    wait_mihomo_ports()


def save_proxy_providers(new_providers: dict):
    """Persist server proxy-providers to disk ONLY (providers.json + providers.extra.yaml + config.yaml) without reloading Mihomo."""
    files = (PROVIDERS_JSON, FRAG_PROVIDERS, CUSTOM_CONF, CONF) if is_custom_config_mode() else (PROVIDERS_JSON, FRAG_PROVIDERS, CONF)
    backup = {}
    for p in files:
        try:
            with open(p) as f:
                backup[p] = f.read()
        except FileNotFoundError:
            backup[p] = None
    try:
        atomic_write(PROVIDERS_JSON, json.dumps(new_providers, indent=2, ensure_ascii=False), 0o600)
        atomic_write(FRAG_PROVIDERS, dump_yaml_providers(new_providers), 0o640)
        _sync_custom_conf_providers(new_providers)
        atomic_write(CONF, assemble_config(), 0o640)
    except Exception:
        for p, data in backup.items():
            if data is None:
                if os.path.exists(p):
                    os.remove(p)
            else:
                atomic_write(p, data, 0o600 if p == PROVIDERS_JSON else 0o640)
        raise


def apply_proxy_providers(new_providers: dict):
    """Write server proxy-providers (providers.json + providers.extra.yaml + config.yaml), validate, restart."""
    files = (PROVIDERS_JSON, FRAG_PROVIDERS, CUSTOM_CONF, CONF) if is_custom_config_mode() else (PROVIDERS_JSON, FRAG_PROVIDERS, CONF)
    backup = {}
    for p in files:
        try:
            with open(p) as f:
                backup[p] = f.read()
        except FileNotFoundError:
            backup[p] = None
    try:
        atomic_write(PROVIDERS_JSON, json.dumps(new_providers, indent=2, ensure_ascii=False), 0o600)
        atomic_write(FRAG_PROVIDERS, dump_yaml_providers(new_providers), 0o640)
        _sync_custom_conf_providers(new_providers)
        atomic_write(CONF, assemble_config(), 0o640)
        rc, out = validate_config()
        if rc != 0:
            raise RuntimeError("配置校验失败（mihomo -t）：" + out[-800:])
        rc, out = run([SYSTEMCTL, "restart", "mihomo"])
        if rc != 0:
            raise RuntimeError("重启失败：" + out[-800:])
    except Exception:
        for p, data in backup.items():
            if data is None:
                if os.path.exists(p):
                    os.remove(p)
            else:
                atomic_write(p, data, 0o600 if p == PROVIDERS_JSON else 0o640)
        run([SYSTEMCTL, "restart", "mihomo"])
        raise
    wait_mihomo_ports()


def apply_custom_config(raw_yaml: str):
    """Validate and apply user-supplied full server config, syncing listeners, outbounds, and client subscription."""
    s = (raw_yaml or "").strip()
    if not s:
        raise ValueError("请输入完整的 mihomo 服务端配置内容")
    s = sanitize_doh_url_line(s) + "\n"
    was_custom = is_custom_config_mode()
    old_specs = collect_ufw_specs(read_nodes(), load_inbounds())
    files = (CUSTOM_CONF, CONF, NODES_TSV, INBOUNDS, PROXIES_JSON, PROVIDERS_JSON)
    backup = {}
    for p in files:
        try:
            with open(p) as f:
                backup[p] = f.read()
        except FileNotFoundError:
            backup[p] = None
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
        for p, data in backup.items():
            if data is None:
                if os.path.exists(p):
                    os.remove(p)
            else:
                atomic_write(p, data, 0o600 if p.endswith(".json") else 0o640)
        run([SYSTEMCTL, "restart", "mihomo"])
        raise
    sync_client_files()
    sync_ufw(old_specs, collect_ufw_specs([], new_inbounds))
    wait_mihomo_ports()


def reset_to_template_config():
    """Restore server config to clean default template and generate a default VlessReality node."""
    env = read_env()
    old_specs = collect_ufw_specs(read_nodes(), load_inbounds())
    files = (CUSTOM_CONF, CONF, NODES_TSV, INBOUNDS, PROXIES_JSON, PROVIDERS_JSON,
             FRAG_REALITY, FRAG_EXTRA, FRAG_PROXIES, FRAG_PROVIDERS, FRAG_CONTROLLER)
    backup = {}
    for p in files:
        try:
            with open(p) as f:
                backup[p] = f.read()
        except FileNotFoundError:
            backup[p] = None
    try:
        reserved = {80, 443, int(env.get("PANEL_PORT", "0") or 0), get_controller_port(env)}
        port = 28443
        for _ in range(1000):
            cand = random.randint(20000, 39999)
            if cand not in reserved:
                port = cand
                break
        priv, pub = reality_keypair()
        dec, enc = vless_x25519_keypair()
        default_node = {
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
        for p, data in backup.items():
            if data is None:
                if os.path.exists(p):
                    os.remove(p)
            else:
                atomic_write(p, data, 0o600 if p.endswith(".json") else 0o640)
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


def render_subscription(env: dict) -> str:
    """Full mihomo client config: install Reality nodes + panel/custom inbounds, via client.yaml.tpl."""
    raw_proxies = [reality_client(n, env) for n in read_nodes()] + [i["client"] for i in load_inbounds()]
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
    return {"active": active.strip() or "unknown", "since": props.get("ActiveEnterTimestamp", ""),
            "pid": props.get("MainPID", ""), "restarts": props.get("NRestarts", ""),
            "version": ver.splitlines()[0] if ver else "", "listening": sorted(listening),
            "cert": cert}


# ---------------------------------------------------------------- Traffic stats & Update helpers
TRAFFIC_LOCK = threading.Lock()


def format_traffic_gb(total_bytes: int) -> str:
    gb = max(0, int(total_bytes)) / (1024 ** 3)
    return f"{gb:.2f} GB"


def format_traffic_detail(up_bytes: int, down_bytes: int) -> str:
    def _fmt(b: int) -> str:
        b = max(0, int(b))
        if b >= 1024 ** 3:
            return f"{b / (1024 ** 3):.2f} GB"
        if b >= 1024 ** 2:
            return f"{b / (1024 ** 2):.1f} MB"
        if b >= 1024:
            return f"{b / 1024:.0f} KB"
        return f"{b} B"
    return f"↑ {_fmt(up_bytes)} · ↓ {_fmt(down_bytes)}"


def _controller_uses_tls(env: dict = None) -> bool:
    for p in (CUSTOM_CONF if is_custom_config_mode() else CONF, FRAG_CONTROLLER):
        try:
            with open(p) as f:
                txt = f.read()
            if re.search(r"^\s*external-controller-tls\s*:", txt, re.M):
                return True
            if re.search(r"^\s*external-controller\s*:", txt, re.M):
                return False
        except Exception:
            pass
    return True


def fetch_mihomo_connections_totals(env: dict = None) -> tuple:
    """Query Mihomo controller /connections for (uploadTotal, downloadTotal) in bytes."""
    if env is None:
        env = read_env()
    cport = get_controller_port(env)
    secret = get_mihomo_secret(env)
    headers = {"Accept": "application/json"}
    if secret:
        headers["Authorization"] = f"Bearer {secret}"
    schemes = ("https", "http") if _controller_uses_tls(env) else ("http", "https")
    for scheme in schemes:
        url = f"{scheme}://127.0.0.1:{cport}/connections"
        req = urllib.request.Request(url, headers=headers)
        try:
            if scheme == "https":
                ctx = ssl._create_unverified_context()
                with urllib.request.urlopen(req, context=ctx, timeout=1.5) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="replace"))
            else:
                with urllib.request.urlopen(req, timeout=1.5) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="replace"))
            if isinstance(data, dict) and ("uploadTotal" in data or "downloadTotal" in data):
                up = max(0, int(data.get("uploadTotal") or 0))
                down = max(0, int(data.get("downloadTotal") or 0))
                return up, down
        except Exception:
            continue
    return None, None


def get_traffic_stats(env: dict = None) -> dict:
    """Compute cumulative proxied traffic across Mihomo restarts by snapshotting /connections totals to traffic.json."""
    with TRAFFIC_LOCK:
        saved = {"base_up": 0, "base_down": 0, "last_up": 0, "last_down": 0, "updated_at": 0}
        try:
            with open(TRAFFIC_JSON) as f:
                d = json.load(f)
                if isinstance(d, dict):
                    for k in saved:
                        if k in d:
                            saved[k] = max(0, int(d[k] or 0))
        except Exception:
            pass

        cur_up, cur_down = fetch_mihomo_connections_totals(env)
        if cur_up is not None and cur_down is not None:
            # If Mihomo restarted, current session counters reset below last recorded session counters
            if cur_up < saved["last_up"] or cur_down < saved["last_down"]:
                saved["base_up"] += saved["last_up"]
                saved["base_down"] += saved["last_down"]
            if (cur_up != saved["last_up"] or cur_down != saved["last_down"]
                    or int(time.time()) - saved["updated_at"] >= 10):
                saved["last_up"] = cur_up
                saved["last_down"] = cur_down
                saved["updated_at"] = int(time.time())
                try:
                    atomic_write(TRAFFIC_JSON, json.dumps(saved, indent=2) + "\n", 0o600)
                except Exception:
                    pass
        total_up = saved["base_up"] + saved["last_up"]
        total_down = saved["base_down"] + saved["last_down"]
        total_bytes = total_up + total_down
        return {
            "up_bytes": total_up,
            "down_bytes": total_down,
            "total_bytes": total_bytes,
            "total_gb": round(total_bytes / (1024 ** 3), 2),
            "display": format_traffic_gb(total_bytes),
            "detail": format_traffic_detail(total_up, total_down),
        }


def start_traffic_poller(interval: int = 30):
    def _loop():
        while True:
            try:
                get_traffic_stats()
            except Exception:
                pass
            time.sleep(interval)
    t = threading.Thread(target=_loop, name="traffic-poller", daemon=True)
    t.start()


def parse_version_tuple(v: str) -> tuple:
    s = (v or "").strip().lstrip("vV")
    nums = [int(x) for x in re.findall(r"\d+", s)]
    return tuple(nums) if nums else (0,)


def get_local_mihomo_version() -> str:
    try:
        _, out = run([resolve_mihomo_bin(), "-v"], timeout=5)
        first = (out.splitlines()[0] if out else "").strip()
        m = re.search(r"\b(v?\d+\.\d+(?:\.\d+)*(?:-[0-9A-Za-z._-]+)?)\b", first)
        if m:
            v = m.group(1)
            return v if v.startswith("v") else f"v{v}"
    except Exception:
        pass
    return ""


def get_mihomo_version_num(st: dict = None) -> str:
    """Return local Mihomo version without leading 'v' (e.g. '1.19.33'), or '' if unreadable."""
    try:
        first = (st.get("version", "") if isinstance(st, dict) else "").strip()
        if first:
            m = re.search(r"\b(v?\d+\.\d+(?:\.\d+)*(?:-[0-9A-Za-z._-]+)?)\b", first)
            if m:
                return m.group(1).lstrip("vV")
        v = get_local_mihomo_version()
        return v.lstrip("vV") if v else ""
    except Exception:
        return ""


def detect_cpu_arch() -> str:
    mach = os.uname().machine.lower()
    if mach in ("x86_64", "amd64"):
        return "amd64"
    if mach in ("aarch64", "arm64"):
        return "arm64"
    if mach.startswith("armv7"):
        return "armv7"
    raise RuntimeError(f"不支持的 CPU 架构：{mach}")


def _http_get_text(url: str, timeout: int = 20, headers: dict = None) -> str:
    hdrs = {"User-Agent": f"clashgate/{VERSION}"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"GitHub 接口请求失败（HTTP {e.code}）") from None
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as e:
        reason = getattr(e, "reason", e)
        raise RuntimeError(f"无法连接 GitHub，请检查服务器网络（{reason}）") from None


def _resolve_repo_slug(env: dict = None) -> str:
    """Resolve REPO_SLUG from env / scripts/lib/common.sh / defaults (ClashGate/ClashGate)."""
    if env is None:
        env = read_env()
    common_vars = {}
    for p in (
        CS_ROOT + "/scripts/lib/common.sh",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts/lib/common.sh"),
    ):
        if os.path.isfile(p):
            try:
                with open(p) as f:
                    for line in f:
                        m = re.match(r"^(REPO_OWNER|REPO_NAME)=\$\{\1:-([^}]+)\}", line.strip())
                        if m:
                            common_vars[m.group(1)] = m.group(2).strip()
                break
            except Exception:
                pass
    owner = os.environ.get("REPO_OWNER") or env.get("REPO_OWNER") or common_vars.get("REPO_OWNER") or REPO_OWNER
    name = os.environ.get("REPO_NAME") or env.get("REPO_NAME") or common_vars.get("REPO_NAME") or REPO_NAME
    return os.environ.get("REPO_SLUG") or env.get("REPO_SLUG") or f"{owner}/{name}"


def fetch_latest_clashgate_version() -> str:
    slug = _resolve_repo_slug()
    url = os.environ.get(
        "CLASHGATE_RAW_COMMON",
        f"https://raw.githubusercontent.com/{slug}/main/scripts/lib/common.sh",
    )
    txt = _http_get_text(url, timeout=20)
    m = re.search(r"^CS_VERSION=([0-9A-Za-z._-]+)", txt, re.M)
    if not m:
        raise RuntimeError("未能从 GitHub 解析最新版本号")
    return m.group(1).strip()


def fetch_latest_mihomo_release() -> dict:
    txt = _http_get_text(MIHOMO_REPO_API, timeout=20, headers={"Accept": "application/vnd.github+json"})
    try:
        data = json.loads(txt)
    except Exception:
        raise RuntimeError("解析 GitHub 返回的版本数据失败") from None
    tag = str(data.get("tag_name") or "").strip()
    if not tag:
        raise RuntimeError("未能从 GitHub 获取 Mihomo 最新版本标签")
    return data


_CORE_UPDATE_TASK_LOCK = threading.Lock()
_CORE_UPDATE_TASK = {
    "running": False,
    "ok": None,
    "msg": "",
    "started_at": 0.0,
    "finished_at": 0.0,
}


def update_mihomo_core_direct() -> tuple:
    """Check GitHub for latest Mihomo release and upgrade binary + restart service if needed.
    Returns (changed: bool, current_ver: str, latest_tag: str, msg: str)."""
    local_ver = get_local_mihomo_version()
    rel = fetch_latest_mihomo_release()
    latest_tag = str(rel.get("tag_name") or "").strip()
    if local_ver and local_ver.strip().lstrip("vV") == latest_tag.lstrip("vV"):
        return False, local_ver, latest_tag, f"已是最新版本 {latest_tag}，无需更新"
    arch = detect_cpu_arch()
    asset_name = f"mihomo-linux-{arch}-{latest_tag}.gz"
    download_url = ""
    for asset in rel.get("assets") or []:
        if isinstance(asset, dict) and asset.get("name") == asset_name:
            download_url = str(asset.get("browser_download_url") or "")
            break
    if not download_url:
        raise RuntimeError(f"GitHub 版本 {latest_tag} 中未找到 {asset_name}")

    bin_path = resolve_mihomo_bin()
    os.makedirs(os.path.dirname(bin_path) or CS_ROOT, mode=0o775, exist_ok=True)
    tmp_gz = bin_path + ".download.gz"
    tmp_bin = bin_path + ".new"
    try:
        req = urllib.request.Request(download_url, headers={"User-Agent": f"clashgate/{VERSION}"})
        try:
            with urllib.request.urlopen(req, timeout=180) as resp, open(tmp_gz, "wb") as out_f:
                shutil.copyfileobj(resp, out_f)
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"下载内核文件失败（HTTP {e.code}）") from None
        except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as e:
            reason = getattr(e, "reason", e)
            raise RuntimeError(f"下载内核文件超时或网络中断，请稍后重试（{reason}）") from None
        try:
            with gzip.open(tmp_gz, "rb") as gz_f, open(tmp_bin, "wb") as bin_f:
                shutil.copyfileobj(gz_f, bin_f)
        except Exception as e:
            raise RuntimeError(f"解压内核文件失败：{e}") from None
        os.chmod(tmp_bin, 0o755)
        rc, v_out = run([tmp_bin, "-v"], timeout=10)
        if rc != 0:
            raise RuntimeError(f"下载的 Mihomo 内核无法运行：{v_out}")
        os.replace(tmp_bin, bin_path)
        if bin_path != "/usr/local/bin/mihomo" and not ROOT:
            try:
                if os.path.islink("/usr/local/bin/mihomo") or not os.path.exists("/usr/local/bin/mihomo"):
                    if os.path.lexists("/usr/local/bin/mihomo"):
                        os.remove("/usr/local/bin/mihomo")
                    os.symlink(bin_path, "/usr/local/bin/mihomo")
            except OSError:
                pass
    finally:
        for p in (tmp_gz, tmp_bin):
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass

    rc, out = validate_config()
    if rc != 0:
        raise RuntimeError("配置校验失败（mihomo -t）：" + out[-300:])
    rc, out = run([SYSTEMCTL, "restart", "mihomo"])
    if rc != 0:
        raise RuntimeError("重启 Mihomo 失败：" + out[-300:])
    wait_mihomo_ports()
    changed = True
    if local_ver:
        msg = f"Mihomo 内核已从 {local_ver} 更新至 {latest_tag} 并重启生效。"
    else:
        msg = f"Mihomo 内核已更新至 {latest_tag} 并重启生效。"
    return changed, local_ver, latest_tag, msg


def start_background_core_update() -> dict:
    """Start or attach to an asynchronous Mihomo core update task so HTTP responses don't time out or get severed by restart."""
    with _CORE_UPDATE_TASK_LOCK:
        if _CORE_UPDATE_TASK["running"]:
            return dict(_CORE_UPDATE_TASK)
        _CORE_UPDATE_TASK["running"] = True
        _CORE_UPDATE_TASK["ok"] = None
        _CORE_UPDATE_TASK["msg"] = "正在后台检查并更新 Mihomo 内核，请稍候…"
        _CORE_UPDATE_TASK["started_at"] = time.time()
        _CORE_UPDATE_TASK["finished_at"] = 0.0

    def _worker():
        ok = False
        msg = ""
        try:
            with LOCK:
                _, _, _, msg = update_mihomo_core_direct()
                ok = True
        except Exception as e:
            msg = f"更新内核失败：{e}"
            ok = False
        finally:
            with _CORE_UPDATE_TASK_LOCK:
                _CORE_UPDATE_TASK["running"] = False
                _CORE_UPDATE_TASK["ok"] = ok
                _CORE_UPDATE_TASK["msg"] = msg
                _CORE_UPDATE_TASK["finished_at"] = time.time()

    t = threading.Thread(target=_worker, name="core-updater", daemon=True)
    t.start()
    with _CORE_UPDATE_TASK_LOCK:
        return dict(_CORE_UPDATE_TASK)


# ---------------------------------------------------------------- Vue 3 + Tailwind CSS Console UI & HTTP
HERE_DIR = os.path.dirname(os.path.abspath(__file__))

STATE_ZH = {"active": ("运行中", "ok"), "inactive": ("已停止", "bad"), "failed": ("失败", "bad"),
            "activating": ("启动中", "warn"), "deactivating": ("停止中", "warn"),
            "reloading": ("重载中", "warn"), "unknown": ("未知", "bad")}
KIND_ZH = {
    "vless-reality": "VLESS Reality",
    "shadowsocks": "Shadowsocks",
    "hysteria2": "Hysteria2",
    "snell": "Snell V5",
    "anytls": "AnyTLS",
    "tuic": "TUIC v5",
    "trusttunnel": "TrustTunnel",
    "shadowquic": "ShadowQUIC",
    "mieru": "Mieru",
    "sudoku": "Sudoku",
    "http": "HTTP",
    "socks": "SOCKS5",
    "hysteria2-realm": "Hysteria2 Realm",
    "mixed": "Mixed",
    "vless": "VLESS",
    "vmess": "VMess",
}


def resolve_dist_file(rel: str) -> str:
    for base in (os.path.join(HERE_DIR, "dist"), os.path.join(CS_ROOT, "panel", "dist")):
        p = os.path.join(base, rel)
        if os.path.isfile(p):
            return p
    return os.path.join(HERE_DIR, "dist", rel)


def load_dist_asset(rel: str) -> str:
    try:
        with open(resolve_dist_file(rel), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def render_spa_html(title: str, boot_data: dict, fallback_html: str = "") -> str:
    css = load_dist_asset("assets/style.css")
    js = load_dist_asset("assets/app.js")
    boot_json = json.dumps(boot_data, ensure_ascii=False).replace("</", "<\\/")
    return (
        "<!doctype html><html lang=zh-CN><head><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>{html.escape(title)}</title>"
        f"<style>{css}</style>"
        f"<script>window.__CS_BOOT__ = {boot_json};</script>"
        "</head>"
        "<body class='bg-[#f6faf8] text-slate-900 antialiased'>"
        f"<div id=app>{fallback_html}</div>"
        f"<script type=module>{js}</script>"
        "</body></html>"
    )


def parse_cert(info: str) -> dict:
    out = {}
    m = re.search(r"notAfter=(.+)", info)
    if m:
        try:
            exp = time.mktime(time.strptime(m.group(1).strip(), "%b %d %H:%M:%S %Y %Z"))
            out["expires"] = time.strftime("%Y-%m-%d %H:%M", time.localtime(exp))
            out["days"] = int((exp - time.time()) // 86400)
            out["hours"] = max(0, int((exp - time.time()) // 3600))
        except ValueError:
            out["expires"] = m.group(1).strip()
    m = re.search(r"issuer=(.+)", info)
    if m:
        cn = re.search(r"CN\s*=\s*([^,/]+)", m.group(1))
        out["issuer"] = (cn.group(1) if cn else m.group(1)).strip()
    return out


class Panel(BaseHTTPRequestHandler):
    server_version = "clashgate/" + VERSION
    cfg: dict = {}
    cfg_path: str = ""
    sessions: dict = {}
    fails: dict = {}

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.client_ip(), fmt % args))

    # -- utils
    def client_ip(self):
        return self.client_address[0]   # direct HTTPS, no reverse proxy: never trust X-Forwarded-For

    def is_https(self):
        return bool(self.cfg.get("tls_cert"))

    def is_ajax(self):
        return (self.headers.get("X-Requested-With") == "fetch"
                or "application/json" in (self.headers.get("Accept") or ""))

    def current_sub_token(self) -> str:
        if self.cfg_path:
            try:
                with open(self.cfg_path) as f:
                    d = json.load(f)
                    if d.get("sub_token"):
                        self.cfg["sub_token"] = d["sub_token"]
            except Exception:
                pass
        return self.cfg.get("sub_token", "")

    def send(self, code, body, ctype="text/html; charset=utf-8", headers=None):
        data = body.encode() if isinstance(body, str) else body
        try:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Connection", "close")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionError, ssl.SSLError, socket.timeout):
            pass

    def redirect(self, to, cookie=None):
        h = {"Location": to}
        if cookie:
            h["Set-Cookie"] = cookie
        self.send(303, "", headers=h)

    def flash(self, msg, ok=True):
        self.redirect(f"/?ok={1 if ok else 0}&msg=" + quote(msg[:600]))

    def build_client_state(self, s: dict, env: dict = None, st: dict = None) -> dict:
        if env is None:
            env = read_env()
        if st is None:
            st = mihomo_status()
        listening = set(st["listening"])
        state_txt, state_cls = STATE_ZH.get(st["active"], (st["active"], "bad"))
        nodes, inbs = read_nodes(), load_inbounds()
        ports = [n["port"] for n in nodes] + [i["port"] for i in inbs]
        n_listen = sum(1 for p in ports if p in listening)
        srv_proxies = load_server_proxies()
        providers = load_proxy_providers()
        cert = parse_cert(st["cert"].get("info", ""))

        inbound_items = []
        all_proxies = []
        for n in nodes:
            proxy = reality_client(n, env)
            all_proxies.append(proxy)
            inbound_items.append({
                "key": f"node:{n['name']}",
                "name": n["name"],
                "kind": "vless-reality",
                "kind_label": KIND_ZH["vless-reality"],
                "port": n["port"],
                "listening": n["port"] in listening,
                "can_reset_password": True,
                "reset_url": f"/nodes/{quote(n['name'])}/reset-password",
                "delete_url": f"/nodes/{quote(n['name'])}/delete",
                "single_config": "- " + json.dumps(proxy, ensure_ascii=False),
                "readable_config": "\n".join(dump_yaml_map(proxy, indent=2, first_dash=True)),
            })
        for i in inbs:
            proxy = i["client"]
            all_proxies.append(proxy)
            can_reset = can_reset_inbound_password(i)
            inbound_items.append({
                "key": f"inb:{i['id']}",
                "name": i["name"],
                "kind": i["kind"],
                "kind_label": KIND_ZH.get(i["kind"], i["kind"]),
                "port": i["port"],
                "listening": i["port"] in listening,
                "can_reset_password": can_reset,
                "reset_url": f"/inbounds/{i['id']}/reset-password" if can_reset else "",
                "delete_url": f"/inbounds/{i['id']}/delete",
                "single_config": "- " + json.dumps(proxy, ensure_ascii=False),
                "readable_config": "\n".join(dump_yaml_map(proxy, indent=2, first_dash=True)),
            })

        all_proxies_yaml = (
            "proxies:\n" + "\n".join("  - " + json.dumps(p, ensure_ascii=False) for p in all_proxies)
            if all_proxies else ""
        )

        proxy_items = []
        for p in srv_proxies:
            if p.get("server") and p.get("port"):
                endpoint = f"{p['server']}:{p['port']}"
            elif p.get("server"):
                endpoint = str(p["server"])
            elif p.get("network-name"):
                endpoint = str(p["network-name"])
            elif p.get("hostname"):
                endpoint = str(p["hostname"])
            else:
                endpoint = str(p.get("type", ""))
            proxy_items.append({
                "name": p["name"],
                "type": str(p.get("type", "")),
                "endpoint": endpoint,
                "udp": bool(p.get("udp", True)),
                "single_config": "- " + json.dumps(p, ensure_ascii=False),
                "readable_config": "\n".join(dump_yaml_map(p, indent=2, first_dash=True)),
            })

        provider_items = []
        for name, cfg in providers.items():
            provider_items.append({
                "name": name,
                "path": str(cfg.get("path", f"./{name}.yaml")),
                "interval": cfg.get("interval", 3600),
                "url": str(cfg.get("url", "")),
                "yaml": dump_yaml_providers({name: cfg}).rstrip("\n"),
            })

        custom_active = is_custom_config_mode()
        try:
            with open(CUSTOM_CONF if custom_active else CONF) as f:
                cur_cfg = f.read()
        except FileNotFoundError:
            cur_cfg = assemble_config()

        cport = get_controller_port(env)
        traffic = get_traffic_stats(env)
        mver = get_mihomo_version_num(st)
        return {
            "version": VERSION,
            "mihomo_version": mver,
            "csrf": s["csrf"],
            "sub_url": self.sub_url(),
            "zb_url": zashboard_url(env),
            "mihomo_secret": get_mihomo_secret(env),
            "srv_cfg_url": "/config/server.yaml",
            "controller_port": cport,
            "controller_listening": cport in listening,
            "certs_present": certs_present(),
            "custom_config_mode": custom_active,
            "custom_config_raw": cur_cfg,
            "status": {
                "active": st["active"],
                "state_txt": state_txt,
                "state_cls": state_cls,
                "mihomo_version": mver,
                "inbound_total": len(ports),
                "inbound_listening": n_listen,
                "outbound_nodes_count": len(srv_proxies),
                "outbound_providers_count": len(providers),
                "cert_days": cert.get("days"),
                "cert_hours": cert.get("hours"),
                "cert_expires": cert.get("expires", ""),
                "traffic_up_bytes": traffic["up_bytes"],
                "traffic_down_bytes": traffic["down_bytes"],
                "traffic_total_bytes": traffic["total_bytes"],
                "traffic_total_gb": traffic["total_gb"],
                "traffic_display": traffic["display"],
                "traffic_detail": traffic["detail"],
            },
            "inbounds": inbound_items,
            "all_proxies_yaml": all_proxies_yaml,
            "proxies": proxy_items,
            "providers": provider_items,
        }

    def respond_mutation(self, s, msg: str, ok: bool = True):
        if not self.is_ajax():
            return self.flash(msg, ok)
        env = read_env()
        st = mihomo_status()
        state = self.build_client_state(s, env, st)
        payload = {
            "ok": ok,
            "msg": msg,
            "state": state,
            "zb_url": state["zb_url"],
            "sub_url": state["sub_url"],
        }
        return self.send(200 if ok else 400, json.dumps(payload, ensure_ascii=False), "application/json; charset=utf-8")

    def simple(self, code, title, text):
        e = html.escape
        body = (f"<div class='min-h-screen flex items-center justify-center p-6'>"
                f"<div class='max-w-md w-full bg-white rounded-2xl border p-8 shadow-sm'>"
                f"<h1 class='text-lg font-bold'>{e(title)}</h1>"
                f"<p class='text-sm text-slate-600 mt-2 mb-4'>{e(text)}</p>"
                f"<a class='inline-block px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm' href=/>返回控制台</a>"
                f"</div></div>")
        self.send(code, render_spa_html(title, {"page": "error", "version": VERSION}, body))

    def session(self):
        for part in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == "cs_session":
                s = self.sessions.get(v)
                if s and s["exp"] > time.time():
                    return v, s
        return None, None

    def form(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 8 * 1024 * 1024:
            raise ValueError("请求体过大（超过 8MB 限制）")
        chunks = []
        rem = n
        while rem > 0:
            chunk = self.rfile.read(min(rem, 65536))
            if not chunk:
                break
            chunks.append(chunk)
            rem -= len(chunk)
        raw = b"".join(chunks).decode("utf-8", errors="replace")
        return {k: v[0] for k, v in parse_qs(raw, keep_blank_values=True).items()}

    def check_csrf(self, s, form):
        return hmac.compare_digest(form.get("csrf", ""), s["csrf"])

    # -- routes
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/healthz":
            return self.send(200, "ok", "text/plain")
        if path.startswith("/assets/"):
            rel = path.lstrip("/")
            if ".." not in rel:
                fp = resolve_dist_file(rel)
                if os.path.isfile(fp):
                    ctype = "application/javascript; charset=utf-8" if fp.endswith(".js") else (
                        "text/css; charset=utf-8" if fp.endswith(".css") else "application/octet-stream"
                    )
                    with open(fp, "rb") as f:
                        return self.send(200, f.read(), ctype)
            return self.send(404, "not found", "text/plain")
        if path == "/login":
            return self.send(200, self.login_page())
        if path.startswith("/sub/"):
            return self.do_sub(path)
        tok, s = self.session()
        if not s:
            return self.redirect("/login")
        if path == "/":
            return self.send(200, self.dashboard(s, initial_tab="inbounds"))
        if path in ("/outbounds",):
            return self.send(200, self.dashboard(s, initial_tab="outbounds"))
        if path in ("/readable", "/convert"):
            return self.send(200, self.dashboard(s, initial_tab="readable"))
        if path in ("/advanced", "/custom-config"):
            return self.send(200, self.dashboard(s, initial_tab="advanced"))
        if path == "/api/state":
            return self.send(200, json.dumps(self.build_client_state(s), ensure_ascii=False), "application/json; charset=utf-8")
        if path == "/api/update-core-status":
            with _CORE_UPDATE_TASK_LOCK:
                tstate = dict(_CORE_UPDATE_TASK)
            if tstate["running"]:
                return self.send(200, json.dumps({"ok": True, "running": True, "msg": tstate["msg"]}, ensure_ascii=False),
                                 "application/json; charset=utf-8")
            state = self.build_client_state(s)
            ok = bool(tstate["ok"]) if tstate["ok"] is not None else True
            payload = {
                "ok": ok,
                "running": False,
                "msg": tstate["msg"] or ("更新内核完成" if ok else "更新内核失败"),
                "state": state,
                "zb_url": state["zb_url"],
                "sub_url": state["sub_url"],
            }
            return self.send(200, json.dumps(payload, ensure_ascii=False), "application/json; charset=utf-8")
        if path in ("/config/server.yaml", "/server.yaml"):
            return self.do_server_config()
        if path == "/api/status":
            st = mihomo_status()
            st["version_panel"] = VERSION
            st["mihomo_version"] = get_mihomo_version_num(st)
            st["custom_config_mode"] = is_custom_config_mode()
            st["traffic"] = get_traffic_stats()
            st["inbounds"] = [{k: i[k] for k in ("id", "kind", "name", "port")} for i in load_inbounds()]
            st["reality_nodes"] = [{"name": n["name"], "port": n["port"]} for n in read_nodes()]
            st["server_proxies"] = [{"name": p.get("name", ""), "type": p.get("type", ""),
                                     "server": p.get("server", ""), "port": p.get("port", "")}
                                    for p in load_server_proxies()]
            st["proxy_providers"] = list(load_proxy_providers().keys())
            return self.send(200, json.dumps(st), "application/json")
        self.simple(404, "页面不存在", "请检查地址是否正确。")

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            form = self.form()
        except ValueError as e:
            if self.is_ajax():
                return self.send(413, json.dumps({"ok": False, "msg": str(e)}), "application/json; charset=utf-8")
            return self.send(413, str(e), "text/plain; charset=utf-8")
        if path == "/login":
            return self.do_login(form)
        tok, s = self.session()
        if not s:
            if self.is_ajax():
                return self.send(401, json.dumps({"ok": False, "msg": "登录会话已过期，请刷新页面重新登录"}), "application/json; charset=utf-8")
            return self.redirect("/login")
        if not self.check_csrf(s, form):
            if self.is_ajax():
                return self.send(403, json.dumps({"ok": False, "msg": "会话校验失败，请刷新页面重试"}), "application/json; charset=utf-8")
            return self.simple(403, "会话校验失败", "页面已过期，请刷新后重试。")
        if path == "/logout":
            self.sessions.pop(tok, None)
            return self.redirect("/login", "cs_session=; Max-Age=0; Path=/")
        if path in ("/action/restart", "/action/reload"):
            return self.do_action(s, path.rsplit("/", 1)[1])
        if path == "/action/update-core":
            return self.do_update_core(s, form)
        if path == "/action/check-update":
            return self.do_check_update(s)
        if path == "/action/upgrade-self":
            return self.do_upgrade_self(s)
        if path == "/action/cert":
            return self.do_cert_action(s)
        if path == "/action/reset-secret":
            return self.do_reset_secret(s)
        if path == "/action/reset-sub":
            return self.do_reset_sub(s)
        if path == "/inbounds/add":
            return self.do_add(s, form)
        if path == "/proxies/add":
            return self.do_add_proxies(s, form)
        if path == "/proxies/delete":
            return self.do_delete_proxy(s, form.get("name", ""))
        if path == "/providers/add":
            return self.do_add_provider(s, form)
        if path == "/providers/delete":
            return self.do_delete_provider(s, form.get("name", ""))
        if path == "/config/custom":
            return self.do_save_custom_config(s, form)
        if path == "/config/reset-template":
            return self.do_reset_template_config(s)
        if path == "/api/convert-readable":
            return self.do_convert_readable(form)
        m = re.fullmatch(r"/inbounds/([0-9a-f]{12})/delete", path)
        if m:
            return self.do_delete(s, m.group(1))
        m = re.fullmatch(r"/inbounds/([0-9a-f]{12})/reset-password", path)
        if m:
            return self.do_reset_inbound_password(s, m.group(1))
        m = re.fullmatch(r"/nodes/([A-Za-z0-9._-]{1,48})/delete", path)
        if m:
            return self.do_delete_node(s, m.group(1))
        m = re.fullmatch(r"/nodes/([A-Za-z0-9._-]{1,48})/reset-password", path)
        if m:
            return self.do_reset_node_password(s, m.group(1))
        self.simple(404, "页面不存在", "请检查地址是否正确。")

    def do_convert_readable(self, form):
        raw = form.get("raw", "")
        try:
            items = parse_mihomo_proxies(raw)
            readable = "proxies:\n" + dump_yaml_proxies(items)
            single = "proxies:\n" + "\n".join("  - " + json.dumps(p, ensure_ascii=False) for p in items)
            payload = {"ok": True, "count": len(items), "readable": readable.rstrip("\n"), "single": single}
            return self.send(200, json.dumps(payload, ensure_ascii=False), "application/json; charset=utf-8")
        except Exception as e:
            return self.send(400, json.dumps({"ok": False, "msg": str(e)}, ensure_ascii=False), "application/json; charset=utf-8")

    def do_server_config(self):
        """GET /config/server.yaml - session-authenticated view of current running server config."""
        try:
            with open(CONF) as f:
                body = f.read()
        except FileNotFoundError:
            body = assemble_config()
        self.send(200, body, "text/plain; charset=utf-8",
                  {"Content-Disposition": 'inline; filename="server.yaml"'})

    def do_sub(self, path):
        """GET /sub/<token>/mihomo.yaml - token-protected subscription; anything else -> 404."""
        m = re.fullmatch(r"/sub/([A-Za-z0-9_-]{16,128})/mihomo\.yaml", path)
        token = self.current_sub_token()
        if not (m and token and hmac.compare_digest(m.group(1), token)):
            return self.send(404, "not found", "text/plain")
        env = read_env()
        try:
            body = render_subscription(env)
        except Exception as e:
            sys.stderr.write(f"subscription render failed: {e}\n")
            return self.send(500, "internal error", "text/plain")
        self.send(200, body, "text/yaml; charset=utf-8",
                  {"Content-Disposition": 'inline; filename="mihomo.yaml"', "profile-update-interval": "24"})

    def sub_url(self):
        token = self.current_sub_token()
        base = panel_base_url(read_env(), self.cfg)
        return f"{base}/sub/{token}/mihomo.yaml" if (token and base) else ""

    def do_login(self, form):
        ip, now = self.client_ip(), time.time()
        recent = [t for t in self.fails.get(ip, []) if now - t < 600]
        if len(recent) >= 5:
            return self.send(429, self.login_page("尝试次数过多，请 10 分钟后再试。"))
        user, pw = form.get("username", ""), form.get("password", "")
        if hmac.compare_digest(user, self.cfg["username"]) and verify_password(pw, self.cfg["password_hash"]):
            self.fails.pop(ip, None)
            tok = secrets.token_urlsafe(32)
            self.sessions[tok] = {"csrf": secrets.token_urlsafe(24), "exp": now + SESSION_TTL}
            cookie = f"cs_session={tok}; HttpOnly; SameSite=Strict; Path=/; Max-Age={SESSION_TTL}"
            if self.is_https():
                cookie += "; Secure"
            return self.redirect("/", cookie)
        recent.append(now)
        self.fails[ip] = recent
        self.send(401, self.login_page("用户名或密码错误。"))

    def do_action(self, s, action):
        global _PENDING_UFW_BASELINE
        zh = {"restart": "重启", "reload": "重载"}[action]
        with LOCK:
            cur_nodes = read_nodes()
            cur_inbs = load_inbounds()
            cur_proxies = load_server_proxies()
            cur_providers = load_proxy_providers()
            atomic_write(FRAG_REALITY, render_reality(cur_nodes), 0o640)
            atomic_write(FRAG_EXTRA, render_extra(cur_inbs), 0o640)
            atomic_write(FRAG_PROXIES, dump_yaml_proxies(cur_proxies), 0o640)
            atomic_write(FRAG_PROVIDERS, dump_yaml_providers(cur_providers), 0o640)
            if is_custom_config_mode():
                _sync_custom_conf_listeners(cur_nodes, cur_inbs)
                _sync_custom_conf_proxies(cur_proxies)
                _sync_custom_conf_providers(cur_providers)
            atomic_write(CONF, assemble_config(), 0o640)
            sync_client_files()
            rc, out = validate_config()
            if rc != 0:
                return self.respond_mutation(s, f"配置校验未通过，未执行{zh}：" + out[-300:], False)
            new_specs = collect_ufw_specs(cur_nodes, cur_inbs)
            old_specs = _PENDING_UFW_BASELINE if _PENDING_UFW_BASELINE is not None else new_specs
            sync_ufw(old_specs, new_specs)
            _PENDING_UFW_BASELINE = new_specs
            rc, out = run([SYSTEMCTL, action, "mihomo"])
            if rc == 0 and action == "reload":
                expected_ports = {int(n["port"]) for n in cur_nodes} | {int(i["port"]) for i in cur_inbs}
                st_now = mihomo_status()
                if st_now["listening"] and not expected_ports.issubset(set(st_now["listening"])):
                    rc, out = run([SYSTEMCTL, "restart", "mihomo"])
            if rc == 0:
                wait_mihomo_ports()
        _, active = run([SYSTEMCTL, "is-active", "mihomo"])
        state = STATE_ZH.get(active.strip(), (active.strip(), ""))[0]
        if rc == 0:
            return self.respond_mutation(s, f"{zh}成功，服务端配置与客户端订阅已同步生效（Mihomo 当前状态：{state}）", active.strip() == "active")
        return self.respond_mutation(s, f"{zh}失败：{out[-300:]}（Mihomo 当前状态：{state}）", False)

    def do_reset_sub(self, s):
        new_token = secrets.token_hex(24)
        with LOCK:
            self.cfg["sub_token"] = new_token
            if self.cfg_path:
                try:
                    with open(self.cfg_path) as f:
                        disk_cfg = json.load(f)
                except Exception:
                    disk_cfg = dict(self.cfg)
                disk_cfg["sub_token"] = new_token
                atomic_write(self.cfg_path, json.dumps(disk_cfg, indent=2, ensure_ascii=False) + "\n", 0o600)
        return self.respond_mutation(s, "订阅链接已更换，旧订阅链接已失效。", True)

    def do_reset_secret(self, s):
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
        new_secret = "".join(secrets.choice(alphabet) for _ in range(20))
        with LOCK:
            old_env = read_env()
            old_secret = old_env.get("MIHOMO_SECRET", "")
            files = (FRAG_CONTROLLER, CUSTOM_CONF, CONF)
            backup = {}
            for p in files:
                try:
                    with open(p) as f:
                        backup[p] = f.read()
                except FileNotFoundError:
                    backup[p] = None
            try:
                write_env_var("MIHOMO_SECRET", new_secret)
                env = read_env()
                atomic_write(FRAG_CONTROLLER, render_controller_fragment(env), 0o640)
                if is_custom_config_mode() and backup[CUSTOM_CONF]:
                    updated = re.sub(r'^(\s*secret\s*:\s*).*$', f'\\1"{new_secret}"', backup[CUSTOM_CONF], flags=re.M)
                    atomic_write(CUSTOM_CONF, updated, 0o640)
                atomic_write(CONF, assemble_config(), 0o640)
                rc, out = validate_config()
                if rc != 0:
                    raise RuntimeError("配置校验失败（mihomo -t）：" + out[-300:])
                rc, out = run([SYSTEMCTL, "restart", "mihomo"])
                if rc != 0:
                    raise RuntimeError("重启失败：" + out[-300:])
                wait_mihomo_ports()
            except Exception as e:
                if old_secret:
                    write_env_var("MIHOMO_SECRET", old_secret)
                for p, data in backup.items():
                    if data is not None:
                        atomic_write(p, data, 0o640)
                run([SYSTEMCTL, "restart", "mihomo"])
                return self.respond_mutation(s, f"重置密钥失败：{e}", False)
        return self.respond_mutation(s, "已重置 Zashboard API 密钥，链接已同步更新。", True)

    def do_cert_action(self, s):
        with LOCK:
            rc, out = run([CERTCTL, "renew"], timeout=180)
        if rc == 0:
            return self.respond_mutation(s, "证书检查 / 续期完成。", True)
        tail = " | ".join(l for l in out.splitlines() if l.strip())[-300:]
        return self.respond_mutation(s, f"证书申请 / 续期失败：{tail}", False)

    def do_update_core(self, s, form=None):
        if form and form.get("async") == "1" and self.is_ajax():
            tstate = start_background_core_update()
            return self.send(
                200,
                json.dumps({"ok": True, "running": True, "msg": tstate["msg"]}, ensure_ascii=False),
                "application/json; charset=utf-8",
            )
        with LOCK:
            try:
                _, _, _, msg = update_mihomo_core_direct()
            except Exception as e:
                return self.respond_mutation(s, f"更新内核失败：{e}", False)
        return self.respond_mutation(s, msg, True)

    def do_check_update(self, s):
        try:
            latest_cs = fetch_latest_clashgate_version()
            cur_cs = VERSION
            has_update = parse_version_tuple(latest_cs) > parse_version_tuple(cur_cs)
            if has_update:
                msg = f"发现新版本 v{latest_cs}（当前 v{cur_cs}）"
            else:
                msg = f"当前已是最新版本（v{cur_cs}）"
            payload = {
                "ok": True,
                "has_update": has_update,
                "current_version": cur_cs,
                "latest_version": latest_cs,
                "msg": msg,
            }
            if not self.is_ajax():
                return self.flash(msg, True)
            return self.send(200, json.dumps(payload, ensure_ascii=False), "application/json; charset=utf-8")
        except Exception as e:
            err_msg = f"检查更新失败：无法连接 GitHub 获取最新版本（{e}）"
            if not self.is_ajax():
                return self.flash(err_msg, False)
            return self.send(400, json.dumps({"ok": False, "has_update": False, "msg": err_msg}, ensure_ascii=False),
                             "application/json; charset=utf-8")

    def do_upgrade_self(self, s):
        with LOCK:
            cmd_bin = CLASHGATE_BIN if os.path.isfile(CLASHGATE_BIN) else "/usr/local/bin/clashgate"
            if not os.path.isfile(cmd_bin):
                return self.respond_mutation(s, "升级失败：未找到 clashgate 管理脚本", False)
            rc, out = run(["bash", cmd_bin, "update"], timeout=180)
            if rc != 0:
                tail = " | ".join(l for l in out.splitlines() if l.strip())[-300:]
                return self.respond_mutation(s, f"升级失败：{tail}", False)
        return self.respond_mutation(s, "升级成功！ClashGate 与 Mihomo 内核已更新至最新版本。", True)

    def do_add(self, s, form):
        env = read_env()
        req_id = (form.get("req_id") or "").strip()
        raw_kind = (form.get("kind") or "").strip()
        if raw_kind == "shadowqiuc":
            raw_kind = "shadowquic"
        elif raw_kind == "soduku":
            raw_kind = "sudoku"
        raw_name = (form.get("name") or "").strip()
        raw_port = (form.get("port") or "").strip()
        with LOCK:
            now = time.time()
            for k in [k for k, v in _RECENT_ADD_REQS.items() if now - v[0] > 60]:
                _RECENT_ADD_REQS.pop(k, None)
            if req_id and req_id in _RECENT_ADD_REQS:
                prev_inb = _RECENT_ADD_REQS[req_id][1]
                return self.respond_mutation(
                    s,
                    f"已添加 {KIND_ZH.get(prev_inb['kind'], prev_inb['kind'])} 节点「{prev_inb['name']}」（端口 {prev_inb['port']}），已保存，请点顶部「重载配置」生效",
                    True,
                )
            cur = load_inbounds()
            target_name = raw_name or DEFAULT_NODE_NAMES.get(raw_kind, raw_kind)
            if any(existing.get("name") == target_name for existing in cur):
                return self.respond_mutation(s, "节点名称重复，添加失败", False)
            try:
                inb = build_inbound(raw_kind, form, env)
                save_inbounds(cur + [inb])
                if req_id:
                    _RECENT_ADD_REQS[req_id] = (now, inb)
            except Exception as e:
                return self.respond_mutation(s, f"添加失败：{e}", False)
        return self.respond_mutation(
            s,
            f"已添加 {KIND_ZH.get(inb['kind'], inb['kind'])} 节点「{inb['name']}」（端口 {inb['port']}），已保存，请点顶部「重载配置」生效",
            True,
        )

    def do_delete(self, s, iid):
        with LOCK:
            _RECENT_ADD_REQS.clear()
            cur = load_inbounds()
            new = [i for i in cur if i["id"] != iid]
            if len(new) == len(cur):
                return self.respond_mutation(s, "节点删除成功，重载配置生效", True)
            try:
                save_inbounds(new)
            except Exception as e:
                return self.respond_mutation(s, f"删除失败：{e}", False)
        return self.respond_mutation(s, "节点删除成功，重载配置生效", True)

    def do_delete_node(self, s, name):
        with LOCK:
            _RECENT_ADD_REQS.clear()
            cur = read_nodes()
            new = [n for n in cur if n["name"] != name]
            if len(new) == len(cur):
                return self.respond_mutation(s, "已删除", True)
            try:
                save_nodes(new)
            except Exception as e:
                return self.respond_mutation(s, f"删除失败：{e}", False)
        return self.respond_mutation(s, f"已删除节点「{name}」，请点顶部「重载配置」生效", True)

    def do_reset_node_password(self, s, name):
        with LOCK:
            cur = read_nodes()
            found = False
            new_nodes = []
            try:
                for n in cur:
                    if n["name"] == name:
                        found = True
                        priv, pub = reality_keypair()
                        dec, enc = vless_x25519_keypair()
                        n = dict(n)
                        n["uuid"] = str(uuidlib.uuid4())
                        n["priv"] = priv
                        n["pub"] = pub
                        n["sid"] = secrets.token_hex(4)
                        n["dec"] = dec
                        n["enc"] = enc
                    new_nodes.append(n)
                if not found:
                    return self.respond_mutation(s, "入站节点不存在", False)
                apply_nodes(new_nodes)
            except Exception as e:
                return self.respond_mutation(s, f"重置密钥失败：{e}", False)
        return self.respond_mutation(s, f"已重置节点「{name}」的 UUID、Reality 私钥与 VLESS 加密密钥，服务端与订阅已同步更新。", True)

    def do_reset_inbound_password(self, s, iid):
        with LOCK:
            cur = load_inbounds()
            target_name = ""
            target_kind = ""
            new_inbs = []
            try:
                for i in cur:
                    if i["id"] == iid:
                        if not can_reset_inbound_password(i):
                            return self.respond_mutation(s, "该入站协议无需密码，不支持重置密码", False)
                        target_name = i["name"]
                        target_kind = i["kind"]
                        i = rotate_inbound_credentials(i)
                    new_inbs.append(i)
                if not target_name:
                    return self.respond_mutation(s, "入站节点不存在", False)
                apply_inbounds(new_inbs)
            except Exception as e:
                return self.respond_mutation(s, f"重置密码失败：{e}", False)
        return self.respond_mutation(s, "密码重置成功，重载配置生效", True)

    def do_add_proxies(self, s, form):
        raw = form.get("proxies_raw", "")
        with LOCK:
            try:
                added = parse_mihomo_proxies(raw)
                cur = load_server_proxies()
                by_name = {p["name"]: i for i, p in enumerate(cur)}
                merged = list(cur)
                for p in added:
                    if p["name"] in by_name:
                        merged[by_name[p["name"]]] = p
                    else:
                        by_name[p["name"]] = len(merged)
                        merged.append(p)
                save_server_proxies(merged)
            except Exception as e:
                return self.respond_mutation(s, f"添加服务端 proxies 节点失败：{e}", False)
        names = "、".join(p["name"] for p in added)
        return self.respond_mutation(s, f"已向服务端 proxies: 添加 {len(added)} 个节点（{names}），已保存，请点顶部「重载配置」生效", True)

    def do_delete_proxy(self, s, name):
        with LOCK:
            cur = load_server_proxies()
            new = [p for p in cur if p["name"] != name]
            if len(new) == len(cur):
                return self.respond_mutation(s, "已删除", True)
            try:
                save_server_proxies(new)
            except Exception as e:
                return self.respond_mutation(s, f"删除服务端节点失败：{e}", False)
        return self.respond_mutation(s, f"已删除节点「{name}」，请点顶部「重载配置」生效", True)

    def do_add_provider(self, s, form):
        url = form.get("sub_url", "")
        name = form.get("provider_name", "")
        with LOCK:
            try:
                cur = load_proxy_providers()
                prov_name, entry = build_proxy_provider(url, name, cur)
                merged = dict(cur)
                merged[prov_name] = entry
                save_proxy_providers(merged)
            except Exception as e:
                return self.respond_mutation(s, f"导入订阅链接失败：{e}", False)
        return self.respond_mutation(
            s, f"已导入订阅源「{prov_name}」（路径 {entry['path']}）到服务端 proxy-providers:，已保存，请点顶部「重载配置」生效", True)

    def do_delete_provider(self, s, name):
        with LOCK:
            cur = load_proxy_providers()
            if name not in cur:
                return self.respond_mutation(s, "已删除", True)
            merged = {k: v for k, v in cur.items() if k != name}
            try:
                save_proxy_providers(merged)
            except Exception as e:
                return self.respond_mutation(s, f"删除订阅源失败：{e}", False)
        return self.respond_mutation(s, f"已删除订阅源「{name}」，请点顶部「重载配置」生效", True)

    def do_save_custom_config(self, s, form):
        raw = form.get("custom_config_raw", "")
        auto_fix = form.get("auto_fix_certs") == "1"
        with LOCK:
            try:
                env = read_env()
                if auto_fix:
                    raw, _ = rewrite_cert_paths_in_yaml(raw, env)
                apply_custom_config(raw)
            except Exception as e:
                return self.respond_mutation(s, f"更新自定义服务端配置失败：{e}", False)
        return self.respond_mutation(s, "自定义 mihomo 服务端配置已通过校验并应用生效。", True)

    def do_reset_template_config(self, s):
        with LOCK:
            try:
                reset_to_template_config()
            except Exception as e:
                return self.respond_mutation(s, f"恢复默认配置失败：{e}", False)
        return self.respond_mutation(s, "已恢复默认服务端配置，并生成默认 VlessReality 节点。", True)

    # -- views
    def login_page(self, err=""):
        e = html.escape
        mver = get_mihomo_version_num()
        boot = {"page": "login", "version": VERSION, "mihomo_version": mver, "login_error": err}
        err_html = f"<div class=err>{e(err)}</div>" if err else ""
        fallback = (
            f"<div><h1>ClashGate <span>v{VERSION}</span></h1>{err_html}"
            f"<form method=post action=/login>"
            f"<input id=u name=username value=admin required>"
            f"<input id=p name=password type=password required>"
            f"<button type=submit>登 录</button></form></div>"
        )
        return render_spa_html("登录 · ClashGate", boot, fallback)

    def dashboard(self, s, initial_tab="inbounds"):
        q = parse_qs(urlparse(self.path).query)
        msg, ok = q.get("msg", [""])[0], q.get("ok", ["1"])[0] == "1"
        tab_q = q.get("tab", [""])[0]
        if tab_q in ("inbounds", "outbounds", "readable", "advanced"):
            initial_tab = tab_q
        env = read_env()
        st = mihomo_status()
        state = self.build_client_state(s, env, st)
        boot = {
            "page": "dashboard",
            "initial_tab": initial_tab,
            "flash_msg": msg,
            "flash_ok": ok,
            **state,
        }
        e = html.escape
        hid = f"<input type=hidden name=csrf value='{e(s['csrf'])}'>"
        opts = "".join(f"<option value={k}>{e(KIND_ZH.get(k, k))}</option>" for k in TYPES)
        inb_rows = "".join(
            f"<div><span>{e(it['name'])}</span><span>{e(it['kind_label'])}</span>"
            f"<span>:{it['port']}</span>"
            f"<button type=button>复制配置</button>"
            + (f"<form method=post action='{e(it['reset_url'])}'>{hid}<button type=submit>重置密码</button></form>" if it.get("can_reset_password") else "")
            + "</div>"
            for it in state["inbounds"]
        )
        zb_sec = (
            f"<section id=zashboard-card><h2>Zashboard 控制面板</h2>"
            f"<div id=zb-url>{e(state['zb_url'])}</div>"
            f"<div id=zb-secret>{e(state.get('mihomo_secret', ''))}</div>"
            f"<a href='{e(state['zb_url'] or '#')}' target=_blank rel=noopener>打开 Zashboard</a>"
            f"<button type=button>复制地址</button>"
            f"<form method=post action=/action/reset-secret>{hid}<button type=submit>重置 API 密钥</button></form></section>"
        )
        sub_sec = (
            f"<section><h2>客户端订阅链接</h2><div id=sub-url>{e(state['sub_url'])}</div>"
            f"<button type=button>复制订阅链接</button>"
            f"<form method=post action=/action/reset-sub>{hid}<button type=submit>更换订阅链接</button></form></section>"
            if state["sub_url"] else ""
        )
        mver = state.get("mihomo_version", "")
        ver_label = f"v{VERSION} · mihomo {mver}" if mver else f"v{VERSION}"
        fallback = (
            f"<header><span>ClashGate</span><span>{e(ver_label)}</span></header>"
            f"<main>{zb_sec}{sub_sec}"
            f"<section><h2>入站节点</h2>{inb_rows}</section>"
            f"<section><h2>添加节点</h2><form method=post action=/inbounds/add>{hid}"
            f"<select id=kind name=kind>{opts}</select>"
            f"<p>{e(PROTOCOL_DESCRIPTIONS['vless-reality'])}</p>"
            f"<input id=nm name=name value=VlessReality placeholder='默认 VlessReality'>"
            f"<input id=port name=port placeholder='留空随机端口'>"
            f"<button type=submit>添加入站节点</button></form></section></main>"
        )
        return render_spa_html("ClashGate", boot, fallback)


class TLSServer(ThreadingHTTPServer):
    """HTTPS server: handshake runs in the worker thread (a slow client cannot block accept),
    and the certificate is reloaded automatically when acme.sh renews it (file mtime changes)."""
    daemon_threads = True

    def __init__(self, addr, handler, cert, key):
        self.cert, self.key, self._stamp, self.ctx = cert, key, None, None
        self._reload()
        super().__init__(addr, handler)

    def _reload(self):
        try:
            stamp = (os.stat(self.cert).st_mtime_ns, os.stat(self.key).st_mtime_ns)
        except OSError:
            return
        if stamp == self._stamp:
            return
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.set_alpn_protocols(["http/1.1"])
        try:
            ctx.load_cert_chain(self.cert, self.key)
        except (OSError, ssl.SSLError) as e:
            sys.stderr.write(f"certificate load failed: {e}\n")
            if self.ctx is None:
                raise
            return
        self.ctx, self._stamp = ctx, stamp
        sys.stderr.write("certificate loaded\n")

    def get_request(self):
        sock, addr = self.socket.accept()
        self._reload()
        sock.settimeout(120)
        return self.ctx.wrap_socket(sock, server_side=True, do_handshake_on_connect=False), addr

    def finish_request(self, request, client_address):
        try:
            request.do_handshake()
            request.settimeout(180)
        except (ssl.SSLError, OSError):
            return   # plain HTTP / scanners / aborted handshakes: drop quietly
        super().finish_request(request, client_address)

    def handle_error(self, request, client_address):
        if isinstance(sys.exc_info()[1], (ssl.SSLError, ConnectionError, socket.timeout)):
            return
        super().handle_error(request, client_address)


def serve(cfg_path):
    ensure_unified_root()
    if not os.path.isfile(cfg_path) and os.path.isfile(CS_ROOT + "/panel.json"):
        cfg_path = CS_ROOT + "/panel.json"
    with open(cfg_path) as f:
        cfg = json.load(f)
    Panel.cfg = cfg
    Panel.cfg_path = cfg_path
    start_traffic_poller(30)
    addr = (cfg.get("listen", "0.0.0.0"), int(cfg.get("port", 8443)))
    if cfg.get("tls_cert"):
        cert_p = ROOT + cfg["tls_cert"]
        key_p = ROOT + cfg["tls_key"]
        if not os.path.isfile(cert_p) and os.path.isfile(ROOT + CERT):
            cert_p, key_p = ROOT + CERT, ROOT + KEY
        httpd = TLSServer(addr, Panel, cert_p, key_p)
        scheme = "https"
    else:   # local development only
        httpd = ThreadingHTTPServer(addr, Panel)
        scheme = "http"
    sys.stderr.write(f"clashgate v{VERSION} listening on {scheme}://{addr[0]}:{addr[1]}\n")
    httpd.serve_forever()


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("hash-password")
    sp = sub.add_parser("serve")
    sp.add_argument("--config", required=True)
    a = ap.parse_args()
    if a.cmd == "hash-password":
        pw = sys.stdin.readline().rstrip("\n")
        if len(pw) < 8:
            sys.exit("密码太短（至少 8 位）")
        print(hash_password(pw))
    else:
        serve(a.config)


if __name__ == "__main__":
    main()
