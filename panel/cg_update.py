"""Traffic stats, core updates, and panel self-upgrade. Moved out of panel.py unchanged."""
import gzip
import json
import os
import re
import shlex
import shutil
import socket
import ssl
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import parse_qs, urlparse, quote


def bind():
    """Copy panel constants and helpers after panel.py has finished loading."""
    mod = sys.modules.get("panel") or sys.modules.get("__main__")
    g = globals()
    for key, val in mod.__dict__.items():
        if key.startswith("__") or key in g:
            continue
        g[key] = val


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
    while len(nums) > 1 and nums[-1] == 0:  # 1.15.0 == 1.15, so "1.15.0" is never offered over 1.15
        nums.pop()
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


def mihomo_supports_snell_v6(bin_path: str = "") -> bool:
    """Snell v6 needs Mihomo >= SNELL_V6_MIN_CORE; unreadable version counts as unsupported."""
    if bin_path:
        try:
            _, out = run([bin_path, "-v"], timeout=5)
        except Exception:
            out = ""
        m = re.search(r"\bv?(\d+\.\d+(?:\.\d+)*)\b", (out.splitlines() or [""])[0])
        ver = m.group(1) if m else ""
    else:
        ver = get_local_mihomo_version().lstrip("vV")
    return bool(ver) and parse_version_tuple(ver) >= parse_version_tuple(SNELL_V6_MIN_CORE)


_SNELL_V5_DEFAULT_NAME = re.compile(r"SnellV5(-\d+)?")


def _snell_needs_v6(inb: dict) -> bool:
    lst = inb.get("listener") if isinstance(inb, dict) else None
    if inb.get("kind") != "snell" or not isinstance(lst, dict) or str(lst.get("type")) != "snell":
        return False
    try:
        return int(lst.get("version") or 4) != SNELL_VERSION
    except (TypeError, ValueError):
        return False


def _name_used_in_routing(name: str) -> bool:
    """True if a routing rule may reference this inbound name (e.g. IN-NAME); then keep it."""
    paths = [FRAG_RULES, ROUTING_JSON]
    try:
        paths += [os.path.join(ROUTING_DIR, f) for f in os.listdir(ROUTING_DIR)]
    except OSError:
        pass
    pat = re.compile(r"(?<![A-Za-z0-9._-])" + re.escape(name) + r"(?![A-Za-z0-9._-])")
    for p in paths:
        try:
            with open(p, errors="replace") as f:
                if pat.search(f.read()):
                    return True
        except OSError:
            continue
    return False


def migrate_snell_to_v6() -> int:
    """Upgrade panel-managed Snell (v4/v5) inbounds to Snell v6 and apply it live.

    v6 servers do not accept v5 clients, so the listener and the subscription client
    change together. Skipped (retried later) when: custom server config is active
    (user-owned YAML), the core is older than v1.19.34, or unsaved drafts exist
    (applying now would also push the user's drafts). Returns the number migrated.
    """
    if is_custom_config_mode():
        return 0
    inbs = load_inbounds()
    targets = [i for i in inbs if _snell_needs_v6(i)]
    if not targets:
        return 0
    if not mihomo_supports_snell_v6():
        sys.stderr.write(f"snell v6 migration deferred: Mihomo core older than v{SNELL_V6_MIN_CORE}\n")
        return 0
    st = load_pending_reload()
    if st.get("items") or st.get("sub_token") or st.get("mihomo_secret"):
        sys.stderr.write("snell v6 migration deferred: unsaved drafts pending reload\n")
        return 0
    env = read_env()
    names = {i.get("name") for i in inbs} | {n["name"] for n in read_nodes()}
    for inb in targets:
        lst = dict(inb["listener"])
        lst["version"] = SNELL_VERSION
        lst.pop("obfs-opts", None)       # v6 rejects http/tls simple-obfs
        lst.pop("mode", None)            # default traffic-shaping mode
        psk = str(lst.get("psk") or "")
        if not SNELL_V6_PSK_LEN[0] <= len(psk.encode()) <= SNELL_V6_PSK_LEN[1]:
            lst["psk"] = new_snell_psk()
        old = str(inb.get("name") or "")
        if _SNELL_V5_DEFAULT_NAME.fullmatch(old) and not _name_used_in_routing(old):
            new = old.replace("SnellV5", "SnellV6", 1)
            if new not in names:
                names.discard(old)
                names.add(new)
                inb["name"] = lst["name"] = new
        inb["listener"] = lst
        server = str((inb.get("client") or {}).get("server") or env.get("SERVER_IP", ""))
        inb["client"] = snell_client_from_listener(lst, inb["name"], server)
    backup = _snapshot_files((INBOUNDS, FRAG_EXTRA, CONF))
    try:
        cleaned = _dedup_inbounds(inbs)
        atomic_write(INBOUNDS, _json_text(cleaned), 0o600)
        atomic_write(FRAG_EXTRA, render_extra(cleaned), 0o640)
        atomic_write(CONF, assemble_config(), 0o640)
        rc, out = validate_config()
        if rc != 0:
            raise RuntimeError("mihomo -t: " + out[-400:])
        rc, out = run([SYSTEMCTL, "restart", "mihomo"])
        if rc != 0:
            raise RuntimeError("restart: " + out[-400:])
    except Exception as e:
        _restore_files(backup)
        run([SYSTEMCTL, "restart", "mihomo"])
        sys.stderr.write(f"snell v6 migration failed, rolled back: {e}\n")
        return 0
    sync_client_files()
    wait_mihomo_ports()
    sys.stderr.write(f"snell v6 migration: upgraded {len(targets)} inbound(s)\n")
    return len(targets)


def run_snell_migration():
    """Locked wrapper; never raises (called from startup, reload, discard and core update)."""
    try:
        with LOCK:
            return migrate_snell_to_v6()
    except Exception as e:
        sys.stderr.write(f"snell v6 migration error: {e}\n")
        return 0


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


def _normalize_update_channel(raw: str) -> str:
    ch = (raw or "").strip().lower()
    if ch in ("stable", "production", "正式"):
        return "stable"
    if ch in ("test", "beat", "测试"):
        return "test"
    return ""


def resolve_update_channel(env: dict = None, settings: dict = None) -> str:
    """Return stable|test. Default stable; legacy ClashGateBeat installs map to test."""
    if settings is None:
        settings = load_panel_settings()
    ch = _normalize_update_channel(settings.get("update_channel") or "")
    if ch:
        return ch
    if env is None:
        env = read_env()
    env_ch = _normalize_update_channel(env.get("UPDATE_CHANNEL") or os.environ.get("UPDATE_CHANNEL") or "")
    if env_ch:
        return env_ch
    name = (os.environ.get("REPO_NAME") or env.get("REPO_NAME") or "").strip()
    if name.endswith("Beat"):
        return "test"
    # Installed from the test branch without an explicit channel: the CLI already updates from
    # REPO_BRANCH=test, so the panel must report (and check) the same channel.
    if (env.get("REPO_BRANCH") or "").strip() == "test":
        return "test"
    return "stable"


def resolve_update_target(env: dict = None, settings: dict = None) -> dict:
    """Resolve repo/branch for the active update channel."""
    if env is None:
        env = read_env()
    channel = resolve_update_channel(env, settings)
    meta = dict(UPDATE_CHANNEL_MAP[channel])
    # Until the user explicitly picks a channel, keep downloading from the installed Beat repo.
    settings = settings if settings is not None else load_panel_settings()
    explicit = _normalize_update_channel(settings.get("update_channel") or "")
    env_ch = _normalize_update_channel(env.get("UPDATE_CHANNEL") or "")
    name = (os.environ.get("REPO_NAME") or env.get("REPO_NAME") or "").strip()
    if not explicit and not env_ch and name.endswith("Beat"):
        owner = os.environ.get("REPO_OWNER") or env.get("REPO_OWNER") or "ClashGate"
        return {
            "channel": "test",
            "owner": owner,
            "name": name,
            "branch": (env.get("REPO_BRANCH") or "main").strip() or "main",
            "label": "测试",
            "slug": f"{owner}/{name}",
            "legacy_beat": True,
        }
    slug = f"{meta['owner']}/{meta['name']}"
    return {
        "channel": channel,
        "owner": meta["owner"],
        "name": meta["name"],
        "branch": meta["branch"],
        "label": meta["label"],
        "slug": slug,
        "legacy_beat": False,
    }


def apply_update_channel_env(channel: str):
    """Persist channel choice into panel_settings + clashgate.env (retires Beat when set)."""
    ch = _normalize_update_channel(channel)
    if ch not in UPDATE_CHANNEL_MAP:
        raise ValueError("invalid update channel")
    meta = UPDATE_CHANNEL_MAP[ch]
    save_panel_settings({"update_channel": ch})
    write_env_var("UPDATE_CHANNEL", ch)
    write_env_var("REPO_OWNER", meta["owner"])
    write_env_var("REPO_NAME", meta["name"])
    write_env_var("REPO_SLUG", f"{meta['owner']}/{meta['name']}")
    write_env_var("REPO_BRANCH", meta["branch"])
    return resolve_update_target()


def fetch_channel_commit_sha(slug: str, branch: str) -> str:
    url = f"https://api.github.com/repos/{slug}/commits/{branch}"
    txt = _http_get_text(url, timeout=20, headers={"Accept": "application/vnd.github+json"})
    data = json.loads(txt)
    sha = str(data.get("sha") or "")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise RuntimeError("未能从 GitHub 解析通道提交")
    return sha


def fetch_channel_tip() -> dict:
    """Fetch CS_VERSION + tip SHA for the active update channel."""
    target = resolve_update_target()
    slug = target["slug"]
    branch = target["branch"]
    url = os.environ.get(
        "CLASHGATE_RAW_COMMON",
        f"https://raw.githubusercontent.com/{slug}/{branch}/scripts/lib/common.sh",
    )
    txt = ""
    if "CLASHGATE_RAW_COMMON" not in os.environ:
        # raw.githubusercontent.com/<branch>/ is CDN-cached ~5 min; read at the tip commit instead.
        try:
            commit = fetch_channel_commit_sha(slug, branch)
            if commit:
                txt = _http_get_text(f"https://raw.githubusercontent.com/{slug}/{commit}/scripts/lib/common.sh", timeout=20)
        except Exception:
            txt = ""
    if not txt:
        txt = _http_get_text(url, timeout=20)
    m = re.search(r"^CS_VERSION=([0-9A-Za-z._-]+)", txt, re.M)
    if not m:
        raise RuntimeError("未能从 GitHub 解析最新版本号")
    version = m.group(1).strip()
    sha = ""
    msha = re.search(r"^CS_SOURCE_SHA=([0-9A-Za-z._-]{4,80})", txt, re.M)
    if msha:
        # Marker + version so every version bump is visible on the test channel.
        sha = f"{msha.group(1).strip()}+{version}"
    if not sha:
        try:
            sha = fetch_channel_commit_sha(slug, branch)
        except Exception:
            sha = ""
    return {
        "version": version,
        "sha": sha,
        "slug": slug,
        "branch": branch,
        "channel": target["channel"],
        "label": target["label"],
    }


def _upgrade_log_tail(n: int = 4) -> str:
    try:
        with open(UPGRADE_LOG, errors="replace") as f:
            lines = [re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", l).strip() for l in f.read().splitlines()]
        return " | ".join(l for l in lines if l)[-300:] if lines else ""
    except Exception:
        return ""


def load_upgrade_status() -> dict:
    try:
        with open(UPGRADE_STATUS_JSON) as f:
            d = json.load(f)
        d = d if isinstance(d, dict) else {}
    except Exception:
        d = {}
    if d.get("state") == "done" and not d.get("tail"):
        d["tail"] = _upgrade_log_tail()
    return d


def start_upgrade_job(cmd_bin: str) -> str:
    """Launch the self-update outside the panel's cgroup. Returns error text or ''."""
    started = int(time.time())
    atomic_write(UPGRADE_STATUS_JSON, json.dumps({"state": "running", "started_at": started, "from": VERSION}) + "\n", 0o600)
    st, lg = shlex.quote(UPGRADE_STATUS_JSON), shlex.quote(UPGRADE_LOG)
    # Status JSON carries only numbers; the log tail is read (ANSI-stripped) in Python.
    # (Embedding raw log text broke the JSON — ANSI escapes / '%' — so the UI never saw "done".)
    script = (
        f"sleep 1; bash {shlex.quote(cmd_bin)} update > {lg} 2>&1; rc=$?; "
        f"printf '{{\"state\":\"done\",\"rc\":%d,\"started_at\":{started},\"finished_at\":%d}}\\n' "
        f"$rc $(date +%s) > {st}.tmp && mv -f {st}.tmp {st}"
    )
    # Pass the channel's tarball explicitly so older local scripts (whose default
    # REPO_TARBALL wrongly counted as a pin) still download the selected branch.
    try:
        tgt = resolve_update_target()
        pin = (f"REPO_BRANCH={shlex.quote(tgt['branch'])} "
               f"REPO_TARBALL={shlex.quote('https://github.com/' + tgt['slug'] + '/archive/refs/heads/' + tgt['branch'] + '.tar.gz')} ")
        script = script.replace(f"bash {shlex.quote(cmd_bin)} update", f"{pin}bash {shlex.quote(cmd_bin)} update", 1)
    except Exception:
        pass
    unit = f"clashgate-upgrade-{started}"
    try:
        if shutil.which("systemd-run"):
            rc, out = run(["systemd-run", "--unit", unit, "--collect", "--quiet",
                           "-p", "KillMode=process", "/bin/bash", "-c", script], timeout=15)
            if rc == 0:
                return ""
        subprocess.Popen(["setsid", "/bin/bash", "-c", script], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return ""
    except Exception as e:
        atomic_write(UPGRADE_STATUS_JSON, json.dumps({"state": "done", "rc": 127, "started_at": started, "tail": str(e)}) + "\n", 0o600)
        return str(e)


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


def _blank_update_slot(current: str = "") -> dict:
    return {"checked_at": 0, "current": current, "latest": "", "has_update": False}


def load_update_check() -> dict:
    data = {
        "core": _blank_update_slot(),
        "panel": _blank_update_slot(VERSION),
        "auto_applied_at": 0,
    }
    try:
        with open(UPDATE_CHECK_JSON) as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            for key in ("core", "panel"):
                slot = raw.get(key)
                if isinstance(slot, dict):
                    data[key].update({
                        "checked_at": int(slot.get("checked_at") or 0),
                        "current": str(slot.get("current") or data[key]["current"]),
                        "latest": str(slot.get("latest") or ""),
                        "has_update": bool(slot.get("has_update")),
                    })
            try:
                data["auto_applied_at"] = int(raw.get("auto_applied_at") or 0)
            except (TypeError, ValueError):
                data["auto_applied_at"] = 0
    except Exception:
        pass
    return data


def save_update_check(data: dict):
    atomic_write(UPDATE_CHECK_JSON, json.dumps(data, ensure_ascii=False, indent=2) + "\n", 0o600)


def public_update_check(core_current: str = "") -> dict:
    """Cached check results for the UI. has_update is re-checked against what is
    installed now, so a result recorded before an upgrade (CLI or panel) never
    keeps showing an update that is already applied."""
    data = load_update_check()
    installed = {"core": (core_current or "").lstrip("vV"), "panel": VERSION}
    out = {}
    for key in ("core", "panel"):
        slot = data[key]
        latest = str(slot.get("latest") or "").lstrip("vV")
        current = installed[key] or str(slot.get("current") or "").lstrip("vV")
        # Only a strictly newer release than the installed build counts; a missing side means no badge.
        has = bool(slot.get("has_update") and latest and current
                   and parse_version_tuple(latest) > parse_version_tuple(current))
        out[key] = {
            "checked_at": int(slot.get("checked_at") or 0),
            "current": current,
            "latest": latest,
            "has_update": has,
        }
    return out


def refresh_update_check_for_version():
    """Run at startup: a cached panel check recorded by another build (i.e. before an
    upgrade or downgrade) is re-evaluated against this VERSION and stamped with it, so the
    stored file never keeps claiming an update that is already installed."""
    data = load_update_check()
    slot = data["panel"]
    if str(slot.get("current") or "").lstrip("vV") == VERSION:
        return False
    latest = str(slot.get("latest") or "").lstrip("vV")
    slot["current"] = VERSION
    slot["has_update"] = bool(latest and parse_version_tuple(latest) > parse_version_tuple(VERSION))
    try:
        save_update_check(data)
    except Exception as e:
        sys.stderr.write(f"update check cache refresh failed: {e}\n")
    return True


def _update_due(slot: dict) -> bool:
    try:
        ts = float(slot.get("checked_at") or 0)
    except (TypeError, ValueError):
        ts = 0
    return time.time() - ts >= UPDATE_CHECK_INTERVAL


def record_core_check(current: str, latest: str, has_update: bool):
    data = load_update_check()
    data["core"] = {
        "checked_at": int(time.time()),
        "current": (current or "").lstrip("vV"),
        "latest": (latest or "").lstrip("vV"),
        "has_update": bool(has_update),
    }
    save_update_check(data)


def record_panel_check(latest: str, has_update: bool, tip_sha: str = ""):
    data = load_update_check()
    data["panel"] = {
        "checked_at": int(time.time()),
        "current": VERSION,
        "latest": (latest or "").lstrip("vV"),
        "has_update": bool(has_update),
        "latest_sha": (tip_sha or ""),
    }
    save_update_check(data)


def check_core_update() -> bool:
    """Compare the local core with the latest stable Mihomo release; record and return has_update."""
    current = get_local_mihomo_version().lstrip("vV")
    latest = str(fetch_latest_mihomo_release().get("tag_name") or "").lstrip("vV")
    has = bool(current and latest and parse_version_tuple(latest) > parse_version_tuple(current))
    record_core_check(current, latest, has)
    return has


def check_panel_update() -> dict:
    """Read the channel tip's CS_VERSION; only a strictly newer version counts (a stale
    raw cache must never offer an older/equal build). Records and returns the tip + has_update."""
    tip = fetch_channel_tip()
    latest = tip["version"].lstrip("vV")
    has = parse_version_tuple(latest) > parse_version_tuple(VERSION)
    record_panel_check(latest, has, tip_sha=tip.get("sha") or "")
    return {**tip, "version": latest, "has_update": has}


def _check_due_updates():
    data = load_update_check()
    if _update_due(data["core"]):
        try:
            check_core_update()
        except Exception as e:
            sys.stderr.write(f"mihomo version check failed: {e}\n")
    if _update_due(data["panel"]):
        try:
            check_panel_update()
        except Exception as e:
            sys.stderr.write(f"clashgate version check failed: {e}\n")


def _apply_auto_update():
    """When enabled, upgrade the panel once a week. `clashgate update` also upgrades Mihomo."""
    if not load_panel_settings().get("auto_update"):
        return
    data = load_update_check()
    try:
        last = float(data.get("auto_applied_at") or 0)
    except (TypeError, ValueError):
        last = 0
    if time.time() - last < UPDATE_CHECK_INTERVAL:
        return
    try:
        core_has = check_core_update()
    except Exception as e:
        sys.stderr.write(f"auto update core check failed: {e}\n")
        core_has = bool(load_update_check()["core"].get("has_update"))
    try:
        panel_has = check_panel_update()["has_update"]
    except Exception as e:
        sys.stderr.write(f"auto update panel check failed: {e}\n")
        panel_has = bool(load_update_check()["panel"].get("has_update"))
    data = load_update_check()
    if not core_has and not panel_has:
        data["auto_applied_at"] = int(time.time())
        save_update_check(data)
        return
    cmd_bin = CLASHGATE_BIN if os.path.isfile(CLASHGATE_BIN) else "/usr/local/bin/clashgate"
    if not os.path.isfile(cmd_bin):
        sys.stderr.write("auto update skipped: clashgate command not installed\n")
        data["auto_applied_at"] = int(time.time())
        save_update_check(data)
        return
    # Mark first: the update restarts this service, so nothing after it would run.
    data["auto_applied_at"] = int(time.time())
    save_update_check(data)
    err = start_upgrade_job(cmd_bin)
    if err:
        sys.stderr.write(f"auto update failed to start: {err}\n")
        return
    sys.stderr.write("auto update started (detached): panel and mihomo core\n")


def start_weekly_update_check():
    """Check versions weekly. If auto-update is on, apply a panel+core upgrade once a week."""
    def _loop():
        while True:
            try:
                _check_due_updates()
                _apply_auto_update()
            except Exception as e:
                sys.stderr.write(f"weekly update check failed: {e}\n")
            time.sleep(3600)
    threading.Thread(target=_loop, name="update-check", daemon=True).start()


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
        record_core_check(local_ver, latest_tag, False)
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
    old_bin = bin_path + ".old"
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
        # Validate the live config with the NEW binary before swapping it in, so a
        # failed check leaves the working core untouched.
        rc, out = validate_config(bin_path=tmp_bin)
        if rc != 0:
            raise RuntimeError("配置校验失败（mihomo -t），已保留原内核：" + out[-300:])
        if os.path.isfile(bin_path):
            shutil.copy2(bin_path, old_bin)
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

    rc, out = run([SYSTEMCTL, "restart", "mihomo"])
    if rc != 0:
        if os.path.isfile(old_bin):
            os.replace(old_bin, bin_path)
            run([SYSTEMCTL, "restart", "mihomo"])
        raise RuntimeError("重启 Mihomo 失败，已恢复原内核：" + out[-300:])
    if os.path.exists(old_bin):
        os.remove(old_bin)
    wait_mihomo_ports()
    try:
        migrate_snell_to_v6()   # caller holds LOCK; picks up Snell inbounds deferred for an old core
    except Exception as e:
        sys.stderr.write(f"snell v6 migration error: {e}\n")
    changed = True
    if local_ver:
        msg = f"Mihomo 内核已从 {local_ver} 更新至 {latest_tag} 并重启生效。"
    else:
        msg = f"Mihomo 内核已更新至 {latest_tag} 并重启生效。"
    record_core_check(latest_tag, latest_tag, False)
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

