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
import threading
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
        form = {"port": str(port), "name": f"{kind}-t"}
        custom_only = kind == "vless-xhttp"   # 1.45: offered in custom server mode only
        inbs.append(P.build_inbound(kind, form, env, advanced=custom_only))
    P._write_template_state([node], inbs, [], {}, env)
    return node, inbs


class VersionTest(unittest.TestCase):
    def test_order(self):
        order = ["1.07.9", "1.08", "1.09", "1.10", "1.11", "1.12", "1.13", "1.14", "1.15", "1.16", "1.17", "1.18", "1.19", "1.20", "1.21", "1.22", "1.23", "1.24", "1.25", "1.26", "1.27", "1.28", "1.29", "1.30", "1.31", "1.32", "1.33", "1.34", "1.35", "1.36", "1.37", "1.38", "1.39", "1.40", "1.41", "1.42", "1.43", "1.44", "1.45", "1.46", "1.47"]
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
        for p in (P.CUSTOM_CONF, P.CUSTOM_SAVED, P.DEFAULT_ENV_BAK):
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

    def _disable(self):
        with mock.patch.dict(P.disable_custom_config.__globals__, {"wait_mihomo_ports": lambda *a, **k: True}):
            return P.disable_custom_config()

    def _custom_with_extra_node(self):
        """The default state from setUp in custom mode, plus a listener only the custom config has."""
        extra = ("  - name: only-in-custom\n    type: socks\n    port: 31555\n    listen: 0.0.0.0\n"
                 "    udp: true\n")
        conf = self.base_conf.replace("listeners:\n", "listeners:\n" + extra, 1)
        self.assertIn("only-in-custom", conf)
        P.apply_custom_config(conf)
        self.assertIn("only-in-custom", [i["name"] for i in P.load_inbounds()])
        return conf

    def test_modes_are_separate(self):
        """1.47: default mode and custom mode never mix. Entering custom mode keeps the default mode's
        state aside; turning it off brings that back exactly, with nothing from the custom config."""
        nodes_before = read(P.NODES_TSV)
        inbs_before = sorted(i["name"] for i in P.load_inbounds())
        secret_before = P.read_env().get("MIHOMO_SECRET", "")
        routing = read(P.ROUTING_JSON) if os.path.exists(P.ROUTING_JSON) else None
        conf = self._custom_with_extra_node()
        self.assertTrue(os.path.exists(P.INBOUNDS + ".tplbak"))
        self.assertTrue(os.path.exists(P.DEFAULT_ENV_BAK))
        # a second custom config while in custom mode does not touch the default mode's copy
        P.apply_custom_config(conf.replace("only-in-custom", "also-only-in-custom"))
        self.assertNotIn("only-in-custom", read(P.INBOUNDS + ".tplbak"))
        P.write_env_var("MIHOMO_SECRET", "custom-secret")   # as a custom config's `secret:` would
        self.assertEqual(self._disable(), "restored")
        self.assertFalse(P.is_custom_config_mode())
        self.assertTrue(os.path.isfile(P.CUSTOM_SAVED))
        self.assertEqual(read(P.NODES_TSV), nodes_before)
        self.assertEqual(sorted(i["name"] for i in P.load_inbounds()), inbs_before)
        self.assertNotIn("only-in-custom", read(P.CONF))
        self.assertEqual(P.read_env().get("MIHOMO_SECRET", ""), secret_before)
        if routing is not None:
            self.assertEqual(read(P.ROUTING_JSON), routing)
        for p in (P.NODES_TSV, P.INBOUNDS, P.PROXIES_JSON, P.PROVIDERS_JSON):
            self.assertFalse(os.path.exists(p + ".tplbak"), p)
        self.assertFalse(os.path.exists(P.DEFAULT_ENV_BAK))
        self.assertEqual(P.validate_config()[0], 0)
        self.assertEqual(P.disable_custom_config(), "")   # not in custom mode: nothing to do
        page = read(os.path.join(REPO, "panel/web/src/composables/useSettings.js"))
        self.assertIn("自定义模式里的改动不会带过去", page)

    def test_no_saved_default_state_gives_a_new_node(self):
        self._custom_with_extra_node()
        for p in (P.NODES_TSV, P.INBOUNDS, P.PROXIES_JSON, P.PROVIDERS_JSON):
            os.remove(p + ".tplbak")   # e.g. custom mode entered by a version that kept nothing
        self.assertEqual(self._disable(), "reset")
        self.assertEqual(len(P.read_nodes()), 1)
        self.assertEqual(P.load_inbounds(), [])   # the custom config's nodes are not carried over
        self.assertNotIn("only-in-custom", read(P.CONF))
        self.assertEqual(P.validate_config()[0], 0)

    def test_saved_default_state_refused_gives_a_new_node(self):
        self._custom_with_extra_node()
        inbs = json.loads(read(P.INBOUNDS + ".tplbak"))
        inbs[0]["listener"]["type"] = "no-such-type"   # the template cannot render it -> mihomo -t fails
        with open(P.INBOUNDS + ".tplbak", "w") as f:
            json.dump(inbs, f)
        self.assertEqual(self._disable(), "reset")
        self.assertEqual(len(P.read_nodes()), 1)
        self.assertEqual(P.load_inbounds(), [])
        self.assertEqual(P.validate_config()[0], 0)


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


class CustomInboundOptionsTest(unittest.TestCase):
    """1.44: with custom server on, the add-node form also shows the options the safe defaults lock
    (passwords, cipher, UUID ...). Blank: the default, as before; not in custom mode: ignored."""

    def setUp(self):
        self.env = P.read_env()

    def build(self, kind, advanced=True, **adv):
        form = {"port": "", "name": ""}
        form.update({"adv_" + k: v for k, v in adv.items()})
        return P.build_inbound(kind, form, self.env, advanced=advanced)

    def test_typed_options_are_used(self):
        ss = self.build("shadowsocks", cipher="chacha20-ietf-poly1305", **{"pass" + "word": "my-pass"})
        self.assertEqual((ss["listener"]["cipher"], ss["listener"]["password"]), ("chacha20-ietf-poly1305", "my-pass"))
        self.assertEqual((ss["client"]["cipher"], ss["client"]["password"]), ("chacha20-ietf-poly1305", "my-pass"))
        k = self.build("shadowsocks", cipher="2022-blake3-aes-128-gcm")   # key generated with the right length
        import base64
        self.assertEqual(len(base64.b64decode(k["listener"]["password"])), 16)
        hy = self.build("hysteria2", obfs="off", **{"pass" + "word": "hy-pass"})
        self.assertEqual(hy["listener"]["users"], {"user": "hy-pass"})
        self.assertNotIn("obfs", hy["listener"])
        self.assertNotIn("obfs", hy["client"])
        uid = "11111111-2222-4333-8444-555555555555"
        vr = self.build("vless-reality", uuid=uid, short_id="ABCD", vless_enc="off")
        self.assertEqual((vr["listener"]["users"][0]["uuid"], vr["listener"]["reality-config"]["short-id"]), (uid, ["abcd"]))
        self.assertNotIn("decryption", vr["listener"])
        self.assertNotIn("encryption", vr["client"])
        so = self.build("socks", username="alice", **{"pass" + "word": "pw-alice"})
        self.assertEqual(so["listener"]["users"], [{"username": "alice", "password": "pw-alice"}])
        su = self.build("sudoku", aead="aes-128-gcm", table="prefer_entropy")
        self.assertEqual((su["listener"]["aead-method"], su["listener"]["table-type"]), ("aes-128-gcm", "prefer_entropy"))

    def test_blank_or_not_custom_keeps_the_defaults(self):
        ss = self.build("shadowsocks")
        self.assertEqual(ss["listener"]["cipher"], "aes-256-gcm")
        self.assertGreaterEqual(len(ss["listener"]["password"]), 16)
        ss = self.build("shadowsocks", advanced=False, cipher="chacha20-ietf-poly1305", **{"pass" + "word": "x"})
        self.assertEqual(ss["listener"]["cipher"], "aes-256-gcm")
        self.assertNotEqual(ss["listener"]["password"], "x")
        hy = self.build("hysteria2", advanced=False, obfs="salamander")   # 1.45: no obfuscation by default
        self.assertNotIn("obfs", hy["listener"])
        self.assertNotIn("obfs", hy["client"])
        hy = self.build("hysteria2", obfs="salamander")
        self.assertEqual((hy["listener"]["obfs"], hy["client"]["obfs"]), ("salamander", "salamander"))
        self.assertEqual(hy["listener"]["obfs-password"], hy["client"]["obfs-password"])
        r = P.rotate_inbound_credentials(hy)
        self.assertNotEqual(r["listener"]["obfs-password"], hy["listener"]["obfs-password"])
        self.assertEqual(r["listener"]["obfs-password"], r["client"]["obfs-password"])
        plain = P.rotate_inbound_credentials(self.build("hysteria2", advanced=False))
        self.assertNotIn("obfs", plain["listener"])   # a reset does not turn obfuscation on

    def test_bad_values_are_refused(self):
        for kind, adv in (("shadowsocks", {"cipher": "rc4"}), ("shadowsocks", {"password": "a b"}),
                          ("shadowsocks", {"cipher": "2022-blake3-aes-256-gcm", "password": "short"}),
                          ("vless-reality", {"uuid": "nope"}), ("vless-reality", {"short_id": "xyz"}),
                          ("vless-reality", {"reality_key": "bad"}), ("socks", {"username": "a b"}),
                          ("snell", {"psk": "short"}), ("sudoku", {"aead": "rc4"})):
            with self.assertRaises(ValueError, msg=(kind, adv)):
                self.build(kind, **adv)

    def test_vless_encryption_is_minimal(self):
        """1.45: VLESS Encryption on plain TCP: one user with Vision and the ML-KEM decryption, nothing else."""
        n = self.build("vless-enc", advanced=False)
        lst, cli = n["listener"], n["client"]
        self.assertEqual(set(lst), {"name", "type", "port", "listen", "users", "decryption"})
        self.assertEqual(lst["users"][0]["flow"], "xtls-rprx-vision")
        self.assertTrue(lst["decryption"].startswith("mlkem768x25519plus.native.600s."))
        self.assertTrue(cli["encryption"].startswith("mlkem768x25519plus.native.0rtt."))
        self.assertEqual((cli["type"], cli["flow"], cli["udp"]), ("vless", "xtls-rprx-vision", True))   # UDP via XUDP
        self.assertNotIn("tls", cli)
        self.assertEqual(P.derive_vless_encryption(lst["decryption"]), cli["encryption"])   # seed -> client key
        self.assertEqual(P.ufw_specs_for_node("vless-enc", 31234), {"31234/tcp"})
        uid = "11111111-2222-4333-8444-555555555555"
        self.assertEqual(self.build("vless-enc", uuid=uid)["client"]["uuid"], uid)
        r = P.rotate_inbound_credentials(n)
        self.assertNotEqual(r["listener"]["decryption"], lst["decryption"])
        self.assertNotEqual(r["client"]["uuid"], cli["uuid"])
        self.assertEqual(r["listener"]["users"][0]["uuid"], r["client"]["uuid"])
        self.assertEqual(r["listener"]["users"][0]["flow"], "xtls-rprx-vision")
        self.assertTrue(P.can_reset_inbound_password(n))

    def test_vless_xhttp(self):
        """1.45, custom server only: VLESS XHTTP with the certificate and VLESS Encryption; plain options,
        blank host = this server's domain."""
        with self.assertRaises(ValueError):
            self.build("vless-xhttp", advanced=False)
        for bad in ({"host": "not a host"}, {"path": "no-slash"}, {"mode": "fast"}, {"uuid": "nope"}):
            with self.assertRaises(ValueError, msg=bad):
                self.build("vless-xhttp", **bad)
        n = self.build("vless-xhttp")
        lst, cli = n["listener"], n["client"]
        dom = self.env["DOMAIN"].removeprefix("*.")
        self.assertEqual(lst["xhttp-config"]["host"], dom)
        self.assertEqual(lst["xhttp-config"]["mode"], "auto")
        self.assertTrue(lst["xhttp-config"]["path"].startswith("/"))
        self.assertEqual((lst["certificate"], lst["private-key"]), (P.CERT, P.KEY))
        self.assertNotIn("flow", lst["users"][0])   # Vision does not run over XHTTP
        self.assertTrue(lst["decryption"].startswith("mlkem768x25519plus."))
        self.assertEqual((cli["server"], cli["servername"], cli["network"], cli["tls"]), (dom, dom, "xhttp", True))
        self.assertEqual(cli["xhttp-opts"], lst["xhttp-config"])
        self.assertTrue(cli["encryption"].startswith("mlkem768x25519plus.native.0rtt."))
        t = self.build("vless-xhttp", host="Edge.Example.com", path="/x", mode="packet-up", vless_enc="off")
        self.assertEqual(t["listener"]["xhttp-config"], {"path": "/x", "host": "edge.example.com", "mode": "packet-up"})
        self.assertEqual(t["client"]["server"], "edge.example.com")
        self.assertNotIn("decryption", t["listener"])
        self.assertNotIn("encryption", t["client"])
        # unchanged in a re-read custom config: the stored client (client key) is kept
        again = P.listener_to_inbound(json.loads(json.dumps(lst)), self.env, {n["name"]: n})
        self.assertEqual((again["kind"], again["client"]), ("vless-xhttp", cli))
        ib = read(os.path.join(REPO, "panel/web/src/composables/useInbounds.js"))
        self.assertIn("customOnly: true", ib[ib.index("value: 'vless-xhttp'"):][:400])
        page = read(os.path.join(REPO, "panel/web/src/pages/InboundsPage.vue"))
        self.assertIn('<option v-if="!p.customOnly || state.custom_server_enabled"', page)

    def test_no_zero_rtt_and_tls_by_default(self):
        """1.45: new TUIC / ShadowQUIC nodes have no 0-RTT; HTTP / SOCKS5 use TLS when there is a certificate."""
        tu = self.build("tuic", advanced=False)
        self.assertNotIn("reduce-rtt", tu["client"])
        sq = self.build("shadowquic", advanced=False)
        self.assertIs(sq["listener"]["zero-rtt"], False)
        self.assertNotIn("zero-rtt", sq["client"])
        for k in ("quic-version-probe", "max-idle-time", "disable-mtu-discovery"):
            self.assertNotIn(k, sq["listener"])
        self.assertTrue(P.certs_present())
        for kind in ("http", "socks"):
            on = self.build(kind, advanced=False)
            self.assertTrue(on["client"]["tls"], kind)
            self.assertIn("certificate", on["listener"])
            off = P.build_inbound(kind, {"port": "", "name": "", f"{kind}_tls": "0"}, self.env)
            self.assertFalse(off["client"]["tls"], kind)

    def test_form_shows_the_locked_options_in_custom_mode(self):
        src = os.path.join(REPO, "panel/web/src")
        page = read(os.path.join(src, "pages/InboundsPage.vue"))
        badge = page[:page.index("t('安全默认策略')")][-200:]
        self.assertIn('v-if="!state.custom_server_enabled"', badge)
        self.assertIn('v-if="!state.custom_server_enabled" class="rounded-xl bg-[#f1f6fe]', page)   # locked note
        self.assertIn('v-if="state.custom_server_enabled && (ADV_FIELDS[inboundForm.kind] || []).length"', page)
        self.assertNotIn("submitAddRaw", page)
        self.assertNotIn("cg-seg", page)
        ib = read(os.path.join(src, "composables/useInbounds.js"))
        self.assertIn("if (state.custom_server_enabled) {", ib)
        self.assertIn("payload['adv_' + f.key] = v", ib)
        # 1.45: every select starts on its '' (默认) option instead of showing blank
        self.assertIn("adv: advDefaults('vless-reality'),", ib)
        self.assertIn("inboundForm.adv = advDefaults(newKind)", ib)
        adv = ib[ib.index("const ADV_FIELDS"):ib.index("const PROTOCOLS")]
        self.assertEqual(adv.count("options:"), adv.count("[{ value: '', desc: '"))
        self.assertNotIn("desc: 'VLESS Encryption'", adv)   # the switch is 量子加密, not the protocol name
        kinds = set(re.findall(r"^    '?([a-z0-9-]+)'?: \[", ib[ib.index("const ADV_FIELDS"):ib.index("const DEFAULT_NAMES")], re.M))
        self.assertEqual(kinds, {p for p in re.findall(r"value: '([a-z0-9-]+)',\n      label", ib)})   # every protocol
        h = read(os.path.join(REPO, "panel/cg_http.py"))
        self.assertIn('advanced=bool(load_panel_settings().get("custom_server_enabled"))', h)
        self.assertNotIn("/inbounds/add-raw", h)
        st = read(os.path.join(src, "composables/useSettings.js"))
        tog = st[st.index("async function toggleCustomServer"):]
        tog = tog[:tog.index("\n  }\n")]
        self.assertIn("if (!next) {", tog)   # always asks before turning custom server off
        self.assertIn("关闭并切回默认模式", tog)   # 1.47: back to the default mode as it was


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

    def _two_members(self):
        st, _, _ = self._state()
        a = st["links"][0]
        b = json.loads(json.dumps(a))
        b.update(id="def456", instance="b" * 32, name="大阪", url="https://osaka.example.com:8443")
        b["in"]["port"] = 31002
        st["links"].append(b)
        return st, a, b

    def test_waiting_entries_go_with_the_members_that_reported_them(self):
        """1.40: a 等待互联 entry stayed forever after the member that reported it was removed (and had
        no button). It now goes with those members, and the page can dismiss it."""
        st, a, b = self._two_members()
        st["pending"] = [
            {"instance": "e" * 32, "name": "硅谷", "url": "https://us.example.com:29535", "error": "x", "via": [a["instance"]]},
            {"instance": "f" * 32, "name": "旧", "url": "", "error": "x"},   # written by 1.39 (no via)
        ]
        P.save_cluster(st)
        self.assertEqual([p["name"] for p in P.load_cluster()["pending"]], ["硅谷", "旧"])
        with mock.patch.dict(P._cluster_commit.__globals__, {"apply_cluster_live": lambda *a, **k: None}):
            P._drop_links({a["instance"]})
        self.assertEqual([p["name"] for p in P.load_cluster()["pending"]], ["旧"])   # only A knew 硅谷
        with mock.patch.dict(P._cluster_commit.__globals__, {"apply_cluster_live": lambda *a, **k: None}):
            P._drop_links({b["instance"]})
        self.assertEqual(P.load_cluster()["pending"], [])   # no members left: nothing is waiting
        self.assertEqual(P.public_cluster_state(False)["pending"], [])
        # a file that still lists them (written before 1.40) shows nothing either
        st["links"] = []
        raw = {"instance": st["instance"], "links": [], "pending": st["pending"], "removed": {}}
        with open(P.CLUSTER_JSON, "w") as f:
            json.dump(raw, f)
        self.assertEqual(P.load_cluster()["pending"], [])
        # 检查 with no members says so and cleans the file too (the page showed 等待互联 next to that message)
        h = object.__new__(P.Panel)
        h.headers = {}
        got = {}
        h.respond_mutation = lambda s, msg, ok=True, detail="": got.update(ok=ok, msg=msg)
        h.do_cluster_sync({}, {})
        self.assertEqual(got, {"ok": True, "msg": "集群里还没有其他面板"})
        self.assertEqual(json.loads(read(P.CLUSTER_JSON))["pending"], [])

    def test_dismiss_a_waiting_entry(self):
        st, a, b = self._two_members()
        st["pending"] = [{"instance": "e" * 32, "name": "硅谷", "url": "https://us.example.com:29535", "error": "x",
                          "via": [a["instance"]]}]
        P.save_cluster(st)
        pub = P.public_cluster_state(False)["pending"]
        self.assertEqual(len(pub), 1)
        self.assertNotIn("e" * 32, json.dumps(pub))   # the page gets an id, not the panel's instance id
        h = object.__new__(P.Panel)
        got = {}
        h.respond_mutation = lambda s, msg, ok=True, detail="": got.update(ok=ok, msg=msg)
        h.do_cluster_dismiss({}, {"id": pub[0]["id"]})
        self.assertTrue(got["ok"], got)
        self.assertIn("硅谷", got["msg"])
        self.assertEqual(P.load_cluster()["pending"], [])
        self.assertEqual(len(P.load_cluster()["links"]), 2)   # members untouched
        h.do_cluster_dismiss({}, {"id": pub[0]["id"]})
        self.assertEqual(got, {"ok": True, "msg": "这条等待互联的记录已经不在了"})

    def _no_staged(self):
        if P._STAGED.get("timer"):
            P._STAGED["timer"].cancel()
        P._STAGED.clear()
        P._STAGED["on"] = False

    def test_one_reload_per_operation(self):
        """1.40: exchange first, then apply: inside cluster_batch nothing reloads until the end, and then
        this core reloads once (it used to reload after every link)."""
        self.addCleanup(self._no_staged)
        st, a, b = self._two_members()
        st["links"] = [a]
        P.save_cluster(st)
        g = P._cluster_commit.__globals__
        calls = []
        with mock.patch.dict(g, {"apply_cluster_live": lambda *x, **k: calls.append(1)}):
            with P.cluster_batch():
                P._cluster_commit(lambda s: s["links"].append(json.loads(json.dumps(b))))
                P._cluster_commit(lambda s: s["links"][0].update(name="东京-2"))
                with P.cluster_batch():   # nested: still one reload
                    P._cluster_commit(lambda s: None)
                self.assertEqual(calls, [])
                self.assertTrue(P._STAGED["on"])
                self.assertEqual(len(P.load_cluster()["links"]), 2)   # saved as they are made
            self.assertEqual(calls, [1])
            self.assertFalse(P._STAGED["on"])
            with P.cluster_batch():   # nothing changed: no reload
                pass
            self.assertEqual(calls, [1])
        # Outside a batch every change still applies at once.
        with mock.patch.dict(g, {"apply_cluster_live": lambda *x, **k: calls.append(2)}):
            P._cluster_commit(lambda s: None)
        self.assertEqual(calls, [1, 2])

    def test_batch_applies_every_touched_panel_after_the_exchange(self):
        """The other panels staged their side (join / connect with defer=1); the batch sends each one
        /api/cluster/apply after all exchanges, then applies here. A panel that answers with a failure
        has undone its side: the link made with it this time is dropped here too."""
        self.addCleanup(self._no_staged)
        st, a, b = self._two_members()
        st["links"] = [a]
        P.save_cluster(st)
        g = P._cluster_commit.__globals__
        order = []

        def fake_http(base, path, data=None, timeout=15):
            order.append((path, base))
            if path == "/api/cluster/apply" and base == b["url"]:
                return 500, {"ok": False, "code": "apply_failed", "msg": "boom"}, "clashgate"
            return 200, {"ok": True}, "clashgate"

        with mock.patch.dict(g, {"apply_cluster_live": lambda *x, **k: order.append(("local", ""))}), \
                mock.patch.dict(g, {"cluster_http": fake_http}):
            with P.cluster_batch() as bt:
                P._cluster_commit(lambda s: s["links"].append(json.loads(json.dumps(b))))
                P._CLUSTER_BATCH.new[b["instance"]] = (b["url"], "c" * 32, "key-b")
                P._CLUSTER_BATCH.touch.update({a["instance"], b["instance"]})
                self.assertEqual(order, [])   # nothing applied while exchanging
        applies = [x for x in order if x[0] == "/api/cluster/apply"]
        self.assertEqual(sorted(x[1] for x in applies), sorted([a["url"], b["url"]]))
        self.assertEqual(order[-1], ("local", ""))   # this panel last, once
        self.assertEqual(order.count(("local", "")), 1)
        self.assertEqual(bt.failed, ["大阪"])
        self.assertEqual([l["name"] for l in P.load_cluster()["links"]], ["东京-1"])   # undone here
        self.assertIn("已撤销", P.cluster_batch_text(bt))

    def test_remote_apply_results(self):
        l = self._two_members()[1]
        g = P._remote_apply.__globals__
        for answer, want in (((200, {"ok": True}, ""), "ok"),
                             ((401, {"ok": False, "msg": "登录会话已过期"}, ""), "ok"),   # panel before 1.40
                             ((500, {"ok": False, "code": "apply_failed", "msg": "x"}, ""), "failed"),
                             ((403, {"ok": False, "code": "bad_token", "msg": "x"}, ""), "failed")):
            with mock.patch.dict(g, {"cluster_http": lambda *x, **k: answer}):
                self.assertEqual(P._remote_apply(l)[0], want, answer)

        def down(*x, **k):
            raise P.ClusterTimeout("连接对方面板超时，请检查地址、端口和对方防火墙")
        with mock.patch.dict(g, {"cluster_http": down}):
            self.assertEqual(P._remote_apply(l)[0], "later")   # it applies by itself after CLUSTER_STAGE_TTL

    def test_staged_links_apply_by_themselves(self):
        """A panel that staged a link (defer=1) but never got /api/cluster/apply applies it after the TTL;
        a direct change meanwhile applies the staged ones with it."""
        self.addCleanup(self._no_staged)
        st, a, b = self._two_members()
        st["links"] = [a]
        P.save_cluster(st)
        g = P._cluster_commit.__globals__
        calls = []
        with mock.patch.dict(g, {"apply_cluster_live": lambda *x, **k: calls.append(x)}):
            P._CLUSTER_BATCH.defer = 1
            try:
                P._cluster_commit(lambda s: s["links"].append(json.loads(json.dumps(b))))
            finally:
                P._CLUSTER_BATCH.defer = 0
            self.assertTrue(P._STAGED["on"] and P._STAGED["timer"].is_alive())
            self.assertEqual(P._STAGED["timer"].interval, P.CLUSTER_STAGE_TTL)
            g["_staged_timeout"]()
            self.assertEqual(len(calls), 1)
            self.assertFalse(P._STAGED["on"])
            self.assertFalse(P.cluster_apply_staged())   # nothing left
            # staged again, then a direct change: one reload covers both, staged state cleared
            P._CLUSTER_BATCH.defer = 1
            try:
                P._cluster_commit(lambda s: s["links"][1].update(name="大阪-2"))
            finally:
                P._CLUSTER_BATCH.defer = 0
            P._cluster_commit(lambda s: None)
            self.assertEqual(len(calls), 2)
            self.assertFalse(P._STAGED["on"])

    def test_failed_batch_reload_undoes_its_links(self):
        self.addCleanup(self._no_staged)
        st, a, b = self._two_members()
        st["links"] = [a]
        P.save_cluster(st)
        before = read(P.CLUSTER_JSON)
        g = P._cluster_commit.__globals__
        told = []

        def bad_apply(*x, **k):
            raise RuntimeError("配置校验失败（mihomo -t）：boom")

        def fake_http(base, path, data=None, timeout=15):
            told.append((base, path, dict(data or {})))
            return 200, {"ok": True}, "clashgate"

        with mock.patch.dict(g, {"apply_cluster_live": bad_apply, "cluster_http": fake_http}):
            with self.assertRaises(P.ClusterError) as cm:
                with P.cluster_batch():
                    P._cluster_commit(lambda s: s["links"].append(json.loads(json.dumps(b))))
                    P._CLUSTER_BATCH.new[b["instance"]] = ("https://osaka.example.com:8443", "c" * 32, "key-b")
        self.assertIn("已撤销", str(cm.exception))
        self.assertEqual(read(P.CLUSTER_JSON), before)
        self.assertEqual(told, [("https://osaka.example.com:8443", "/api/cluster/leave", {"instance": "c" * 32, "key": "key-b"})])
        self.assertFalse(P._deferring() or P._STAGED["on"])

    def test_join_and_connect_stage_when_asked(self):
        h = read(os.path.join(REPO, "panel/cg_http.py"))
        for fn in ("def do_cluster_join", "def do_cluster_connect"):
            body = h[h.index(fn):]
            body = body[:body.index("\n    def ", 10)]
            self.assertIn('_CLUSTER_BATCH.defer = 1 if form.get("defer") == "1" else 0', body, fn)
            self.assertIn("_CLUSTER_BATCH.defer = 0", body[body.index("finally:"):], fn)
        self.assertIn('if path == "/api/cluster/apply":', h)
        cl = read(os.path.join(REPO, "panel/cg_cluster.py"))
        self.assertIn('**({"defer": "1"} if _deferring() else {})', cl[cl.index("def cluster_pair"):])
        mesh = cl[cl.index("# 3. link members with each other"):]
        self.assertIn('"defer": "1"', mesh[:mesh.index("rep[\"meshed\"] += 1")])

    def _sync_with(self, introduce):
        """cluster_sync where both members know 硅谷 (not linked here); introduce(link) answers for each."""
        st, a, b = self._two_members()
        P.save_cluster(st)
        g = P.cluster_sync.__globals__
        paired = []
        us = {"instance": "e" * 32, "name": "硅谷", "url": "https://us.example.com:29535"}

        def fake_call(l, path, extra=None, timeout=30, fallback=""):
            if path == "/api/cluster/status":
                others = [{"instance": x["instance"], "name": x["name"]} for x in (a, b) if x["instance"] != l["instance"]]
                return {"ok": True, "name": l["name"], "members": [dict(us)] + others}
            if path == "/api/cluster/introduce":
                return introduce(l)
            return {"ok": True}

        def fake_pair(base, auth, expect_instance=""):
            paired.append((base, auth, expect_instance))
            def add(s):
                l = json.loads(json.dumps(b))
                l.update(id="aaa999", instance=expect_instance, name="硅谷", url=base)
                l["in"]["port"] = 31003
                s["links"].append(l)
            s = P.load_cluster()
            add(s)
            P.save_cluster(s)
            return s["links"][-1], []

        with mock.patch.dict(g, {"cluster_call": fake_call, "cluster_pair": fake_pair,
                                 "apply_cluster_live": lambda *x, **k: None}):
            rep = P.cluster_sync()
        return rep, paired

    def test_sync_asks_the_next_member_when_one_cannot_reach_the_panel(self):
        def introduce(l):
            if l["name"] == "东京-1":
                raise P.ClusterRemoteError("对方面板没有响应集群请求：连接对方面板超时，请检查地址、端口和对方防火墙",
                                           "unreachable", "连接对方面板超时，请检查地址、端口和对方防火墙")
            return {"ok": True, "ticket": "t-osaka", "url": "https://us.example.com:29535", "instance": "e" * 32}

        rep, paired = self._sync_with(introduce)
        self.assertEqual(rep["linked"], ["硅谷"])
        self.assertEqual(paired, [("https://us.example.com:29535", {"ticket": "t-osaka"}, "e" * 32)])
        self.assertEqual(P.load_cluster()["pending"], [])

    def test_sync_names_the_members_that_cannot_reach_a_waiting_panel(self):
        def introduce(l):
            raise P.ClusterRemoteError("对方面板没有响应集群请求：连接对方面板超时，请检查地址、端口和对方防火墙",
                                       "unreachable", "连接对方面板超时，请检查地址、端口和对方防火墙")

        rep, paired = self._sync_with(introduce)
        self.assertEqual((rep["linked"], paired, rep["failed"]), ([], [], ["硅谷"]))
        (p,) = P.load_cluster()["pending"]
        self.assertEqual(p["error"], "「东京-1、大阪」现在也连不上它：连接对方面板超时，请检查地址、端口和对方防火墙")
        self.assertEqual(sorted(p["via"]), sorted(["a" * 32, "b" * 32]))

    def test_ticket_request_retries_a_timeout_once(self):
        st, a, b = self._two_members()
        g = P.cluster_issue_ticket.__globals__
        calls = []

        def flaky(l, path, extra=None, timeout=30, fallback=""):
            calls.append(dict(extra))
            if len(calls) == 1:
                raise P.ClusterTimeout("连接对方面板超时，请检查地址、端口和对方防火墙")
            return {"ok": True}

        with mock.patch.dict(g, {"cluster_call": flaky}):
            ticket = P.cluster_issue_ticket(b, a)
        self.assertTrue(ticket)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0], calls[1])   # the same ticket both times
        calls.clear()

        def down(l, path, extra=None, timeout=30, fallback=""):
            calls.append(1)
            raise P.ClusterTimeout("连接对方面板超时，请检查地址、端口和对方防火墙")

        with mock.patch.dict(g, {"cluster_call": down}):
            with self.assertRaises(P.ClusterTimeout):
                P.cluster_issue_ticket(b, a)
        self.assertEqual(len(calls), 2)   # one retry, not more

    def test_retry_a_member(self):
        """1.40: 「重试」 next to 「移除」 on a member that failed: ask it again, then a full 检查."""
        self.addCleanup(self._no_staged)
        st, a, b = self._two_members()
        a.update(ok=False, error="连接对方面板超时，请检查地址、端口和对方防火墙")
        P.save_cluster(st)
        h = object.__new__(P.Panel)
        h.headers = {}
        got = {}
        h.respond_mutation = lambda s, msg, ok=True, detail="": got.update(ok=ok, msg=msg)
        g = P.Panel.do_cluster_retry.__globals__   # cg_http: the handler's own cluster_call / cluster_sync
        synced = []

        def down(l, path, extra=None, timeout=30, fallback=""):
            raise P.ClusterTimeout("连接对方面板超时，请检查地址、端口和对方防火墙")

        with mock.patch.dict(g, {"cluster_call": down}):
            h.do_cluster_retry({}, {"id": a["id"]})
        self.assertFalse(got["ok"])
        self.assertEqual(got["msg"], "「东京-1」仍然连接失败：连接对方面板超时，请检查地址、端口和对方防火墙")

        def up(l, path, extra=None, timeout=30, fallback=""):
            return {"ok": True, "name": l["name"], "members": []}

        def fake_sync():
            synced.append(1)
            P._update_link(a["instance"], ok=True, error="")
            return {"linked": [], "meshed": 0, "failed": [], "dropped": [], "offline": []}

        with mock.patch.dict(g, {"cluster_call": up, "cluster_sync": fake_sync}):
            h.do_cluster_retry({}, {"id": a["id"]})
        self.assertEqual(got, {"ok": True, "msg": "已重新连上「东京-1」"})
        self.assertEqual(synced, [1])
        self.assertIsNot(P.public_cluster_state(False)["members"][0]["ok"], False)
        h.do_cluster_retry({}, {"id": "nope"})
        self.assertEqual(got, {"ok": False, "msg": "集群成员不存在"})
        page = read(os.path.join(REPO, "panel/web/src/pages/ClusterPage.vue"))
        row = page[page.index('v-for="m in state.cluster.members"'):page.index('v-for="p in state.cluster.pending"')]
        self.assertIn('@click="retryClusterMember(m)"', row)
        self.assertIn('v-if="m.ok === false || (m.missing && m.missing.length)"', row)
        self.assertIn("t('连接失败')", row)
        self.assertNotIn("联系不上", page)

    def test_reset_template_turns_custom_server_off(self):
        """1.41: 恢复默认服务端模板 also turns custom server off and keeps the user's file for later."""
        P.save_panel_settings({"custom_server_enabled": True})
        P.atomic_write(P.CUSTOM_CONF, P.assemble_config(), 0o640)
        mine = read(P.CUSTOM_CONF)
        h = object.__new__(P.Panel)
        h.headers = {}
        got = {}
        h.respond_mutation = lambda s, msg, ok=True, detail="": got.update(ok=ok, msg=msg)
        try:
            with mock.patch.dict(P.reset_to_template_config.__globals__, {"wait_mihomo_ports": lambda *a, **k: True}):
                h.do_reset_template_config({})
            self.assertTrue(got["ok"], got)
            self.assertIn("关闭自定义服务端", got["msg"])
            self.assertFalse(P.load_panel_settings().get("custom_server_enabled"))
            self.assertFalse(P.is_custom_config_mode())
            self.assertEqual(read(P.CUSTOM_SAVED), mine)
        finally:
            for f in (P.CUSTOM_CONF, P.CUSTOM_SAVED):
                if os.path.exists(f):
                    os.remove(f)
            P.save_panel_settings({"custom_server_enabled": False})
        page = read(os.path.join(REPO, "panel/web/src/composables/useCustomConfig.js"))
        body = page[page.index("function resetTemplateConfig"):]
        self.assertIn("openConfirmDialog(", body[:300])
        self.assertIn("selectTab('inbounds')", body)

    def test_leaving_drops_the_links_here_first(self):
        """1.41: 退出集群 changes this panel's config first and tells the members in the background."""
        st, a, b = self._two_members()
        P.save_cluster(st)
        release = threading.Event()
        told = []

        def slow_call(l, path, extra=None, timeout=30, fallback=""):
            release.wait(5)
            told.append((l["name"], path))
            return {"ok": True}

        g = P.cluster_leave_all.__globals__
        with mock.patch.dict(g, {"cluster_call": slow_call, "apply_cluster_live": lambda *x, **k: None}):
            t0 = time.monotonic()
            n, missed = P.cluster_leave_all(background=True)
            self.assertLess(time.monotonic() - t0, 2)   # did not wait for the members
            self.assertEqual((n, missed), (2, []))
            self.assertEqual(P.load_cluster()["links"], [])   # dropped before anyone was told
            self.assertEqual(told, [])
            release.set()
            for _ in range(100):
                if len(told) == 2:
                    break
                time.sleep(0.02)
        self.assertEqual(sorted(told), [("东京-1", "/api/cluster/leave"), ("大阪", "/api/cluster/leave")])
        self.assertEqual(P.cluster_leave_all(background=True), (0, []))

    def _shared_state(self):
        """Two members as 1.42 makes them: one user each in the shared cluster inbound."""
        st, _, _ = self._two_members()
        dec, enc = P.vless_mlkem768_pair()
        st["inbound"] = {"port": 31050, "decryption": dec, "encryption": enc}
        for l in st["links"]:
            l["in"] = {"uuid": "%s-0000-4000-8000-000000000000" % l["id"][:6].ljust(8, "0")}
        return st, dec, enc

    def test_one_cluster_inbound_for_every_member(self):
        """1.42: each panel has one cluster inbound; every member is a user (its own UUID) in it.
        Adding or removing a member never changes the port or the keys."""
        st, dec, enc = self._shared_state()
        P.save_cluster(st)
        conf = P.assemble_config()
        P.atomic_write(P.CONF, conf, 0o640)
        rc, out = P.validate_config()
        self.assertEqual(rc, 0, out)
        lst, prox = P._conf_cluster_entries(conf)
        self.assertEqual([x["name"] for x in lst], [P.CLUSTER_SHARED_LISTENER])
        self.assertEqual((lst[0]["port"], lst[0]["decryption"], lst[0]["proxy"]), (31050, dec, "DIRECT"))
        self.assertEqual([u["uuid"] for u in lst[0]["users"]], [l["in"]["uuid"] for l in st["links"]])
        self.assertEqual(len(prox), 2)
        self.assertEqual(P.cluster_ports(), {31050})
        self.assertEqual(P.cluster_ufw_specs(), {"31050/tcp"})
        g = P._cluster_commit.__globals__
        with mock.patch.dict(g, {"apply_cluster_live": lambda *a, **k: None}):
            P._drop_links({st["links"][0]["instance"]})
            lst = P.cluster_listeners(P.load_cluster())
            self.assertEqual([(x["port"], len(x["users"])) for x in lst], [(31050, 1)])
            P._drop_links({st["links"][1]["instance"]})
        self.assertEqual(P.cluster_listeners(P.load_cluster()), [])
        self.assertEqual(P.load_cluster()["inbound"]["port"], 31050)   # kept for the next member
        self.assertIn(31050, P.cluster_reserved_ports())
        self.assertIn(31050, P.used_ports(P.read_env()))

    def test_new_members_share_the_inbound(self):
        a = P._cluster_new_inbound()
        b = P._cluster_new_inbound()
        self.assertEqual((a["port"], a["_enc"], a["decryption"]), (b["port"], b["_enc"], b["decryption"]))
        self.assertNotEqual(a["uuid"], b["uuid"])
        self.assertEqual(json.loads(read(P.CLUSTER_JSON))["inbound"]["port"], a["port"])
        self.assertIn(a["port"], P.used_ports(P.read_env()))
        src = read(os.path.join(REPO, "panel/cg_cluster.py")) + read(os.path.join(REPO, "panel/cg_http.py"))
        self.assertEqual(src.count('"in": {"uuid": inb["uuid"]}'), 2)   # cluster_pair and the join handler
        self.assertNotIn('"in": {k: inb[k]', src)

    def test_old_links_move_to_the_shared_inbound(self):
        """Links made before 1.42 (own inbound each) move when the member is 1.42 too; an older member
        answers 401 to /api/cluster/node and keeps its dedicated inbound for now."""
        self.addCleanup(self._no_staged)
        st, a, b = self._two_members()
        P.save_cluster(st)
        g = P._cluster_commit.__globals__
        calls = []

        def fake_http(base, path, data=None, timeout=15):
            calls.append((base, path, dict(data or {})))
            if path == "/api/cluster/node" and base == b["url"]:
                return 401, {"ok": False, "msg": "登录会话已过期，请刷新页面重新登录"}, "clashgate/1.41"
            return 200, {"ok": True}, "clashgate"

        with mock.patch.dict(g, {"cluster_http": fake_http, "apply_cluster_live": lambda *x, **k: None}):
            with P.cluster_batch():
                moved = P.cluster_migrate_links()
        self.assertEqual(moved, ["东京-1"])
        inb = P.load_cluster()["inbound"]
        sent = [c for c in calls if c[1] == "/api/cluster/node" and c[0] == a["url"]][0][2]
        self.assertEqual((int(sent["port"]), sent["encryption"], sent["defer"]), (inb["port"], inb["encryption"], "1"))
        links = {l["name"]: l for l in P.load_cluster()["links"]}
        self.assertEqual(links["东京-1"]["in"], {"uuid": sent["uuid"]})
        self.assertTrue(P._link_legacy(links["大阪"]))
        names = [x["name"] for x in P.cluster_listeners(P.load_cluster())]
        self.assertEqual(names, [P.CLUSTER_SHARED_LISTENER, P.CLUSTER_LISTENER_PREFIX + b["id"]])
        self.assertIn(("https://tokyo.example.com:8443", "/api/cluster/apply"), [(c[0], c[1]) for c in calls])
        self.assertIsNotNone(P.start_cluster_migration(delay=3600))   # 大阪 still has its own inbound
        P.save_cluster({**P.load_cluster(), "links": [links["东京-1"]]})
        self.assertIsNone(P.start_cluster_migration(delay=3600))      # nothing left to move

    def test_member_points_its_outbound_at_the_new_node(self):
        self.addCleanup(self._no_staged)
        st, a, b = self._two_members()
        P.save_cluster(st)
        h = object.__new__(P.Panel)
        h._cluster_link_auth = lambda form: (P._link_by(P.load_cluster(), instance=a["instance"]), None)
        sent = []
        h._cjson = lambda code, obj: sent.append((code, obj))
        _, enc = P.vless_mlkem768_pair()
        node = {"port": "31077", "uuid": "77777777-7777-4777-8777-777777777777", "encryption": enc}
        with mock.patch.dict(P._cluster_commit.__globals__, {"apply_cluster_live": lambda *x, **k: None}):
            h.do_cluster_node(dict(node, defer="1"))
        self.assertEqual(sent[-1], (200, {"ok": True}))
        out = P._link_by(P.load_cluster(), instance=a["instance"])["out"]
        self.assertEqual(out, {"server": "tokyo.example.com", "port": 31077, "uuid": node["uuid"], "encryption": enc})
        self.assertTrue(P._STAGED["on"])   # staged: the caller sends /api/cluster/apply when done
        h.do_cluster_node({"port": "x"})
        self.assertEqual(sent[-1][0], 400)

    def test_reload_core_waits_before_restarting(self):
        """1.43: `systemctl reload` only sends SIGHUP; the core applies the file afterwards. The panel
        used to check the ports right away and restart (dropping every connection) when a new port was
        not up yet. reload_core waits for the ports and restarts only if they never come up."""
        g = P.reload_core.__globals__
        calls, up = [], {"after": 3}

        def fake_run(cmd, **kw):
            calls.append(cmd[1])
            return (1, "refused") if fake_run.refuse and cmd[1] == "reload" else (0, "")
        fake_run.refuse = False

        def fake_status():
            up["after"] -= 1
            return {"active": "active", "listening": [1000, 2000] if up["after"] <= 0 else [1000],
                    "pid": "1", "version": "", "since": "", "restarts": "", "cert": {}, "uptime": 1}

        with mock.patch.dict(g, {"run": fake_run, "mihomo_status": fake_status}):
            self.assertEqual(P.reload_core({1000, 2000}, timeout=5)[0], 0)
            self.assertEqual(calls, ["reload"])   # the new port came up a moment later: no restart
            calls.clear()
            up["after"] = 10 ** 6
            rc, out = P.reload_core({1000, 2000}, timeout=0.3)
            self.assertEqual((calls, rc), (["reload", "restart"], 1))
            self.assertIn("监听", out)
            calls.clear()
            fake_run.refuse = True   # core not running: reload refused, start it
            up["after"] = 0
            self.assertEqual(P.reload_core({1000}, timeout=1)[0], 0)
            self.assertEqual(calls, ["reload", "restart"])

    def test_config_changes_reload_instead_of_restart(self):
        """Only a new core binary and renewed certificates still restart the core."""
        h = read(os.path.join(REPO, "panel/cg_http.py"))
        act = h[h.index("def do_action"):]
        act = act[:act.index("\n    def ", 10)]
        self.assertIn("reload_core(", act)
        self.assertNotIn("mihomo_status()", act)   # no port check right after the signal
        cfg = read(os.path.join(REPO, "panel/cg_config.py"))
        for fn in ("def apply_custom_config", "def disable_custom_config", "def reset_to_template_config",
                   "def refresh_template_if_flagged"):
            body = cfg[cfg.index(fn):]
            body = body[:body.index("\ndef ", 10)]
            self.assertIn("reload_core(", body, fn)
            self.assertNotIn('rc, out = run([SYSTEMCTL, "restart", "mihomo"])', body, fn)
        cl = read(os.path.join(REPO, "panel/cg_cluster.py"))
        live = cl[cl.index("def apply_cluster_live"):]
        live = live[:live.index("\ndef ", 10)]
        self.assertIn("reload_core(", live)
        up = read(os.path.join(REPO, "panel/cg_update.py"))
        snell = up[up.index("def migrate_snell_to_v6"):]
        snell = snell[:snell.index("\ndef ", 10)]
        self.assertIn("reload_core()", snell)

    def test_update_skips_a_current_core_and_survives_a_failed_download(self):
        """1.43: `clashgate update` compares the core version first; when the version cannot be fetched
        or the download fails, the panel update goes on and the failure is reported at the end."""
        d = tempfile.mkdtemp(prefix="cg-core-")
        self.addCleanup(shutil.rmtree, d, True)
        fake = os.path.join(d, "mihomo")
        with open(fake, "w") as f:
            f.write("#!/bin/sh\necho 'Mihomo Meta v1.19.34 linux amd64 with go1.25'\n")
        os.chmod(fake, 0o755)

        def run_case(body):
            script = (f'log() {{ :; }}; info() {{ :; }}; arch() {{ echo amd64; }}; source scripts/lib/core.sh; '
                      f'CS_ROOT={d}; BIN={fake}; {body}; update_core; '
                      f'echo "UPDATED=$CORE_UPDATED"; echo "NOTE=$CORE_NOTE"; cat {d}/core_update_failed 2>/dev/null; true')
            r = subprocess.run(["bash", "-c", script], cwd=REPO, capture_output=True, text=True, timeout=30)
            return r.stdout + r.stderr

        out = run_case("core_latest() { return 1; }")
        self.assertIn("UPDATED=0", out)
        self.assertIn("无法获取最新版本信息", out)
        self.assertIn("fetch\tv1.19.34", out)
        out = run_case('core_latest() { CORE_TAG=v1.19.34; }; core_download() { echo DOWNLOADED; }')
        self.assertIn("UPDATED=0", out)
        self.assertIn("NOTE=\n", out + "\n")
        self.assertNotIn("DOWNLOADED", out)   # already the latest: nothing downloaded
        self.assertFalse(os.path.exists(os.path.join(d, "core_update_failed")))
        out = run_case('core_latest() { CORE_TAG=v1.19.40; }; core_download() { CORE_ERR=download; return 1; }')
        self.assertIn("UPDATED=0", out)
        self.assertIn("下载失败", out)
        self.assertIn("download\tv1.19.34\tv1.19.40", out)
        out = run_case('core_latest() { CORE_TAG=v1.19.40; }; core_download() { return 0; }')
        self.assertIn("UPDATED=1", out)
        self.assertFalse(os.path.exists(os.path.join(d, "core_update_failed")))
        sh = read(os.path.join(REPO, "scripts/cmd/clashgate.sh"))
        upd = sh[sh.index("do_update() {"):]
        upd = upd[:upd.index("\n}\n")]
        self.assertIn("update_core", upd)
        self.assertNotIn("install_core", upd)
        self.assertIn("systemctl reload mihomo", upd)   # same binary: hot reload
        self.assertIn('warn "$CORE_NOTE"', upd)

    def test_cluster_page_checks_by_itself(self):
        """1.43: 检查 is there with no members too (another panel may have added this one), and opening
        the cluster page runs it once, quietly and at most every 30 minutes (1.45; kept across reloads)."""
        src = os.path.join(REPO, "panel/web/src")
        page = read(os.path.join(src, "pages/ClusterPage.vue"))
        btn = page[:page.index("t('检查中…')")]
        btn = btn[btn.rindex("<button"):]
        self.assertNotIn("v-if", btn)
        cl = read(os.path.join(src, "composables/useCluster.js"))
        auto = cl[cl.index("function autoCheckCluster"):]
        auto = auto[:auto.index("\n  }\n")]
        self.assertIn("{ quiet: true }", auto)
        self.assertIn("< AUTO_CHECK_MS", auto)
        self.assertIn("const AUTO_CHECK_MS = 30 * 60 * 1000", cl)
        self.assertIn("localStorage.setItem(AUTO_CHECK_KEY", auto)
        self.assertIn("busyKey.value || clusterBusy.value", auto)
        panel = read(os.path.join(src, "composables/usePanel.js"))
        self.assertRegex(panel, r"watch\(activeTab, \(tab\) => \{ if \(tab === 'cluster'[^}]*autoCheckCluster\(\)")
        self.assertIn("if (activeTab.value === 'cluster') autoCheckCluster()", panel)   # opened on /cluster
        h = object.__new__(P.Panel)
        h.headers = {}
        got = {}
        h.respond_mutation = lambda s, msg, ok=True, detail="": got.update(ok=ok, msg=msg)
        P.save_cluster({"instance": "c" * 32, "links": [], "pending": [], "removed": {}})
        h.do_cluster_sync({}, {})
        self.assertEqual(got, {"ok": True, "msg": "集群里还没有其他面板"})   # answers at once, with fresh state

    def test_cluster_overlay_lists_the_steps(self):
        """1.44: the add overlay has a progress bar and lists the steps done so far (CgSpinner)."""
        src = os.path.join(REPO, "panel/web/src")
        app = read(os.path.join(src, "App.vue"))
        ov = app[app.index('id="cluster-task-overlay"'):]
        ov = ov[:ov.index("</Transition>")]
        for needle in ('class="cg-progress', "clusterTask.steps.slice(-3)", "<CgSpinner", 'class="cg-step is-now"'):
            self.assertIn(needle, ov)
        cl = read(os.path.join(src, "composables/useCluster.js"))
        self.assertIn("clusterTask.steps.push(clusterTask.stage)", cl)
        for f in ("App.vue", "pages/ClusterPage.vue", "pages/InboundsPage.vue"):
            self.assertNotIn('class="cg-spin', read(os.path.join(src, f)), f)
        self.assertIn("@keyframes cg-spinner-dash", read(os.path.join(src, "style.css")))

    def test_about_page(self):
        """1.44: 设置 -> 关于: version, a short changelog (current version marked) and the credits."""
        src = os.path.join(REPO, "panel/web/src")
        page = read(os.path.join(src, "pages/AboutPage.vue"))
        for url in ("https://github.com/MetaCubeX/mihomo", "https://github.com/XTLS/Xray-core"):
            self.assertIn(f"url: '{url}'", page)
        self.assertIn('target="_blank"', page)
        self.assertIn('rel="noopener noreferrer"', page)
        # 1.46: link to the project's repository; the credits show the projects' own logos, bundled
        # (the CSP allows images from the panel only)
        self.assertIn("const REPO_URL = 'https://github.com/ClashGate/ClashGate'", page)
        self.assertIn(':href="REPO_URL" target="_blank" rel="noopener noreferrer"', page)
        for logo in ("mihomo.png", "xray.png"):
            self.assertIn(f"logo: '/assets/{logo}'", page)
            with open(os.path.join(REPO, "panel/web/public/assets", logo), "rb") as f:
                self.assertEqual(f.read(8), b"\x89PNG\r\n\x1a\n", logo)
        self.assertNotIn("mark: '", page)
        first = page[page.index("const CHANGELOG = ["):].split("\n")[1]
        self.assertTrue(first.strip().startswith(f"{{ v: '{P.VERSION}'"), first)   # newest first: this version
        self.assertLessEqual(page.count("{ v: '"), 8)   # short
        panel = read(os.path.join(src, "composables/usePanel.js"))
        self.assertIn("'about'", panel[panel.index("const VALID_TABS"):panel.index("const TAB_PATHS")])
        self.assertIn("about: '/about'", panel)
        self.assertIn("selectTab('about')", read(os.path.join(src, "pages/SettingsPage.vue")))
        self.assertIn("<AboutPage v-else-if=\"activeTab === 'about'\"", read(os.path.join(src, "App.vue")))
        self.assertIn('if path == "/about":', read(os.path.join(REPO, "panel/cg_http.py")))

    def test_unapplied_node_is_not_copied(self):
        """1.47: a node in the draft (added / new password, not applied) is not served yet: the server sends
        no config for it and leaves it out of 复制全部配置; the page asks to apply first."""
        h = read(os.path.join(REPO, "panel/cg_http.py"))
        self.assertEqual(h.count('"single_config": "" if is_pending else'), 2)
        self.assertEqual(h.count("if not is_pending:\n                all_proxies.append(proxy)"), 2)
        page = read(os.path.join(REPO, "panel/web/src/pages/InboundsPage.vue"))
        self.assertIn('@click="copyNodeConfig(item)"', page)
        self.assertIn('@click="copyAllNodeConfigs"', page)
        fn = page[page.index("function copyNodeConfig"):page.index("function copyAllNodeConfigs")]
        self.assertLess(fn.index("item.pending_reload"), fn.index("copyRaw("))
        self.assertIn("请先点顶部「应用配置」再复制", fn)

    def test_ui_polish_146(self):
        """1.46: every busy 「…中…」 button shows CgSpinner; copy buttons show a check; row actions use the
        shared button classes; the add-node card keeps one height in custom server mode."""
        src = os.path.join(REPO, "panel/web/src")
        busy = re.compile(r"\{\{\s*busyKey === ([^?]+?) \? t\('[^']*中…'\)")
        copied = re.compile(r"\{\{\s*copiedKey === ([^?]+?) \? t\(")
        for dp, _, files in os.walk(src):
            for fn in files:
                if not fn.endswith(".vue"):
                    continue
                page = read(os.path.join(dp, fn))
                for m in busy.finditer(page):
                    btn = page[page.rindex("<button", 0, m.start()):m.start()]
                    self.assertIn("<CgSpinner", btn, (fn, m.group(1)))
                for m in copied.finditer(page):
                    btn = page[page.rindex("<button", 0, m.start()):m.start()]
                    self.assertIn('name="check"', btn, (fn, m.group(1)))
                for bad in ("hover:bg-sky-50", "bg-sky-50 hover:bg-sky-100", "bg-rose-50 hover:bg-rose-100 text-rose-700"):
                    self.assertNotIn(bad, page, (fn, bad))
        home = read(os.path.join(src, "pages/InboundsPage.vue"))
        ghost = home[home.index('class="cg-stack-ghost space-y-4"') - 300:home.index("</div>\n                  <div class=\"space-y-4\">")]
        self.assertIn("PROTOCOLS.filter((x) => !x.customOnly || state.custom_server_enabled)", ghost)
        self.assertIn('v-if="state.custom_server_enabled && (ADV_FIELDS[p.value] || []).length"', ghost)
        self.assertIn('v-for="f in ADV_FIELDS[p.value]"', ghost)

    def test_home_layout_zashboard_right(self):
        css = read(os.path.join(REPO, "panel/web/src/style.css"))
        self.assertIn(".cg-home-zb { grid-column: 2; grid-row: 1; }", css)
        self.assertIn(".cg-home-add { grid-column: 2; grid-row: 2; }", css)
        self.assertIn(".cg-home-add.is-first { grid-row: 1 / span 2; }", css)

    def test_leave_interrupts_a_running_check(self):
        """1.44: 退出集群 during 检查 is not refused: the check stops at its next step and the leave runs."""
        h = object.__new__(P.Panel)
        h.headers = {"X-Requested-With": "fetch"}
        sent, got = [], {}
        h.send = lambda code, body, ctype="", headers=None, cache_key=None: sent.append((code, json.loads(body)))
        h.build_client_state = lambda s, *a: {}
        h.tr = lambda m: m
        h.respond_mutation = lambda s, msg, ok=True, detail="": got.update(ok=ok, msg=msg)
        go, steps = threading.Event(), []

        def check():
            P.cluster_stage("正在检查「东京-1」")
            go.wait(5)
            steps.append("after-wait")
            P.cluster_stage("正在检查「大阪」")   # cancelled here
            steps.append("not reached")
            return "集群成员都在线，互联完整", True

        h._cluster_job({}, check, {"async": "1"}, "sync")
        check_id = sent[-1][1]["id"]
        for _ in range(50):
            if P._CLUSTER_TASK.get("stage"):
                break
            time.sleep(0.02)
        h._cluster_job({}, lambda: ("已添加", True), {"async": "1"}, "add")   # other operations still wait
        self.assertEqual(got["msg"], "另一个集群操作正在进行，请稍候再试")
        h._cluster_job({}, lambda: ("本机已退出集群，正在后台通知其他成员", True), {"async": "1"}, "leave")
        leave_id = sent[-1][1]["id"]
        self.assertEqual((sent[-1][0], sent[-1][1]["running"]), (200, True))
        self.assertNotEqual(leave_id, check_id)
        self.assertTrue(P._CLUSTER_CANCEL.is_set())
        for _ in range(100):
            h.cluster_task_status({})
            if not sent[-1][1]["running"]:
                break
            time.sleep(0.02)
        self.assertEqual((sent[-1][1]["id"], sent[-1][1]["msg"]), (leave_id, "本机已退出集群，正在后台通知其他成员"))
        go.set()
        for _ in range(100):
            if P._CLUSTER_OP_LOCK.acquire(blocking=False):
                break
            time.sleep(0.02)
        else:
            self.fail("the interrupted check never released the lock")
        P._CLUSTER_OP_LOCK.release()
        self.assertEqual(steps, ["after-wait"])
        h.cluster_task_status({})
        self.assertEqual(sent[-1][1]["id"], leave_id)   # the check's end did not overwrite the leave
        P._CLUSTER_CANCEL.clear()
        page = read(os.path.join(REPO, "panel/web/src/pages/ClusterPage.vue"))
        btn = page[:page.index("t('退出集群') }}</button>")]
        self.assertIn(':disabled="!!busyKey || leaveBlocked"', btn[btn.rindex("<button"):])
        cl = read(os.path.join(REPO, "panel/web/src/composables/useCluster.js"))
        self.assertIn("'cluster-leave', 'leave', { preempt: true }", cl)

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
        members = {p.get("name") for p in P._section_items(conf, "proxies")}
        for name in SYMBOL_NAMES:
            self.assertIn(name, members)
            self.assertIn("  - name: " + P.yaml_scalar(name, "name") + "\n", conf)
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
        lst, prox = P._conf_cluster_entries(conf)
        self.assertEqual([(p["name"], p["server"], p["encryption"], p["flow"]) for p in prox],
                         [("东京-1", "tokyo.example.com", enc, "xtls-rprx-vision")])
        self.assertEqual([(x["name"], x["decryption"], x["users"][0]["flow"]) for x in lst],
                         [("cg-cluster-abc123", dec, "xtls-rprx-vision")])
        self.assertNotRegex(conf, r"(?m)^\s*- \{")   # 1.41: multi-line YAML, no one-line JSON entries
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

    def test_custom_mode_cluster_entries_follow_cluster_json(self):
        """Since 1.37 the cluster works in custom-server mode: only the cluster entries of the user's
        file change, the user's own listeners / proxies / groups stay."""
        st, _, _ = self._state()
        P.save_cluster(st)
        user = ("mode: rule\n"
                "listeners:\n  - name: my-ss\n    type: shadowsocks\n    port: 30333\n    listen: 0.0.0.0\n"
                "    password: pw-12345678\n    cipher: aes-256-gcm\n"
                "  - name: cg-cluster-stale\n    type: vless\n    port: 39999\n"
                "proxies:\n  - name: mine\n    type: socks5\n    server: 1.1.1.1\n    port: 1080\n"
                "  - name: 东京-1\n    type: socks5\n    server: 9.9.9.9\n    port: 1\n"
                "proxy-groups:\n  - name: G\n    type: select\n    include-all: true\n"
                "rules:\n  - MATCH,G\n")
        out = P.custom_conf_with_cluster(user)
        lst = P.extract_top_level_yaml_section(out, "listeners")
        prox = P.extract_top_level_yaml_section(out, "proxies")
        self.assertEqual([l["name"] for l in lst], ["my-ss", P.CLUSTER_LISTENER_PREFIX + "abc123"])
        self.assertEqual([p["name"] for p in prox], ["mine", "东京-1"])
        self.assertEqual(prox[1]["server"], "tokyo.example.com")   # from cluster.json, not the pasted text
        self.assertEqual(lst[1].get("proxy"), "DIRECT")   # exit only in custom mode too (no loops)
        self.assertIn("include-all: true", out)
        self.assertIn("MATCH,G", out)
        # A member that left: its outbound is dropped when it is named in old_names.
        P.save_cluster({**st, "links": []})
        out2 = P.custom_conf_with_cluster(out, old_names={"东京-1"})
        self.assertEqual([p["name"] for p in P.extract_top_level_yaml_section(out2, "proxies")], ["mine"])
        self.assertFalse([l for l in P.extract_top_level_yaml_section(out2, "listeners")
                          if l["name"].startswith(P.CLUSTER_LISTENER_PREFIX)])
        self.assertEqual(P.custom_conf_with_cluster(out2), out2)   # nothing to change: idempotent

    def test_custom_mode_cluster_change_is_applied(self):
        st, _, _ = self._state()
        P.save_cluster({**st, "links": []})
        base = P.assemble_config()
        P.atomic_write(P.CUSTOM_CONF, base, 0o640)
        g = P.apply_cluster_live.__globals__
        try:
            with mock.patch.dict(g, {"_wait_cluster_ports": lambda want, timeout=8.0: True}):
                P._cluster_commit(lambda s: s["links"].extend(st["links"]))
            live = read(P.CUSTOM_CONF)
            self.assertEqual(read(P.CONF), live)
            self.assertIn(P.CLUSTER_LISTENER_PREFIX + "abc123", live)
            self.assertIn("tokyo.example.com", live)
            rc, out = P.validate_config()
            self.assertEqual(rc, 0, out)
            # A failed check (here: a group naming a member that is being renamed away) restores everything.
            self.assertIn("\nproxy-groups:\n", live)
            pinned = live.replace("\nproxy-groups:\n", "\nproxy-groups:\n  - name: pin\n    type: select\n    proxies:\n      - 东京-1\n", 1)
            P.atomic_write(P.CUSTOM_CONF, pinned, 0o640)
            P.atomic_write(P.CONF, pinned, 0o640)
            self.assertEqual(P.validate_config()[0], 0)   # valid while the member is called 东京-1
            before = read(P.CUSTOM_CONF)

            def rename(s):
                s["links"][0]["name"] = "大阪-2"
            with mock.patch.dict(g, {"_wait_cluster_ports": lambda want, timeout=8.0: True}):
                with self.assertRaises(RuntimeError):
                    P._cluster_commit(rename)
            self.assertEqual(read(P.CUSTOM_CONF), before)
            self.assertEqual(P.load_cluster()["links"][0]["name"], "东京-1")
        finally:
            if os.path.exists(P.CUSTOM_CONF):
                os.remove(P.CUSTOM_CONF)
            P.atomic_write(P.CONF, base, 0o640)

    def test_one_json_object_per_line_becomes_multi_line_yaml_without_a_reload(self):
        """1.41: panel inbounds, cluster fragments and config.yaml used one JSON object per line. The first
        start rewrites them as multi-line YAML; the entries are the same, so nothing reloads."""
        st, _, _ = self._state()
        P.save_cluster(st)

        def one_line(items):
            return "".join("  - " + json.dumps(x, ensure_ascii=False) + "\n" for x in items)

        P.atomic_write(P.FRAG_CLUSTER_LISTENERS, one_line([P.cluster_listener_from_link(l) for l in st["links"]]), 0o640)
        P.atomic_write(P.FRAG_CLUSTER_PROXIES, one_line([P.cluster_proxy_from_link(l) for l in st["links"]]), 0o640)
        P.atomic_write(P.FRAG_EXTRA, one_line([i["listener"] for i in P.load_inbounds()]), 0o640)
        P.atomic_write(P.CONF, P.assemble_config(), 0o640)
        old = read(P.CONF)
        self.assertRegex(old, r'(?m)^  - \{"name": ')

        def no_reload(*a, **k):
            raise AssertionError("the core was reloaded for a format change")

        with mock.patch.dict(P.apply_cluster_live.__globals__, {"apply_cluster_live": no_reload}):
            self.assertTrue(P.reformat_flow_entries())
            self.assertFalse(P.refresh_cluster_fragments())
            self.assertFalse(P.reformat_flow_entries())   # once
        new = read(P.CONF)
        self.assertNotRegex(new, r"(?m)^\s*- \{")
        for sec in ("listeners", "proxies"):
            self.assertEqual(P._section_items(new, sec), P._section_items(old, sec))
        for f in (P.FRAG_EXTRA, P.FRAG_CLUSTER_LISTENERS, P.FRAG_CLUSTER_PROXIES):
            self.assertNotRegex(read(f), r"(?m)^\s*- \{", f)
        self.assertEqual(new, P.assemble_config())   # what the panel writes from now on
        rc, out = P.validate_config()
        self.assertEqual(rc, 0, out)

    def test_yaml_values_keep_their_type(self):
        """Strings a YAML reader would take as numbers, booleans or reserved syntax are quoted."""
        item = {"name": "@x", "type": "socks5", "server": "1.2.3.4", "port": 1, "password": "1e5", "a": "0x1F",
                "b": ".inf", "c": "1:30", "d": "y", "e": "`t", "f": "01234567", "g": [], "h": {}, "i": [[1], {}],
                "j": "a: b", "k": "#c", "l": "plain-text_1.2/3", "m": None, "n": 1.5, "o": True}
        out = P.dump_yaml_proxies([item])
        self.assertEqual(P._section_items("x:\n" + out, "x"), [item])
        self.assertIn("    l: plain-text_1.2/3\n", out)
        for k in ("name", "password", "a", "b", "c", "d", "e", "f"):
            self.assertRegex(out, r'(?m)^ +(- )?%s: "' % k, k)
        # the Reality short-id stays a string even when it is all digits with a leading zero
        node = dict(P.read_nodes()[0], sid="01234567")
        self.assertIn('        - "01234567"\n', P.render_reality([node]))

    def test_cluster_members_are_exits_not_relays(self):
        """Traffic from another panel leaves directly, so A -> B -> A can never happen, whatever is
        selected in Zashboard. Existing links get this on the first start after an update."""
        st, _, _ = self._state()
        self.assertEqual(P.cluster_listener_from_link(st["links"][0])["proxy"], "DIRECT")
        P.save_cluster(st)
        # what 1.37 left on disk: one JSON object per line and no proxy: DIRECT
        old_shape = "".join("  - " + json.dumps({k: v for k, v in P.cluster_listener_from_link(l).items() if k != "proxy"},
                                                 ensure_ascii=False) + "\n" for l in st["links"])
        P.atomic_write(P.FRAG_CLUSTER_LISTENERS, old_shape, 0o640)
        P.atomic_write(P.CONF, P.assemble_config(), 0o640)
        self.assertEqual([x.get("proxy") for x in P._conf_cluster_entries(read(P.CONF))[0]], [None])
        g = P.apply_cluster_live.__globals__
        with mock.patch.dict(g, {"_wait_cluster_ports": lambda want, timeout=8.0: True}):
            self.assertTrue(P.refresh_cluster_fragments())
            self.assertFalse(P.refresh_cluster_fragments())   # done once
        self.assertEqual(read(P.FRAG_CLUSTER_LISTENERS), P.render_cluster_listeners(st))
        conf = read(P.CONF)
        self.assertEqual([x.get("proxy") for x in P._conf_cluster_entries(conf)[0]], ["DIRECT"])
        rc, out = P.validate_config()
        self.assertEqual(rc, 0, out)
        P.save_cluster({**st, "links": []})
        self.assertFalse(P.refresh_cluster_fragments())   # no links: nothing to do

    def test_custom_mode_old_cluster_inbound_gets_direct(self):
        """A 1.37 custom config (cluster inbound without proxy: DIRECT) is fixed on the first start,
        even if the user deleted the field by hand; then nothing more to do."""
        st, _, _ = self._state()
        P.save_cluster(st)
        base = P.custom_conf_with_cluster(P.assemble_config())
        self.assertEqual(base.count("    proxy: DIRECT\n"), 1)   # only the cluster inbound has it
        old = base.replace("    proxy: DIRECT\n", "")
        P.atomic_write(P.CUSTOM_CONF, old, 0o640)
        P.atomic_write(P.CONF, old, 0o640)
        g = P.apply_cluster_live.__globals__
        try:
            with mock.patch.dict(g, {"_wait_cluster_ports": lambda want, timeout=8.0: True}):
                self.assertTrue(P.refresh_cluster_fragments())
                self.assertFalse(P.refresh_cluster_fragments())
            lst = P.extract_top_level_yaml_section(read(P.CUSTOM_CONF), "listeners")
            cl = [x for x in lst if x["name"].startswith(P.CLUSTER_LISTENER_PREFIX)]
            self.assertEqual([x.get("proxy") for x in cl], ["DIRECT"])
            self.assertEqual(read(P.CONF), read(P.CUSTOM_CONF))
        finally:
            os.remove(P.CUSTOM_CONF)
            P.atomic_write(P.CONF, P.assemble_config(), 0o640)

    def test_cluster_operation_runs_in_background_with_steps(self):
        """1.39: the page starts a cluster operation with async=1 and polls its current step, so a long
        add (both cores reload) shows progress instead of a frozen button."""
        h = object.__new__(P.Panel)
        h.headers = {"X-Requested-With": "fetch"}
        sent = []
        h.send = lambda code, body, ctype="", headers=None, cache_key=None: sent.append((code, json.loads(body)))
        h.build_client_state = lambda s, *a: {"x": 1}
        h.tr = lambda m: m
        got = {}
        h.respond_mutation = lambda s, msg, ok=True, detail="": got.update(ok=ok, msg=msg)
        go = threading.Event()

        def job():
            P.cluster_stage("正在检查「东京-1」")
            go.wait(5)
            return "集群成员都在线，互联完整", True

        h._cluster_job({}, job, {"async": "1"}, "sync")
        code, started = sent[-1]
        self.assertEqual((code, started["ok"], started["running"]), (200, True, True))
        for _ in range(50):
            h.cluster_task_status({})
            if sent[-1][1].get("stage"):
                break
            time.sleep(0.02)
        run = sent[-1][1]
        self.assertEqual((run["running"], run["kind"], run["stage"]), (True, "sync", "正在检查「东京-1」"))
        h._cluster_job({}, job, {"async": "1"}, "add")   # one operation at a time
        self.assertEqual(got, {"ok": False, "msg": "另一个集群操作正在进行，请稍候再试"})
        go.set()
        for _ in range(100):
            h.cluster_task_status({})
            if not sent[-1][1]["running"]:
                break
            time.sleep(0.02)
        done = sent[-1][1]
        self.assertEqual((done["done"], done["ok"], done["msg"], done["state"]), (True, True, "集群成员都在线，互联完整", {"x": 1}))
        self.assertEqual(done["id"], started["id"])   # the page only reports the task it started
        self.assertTrue(P._CLUSTER_OP_LOCK.acquire(blocking=False))   # released after the job
        P._CLUSTER_OP_LOCK.release()
        # Outside a page task a step report changes nothing (CLI `clashgate uninstall` leaves too).
        P.cluster_stage("正在通知「x」")
        self.assertEqual(P._CLUSTER_TASK["stage"], "")
        # Without async=1 (other panels, older pages, tests) it still answers in the same request.
        h._cluster_job({}, lambda: ("ok-now", True), {}, "sync")
        self.assertEqual(got, {"ok": True, "msg": "ok-now"})

    def test_cluster_page_overlay_while_an_operation_runs(self):
        src = os.path.join(REPO, "panel/web/src")
        app = read(os.path.join(src, "App.vue"))
        ov = app[app.index('id="cluster-task-overlay"'):]
        ov = ov[:ov.index("</Transition>")]
        for needle in ('v-if="clusterTask.show"', "v-cg-dialog", 'role="alertdialog"', 'aria-busy="true"',
                       "clusterTask.stage", "clusterTask.elapsed", "<CgSpinner"):
            self.assertIn(needle, ov)
        self.assertNotIn("✕", ov)   # nothing to close: it ends with the operation
        self.assertIn("t('正在添加到集群')", ov)
        cl = read(os.path.join(src, "composables/useCluster.js"))
        for url, kind in (("/cluster/add", "add"), ("/cluster/sync", "sync"), ("/cluster/remove", "remove"), ("/cluster/leave", "leave")):
            self.assertRegex(cl, r"runClusterTask\(\s*'" + re.escape(url) + r"'[^)]*'" + kind + "'", url)
        self.assertNotIn("postAction('/cluster/", cl)
        # 1.41: only the first add blocks the page; 检查 / 重试 / 移除 / 退出 run behind their own button
        self.assertEqual(cl.count("{ overlay: true }"), 1)
        self.assertRegex(cl, r"runClusterTask\(\s*'/cluster/add'[^)]*\{ overlay: true \}")
        page = read(os.path.join(src, "pages/ClusterPage.vue"))
        for key in ("'cluster-sync'", "'cluster-leave'", "`cl-rt-${m.id}`", "`cl-rm-${m.id}`"):
            self.assertRegex(page, r'<CgSpinner v-if="clusterBusy === ' + re.escape(key) + r'" :size="13"', key)
        self.assertIn("resumeClusterTaskIfRunning()", read(os.path.join(src, "composables/usePanel.js")))

    def test_core_build_matches_the_cpu(self):
        """1.39: the plain amd64 core needs an x86-64-v3 CPU ("can only be run on AMD64 processors with v3
        microarchitecture support"); install and panel update pick a build by CPU level and fall back."""
        U = sys.modules["cg_update"]
        tag = "v1.19.34"
        self.assertEqual(U.mihomo_asset_candidates("amd64", tag, level=1),
                         ["mihomo-linux-amd64-v1-v1.19.34.gz", "mihomo-linux-amd64-compatible-v1.19.34.gz"])
        self.assertEqual(U.mihomo_asset_candidates("amd64", tag, level=2)[0], "mihomo-linux-amd64-v2-v1.19.34.gz")
        self.assertEqual(U.mihomo_asset_candidates("amd64", tag, level=3)[:2],
                         ["mihomo-linux-amd64-v3-v1.19.34.gz", "mihomo-linux-amd64-v1.19.34.gz"])
        for lvl in (1, 2, 3):
            self.assertEqual(U.mihomo_asset_candidates("amd64", tag, level=lvl)[-1], "mihomo-linux-amd64-compatible-v1.19.34.gz")
        self.assertEqual(U.mihomo_asset_candidates("arm64", tag), ["mihomo-linux-arm64-v1.19.34.gz"])
        core = read(os.path.join(REPO, "scripts/lib/core.sh"))
        body = core[core.index("core_download() {"):]
        body = body[:body.index("\n}\n")]
        self.assertIn("core_asset_candidates", body)
        self.assertNotIn('mihomo-linux-${a}-${tag}.gz" \'.assemblies[]', body)
        # the shell list is the same as the Python one for each level
        for lvl in (1, 2, 3):
            out = subprocess.run(["bash", "-c", f'source scripts/lib/core.sh; amd64_level() {{ echo {lvl}; }}; core_asset_candidates amd64 {tag}'],
                                 cwd=REPO, capture_output=True, text=True)
            self.assertEqual(out.stdout.split(), U.mihomo_asset_candidates("amd64", tag, level=lvl), out.stderr)

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

    def test_token_update_without_new_certificate(self):
        """1.47: DNS mode, new token: checked against Cloudflare and saved; certctl is not run (no new
        certificate). /action/cert-mode with the same mode and a new token takes the same path."""
        env_before = read(P.ENV_FILE)
        h = object.__new__(P.Panel)
        h.respond_mutation = lambda s, msg, ok=True, detail="": (ok, msg)
        g = P.Panel.do_cert_token.__globals__
        checked = []

        def no_certctl(cmd, **kw):
            raise AssertionError("certctl must not run for a token update: %r" % (cmd,))

        try:
            P.write_env_var("CERT_MODE", "dns")
            P.write_env_var("CF_TOKEN", "old-token")
            with mock.patch.dict(g, {"run": no_certctl,
                                     "cf_token_check": lambda tok, dom: checked.append(tok) or ""}):
                ok, msg = h.do_cert_token({}, {"cf_token": "new-token"})
                self.assertTrue(ok, msg)
                self.assertIn("没有重新申请证书", msg)
                self.assertEqual(P.read_env().get("CF_TOKEN"), "new-token")
                ok, msg = h.do_cert_mode({}, {"cert_mode": "dns", "cf_token": "newer-token"})
                self.assertTrue(ok, msg)
                self.assertEqual(P.read_env().get("CF_TOKEN"), "newer-token")
                self.assertEqual(checked, ["new-token", "newer-token"])
                self.assertFalse(h.do_cert_token({}, {"cf_token": "newer-token"})[0])   # unchanged
                self.assertFalse(h.do_cert_token({}, {"cf_token": "a b"})[0])
            with mock.patch.dict(g, {"run": no_certctl, "cf_token_check": lambda tok, dom: P.CF_TOKEN_BAD}):
                ok, msg = h.do_cert_token({}, {"cf_token": "bad-token"})
                self.assertFalse(ok)
                self.assertIn("Token 无效", msg)
                self.assertEqual(P.read_env().get("CF_TOKEN"), "newer-token")   # a refused token is not saved
            P.write_env_var("CERT_MODE", "port")
            self.assertFalse(h.do_cert_token({}, {"cf_token": "x-token"})[0])   # not DNS mode: switch instead
        finally:
            with open(P.ENV_FILE, "w") as f:
                f.write(env_before)
        src = os.path.join(REPO, "panel/web/src")
        certs = read(os.path.join(src, "composables/useCerts.js"))
        self.assertIn("postAction('/action/cert-token'", certs)
        self.assertIn("certModeValue.value === 'dns' &&", certs)
        self.assertIn("t('更新 Cloudflare API Token')", read(os.path.join(src, "pages/CertsPage.vue")))

    def test_cf_token_check(self):
        """1.47: the same zone lookup as certctl.sh's cf_zone_check (name, then parents)."""
        import io
        import urllib.error
        g = P.cf_token_check.__globals__
        asked = []

        def answer(zones, code=200):
            def fake(req, timeout=0):
                name = urllib.parse.parse_qs(urllib.parse.urlparse(req.full_url).query)["name"][0]
                asked.append(name)
                if code != 200:
                    raise urllib.error.HTTPError(req.full_url, code, "no", {}, io.BytesIO(b"{}"))
                body = {"result": [{"name": name}] if name in zones else []}
                return io.BytesIO(json.dumps(body).encode())
            return fake

        env_keys = {k: os.environ.pop(k) for k in ("CS_DNS_HOOK", "CS_ACME_SERVER") if k in os.environ}
        try:
            with mock.patch.object(g["urllib"].request, "urlopen", answer({"example.com"})):
                self.assertEqual(P.cf_token_check("t", "*.a.b.example.com"), "")
            self.assertEqual(asked, ["a.b.example.com", "b.example.com", "example.com"])
            with mock.patch.object(g["urllib"].request, "urlopen", answer(set())):
                self.assertEqual(P.cf_token_check("t", "a.example.com"), P.CF_ZONE_MISSING)
            with mock.patch.object(g["urllib"].request, "urlopen", answer(set(), 403)):
                self.assertEqual(P.cf_token_check("t", "a.example.com"), P.CF_TOKEN_BAD)
            with mock.patch.object(g["urllib"].request, "urlopen", answer(set(), 503)):
                self.assertEqual(P.cf_token_check("t", "a.example.com"), "")   # Cloudflare down: do not block
        finally:
            os.environ.update(env_keys)

    def test_last_failure_is_shown(self):
        """1.47: certctl.sh keeps why the last request failed (timer too) in CERT_FAILED until a request
        succeeds; the HTTPS page shows the short reason, never for manual certificates."""
        env_before = read(P.ENV_FILE)
        try:
            P.write_env_var("CERT_MODE", "port")
            with open(P.CERT_FAILED, "w") as f:
                f.write("1764200000\nport\n2\ncertctl: 80 端口被占用，无法申请证书（端口模式需要临时使用 80 端口）：\n")
            st = P.cert_failure_state()
            self.assertEqual((st["at"], st["fails"]), (1764200000, 2))
            self.assertTrue(st["reason"].startswith("80 端口被占用"), st)
            self.assertNotIn("重新生成证书失败", st["reason"])
            with open(P.CERT_FAILED, "w") as f:
                f.write("1764200000\ndns\n1\nError add txt for domain:_acme-challenge.x\ninvalid domain\n")
            self.assertIn("找不到该域名", P.cert_failure_state()["reason"])
            import i18n_en
            for lang in ("en", "ru", "fa"):
                self.assertNotRegex(i18n_en.tr(P.cert_failure_state()["reason"], lang), r"[\u4e00-\u9fff]", lang)
            P.write_env_var("CERT_MODE", "manual")
            self.assertEqual(P.cert_failure_state(), {})
            os.remove(P.CERT_FAILED)
            P.write_env_var("CERT_MODE", "port")
            self.assertEqual(P.cert_failure_state(), {})
        finally:
            if os.path.exists(P.CERT_FAILED):
                os.remove(P.CERT_FAILED)
            with open(P.ENV_FILE, "w") as f:
                f.write(env_before)
        sh = read(os.path.join(REPO, "scripts/certctl.sh"))
        self.assertIn("trap 'record_result $?' EXIT", sh)
        self.assertIn('rm -f "$FAILED_FILE"', sh)
        self.assertIn('line=${line//"$CF_TOKEN"/***}', sh)   # the token never goes into the file
        # daily timer with back-off: after n failures in a row wait min(n, 3) days; the panel is never held back
        self.assertIn("OnCalendar=daily", read(os.path.join(REPO, "scripts/init/clashgate-cert.timer")))
        self.assertIn("ExecStart=/etc/clashgate/scripts/certctl.sh auto", read(os.path.join(REPO, "scripts/init/clashgate-cert.service")))
        self.assertIn("wait_days=$((fails < 3 ? fails : 3))", sh)
        self.assertIn("if ((AUTO)) && [[ -f $FAILED_FILE ]]; then", sh)
        self.assertLess(sh.index("if ((AUTO)) && [[ -f $FAILED_FILE ]]; then"), sh.index("trap 'record_result $?' EXIT"))
        self.assertIn("builtin echo $((fails + 1))", sh)
        self.assertLess(sh.index("trap 'record_result $?' EXIT"), sh.index("ACME=$ACME_HOME/acme.sh"))
        self.assertGreater(sh.index("trap 'record_result $?' EXIT"), sh.index('if [[ $CERT_MODE == manual ]]; then'))
        page = read(os.path.join(REPO, "panel/web/src/pages/CertsPage.vue"))
        self.assertIn('v-if="state.cert_failure && certModeValue !== \'manual\'"', page)

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

    def test_drafts_made_live_outside_panel_leave_pending(self):
        # Before 1.35 `clashgate update` assembled config.yaml from the drafts: the core ran them
        # while the panel still listed them as pending and served the pre-draft subscription.
        node, _ = write_default_state()
        P.clear_pending_reload()
        P.save_nodes([])
        P.record_pending_reload(op="delete", kind="vless-reality", name=node["name"], port=node["port"],
                                detail=f"- 删除节点「{node['name']}」")
        P.record_pending_reload(op="reset-sub", kind="sub", name="sub", sub_token="N" * 24)
        live = read(P.CONF)
        try:
            self.assertFalse(P.reconcile_pending_with_live())   # not live yet: keep the drafts
            self.assertEqual(len(P.load_pending_reload()["items"]), 2)
            P.atomic_write(P.CONF, live + "# hand edit\n", 0o640)
            self.assertFalse(P.reconcile_pending_with_live())   # changed, but not to the drafts
            self.assertEqual(P.live_nodes_and_inbounds()[0][0]["name"], node["name"])
            P.atomic_write(P.CONF, P.assemble_config(), 0o640)  # what update_self used to do
            self.assertTrue(P.reconcile_pending_with_live())
            st = P.load_pending_reload()
            self.assertEqual([it["op"] for it in st["items"]], ["reset-sub"])   # token is not in config.yaml
            self.assertEqual(st["sub_token"], "N" * 24)
            self.assertEqual(P.live_nodes_and_inbounds()[0], [])
            self.assertFalse(P.reconcile_pending_with_live())
        finally:
            P.clear_pending_reload()

    def test_update_keeps_live_config_while_drafts_pending(self):
        sh = read(os.path.join(REPO, "scripts/cmd/clashgate.sh"))
        body = sh[sh.index("update_self() {"):sh.index("do_status() {")]
        guard = body.index("if ! has_panel_drafts; then")
        self.assertLess(guard, body.index("assemble_config"))
        self.assertLess(guard, body.index("render_client"))
        fn = sh[sh.index("has_panel_drafts() {"):sh.index("update_self() {")]
        start = fn.index("\n", fn.index("<<'PY'")) + 1
        script = fn[start:fn.index("\nPY\n")]
        cases = (
            ({"items": [{"op": "delete", "name": "x"}], "sub_token": "", "mihomo_secret": ""}, 0),
            ({"items": [], "sub_token": "T" * 24, "mihomo_secret": ""}, 0),
            ({"items": [], "sub_token": "", "mihomo_secret": ""}, 1),
        )
        for data, want in cases:
            p = os.path.join(tempfile.mkdtemp(), "pending_reload.json")
            with open(p, "w") as f:
                json.dump(data, f)
            r = subprocess.run([sys.executable, "-", p], input=script, text=True, capture_output=True)
            self.assertEqual(r.returncode, want, data)

    def test_status_counts_only_core_sockets(self):
        # A port held by another program (or another core) must not show a node as running.
        g = P.mihomo_status.__globals__
        with_users = ('tcp LISTEN 0 4096 0.0.0.0:30111 0.0.0.0:* users:(("mihomo",pid=4242,fd=7))\n'
                      'udp UNCONN 0 0 0.0.0.0:30112 0.0.0.0:* users:(("mihomo",pid=4242,fd=8))\n'
                      'tcp LISTEN 0 128 0.0.0.0:30113 0.0.0.0:* users:(("nginx",pid=99,fd=6))\n')
        no_users = "tcp LISTEN 0 4096 0.0.0.0:30111 0.0.0.0:*\ntcp LISTEN 0 128 0.0.0.0:30113 0.0.0.0:*\n"

        def fake(active, ss):
            def run(cmd, **kw):
                if cmd[:2] == [g["SYSTEMCTL"], "is-active"]:
                    return (0 if active == "active" else 3), active + "\n"
                if cmd[:2] == [g["SYSTEMCTL"], "show"]:
                    return 0, "MainPID=%s\n" % ("4242" if active == "active" else "0")
                if cmd and cmd[0] == "ss":
                    return 0, ss
                return 0, ""
            return run

        with mock.patch.dict(g, {"run": fake("active", with_users)}):
            self.assertEqual(P.mihomo_status()["listening"], [30111, 30112])
        with mock.patch.dict(g, {"run": fake("active", no_users)}):   # no process info: count all
            self.assertEqual(P.mihomo_status()["listening"], [30111, 30113])
        with mock.patch.dict(g, {"run": fake("inactive", with_users)}):
            self.assertEqual(P.mihomo_status()["listening"], [])

    def test_manual_port_held_by_other_program(self):
        write_default_state()
        env = P.read_env()
        for stype in (socket.SOCK_STREAM, socket.SOCK_DGRAM):
            holder = socket.socket(socket.AF_INET, stype)
            port = None
            for p in range(31200, 31400):
                if p in P.used_ports(env):
                    continue
                try:
                    holder.bind(("0.0.0.0", p))
                    port = p
                    break
                except OSError:
                    continue
            self.assertIsNotNone(port, "could not bind a test port")
            try:
                with self.assertRaises(ValueError) as cm:
                    P.build_inbound("shadowsocks", {"port": str(port), "name": "ss-busy"}, env)
                self.assertIn(str(port), str(cm.exception))
            finally:
                holder.close()

    def test_api_get_without_session_is_401(self):
        h = object.__new__(P.Panel)
        got = {}
        h.send = lambda code, body, ctype="", headers=None, cache_key=None: got.update(code=code, ctype=ctype)
        h.sessions = {}
        for path, ajax, want in (("/api/state", False, 401), ("/api/upgrade-status", False, 401),
                                 ("/", False, 303), ("/routing", True, 401)):
            got.clear()
            h.path = path
            h.headers = {"Accept": "application/json"} if ajax else {}
            h.do_GET()
            self.assertEqual(got.get("code"), want, path)
            if want == 401:
                self.assertTrue(got["ctype"].startswith("application/json"), path)

    def test_cli_reset_sub_drops_panel_link_draft(self):
        # Otherwise the panel's older pending link replaces the one `clashgate reset-sub` printed.
        sh = read(os.path.join(REPO, "scripts/cmd/clashgate.sh"))
        body = sh[sh.index("do_reset_sub() {"):sh.index("do_reset_password() {")]
        self.assertLess(body.index("write_panel_cfg"), body.index("drop_panel_sub_draft"))
        fn = sh[sh.index("drop_panel_sub_draft() {"):sh.index("do_reset_sub() {")]
        start = fn.index("\n", fn.index("<<'PY'")) + 1
        script = fn[start:fn.index("\nPY\n")]
        d = tempfile.mkdtemp()
        p, b = os.path.join(d, "pending_reload.json"), os.path.join(d, "pending_baseline.json")

        def run_case(data):
            with open(p, "w") as f:
                json.dump(data, f)
            with open(b, "w") as f:
                f.write("{}")
            subprocess.run([sys.executable, "-", p, b], input=script, text=True, check=True)

        run_case({"items": [{"op": "reset-sub", "name": "sub"}], "sub_token": "T" * 24, "mihomo_secret": ""})
        self.assertFalse(os.path.exists(p))
        self.assertFalse(os.path.exists(b))
        run_case({"items": [{"op": "reset-sub"}, {"op": "delete", "name": "x"}], "sub_token": "T" * 24, "mihomo_secret": ""})
        st = json.loads(read(p))
        self.assertEqual(([it["op"] for it in st["items"]], st["sub_token"]), (["delete"], ""))
        self.assertTrue(os.path.exists(b))
        run_case({"items": [{"op": "delete", "name": "x"}], "sub_token": "", "mihomo_secret": ""})
        self.assertEqual(json.loads(read(p))["items"], [{"op": "delete", "name": "x"}])

    def test_menu_confirms_resets_and_reopens_after_update(self):
        sh = read(os.path.join(REPO, "scripts/cmd/clashgate.sh"))
        menu = sh[sh.index("do_menu() {"):sh.index("cluster_link_count()")]
        run_at = menu.index('"do_${item//-/_}"')
        for item in ("reset-sub", "reset-password"):
            self.assertLess(menu.index(f"[[ $item == {item} ]] && [[ $(ask"), run_at)
        self.assertIn("[[ $item == update || $item == cert ]] && ((rc == 0)); then exec bash", menu)

    def test_firewall_is_only_opened_never_closed(self):
        g = P.sync_ufw.__globals__
        calls = []

        def fake(cmd, **kw):
            calls.append(list(cmd))
            if cmd[:2] == [g["UFW_BIN"], "status"]:
                return 0, "Status: active\n"
            return 0, ""

        with mock.patch.dict(g, {"run": fake}):
            P.sync_ufw({"30001/tcp", "30002/tcp"}, {"30002/tcp", "30003/tcp", "30003/udp"})
        changes = [c[1:] for c in calls if c[0] == g["UFW_BIN"] and c[1] != "status"]
        self.assertEqual(changes, [["allow", "30003/tcp"], ["allow", "30003/udp"]])
        calls.clear()
        with mock.patch.dict(g, {"run": fake}):
            P.sync_ufw({"30001/tcp"}, set())   # a node was deleted: its port stays open
        self.assertEqual(calls, [])

    def test_template_refresh_after_drafts_are_gone(self):
        write_default_state()
        P.clear_pending_reload()
        good = P.assemble_config()
        P.atomic_write(P.CONF, good + "# assembled by an older template\n", 0o640)
        P.record_pending_reload(op="add", kind="shadowsocks", name="x", port=30999, detail="+ x")
        open(P.TEMPLATE_REFRESH_FLAG, "w").close()
        try:
            self.assertFalse(P.refresh_template_if_flagged())   # drafts pending: wait for them
            self.assertTrue(os.path.exists(P.TEMPLATE_REFRESH_FLAG))
            P.clear_pending_reload()
            self.assertTrue(P.refresh_template_if_flagged())
            self.assertFalse(os.path.exists(P.TEMPLATE_REFRESH_FLAG))
            self.assertEqual(read(P.CONF), good)
            self.assertFalse(P.refresh_template_if_flagged())
        finally:
            P.clear_pending_reload()
            if os.path.exists(P.TEMPLATE_REFRESH_FLAG):
                os.remove(P.TEMPLATE_REFRESH_FLAG)
        sh = read(os.path.join(REPO, "scripts/cmd/clashgate.sh"))
        body = sh[sh.index("update_self() {"):sh.index("do_status() {")]
        self.assertIn(': > "$CS_ROOT/template_refresh"', body[body.index("if ! has_panel_drafts; then"):])
        http = read(os.path.join(REPO, "panel/cg_http.py"))
        disc = http[http.index("def do_discard_pending"):http.index("def do_settings")]
        self.assertLess(disc.index("discard_pending_reload()"), disc.index("refresh_template_if_flagged()"))

    def test_ipv6_only_server_config(self):
        env_before = read(P.ENV_FILE)
        write_default_state(extra_kinds=("shadowsocks",))
        try:
            v4 = P.assemble_config()
            self.assertNotIn('listen: "::"', v4)
            with open(P.ENV_FILE, "w") as f:
                f.write(env_before.replace('SERVER_IP="1.2.3.4"', 'SERVER_IP="2001:db8::10"'))
            v6 = P.assemble_config()
            self.assertIn('listen: "::"', v6)
            self.assertIn('"listen": "::"', v6)
            self.assertIn('external-controller-tls: "[::]:', v6)
            self.assertNotIn("listen: 0.0.0.0", v6)
            self.assertIn(P.DNS_IPV6_ONLY, v6)
            self.assertNotIn("default-nameserver", v6)
            P.atomic_write(P.CONF, v6, 0o640)
            rc, out = P.validate_config()
            self.assertEqual(rc, 0, out)
        finally:
            with open(P.ENV_FILE, "w") as f:
                f.write(env_before)
        # core.sh prints the same DNS block for the installer / `clashgate update`.
        core = read(os.path.join(REPO, "scripts/lib/core.sh"))
        awk = core[core.index('v6 == 1 && /^dns:$/ {'):core.index("skipdns = 1")]
        printed = [json.loads(m) for m in re.findall(r'^\s*print ("(?:[^"\\]|\\.)*")$', awk, re.M)]
        self.assertEqual("\n".join(printed) + "\n", P.DNS_IPV6_ONLY)

    def test_cert_job_runs_in_background(self):
        h = object.__new__(P.Panel)
        h.headers = {"X-Requested-With": "fetch"}
        sent = []
        h.send = lambda code, body, ctype="", headers=None, cache_key=None: sent.append((code, json.loads(body)))
        h.build_client_state = lambda s, *a: {"x": 1}
        g = P.Panel.do_cert_action.__globals__

        def slow_run(cmd, **kw):
            time.sleep(0.3)
            return 0, "certctl: ok\n"

        with mock.patch.dict(g, {"run": slow_run}):
            h.do_cert_action({}, {"async": "1"})
            self.assertEqual(sent[-1], (200, {"ok": True, "running": True}))
            got = {}
            h.respond_mutation = lambda s, msg, ok=True, detail="": got.update(ok=ok, msg=msg)
            h.do_cert_action({}, {"async": "1"})   # a second job while the first runs
            self.assertEqual(got, {"ok": False, "msg": "另一个证书任务正在运行，请稍后再试"})
            for _ in range(50):
                h.cert_task_status({})
                if not sent[-1][1]["running"]:
                    break
                time.sleep(0.05)
        done = sent[-1][1]
        self.assertEqual((done["running"], done["done"], done["ok"]), (False, True, True))
        self.assertEqual(done["msg"], "证书检查 / 续期完成。")
        self.assertEqual(done["state"], {"x": 1})

    def test_global_login_cap_spares_trusted_sources(self):
        h = object.__new__(P.Panel)
        h.client_address = ("9.9.9.9", 1)
        h.headers = {}
        h.cfg = {"username": "admin", "password_hash": P.hash_password("correct-horse")}
        h.cfg_path = None
        sent = []
        h.send = lambda code, body, ctype="", headers=None, cache_key=None: sent.append(code)
        h.login_page = lambda err="": err
        now = time.time()
        fails, trusted = dict(P.Panel.fails), dict(P.Panel.trusted)
        try:
            P.Panel.fails.clear()
            P.Panel.fails.update({f"10.0.{i // 250}.{i % 250}": [now] for i in range(P.LOGIN_MAX_FAILS_TOTAL)})
            P.Panel.trusted.clear()
            h.do_login({"username": "admin", "password": "correct-horse"})
            self.assertEqual(sent[-1], 429)   # unknown source while many addresses are guessing
            P.Panel.trusted["9.9.9.9"] = now - 60
            h.do_login({"username": "admin", "password": "correct-horse"})
            self.assertEqual(sent[-1], 303)   # signed in here before: still allowed
        finally:
            P.Panel.fails.clear()
            P.Panel.fails.update(fails)
            P.Panel.trusted.clear()
            P.Panel.trusted.update(trusted)

    def test_status_caches_version_and_cert(self):
        g = P.mihomo_status.__globals__
        binf = os.path.join(tempfile.mkdtemp(), "mihomo")
        with open(binf, "w") as f:
            f.write("x")
        calls = []

        def fake(cmd, **kw):
            if cmd[:1] == [binf]:
                calls.append("v")
                return 0, "Mihomo Meta v1.19.34\n"
            if cmd and cmd[0] == "openssl":
                calls.append("cert")
                return 0, "notAfter=Jan  1 00:00:00 2030 GMT\nissuer=CN = R11\n"
            return 0, ""

        with mock.patch.dict(g, {"run": fake, "resolve_mihomo_bin": lambda: binf}):
            for _ in range(3):
                st = P.mihomo_status()
            self.assertEqual(st["version"], "Mihomo Meta v1.19.34")
            self.assertEqual(calls.count("v"), 1)
            self.assertLessEqual(calls.count("cert"), 1)
            with open(binf, "w") as f:   # core updated: read the version again
                f.write("xy")
            P.mihomo_status()
            self.assertEqual(calls.count("v"), 2)

    def test_status_uptime_and_live_node_counts(self):
        if not os.path.isfile("/proc/uptime"):
            self.skipTest("no /proc/uptime")
        g = P.mihomo_status.__globals__
        boot = float(read("/proc/uptime").split()[0])
        mono = int((boot - 3700) * 1e6)

        def fake(cmd, **kw):
            if cmd[:2] == [g["SYSTEMCTL"], "is-active"]:
                return 0, "active\n"
            if cmd[:2] == [g["SYSTEMCTL"], "show"]:
                return 0, f"MainPID=0\nActiveEnterTimestampMonotonic={mono}\n"
            return 0, ""

        with mock.patch.dict(g, {"run": fake}):
            up = P.mihomo_status()["uptime"]
        self.assertTrue(3690 <= up <= 3800, up)
        node, inbs = write_default_state(extra_kinds=("shadowsocks",))
        P.clear_pending_reload()
        counts = P.Panel._live_node_counts({node["port"]})
        self.assertEqual(counts, {"live_total": 2, "live_up": 1})
        # A node added as a draft is not live yet: it does not count as offline.
        P._ensure_pending_baseline()
        env = P.read_env()
        P.save_inbounds(P.load_inbounds() + [P.build_inbound("shadowsocks", {"port": "30777", "name": "draft-ss"}, env)])
        P.record_pending_reload(op="add", kind="shadowsocks", name="draft-ss", port=30777, detail="+")
        try:
            self.assertEqual(P.Panel._live_node_counts({node["port"]}), {"live_total": 2, "live_up": 1})
        finally:
            P.discard_pending_reload()

    def test_page_links_cacheable_versioned_assets(self):
        g = P.Panel.send.__globals__
        page = P.render_spa_html("ClashGate", {"page": "dashboard"})
        ver = g["asset_version"]("assets/app.js")
        self.assertRegex(ver, r"^[0-9a-f]{12}$")
        self.assertIn(f'<script src="/assets/app.js?v={ver}"></script>', page)
        self.assertIn('<link rel=stylesheet href="/assets/style.css?v=', page)
        self.assertLess(len(page), 20000)   # the bundles are no longer inlined
        h = object.__new__(P.Panel)
        sent = []
        h.send = lambda code, body, ctype="", headers=None, cache_key=None: sent.append((code, headers or {}, body))
        for path, inm, want_code, want_cc in (
                (f"/assets/app.js?v={ver}", "", 200, "public, max-age=31536000, immutable"),
                ("/assets/app.js?v=old", "", 200, "no-cache"),
                ("/assets/app.js", "", 200, "no-cache"),
                ("/assets/app.js", f'W/"{ver}"', 304, "no-cache"),
                ("/assets/ibm-plex-sans-latin-400-normal.woff2", "", 200, "public, max-age=604800")):
            h.path = path
            h.headers = {"If-None-Match": inm} if inm else {}
            h.do_GET()
            code, hdrs, body = sent[-1]
            self.assertEqual((code, hdrs.get("Cache-Control")), (want_code, want_cc), path)
            self.assertTrue(hdrs.get("ETag", "").startswith('W/"'), path)
            if code == 304:
                self.assertEqual(body, b"")

    def test_deleted_nodes_stay_listed_until_applied(self):
        node, inbs = write_default_state(extra_kinds=("shadowsocks",))
        P.clear_pending_reload()
        P._ensure_pending_baseline()
        ss = inbs[0]
        P.save_inbounds([])
        P.record_pending_reload(op="delete", kind="shadowsocks", name=ss["name"], port=ss["port"], detail="-")
        try:
            items = P.Panel._pending_delete_items({ss["port"]}, P.load_pending_reload()["items"], P.read_nodes(), [])
            self.assertEqual([(i["name"], i["pending_delete"], i["listening"], i["delete_url"]) for i in items],
                             [(ss["name"], True, True, "")])
            # Re-added under the same name in the draft: listed once, as the draft node.
            self.assertEqual(P.Panel._pending_delete_items(set(), P.load_pending_reload()["items"], P.read_nodes(), [ss]), [])
        finally:
            P.discard_pending_reload()

    def test_ui_1_37_details(self):
        src = os.path.join(REPO, "panel/web/src")
        app = read(os.path.join(src, "App.vue"))
        self.assertEqual(app.count("v-cg-dialog"), 4)
        self.assertEqual(app.count('role="dialog"'), 4)
        self.assertEqual(app.count('aria-modal="true"'), 4)
        self.assertNotRegex(app, r"<button(?![^>]*aria-label)[^>]*>\s*✕")
        home = read(os.path.join(src, "pages/InboundsPage.vue"))
        self.assertIn('id="zashboard-card"', home)
        self.assertNotIn('id="zashboard-card"', read(os.path.join(src, "pages/OutboundsPage.vue")))
        self.assertIn("item.pending_delete", home)
        self.assertIn("moveRoutingGroup(idx, -1)", read(os.path.join(src, "pages/RoutingPage.vue")))
        settings = read(os.path.join(src, "pages/SettingsPage.vue"))
        order = [settings.index(k) for k in ('id="settings-password-card"', "setUpdateChannel('stable')",
                                             "toggleAutoUpdate", 'id="settings-core-card"',
                                             "setTheme('dark')", "toggleCustomServer")]
        self.assertEqual(order, sorted(order))
        self.assertNotIn("settings-panel-card", settings)   # the panel version lives on the home page
        self.assertIn("'dark'", read(os.path.join(src, "theme.js")))
        self.assertIn("t==='dark'", P.render_spa_html("x", {}))

    def test_glass_skin(self):
        """1.46: the opt-in 玻璃 (glass) skin: listed, applied before first paint, every rule scoped to it,
        with fallbacks when backdrop-filter is missing or the user asks for less transparency."""
        src = os.path.join(REPO, "panel/web/src")
        self.assertIn("'glass'", read(os.path.join(src, "theme.js")))
        self.assertIn("import './theme-glass.css'", read(os.path.join(src, "main.js")))
        self.assertIn("setTheme('glass')", read(os.path.join(src, "pages/SettingsPage.vue")))
        self.assertIn("t==='glass'", P.render_spa_html("x", {}))
        css = read(os.path.join(src, "theme-glass.css"))
        self.assertNotIn("prefers-color-scheme", css)   # picked by the user, never automatic
        self.assertIn("@supports not ((backdrop-filter: blur(1px))", css)
        self.assertIn("prefers-reduced-transparency: reduce", css)
        body = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        for head in re.findall(r"([^{}]+)\{", body):
            head = head.strip()
            if head.startswith("@"):
                continue
            for sel in head.split(","):
                self.assertTrue(sel.strip().startswith('html[data-theme="glass"]'), sel)

    def test_dark_theme_css_is_generated(self):
        r = subprocess.run([sys.executable, os.path.join(REPO, "panel/web/dark-theme.py"), "--check"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, "panel/web/src/theme-dark.css is out of date: run python3 panel/web/dark-theme.py")
        css = read(os.path.join(REPO, "panel/web/src/theme-dark.css"))
        self.assertNotIn("prefers-color-scheme", css)   # a skin the user picks, not the default
        for line in css.splitlines():
            if line.startswith("html") and "{" in line and not line.startswith("html["):
                self.fail("selector without the dark-skin prefix: " + line)

    def test_cert_failure_message_unknown_cloudflare_zone(self):
        for out in ("[x] invalid domain\nError adding TXT record to domain: _acme-challenge.a.b.c",
                    "certctl: 这个 Cloudflare 账号里找不到 a.b.c 所在的域名：请确认域名已添加到该账号"):
            msg = P.cert_failure_message(out, "dns")
            self.assertIn("找不到该域名", msg, out)
            self.assertIn("端口模式", msg)
        self.assertIn("Token", P.cert_failure_message("certctl: Cloudflare API Token 无效或已过期", "dns"))
        import i18n_en
        self.assertNotRegex(i18n_en.tr(P.cert_failure_message("invalid domain", "dns"), "en"), r"[\u4e00-\u9fff]")

    def _shell_fn(self, path, name):
        src = read(os.path.join(REPO, path))
        start = src.index(name + "() {")
        return src[start:src.index("\n}\n", start) + 3]

    def test_certctl_cloudflare_zone_precheck(self):
        fn = self._shell_fn("scripts/certctl.sh", "cf_zone_check")
        harness = r"""
err() { builtin echo "ERR $*"; }
curl() {   # FAKE: "<code> <zone that exists>"
  local url=${@: -1} code zone; read -r code zone <<<"$FAKE"
  builtin echo "$url" >> "$LOG"
  if [[ $code == 000 ]]; then return 7; fi
  if [[ $url == *"name=$zone&"* ]]; then builtin printf '{"result":[{"id":"z1","name":"%s"}],"success":true}\n%s' "$zone" "$code"
  else builtin printf '{"result":[],"success":true}\n%s' "$code"; fi
}
BASE_DOMAIN=usgc.abce.kdns.fr CF_TOKEN=tok
""" + fn + "\ncf_zone_check; echo rc=$?\n"
        cases = (("200 kdns.fr", "rc=0", ""), ("200 example.com", "rc=1", "找不到 usgc.abce.kdns.fr"),
                 ("403 kdns.fr", "rc=1", "Token 无效"), ("000 kdns.fr", "rc=0", ""), ("500 kdns.fr", "rc=0", ""))
        for fake, rc, msg in cases:
            log = os.path.join(tempfile.mkdtemp(), "log")
            r = subprocess.run(["bash", "-c", harness], env=dict(os.environ, FAKE=fake, LOG=log),
                               capture_output=True, text=True)
            self.assertIn(rc, r.stdout, fake)
            self.assertIn(msg, r.stdout, fake)
        # Walks from the full name up to the parent domains, and stops at the first zone found.
        log = os.path.join(tempfile.mkdtemp(), "log")
        subprocess.run(["bash", "-c", harness], env=dict(os.environ, FAKE="200 abce.kdns.fr", LOG=log), capture_output=True)
        asked = [re.search(r"name=([^&]+)", l).group(1) for l in read(log).splitlines()]
        self.assertEqual(asked, ["usgc.abce.kdns.fr", "abce.kdns.fr"])
        sh = read(os.path.join(REPO, "scripts/certctl.sh"))
        self.assertLess(sh.index("cf_zone_check || exit 1"), sh.index("已移除旧域名的证书记录"))

    def test_cli_status_counts_only_core_sockets(self):
        fn = self._shell_fn("scripts/cmd/clashgate.sh", "core_sockets")
        harness = r"""
systemctl() {
  case "$1 $2" in
    "is-active --quiet") [[ $ACTIVE == 1 ]] ;;
    "show -p") builtin echo 4242 ;;
  esac
}
ss() { builtin printf '%s\n' \
  'tcp LISTEN 0 4096 0.0.0.0:30111 0.0.0.0:* users:(("mihomo",pid=4242,fd=7))' \
  'tcp LISTEN 0 128 0.0.0.0:30113 0.0.0.0:* users:(("nginx",pid=99,fd=6))'; }
""" + fn + "\nout=$(core_sockets); for p in 30111 30113; do grep -q \":$p \" <<<\"$out\" && echo up=$p; done; echo end\n"
        r = subprocess.run(["bash", "-c", harness], env=dict(os.environ, ACTIVE="1"), capture_output=True, text=True)
        self.assertIn("up=30111", r.stdout)
        self.assertNotIn("up=30113", r.stdout)
        r = subprocess.run(["bash", "-c", harness], env=dict(os.environ, ACTIVE="0"), capture_output=True, text=True)
        self.assertNotIn("up=", r.stdout)
        self.assertIn("end", r.stdout)

    def test_typed_reality_sni_must_answer_tls13(self):
        g = P.check_reality_dest.__globals__

        def refuse(addr, timeout=None):
            raise ConnectionRefusedError(111, "Connection refused")

        with mock.patch.object(g["socket"], "create_connection", refuse):
            with self.assertRaises(ValueError) as cm:
                P.check_reality_dest("dead.example.com")
        self.assertIn("dead.example.com:443", cm.exception.args[0])
        self.assertIn("refused", cm.exception.args[1].lower())
        # The add-node request stops before touching any file, with the raw reason as 「详情」.
        write_default_state()
        before = read(P.INBOUNDS)
        h = object.__new__(P.Panel)
        got = {}
        h.respond_mutation = lambda s, msg, ok=True, detail="": got.update(ok=ok, msg=msg, detail=detail)
        hg = P.Panel.do_add.__globals__
        with mock.patch.dict(hg, {"check_reality_dest": lambda host: (_ for _ in ()).throw(ValueError("无法连接 x", "why"))}):
            h.do_add({}, {"kind": "vless-reality", "sni": "www.example.com", "name": "r2"})
        self.assertEqual((got["ok"], got["detail"]), (False, "why"))
        self.assertTrue(got["msg"].startswith("添加失败："))
        self.assertEqual(read(P.INBOUNDS), before)
        # Blank SNI: drawn from the built-in pool, no network check.
        try:
            with mock.patch.dict(hg, {"check_reality_dest": lambda host: self.fail("checked a pool SNI")}):
                h.do_add({}, {"kind": "vless-reality", "sni": "", "name": "r3", "port": "31777"})
            self.assertTrue(got["ok"], got)
        finally:
            P.clear_pending_reload()
            write_default_state()

    def test_csp_allows_only_the_panel_scripts(self):
        import base64
        import hashlib
        g = P.Panel.send.__globals__
        page = P.render_spa_html("x", {"page": "dashboard", "note": "</script><script>alert(1)</script>"})
        inline = re.findall(r"<script>(.*?)</script>", page, re.S)
        self.assertEqual(len(inline), 1)
        sha = base64.b64encode(hashlib.sha256(inline[0].encode()).digest()).decode()
        self.assertIn(f"'sha256-{sha}'", g["CSP"])
        self.assertNotIn("unsafe-eval", g["CSP"])
        self.assertNotIn("'unsafe-inline'", g["CSP"].split("script-src")[1].split(";")[0])
        boot = re.search(r"<script type=application/json id=cs-boot>(.*?)</script>", page, re.S).group(1)
        self.assertNotIn("<", boot)
        self.assertEqual(json.loads(boot)["note"], "</script><script>alert(1)</script>")
        self.assertIn("import './boot.js'", read(os.path.join(REPO, "panel/web/src/main.js")).splitlines()[0])
        h = object.__new__(P.Panel)
        h.headers = {}
        h.command = "GET"
        sent = []
        h.send_response = lambda code: None
        h.send_header = lambda k, v: sent.append((k, v))
        h.end_headers = lambda: None
        h.wfile = io.BytesIO()
        h.send(200, "ok", "text/plain")
        self.assertIn(("Content-Security-Policy", g["CSP"]), sent)

    def test_home_cert_alert_only_on_problems(self):
        src = os.path.join(REPO, "panel/web/src")
        self.assertIn('v-if="certAlert"', read(os.path.join(src, "App.vue")))
        certs = read(os.path.join(src, "composables/useCerts.js"))
        body = certs[certs.index("const certAlert = computed"):]
        body = body[:body.index("\n  })\n")]
        for cond in ("state.mode === 'no-cert'", "certs_present === false", "certIsTemp.value", "d < 0", "d < 14"):
            self.assertIn(cond, body)

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
