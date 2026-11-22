"""Panel HTTP server. Moved out of panel.py unchanged."""
import sys
import argparse
import base64
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import socket
import ssl
import threading
import time
import uuid as uuidlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse, quote


def bind():
    """Copy panel constants and helpers. panel.py imports this module last."""
    mod = sys.modules.get("panel") or sys.modules.get("__main__")
    if mod is None:
        return
    g = globals()
    for key, val in mod.__dict__.items():
        if key.startswith("__") or key in g:
            continue
        g[key] = val


bind()


# gzip for the SPA page, its assets and JSON/YAML responses (the page inlines ~450 kB of JS/CSS).
# Static files are compressed once and cached by (path, mtime); per-request pages are compressed
# on the fly (about 10 ms at level 6).
_GZIP_TYPES = ("text/", "application/javascript", "application/json", "image/svg+xml", "text/yaml")
_GZIP_MIN = 1024
_GZ_CACHE = {}
_GZ_CACHE_LOCK = threading.Lock()


def _compressible(ctype: str, data: bytes) -> bool:
    return len(data) >= _GZIP_MIN and ctype.startswith(_GZIP_TYPES)


def _gzip_bytes(data: bytes, cache_key=None) -> bytes:
    import gzip
    if cache_key is None:
        return gzip.compress(data, 6)
    with _GZ_CACHE_LOCK:
        hit = _GZ_CACHE.get(cache_key)
    if hit is not None:
        return hit
    out = gzip.compress(data, 9)
    with _GZ_CACHE_LOCK:
        if len(_GZ_CACHE) > 64:
            _GZ_CACHE.clear()
        _GZ_CACHE[cache_key] = out
    return out


_CERT_TASK = {"running": False, "ok": None, "msg": "", "detail": "", "started_at": 0.0, "finished_at": 0.0}
_CERT_TASK_LOCK = threading.Lock()


def _read_or_none(path: str):
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        return None


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


_ASSET_VER = {}
_ASSET_VER_LOCK = threading.Lock()


def asset_version(rel: str) -> str:
    """Short content hash of a dist file, computed once per (path, mtime, size)."""
    fp = resolve_dist_file(rel)
    try:
        st = os.stat(fp)
    except OSError:
        return ""
    key = (fp, st.st_mtime_ns, st.st_size)
    with _ASSET_VER_LOCK:
        hit = _ASSET_VER.get(rel)
    if hit and hit[0] == key:
        return hit[1]
    try:
        with open(fp, "rb") as f:
            ver = hashlib.sha256(f.read()).hexdigest()[:12]
    except OSError:
        return ""
    with _ASSET_VER_LOCK:
        _ASSET_VER[rel] = (key, ver)
    return ver


def asset_url(rel: str) -> str:
    """/assets/app.js?v=<hash>: the browser keeps it until a panel upgrade changes the file."""
    ver = asset_version(rel)
    return f"/{rel}?v={ver}" if ver else f"/{rel}"


# Panel skin (Settings): applied before first paint so the page never flashes the default look.
# The only inline script on the page; the CSP below allows exactly this text by its hash.
_THEME_JS = ("try{var t=localStorage.getItem('clashgate_theme');if(t==='christmas'||t==='dark')"
             "document.documentElement.dataset.theme=t}catch(e){}")
_THEME_JS_SHA = base64.b64encode(hashlib.sha256(_THEME_JS.encode()).digest()).decode()
# Scripts only from this panel (the bundles) plus the skin snippet; no eval, no other origins.
# Styles allow inline (Vue :style bindings, the small <style> in the page head).
CSP = ("default-src 'self'; "
       f"script-src 'self' 'sha256-{_THEME_JS_SHA}'; "
       "style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; "
       "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")


def render_spa_html(title: str, boot_data: dict, fallback_html: str = "") -> str:
    # The JS / CSS bundles (~450 kB) are separate, content-versioned files the browser caches;
    # only this small page (boot data) is sent on every visit.
    css_url = html.escape(asset_url("assets/style.css"), quote=True)
    js_url = html.escape(asset_url("assets/app.js"), quote=True)
    # A JSON data block, not a script (src/boot.js reads it): "<" escaped so no text can end the element.
    boot_json = json.dumps(boot_data, ensure_ascii=False).replace("<", "\\u003c")
    noscript = f"<noscript>{fallback_html}</noscript>" if fallback_html else ""
    return (
        "<!doctype html><html lang=zh-CN><head><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>{html.escape(title)}</title>"
        "<link rel=icon type=image/png href=/favicon.png><link rel='shortcut icon' href=/favicon.ico>"
        "<style>html{background:#f3f6fb}html[data-theme=dark]{background:#0f1318;color-scheme:dark}"
        "html:not(.cg-ready) #app{visibility:hidden}</style>"
        f"<script>{_THEME_JS}</script>"
        f"<link rel=stylesheet href=\"{css_url}\">"
        f"<script type=application/json id=cs-boot>{boot_json}</script>"
        "</head>"
        "<body class='antialiased'>"
        "<div id=app></div>"
        f"{noscript}"
        f"<script src=\"{js_url}\"></script>"
        "</body></html>"
    )


def certctl_env() -> dict:
    """certctl follows the CLI language; panel runs pin Chinese so cert_failure_message can parse the output."""
    return dict(os.environ, CLASHGATE_LANG="zh")


def cli_default_lang(env=None) -> str:
    """CLI language chosen at install / `clashgate lang`: the panel's language until a browser picks one."""
    v = ((env if env is not None else read_env()).get("CLASHGATE_LANG") or "").strip().lower()
    return v if v in ("zh", "en", "ru") else ""


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
        "pending": [{"id": cluster_pending_id(p), "name": p.get("name", ""), "url": p.get("url", ""), "error": tr(p.get("error", ""))}
                    for p in st["pending"]],
    }


class Panel(BaseHTTPRequestHandler):
    server_version = "clashgate/" + VERSION
    cfg: dict = {}
    cfg_path: str = ""
    sessions: dict = {}
    fails: dict = {}
    # Rate-limit buckets that signed in successfully (bucket -> time). The all-sources cap must not
    # let someone guessing from many addresses lock the owner out of their own panel.
    trusted: dict = {}

    def _is_trusted(self, bucket: str, now: float) -> bool:
        return now - self.trusted.get(bucket, 0) < SESSION_TTL

    def _trust(self, bucket: str, now: float):
        with _SESSION_LOCK:
            for k in [k for k, v in self.trusted.items() if now - v >= SESSION_TTL]:
                self.trusted.pop(k, None)
            if len(self.trusted) < 256 or bucket in self.trusted:
                self.trusted[bucket] = now

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

    def accepts_gzip(self) -> bool:
        if self.command == "HEAD":
            return False
        for part in (self.headers.get("Accept-Encoding") or "").split(","):
            enc, _, q = part.strip().partition(";")
            if enc.strip().lower() == "gzip":
                return q.strip().replace(" ", "") not in ("q=0", "q=0.0", "q=0.00", "q=0.000")
        return False

    def send(self, code, body, ctype="text/html; charset=utf-8", headers=None, cache_key=None):
        if ctype.startswith("application/json") and isinstance(body, str) and self.lang() in ("en", "ru", "fa"):
            try:
                obj = json.loads(body)
                if isinstance(obj, dict) and isinstance(obj.get("msg"), str):
                    obj["msg"] = _tr_msg(obj["msg"], self.lang())
                    if obj.get("detail") and isinstance(obj["detail"], str):
                        obj["detail"] = _tr_msg(obj["detail"], self.lang())
                    body = json.dumps(obj, ensure_ascii=False)
            except ValueError:
                pass
        data = body.encode() if isinstance(body, str) else body
        headers = dict(headers or {})
        if self.accepts_gzip() and _compressible(ctype, data):
            data = _gzip_bytes(data, cache_key)
            headers["Content-Encoding"] = "gzip"
            headers["Vary"] = "Accept-Encoding"
        try:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Connection", "close")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", CSP)
            if "Cache-Control" not in headers:
                self.send_header("Cache-Control", "no-store")
            for k, v in headers.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionError, ssl.SSLError, socket.timeout):
            pass

    def send_asset(self, fp: str, rel: str, ctype: str):
        """Static dist file with caching: the exact versioned URL the page links is immutable;
        fonts / images keep a week; anything else revalidates. An ETag answers repeat visits with 304."""
        ver = asset_version(rel)
        asked = parse_qs(urlparse(self.path).query).get("v", [""])[0]
        if ver and asked == ver:
            cc = "public, max-age=31536000, immutable"
        elif fp.endswith((".woff2", ".woff", ".png")):
            cc = "public, max-age=604800"
        else:
            cc = "no-cache"
        headers = {"Cache-Control": cc}
        if ver:
            etag = f'W/"{ver}"'
            headers["ETag"] = etag
            inm = self.headers.get("If-None-Match") or ""
            if etag in [t.strip() for t in inm.split(",")] or inm.strip() == "*":
                return self.send(304, b"", ctype, headers)
        with open(fp, "rb") as f:
            return self.send(200, f.read(), ctype, headers, cache_key=(fp, os.path.getmtime(fp)))

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
        # A node is "pending" only when the draft list says so (added / new password, not applied yet);
        # a port that is not listening for another reason shows as not running.
        pending_node_names = {
            it.get("name") for it in pending_items
            if it.get("op") in ("add", "reset-password") and it.get("name")
        }

        inbound_items = []
        all_proxies = []
        for n in nodes:
            proxy = reality_client(n, env)
            all_proxies.append(proxy)
            is_pending = n["name"] in pending_node_names
            inbound_items.append({
                "key": f"node:{n['name']}",
                "name": n["name"],
                "kind": "vless-reality",
                "kind_label": KIND_ZH["vless-reality"],
                "port": n["port"],
                "listening": n["port"] in listening and not is_pending,
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
            is_pending = i["name"] in pending_node_names
            inbound_items.append({
                "key": f"inb:{i['id']}",
                "name": i["name"],
                "kind": i["kind"],
                "kind_label": KIND_ZH.get(i["kind"], i["kind"]),
                "port": i["port"],
                "listening": i["port"] in listening and not is_pending,
                "pending_reload": is_pending,
                "can_reset_password": can_reset,
                "reset_url": f"/inbounds/{i['id']}/reset-password" if can_reset else "",
                "delete_url": f"/inbounds/{i['id']}/delete",
                "single_config": "- " + json.dumps(proxy, ensure_ascii=False),
                "readable_config": "\n".join(dump_yaml_map(proxy, indent=2, first_dash=True)),
            })

        # Nodes deleted in the draft are still served until 「应用配置」: keep them in the list, marked.
        inbound_items += self._pending_delete_items(listening, pending_items, nodes, inbs)

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
                # Nodes the core is serving now (drafts not applied yet are left out), for 「节点 x/y 在线」.
                **self._live_node_counts(listening),
                "uptime_s": st.get("uptime"),
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
            "cluster": public_cluster_state(False, req_lang),
            "routing": _localize_routing_state(_beginner_routing_state(
                get_routing().public_state(cur_cfg, custom_mode=True)
                if custom_active
                else get_routing().public_state()
            ), req_lang),
        }

    @staticmethod
    def _pending_delete_items(listening: set, pending_items: list, nodes: list, inbs: list) -> list:
        """Live nodes the draft deletes: shown greyed (「待删除」) with no actions until the config is applied."""
        deleted = {it.get("name") for it in pending_items if it.get("op") == "delete" and it.get("name")}
        if not deleted:
            return []
        draft = {n["name"] for n in nodes} | {i["name"] for i in inbs}
        try:
            live_n, live_i = live_nodes_and_inbounds()
        except Exception:
            return []
        out = []
        for kind, name, port in ([("vless-reality", n["name"], n["port"]) for n in live_n]
                                 + [(i["kind"], i["name"], i["port"]) for i in live_i]):
            if name not in deleted or name in draft:
                continue
            out.append({
                "key": f"gone:{name}",
                "name": name,
                "kind": kind,
                "kind_label": KIND_ZH.get(kind, kind),
                "port": port,
                "listening": port in listening,
                "pending_reload": True,
                "pending_delete": True,
                "can_reset_password": False,
                "reset_url": "",
                "delete_url": "",
                "single_config": "",
                "readable_config": "",
            })
        return out

    @staticmethod
    def _live_node_counts(listening: set) -> dict:
        try:
            live_n, live_i = live_nodes_and_inbounds()
            ports = [int(n["port"]) for n in live_n] + [int(i["port"]) for i in live_i]
        except Exception:
            return {"live_total": None, "live_up": None}
        return {"live_total": len(ports), "live_up": sum(1 for p in ports if p in listening)}

    def respond_mutation(self, s, msg: str, ok: bool = True, detail: str = ""):
        if not ok and not detail:
            msg, detail = friendly_error(msg)
        if not self.is_ajax():
            return self.flash(msg, ok)
        env = read_env()
        st = mihomo_status()
        state = self.build_client_state(s, env, st)
        payload = {
            "ok": ok,
            "msg": msg,
            "detail": detail,
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
                    return self.send_asset(fp, rel, ctype)
            return self.send(404, "not found", "text/plain")
        if path in ("/favicon.ico", "/favicon.png", "/logo.png"):
            fp = resolve_dist_file("favicon.ico" if path == "/favicon.ico" else ("assets/logo.png" if path == "/logo.png" else "favicon.png"))
            if os.path.isfile(fp):
                with open(fp, "rb") as f:
                    return self.send(200, f.read(), "image/x-icon" if fp.endswith(".ico") else "image/png",
                                     {"Cache-Control": "public, max-age=86400"}, cache_key=(fp, os.path.getmtime(fp)))
            return self.send(404, "not found", "text/plain")
        if path == "/login":
            return self.send(200, self.login_page())
        if path.startswith("/sub/"):
            return self.do_sub(path)
        if path == "/api/cluster/hello":
            return self.do_cluster_hello()
        tok, s = self.session()
        if not s:
            if path.startswith("/api/") or self.is_ajax():
                # Polling clients must see the expired session, not a 303 to the login page's HTML.
                return self.send(401, json.dumps({"ok": False, "msg": "登录会话已过期，请刷新页面重新登录"}, ensure_ascii=False),
                                 "application/json; charset=utf-8")
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
        if path == "/about":
            return self.send(200, self.dashboard(s, initial_tab="about"))
        if path == "/cluster":
            return self.send(200, self.dashboard(s, initial_tab="cluster"))
        if path == "/api/state":
            return self.send(200, json.dumps(self.build_client_state(s), ensure_ascii=False), "application/json; charset=utf-8")
        if path == "/api/upgrade-status":
            d = load_upgrade_status()
            d["version"] = VERSION
            # 1.43: `clashgate update` goes on without the core when it cannot get or download it
            # (core_update_failed); the page says so after the panel update succeeded.
            try:
                if d.get("state") == "done" and os.path.getmtime(CORE_UPDATE_FAILED) >= float(d.get("started_at") or 0):
                    with open(CORE_UPDATE_FAILED) as f:
                        d["core_failed"] = (f.read().split("\t") + [""])[0].strip() or "download"
            except (OSError, ValueError):
                pass
            if d.get("state") == "done" and d.get("rc") == 0 and not d.get("recorded"):
                try:
                    record_panel_check(VERSION, False)
                    d["recorded"] = True
                    atomic_write(UPGRADE_STATUS_JSON, json.dumps(d) + "\n", 0o600)
                except Exception:
                    pass
            return self.send(200, json.dumps(d, ensure_ascii=False), "application/json; charset=utf-8")
        if path == "/api/cert-task-status":
            return self.cert_task_status(s)
        if path == "/api/cluster-task-status":
            return self.cluster_task_status(s)
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
        if path == "/api/cluster/apply":
            return self.do_cluster_apply(form)
        if path == "/api/cluster/node":
            return self.do_cluster_node(form)
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
        if path == "/action/reload":
            return self.do_action(s, "reload")
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
            return self.do_cert_action(s, form)
        if path == "/action/cert-mode":
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
            return self.do_cluster_sync(s, form)
        if path == "/cluster/leave":
            return self.do_cluster_leave_ui(s, form)
        if path == "/cluster/dismiss":
            return self.do_cluster_dismiss(s, form)
        if path == "/cluster/retry":
            return self.do_cluster_retry(s, form)
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
        if len(recent) >= LOGIN_MAX_FAILS_PER_IP or (total >= LOGIN_MAX_FAILS_TOTAL and not self._is_trusted(ip, now)):
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
            self._trust(ip, now)
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
        return len(recent) >= LOGIN_MAX_FAILS_PER_IP or (total >= LOGIN_MAX_FAILS_TOTAL and not self._is_trusted(ip, now))

    def _cluster_note_fail(self):
        ip, now = self.login_bucket(), time.time()
        with _SESSION_LOCK:
            self.fails[ip] = [t for t in self.fails.get(ip, []) if now - t < LOGIN_WINDOW] + [now]

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
            self._trust(self.login_bucket(), time.time())
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
                "in": {"uuid": inb["uuid"]},   # a user in the shared cluster inbound (1.42)
                "out": {"server": urlparse(url).hostname, **node}}

        def add(st):
            old = _link_by(st, instance=inst)   # the same panel joining again replaces its old link
            if peer_name in (used_proxy_names() - ({old.get("name")} if old else set())):
                raise ClusterError(f"名称「{peer_name}」在对方面板上已被出站或分流组使用，请换一个本机名称")
            st["links"] = [l for l in st["links"] if l.get("instance") != inst] + [link]
            st["pending"] = [p for p in st["pending"] if p.get("instance") != inst]
            st["removed"].pop(inst, None)
            return cluster_members_view(st, skip=inst)
        # defer=1 (1.40): the calling panel is still exchanging with others; it sends /api/cluster/apply
        # when every panel has its links, so this core reloads once instead of in the middle.
        _CLUSTER_BATCH.defer = 1 if form.get("defer") == "1" else 0
        try:
            members = _cluster_commit(add)
        except ClusterError as e:
            return self._cjson(409, {"ok": False, "code": "name_clash", "msg": str(e)})
        except Exception as e:
            sys.stderr.write(f"cluster join failed: {e}\n")
            return self._cjson(500, {"ok": False, "code": "apply_failed", "msg": str(e)[:300]})
        finally:
            _CLUSTER_BATCH.defer = 0
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
        target = str(form.get("target_instance") or "")
        if _link_by(load_cluster(), instance=target):
            return self._cjson(200, {"ok": True, "already": True})
        _CLUSTER_BATCH.defer = 1 if form.get("defer") == "1" else 0   # both sides stage; the caller applies
        try:
            url = normalize_panel_url(str(form.get("target_url") or ""))
            cluster_pair(url, {"ticket": str(form.get("ticket") or "")}, expect_instance=target)
        except ClusterError as e:
            return self._cjson(502, {"ok": False, "code": "unreachable", "msg": str(e)})
        finally:
            _CLUSTER_BATCH.defer = 0
        return self._cjson(200, {"ok": True})

    def do_cluster_node(self, form):
        """1.42: a member moved our link to its shared cluster inbound: point our outbound at it."""
        link, err = self._cluster_link_auth(form)
        if not link:
            return err
        try:
            node = _parse_node(form)
        except ClusterError:
            return self._cjson(400, {"ok": False, "code": "bad_request", "msg": "集群请求参数无效"})

        def upd(st):
            x = _link_by(st, instance=link["instance"])
            if x:
                x["out"] = {**(x.get("out") or {}), **node}
        _CLUSTER_BATCH.defer = 1 if form.get("defer") == "1" else 0   # the caller applies when done
        try:
            _cluster_commit(upd)
        except Exception as e:
            sys.stderr.write(f"cluster node update failed: {e}\n")
            return self._cjson(500, {"ok": False, "code": "apply_failed", "msg": str(e)[:300]})
        finally:
            _CLUSTER_BATCH.defer = 0
        return self._cjson(200, {"ok": True})

    def do_cluster_apply(self, form):
        """A member finished exchanging links with every panel: make our staged cluster changes live."""
        link, err = self._cluster_link_auth(form)
        if not link:
            return err
        try:
            cluster_apply_staged()
        except Exception as e:
            sys.stderr.write(f"cluster apply failed: {e}\n")
            return self._cjson(500, {"ok": False, "code": "apply_failed", "msg": str(e)[:300]})
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
    @staticmethod
    def _run_cluster_job(job) -> tuple:
        try:
            return job()
        except ClusterCancelled:
            return "检查已中断，正在退出集群", False
        except (ClusterError, ValueError) as e:
            return str(e), False
        except Exception as e:   # never drop the connection on an unexpected error
            sys.stderr.write(f"cluster job failed: {e!r}\n")
            return f"集群操作失败：{e}", False

    _PREEMPTABLE = ("sync", "retry")   # 检查 / 重试 give way to 退出集群 (1.44)

    def _cluster_job(self, s, job, form=None, kind=""):
        """Run a cluster operation. With async=1 (the page) it runs in a background thread and the page
        polls /api/cluster-task-status for the current step: adding a panel waits for both cores to
        reload and can take a minute, longer than a request should hang.
        1.44: 退出集群 does not wait for a running 检查 / 重试: it tells that one to stop (_CLUSTER_CANCEL,
        honoured at its next step) and leaves at once; the check releases the lock when it stops."""
        locked = _CLUSTER_OP_LOCK.acquire(blocking=False)
        if not locked:
            with _CLUSTER_TASK_LOCK:
                busy_kind = _CLUSTER_TASK["kind"] if _CLUSTER_TASK["running"] else ""
            if kind != "leave" or busy_kind not in self._PREEMPTABLE:
                return self.respond_mutation(s, "另一个集群操作正在进行，请稍候再试", False)
            _CLUSTER_CANCEL.set()
            sys.stderr.write(f"cluster: {busy_kind} interrupted by leave\n")
        else:
            _CLUSTER_CANCEL.clear()
        cancellable = kind in self._PREEMPTABLE

        def run():
            _CLUSTER_BATCH.cancellable = cancellable
            try:
                return self._run_cluster_job(job)
            finally:
                _CLUSTER_BATCH.cancellable = False
                if locked:
                    _CLUSTER_OP_LOCK.release()

        if not ((form or {}).get("async") == "1" and self.is_ajax()):
            msg, ok = run()
            return self.respond_mutation(s, msg, ok)
        with _CLUSTER_TASK_LOCK:
            _CLUSTER_TASK.update(id=_CLUSTER_TASK["id"] + 1, running=True, kind=kind, ok=None, msg="", stage="",
                                 started_at=time.time(), finished_at=0.0)
            task_id = _CLUSTER_TASK["id"]

        def worker():
            msg, ok = "集群操作失败", False
            try:
                msg, ok = run()
            finally:
                with _CLUSTER_TASK_LOCK:
                    if _CLUSTER_TASK["id"] == task_id:   # an interrupted check does not overwrite the leave
                        _CLUSTER_TASK.update(running=False, ok=ok, msg=msg, stage="", finished_at=time.time())

        threading.Thread(target=worker, name=f"cluster-{kind or 'task'}", daemon=True).start()
        return self.send(200, json.dumps({"ok": True, "running": True, "id": task_id}), "application/json; charset=utf-8")

    def cluster_task_status(self, s):
        with _CLUSTER_TASK_LOCK:
            t = dict(_CLUSTER_TASK)
        if t["running"]:
            payload = {"ok": True, "running": True, "id": t["id"], "kind": t["kind"], "stage": self.tr(t["stage"]) if t["stage"] else "",
                       "elapsed": int(time.time() - t["started_at"])}
        else:
            payload = {"ok": t["ok"] is not False, "running": False, "done": t["ok"] is not None, "id": t["id"], "kind": t["kind"],
                       "msg": t["msg"], "state": self.build_client_state(s)}
        return self.send(200, json.dumps(payload, ensure_ascii=False), "application/json; charset=utf-8")

    def do_cluster_add(self, s, form):
        def job():
            base = normalize_panel_url(form.get("url", ""))
            pw = str(form.get("password") or "")
            if not pw:
                raise ClusterError("请填写对方面板密码")
            with cluster_batch() as b:   # exchange with every panel first, then each applies once
                link, _ = cluster_pair(base, {"password": pw})
                rep = cluster_sync()
            if link["name"] in b.failed:
                return f"「{link['name']}」没能让新配置生效，已撤销这次互联，请稍后重试", False
            msg = f"已和「{link['name']}」双向互联，双方都已把对方写入服务端出站并立即生效"
            extra = "；".join(x for x in (cluster_report_text(rep), cluster_batch_text(b)) if x)
            return (f"{msg}；{extra}" if extra else msg), True
        return self._cluster_job(s, job, form, "add")

    def do_cluster_sync(self, s, form=None):
        def job():
            if not load_cluster()["links"]:
                with LOCK:   # no members: nothing can be waiting either (load_cluster already drops them)
                    save_cluster(load_cluster())
                return "集群里还没有其他面板", True
            with cluster_batch() as b:
                rep = cluster_sync()
            text = "；".join(x for x in (cluster_report_text(rep), cluster_batch_text(b)) if x)
            return text or "集群成员都在线，互联完整", True
        return self._cluster_job(s, job, form, "sync")

    def do_cluster_retry(self, s, form):
        """「重试」 on a member that failed: ask it again now; when it answers, 检查 fills in what is missing."""
        def job():
            st = load_cluster()
            x = _link_by(st, lid=str(form.get("id") or ""))
            if not x:
                return "集群成员不存在", False
            name = x.get("name", "")
            cluster_stage(f"正在检查「{name}」")
            try:
                cluster_call(x, "/api/cluster/status", {"name": local_node_name(), "url": local_cluster_url(), "version": VERSION},
                             timeout=20)
            except ClusterRemoteError as e:
                if e.code != "bad_token":
                    _update_link(x["instance"], ok=False, error=str(e))
                    return f"「{name}」仍然连接失败：{e}", False
            except ClusterError as e:
                _update_link(x["instance"], ok=False, error=str(e))
                return f"「{name}」仍然连接失败：{e}", False
            # it answered (or says it removed us): a full 检查 updates everything with one reload per panel
            with cluster_batch() as b:
                rep = cluster_sync()
            if not _link_by(load_cluster(), instance=x["instance"]):
                return f"「{name}」已把本机移出集群，本机这边也已删除", True
            extra = "；".join(t for t in (cluster_report_text({**rep, "offline": [n for n in rep["offline"] if n != name]}),
                                           cluster_batch_text(b)) if t)
            msg = f"已重新连上「{name}」"
            return (f"{msg}；{extra}" if extra else msg), True
        return self._cluster_job(s, job, form, "retry")

    def do_cluster_remove(self, s, form):
        def job():
            st = load_cluster()
            x = _link_by(st, lid=str(form.get("id") or ""))
            if not x:
                return "集群成员不存在", False
            others = [l for l in st["links"] if l["instance"] != x["instance"]]
            cluster_stage("本机正在删除互联")
            _drop_links({x["instance"]}, tombstone=True)
            missed = []
            for y in others:
                cluster_stage(f"正在通知「{y.get('name', '')}」")
                try:
                    cluster_call(y, "/api/cluster/forget", {"target": x["instance"]}, timeout=40)
                except ClusterError:
                    missed.append(y.get("name", ""))
            cluster_stage(f"正在通知「{x.get('name', '')}」")
            try:
                cluster_call(x, "/api/cluster/leave", {"all": "1"}, timeout=30)
            except ClusterError:
                missed.append(x.get("name", ""))
            name = x.get("name", "")
            if missed:
                return f"已把「{name}」移出集群；「{'、'.join(missed)}」暂时连接失败，恢复后在任意成员上点「检查」会自动清理", True
            return f"已把「{name}」移出集群，所有成员上和它的互联都已删除", True
        return self._cluster_job(s, job, form, "remove")

    def do_cluster_dismiss(self, s, form):
        """Hide a 等待互联 entry. Nothing changes on any panel; the next 检查 tries that panel again."""
        pid = str(form.get("id") or "")
        with LOCK:
            st = load_cluster()
            hit = [p for p in st["pending"] if cluster_pending_id(p) == pid]
            if not hit:
                return self.respond_mutation(s, "这条等待互联的记录已经不在了", True)
            st["pending"] = [p for p in st["pending"] if cluster_pending_id(p) != pid]
            save_cluster(st)
        return self.respond_mutation(s, f"已忽略「{hit[0].get('name', '')}」；下次点「检查」时会再试着和它互联", True)

    def do_cluster_leave_ui(self, s, form=None):
        def job():
            # This panel's config first; the members are told in the background (1.41)
            n, _ = cluster_leave_all(background=True)
            if not n:
                return "本机不在集群里", True
            return "本机已退出集群，正在后台通知其他成员", True
        return self._cluster_job(s, job, form, "leave")

    def do_discard_pending(self, s):
        with LOCK:
            try:
                discard_pending_reload()
            except Exception as e:
                return self.respond_mutation(s, f"丢弃草稿失败：{e}", False)
            try:
                refresh_template_if_flagged()   # an update that waited for the drafts lands now
            except Exception as e:
                sys.stderr.write(f"template refresh failed: {e}\n")
        run_snell_migration()
        return self.respond_mutation(s, "已丢弃待应用草稿", True)

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
                    return self.respond_mutation(s, "已关闭自定义服务端，已切换回默认服务端模板并应用生效。", True)
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
        # This baseline lives on the panel module; other save_* functions rebind it there.
        mod = sys.modules.get("panel") or sys.modules["__main__"]
        zh = {"reload": "应用配置"}[action]
        with LOCK:
            pending_st = load_pending_reload()
            # A pending new API secret / subscription token only becomes real after the new config
            # passed `mihomo -t` and the core accepted it; until then clashgate.env and panel.json keep
            # the old values, so a failed apply leaves everything as it was (the change stays pending).
            new_secret = pending_st.get("mihomo_secret") or ""
            new_token = pending_st.get("sub_token") or ""
            conf_backup = _read_or_none(CONF)
            custom_backup = _read_or_none(CUSTOM_CONF) if is_custom_config_mode() else None

            def restore():
                if conf_backup is not None:
                    atomic_write(CONF, conf_backup, 0o640)
                if custom_backup is not None:
                    atomic_write(CUSTOM_CONF, custom_backup, 0o640)

            if new_secret:
                env_draft = dict(read_env())
                env_draft["MIHOMO_SECRET"] = new_secret
                atomic_write(FRAG_CONTROLLER, render_controller_fragment(env_draft), 0o640)
                if custom_backup is not None:
                    updated_c = re.sub(r'^(\s*secret\s*:\s*).*$', f'\\1"{new_secret}"', custom_backup, flags=re.M)
                    atomic_write(CUSTOM_CONF, updated_c, 0o640)
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
            try:
                get_routing().ensure_seeded()
                get_routing().regenerate_frags()
            except Exception as e:
                restore()
                return self.respond_mutation(s, f"分流配置组装失败：{e}", False)
            atomic_write(CONF, assemble_config(), 0o640)
            rc, out = validate_config()
            if rc != 0:
                restore()
                return self.respond_mutation(s, f"配置校验未通过，未执行{zh}：" + out[-300:], False)
            new_specs = collect_ufw_specs(cur_nodes, cur_inbs)
            old_specs = mod._PENDING_UFW_BASELINE if mod._PENDING_UFW_BASELINE is not None else new_specs
            sync_ufw(old_specs, new_specs)
            mod._PENDING_UFW_BASELINE = new_specs
            # 1.43: the ports were checked right after `systemctl reload`, which returns before the core
            # has applied the file, so adding an inbound nearly always ended in a restart (every
            # connection dropped). reload_core waits for the ports first.
            rc, out = reload_core({int(n["port"]) for n in cur_nodes} | {int(i["port"]) for i in cur_inbs} | cluster_ports())
            if rc != 0:
                restore()
                run([SYSTEMCTL, "restart", "mihomo"])
            if rc == 0:
                if new_secret:
                    write_env_var("MIHOMO_SECRET", new_secret)
                if new_token:
                    self._commit_sub_token(new_token)
                clear_pending_reload()
                try:
                    os.remove(TEMPLATE_REFRESH_FLAG)   # assembled with the current template just now
                except OSError:
                    pass
                sync_client_files()
                wait_mihomo_ports()
        if rc == 0:
            run_snell_migration()
        _, active = run([SYSTEMCTL, "is-active", "mihomo"])
        state = STATE_ZH.get(active.strip(), (active.strip(), ""))[0]
        if rc == 0:
            return self.respond_mutation(s, f"{zh}成功，服务端配置与客户端订阅已同步生效（Mihomo 当前状态：{state}）", active.strip() == "active")
        return self.respond_mutation(s, f"{zh}失败：{out[-300:]}（Mihomo 当前状态：{state}）", False)

    def _commit_sub_token(self, new_token):
        self.cfg["sub_token"] = new_token
        if self.cfg_path:
            try:
                with open(self.cfg_path) as f:
                    disk_cfg = json.load(f)
            except Exception:
                disk_cfg = dict(self.cfg)
            disk_cfg["sub_token"] = new_token
            atomic_write(self.cfg_path, json.dumps(disk_cfg, indent=2, ensure_ascii=False) + "\n", 0o600)

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
        return self.respond_mutation(s, "已记录更换订阅链接，请点顶部「应用配置」生效（应用后旧订阅链接失效）。", True)

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
        return self.respond_mutation(s, "已生成新 Zashboard API 密钥，请点顶部「应用配置」生效（应用后直连地址才会更新）。", True)

    # Certificate jobs (renew / switch mode) can take up to 3 minutes (ACME, DNS propagation).
    # They run without the panel LOCK (certctl serializes itself with its flock), one at a time,
    # and with `async=1` in a background thread the browser polls (/api/cert-task-status).
    def _cert_job(self, s, form, job):
        if form.get("async") == "1" and self.is_ajax():
            with _CERT_TASK_LOCK:
                if _CERT_TASK["running"]:
                    return self.respond_mutation(s, "另一个证书任务正在运行，请稍后再试", False)
                _CERT_TASK.update(running=True, ok=None, msg="", detail="", started_at=time.time(), finished_at=0.0)

            def worker():
                try:
                    ok, msg, detail = job()
                except Exception as e:
                    ok, msg, detail = False, f"证书任务失败：{e}", ""
                with _CERT_TASK_LOCK:
                    _CERT_TASK.update(running=False, ok=ok, msg=msg, detail=detail, finished_at=time.time())

            threading.Thread(target=worker, name="cert-task", daemon=True).start()
            return self.send(200, json.dumps({"ok": True, "running": True}), "application/json; charset=utf-8")
        with _CERT_TASK_LOCK:
            if _CERT_TASK["running"]:
                return self.respond_mutation(s, "另一个证书任务正在运行，请稍后再试", False)
            _CERT_TASK["running"] = True
        try:
            ok, msg, detail = job()
        finally:
            with _CERT_TASK_LOCK:
                _CERT_TASK["running"] = False
        return self.respond_mutation(s, msg, ok, detail=detail)

    def cert_task_status(self, s):
        with _CERT_TASK_LOCK:
            t = dict(_CERT_TASK)
        if t["running"]:
            payload = {"ok": True, "running": True, "elapsed": int(time.time() - t["started_at"])}
        else:
            state = self.build_client_state(s)
            payload = {"ok": t["ok"] is not False, "running": False, "done": t["ok"] is not None,
                       "msg": t["msg"], "detail": t["detail"], "state": state}
        return self.send(200, json.dumps(payload, ensure_ascii=False), "application/json; charset=utf-8")

    def do_cert_action(self, s, form=None):
        def job():
            env = read_env()
            rc, out = run([resolve_certctl_path(), "renew"], timeout=180, env=certctl_env())
            tok = env.get("CF_TOKEN", "")
            if tok:
                out = out.replace(tok, "***")
            if rc == 0:
                return True, "证书检查 / 续期完成。", ""
            return False, friendly_error("证书申请 / 续期失败：")[0], raw_detail(out)
        return self._cert_job(s, form or {}, job)

    def do_cert_mode(self, s, form):
        mode = (form.get("cert_mode") or "dns").strip()
        if mode not in ("dns", "port", "manual"):
            return self.respond_mutation(s, "不支持的证书模式", False)
        if mode == "manual":
            return self.do_cert_manual(s)
        raw_token = (form.get("cf_token") if "cf_token" in form else form.get("token", "")).strip()
        if mode == "dns":
            if not raw_token:
                return self.respond_mutation(s, "请输入 Cloudflare API Token", False)
            if re.search(r'[\s"\'`$\\]', raw_token):
                return self.respond_mutation(s, "API Token 不能包含空格或引号", False)
        env = read_env()
        prev_mode = (env.get("CERT_MODE") or "port").strip()
        prev_token = env.get("CF_TOKEN", "")
        if mode == prev_mode and (mode != "dns" or raw_token == prev_token):
            return self.respond_mutation(s, "未切换证书模式，未重新生成证书。", False)

        def job():
            with LOCK:
                if mode == "dns":
                    write_env_var("CERT_MODE", "dns")
                    write_env_var("CF_TOKEN", raw_token)
                else:
                    write_env_var("CERT_MODE", "port")
            rc, out = run([resolve_certctl_path(), "reissue"], timeout=180, env=certctl_env())
            if raw_token:
                out = out.replace(raw_token, "***")
            with LOCK:
                if rc != 0:
                    write_env_var("CERT_MODE", prev_mode or "port")
                    if prev_mode == "dns" and prev_token:
                        write_env_var("CF_TOKEN", prev_token)
                    return False, cert_failure_message(out, mode), raw_detail(out)
                if prev_mode == "manual":
                    enable_cert_renew_timer()
            return True, "已切换并重新生成证书。", ""
        return self._cert_job(s, form, job)

    def do_cert_manual(self, s):
        """Switch to (or re-check) the manual certificate placed in /etc/clashgate/certs/."""
        cert_dir = CS_ROOT + "/certs"
        with _CERT_TASK_LOCK:
            if _CERT_TASK["running"]:
                return self.respond_mutation(s, "另一个证书任务正在运行，请稍后再试", False)
        with LOCK:
            env = read_env()
            prev_mode = (env.get("CERT_MODE") or "port").strip()
            lock_fd = cert_task_lock()
            if lock_fd is False:
                return self.respond_mutation(s, "另一个证书任务正在运行，请稍后再试", False)
            try:
                try:
                    info = check_manual_cert(cert_dir, env.get("DOMAIN", ""))
                    install_manual_cert(cert_dir, info["crt"], info["key"])
                except ManualCertError as e:
                    return self.respond_mutation(s, str(e), False)
                if prev_mode != "manual":
                    write_env_var("CERT_MODE", "manual")
                    # Manual certificates are never renewed by acme.sh; stop the hourly job.
                    run([SYSTEMCTL, "disable", "--now", "clashgate-cert.timer"], timeout=30)
            finally:
                if lock_fd is not None:
                    os.close(lock_fd)
            # The panel reloads its certificate when the files change; Mihomo needs a restart.
            restart_mihomo_for_cert()
        days = info["days"] if info["days"] is not None else "—"
        if prev_mode == "manual":
            msg = "手动证书校验通过，已重新加载（颁发者：{}，到期：{}，剩余 {} 天）"
        else:
            msg = "已切换为手动证书（颁发者：{}，到期：{}，剩余 {} 天）"
        return self.respond_mutation(s, msg.format(info["issuer"], info["expires"], days), True)

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
        if raw_kind == "vless-reality" and (form.get("sni") or "").strip():
            # A typed Reality SNI must work from here (checked outside LOCK: it is a network round trip).
            try:
                check_reality_dest(resolve_sni(form))
            except ValueError as e:
                detail = str(e.args[1]) if len(e.args) > 1 else ""
                return self.respond_mutation(s, f"添加失败：{e.args[0]}", False, detail=detail)
        with LOCK:
            now = time.time()
            for k in [k for k, v in _RECENT_ADD_REQS.items() if now - v[0] > 60]:
                _RECENT_ADD_REQS.pop(k, None)
            if req_id and req_id in _RECENT_ADD_REQS:
                prev_inb = _RECENT_ADD_REQS[req_id][1]
                return self.respond_mutation(
                    s,
                    f"已添加 {KIND_ZH.get(prev_inb['kind'], prev_inb['kind'])} 节点「{prev_inb['name']}」（端口 {prev_inb['port']}），已保存，请点顶部「应用配置」生效",
                    True,
                )
            cur = load_inbounds()
            target_name = raw_name or DEFAULT_NODE_NAMES.get(raw_kind, raw_kind)
            if any(existing.get("name") == target_name for existing in cur):
                return self.respond_mutation(s, "节点名称重复，添加失败", False)
            try:
                # 1.44: with custom server on, the locked options may be typed in (adv_*); blank = default
                inb = build_inbound(raw_kind, form, env, advanced=bool(load_panel_settings().get("custom_server_enabled")))
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
            f"已添加 {KIND_ZH.get(inb['kind'], inb['kind'])} 节点「{inb['name']}」（端口 {inb['port']}），已保存，请点顶部「应用配置」生效",
            True,
        )

    def do_delete(self, s, iid):
        with LOCK:
            _RECENT_ADD_REQS.clear()
            cur = load_inbounds()
            removed = [i for i in cur if i["id"] == iid]
            new = [i for i in cur if i["id"] != iid]
            if len(new) == len(cur):
                return self.respond_mutation(s, "入站节点不存在", False)
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
        return self.respond_mutation(s, "节点删除成功，应用配置后生效", True)

    def do_delete_node(self, s, name):
        with LOCK:
            _RECENT_ADD_REQS.clear()
            cur = read_nodes()
            removed = [n for n in cur if n["name"] == name]
            new = [n for n in cur if n["name"] != name]
            if len(new) == len(cur):
                return self.respond_mutation(s, "入站节点不存在", False)
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
        return self.respond_mutation(s, f"已删除节点「{name}」，请点顶部「应用配置」生效", True)

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
        return self.respond_mutation(s, f"已重置节点「{name}」的 UUID、Reality 私钥与 VLESS 加密密钥，应用配置后生效", True)

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
        return self.respond_mutation(s, "密码重置成功，应用配置后生效", True)

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
        return self.respond_mutation(s, f"已添加 {len(added)} 个服务端出站（{names}），已保存，请点顶部「应用配置」生效", True)

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
        return self.respond_mutation(s, f"已删除节点「{name}」，请点顶部「应用配置」生效", True)

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
            s, f"已导入订阅源「{prov_name}」（路径 {entry['path']}），已保存，请点顶部「应用配置」生效", True)

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
        return self.respond_mutation(s, f"已删除订阅源「{name}」，请点顶部「应用配置」生效", True)


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
        return self.respond_mutation(s, f"已添加分流组「{entry['name']}」，已保存，请点顶部「应用配置」生效", True)

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
        return self.respond_mutation(s, f"已引入分流组「{entry['name']}」，已保存，请点顶部「应用配置」生效", True)

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
        return self.respond_mutation(s, f"已删除分流组「{name}」，请点顶部「应用配置」生效", True)

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
        return self.respond_mutation(s, f"已重命名分流组为「{new_name}」，请点顶部「应用配置」生效", True)

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
        return self.respond_mutation(s, f"{detail.lstrip('+- ')}，请点顶部「应用配置」生效", True)

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
        return self.respond_mutation(s, "已调整分流顺序，请点顶部「应用配置」生效", True)

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
        return self.respond_mutation(s, f"已更新分流组「{name}」规则，请点顶部「应用配置」生效", True)

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
            # 1.41: back on the template, so custom mode is turned off too (Settings shows it off)
            save_panel_settings({"custom_server_enabled": False})
        return self.respond_mutation(s, "已恢复默认服务端模板并关闭自定义服务端，已生成新的默认 VlessReality 节点，请在客户端更新订阅。", True)

    # -- views
    def login_page(self, err=""):
        err = self.tr(err)
        mver = get_mihomo_version_num()
        boot = {"page": "login", "version": VERSION, "mihomo_version": mver, "login_error": err,
                "default_lang": cli_default_lang()}
        return render_spa_html(self.tr("登录 · ClashGate"), boot, self.noscript_notice())

    def noscript_notice(self) -> str:
        """Shown only when the browser has JavaScript turned off (the panel is a Vue app)."""
        return ("<div style='max-width:28rem;margin:4rem auto;padding:1.5rem;font:14px/1.6 system-ui,sans-serif;"
                "color:#1a2330;background:#fff;border:1px solid #dbe3ee;border-radius:1rem'>"
                f"<b>ClashGate</b><p>{html.escape(self.tr('管理面板需要浏览器开启 JavaScript，请开启后刷新页面。'))}</p></div>")

    def dashboard(self, s, initial_tab="inbounds"):
        q = parse_qs(urlparse(self.path).query)
        msg, ok = q.get("msg", [""])[0], q.get("ok", ["1"])[0] == "1"
        tab_q = q.get("tab", [""])[0]
        if tab_q in ("inbounds", "outbounds", "readable", "advanced", "certs", "settings", "cluster", "about"):
            initial_tab = tab_q
        env = read_env()
        st = mihomo_status()
        state = self.build_client_state(s, env, st)
        boot = {
            "page": "dashboard",
            "initial_tab": initial_tab,
            "flash_msg": msg,
            "flash_ok": ok,
            "default_lang": cli_default_lang(env),
            **state,
        }
        return render_spa_html("ClashGate", boot, self.noscript_notice())


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
    try:
        with LOCK:
            reconcile_pending_with_live()   # before the Snell migration, which waits for no drafts
            refresh_template_if_flagged()
    except Exception as e:
        sys.stderr.write(f"pending reconcile failed: {e}\n")
    try:
        if reformat_flow_entries():
            sys.stderr.write("config.yaml: entries rewritten as multi-line YAML (same content, no reload)\n")
    except Exception as e:
        sys.stderr.write(f"config reformat failed: {e}\n")
    try:
        if refresh_cluster_fragments():
            sys.stderr.write("cluster links updated: members are exits only (no loops)\n")
    except Exception as e:
        sys.stderr.write(f"cluster refresh failed: {e}\n")
    try:
        start_cluster_migration()   # 1.42: links with their own inbound move to the shared one
    except Exception as e:
        sys.stderr.write(f"cluster migration not started: {e}\n")
    start_traffic_poller(30)
    refresh_update_check_for_version()
    start_weekly_update_check()
    threading.Thread(target=run_snell_migration, name="snell-v6-migration", daemon=True).start()
    threading.Thread(target=ensure_geodata, name="geodata", daemon=True).start()
    host = cfg.get("listen", "0.0.0.0")
    if host == "0.0.0.0" and ipv6_only():
        host = "::"   # IPv6-only server: listen on both stacks (Linux default bindv6only=0)
    addr = (host, int(cfg.get("port", 8443)))
    six = {"address_family": socket.AF_INET6} if ":" in host else {}
    if cfg.get("tls_cert"):
        cert_p = ROOT + cfg["tls_cert"]
        key_p = ROOT + cfg["tls_key"]
        if not os.path.isfile(cert_p) and os.path.isfile(ROOT + CERT):
            cert_p, key_p = ROOT + CERT, ROOT + KEY
        httpd = type("TLSServer6", (TLSServer,), six)(addr, Panel, cert_p, key_p) if six else TLSServer(addr, Panel, cert_p, key_p)
        scheme = "https"
    else:   # local development only
        httpd = type("HTTPServer6", (ThreadingHTTPServer,), six)(addr, Panel) if six else ThreadingHTTPServer(addr, Panel)
        scheme = "http"
    sys.stderr.write(f"clashgate v{VERSION} listening on {scheme}://{addr[0]}:{addr[1]}\n")
    httpd.serve_forever()


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("hash-password")
    sub.add_parser("cluster-leave")
    sp = sub.add_parser("serve")
    sp.add_argument("--config", required=True)
    a = ap.parse_args()
    if a.cmd == "hash-password":
        pw = sys.stdin.readline().rstrip("\n")
        if len(pw) < 8:
            sys.exit("密码太短（至少 8 位）")
        print(hash_password(pw))
    elif a.cmd == "cluster-leave":
        # Used by `clashgate uninstall` / reinstall: leave the cluster first so the other members drop
        # their links to this server. Prints "<links>\t<unreachable names, comma separated>".
        if not load_cluster()["links"]:
            print("0\t")
            return
        with _CLUSTER_OP_LOCK:
            n, missed = cluster_leave_all()
        print(f"{n}\t{','.join(missed)}")
    else:
        serve(a.config)

