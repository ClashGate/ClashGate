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



# ---------------------------------------------------------------- manual certificate (1.20)
# The panel can switch an installed server to the installer's "manual certificate" mode: the user
# drops a certificate and key into /etc/clashgate/certs/, and the panel picks them up, checks them
# the same way scripts/lib/cert.sh check_manual_cert_files does, and installs them as
# fullchain.pem / privkey.pem (root:mihomo 0640) for Mihomo and the panel.
MANUAL_CERT_DIR_SHOWN = "/etc/clashgate/certs/"
_TEMP_CERT_CN = "clashgate temporary certificate"
_KEY_PEM_RE = re.compile(r"-----BEGIN (?:EC |RSA |ENCRYPTED )?PRIVATE KEY-----")
_PEM_MAX = 1 << 20


class ManualCertError(Exception):
    """A manual certificate check failed; str(e) is the user-facing (Chinese) reason."""


def _ossl(args, data=None):
    import subprocess
    try:
        r = subprocess.run(["openssl"] + list(args), input=data, capture_output=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return 1, b""
    return r.returncode, r.stdout


def _pubkey_digest(path: str, is_cert: bool) -> str:
    import hashlib
    if is_cert:
        rc, pub = _ossl(["x509", "-noout", "-pubkey", "-in", path])
        if rc != 0 or not pub:
            return ""
        rc, der = _ossl(["pkey", "-pubin", "-pubout", "-outform", "DER"], pub)
    else:
        rc, der = _ossl(["pkey", "-in", path, "-passin", "pass:", "-pubout", "-outform", "DER"])
    return hashlib.sha256(der).hexdigest() if rc == 0 and der else ""


def _read_head(path: str) -> str:
    try:
        if os.path.getsize(path) > _PEM_MAX:
            return ""
        with open(path, "rb") as f:
            return f.read().decode("utf-8", "replace")
    except OSError:
        return ""


def _manual_candidates(cert_dir: str):
    """(certificate files, key files) in cert_dir, newest first. Names follow the installer's
    auto_discover_manual_cert: fullchain.* / cert.pem / *.crt / *.cer / *.pem for the certificate,
    privkey.* / key.pem / *.key / *.pem for the key, recognised by their PEM headers."""
    try:
        names = os.listdir(cert_dir)
    except OSError:
        return [], []
    files = []
    for n in names:
        p = os.path.join(cert_dir, n)
        if n.startswith(".") or n.endswith((".new", ".bak", ".old")) or not os.path.isfile(p):
            continue
        try:
            files.append((os.stat(p).st_mtime, n, p))
        except OSError:
            continue
    # Newest first; on a tie prefer a file the user placed over the installed fullchain/privkey.
    files.sort(key=lambda x: (x[0], x[1] not in ("fullchain.pem", "privkey.pem")), reverse=True)
    certs, keys = [], []
    for _, n, p in files:
        low = n.lower()
        text = _read_head(p)
        if (low != "privkey.pem" and not low.endswith(".key")
                and (low.endswith((".crt", ".cer", ".pem")) or low.startswith("fullchain."))
                and "-----BEGIN CERTIFICATE-----" in text):
            certs.append(p)
        if ((low.endswith((".key", ".pem")) or low.startswith("privkey.")) and _KEY_PEM_RE.search(text)):
            keys.append(p)
    return certs, keys


def _cert_info(path: str) -> dict:
    rc, out = _ossl(["x509", "-noout", "-enddate", "-issuer", "-subject", "-in", path])
    if rc != 0:
        return {}
    text = out.decode("utf-8", "replace")
    info = _panel().parse_cert(text)
    info["subject"] = (re.search(r"subject=(.*)", text) or [None, ""])[1].strip()
    return info


def check_manual_cert(cert_dir: str, domain: str) -> dict:
    """Pick and check the manual certificate in cert_dir for `domain`.

    Mirrors scripts/lib/cert.sh check_manual_cert_files: the certificate must parse, not be
    expired, cover the domain (base name of a *.wildcard), and match a private key in the same
    directory. The newest certificate file wins, so a freshly copied *.crt beats the old
    fullchain.pem. Returns {crt, key, issuer, expires, days}; raises ManualCertError."""
    base = (domain or "").strip().lower().removeprefix("*.")
    if not base:
        raise ManualCertError("未设置域名，无法使用手动证书")
    certs, keys = _manual_candidates(cert_dir)
    # The installer's 30-day stand-in is never a real certificate.
    certs = [c for c in certs if _TEMP_CERT_CN not in _cert_info(c).get("subject", "")]
    if not certs:
        raise ManualCertError(
            "未找到证书文件：请把证书（fullchain.pem 或 *.crt）放入 /etc/clashgate/certs/ 后再试")
    crt = certs[0]
    info = _cert_info(crt)
    if not info:
        raise ManualCertError("证书文件无法识别：{}".format(os.path.basename(crt)))
    rc, _ = _ossl(["x509", "-noout", "-checkend", "0", "-in", crt])
    if rc != 0:
        raise ManualCertError("证书已过期（到期时间：{}），请换成有效的证书".format(info.get("expires") or "—"))
    rc, out = _ossl(["x509", "-noout", "-checkhost", base, "-in", crt])
    if rc != 0 or b"does match" not in out:
        raise ManualCertError("证书域名不匹配：证书里没有 {}，请换成这个域名或 *.泛域名的证书".format(base))
    if not keys:
        raise ManualCertError(
            "未找到私钥文件：请把私钥（privkey.pem 或 *.key）放入 /etc/clashgate/certs/ 后再试")
    want = _pubkey_digest(crt, True)
    key = next((k for k in keys if want and _pubkey_digest(k, False) == want), "")
    if not key:
        if any("ENCRYPTED" in _read_head(k) for k in keys):
            raise ManualCertError("私钥带有密码，请换成不带密码的私钥")
        raise ManualCertError("证书与私钥不匹配：请确认私钥和证书是同一次申请得到的")
    return {"crt": crt, "key": key, "issuer": info.get("issuer") or "—",
            "expires": info.get("expires") or "—", "days": info.get("days")}


def _mihomo_ids():
    try:
        import grp
        import pwd
    except ImportError:
        return None, None
    uid = gid = None
    try:
        gid = grp.getgrnam("mihomo").gr_gid
    except KeyError:
        pass
    try:
        uid = pwd.getpwnam("mihomo").pw_uid
    except KeyError:
        pass
    return uid, gid


def _mihomo_can_read(path: str) -> bool:
    uid, gid = _mihomo_ids()
    if uid is None or not hasattr(os, "geteuid") or os.geteuid() != 0:
        return True   # no mihomo user here (local test tree) or not root: nothing to check
    rc, _ = _panel().run(["su", "-s", "/bin/sh", "mihomo", "-c", 'test -r "$0"', path])
    return rc == 0


def install_manual_cert(cert_dir: str, crt: str, key: str) -> bool:
    """Install the checked pair as fullchain.pem / privkey.pem (root:mihomo 0640). Restores the old
    files if Mihomo cannot read the key. Returns True if the installed files changed."""
    dest_c = os.path.join(cert_dir, "fullchain.pem")
    dest_k = os.path.join(cert_dir, "privkey.pem")

    def rd(p):
        try:
            with open(p, "rb") as f:
                return f.read()
        except OSError:
            return None

    new_c, new_k = rd(crt), rd(key)
    if new_c is None or new_k is None:
        raise ManualCertError("写入证书失败：{}".format("无法读取证书文件"))
    old_c, old_k = rd(dest_c), rd(dest_k)
    changed = (new_c, new_k) != (old_c, old_k)
    _, gid = _mihomo_ids()

    def put(path, data):
        tmp = path + ".new"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o640)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        fix_mode(tmp)
        os.replace(tmp, path)

    def fix_mode(path):
        os.chmod(path, 0o640)
        if gid is not None and hasattr(os, "geteuid") and os.geteuid() == 0:
            os.chown(path, 0, gid)

    try:
        if changed:
            put(dest_k, new_k)   # key first, like certctl deploy
            put(dest_c, new_c)
        else:
            fix_mode(dest_k)
            fix_mode(dest_c)
    except OSError as e:
        raise ManualCertError("写入证书失败：{}".format(e.strerror or e))
    if not _mihomo_can_read(dest_k):
        if changed and old_c is not None and old_k is not None:
            try:
                put(dest_k, old_k)
                put(dest_c, old_c)
            except OSError:
                pass
        raise ManualCertError("Mihomo 无法读取私钥，请检查 /etc/clashgate/certs/ 的文件权限")
    return changed
