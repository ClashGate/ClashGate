"""Cloudflare MASQUE registration. Moved out of panel.py unchanged."""
import base64
import datetime
import json
import os
import secrets
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

_BOUND = False


def _ensure_bound():
    """Copy path constants and helpers from the panel module on first use.

    This module is imported while panel.py is still loading, so the copy cannot
    happen at import time.
    """
    global _BOUND
    if _BOUND:
        return
    mod = sys.modules.get("panel") or sys.modules.get("__main__")
    if mod is None:
        return
    g = globals()
    for key, val in mod.__dict__.items():
        if key.startswith("__") or key in g:
            continue
        g[key] = val
    _BOUND = True


def _openssl(args, data=None, timeout=20) -> bytes:
    _ensure_bound()
    proc = subprocess.run(["openssl", *args], input=data, capture_output=True, timeout=timeout)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or b"openssl failed").decode("utf-8", "replace").strip()
        raise RuntimeError(err[:300] or "openssl failed")
    return proc.stdout


def _x25519_public_b64() -> str:
    _ensure_bound()
    pem = _openssl(["genpkey", "-algorithm", "X25519"])
    der = _openssl(["pkey", "-pubout", "-outform", "DER"], pem)
    if len(der) < 32:
        raise RuntimeError("X25519 公钥生成失败")
    return base64.b64encode(der[-32:]).decode()


def _p256_keypair_b64():
    _ensure_bound()
    pem = _openssl(["genpkey", "-algorithm", "EC", "-pkeyopt", "ec_paramgen_curve:P-256"])
    sec1 = _openssl(["ec", "-outform", "DER"], pem)
    pub = _openssl(["pkey", "-pubout", "-outform", "DER"], pem)
    return base64.b64encode(sec1).decode(), base64.b64encode(pub).decode()


def _edge_public_b64(value: str) -> str:
    _ensure_bound()
    raw = (value or "").strip()
    if not raw:
        raise RuntimeError("注册响应里没有边缘公钥")
    if "BEGIN" in raw:
        der = _openssl(["pkey", "-pubin", "-outform", "DER"], raw.encode())
        return base64.b64encode(der).decode()
    try:
        der = base64.b64decode(raw, validate=True)
    except Exception as e:
        raise RuntimeError("边缘公钥不是合法的 PEM 或 Base64") from e
    if not der.startswith(b"\x30"):
        raise RuntimeError("边缘公钥格式无法识别")
    return raw


def _cf_json(method: str, url: str, body=None, token: str = ""):
    _ensure_bound()
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "WARP for Android")
    req.add_header("CF-Client-Version", "a-6.35-4471")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            code, payload = resp.status, resp.read()
    except urllib.error.HTTPError as e:
        code, payload = e.code, e.read()
    except Exception as e:
        raise RuntimeError(f"无法连接 Cloudflare 注册接口：{e}") from e
    text = payload.decode("utf-8", "replace")
    if code != 200:
        raise RuntimeError(f"Cloudflare 注册接口返回 {code}：{text[:400]}")
    try:
        parsed = json.loads(text)
    except ValueError as e:
        raise RuntimeError("Cloudflare 注册接口返回了无法解析的内容") from e
    if not isinstance(parsed, dict):
        raise RuntimeError("Cloudflare 注册接口返回格式异常")
    return parsed


def _host_only(value: str) -> str:
    _ensure_bound()
    text = (value or "").strip()
    if not text:
        return ""
    if text.startswith("["):
        end = text.find("]")
        return text[1:end] if end > 1 else ""
    if text.count(":") == 1:
        host, _, _port = text.partition(":")
        return host
    return text


def register_cloudflare_masque() -> dict:
    """Register one Cloudflare WARP device and switch it to MASQUE. Stdlib + openssl."""
    _ensure_bound()
    wg_pub = _x25519_public_b64()
    priv_b64, _client_pub_b64 = _p256_keypair_b64()
    client_pub = _client_pub_b64
    created = _cf_json("POST", "https://api.cloudflareclient.com/v0a4471/reg", {
        "key": wg_pub,
        "install_id": "",
        "fcm_token": "",
        "tos": datetime.datetime.now().astimezone().isoformat(timespec="milliseconds"),
        "model": "PC",
        "serial_number": secrets.token_hex(8),
        "key_type": "curve25519",
        "tunnel_type": "wireguard",
        "locale": "en_US",
        "warp_enabled": True,
    })
    reg_id = str(created.get("id") or "")
    reg_token = str(created.get("token") or "")
    if not reg_id or not reg_token:
        raise RuntimeError("Cloudflare 注册响应缺少设备 id 或 token")
    enrolled = _cf_json(
        "PATCH",
        "https://api.cloudflareclient.com/v0a4471/reg/" + reg_id,
        {"key": client_pub, "key_type": "secp256r1", "tunnel_type": "masque"},
        token=reg_token,
    )
    config = enrolled.get("config") if isinstance(enrolled.get("config"), dict) else {}
    peers = config.get("peers") if isinstance(config.get("peers"), list) else []
    peer = peers[0] if peers and isinstance(peers[0], dict) else {}
    endpoint = peer.get("endpoint") if isinstance(peer.get("endpoint"), dict) else {}
    addresses = {}
    interface = config.get("interface") if isinstance(config.get("interface"), dict) else {}
    if isinstance(interface.get("addresses"), dict):
        addresses = interface["addresses"]
    server = _host_only(str(endpoint.get("v4") or endpoint.get("host") or ""))
    ports = endpoint.get("ports") if isinstance(endpoint.get("ports"), list) else []
    port = 443
    for candidate in ports:
        try:
            if int(candidate) == 443:
                port = 443
                break
            port = int(candidate)
        except (TypeError, ValueError):
            continue
    if not server:
        raise RuntimeError("注册成功但没有返回 MASQUE 接入地址")
    ipv4 = str(addresses.get("v4") or "").strip()
    ipv6 = str(addresses.get("v6") or "").strip()
    if ipv4 and "/" not in ipv4:
        ipv4 += "/32"
    if ipv6 and "/" not in ipv6:
        ipv6 += "/128"
    if not ipv4:
        raise RuntimeError("注册成功但没有返回隧道 IPv4")
    edge_pub = _edge_public_b64(str(peer.get("public_key") or ""))
    proxy = {
        "name": MASQUE_NAME,
        "type": "masque",
        "server": server,
        "port": port,
        "private-key": priv_b64,
        "public-key": edge_pub,
        "ip": ipv4,
        "mtu": 1280,
        "udp": True,
        "uri": "https://cloudflareaccess.com",
        "sni": "consumer-masque.cloudflareclient.com",
        "network": "quic",
    }
    if ipv6:
        proxy["ipv6"] = ipv6
    return {
        "status": "ok",
        "name": proxy["name"],
        "endpoint": f"{server}:{port}",
        "proxy": proxy,
        "yaml": "- " + json.dumps(proxy, ensure_ascii=False),
        "error": "",
        "updated": int(time.time()),
    }


def load_masque_state() -> dict:
    _ensure_bound()
    try:
        with open(MASQUE_JSON) as f:
            raw = json.load(f)
        if isinstance(raw, dict) and raw.get("status") == "ok" and isinstance(raw.get("proxy"), dict):
            proxy = raw["proxy"]
            return {
                "status": "ok",
                "name": str(raw.get("name") or proxy.get("name") or MASQUE_NAME),
                "endpoint": str(raw.get("endpoint") or ""),
                "yaml": str(raw.get("yaml") or ""),
                "error": "",
            }
        if isinstance(raw, dict):
            return {
                "status": str(raw.get("status") or "error"),
                "name": MASQUE_NAME,
                "endpoint": "",
                "yaml": "",
                "error": str(raw.get("error") or ""),
            }
    except Exception:
        pass
    return {"status": "idle", "name": MASQUE_NAME, "endpoint": "", "yaml": "", "error": ""}


def save_masque_state(state: dict):
    _ensure_bound()
    # Credentials stay on disk at 0600. The panel only exposes them to a logged-in admin.
    atomic_write(MASQUE_JSON, json.dumps(state, ensure_ascii=False) + "\n", 0o600)


def _masque_worker():
    _ensure_bound()
    with _MASQUE_LOCK:
        current = load_masque_state()
        if current.get("status") == "ok" and current.get("yaml"):
            return
        try:
            save_masque_state({"status": "pending", "name": MASQUE_NAME, "error": "", "updated": int(time.time())})
            ready = register_cloudflare_masque()
            save_masque_state(ready)
            sys.stderr.write(f"cloudflare masque registered: {ready.get('endpoint')}\n")
        except Exception as e:
            save_masque_state({
                "status": "error",
                "name": MASQUE_NAME,
                "error": str(e)[:500],
                "updated": int(time.time()),
            })
            sys.stderr.write(f"cloudflare masque registration failed: {e}\n")


def start_masque_registrar(force: bool = False):
    _ensure_bound()
    if force:
        try:
            os.remove(MASQUE_JSON)
        except OSError:
            pass
    threading.Thread(target=_masque_worker, name="masque-reg", daemon=True).start()

