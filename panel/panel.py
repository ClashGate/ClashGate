#!/usr/bin/env python3
"""ClashGate v1.38 - admin console (Vue 3 + Tailwind CSS).

Stdlib only (Python 3). Serves HTTPS itself with the same certificate
Mihomo uses (/etc/clashgate/certs); no reverse proxy.
Unified directory layout under /etc/clashgate.

Subcommands:
  panel.py hash-password            read password on stdin, print hash
  panel.py cluster-leave            leave the cluster (used by uninstall)
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
# `python3 panel.py serve` loads this file as __main__. scripts/lib/core.sh
# seed_routing loads it via importlib as cg_panel_seed (and historically did
# not pre-register that name in sys.modules). Later modules bind() from
# sys.modules["panel"] or do `import panel` and must get this same module,
# not a second copy.
if __name__ != "panel":
    _mod = sys.modules.get(__name__)
    if _mod is None:
        import gc as _gc
        import types as _types
        _g = globals()
        _mod = next((obj for obj in _gc.get_referrers(_g)
                     if isinstance(obj, _types.ModuleType) and obj.__dict__ is _g), None)
        del _gc, _types, _g
        if _mod is None:
            raise RuntimeError("clashgate: cannot identify the panel module")
    sys.modules.setdefault(__name__, _mod)
    sys.modules.setdefault("panel", _mod)
    del _mod

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
    ManualCertError,
    check_manual_cert,
    install_manual_cert,
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
    custom_conf_with_cluster,
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

# Versions compare as integer tuples (parse_version_tuple): 1.38 > 1.37 > 1.36 > 1.35 > 1.34 > 1.33 > 1.32 > 1.31 > 1.30 > 1.29 > 1.28 > 1.27 > 1.26 > 1.25 > 1.24 > 1.23 > 1.22 > 1.21 > 1.20 > 1.19 > 1.18 > 1.17 > 1.16 > 1.15 > 1.14 > 1.13 > 1.12 > 1.11 > 1.10 > 1.09. Never publish "1.1"/"1.2" (they
# would sort below 1.09 on every installed panel); the next releases are 1.39, 1.40, ...
VERSION = "1.38"

# CLASHGATE_ROOT lets the panel run against a fake tree for local testing.
ROOT = os.environ.get("CLASHGATE_ROOT", "")
CS_ROOT = ROOT + "/etc/clashgate"
ENV_FILE = CS_ROOT + "/clashgate.env"
INBOUNDS = CS_ROOT + "/inbounds.json"
PROXIES_JSON = CS_ROOT + "/proxies.json"
PROVIDERS_JSON = CS_ROOT + "/providers.json"
PENDING_RELOAD_JSON = CS_ROOT + "/pending_reload.json"
PENDING_BASELINE_JSON = CS_ROOT + "/pending_baseline.json"
# Written by `clashgate update` when it kept the live config because panel drafts were pending:
# the config still uses the old template until it is assembled again (refresh_template_if_flagged).
TEMPLATE_REFRESH_FLAG = CS_ROOT + "/template_refresh"
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
# Keep in sync with REALITY_SNI_POOL in scripts/lib/common.sh.
REALITY_SNI_POOL = (
    "www.microsoft.com",
    "www.apple.com",
    "addons.mozilla.org",
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



_PENDING_UFW_BASELINE = None
_RECENT_ADD_REQS = {}





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



import cg_config  # noqa: E402
from cg_config import (  # noqa: E402
    pick_reality_sni,
    _SNI_HOST,
    resolve_sni,
    TYPES,
    DEFAULT_NODE_NAMES,
    PROTOCOL_DESCRIPTIONS,
    ANYTLS_FP_POOL,
    CERT_TYPES,
    random_anytls_padding,
    LOCK,
    resolve_mihomo_bin,
    resolve_template_path,
    resolve_certctl_path,
    _ROUTING,
    _seed_dir,
    _beginner_routing_state,
    _localize_fields,
    _localize_routing_state,
    get_routing,
    ensure_unified_root,
    hash_password,
    verify_password,
    read_env,
    run,
    _clean_inbounds,
    load_inbounds,
    load_server_proxies,
    load_proxy_providers,
    is_custom_config_mode,
    _parse_nodes_tsv,
    read_nodes,
    live_nodes_and_inbounds,
    get_controller_port,
    extract_yaml_secret,
    get_mihomo_secret,
    used_ports,
    pick_port,
    reality_keypair,
    sudoku_keypair,
    vless_x25519_keypair,
    certs_present,
    panel_base_url,
    zashboard_url,
    write_env_var,
    render_controller_fragment,
    x25519_pub_from_priv,
    derive_vless_encryption,
    extract_top_level_yaml_section,
    _first_user_creds,
    SNELL_VERSION,
    SNELL_V6_MIN_CORE,
    SNELL_V6_PSK_LEN,
    new_snell_psk,
    snell_client_from_listener,
    listener_to_inbound,
    parse_custom_config_state,
    check_reality_dest,
    build_inbound,
    can_reset_inbound_password,
    rotate_inbound_credentials,
    render_nodes_tsv,
    render_reality,
    render_extra,
    assemble_config,
    _json_text,
    _snapshot_files,
    _restore_files,
    atomic_write,
    _load_sessions_file,
    _save_sessions_file,
    remember_session,
    revoke_other_sessions,
    forget_session,
    NODE_NAME_MAX,
    NODE_NAME_PEER_MAX,
    _NODE_NAME_BAD,
    RESERVED_PROXY_NAMES,
    validate_node_name,
    validate_peer_name,
    default_node_name,
    local_node_name,
    load_panel_settings,
    save_panel_settings,
    cert_failure_message,
    raw_detail,
    FRIENDLY_REASONS,
    FRIENDLY_PREFIXES,
    friendly_error,
    CERT_LOCK_FILE,
    cert_task_lock,
    restart_mihomo_for_cert,
    enable_cert_renew_timer,
    ensure_geodata,
    validate_config,
    ufw_specs_for_node,
    collect_ufw_specs,
    sync_ufw,
    sync_client_files,
    replace_top_level_yaml_section,
    _sync_custom_conf_listeners,
    _sync_custom_conf_proxies,
    _sync_custom_conf_providers,
    wait_mihomo_ports,
    load_pending_reload,
    save_pending_reload,
    _TRACKED_DRAFT_FILES,
    _all_tracked_draft_files,
    _is_tracked_draft_path,
    _conf_digest,
    _ensure_pending_baseline,
    clear_pending_reload,
    _reconstruct_draft_from_live_conf,
    discard_pending_reload,
    reconcile_pending_with_live,
    refresh_template_if_flagged,
    DNS_IPV6_ONLY,
    ipv6_only,
    ipv6_listen,
    record_pending_reload,
    _dedup_inbounds,
    save_inbounds,
    save_nodes,
    save_server_proxies,
    save_proxy_providers,
    apply_custom_config,
    new_default_reality_node,
    _write_template_state,
    disable_custom_config,
    reset_to_template_config,
    reality_client,
    sanitize_doh_url_line,
    render_subscription,
    mihomo_status,
)
import cg_http  # noqa: E402
from cg_http import (  # noqa: E402
    resolve_dist_file,
    load_dist_asset,
    render_spa_html,
    parse_cert,
    public_cluster_state,
    Panel,
    TLSServer,
    serve,
    main,
)
cg_cluster.bind()
cg_http.bind()
cg_update.bind()
cg_config.bind()

if __name__ == "__main__":
    main()
