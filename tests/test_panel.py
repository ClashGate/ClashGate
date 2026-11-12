"""ClashGate panel tests: run against a throw-away fake /etc/clashgate tree.

Needs a Mihomo binary for `mihomo -t` (MIHOMO_BIN, default tests/.cache/mihomo; tests/run.sh
downloads the pinned version). Run: python3 -m unittest discover -s tests -v
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

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
        order = ["1.07.9", "1.08", "1.09", "1.10", "1.11", "1.12", "1.13", "1.14", "1.15"]
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
        vue = read(os.path.join(REPO, "panel/web/src/App.vue"))
        js = vue[vue.index("const CG_CERT_PATH"):vue.index("async function saveCustomConfig")]
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
        vue = read(os.path.join(REPO, "panel/web/src/App.vue"))
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
        vue = read(os.path.join(REPO, "panel/web/src/App.vue"))
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


if __name__ == "__main__":
    unittest.main()
