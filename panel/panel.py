#!/usr/bin/env python3
"""ClashGate v1.17 - admin console (Vue 3 + Tailwind CSS).

Stdlib only (Python 3). Serves HTTPS itself with the same certificate
Mihomo uses (/etc/clashgate/certs); no reverse proxy.
Unified directory layout under /etc/clashgate.

Subcommands:
  panel.py hash-password            read password on stdin, print hash
  panel.py serve --config FILE      run the HTTP server
"""
import argparse
import base64
import datetime
import gzip
import hashlib
import hmac
import html
import json
import os
import random
import re
import secrets
import shlex
import shutil
import socket
import ssl
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid as uuidlib
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse, quote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# `python3 panel.py serve` loads this file as __main__. Later modules import panel
# and must get this same module, not a second copy.
if __name__ == "__main__":
    sys.modules["panel"] = sys.modules[__name__]

from i18n_en import tr as _tr_msg, detect_lang as _detect_lang  # noqa: E402  (0.97 i18n: zh default, en on cookie clashgate_lang=en)
from routing_mgr import RoutingManager, parse_yaml_document_factory  # noqa: E402
from cg_masque import (  # noqa: E402
    _cf_json,
    _edge_public_b64,
    _host_only,
    _masque_worker,
    _openssl,
    _p256_keypair_b64,
    _x25519_public_b64,
    load_masque_state,
    register_cloudflare_masque,
    save_masque_state,
    start_masque_registrar,
)
from cg_cert import (  # noqa: E402
    _CERT_FILE_EXT,
    _CERT_SECTIONS,
    _WG_KEY_RE,
    _is_cert_path_value,
    _iter_server_cert_lines,
    missing_cert_files,
    rewrite_cert_paths_in_yaml,
    server_cert_paths,
    sync_env_from_custom_config,
)
from cg_yaml import (  # noqa: E402
    STR_KEYS,
    build_proxy_provider,
    dump_yaml_map,
    dump_yaml_providers,
    dump_yaml_proxies,
    parse_flow_val,
    parse_mihomo_proxies,
    parse_scalar,
    parse_yaml_lines,
    split_flow,
    split_kv,
    strip_yaml_comment,
    yaml_scalar,
)
import cg_update  # noqa: E402
from cg_update import (  # noqa: E402
    TRAFFIC_LOCK,
    format_traffic_gb,
    format_traffic_detail,
    _controller_uses_tls,
    fetch_mihomo_connections_totals,
    get_traffic_stats,
    start_traffic_poller,
    parse_version_tuple,
    get_local_mihomo_version,
    mihomo_supports_snell_v6,
    _SNELL_V5_DEFAULT_NAME,
    _snell_needs_v6,
    _name_used_in_routing,
    migrate_snell_to_v6,
    run_snell_migration,
    get_mihomo_version_num,
    detect_cpu_arch,
    _http_get_text,
    _normalize_update_channel,
    resolve_update_channel,
    resolve_update_target,
    apply_update_channel_env,
    fetch_channel_commit_sha,
    fetch_channel_tip,
    _upgrade_log_tail,
    load_upgrade_status,
    start_upgrade_job,
    fetch_latest_mihomo_release,
    _blank_update_slot,
    load_update_check,
    save_update_check,
    public_update_check,
    refresh_update_check_for_version,
    _update_due,
    record_core_check,
    record_panel_check,
    check_core_update,
    check_panel_update,
    _check_due_updates,
    _apply_auto_update,
    start_weekly_update_check,
    _CORE_UPDATE_TASK_LOCK,
    _CORE_UPDATE_TASK,
    update_mihomo_core_direct,
    start_background_core_update,
)
import cg_cluster  # noqa: E402
from cg_cluster import (  # noqa: E402
    CLUSTER_PROTOCOL,
    CLUSTER_MIN_VERSION,
    CLUSTER_LISTENER_PREFIX,
    CLUSTER_FLOW,
    CLUSTER_TICKET_TTL,
    CLUSTER_TOMBSTONE_TTL,
    _CLUSTER_OP_LOCK,
    _CLUSTER_TICKETS,
    _CLUSTER_TICKETS_LOCK,
    _CLUSTER_PORT_HOLD,
    _INST_RE,
    _ENC_RE,
    load_cluster,
    cluster_instance_id,
    cluster_proxy_from_link,
    cluster_listener_from_link,
    render_cluster_proxies,
    render_cluster_listeners,
    save_cluster,
    _read_frag,
    cluster_proxy_names,
    cluster_ports,
    cluster_ufw_specs,
    vless_mlkem768_pair,
    used_proxy_names,
    _live_conf_with_cluster,
    apply_cluster_live,
    ClusterError,
    _NoRedirect,
    normalize_panel_url,
    _cluster_ssl_context,
    cluster_http,
    cluster_hello,
    ClusterRemoteError,
    _remote_error,
    local_cluster_url,
    _link_by,
    cluster_members_view,
    _link_auth,
    cluster_call,
    _cluster_new_inbound,
    _cluster_commit,
    _parse_node,
    cluster_pair,
    cluster_issue_ticket,
    _drop_links,
    cluster_leave_all,
    _update_link,
    cluster_sync,
    cluster_report_text,
    cluster_push_name_async,
)
from cg_qr import (  # noqa: E402
    _GF_EXP,
    _GF_LOG,
    _QR_CACHE,
    _QR_VER_L,
    _gf_mul,
    _i,
    _make_qr_matrix,
    _rs_encode,
    _x,
    qr_png_data_url,
)

# Versions compare as integer tuples (parse_version_tuple): 1.17 > 1.16 > 1.15 > 1.14 > 1.13 > 1.12 > 1.11 > 1.10 > 1.09. Never publish "1.1"/"1.2" (they
# would sort below 1.09 on every installed panel); the next releases are 1.18, 1.19, ...
VERSION = "1.17"

# CLASHGATE_ROOT lets the panel run against a fake tree for local testing.
ROOT = os.environ.get("CLASHGATE_ROOT", "")
CS_ROOT = ROOT + "/etc/clashgate"
ENV_FILE = CS_ROOT + "/clashgate.env"
INBOUNDS = CS_ROOT + "/inbounds.json"
PROXIES_JSON = CS_ROOT + "/proxies.json"
PROVIDERS_JSON = CS_ROOT + "/providers.json"
PENDING_RELOAD_JSON = CS_ROOT + "/pending_reload.json"
PENDING_BASELINE_JSON = CS_ROOT + "/pending_baseline.json"
TRAFFIC_JSON = CS_ROOT + "/traffic.json"
SESSIONS_JSON = CS_ROOT + "/sessions.json"
PANEL_SETTINGS = CS_ROOT + "/panel_settings.json"
MASQUE_JSON = CS_ROOT + "/masque.json"
MASQUE_NAME = "⛅️ Cloudflare-MASQUE"
UPDATE_CHECK_JSON = CS_ROOT + "/update_check.json"
UPDATE_CHECK_INTERVAL = 7 * 24 * 3600
UPDATE_CHANNEL_MAP = {
    "stable": {"owner": "ClashGate", "name": "ClashGate", "branch": "main", "label": "正式"},
    "test": {"owner": "ClashGate", "name": "ClashGate", "branch": "test", "label": "测试"},
}
MIHOMO_DIR = CS_ROOT
CONF = MIHOMO_DIR + "/config.yaml"
CUSTOM_CONF = MIHOMO_DIR + "/custom_config.yaml"
# Kept when custom mode is switched off, so turning it back on can restore the user's config.
CUSTOM_SAVED = CUSTOM_CONF + ".saved"
NODES_TSV = MIHOMO_DIR + "/nodes.tsv"
FRAG_CONTROLLER = MIHOMO_DIR + "/controller.yaml"
FRAG_REALITY = MIHOMO_DIR + "/listeners.reality.yaml"
FRAG_EXTRA = MIHOMO_DIR + "/listeners.extra.yaml"
FRAG_PROXIES = MIHOMO_DIR + "/proxies.extra.yaml"
FRAG_PROVIDERS = MIHOMO_DIR + "/providers.extra.yaml"
ROUTING_JSON = CS_ROOT + "/routing.json"
ROUTING_DIR = CS_ROOT + "/routing"
FRAG_RULE_PROVIDERS = MIHOMO_DIR + "/routing.rule-providers.yaml"
FRAG_PROXY_GROUPS = MIHOMO_DIR + "/routing.proxy-groups.yaml"
FRAG_RULES = MIHOMO_DIR + "/routing.rules.yaml"
# 1.14 cluster: links to other ClashGate panels. Kept out of the draft / reload flow and out of the
# node list and client subscription; rendered into their own fragments and applied live.
CLUSTER_JSON = CS_ROOT + "/cluster.json"
FRAG_CLUSTER_LISTENERS = MIHOMO_DIR + "/listeners.cluster.yaml"
FRAG_CLUSTER_PROXIES = MIHOMO_DIR + "/proxies.cluster.yaml"
CLIENT_DIR = CS_ROOT + "/client"
CERTCTL = CS_ROOT + "/scripts/certctl.sh"
CERT = "/etc/clashgate/certs/fullchain.pem"   # paths as seen by mihomo (not ROOT-prefixed)
KEY = "/etc/clashgate/certs/privkey.pem"
MIHOMO_REPO_API = os.environ.get("MIHOMO_REPO_API", "https://api.github.com/repos/MetaCubeX/mihomo/releases/latest")
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
SESSION_TTL = 7 * 24 * 3600
LOGIN_WINDOW = 600              # seconds
LOGIN_MAX_FAILS_PER_IP = 5      # per IPv4 address / IPv6 /64 within the window
LOGIN_MAX_FAILS_TOTAL = 50      # all sources together (distributed guessing)
_SESSION_LOCK = threading.Lock()
_MASQUE_LOCK = threading.Lock()


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


_PENDING_UFW_BASELINE = None
_RECENT_ADD_REQS = {}


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
    global _PENDING_UFW_BASELINE
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
    _PENDING_UFW_BASELINE = None
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
    global _PENDING_UFW_BASELINE
    _ensure_pending_baseline()
    cur_nodes = read_nodes()
    if _PENDING_UFW_BASELINE is None:
        _PENDING_UFW_BASELINE = collect_ufw_specs(cur_nodes, load_inbounds())
    cleaned = _dedup_inbounds(new)
    atomic_write(INBOUNDS, json.dumps(cleaned, indent=2, ensure_ascii=False), 0o600)
    atomic_write(FRAG_EXTRA, render_extra(cleaned), 0o640)
    _sync_custom_conf_listeners(cur_nodes, cleaned)
    # 0.96: draft only. Live CONF / client sync / reload happen solely in do_action(reload|restart).


def save_nodes(new_nodes: list):
    """Persist install-time VLESS Reality nodes (nodes.tsv) and config fragments to disk without reloading Mihomo."""
    global _PENDING_UFW_BASELINE
    _ensure_pending_baseline()
    cur_inbs = load_inbounds()
    if _PENDING_UFW_BASELINE is None:
        _PENDING_UFW_BASELINE = collect_ufw_specs(read_nodes(), cur_inbs)
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




UPGRADE_STATUS_JSON = CS_ROOT + "/upgrade_status.json"
UPGRADE_LOG = CS_ROOT + "/upgrade.log"




# ---------------------------------------------------------------- Vue 3 + Tailwind CSS Console UI & HTTP
HERE_DIR = os.path.dirname(os.path.abspath(__file__))

STATE_ZH = {"active": ("运行中", "ok"), "inactive": ("已停止", "bad"), "failed": ("失败", "bad"),
            "activating": ("启动中", "warn"), "deactivating": ("停止中", "warn"),
            "reloading": ("重载中", "warn"), "unknown": ("未知", "bad")}
KIND_ZH = {
    "vless-reality": "VLESS Reality",
    "shadowsocks": "Shadowsocks",
    "hysteria2": "Hysteria2",
    "snell": "Snell V6",
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
    noscript = f"<noscript>{fallback_html}</noscript>" if fallback_html else ""
    return (
        "<!doctype html><html lang=zh-CN><head><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>{html.escape(title)}</title>"
        "<link rel=icon type=image/png href=/favicon.png><link rel='shortcut icon' href=/favicon.ico>"
        "<style>html{background:#f3f6fb}html:not(.cg-ready) #app{visibility:hidden}</style>"
        # Panel skin (Settings): applied before first paint so the page never flashes the default look.
        "<script>try{if(localStorage.getItem('clashgate_theme')==='christmas')"
        "document.documentElement.dataset.theme='christmas'}catch(e){}</script>"
        f"<style>{css}</style>"
        f"<script>window.__CS_BOOT__ = {boot_json};</script>"
        "</head>"
        "<body class='antialiased'>"
        "<div id=app></div>"
        f"{noscript}"
        f"<script>{js}</script>"
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


def public_cluster_state(locked: bool, lang: str = "zh") -> dict:
    """Cluster data for the browser. Never includes keys, UUIDs or tickets."""
    st = load_cluster()

    def tr(msg):
        return _tr_msg(msg, lang) if msg and lang in ("en", "ru", "fa") else msg
    settings = load_panel_settings()
    return {
        "node_name": settings.get("node_name") or default_node_name(),
        "node_name_set": bool(settings.get("node_name")),
        "node_name_max": NODE_NAME_MAX,
        "locked": bool(locked),
        "self_url": local_cluster_url(),
        "members": [{"id": l["id"], "name": l.get("name", ""), "url": l.get("url", ""), "version": l.get("version", ""),
                     "ok": l.get("ok", True), "error": tr(l.get("error", "")), "missing": list(l.get("missing") or []),
                     "created": l.get("created", 0), "seen": l.get("seen", 0)} for l in st["links"]],
        "pending": [{"name": p.get("name", ""), "url": p.get("url", ""), "error": tr(p.get("error", ""))} for p in st["pending"]],
    }


class Panel(BaseHTTPRequestHandler):
    server_version = "clashgate/" + VERSION
    cfg: dict = {}
    cfg_path: str = ""
    sessions: dict = {}
    fails: dict = {}

    def log_message(self, fmt, *args):
        # Never log the subscription token (the access log goes to the journal).
        line = re.sub(r"/sub/[^/\s\"]+", "/sub/<token>", fmt % args)
        sys.stderr.write("%s %s\n" % (self.client_ip(), line))

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

    def lang(self):
        return _detect_lang(self.headers.get("Cookie") or "", self.headers.get("Accept-Language") or "")

    def tr(self, msg):
        return _tr_msg(msg, self.lang())

    def send(self, code, body, ctype="text/html; charset=utf-8", headers=None):
        if ctype.startswith("application/json") and isinstance(body, str) and self.lang() in ("en", "ru", "fa"):
            try:
                obj = json.loads(body)
                if isinstance(obj, dict) and isinstance(obj.get("msg"), str):
                    obj["msg"] = _tr_msg(obj["msg"], self.lang())
                    body = json.dumps(obj, ensure_ascii=False)
            except ValueError:
                pass
        data = body.encode() if isinstance(body, str) else body
        try:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Connection", "close")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
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
        self.redirect(f"/?ok={1 if ok else 0}&msg=" + quote(self.tr(msg)[:600]))

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

        pending_st = load_pending_reload()
        pending_items = list(pending_st["items"])
        pending_reset_names = {
            it.get("name") for it in pending_items
            if it.get("op") == "reset-password" and it.get("name")
        }

        inbound_items = []
        all_proxies = []
        for n in nodes:
            proxy = reality_client(n, env)
            all_proxies.append(proxy)
            is_pending = (n["port"] not in listening and st["active"] == "active") or (n["name"] in pending_reset_names)
            inbound_items.append({
                "key": f"node:{n['name']}",
                "name": n["name"],
                "kind": "vless-reality",
                "kind_label": KIND_ZH["vless-reality"],
                "port": n["port"],
                "listening": n["port"] in listening and (n["name"] not in pending_reset_names),
                "pending_reload": is_pending,
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
            is_pending = (i["port"] not in listening and st["active"] == "active") or (i["name"] in pending_reset_names)
            inbound_items.append({
                "key": f"inb:{i['id']}",
                "name": i["name"],
                "kind": i["kind"],
                "kind_label": KIND_ZH.get(i["kind"], i["kind"]),
                "port": i["port"],
                "listening": i["port"] in listening and (i["name"] not in pending_reset_names),
                "pending_reload": is_pending,
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
        custom_saved = (not custom_active) and os.path.isfile(CUSTOM_SAVED)
        try:
            with open(CUSTOM_CONF if custom_active else (CUSTOM_SAVED if custom_saved else CONF)) as f:
                cur_cfg = f.read()
        except FileNotFoundError:
            cur_cfg = assemble_config()

        cport = get_controller_port(env)
        traffic = get_traffic_stats(env)
        mver = get_mihomo_version_num(st)
        cur_sub_url = self.sub_url()
        req_lang = self.lang()
        localized_pending_items = []
        for it in pending_items:
            entry = dict(it)
            if req_lang in ("en", "ru", "fa") and isinstance(entry.get("detail"), str):
                entry["detail"] = _tr_msg(entry["detail"], req_lang)
            localized_pending_items.append(entry)
        has_certs = certs_present()
        install_mode = env.get("MODE") or ("auto-cert" if (has_certs or env.get("DOMAIN") or env.get("CERT_MODE")) else "no-cert")
        cert_mode = env.get("CERT_MODE") or "port"
        domain = env.get("DOMAIN", "")
        cf_token = env.get("CF_TOKEN", "")
        cert_issuer = cert.get("issuer", "")
        cert_expires = cert.get("expires", "")
        cert_days = cert.get("days")
        cert_hours = cert.get("hours")
        return {
            "version": VERSION,
            "mihomo_version": mver,
            "csrf": s["csrf"],
            "sub_url": cur_sub_url,
            "sub_qr_data_url": qr_png_data_url(cur_sub_url) if cur_sub_url else "",
            "zb_url": zashboard_url(env),
            "mihomo_secret": get_mihomo_secret(env),
            "srv_cfg_url": "/config/server.yaml",
            "controller_port": cport,
            "controller_listening": cport in listening,
            "certs_present": has_certs,
            "mode": install_mode,
            "cert_mode": cert_mode,
            "domain": domain,
            "cf_token": cf_token,
            "cert_issuer": cert_issuer,
            "cert_expires": cert_expires,
            "cert_days": cert_days,
            "cert_hours": cert_hours,
            "custom_config_mode": custom_active,
            "custom_config_saved": custom_saved,
            "custom_server_enabled": bool(load_panel_settings().get("custom_server_enabled")),
            "auto_update": bool(load_panel_settings().get("auto_update")),
            **(lambda t: {"update_channel": t["channel"], "update_channel_label": t["label"]})(resolve_update_target()),
            "custom_config_raw": cur_cfg,
            "masque": _localize_fields(load_masque_state(), ("error",), req_lang),
            "update_check": public_update_check(mver),
            "pending_reload_count": len(localized_pending_items),
            "pending_reload_items": localized_pending_items,
            "status": {
                "active": st["active"],
                "state_txt": state_txt,
                "state_cls": state_cls,
                "mihomo_version": mver,
                "inbound_total": len(ports),
                "inbound_listening": n_listen,
                "outbound_nodes_count": len(srv_proxies),
                "outbound_providers_count": len(providers),
                "pending_reload_count": len(localized_pending_items),
                "mode": install_mode,
                "cert_mode": cert_mode,
                "domain": domain,
                "cert_issuer": cert_issuer,
                "cert_days": cert_days,
                "cert_hours": cert_hours,
                "cert_expires": cert_expires,
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
            "cluster": public_cluster_state(custom_active or bool(load_panel_settings().get("custom_server_enabled")), req_lang),
            "routing": _localize_routing_state(_beginner_routing_state(
                get_routing().public_state(cur_cfg, custom_mode=True)
                if custom_active
                else get_routing().public_state()
            ), req_lang),
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
        title, text = self.tr(title), self.tr(text)
        body = (f"<div class='min-h-screen flex items-center justify-center p-6'>"
                f"<div class='max-w-md w-full bg-white rounded-2xl border p-8 shadow-sm'>"
                f"<h1 class='text-lg font-bold'>{e(title)}</h1>"
                f"<p class='text-sm text-slate-600 mt-2 mb-4'>{e(text)}</p>"
                f"<a class='inline-block px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm' href=/>{e(self.tr('返回控制台'))}</a>"
                f"</div></div>")
        self.send(code, render_spa_html(title, {"page": "error", "version": VERSION}, body))

    def session(self):
        now = time.time()
        for part in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == "cs_session":
                s = self.sessions.get(v)
                if s and s["exp"] > now:
                    return v, s
        if os.environ.get("CLASHGATE_PREVIEW") == "1":
            return "preview", {"csrf": "preview", "exp": now + SESSION_TTL}
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
                        "text/css; charset=utf-8" if fp.endswith(".css") else (
                            "image/png" if fp.endswith(".png") else (
                                "font/woff2" if fp.endswith(".woff2") else (
                                    "font/woff" if fp.endswith(".woff") else "application/octet-stream")))
                    )
                    with open(fp, "rb") as f:
                        return self.send(200, f.read(), ctype)
            return self.send(404, "not found", "text/plain")
        if path in ("/favicon.ico", "/favicon.png", "/logo.png"):
            fp = resolve_dist_file("favicon.ico" if path == "/favicon.ico" else ("assets/logo.png" if path == "/logo.png" else "favicon.png"))
            if os.path.isfile(fp):
                with open(fp, "rb") as f:
                    return self.send(200, f.read(), "image/x-icon" if fp.endswith(".ico") else "image/png",
                                     {"Cache-Control": "public, max-age=86400"})
            return self.send(404, "not found", "text/plain")
        if path == "/login":
            return self.send(200, self.login_page())
        if path.startswith("/sub/"):
            return self.do_sub(path)
        if path == "/api/cluster/hello":
            return self.do_cluster_hello()
        tok, s = self.session()
        if not s:
            return self.redirect("/login")
        if path == "/":
            return self.send(200, self.dashboard(s, initial_tab="inbounds"))
        if path in ("/outbounds",):
            return self.send(200, self.dashboard(s, initial_tab="outbounds"))
        if path in ("/routing",):
            return self.send(200, self.dashboard(s, initial_tab="routing"))
        if path in ("/readable", "/convert"):
            return self.send(200, self.dashboard(s, initial_tab="readable"))
        if path in ("/advanced", "/custom-config"):
            return self.send(200, self.dashboard(s, initial_tab="advanced"))
        if path in ("/certs", "/cert"):
            return self.send(200, self.dashboard(s, initial_tab="certs"))
        if path == "/settings":
            return self.send(200, self.dashboard(s, initial_tab="settings"))
        if path == "/cluster":
            return self.send(200, self.dashboard(s, initial_tab="cluster"))
        if path == "/api/state":
            return self.send(200, json.dumps(self.build_client_state(s), ensure_ascii=False), "application/json; charset=utf-8")
        if path == "/api/upgrade-status":
            d = load_upgrade_status()
            d["version"] = VERSION
            if d.get("state") == "done" and d.get("rc") == 0 and not d.get("recorded"):
                try:
                    record_panel_check(VERSION, False)
                    d["recorded"] = True
                    atomic_write(UPGRADE_STATUS_JSON, json.dumps(d) + "\n", 0o600)
                except Exception:
                    pass
            return self.send(200, json.dumps(d, ensure_ascii=False), "application/json; charset=utf-8")
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
            env_st = read_env()
            cert_parsed = parse_cert(st["cert"].get("info", ""))
            st["version_panel"] = VERSION
            st["mihomo_version"] = get_mihomo_version_num(st)
            st["custom_config_mode"] = is_custom_config_mode()
            st["domain"] = env_st.get("DOMAIN", "")
            st["cert_mode"] = env_st.get("CERT_MODE") or "port"
            st["cert_expires"] = cert_parsed.get("expires", "")
            st["cert_days"] = cert_parsed.get("days")
            st["cert_issuer"] = cert_parsed.get("issuer", "")
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
        if path == "/api/cluster/join":
            return self.do_cluster_join(form)
        if path == "/api/cluster/leave":
            return self.do_cluster_leave(form)
        if path == "/api/cluster/status":
            return self.do_cluster_status(form)
        if path == "/api/cluster/expect":
            return self.do_cluster_expect(form)
        if path == "/api/cluster/introduce":
            return self.do_cluster_introduce(form)
        if path == "/api/cluster/connect":
            return self.do_cluster_connect(form)
        if path == "/api/cluster/forget":
            return self.do_cluster_forget(form)
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
            forget_session(tok)
            return self.redirect("/login", "cs_session=; Max-Age=0; Path=/; HttpOnly; SameSite=Strict")
        if path in ("/action/restart", "/action/reload"):
            return self.do_action(s, path.rsplit("/", 1)[1])
        if path == "/action/discard-pending":
            return self.do_discard_pending(s)
        if path == "/action/change-password":
            return self.do_change_password(s, form)
        if path == "/action/settings":
            return self.do_settings(s, form)
        if path == "/action/masque-register":
            return self.do_masque_register(s)
        if path == "/action/update-core":
            return self.do_update_core(s, form)
        if path == "/action/check-update":
            return self.do_check_update(s)
        if path == "/action/upgrade-self":
            return self.do_upgrade_self(s)
        if path == "/action/cert":
            return self.do_cert_action(s)
        if path in ("/action/cert-mode", "/action/cert-dns"):
            return self.do_cert_mode(s, form)
        if path == "/action/reset-secret":
            return self.do_reset_secret(s)
        if path == "/action/reset-sub":
            return self.do_reset_sub(s)
        if path == "/inbounds/add":
            return self.do_add(s, form)
        if path == "/cluster/add":
            return self.do_cluster_add(s, form)
        if path == "/cluster/remove":
            return self.do_cluster_remove(s, form)
        if path == "/cluster/sync":
            return self.do_cluster_sync(s)
        if path == "/cluster/leave":
            return self.do_cluster_leave_ui(s)
        if path == "/proxies/add":
            return self.do_add_proxies(s, form)
        if path == "/proxies/delete":
            return self.do_delete_proxy(s, form.get("name", ""))
        if path == "/providers/add":
            return self.do_add_provider(s, form)
        if path == "/providers/delete":
            return self.do_delete_provider(s, form.get("name", ""))
        if path == "/routing/add":
            return self.do_routing_add(s, form)
        if path == "/routing/import":
            return self.do_routing_import(s, form)
        if path == "/routing/delete":
            return self.do_routing_delete(s, form)
        if path == "/routing/rename":
            return self.do_routing_rename(s, form)
        if path == "/routing/reorder":
            return self.do_routing_reorder(s, form)
        if path == "/routing/provider/add":
            return self.do_routing_provider(s, form, add=True)
        if path == "/routing/provider/delete":
            return self.do_routing_provider(s, form, add=False)
        if path == "/routing/update":
            return self.do_routing_update(s, form)
        if path == "/routing/rules":
            return self.do_routing_rules(s, form)
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

    def login_bucket(self) -> str:
        """Rate-limit key: the IPv4 address, or the /64 of an IPv6 one (one host rotates within it)."""
        ip = self.client_ip()
        if ip.startswith("::ffff:"):
            ip = ip[7:]
        if ":" in ip:
            try:
                import ipaddress
                return str(ipaddress.ip_network(ip + "/64", strict=False))
            except ValueError:
                pass
        return ip

    def do_login(self, form):
        ip, now = self.login_bucket(), time.time()
        with _SESSION_LOCK:
            for k in [k for k, v in self.fails.items() if not v or now - v[-1] >= LOGIN_WINDOW]:
                self.fails.pop(k, None)   # prune so the table cannot grow without bound
            recent = [t for t in self.fails.get(ip, []) if now - t < LOGIN_WINDOW]
            total = sum(len(v) for v in self.fails.values())
        if len(recent) >= LOGIN_MAX_FAILS_PER_IP or total >= LOGIN_MAX_FAILS_TOTAL:
            return self.send(429, self.login_page("尝试次数过多，请 10 分钟后再试。"))
        if self.cfg_path and os.path.isfile(self.cfg_path):
            try:
                with open(self.cfg_path) as f:
                    d = json.load(f)
                if isinstance(d, dict) and d.get("password_hash"):
                    self.cfg["password_hash"] = d["password_hash"]
            except Exception:
                pass
        user, pw = form.get("username", ""), form.get("password", "")
        if hmac.compare_digest(user, self.cfg["username"]) and verify_password(pw, self.cfg["password_hash"]):
            self.fails.pop(ip, None)
            tok = secrets.token_urlsafe(32)
            sess = {"csrf": secrets.token_urlsafe(24), "exp": now + SESSION_TTL}
            remember_session(tok, sess)
            cookie = f"cs_session={tok}; HttpOnly; SameSite=Strict; Path=/; Max-Age={SESSION_TTL}"
            if self.is_https():
                cookie += "; Secure"
            return self.redirect("/", cookie)
        recent.append(now)
        with _SESSION_LOCK:
            self.fails[ip] = recent
        self.send(401, self.login_page("用户名或密码错误。"))

    # -- cluster (集群): API called by other panels (no session; password, one-time ticket or link key)
    def _cjson(self, code: int, obj: dict):
        return self.send(code, json.dumps(obj, ensure_ascii=False), "application/json; charset=utf-8")

    def _cluster_rate_limited(self) -> bool:
        ip, now = self.login_bucket(), time.time()
        with _SESSION_LOCK:
            recent = [t for t in self.fails.get(ip, []) if now - t < LOGIN_WINDOW]
            total = sum(len([t for t in v if now - t < LOGIN_WINDOW]) for v in self.fails.values())
        return len(recent) >= LOGIN_MAX_FAILS_PER_IP or total >= LOGIN_MAX_FAILS_TOTAL

    def _cluster_note_fail(self):
        ip, now = self.login_bucket(), time.time()
        with _SESSION_LOCK:
            self.fails[ip] = [t for t in self.fails.get(ip, []) if now - t < LOGIN_WINDOW] + [now]

    def _cluster_busy_mode(self):
        if is_custom_config_mode() or load_panel_settings().get("custom_server_enabled"):
            return self._cjson(409, {"ok": False, "code": "custom_mode", "msg": "已启用自定义服务端配置，集群暂不可用"})
        return None

    def do_cluster_hello(self):
        return self._cjson(200, {"clashgate": True, "cluster": CLUSTER_PROTOCOL, "version": VERSION,
                                 "name": local_node_name(), "instance": cluster_instance_id()})

    def _cluster_link_auth(self, form):
        """(link, None) for a valid instance + key, else (None, error response sent)."""
        if self._cluster_rate_limited():
            return None, self._cjson(429, {"ok": False, "code": "rate_limited", "msg": "尝试次数过多，请 10 分钟后再试。"})
        inst, key = str(form.get("instance") or ""), str(form.get("key") or "")
        link = _link_by(load_cluster(), instance=inst) if _INST_RE.fullmatch(inst) else None
        if not link or not key or not hmac.compare_digest(key.encode(), str(link.get("key") or "").encode()):
            self._cluster_note_fail()
            return None, self._cjson(403, {"ok": False, "code": "bad_token", "msg": "集群连接凭据无效"})
        return link, None

    def do_cluster_join(self, form):
        """Another panel pairs with this one: password (user added us) or a ticket (a member vouched)."""
        if self._cluster_rate_limited():
            return self._cjson(429, {"ok": False, "code": "rate_limited", "msg": "尝试次数过多，请 10 分钟后再试。"})
        inst = str(form.get("instance") or "")
        if not _INST_RE.fullmatch(inst):
            return self._cjson(400, {"ok": False, "code": "bad_request", "msg": "集群请求参数无效"})
        ticket = str(form.get("ticket") or "")
        if ticket:
            th = hashlib.sha256(ticket.encode()).hexdigest()
            with _CLUSTER_TICKETS_LOCK:
                allowed = _CLUSTER_TICKETS.pop(th, None)
            if not allowed or allowed[0] != inst or allowed[1] < time.time():
                self._cluster_note_fail()
                return self._cjson(403, {"ok": False, "code": "bad_ticket", "msg": "集群邀请已失效，请点「检查」重试"})
        else:
            if self.cfg_path and os.path.isfile(self.cfg_path):
                try:
                    with open(self.cfg_path) as f:
                        d = json.load(f)
                    if isinstance(d, dict) and d.get("password_hash"):
                        self.cfg["password_hash"] = d["password_hash"]
                except Exception:
                    pass
            if not verify_password(str(form.get("password") or ""), self.cfg.get("password_hash", "")):
                self._cluster_note_fail()
                return self._cjson(401, {"ok": False, "code": "bad_password", "msg": "面板密码错误"})
            with _SESSION_LOCK:
                self.fails.pop(self.login_bucket(), None)
        busy = self._cluster_busy_mode()
        if busy:
            return busy
        if inst == cluster_instance_id():
            return self._cjson(400, {"ok": False, "code": "self", "msg": "不能添加本机"})
        try:
            peer_name = validate_peer_name(form.get("name"))
            url = normalize_panel_url(str(form.get("url") or ""))
            node = _parse_node(form)
            key = str(form.get("key") or "")
            assert re.fullmatch(r"[A-Za-z0-9_-]{32,128}", key)
        except (ValueError, ClusterError, AssertionError):
            return self._cjson(400, {"ok": False, "code": "bad_request", "msg": "集群请求参数无效"})
        # The other panel must be reachable at the address it announced, with a valid certificate,
        # and really be the panel that called (same instance id): only then do we write an outbound to it.
        try:
            back = cluster_hello(url)
            if back.get("instance") != inst:
                raise ClusterError("这个地址上的面板不是发起请求的面板")
        except ClusterError as e:
            return self._cjson(400, {"ok": False, "code": "unreachable_back",
                                     "msg": f"对方面板无法通过 {url} 连回发起方：{e}"})
        try:
            inb = _cluster_new_inbound()
        except Exception as e:
            return self._cjson(500, {"ok": False, "code": "apply_failed", "msg": str(e)[:300]})
        link = {"id": secrets.token_hex(6), "instance": inst, "name": peer_name, "url": url, "key": key,
                "version": str(form.get("version") or "")[:16], "created": int(time.time()), "seen": int(time.time()),
                "ok": True, "error": "", "missing": [],
                "in": {k: inb[k] for k in ("port", "uuid", "decryption")},
                "out": {"server": urlparse(url).hostname, **node}}

        def add(st):
            old = _link_by(st, instance=inst)   # the same panel joining again replaces its old link
            if peer_name in (used_proxy_names() - ({old.get("name")} if old else set())):
                raise ClusterError(f"名称「{peer_name}」在对方面板上已被出站或分流组使用，请换一个本机名称")
            st["links"] = [l for l in st["links"] if l.get("instance") != inst] + [link]
            st["pending"] = [p for p in st["pending"] if p.get("instance") != inst]
            st["removed"].pop(inst, None)
            return cluster_members_view(st, skip=inst)
        try:
            members = _cluster_commit(add)
        except ClusterError as e:
            return self._cjson(409, {"ok": False, "code": "name_clash", "msg": str(e)})
        except Exception as e:
            sys.stderr.write(f"cluster join failed: {e}\n")
            return self._cjson(500, {"ok": False, "code": "apply_failed", "msg": str(e)[:300]})
        finally:
            _CLUSTER_PORT_HOLD.discard(inb["port"])
        sys.stderr.write(f"cluster: panel '{peer_name}' linked, inbound port {inb['port']}\n")
        return self._cjson(200, {"ok": True, "version": VERSION, "name": local_node_name(),
                                 "node": {"port": inb["port"], "uuid": inb["uuid"], "flow": CLUSTER_FLOW,
                                          "encryption": inb["_enc"]},
                                 "members": members})

    def do_cluster_leave(self, form):
        """The calling panel drops its link with us: drop ours (both directions)."""
        inst = str(form.get("instance") or "")
        if not _link_by(load_cluster(), instance=inst) and not self._cluster_rate_limited():
            return self._cjson(200, {"ok": True, "gone": True})
        link, err = self._cluster_link_auth(form)
        if not link:
            return err
        try:
            _drop_links({inst})
        except Exception as e:
            return self._cjson(500, {"ok": False, "code": "apply_failed", "msg": str(e)[:300]})
        if form.get("all") == "1":
            # We were removed from the cluster: leave the remaining members too.
            threading.Thread(target=cluster_leave_all, name="cluster-leave-all", daemon=True).start()
        return self._cjson(200, {"ok": True})

    def do_cluster_status(self, form):
        link, err = self._cluster_link_auth(form)
        if not link:
            return err
        try:
            name = validate_peer_name(form.get("name"))
        except ValueError:
            name = None
        fields = {"seen": int(time.time()), "version": str(form.get("version") or link.get("version") or "")[:16]}
        _update_link(link["instance"], **fields, **({"name": name} if name else {}))
        return self._cjson(200, {"ok": True, "version": VERSION, "name": local_node_name(),
                                 "members": cluster_members_view(load_cluster(), skip=link["instance"])})

    def do_cluster_expect(self, form):
        """A member vouches for another panel: accept one pairing from it with this ticket."""
        link, err = self._cluster_link_auth(form)
        if not link:
            return err
        busy = self._cluster_busy_mode()
        if busy:
            return busy
        joiner, th = str(form.get("from_instance") or ""), str(form.get("ticket_hash") or "")
        if not _INST_RE.fullmatch(joiner) or not re.fullmatch(r"[0-9a-f]{64}", th):
            return self._cjson(400, {"ok": False, "code": "bad_request", "msg": "集群请求参数无效"})
        removed_at = load_cluster()["removed"].get(joiner)
        if removed_at:
            try:
                since = float(form.get("since") or 0)
            except ValueError:
                since = 0
            if since <= removed_at:
                return self._cjson(409, {"ok": False, "code": "left", "msg": "这个面板已被移出集群，需要用密码重新添加"})
            with LOCK:   # it was added back to the cluster after we removed it
                st = load_cluster()
                st["removed"].pop(joiner, None)
                save_cluster(st)
        now = time.time()
        with _CLUSTER_TICKETS_LOCK:
            for k in [k for k, v in _CLUSTER_TICKETS.items() if v[1] < now]:
                _CLUSTER_TICKETS.pop(k, None)
            if len(_CLUSTER_TICKETS) >= 64:
                return self._cjson(429, {"ok": False, "code": "rate_limited", "msg": "尝试次数过多，请 10 分钟后再试。"})
            _CLUSTER_TICKETS[th] = (joiner, now + CLUSTER_TICKET_TTL)
        return self._cjson(200, {"ok": True})

    def do_cluster_introduce(self, form):
        """The calling member wants a link with `target`, which we know: get it a ticket from target."""
        link, err = self._cluster_link_auth(form)
        if not link:
            return err
        target = _link_by(load_cluster(), instance=str(form.get("target") or ""))
        if not target:
            return self._cjson(404, {"ok": False, "code": "bad_request", "msg": "集群成员不存在"})
        try:
            ticket = cluster_issue_ticket(target, link)
        except ClusterError as e:
            return self._cjson(502, {"ok": False, "code": "unreachable", "msg": str(e)})
        return self._cjson(200, {"ok": True, "ticket": ticket, "url": target["url"], "name": target.get("name", ""),
                                 "instance": target["instance"]})

    def do_cluster_connect(self, form):
        """A member asks us to link with another member (it already got us a ticket there)."""
        link, err = self._cluster_link_auth(form)
        if not link:
            return err
        busy = self._cluster_busy_mode()
        if busy:
            return busy
        target = str(form.get("target_instance") or "")
        if _link_by(load_cluster(), instance=target):
            return self._cjson(200, {"ok": True, "already": True})
        try:
            url = normalize_panel_url(str(form.get("target_url") or ""))
            cluster_pair(url, {"ticket": str(form.get("ticket") or "")}, expect_instance=target)
        except ClusterError as e:
            return self._cjson(502, {"ok": False, "code": "unreachable", "msg": str(e)})
        return self._cjson(200, {"ok": True})

    def do_cluster_forget(self, form):
        """A member removed `target` from the cluster: drop our link with it and tell it (best effort)."""
        link, err = self._cluster_link_auth(form)
        if not link:
            return err
        target = str(form.get("target") or "")
        if not _INST_RE.fullmatch(target) or target == cluster_instance_id():
            return self._cjson(400, {"ok": False, "code": "bad_request", "msg": "集群请求参数无效"})
        gone = _link_by(load_cluster(), instance=target)
        try:
            _drop_links({target}, tombstone=True)
        except Exception as e:
            return self._cjson(500, {"ok": False, "code": "apply_failed", "msg": str(e)[:300]})
        if gone:
            try:
                cluster_call(gone, "/api/cluster/leave", {"all": "1"}, timeout=20)
            except ClusterError:
                pass
        return self._cjson(200, {"ok": True})

    # -- cluster: this panel's own page (session + CSRF)
    def _cluster_locked(self) -> bool:
        return is_custom_config_mode() or bool(load_panel_settings().get("custom_server_enabled"))

    def _cluster_job(self, s, job):
        if self._cluster_locked():
            return self.respond_mutation(s, "已启用自定义服务端配置，集群暂不可用", False)
        if not _CLUSTER_OP_LOCK.acquire(blocking=False):
            return self.respond_mutation(s, "另一个集群操作正在进行，请稍候再试", False)
        try:
            msg, ok = job()
        except (ClusterError, ValueError) as e:
            msg, ok = str(e), False
        except Exception as e:   # never drop the connection on an unexpected error
            sys.stderr.write(f"cluster job failed: {e!r}\n")
            msg, ok = f"集群操作失败：{e}", False
        finally:
            _CLUSTER_OP_LOCK.release()
        return self.respond_mutation(s, msg, ok)

    def do_cluster_add(self, s, form):
        def job():
            base = normalize_panel_url(form.get("url", ""))
            pw = str(form.get("password") or "")
            if not pw:
                raise ClusterError("请填写对方面板密码")
            link, _ = cluster_pair(base, {"password": pw})
            rep = cluster_sync()
            msg = f"已和「{link['name']}」双向互联，双方都已把对方写入服务端出站并立即生效"
            extra = cluster_report_text(rep)
            return (f"{msg}；{extra}" if extra else msg), True
        return self._cluster_job(s, job)

    def do_cluster_sync(self, s):
        def job():
            if not load_cluster()["links"]:
                return "集群里还没有其他面板", True
            rep = cluster_sync()
            return cluster_report_text(rep) or "集群成员都在线，互联完整", True
        return self._cluster_job(s, job)

    def do_cluster_remove(self, s, form):
        def job():
            st = load_cluster()
            x = _link_by(st, lid=str(form.get("id") or ""))
            if not x:
                return "集群成员不存在", False
            others = [l for l in st["links"] if l["instance"] != x["instance"]]
            _drop_links({x["instance"]}, tombstone=True)
            missed = []
            for y in others:
                try:
                    cluster_call(y, "/api/cluster/forget", {"target": x["instance"]}, timeout=40)
                except ClusterError:
                    missed.append(y.get("name", ""))
            try:
                cluster_call(x, "/api/cluster/leave", {"all": "1"}, timeout=30)
            except ClusterError:
                missed.append(x.get("name", ""))
            name = x.get("name", "")
            if missed:
                return f"已把「{name}」移出集群；「{'、'.join(missed)}」暂时联系不上，恢复后在任意成员上点「检查」会自动清理", True
            return f"已把「{name}」移出集群，所有成员上和它的互联都已删除", True
        return self._cluster_job(s, job)

    def do_cluster_leave_ui(self, s):
        def job():
            n, missed = cluster_leave_all()
            if not n:
                return "本机不在集群里", True
            if missed:
                return f"本机已退出集群；「{'、'.join(missed)}」暂时联系不上，恢复后在它们上面点「检查」会自动删除和本机的互联", True
            return "本机已退出集群，其他成员上和本机的互联都已删除", True
        return self._cluster_job(s, job)

    def do_discard_pending(self, s):
        with LOCK:
            try:
                discard_pending_reload()
            except Exception as e:
                return self.respond_mutation(s, f"丢弃草稿失败：{e}", False)
        run_snell_migration()
        return self.respond_mutation(s, "已丢弃待重载草稿", True)

    def do_settings(self, s, form):
        if "node_name" in form:
            try:
                name = validate_node_name(form.get("node_name"))
                with LOCK:
                    save_panel_settings({"node_name": name})
            except ValueError as e:
                return self.respond_mutation(s, str(e), False)
            if load_cluster()["links"]:
                cluster_push_name_async()
                return self.respond_mutation(s, f"本机名称已保存为「{name}」，正在通知其他集群成员", True)
            return self.respond_mutation(s, f"本机名称已保存为「{name}」", True)
        updates = {}
        channel_raw = (form.get("update_channel") or "").strip()
        for key in ("custom_server_enabled", "auto_update"):
            if key not in form:
                continue
            raw = (form.get(key) or "").strip().lower()
            if raw not in ("0", "1", "false", "true", "on", "off"):
                return self.respond_mutation(s, "设置项无效", False)
            updates[key] = raw in ("1", "true", "on")
        if channel_raw:
            ch = _normalize_update_channel(channel_raw)
            if ch not in UPDATE_CHANNEL_MAP:
                return self.respond_mutation(s, "设置项无效", False)
            updates["update_channel"] = ch
        if not updates:
            return self.respond_mutation(s, "设置项无效", False)
        with LOCK:
            if updates.get("custom_server_enabled") is False and is_custom_config_mode():
                try:
                    used = disable_custom_config()
                    clear_pending_reload()
                except Exception as e:
                    return self.respond_mutation(s, f"切换回默认服务端模板失败：{e}", False)
                save_panel_settings({"custom_server_enabled": False})
                updates.pop("custom_server_enabled")
                if not updates:
                    if used == "reset":
                        return self.respond_mutation(s, "已关闭自定义服务端。原有节点无法用默认模板生成，已重置为默认服务端模板并生成新的 VlessReality 节点，请在客户端更新订阅。", True)
                    return self.respond_mutation(s, "已关闭自定义服务端，已切换回默认服务端模板并重载生效。", True)
            if "update_channel" in updates:
                apply_update_channel_env(updates["update_channel"])
                # Keep other toggles if sent together.
                other = {k: updates[k] for k in ("custom_server_enabled", "auto_update") if k in updates}
                if other:
                    save_panel_settings(other)
            else:
                save_panel_settings(updates)
        if "update_channel" in updates and len(updates) == 1:
            if updates["update_channel"] == "test":
                msg = "已切换到测试通道，请点「检查更新」。"
            else:
                msg = "已切换到正式通道，请点「检查更新」。"
            return self.respond_mutation(s, msg, True)
        if "auto_update" in updates and len(updates) == 1:
            if updates["auto_update"]:
                return self.respond_mutation(s, "已开启每周自动更新。更新面板时会同时更新 Mihomo 内核。", True)
            return self.respond_mutation(s, "已关闭每周自动更新。", True)
        if updates.get("custom_server_enabled"):
            if not is_custom_config_mode() and os.path.isfile(CUSTOM_SAVED):
                return self.respond_mutation(s, "已开启自定义服务端。上次的自定义配置已载入编辑框，点「更新 Mihomo 服务端配置」即可恢复。", True)
            return self.respond_mutation(s, "已开启自定义服务端。", True)
        if "custom_server_enabled" in updates:
            return self.respond_mutation(s, "已关闭自定义服务端。", True)
        return self.respond_mutation(s, "设置已保存。", True)

    def do_masque_register(self, s):
        start_masque_registrar(force=True)
        return self.respond_mutation(s, "正在向 Cloudflare 注册 MASQUE，完成后点「加入服务端出站」。", True)

    def do_change_password(self, s, form):
        cur_pw = form.get("current_password", "")
        new_pw = form.get("new_password", "")
        confirm_pw = form.get("confirm_password", "")
        with LOCK:
            disk_cfg = dict(self.cfg)
            cfg_file = self.cfg_path or (CS_ROOT + "/panel.json" if os.path.isfile(CS_ROOT + "/panel.json") else "")
            if cfg_file and os.path.isfile(cfg_file):
                try:
                    with open(cfg_file) as f:
                        loaded = json.load(f)
                    if isinstance(loaded, dict):
                        disk_cfg.update(loaded)
                        self.cfg.update(loaded)
                except Exception:
                    pass
            if not cur_pw or not verify_password(cur_pw, disk_cfg.get("password_hash", "")):
                return self.respond_mutation(s, "当前密码错误", False)
            if len(new_pw) < 8:
                return self.respond_mutation(s, "新密码长度至少 8 位", False)
            if confirm_pw and new_pw != confirm_pw:
                return self.respond_mutation(s, "两次输入的新密码不一致", False)
            new_hash = hash_password(new_pw)
            self.cfg["password_hash"] = new_hash
            disk_cfg["password_hash"] = new_hash
            if cfg_file:
                atomic_write(cfg_file, json.dumps(disk_cfg, indent=2, ensure_ascii=False) + "\n", 0o600)
        revoke_other_sessions(self.session()[0])
        return self.respond_mutation(s, "面板密码已修改", True)

    def do_action(self, s, action):
        global _PENDING_UFW_BASELINE
        zh = {"restart": "重启", "reload": "重载"}[action]
        with LOCK:
            pending_st = load_pending_reload()
            if pending_st.get("mihomo_secret"):
                new_secret = pending_st["mihomo_secret"]
                write_env_var("MIHOMO_SECRET", new_secret)
                env = read_env()
                atomic_write(FRAG_CONTROLLER, render_controller_fragment(env), 0o640)
                if is_custom_config_mode():
                    try:
                        with open(CUSTOM_CONF) as f:
                            raw_c = f.read()
                        updated_c = re.sub(r'^(\s*secret\s*:\s*).*$', f'\\1"{new_secret}"', raw_c, flags=re.M)
                        atomic_write(CUSTOM_CONF, updated_c, 0o640)
                    except FileNotFoundError:
                        pass
            if pending_st.get("sub_token"):
                new_token = pending_st["sub_token"]
                self.cfg["sub_token"] = new_token
                if self.cfg_path:
                    try:
                        with open(self.cfg_path) as f:
                            disk_cfg = json.load(f)
                    except Exception:
                        disk_cfg = dict(self.cfg)
                    disk_cfg["sub_token"] = new_token
                    atomic_write(self.cfg_path, json.dumps(disk_cfg, indent=2, ensure_ascii=False) + "\n", 0o600)
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
            conf_backup = None
            custom_backup = None
            try:
                with open(CONF) as f:
                    conf_backup = f.read()
            except FileNotFoundError:
                conf_backup = None
            if is_custom_config_mode():
                try:
                    with open(CUSTOM_CONF) as f:
                        custom_backup = f.read()
                except FileNotFoundError:
                    custom_backup = None
            try:
                get_routing().ensure_seeded()
                get_routing().regenerate_frags()
            except Exception as e:
                return self.respond_mutation(s, f"分流配置组装失败：{e}", False)
            atomic_write(CONF, assemble_config(), 0o640)
            rc, out = validate_config()
            if rc != 0:
                if conf_backup is not None:
                    atomic_write(CONF, conf_backup, 0o640)
                if custom_backup is not None:
                    atomic_write(CUSTOM_CONF, custom_backup, 0o640)
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
            if rc != 0:
                if conf_backup is not None:
                    atomic_write(CONF, conf_backup, 0o640)
                if custom_backup is not None:
                    atomic_write(CUSTOM_CONF, custom_backup, 0o640)
                run([SYSTEMCTL, "restart", "mihomo"])
            if rc == 0:
                clear_pending_reload()
                sync_client_files()
                wait_mihomo_ports()
        if rc == 0:
            run_snell_migration()
        _, active = run([SYSTEMCTL, "is-active", "mihomo"])
        state = STATE_ZH.get(active.strip(), (active.strip(), ""))[0]
        if rc == 0:
            return self.respond_mutation(s, f"{zh}成功，服务端配置与客户端订阅已同步生效（Mihomo 当前状态：{state}）", active.strip() == "active")
        return self.respond_mutation(s, f"{zh}失败：{out[-300:]}（Mihomo 当前状态：{state}）", False)

    def do_reset_sub(self, s):
        new_token = secrets.token_hex(24)
        with LOCK:
            _ensure_pending_baseline()
            record_pending_reload(
                op="reset-sub",
                kind="sub",
                name="sub",
                detail="~ 更换订阅链接",
                sub_token=new_token,
            )
        return self.respond_mutation(s, "已记录更换订阅链接，请点顶部「重载配置」生效（重载后旧订阅链接失效）。", True)

    def do_reset_secret(self, s):
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
        new_secret = "".join(secrets.choice(alphabet) for _ in range(20))
        with LOCK:
            try:
                _ensure_pending_baseline()
                env = read_env()
                env_draft = dict(env)
                env_draft["MIHOMO_SECRET"] = new_secret
                atomic_write(FRAG_CONTROLLER, render_controller_fragment(env_draft), 0o640)
                record_pending_reload(
                    op="reset-secret",
                    kind="secret",
                    name="secret",
                    detail="~ 重置 API 密钥",
                    mihomo_secret=new_secret,
                )
            except Exception as e:
                return self.respond_mutation(s, f"重置密钥失败：{e}", False)
        return self.respond_mutation(s, "已生成新 Zashboard API 密钥，请点顶部「重载配置」生效（重载后直连地址才会更新）。", True)

    def do_cert_action(self, s):
        with LOCK:
            env = read_env()
            rc, out = run([resolve_certctl_path(), "renew"], timeout=180)
            tok = env.get("CF_TOKEN", "")
            if tok:
                out = out.replace(tok, "***")
        if rc == 0:
            return self.respond_mutation(s, "证书检查 / 续期完成。", True)
        tail = " | ".join(l for l in out.splitlines() if l.strip())[-300:]
        return self.respond_mutation(s, f"证书申请 / 续期失败：{tail}", False)

    def do_cert_mode(self, s, form):
        mode = (form.get("cert_mode") or "dns").strip()
        if mode not in ("dns", "port"):
            return self.respond_mutation(s, "不支持的证书模式", False)
        raw_token = (form.get("cf_token") if "cf_token" in form else form.get("token", "")).strip()
        if mode == "dns":
            if not raw_token:
                return self.respond_mutation(s, "请输入 Cloudflare API Token", False)
            if re.search(r'[\s"\'`$\\]', raw_token):
                return self.respond_mutation(s, "API Token 不能包含空格或引号", False)
        with LOCK:
            env = read_env()
            prev_mode = (env.get("CERT_MODE") or "port").strip()
            prev_token = env.get("CF_TOKEN", "")
            if mode == prev_mode and (mode != "dns" or raw_token == prev_token):
                return self.respond_mutation(s, "未切换证书模式，未重新生成证书。", False)
            if mode == "dns":
                write_env_var("CERT_MODE", "dns")
                write_env_var("CF_TOKEN", raw_token)
            else:
                write_env_var("CERT_MODE", "port")
            rc, out = run([resolve_certctl_path(), "reissue"], timeout=180)
            if raw_token:
                out = out.replace(raw_token, "***")
            if rc != 0:
                write_env_var("CERT_MODE", prev_mode or "port")
                if prev_mode == "dns" and prev_token:
                    write_env_var("CF_TOKEN", prev_token)
                return self.respond_mutation(s, cert_failure_message(out, mode), False)
        return self.respond_mutation(s, "已切换并重新生成证书。", True)

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
            tip = check_panel_update()
            latest_cs = tip["version"]
            cur_cs = VERSION
            target = resolve_update_target()
            has_update = tip["has_update"]
            ch_label = target.get("label") or ("测试" if target["channel"] == "test" else "正式")
            if has_update:
                msg = f"发现新版本 v{latest_cs}（当前 v{cur_cs}，通道：{ch_label}"
                if re.fullmatch(r"[0-9a-f]{7,40}", tip.get("sha") or ""):
                    msg += f"，{tip['sha'][:7]}"
                msg += "）"
            else:
                msg = f"当前已是最新版本（v{cur_cs}，通道：{ch_label}）"
            payload = {
                "ok": True,
                "has_update": has_update,
                "current_version": cur_cs,
                "latest_version": latest_cs,
                "update_channel": target["channel"],
                "update_channel_label": ch_label,
                "repo": tip.get("slug") or target["slug"],
                "branch": tip.get("branch") or target["branch"],
                "latest_sha": tip.get("sha") or "",
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
        """Start `clashgate update` detached and answer immediately.

        The update restarts the clashgate (panel) service itself, so running it
        inside the request killed the handler before any response was sent and
        the UI hung. Now it runs in its own transient unit (outside our cgroup);
        the client polls /api/upgrade-status and the restarted panel.
        """
        cmd_bin = CLASHGATE_BIN if os.path.isfile(CLASHGATE_BIN) else "/usr/local/bin/clashgate"
        if not os.path.isfile(cmd_bin):
            return self.respond_mutation(s, "升级失败：未找到 clashgate 管理脚本", False)
        with LOCK:
            cur = load_upgrade_status()
            if cur.get("state") == "running" and time.time() - float(cur.get("started_at") or 0) < 600:
                return self.respond_mutation(s, "升级正在进行中，请稍候……", True)
            err = start_upgrade_job(cmd_bin)
        if err:
            return self.respond_mutation(s, f"升级失败：{err}", False)
        return self.respond_mutation(s, "已开始升级，完成后面板会自动重启并刷新（约 1 分钟）……", True)

    def do_add(self, s, form):
        env = read_env()
        req_id = (form.get("req_id") or "").strip()
        raw_kind = (form.get("kind") or "").strip()
        if raw_kind == "shadowqiuc":
            raw_kind = "shadowquic"
        elif raw_kind == "soduku":
            raw_kind = "sudoku"
        raw_name = (form.get("name") or "").strip()
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
                record_pending_reload(
                    op="add",
                    kind=inb["kind"],
                    name=inb["name"],
                    port=inb["port"],
                    detail=f"+ 添加节点「{inb['name']}」（端口 {inb['port']}）",
                )
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
            removed = [i for i in cur if i["id"] == iid]
            new = [i for i in cur if i["id"] != iid]
            if len(new) == len(cur):
                return self.respond_mutation(s, "节点删除成功，重载配置生效", True)
            try:
                save_inbounds(new)
                for rm in removed:
                    record_pending_reload(
                        op="delete",
                        kind=rm.get("kind", ""),
                        name=rm["name"],
                        port=rm.get("port"),
                        detail=f"- 删除节点「{rm['name']}」",
                    )
            except Exception as e:
                return self.respond_mutation(s, f"删除失败：{e}", False)
        return self.respond_mutation(s, "节点删除成功，重载配置生效", True)

    def do_delete_node(self, s, name):
        with LOCK:
            _RECENT_ADD_REQS.clear()
            cur = read_nodes()
            removed = [n for n in cur if n["name"] == name]
            new = [n for n in cur if n["name"] != name]
            if len(new) == len(cur):
                return self.respond_mutation(s, "已删除", True)
            try:
                save_nodes(new)
                for rm in removed:
                    record_pending_reload(
                        op="delete",
                        kind="vless-reality",
                        name=rm["name"],
                        port=rm.get("port"),
                        detail=f"- 删除节点「{rm['name']}」",
                    )
            except Exception as e:
                return self.respond_mutation(s, f"删除失败：{e}", False)
        return self.respond_mutation(s, f"已删除节点「{name}」，请点顶部「重载配置」生效", True)

    def do_reset_node_password(self, s, name):
        with LOCK:
            cur = read_nodes()
            found = False
            found_port = None
            new_nodes = []
            try:
                for n in cur:
                    if n["name"] == name:
                        found = True
                        found_port = n.get("port")
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
                save_nodes(new_nodes)
                record_pending_reload(
                    op="reset-password",
                    kind="vless-reality",
                    name=name,
                    port=found_port,
                    detail=f"~ 重置密码「{name}」",
                )
            except Exception as e:
                return self.respond_mutation(s, f"重置密钥失败：{e}", False)
        return self.respond_mutation(s, f"已重置节点「{name}」的 UUID、Reality 私钥与 VLESS 加密密钥，重载配置生效", True)

    def do_reset_inbound_password(self, s, iid):
        with LOCK:
            cur = load_inbounds()
            target_name = ""
            target_kind = ""
            target_port = None
            new_inbs = []
            try:
                for i in cur:
                    if i["id"] == iid:
                        if not can_reset_inbound_password(i):
                            return self.respond_mutation(s, "该入站协议无需密码，不支持重置密码", False)
                        target_name = i["name"]
                        target_kind = i["kind"]
                        target_port = i.get("port")
                        i = rotate_inbound_credentials(i)
                    new_inbs.append(i)
                if not target_name:
                    return self.respond_mutation(s, "入站节点不存在", False)
                save_inbounds(new_inbs)
                record_pending_reload(
                    op="reset-password",
                    kind=target_kind,
                    name=target_name,
                    port=target_port,
                    detail=f"~ 重置密码「{target_name}」",
                )
            except Exception as e:
                return self.respond_mutation(s, f"重置密码失败：{e}", False)
        return self.respond_mutation(s, "密码重置成功，重载配置生效", True)

    def do_add_proxies(self, s, form):
        raw = form.get("proxies_raw", "")
        with LOCK:
            try:
                added = parse_mihomo_proxies(raw)
                taken = cluster_proxy_names()
                for p in added:
                    if p["name"] in taken:
                        raise ValueError(f"名称「{p['name']}」已被集群成员使用，请换一个名字")
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
                for p in added:
                    record_pending_reload(
                        op="add-proxy",
                        kind="proxy",
                        name=p["name"],
                        port=p.get("port"),
                        detail=f"+ 添加服务端出站「{p['name']}」",
                    )
            except Exception as e:
                return self.respond_mutation(s, f"添加服务端 proxies 节点失败：{e}", False)
        names = "、".join(p["name"] for p in added)
        return self.respond_mutation(s, f"已添加 {len(added)} 个服务端出站（{names}），已保存，请点顶部「重载配置」生效", True)

    def do_delete_proxy(self, s, name):
        with LOCK:
            cur = load_server_proxies()
            new = [p for p in cur if p["name"] != name]
            if len(new) == len(cur):
                return self.respond_mutation(s, "已删除", True)
            try:
                save_server_proxies(new)
                record_pending_reload(
                    op="delete-proxy",
                    kind="proxy",
                    name=name,
                    detail=f"- 删除服务端出站「{name}」",
                )
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
                record_pending_reload(
                    op="add-provider",
                    kind="provider",
                    name=prov_name,
                    detail=f"+ 导入订阅源「{prov_name}」",
                )
            except Exception as e:
                return self.respond_mutation(s, f"导入订阅链接失败：{e}", False)
        return self.respond_mutation(
            s, f"已导入订阅源「{prov_name}」（路径 {entry['path']}），已保存，请点顶部「重载配置」生效", True)

    def do_delete_provider(self, s, name):
        with LOCK:
            cur = load_proxy_providers()
            if name not in cur:
                return self.respond_mutation(s, "已删除", True)
            merged = {k: v for k, v in cur.items() if k != name}
            try:
                save_proxy_providers(merged)
                record_pending_reload(
                    op="delete-provider",
                    kind="provider",
                    name=name,
                    detail=f"- 删除订阅源「{name}」",
                )
            except Exception as e:
                return self.respond_mutation(s, f"删除订阅源失败：{e}", False)
        return self.respond_mutation(s, f"已删除订阅源「{name}」，请点顶部「重载配置」生效", True)


    def do_routing_add(self, s, form):
        name = (form.get("name") or "").strip()
        rules_raw = form.get("rules_raw", "")
        yaml_raw = form.get("yaml_raw", "")
        if not name:
            return self.respond_mutation(s, "请填写分流组名称", False)
        if not (rules_raw or "").strip() and not (yaml_raw or "").strip():
            return self.respond_mutation(s, "请粘贴至少一条分流规则（如 - DOMAIN-SUFFIX,example.com）", False)
        with LOCK:
            try:
                _ensure_pending_baseline()
                entry = get_routing().add_group(name=name, rules_raw=rules_raw, yaml_raw=yaml_raw)
                record_pending_reload(
                    op="add-routing",
                    kind="routing",
                    name=entry["name"],
                    detail=f"+ 添加分流组「{entry['name']}」",
                )
            except Exception as e:
                return self.respond_mutation(s, f"添加分流组失败：{e}", False)
        return self.respond_mutation(s, f"已添加分流组「{entry['name']}」，已保存，请点顶部「重载配置」生效", True)

    def do_routing_import(self, s, form):
        name = (form.get("name") or "").strip()
        url = (form.get("url") or "").strip()
        if not name:
            return self.respond_mutation(s, "请填写分流组名称", False)
        if not url:
            return self.respond_mutation(s, "请填写外部规则集 URL", False)
        with LOCK:
            try:
                _ensure_pending_baseline()
                entry = get_routing().import_group(name=name, url=url)
                record_pending_reload(
                    op="import-routing",
                    kind="routing",
                    name=entry["name"],
                    detail=f"+ 引入分流组「{entry['name']}」",
                )
            except Exception as e:
                return self.respond_mutation(s, f"引入分流规则失败：{e}", False)
        return self.respond_mutation(s, f"已引入分流组「{entry['name']}」，已保存，请点顶部「重载配置」生效", True)

    def do_routing_delete(self, s, form):
        gid = (form.get("id") or "").strip()
        with LOCK:
            try:
                _ensure_pending_baseline()
                name = get_routing().delete_group(gid)
                if not name:
                    return self.respond_mutation(s, "已删除", True)
                record_pending_reload(
                    op="delete-routing",
                    kind="routing",
                    name=name,
                    detail=f"- 删除分流组「{name}」",
                )
            except Exception as e:
                return self.respond_mutation(s, f"删除分流组失败：{e}", False)
        return self.respond_mutation(s, f"已删除分流组「{name}」，请点顶部「重载配置」生效", True)

    def do_routing_rename(self, s, form):
        gid = (form.get("id") or "").strip()
        new_name = (form.get("name") or "").strip()
        with LOCK:
            try:
                _ensure_pending_baseline()
                old_name, new_name = get_routing().rename_group(gid, new_name)
                if old_name != new_name:
                    record_pending_reload(
                        op="rename-routing",
                        kind="routing",
                        name=new_name,
                        detail=f"~ 重命名分流组「{old_name}」→「{new_name}」",
                    )
            except Exception as e:
                return self.respond_mutation(s, f"重命名分流组失败：{e}", False)
        return self.respond_mutation(s, f"已重命名分流组为「{new_name}」，请点顶部「重载配置」生效", True)

    def do_routing_provider(self, s, form, add: bool):
        gid = (form.get("id") or "").strip()
        pname = (form.get("provider") or "").strip()
        with LOCK:
            try:
                if is_custom_config_mode():
                    raise ValueError("自定义配置模式下请在自定义服务端里修改")
                _ensure_pending_baseline()
                if add:
                    gname = get_routing().add_provider(
                        gid, pname, form.get("url") or "",
                        "classical",
                        "yaml",
                    )
                    detail = f"+ 分流组「{gname}」添加规则集「{pname}」"
                else:
                    gname = get_routing().delete_provider(gid, pname)
                    detail = f"- 分流组「{gname}」删除规则集「{pname}」"
                record_pending_reload(op="update-routing", kind="routing", name=gname, detail=detail)
            except Exception as e:
                return self.respond_mutation(s, f"修改规则集失败：{e}", False)
        return self.respond_mutation(s, f"{detail.lstrip('+- ')}，请点顶部「重载配置」生效", True)

    def do_routing_reorder(self, s, form):
        raw = (form.get("order") or "").strip()
        with LOCK:
            try:
                if raw.startswith("["):
                    order = json.loads(raw)
                else:
                    order = [x for x in raw.split(",") if x.strip()]
                if not isinstance(order, list):
                    raise ValueError("order 必须是数组")
                order = [str(x).strip() for x in order if str(x).strip()]
                _ensure_pending_baseline()
                get_routing().reorder_groups(order)
                record_pending_reload(
                    op="reorder-routing",
                    kind="routing",
                    name="order",
                    detail="~ 调整分流顺序",
                )
            except Exception as e:
                return self.respond_mutation(s, f"调整分流顺序失败：{e}", False)
        return self.respond_mutation(s, "已调整分流顺序，请点顶部「重载配置」生效", True)

    def do_routing_rules(self, s, form):
        gid = (form.get("id") or "").strip()
        rules_raw = form.get("rules_raw", "")
        if not gid:
            return self.respond_mutation(s, "缺少分流组 id", False)
        with LOCK:
            try:
                if is_custom_config_mode():
                    raise ValueError("自定义配置模式下请在自定义服务端里修改")
                _ensure_pending_baseline()
                name = get_routing().update_group_rules(gid, rules_raw)
                record_pending_reload(
                    op="update-routing",
                    kind="routing",
                    name=name,
                    detail=f"~ 更新分流组「{name}」规则",
                )
            except Exception as e:
                return self.respond_mutation(s, f"更新分流规则失败：{e}", False)
        return self.respond_mutation(s, f"已更新分流组「{name}」规则，请点顶部「重载配置」生效", True)

    def do_routing_update(self, s, form):
        gid = (form.get("id") or "").strip()
        yaml_raw = form.get("yaml_raw", "")
        with LOCK:
            try:
                if is_custom_config_mode():
                    # Custom mode: rewrite sections in CUSTOM_CONF from provided group yaml
                    _ensure_pending_baseline()
                    with open(CUSTOM_CONF) as f:
                        raw = f.read()
                    # Merge: update one group's yaml inside synthetic list then rewrite
                    st = get_routing().public_state(raw, custom_mode=True)
                    if not st.get("ok"):
                        raise ValueError(st.get("error") or "自定义分流无法解析")
                    groups = st.get("groups") or []
                    found = False
                    for g in groups:
                        if g.get("id") == gid:
                            g["yaml"] = yaml_raw
                            found = True
                            break
                    if not found:
                        raise ValueError("分流组不存在")
                    updated = get_routing().apply_custom_routing_edit(
                        raw, groups, rule_providers_yaml=st.get("rule_providers_yaml") or ""
                    )
                    atomic_write(CUSTOM_CONF, updated, 0o640)
                    name = next((g.get("name") for g in groups if g.get("id") == gid), gid)
                else:
                    _ensure_pending_baseline()
                    name = get_routing().update_group_yaml(gid, yaml_raw)
                record_pending_reload(
                    op="update-routing",
                    kind="routing",
                    name=name,
                    detail=f"~ 更新分流组「{name}」",
                )
            except Exception as e:
                return self.respond_mutation(s, f"更新分流组失败：{e}", False)
        return self.respond_mutation(s, f"已更新分流组「{name}」，请点顶部「重载配置」生效", True)

    def do_save_custom_config(self, s, form):
        if not load_panel_settings().get("custom_server_enabled"):
            return self.respond_mutation(s, "高级功能请到设置页开启", False)
        raw = form.get("custom_config_raw", "")
        auto_fix = form.get("auto_fix_certs") == "1"
        fixed = 0
        with LOCK:
            try:
                env = read_env()
                if auto_fix:
                    raw, fixed = rewrite_cert_paths_in_yaml(raw, env)
                apply_custom_config(raw)
                clear_pending_reload()
            except Exception as e:
                return self.respond_mutation(s, f"更新自定义服务端配置失败：{e}", False)
        if fixed:
            return self.respond_mutation(s, f"已自动配置 {fixed} 处证书路径，自定义 Mihomo 服务端配置已通过校验并应用生效。", True)
        return self.respond_mutation(s, "自定义 Mihomo 服务端配置已通过校验并应用生效。", True)

    def do_reset_template_config(self, s):
        if not load_panel_settings().get("custom_server_enabled"):
            return self.respond_mutation(s, "高级功能请到设置页开启", False)
        with LOCK:
            try:
                reset_to_template_config()
                clear_pending_reload()
            except Exception as e:
                return self.respond_mutation(s, f"恢复默认配置失败：{e}", False)
        return self.respond_mutation(s, "已恢复默认服务端配置，并生成默认 VlessReality 节点。", True)

    # -- views
    def login_page(self, err=""):
        e = html.escape
        err = self.tr(err)
        mver = get_mihomo_version_num()
        boot = {"page": "login", "version": VERSION, "mihomo_version": mver, "login_error": err}
        err_html = f"<div class=err>{e(err)}</div>" if err else ""
        fallback = (
            f"<div><h1>ClashGate <span>v{VERSION}</span></h1>{err_html}"
            f"<form method=post action=/login>"
            f"<input id=u name=username value=admin required>"
            f"<input id=p name=password type=password required>"
            f"<button type=submit>{e(self.tr('登 录'))}</button></form></div>"
        )
        return render_spa_html(self.tr("登录 · ClashGate"), boot, fallback)

    def dashboard(self, s, initial_tab="inbounds"):
        q = parse_qs(urlparse(self.path).query)
        msg, ok = q.get("msg", [""])[0], q.get("ok", ["1"])[0] == "1"
        tab_q = q.get("tab", [""])[0]
        if tab_q in ("inbounds", "outbounds", "readable", "advanced", "certs", "settings", "cluster"):
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
            f"<div id=zb-url>••••••••••••••••••••••••</div>"
            f"<div id=zb-secret>••••••••••••</div>"
            f"<a href='{e(state['zb_url'] or '#')}' target=_blank rel=noopener>打开 Zashboard</a>"
            f"<button type=button>复制地址</button>"
            f"<form method=post action=/action/reset-secret>{hid}<button type=submit>重置 API 密钥</button></form></section>"
        )
        sub_sec = (
            f"<section id=sub-card><h2>客户端订阅链接</h2>"
            f"<div id=sub-url>••••••••••••••••••••••••</div>"
            f"<button type=button>复制订阅链接</button>"
            f"<button type=button>二维码</button>"
            f"<form method=post action=/action/reset-sub>{hid}<button type=submit>更换订阅链接</button></form></section>"
            if state["sub_url"] else ""
        )
        cert_sec = (
            f"<section id=certs-card><h2>HTTPS 证书</h2>"
            f"<div><span>{e(state.get('domain') or '—')}</span>"
            f"<span>{e(state.get('cert_mode') or 'port')}</span>"
            f"<span>{e(state.get('cert_issuer') or '—')}</span>"
            f"<span>{e(state.get('cert_expires') or '—')}</span></div>"
            f"<form method=post action=/action/cert-mode>{hid}"
            f"<input type=hidden name=cert_mode value=dns>"
            f"<input id=cf-token name=cf_token type=password placeholder='Cloudflare API Token'>"
            f"<button type=submit>切换并重新生成证书</button></form>"
            f"<a href='https://dash.cloudflare.com/profile/api-tokens' target=_blank rel=noopener>https://dash.cloudflare.com/profile/api-tokens</a>"
            f"</section>"
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
            f"<button type=submit>添加入站节点</button></form></section>"
            f"<section><h2>自定义 Mihomo 服务端配置</h2>"
            f"<form method=post action=/config/reset-template>{hid}<button type=submit>恢复默认服务端模板</button></form></section>"
            f"{cert_sec}</main>"
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
    Panel.sessions = _load_sessions_file()
    cluster_instance_id()   # create it before any request can race for it
    start_traffic_poller(30)
    refresh_update_check_for_version()
    start_weekly_update_check()
    threading.Thread(target=run_snell_migration, name="snell-v6-migration", daemon=True).start()
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


cg_cluster.bind()
cg_update.bind()

if __name__ == "__main__":
    main()
