"""Rewrite server TLS certificate paths inside a Mihomo config. Moved unchanged."""
import os
import re
import sys


def _panel():
    """The already-loaded panel module (aliased even when loaded as cg_panel_seed)."""
    return sys.modules.get("panel") or sys.modules["__main__"]

# ---------------------------------------------------------------- custom server config helpers
_CERT_FILE_EXT = re.compile(r"\.(pem|crt|cer|key)$", re.I)
_WG_KEY_RE = re.compile(r"^[A-Za-z0-9+/]{42,43}=$")
# Top-level sections whose certificate / private-key are this server's TLS files.
_CERT_SECTIONS = ("listeners", "tls")


def _is_cert_path_value(val: str) -> bool:
    """True if a certificate/private-key value is a file path (not inline PEM or a key string)."""
    v = (val or "").strip().strip("'\"")
    if not v or v[0] in "|>" or v.startswith("-----") or _WG_KEY_RE.match(v):
        return False
    return v.startswith(("/", "./", "../", "~")) or bool(_CERT_FILE_EXT.search(v))


def _iter_server_cert_lines(lines: list):
    """Yield (index, match, kind) for certificate / private-key file-path lines under the top-level
    `listeners:` / `tls:` sections (reality-config keys, inline PEM and WireGuard keys skipped).
    match groups: 1 = prefix up to the value, 3 = value, 4 = trailing comment."""
    top = ""
    in_reality = False
    reality_indent = 0
    for i, line in enumerate(lines):
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        if not stripped or stripped.startswith("#"):
            continue
        if indent == 0 and not stripped.startswith("-"):  # `- item` at column 0 stays in its section
            m_top = re.match(r"^([A-Za-z0-9_-]+)\s*:", stripped)
            top = m_top.group(1) if m_top else ""
        if in_reality and indent <= reality_indent:
            in_reality = False
        if re.match(r"^(?:-\s+)?reality-config\s*:", stripped):
            in_reality = True
            reality_indent = indent
            continue
        if top not in _CERT_SECTIONS or in_reality:
            continue
        m = re.match(r"^((?:-\s+)?(certificate|private-key)\s*:\s*)([^#\n]+?)(\s*(?:#.*)?)$", stripped)
        if m and _is_cert_path_value(m.group(3)):
            yield i, m, m.group(2)


def server_cert_paths(raw_yaml: str) -> list:
    """Certificate / private-key file paths the server TLS config references (as written)."""
    lines = (raw_yaml or "").splitlines()
    return [m.group(3).strip().strip("'\"") for _, m, _ in _iter_server_cert_lines(lines)]


def missing_cert_files(raw_yaml: str) -> list:
    """Referenced cert/key paths that are not readable files. Relative paths resolve against the
    Mihomo home directory (-d), as the core resolves them."""
    P = _panel()
    missing = []
    for p in server_cert_paths(raw_yaml):
        # Absolute paths are as the core sees them; ROOT only prefixes them in local test trees.
        full = (P.ROOT + p) if os.path.isabs(p) else os.path.normpath(os.path.join(P.MIHOMO_DIR, p))
        if not (os.path.isfile(full) and os.access(full, os.R_OK)) and p not in missing:
            missing.append(p)
    return missing


def rewrite_cert_paths_in_yaml(raw_yaml: str, env: dict = None) -> tuple:
    """Point TLS certificate/private-key file paths under `listeners:` and `tls:` at this
    server's own certs (CERT / KEY); also rename a reserved `default` proxy-provider.

    Returns (new_yaml, n) where n counts certificate/key paths that differed from
    CERT / KEY (relative paths included); n == 0 means nothing to ask the user about.
    Never touches reality-config private keys, inline PEM, or outbound proxies.
    Keep in sync with fixCertPaths() in panel/web/src/App.vue."""
    P = _panel()
    lines = raw_yaml.splitlines()
    changed = 0
    for i, m, kind in list(_iter_server_cert_lines(lines)):
        target = P.CERT if kind == "certificate" else P.KEY
        if m.group(3).strip().strip("'\"") != target:
            changed += 1
            indent = len(lines[i]) - len(lines[i].lstrip(" "))
            lines[i] = (" " * indent) + f"{m.group(1)}{target}{m.group(4)}"
    # Rename reserved provider key `default:` under `proxy-providers:` so mihomo -t passes
    in_providers = False
    providers_indent = 0
    for i, line in enumerate(lines):
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        if not stripped or stripped.startswith("#"):
            continue
        if in_providers and indent <= providers_indent:
            in_providers = False
        if re.match(r"^proxy-providers\s*:", stripped):
            in_providers = True
            providers_indent = indent
            continue
        if in_providers and indent == providers_indent + 2 and re.match(r"^default\s*:\s*(#.*)?$", stripped):
            lines[i] = (" " * indent) + re.sub(r"^default(\s*:)", r"default-sub\1", stripped, count=1)
    res = "\n".join(lines) + ("\n" if raw_yaml.endswith("\n") else "")
    return res, changed


def sync_env_from_custom_config(raw_yaml: str):
    """Sync CONTROLLER_PORT and MIHOMO_SECRET from a custom server config if present."""
    P = _panel()
    for pat in (
        r'^\s*external-controller-tls\s*:\s*["\']?[^"\':\s]+:(\d+)["\']?',
        r'^\s*external-controller\s*:\s*["\']?[^"\':\s]+:(\d+)["\']?',
    ):
        m_port = re.search(pat, raw_yaml, re.M)
        if m_port:
            p = int(m_port.group(1))
            if 1 <= p <= 65535:
                P.write_env_var("CONTROLLER_PORT", str(p))
                break
    sec = P.extract_yaml_secret(raw_yaml)
    if sec:
        P.write_env_var("MIHOMO_SECRET", sec)

