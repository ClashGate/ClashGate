"""ClashGate panel tests: run against a throw-away fake /etc/clashgate tree.

Needs a Mihomo binary for `mihomo -t` (MIHOMO_BIN, default tests/.cache/mihomo; tests/run.sh
downloads the pinned version). Run: python3 -m unittest discover -s tests -v
"""
import json
import io
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import guardlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
MIHOMO = os.environ.get("MIHOMO_BIN") or os.path.join(HERE, ".cache", "mihomo")
if not os.path.isfile(MIHOMO):
    raise SystemExit(f"Mihomo binary not found at {MIHOMO} (set MIHOMO_BIN or run tests/run.sh)")

ROOT = tempfile.mkdtemp(prefix="cg-test-")
os.environ.update(CLASHGATE_ROOT=ROOT, MIHOMO_BIN=MIHOMO, SYSTEMCTL="true",
                  UFW_BIN="false", FIREWALL_CMD_BIN="false")
CS = ROOT + "/etc/clashgate"
os.makedirs(CS + "/certs")
shutil.copytree(os.path.join(REPO, "resources"), CS + "/resources")
GEO_CACHE = os.environ.get("CG_TEST_GEO_DIR", "")   # tests/run.sh fills it once
for _g in os.listdir(GEO_CACHE) if GEO_CACHE else []:
    shutil.copy(os.path.join(GEO_CACHE, _g), CS + "/" + _g)
sys.path.insert(0, os.path.join(REPO, "panel"))
import panel as P  # noqa: E402

with open(CS + "/clashgate.env", "w") as f:
    f.write('MODE="auto-cert"\nSERVER_IP="1.2.3.4"\nDOMAIN="ex.sslip.io"\nPANEL_PORT="25183"\n'
            'CONTROLLER_PORT="25184"\nMIHOMO_SECRET="test-secret"\n')
for name in ("fullchain.pem", "privkey.pem"):
    with open(CS + "/certs/" + name, "w") as f:
        f.write("placeholder\n")


def read(p, **kw):
    with open(p, **kw) as f:
        return f.read()


def frontend_script_text():
    """App.vue plus every JS/Vue module under panel/web/src, so JS-mirror tests survive splits."""
    root = os.path.join(REPO, "panel/web/src")
    parts = []
    for dirpath, _, files in os.walk(root):
        for fn in sorted(files):
            if fn.endswith((".js", ".vue")):
                parts.append(read(os.path.join(dirpath, fn)))
    return "\n".join(parts)


def mihomo_t(path, home=None):
    home = home or tempfile.mkdtemp()
    os.makedirs(home + "/ui", exist_ok=True)
    r = subprocess.run([MIHOMO, "-t", "-d", home, "-f", path], capture_output=True, text=True, timeout=180)
    return r.returncode, (r.stdout + r.stderr)[-800:]


def write_default_state(extra_kinds=()):
    env = P.read_env()
    P._write_template_state([], [], [], {}, env)  # build_inbound checks ports against current state
    node = P.new_default_reality_node(env)
    inbs = []
    port = 30100
    for kind in extra_kinds:
        port += 1
        inbs.append(P.build_inbound(kind, {"port": str(port), "name": f"{kind}-t"}, env))
    P._write_template_state([node], inbs, [], {}, env)
    return node, inbs


class VersionTest(unittest.TestCase):
    def test_order(self):
        order = ["1.07.9", "1.08", "1.09", "1.10", "1.11", "1.12", "1.13", "1.14", "1.15", "1.16", "1.17", "1.18", "1.19", "1.20", "1.21", "1.22", "1.23", "1.24", "1.25", "1.26", "1.27", "1.28", "1.29", "1.30", "1.31"]
        tuples = [P.parse_version_tuple(v) for v in order]
        self.assertEqual(tuples, sorted(tuples))
        self.assertEqual(len(set(tuples)), len(tuples))
        self.assertLess(P.parse_version_tuple("1.1"), P.parse_version_tuple("1.09"))  # why 1.1 is never used

    def test_trailing_zeros_do_not_count(self):
        self.assertEqual(P.parse_version_tuple("1.15.0"), P.parse_version_tuple("1.15"))
        self.assertEqual(P.parse_version_tuple("v1.15.0.0"), P.parse_version_tuple("1.15"))
        self.assertGreater(P.parse_version_tuple("1.15.1"), P.parse_version_tuple("1.15"))
        self.assertEqual(P.parse_version_tuple("0"), (0,))

    def test_repo_versions_agree(self):
        with open(os.path.join(REPO, "scripts/lib/common.sh")) as f:
            cs = re.search(r"^CS_VERSION=([0-9.]+)", f.read(), re.M).group(1)
        with open(os.path.join(REPO, "panel/web/package.json")) as f:
            pkg = json.load(f)["version"]
        self.assertEqual(P.VERSION, cs)
        self.assertEqual(pkg, cs + ".0")
        for readme in ("README.md", "README.en.md"):
            with open(os.path.join(REPO, readme)) as f:
                self.assertIn(f"version-v{cs}-", f.read(), readme)

    def test_import_surface_unchanged(self):
        guardlib.assert_surface(P)


class ConfigGenerationTest(unittest.TestCase):
    def test_every_inbound_kind_passes_mihomo_t(self):
        kinds = [k for k in P.TYPES if k != "vless-reality"]
        write_default_state(kinds)
        rc, out = P.validate_config()
        self.assertEqual(rc, 0, out)
        conf = read(P.CONF)
        for k in kinds:
            self.assertIn(f"{k}-t", conf)

    def test_subscription(self):
        kinds = [k for k in P.TYPES if k != "vless-reality"]
        write_default_state(kinds)
        sub = P.render_subscription(P.read_env(), live=False)
        self.assertNotIn("skip-cert-verify", sub)
        d = tempfile.mkdtemp()
        with open(d + "/c.yaml", "w") as f:
            f.write(sub)
        rc, out = mihomo_t(d + "/c.yaml", d)
        self.assertEqual(rc, 0, out)
        self.assertIn("VlessReality", sub)

    def test_no_skip_cert_verify_in_sources(self):
        hits = []
        for base in ("resources", "scripts"):
            for dp, _, files in os.walk(os.path.join(REPO, base)):
                for fn in files:
                    p = os.path.join(dp, fn)
                    try:
                        txt = read(p, encoding="utf-8")
                    except (UnicodeDecodeError, OSError):
                        continue
                    if re.search(r"skip-cert-verify\s*:\s*true", txt):
                        hits.append(p)
        self.assertEqual(hits, [])

    def test_fixed_inputs_match_golden_config_and_subscription(self):
        guardlib.assert_goldens(P)


CERT_CASES = {
    # name: (yaml, expected rewrite count)
    "abs-other": ("listeners:\n  - name: h2\n    type: hysteria2\n    port: 443\n"
                  "    certificate: /root/cert/fullchain.cer\n    private-key: \"/root/cert/my.key\"  # note\n", 2),
    "relative": ("listeners:\n  - name: t\n    type: trojan\n    certificate: ./server.crt\n"
                 "    private-key: certs/privkey.pem\n", 2),
    "already-ok": ("tls:\n  certificate: /etc/clashgate/certs/fullchain.pem\n  private-key: /etc/clashgate/certs/privkey.pem\n"
                   "listeners:\n  - name: v\n    type: vless\n    reality-config:\n      dest: a.com:443\n"
                   "      private-key: aBcD_efgh-ijklmnopqrstuvwxyz0123456789ABCDE\n", 0),
    "outbound-and-inline": ("proxies:\n  - name: wg\n    type: wireguard\n    private-key: /AbCdEfGhIjKlMnOpQrStUvWxYz0123456789abcdef=\n"
                            "    certificate: /home/u/client.pem\nlisteners:\n  - name: x\n    type: anytls\n"
                            "    certificate: |\n      -----BEGIN CERTIFICATE-----\n      MIIB\n      -----END CERTIFICATE-----\n"
                            "    private-key: |\n      -----BEGIN PRIVATE KEY-----\n", 0),
    "tls-top": ("tls:\n  certificate: fullchain.pem\n  private-key: /etc/ssl/private/k.key\n"
                "proxy-providers:\n  default:\n    type: http\n", 2),
    "flow-list-dash": ("listeners:\n- name: a\n  type: tuic\n  certificate: /opt/a.pem\n  private-key: /opt/a.key\n", 2),
    "wg-key-in-listener": ("listeners:\n  - name: w\n    type: wireguard\n    private-key: 8BzqKxXgYzQ2nqYvwz/3jP1yO4j0kGFxAa0bfH7zN2k=\n", 0),
    "quoted-ok-and-comment": ("listeners:\n  - name: q\n    type: hysteria2\n    certificate: '/etc/clashgate/certs/fullchain.pem' # ok\n"
                              "    private-key: \"/etc/clashgate/certs/privkey.pem\"\n", 0),
    "home-tilde": ("listeners:\n  - name: h\n    type: anytls\n    certificate: ~/c.pem\n    private-key: ~/c.key\n", 2),
    "commented-out": ("listeners:\n  - name: c\n    type: anytls\n    # certificate: /root/x.pem\n", 0),
}


class CertPathTest(unittest.TestCase):
    def test_python_counts(self):
        for name, (raw, want) in CERT_CASES.items():
            out, n = P.rewrite_cert_paths_in_yaml(raw)
            self.assertEqual(n, want, name)
            again, n2 = P.rewrite_cert_paths_in_yaml(out)
            self.assertEqual(n2, 0, name + " (idempotent)")
            self.assertEqual(again, out, name)

    def test_reserved_provider_renamed(self):
        out, _ = P.rewrite_cert_paths_in_yaml(CERT_CASES["tls-top"][0])
        self.assertIn("  default-sub:", out)

    def test_js_mirror_matches(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        vue = read(os.path.join(REPO, "panel/web/src/composables/validation.js"))
        js = vue[vue.index("const CG_CERT_PATH"):vue.index("// end cert-path")]
        js += ("\nconst c=JSON.parse(require('fs').readFileSync(0,'utf8'));"
               "console.log(JSON.stringify(c.map(x=>{const r=fixCertPaths(x);return [r.text,r.changed]})))")
        names = list(CERT_CASES)
        r = subprocess.run([node, "-e", js], input=json.dumps([CERT_CASES[n][0] for n in names]),
                           capture_output=True, text=True, check=True)
        for name, (jtext, jn) in zip(names, json.loads(r.stdout)):
            ptext, pn = P.rewrite_cert_paths_in_yaml(CERT_CASES[name][0])
            self.assertEqual(jn, pn, name)
            self.assertEqual(jtext, ptext.replace("default-sub:", "default:"), name)

    def test_missing_cert_files(self):
        raw = ("tls:\n  certificate: /etc/clashgate/certs/fullchain.pem\n  private-key: certs/privkey.pem\n"
               "listeners:\n  - name: a\n    type: anytls\n    certificate: /nope/a.pem\n    private-key: ./nope.key\n")
        self.assertEqual(P.missing_cert_files(raw), ["/nope/a.pem", "./nope.key"])


class CustomModeTest(unittest.TestCase):
    CUSTOM = None

    def setUp(self):
        for p in (P.CUSTOM_CONF, P.CUSTOM_SAVED):
            if os.path.exists(p):
                os.remove(p)
        for p in (P.NODES_TSV, P.INBOUNDS, P.PROXIES_JSON, P.PROVIDERS_JSON):
            if os.path.exists(p + ".tplbak"):
                os.remove(p + ".tplbak")
        write_default_state(["shadowsocks"])
        with open(P.CONF) as f:
            self.base_conf = f.read()

    def test_apply_rejects_missing_cert(self):
        bad = self.base_conf.replace("/etc/clashgate/certs/fullchain.pem", "/root/missing/fullchain.pem")
        with self.assertRaises(ValueError) as cm:
            P.apply_custom_config(bad)
        self.assertIn("/root/missing/fullchain.pem", str(cm.exception))
        self.assertFalse(P.is_custom_config_mode())

    def test_disable_restores_backup(self):
        P.apply_custom_config(self.base_conf)
        self.assertTrue(P.is_custom_config_mode())
        self.assertEqual(P.disable_custom_config(), "restored")
        self.assertFalse(P.is_custom_config_mode())
        self.assertTrue(os.path.isfile(P.CUSTOM_SAVED))
        self.assertIn("shadowsocks-t", read(P.CONF))
        self.assertEqual(P.validate_config()[0], 0)

    def test_disable_without_backup_keeps_tracked_nodes(self):
        P.apply_custom_config(self.base_conf)
        for p in (P.NODES_TSV, P.INBOUNDS, P.PROXIES_JSON, P.PROVIDERS_JSON):
            if os.path.exists(p + ".tplbak"):
                os.remove(p + ".tplbak")
        self.assertEqual(P.disable_custom_config(), "kept")
        conf = read(P.CONF)
        self.assertIn("shadowsocks-t", conf)
        self.assertEqual(P.validate_config()[0], 0)

    def test_disable_falls_back_to_reset(self):
        P.apply_custom_config(self.base_conf)
        for p in (P.NODES_TSV, P.INBOUNDS, P.PROXIES_JSON, P.PROVIDERS_JSON):
            if os.path.exists(p + ".tplbak"):
                os.remove(p + ".tplbak")
        inbs = P.load_inbounds()
        inbs[0]["listener"]["type"] = "no-such-type"   # template cannot render it -> mihomo -t fails
        with open(P.INBOUNDS, "w") as f:
            json.dump(inbs, f)
        self.assertEqual(P.disable_custom_config(), "reset")
        self.assertEqual(P.validate_config()[0], 0)
        self.assertEqual(len(P.read_nodes()), 1)


NODE_NAMES_OK = ["东京", "Tokyo-1", "  hk 01  ", "A" * 15, "节点" * 7 + "x", "日本 🇯🇵", "de.fra_2", "direct-1",
                 "a,b", 'a"b', "a'b", "a\\b", "a`b", "a{b}", "[x]", "a#b", "a|b", "<x>", "k: v", "&*!%@", "#1 🚀"]
NODE_NAMES_BAD = ["", "   ", "A" * 16, "节点" * 8, "a\nb", "a\tb", "a\rb", "a\x00b", "a\x7fb", "a\u0085b", "a\u2028b",
                  "a\u200bb", "a\u202eb", "a\ufeffb", "DIRECT", "reject", "Global", "pass"]
# Every symbol the user may type, spread over names of at most 15 characters.
SYMBOL_NAMES = ['B,"\'[]{}#|<>🚀', "C:&*!%@`~ $^ 1", "D \\ /?=+;()", "🇯🇵 东京-#1"]


class UpdateCheckTest(unittest.TestCase):
    """After an upgrade the panel must never show the update it just installed."""

    def setUp(self):
        if os.path.exists(P.UPDATE_CHECK_JSON):
            os.remove(P.UPDATE_CHECK_JSON)

    def _bump(self, v, n=1):
        t = list(P.parse_version_tuple(v))
        t[-1] += n
        return ".".join(str(x) for x in t)

    def _stale(self, current, latest):
        with open(P.UPDATE_CHECK_JSON, "w") as f:
            json.dump({"panel": {"checked_at": 100, "current": current, "latest": latest, "has_update": True},
                       "core": {"checked_at": 100, "current": "1.19.0", "latest": "1.19.1", "has_update": True}}, f)

    def test_check_recorded_before_upgrade_is_not_shown(self):
        old = "1.01"
        self._stale(old, P.VERSION)                       # checked on the old build: "VERSION is available"
        pub = P.public_update_check("v1.19.1")
        self.assertFalse(pub["panel"]["has_update"])
        self.assertEqual(pub["panel"]["current"], P.VERSION)
        self.assertFalse(pub["core"]["has_update"])       # core already upgraded too
        self._stale(old, P.VERSION + ".0")                # same version spelled differently
        self.assertFalse(P.public_update_check("")["panel"]["has_update"])
        self._stale(old, self._bump(P.VERSION))           # a genuinely newer build is still offered
        self.assertTrue(P.public_update_check("")["panel"]["has_update"])
        self._stale(old, "")                              # nothing to compare: no badge
        self.assertFalse(P.public_update_check("")["panel"]["has_update"])

    def test_startup_rewrites_cache_written_by_another_build(self):
        self._stale("1.01", P.VERSION)
        self.assertTrue(P.refresh_update_check_for_version())
        slot = P.load_update_check()["panel"]
        self.assertEqual((slot["current"], slot["has_update"]), (P.VERSION, False))
        self.assertFalse(P.refresh_update_check_for_version())   # idempotent
        newer = self._bump(P.VERSION)
        self._stale("1.01", newer)
        P.refresh_update_check_for_version()
        self.assertTrue(P.load_update_check()["panel"]["has_update"])

    def test_frontend_never_flashes_update_during_or_after_upgrade(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        vue = frontend_script_text()
        js = vue[vue.index("// update-state: pure helpers"):vue.index("// end update-state")]
        js += r"""
const out = {}
out.newer = [cgVersionNewer('1.16', '1.15'), cgVersionNewer('1.15', '1.15'), cgVersionNewer('1.15.0', '1.15'),
             cgVersionNewer('1.14', '1.15'), cgVersionNewer('v1.15.1', '1.15'), cgVersionNewer('1.10', '1.9')]
// 1. 检查更新 finds 1.16 while 1.15 is installed: badge
let slot = { checked_at: 1, current: '1.15', latest: '1.16', has_update: true }
out.found = cgShowUpdate(slot, '1.15', false)
// 2. upgrade running (old page, old version): no badge
out.running = cgShowUpdate(slot, '1.15', true)
// 3. upgrade done, page about to reload: still "upgrading", slot already cleared
slot = cgSlotAfterUpgrade(slot, '1.16')
out.reloading = cgShowUpdate(slot, '1.16', true)
// 4. even if the upgrading flag dropped before the browser replaced the page
out.afterFlag = cgShowUpdate(slot, '1.16', false)
out.slot = slot
// 5. a stale slot from before the upgrade, compared with the new installed version
out.stale = cgShowUpdate({ has_update: true, latest: '1.16' }, '1.16', false)
out.staleZero = cgShowUpdate({ has_update: true, latest: '1.16.0' }, '1.16', false)
console.log(JSON.stringify(out))
"""
        r = subprocess.run([node, "-e", js], capture_output=True, text=True, check=True)
        out = json.loads(r.stdout)
        self.assertEqual(out["newer"], [True, False, False, False, True, True])
        self.assertTrue(out["found"])
        for k in ("running", "reloading", "afterFlag", "stale", "staleZero"):
            self.assertFalse(out[k], k)
        self.assertEqual((out["slot"]["current"], out["slot"]["has_update"]), ("1.16", False))
        # The buttons use the guarded computeds, and the upgrade watcher keeps the page in the
        # upgrading state once it decides to reload (location.reload() returns immediately).
        self.assertNotRegex(vue, r"(?:v-if|:class|:title)=\"[^\"]*(?:panelUpdate|coreUpdate)\.has_update")
        self.assertIn("'is-update': panelHasUpdate", vue)
        self.assertIn("'is-update': coreHasUpdate", vue)
        body = vue[vue.index("async function reloadPanelAfterUpgrade"):vue.index("const createRoutingForm")]
        self.assertIn("if (!reloading) upgradeInProgress.value = false", body)
        for m in re.finditer(r"window\.location\.reload\(\)", body):
            self.assertIn("reloading = true", body[max(0, m.start() - 400):m.start()], "reload without keeping the upgrading state")
        self.assertIn("cgSlotAfterUpgrade(", body)
        self.assertRegex(vue, r"const panelHasUpdate = computed\(\(\) =>\s*cgShowUpdate\(panelUpdate\.value, state\.version, "
                              r"upgradeInProgress\.value \|\| busyKey\.value === '/action/upgrade-self'\)")


class ClusterTest(unittest.TestCase):
    def setUp(self):
        write_default_state(["shadowsocks"])
        self.addCleanup(self._clean)

    def _clean(self):
        for f in (P.CLUSTER_JSON, P.FRAG_CLUSTER_PROXIES, P.FRAG_CLUSTER_LISTENERS, P.PANEL_SETTINGS):
            if os.path.exists(f):
                os.remove(f)

    def _state(self):
        dec_in, enc_peer = P.vless_mlkem768_pair()     # our inbound for the other panel
        _, enc_out = P.vless_mlkem768_pair()           # the other panel's inbound, seen from here
        link = {"id": "abc123", "instance": "a" * 32, "name": "东京-1", "url": "https://tokyo.example.com:8443",
                "key": "k" * 43, "version": "1.14", "created": 1, "seen": 1, "ok": True, "error": "", "missing": [],
                "in": {"port": 31001, "uuid": "66666666-7777-4888-9999-000000000000", "decryption": dec_in},
                "out": {"server": "tokyo.example.com", "port": 31000, "uuid": "11111111-2222-4333-8444-555555555555",
                        "encryption": enc_out}}
        return {"instance": "c" * 32, "links": [link], "pending": [], "removed": {}}, dec_in, enc_out

    def test_node_name_validation(self):
        for name in NODE_NAMES_OK:
            self.assertEqual(P.validate_node_name(name), name.strip(), name)
        for name in NODE_NAMES_BAD:
            with self.assertRaises(ValueError, msg=repr(name)):
                P.validate_node_name(name)
        P.save_panel_settings({"node_name": " 大阪 "})
        self.assertEqual(P.local_node_name(), "大阪")
        with self.assertRaises(ValueError):
            P.save_panel_settings({"node_name": "x" * 16})
        self.assertEqual(P.local_node_name(), "大阪")
        self.assertLessEqual(len(P.default_node_name()), P.NODE_NAME_MAX)
        self.assertEqual(P.NODE_NAME_MAX, 15)
        # a name saved under the old 20-character limit is shortened, not dropped
        cur = json.loads(read(P.PANEL_SETTINGS))
        cur["node_name"] = "y" * 20
        with open(P.PANEL_SETTINGS, "w") as f:
            json.dump(cur, f)
        self.assertEqual(P.local_node_name(), "y" * 15)
        # names announced by other (older) panels keep the old 20-character limit
        self.assertEqual(P.validate_peer_name("z" * 20), "z" * 20)
        with self.assertRaises(ValueError):
            P.validate_peer_name("z" * 21)

    def test_symbol_names_are_quoted_everywhere(self):
        st, dec, enc = self._state()
        base = st["links"][0]
        links = []
        for i, name in enumerate(SYMBOL_NAMES):
            self.assertEqual(P.validate_node_name(name), name)
            l = json.loads(json.dumps(base))
            l.update(id=f"id{i:04d}", instance=str(i) * 32, name=name)
            l["in"]["port"] = 31001 + i
            links.append(l)
        st["links"] = links
        P.save_cluster(st)
        conf = P.assemble_config()
        with open(P.CONF, "w") as f:
            f.write(conf)
        rc, out = P.validate_config()
        self.assertEqual(rc, 0, out)
        for name in SYMBOL_NAMES:
            self.assertIn('"name": ' + json.dumps(name, ensure_ascii=False), conf)
        self.assertEqual(P.cluster_proxy_names(), set(SYMBOL_NAMES))
        self.assertTrue(set(SYMBOL_NAMES) <= P.used_proxy_names())
        # hidden from the subscription and the outbound list, in both template and custom mode
        sub = P.render_subscription(P.read_env(), live=False)
        for name in SYMBOL_NAMES:
            self.assertNotIn(name, sub)
        self.assertFalse(set(SYMBOL_NAMES) & {p.get("name") for p in P.load_server_proxies()})
        inbs, proxies, _ = P.parse_custom_config_state(conf)
        self.assertFalse(set(SYMBOL_NAMES) & {p.get("name") for p in proxies})
        self.assertFalse([i for i in inbs if i["name"].startswith(P.CLUSTER_LISTENER_PREFIX)])
        names = [m["name"] for m in P.public_cluster_state(False)["members"]]
        self.assertEqual(sorted(names), sorted(SYMBOL_NAMES))

    def test_node_name_js_mirror_matches(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        vue = read(os.path.join(REPO, "panel/web/src/composables/validation.js"))
        js = "const t=(s)=>s;\n" + vue[vue.index("const CG_NODE_NAME_MAX"):vue.index("// end node-name")]
        js += ("\nconst c=JSON.parse(require('fs').readFileSync(0,'utf8'));"
               "console.log(JSON.stringify(c.map(x=>nodeNameError(x)==='')))")
        names = NODE_NAMES_OK + NODE_NAMES_BAD + SYMBOL_NAMES + ["ß" * 15, "e\u0301" * 7, "e\u0301" * 8, "a\u00a0b", "a\u2066b"]
        r = subprocess.run([node, "-e", js], input=json.dumps(names), capture_output=True, text=True, check=True)
        for name, js_ok in zip(names, json.loads(r.stdout)):
            try:
                P.validate_node_name(name)
                py_ok = True
            except ValueError:
                py_ok = False
            self.assertEqual(js_ok, py_ok, repr(name))

    def test_config_has_hidden_cluster_entries(self):
        st, dec, enc = self._state()
        self.assertTrue(dec.startswith("mlkem768x25519plus.native.600s."))
        self.assertTrue(enc.startswith("mlkem768x25519plus.native.0rtt."))
        P.save_cluster(st)
        self.assertEqual(oct(os.stat(P.CLUSTER_JSON).st_mode & 0o777), "0o600")
        conf = P.assemble_config()
        with open(P.CONF, "w") as f:
            f.write(conf)
        rc, out = P.validate_config()
        self.assertEqual(rc, 0, out)
        # one link = one outbound to the other panel + one dedicated inbound for it
        self.assertIn('"name": "东京-1"', conf)
        self.assertIn('"server": "tokyo.example.com"', conf)
        self.assertIn('"encryption": "' + enc + '"', conf)
        self.assertIn('"name": "cg-cluster-abc123"', conf)
        self.assertIn('"decryption": "' + dec + '"', conf)
        self.assertEqual(conf.count('"flow": "xtls-rprx-vision"'), 2)
        self.assertNotIn("skip-cert-verify", conf)
        # routing groups use include-all, so the link is selectable without listing it anywhere
        self.assertIn("include-all: true", read(P.FRAG_PROXY_GROUPS) if os.path.exists(P.FRAG_PROXY_GROUPS) else conf)
        self.assertIn(31001, P.used_ports(P.read_env()))
        self.assertEqual(P.cluster_ufw_specs(), {"31001/tcp"})
        self.assertIn("东京-1", P.used_proxy_names())

    def test_cluster_hidden_from_subscription_and_ui(self):
        st, dec, enc = self._state()
        P.save_cluster(st)
        link = st["links"][0]
        sub = P.render_subscription(P.read_env(), live=False)
        for secret in ("东京-1", "cg-cluster", enc, dec, link["out"]["uuid"], link["in"]["uuid"], link["key"]):
            self.assertNotIn(secret, sub)
        self.assertNotIn("东京-1", [p.get("name") for p in P.load_server_proxies()])
        pub = P.public_cluster_state(False)
        self.assertEqual([m["name"] for m in pub["members"]], ["东京-1"])
        self.assertEqual(pub["self_url"], "https://ex.sslip.io:25183")
        raw = json.dumps(pub, ensure_ascii=False)
        for secret in (enc, dec, link["key"], link["out"]["uuid"], link["in"]["uuid"]):
            self.assertNotIn(secret, raw)
        view = json.dumps(P.cluster_members_view(P.load_cluster()))
        self.assertNotIn(link["key"], view)
        self.assertIn("tokyo.example.com", view)

    def test_custom_mode_keeps_cluster_out_of_parsed_state(self):
        st, _, _ = self._state()
        P.save_cluster(st)
        inbs, proxies, _ = P.parse_custom_config_state(P.assemble_config())
        self.assertFalse([i for i in inbs if i["name"].startswith(P.CLUSTER_LISTENER_PREFIX)])
        self.assertNotIn("东京-1", [p.get("name") for p in proxies])
        self.assertIn("shadowsocks-t", [i["name"] for i in inbs])

    def test_old_cluster_file_is_ignored(self):
        with open(P.CLUSTER_JSON, "w") as f:
            json.dump({"instance": "d" * 32, "members": [{"id": "x"}], "peers": [{"id": "y"}]}, f)
        st = P.load_cluster()
        self.assertEqual((st["instance"], st["links"]), ("d" * 32, []))

    def test_pick_port_skips_a_bound_port(self):
        """pick_port must not return a port that bind() would reject (other process or TIME_WAIT)."""
        holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.addCleanup(holder.close)
        occupied = None
        for p in range(23450, 23600):
            if p in P.used_ports(P.read_env()):
                continue
            try:
                holder.bind(("0.0.0.0", p))
                occupied = p
                break
            except OSError:
                continue
        self.assertIsNotNone(occupied, "could not bind a test port")
        self.assertFalse(P.pick_port.__globals__['port_is_available'](occupied))
        free = None
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            for p in range(occupied + 1, occupied + 80):
                if p in P.used_ports(P.read_env()):
                    continue
                try:
                    probe.bind(("0.0.0.0", p))
                    free = p
                    break
                except OSError:
                    continue
        finally:
            probe.close()
        self.assertIsNotNone(free, "could not find a free follow-up port")
        self.assertTrue(P.pick_port.__globals__['port_is_available'](free))
        seq = iter([occupied, occupied, free])
        with mock.patch.object(P.pick_port.__globals__["random"], "randint",
                               side_effect=lambda a, b: next(seq)):
            self.assertEqual(P.pick_port(P.read_env()), free)

    def test_apply_cluster_live_fails_if_inbound_never_listens(self):
        """systemctl reload/restart succeeding is not enough if the cluster port never binds."""
        st, _, _ = self._state()
        P.save_cluster(st)
        P.render_cluster_listeners(st)
        P.render_cluster_proxies(st)
        g = P.apply_cluster_live.__globals__
        real_run = g["run"]

        def fake_run(cmd, **kw):
            joined = " ".join(str(c) for c in cmd)
            if any(k in joined for k in ("reload", "restart", "is-active", "show")):
                return 0, "active\n"
            if joined.endswith("-v") or " -v" in joined:
                return 0, "Mihomo Meta v1.19.34\n"
            return real_run(cmd, **kw)

        def fake_status():
            # Other ports may be up; the new cluster inbound is not.
            return {"active": "active", "listening": [80, 443, 25183], "pid": "1",
                    "version": "", "since": "", "restarts": "", "cert": {}}

        with mock.patch.dict(g, {"run": fake_run, "mihomo_status": fake_status}):
            # Shrink the wait so the test does not sleep 16s.
            with mock.patch.object(P, "apply_cluster_live", P.apply_cluster_live):
                pass
            orig_wait = g["_wait_cluster_ports"]

            def quick_wait(want, timeout=8.0):
                return orig_wait(want, timeout=0.01)

            g["_wait_cluster_ports"] = quick_wait
            try:
                with self.assertRaises(RuntimeError) as cm:
                    P.apply_cluster_live(set())
                self.assertIn("监听", str(cm.exception))
            finally:
                g["_wait_cluster_ports"] = orig_wait

    def test_report_text(self):
        rep = {"linked": ["B", "C"], "meshed": 2, "failed": ["D ↔ E"], "dropped": [], "offline": ["F"]}
        txt = P.cluster_report_text(rep)
        self.assertIn("「B、C」", txt)
        import i18n_en
        self.assertNotRegex(i18n_en.tr(txt, "en"), r"[\u4e00-\u9fff]")

    def test_panel_url_normalization(self):
        self.assertEqual(P.normalize_panel_url("panel.example.com:8443/"), "https://panel.example.com:8443")
        self.assertEqual(P.normalize_panel_url("https://Panel.Example.com/x?y"), "https://panel.example.com")
        for bad in ("", "http://a.com", "https://user:pw@a.com", "ftp://a.com", "https://"):
            with self.assertRaises(P.ClusterError, msg=bad):
                P.normalize_panel_url(bad)


class ManualCertTest(unittest.TestCase):
    """1.20: switch to a manual certificate from the panel (self-signed test certs only)."""
    DOMAIN = "ex.sslip.io"

    @staticmethod
    def _ossl(*args, cwd=None):
        subprocess.run(["openssl", *args], check=True, capture_output=True, cwd=cwd)

    @classmethod
    def make(cls, d, name, sans, cn=None, expired=False):
        """Self-signed EC cert + key in d: name.crt / name.key."""
        key, crt = os.path.join(d, name + ".key"), os.path.join(d, name + ".crt")
        subj = "/CN=" + (cn or sans.split(",")[0].split(":", 1)[1])
        if not expired:
            cls._ossl("req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256", "-nodes", "-days", "30",
                      "-subj", subj, "-addext", "subjectAltName=" + sans, "-keyout", key, "-out", crt)
            return crt, key
        work = tempfile.mkdtemp(dir=d)
        cls._ossl("req", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256", "-nodes", "-subj", subj,
                  "-addext", "subjectAltName=" + sans, "-keyout", key, "-out", work + "/r.csr")
        open(work + "/index.txt", "w").close()
        with open(work + "/serial", "w") as f:
            f.write("01\n")
        with open(work + "/ca.cnf", "w") as f:
            f.write("[ca]\ndefault_ca=c\n[c]\ndatabase=index.txt\nnew_certs_dir=.\nserial=serial\n"
                    "default_md=sha256\npolicy=p\ncopy_extensions=copy\n[p]\ncommonName=supplied\n")
        cls._ossl("ca", "-batch", "-config", "ca.cnf", "-selfsign", "-keyfile", key, "-in", "r.csr",
                  "-startdate", "20200101000000Z", "-enddate", "20200102000000Z", "-notext", "-out", crt, cwd=work)
        shutil.rmtree(work)
        return crt, key

    def setUp(self):
        self.store = tempfile.mkdtemp(prefix="cg-mcert-src-")
        self.dir = tempfile.mkdtemp(prefix="cg-mcert-")

    def tearDown(self):
        shutil.rmtree(self.store, ignore_errors=True)
        shutil.rmtree(self.dir, ignore_errors=True)

    def put(self, src, name, age=0):
        dst = os.path.join(self.dir, name)
        shutil.copyfile(src, dst)
        t = time.time() - age
        os.utime(dst, (t, t))
        return dst

    def err(self, domain=None):
        with self.assertRaises(P.ManualCertError) as cm:
            P.check_manual_cert(self.dir, domain or self.DOMAIN)
        return str(cm.exception)

    def test_valid_pair_installed_names(self):
        crt, key = self.make(self.store, "ok", "DNS:ex.sslip.io", cn="My Test CA")
        self.put(crt, "fullchain.pem")
        self.put(key, "privkey.pem")
        info = P.check_manual_cert(self.dir, self.DOMAIN)
        self.assertEqual(os.path.basename(info["crt"]), "fullchain.pem")
        self.assertEqual(os.path.basename(info["key"]), "privkey.pem")
        self.assertEqual(info["issuer"], "My Test CA")
        self.assertIn(info["days"], (28, 29, 30))
        self.assertFalse(P.install_manual_cert(self.dir, info["crt"], info["key"]))
        self.assertEqual(os.stat(os.path.join(self.dir, "privkey.pem")).st_mode & 0o777, 0o640)

    def test_newest_crt_and_key_win_and_get_installed(self):
        old_c, old_k = self.make(self.store, "old", "DNS:ex.sslip.io")
        new_c, new_k = self.make(self.store, "new", "DNS:ex.sslip.io,DNS:www.ex.sslip.io")
        self.put(old_c, "fullchain.pem", age=600)
        self.put(old_k, "privkey.pem", age=600)
        self.put(new_c, "my-site.crt")
        self.put(new_k, "my-site.key")
        info = P.check_manual_cert(self.dir, self.DOMAIN)
        self.assertEqual(os.path.basename(info["crt"]), "my-site.crt")
        self.assertEqual(os.path.basename(info["key"]), "my-site.key")
        self.assertTrue(P.install_manual_cert(self.dir, info["crt"], info["key"]))
        self.assertEqual(read(os.path.join(self.dir, "fullchain.pem")), read(new_c))
        self.assertEqual(read(os.path.join(self.dir, "privkey.pem")), read(new_k))
        self.assertFalse(os.path.exists(os.path.join(self.dir, "fullchain.pem.new")))
        # Checking again picks the installed copy and changes nothing.
        info2 = P.check_manual_cert(self.dir, self.DOMAIN)
        self.assertFalse(P.install_manual_cert(self.dir, info2["crt"], info2["key"]))

    def test_wildcard(self):
        crt, key = self.make(self.store, "wild", "DNS:*.ex.sslip.io,DNS:ex.sslip.io")
        self.put(crt, "fullchain.pem")
        self.put(key, "privkey.pem")
        self.assertTrue(P.check_manual_cert(self.dir, "*.ex.sslip.io")["crt"].endswith("fullchain.pem"))

    def test_missing_files(self):
        self.assertIn("未找到证书文件", self.err())
        crt, key = self.make(self.store, "c", "DNS:ex.sslip.io")
        self.put(crt, "fullchain.pem")
        self.assertIn("未找到私钥文件", self.err())
        self.assertIn("/etc/clashgate/certs/", self.err())
        with self.assertRaises(P.ManualCertError) as cm:
            P.check_manual_cert(self.dir + "/nope", self.DOMAIN)
        self.assertIn("未找到证书文件", str(cm.exception))

    def test_mismatched_key(self):
        crt, _ = self.make(self.store, "a", "DNS:ex.sslip.io")
        _, other = self.make(self.store, "b", "DNS:ex.sslip.io")
        self.put(crt, "fullchain.pem")
        self.put(other, "privkey.pem")
        self.assertIn("证书与私钥不匹配", self.err())

    def test_expired(self):
        crt, key = self.make(self.store, "exp", "DNS:ex.sslip.io", expired=True)
        self.put(crt, "fullchain.pem")
        self.put(key, "privkey.pem")
        msg = self.err()
        self.assertIn("证书已过期", msg)
        self.assertIn("2020-01-0", msg)

    def test_wrong_domain(self):
        crt, key = self.make(self.store, "other", "DNS:other.example.com")
        self.put(crt, "fullchain.pem")
        self.put(key, "privkey.pem")
        msg = self.err()
        self.assertIn("证书域名不匹配", msg)
        self.assertIn("ex.sslip.io", msg)
        with self.assertRaises(P.ManualCertError) as cm:
            P.check_manual_cert(self.dir, "")
        self.assertIn("未设置域名", str(cm.exception))

    def test_installer_temporary_cert_is_not_a_manual_cert(self):
        crt, key = self.make(self.store, "tmp", "DNS:ex.sslip.io", cn="clashgate temporary certificate")
        self.put(crt, "fullchain.pem")
        self.put(key, "privkey.pem")
        self.assertIn("未找到证书文件", self.err())

    def test_encrypted_key(self):
        crt, key = self.make(self.store, "enc", "DNS:ex.sslip.io")
        enc = os.path.join(self.store, "enc-locked.key")
        self._ossl("pkey", "-in", key, "-aes256", "-passout", "pass:secret", "-out", enc)
        self.put(crt, "fullchain.pem")
        self.put(enc, "privkey.pem")
        self.assertIn("私钥带有密码", self.err())

    def test_messages_translate(self):
        import i18n_en
        for zh in ("证书已过期（到期时间：2020-01-02 08:00），请换成有效的证书",
                   "证书域名不匹配：证书里没有 ex.sslip.io，请换成这个域名或 *.泛域名的证书",
                   "已切换为手动证书（颁发者：R11，到期：2027-01-01 00:00，剩余 40 天）"):
            for lang in ("en", "ru", "fa"):
                self.assertNotRegex(i18n_en.tr(zh, lang), r"[\u4e00-\u9fff]", f"{lang}: {zh}")

    def test_handler_switch_and_revalidate(self):
        """POST /action/cert-mode cert_mode=manual: rejects bad files without touching CERT_MODE,
        switches on good files, and re-checks when already manual."""
        certs = P.CS_ROOT + "/certs"
        saved = {n: read(os.path.join(certs, n)) for n in ("fullchain.pem", "privkey.pem")}
        env_before = read(P.ENV_FILE)
        calls = []
        h = object.__new__(P.Panel)
        h.respond_mutation = lambda s, msg, ok=True, detail="": (ok, msg)
        g = P.Panel.do_cert_manual.__globals__
        real_run = g["run"]

        def fake_run(cmd, **kw):
            if cmd and cmd[0] == P.SYSTEMCTL:
                calls.append(cmd[1:])
                return 0, ""
            return real_run(cmd, **kw)

        try:
            with mock.patch.dict(g, {"run": fake_run}):
                ok, msg = h.do_cert_mode({}, {"cert_mode": "manual"})   # placeholder files from module setup
                self.assertFalse(ok)
                self.assertIn("未找到证书文件", msg)
                self.assertNotIn("CERT_MODE", read(P.ENV_FILE))
                crt, key = self.make(self.store, "h", "DNS:ex.sslip.io", cn="Handler CA")
                shutil.copyfile(crt, certs + "/site.crt")
                shutil.copyfile(key, certs + "/site.key")
                ok, msg = h.do_cert_mode({}, {"cert_mode": "manual"})
                self.assertTrue(ok, msg)
                self.assertIn("已切换为手动证书（颁发者：Handler CA", msg)
                self.assertEqual(P.read_env().get("CERT_MODE"), "manual")
                self.assertEqual(read(certs + "/fullchain.pem"), read(crt))
                self.assertIn(["disable", "--now", "clashgate-cert.timer"], calls)
                ok, msg = h.do_cert_mode({}, {"cert_mode": "manual"})
                self.assertTrue(ok, msg)
                self.assertIn("手动证书校验通过", msg)
        finally:
            for n, txt in saved.items():
                with open(os.path.join(certs, n), "w") as f:
                    f.write(txt)
            for n in ("site.crt", "site.key"):
                if os.path.exists(os.path.join(certs, n)):
                    os.remove(os.path.join(certs, n))
            with open(P.ENV_FILE, "w") as f:
                f.write(env_before)


class SecurityTest(unittest.TestCase):
    def test_env_value_cannot_inject_lines(self):
        for bad in ('x\nREPO_OWNER=evil', 'a"b', "back\\slash", "cr\r"):
            with self.assertRaises(ValueError):
                P.write_env_var("MIHOMO_SECRET", bad)
        P.write_env_var("MIHOMO_SECRET", "test-secret")
        self.assertEqual(P.read_env()["MIHOMO_SECRET"], "test-secret")

    def test_password_change_revokes_other_sessions(self):
        P.Panel.sessions = {"keep": {"csrf": "a", "exp": 9e12}, "old": {"csrf": "b", "exp": 9e12}}
        P.revoke_other_sessions("keep")
        self.assertEqual(list(P.Panel.sessions), ["keep"])
        self.assertEqual(oct(os.stat(P.SESSIONS_JSON).st_mode & 0o777), "0o600")

    def _handler(self, ip):
        h = P.Panel.__new__(P.Panel)
        h.client_address = (ip, 1234)
        return h

    def test_login_bucket(self):
        self.assertEqual(self._handler("203.0.113.5").login_bucket(), "203.0.113.5")
        self.assertEqual(self._handler("::ffff:203.0.113.5").login_bucket(), "203.0.113.5")
        a = self._handler("2001:db8:1:2:aaaa::1").login_bucket()
        b = self._handler("2001:db8:1:2:bbbb::9").login_bucket()
        self.assertEqual(a, b)

    def test_access_log_hides_sub_token(self):
        import io
        h = self._handler("198.51.100.7")
        buf, old = io.StringIO(), sys.stderr
        sys.stderr = buf
        try:
            h.log_message('"%s" %s %s', "GET /sub/SECRETTOKEN1234567/mihomo.yaml HTTP/1.1", "200", "-")
        finally:
            sys.stderr = old
        self.assertNotIn("SECRETTOKEN", buf.getvalue())
        self.assertIn("/sub/<token>/mihomo.yaml", buf.getvalue())

    def test_sticky_root_dir(self):
        os.chmod(P.CS_ROOT, 0o775)
        P.ensure_unified_root()
        self.assertTrue(os.stat(P.CS_ROOT).st_mode & 0o1000)


class V121Test(unittest.TestCase):
    """1.21: friendly errors, gzip, deferred secret/token commit, uninstall order, client header."""

    def test_friendly_error(self):
        fe = P.friendly_error
        self.assertEqual(fe("节点名称不能为空"), ("节点名称不能为空", ""))
        self.assertEqual(fe("集群操作失败：对方面板版本太低"), ("集群操作失败：对方面板版本太低", ""))
        plain, detail = fe("集群操作失败：<urlopen error [Errno 111] Connection refused>")
        self.assertTrue(plain.startswith("连接被拒绝"))
        self.assertIn("Errno 111", detail)
        plain, detail = fe("配置校验未通过，未执行应用配置：level=fatal msg=\"parse config error: yaml: line 3\"")
        self.assertEqual(plain, "新配置没有通过内核校验，已保留原来的配置。请检查最近的改动。")
        self.assertIn("yaml: line 3", detail)
        plain, _ = fe("对方面板无法通过 https://h:1 连回发起方：timed out")
        self.assertTrue(plain.startswith("对方面板无法通过 https://h:1 连回发起方：连接超时"), plain)
        plain, _ = fe("对方面板的 HTTPS 证书验证失败，请用对方证书上的域名访问（[SSL: CERTIFICATE_VERIFY_FAILED]）")
        self.assertEqual(plain, "对方面板的 HTTPS 证书验证失败，请用对方证书上的域名访问")
        self.assertTrue(fe("证书申请 / 续期失败：")[0].startswith("证书申请 / 续期失败：请确认"))
        self.assertTrue(fe("OSError: [Errno 98] Address already in use")[0].startswith("端口已被其他程序占用"))
        self.assertEqual(P.raw_detail("\x1b[31mred\x1b[0m " + "x" * 2000)[-5:], "xxxxx")
        self.assertNotIn("\x1b", P.raw_detail("\x1b[31mred\x1b[0m"))

    def test_cert_failure_message_any_certctl_language(self):
        """certctl prints in the CLI language; the panel pins zh, but every language is still recognised."""
        for line in ("certctl: 80 端口被占用，无法申请证书（端口模式需要临时使用 80 端口）：",
                     "certctl: Port 80 is in use, cannot request the certificate (port mode needs port 80 temporarily):",
                     "certctl: Порт 80 занят, запросить сертификат нельзя (режиму порта нужен порт 80 на время выпуска):"):
            self.assertIn("80 端口被占用", P.cert_failure_message(line, "port"), line)
        for line in ("certctl: 证书申请失败（请检查 Cloudflare API Token 是否具备 example.com 的 DNS 编辑权限）",
                     "certctl: Certificate request failed (check that the Cloudflare API Token has DNS edit permission for example.com)",
                     "certctl: Запрос сертификата не удался (проверьте, что у Cloudflare API Token есть право на изменение DNS для example.com)"):
            self.assertIn("Token 无效", P.cert_failure_message(line, "dns"), line)
        env = P.Panel.do_cert_action.__globals__["certctl_env"]()
        self.assertEqual(env["CLASHGATE_LANG"], "zh")

    def test_friendly_sentences_translate(self):
        import i18n_en
        texts = [t for _, t in P.FRIENDLY_REASONS] + [t for _, t in P.FRIENDLY_PREFIXES]
        texts += [P.cert_failure_message("boom", m) for m in ("port", "dns")]
        texts += [P.cert_failure_message("Invalid API Token", "dns"), "管理面板需要浏览器开启 JavaScript，请开启后刷新页面。",
                  "对方面板无法通过 https://h:1 连回发起方：" + P.FRIENDLY_REASONS[0][1]]
        for zh in texts:
            for lang in ("en", "ru", "fa"):
                self.assertNotRegex(i18n_en.tr(zh, lang), r"[\u4e00-\u9fff]", f"{lang}: {zh}")

    def _handler(self, accept="", command="GET"):
        h = object.__new__(P.Panel)
        h.command = command
        h.headers = {"Accept-Encoding": accept}
        return h

    def test_accepts_gzip(self):
        self.assertTrue(self._handler("gzip, deflate, br").accepts_gzip())
        self.assertTrue(self._handler("br;q=1.0, gzip;q=0.8").accepts_gzip())
        self.assertFalse(self._handler("gzip;q=0").accepts_gzip())
        self.assertFalse(self._handler("deflate").accepts_gzip())
        self.assertFalse(self._handler("").accepts_gzip())
        self.assertFalse(self._handler("gzip", "HEAD").accepts_gzip())

    def test_gzip_bytes_cached(self):
        import gzip
        g = P.Panel.send.__globals__
        data = b"<html>" + b"hello " * 400 + b"</html>"
        a = g["_gzip_bytes"](data, ("k", 1))
        self.assertEqual(gzip.decompress(a), data)
        self.assertIs(g["_gzip_bytes"](data, ("k", 1)), a)
        self.assertTrue(g["_compressible"]("text/html; charset=utf-8", data))
        self.assertFalse(g["_compressible"]("image/png", data))
        self.assertFalse(g["_compressible"]("text/html", b"tiny"))

    def test_reload_failure_keeps_old_secret_and_token(self):
        env_before = read(P.ENV_FILE)
        write_default_state()
        P.clear_pending_reload()
        P.record_pending_reload(op="reset-secret", kind="secret", name="secret", mihomo_secret="NEWSECRET123")
        P.record_pending_reload(op="reset-sub", kind="sub", name="sub", sub_token="N" * 24)
        h = object.__new__(P.Panel)
        h.cfg, h.cfg_path = {"sub_token": "O" * 24}, None
        got = {}

        def respond(s, msg, ok=True, detail=""):
            got.update(ok=ok, msg=msg)
            return ok, msg
        h.respond_mutation = respond
        g = P.Panel.do_action.__globals__
        try:
            with mock.patch.dict(g, {"validate_config": lambda *a, **k: (1, "level=fatal msg=bad")}):
                h.do_action({}, "reload")
            self.assertFalse(got["ok"])
            self.assertEqual(P.read_env().get("MIHOMO_SECRET"), "test-secret")
            self.assertEqual(h.cfg["sub_token"], "O" * 24)
            st = P.load_pending_reload()
            self.assertEqual((st["mihomo_secret"], st["sub_token"]), ("NEWSECRET123", "N" * 24))
        finally:
            P.clear_pending_reload()
            with open(P.ENV_FILE, "w") as f:
                f.write(env_before)

    def test_uninstall_leaves_cluster_first(self):
        un = read(os.path.join(REPO, "scripts/cmd/clashgate.sh"))
        body = un[un.index("do_uninstall() {"):]
        self.assertNotIn("close_firewall", body)   # 1.29: uninstall leaves firewall rules alone
        self.assertLess(body.index("leave_cluster"), body.index("systemctl disable --now clashgate"))

    def test_client_header_has_version(self):
        out = P.render_subscription(P.read_env(), live=False)
        self.assertTrue(out.startswith(f"# Generated by ClashGate v{P.VERSION}."), out[:80])
        self.assertNotIn("@@VERSION@@", out)

    def test_panel_unit_uses_detected_python(self):
        sh = read(os.path.join(REPO, "scripts/lib/common.sh"))
        self.assertIn("sys.version_info >= (3, 9)", sh)
        for f in ("scripts/lib/panel.sh", "scripts/cmd/clashgate.sh"):
            src = read(os.path.join(REPO, f))
            self.assertNotIn("scripts/init/clashgate.service\" /etc/systemd", src)
            self.assertNotIn("| python3 ", src)
        self.assertIn("ExecStart=/usr/bin/python3 ", read(os.path.join(REPO, "scripts/init/clashgate.service")))

    def test_frontend_1_21(self):
        js = frontend_script_text()
        app = read(os.path.join(REPO, "panel/web/src/App.vue"))
        self.assertNotIn("confirmUpdateCore", app)   # the core update lives on the Settings page now
        self.assertIn("settings-update-core", read(os.path.join(REPO, "panel/web/src/pages/SettingsPage.vue")))
        certs = read(os.path.join(REPO, "panel/web/src/pages/CertsPage.vue"))
        for needle in ('id="cert-renew"', 'id="cert-port-guide-card"', 'id="cf-token-eye"', "cfTokenRevealed ? 'text' : 'password'"):
            self.assertIn(needle, certs)
        self.assertIn("'/action/cert'", js)
        for gone in ("/action/restart", "/action/cert-dns", "/routing/update"):
            self.assertNotIn(gone, js)


class GeoDataTest(unittest.TestCase):
    """1.31: geo data is fetched up front into the core's home dir; mihomo -t must never download it."""

    def setUp(self):
        global G
        G = P.ensure_geodata.__globals__

    def test_reality_sni_pool_has_no_yahoo(self):
        self.assertFalse([h for h in P.REALITY_SNI_POOL if "yahoo" in h])
        self.assertNotIn("yahoo", read(os.path.join(REPO, "scripts/lib/common.sh")))

    def test_validation_uses_local_geodata_offline(self):
        P.ensure_geodata()
        for name, _ in G["GEO_FILES"]:
            self.assertTrue(G["_geo_present"](P.CS_ROOT, name), name)
        # geox-url points nowhere: the check only passes if the validator links the local files.
        cfg = os.path.join(tempfile.mkdtemp(), "geo.yaml")
        with open(cfg, "w") as f:
            f.write("geodata-mode: false\ngeox-url:\n  mmdb: http://127.0.0.1:9/a.mmdb\n"
                    "  geosite: http://127.0.0.1:9/b.dat\n  asn: http://127.0.0.1:9/c.mmdb\n"
                    "proxies: []\nrules:\n  - GEOSITE,google,DIRECT\n  - IP-ASN,13335,DIRECT,no-resolve\n"
                    "  - GEOIP,private,DIRECT,no-resolve\n  - MATCH,DIRECT\n")
        with mock.patch.object(G["urllib"].request, "urlopen",
                               side_effect=OSError("offline")):
            rc, out = P.validate_config(path=cfg)
        self.assertEqual(rc, 0, out)
        self.assertNotIn("download", out.lower())

    def test_ensure_geodata_fetches_missing_files(self):
        root = tempfile.mkdtemp()
        with open(root + "/Country.mmdb", "wb") as f:   # legacy name, any case, counts for GEOIP
            f.write(b"x")
        seen = []

        def fake(url, timeout=0):
            seen.append(url)
            return io.BytesIO(b"g" * 4096)
        with mock.patch.object(G["urllib"].request, "urlopen", side_effect=fake):
            self.assertEqual(P.ensure_geodata(root), [])
            self.assertEqual(P.ensure_geodata(root), [])   # second call: nothing to fetch
        self.assertEqual(sorted(os.listdir(root)), ["ASN.mmdb", "Country.mmdb", "GeoSite.dat"])
        self.assertEqual([u.rsplit("/", 1)[1] for u in seen], ["geosite.dat", "GeoLite2-ASN.mmdb"])
        with mock.patch.object(G["urllib"].request, "urlopen",
                               side_effect=OSError("offline")):
            self.assertEqual(P.ensure_geodata(tempfile.mkdtemp()), ["geoip.metadb", "GeoSite.dat", "ASN.mmdb"])

    def test_installer_and_update_fetch_geodata(self):
        sh = read(os.path.join(REPO, "scripts/cmd/clashgate.sh"))
        core = read(os.path.join(REPO, "scripts/lib/core.sh"))
        inst = sh[sh.index("do_install() {"):sh.index("do_update() {")]
        self.assertLess(inst.index("ensure_geodata || die"), inst.index("render_server"))
        upd = sh[sh.index("do_update() {"):sh.index("update_self() {")]
        self.assertLess(upd.index("ensure_geodata"), upd.index("update_self"))
        self.assertIn('"$CONF_DIR"/*.metadb', core)
        tpl = read(os.path.join(REPO, "resources/server.yaml.tpl"))
        for name, remote in G["GEO_FILES"]:
            self.assertIn(f'"{name} {remote}"', core)
            self.assertIn(f"{G["GEO_BASES"][0]}/{remote}", tpl)
        for base in G["GEO_BASES"]:
            self.assertIn(base, core)
        self.assertIn('target=ensure_geodata', read(os.path.join(REPO, "panel/cg_http.py")))


if __name__ == "__main__":
    unittest.main()
