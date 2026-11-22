"""Regression: every script path that loads panel.py still works after the split.

scripts/lib/core.sh seed_routing imports panel.py via importlib as cg_panel_seed,
not as panel or __main__. These tests run that exact snippet (and the other
script entry points) in a throw-away prefix tree, in a fresh interpreter.
"""
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
CORE_SH = os.path.join(REPO, "scripts", "lib", "core.sh")


def core_sh_seed_snippet():
    """The python3 -c program in seed_routing(), taken from the live script."""
    with open(CORE_SH, encoding="utf-8") as f:
        text = f.read()
    m = re.search(
        r"(?:python3|\"\$\(py_bin \|\| echo python3\)\") -c\s+\\\s*\n\s*'([^']+)'\s+\\",
        text,
    )
    if not m:
        raise AssertionError(
            "could not find the python3 -c snippet in scripts/lib/core.sh seed_routing()"
        )
    return m.group(1)


def install_prefix(tmpdir):
    """Lay out $prefix/etc/clashgate like an installed tree (panel + resources + scripts)."""
    prefix = os.path.join(tmpdir, "prefix")
    cs = os.path.join(prefix, "etc", "clashgate")
    os.makedirs(cs, exist_ok=True)
    for name in ("panel", "resources", "scripts"):
        dst = os.path.join(cs, name)
        if os.path.islink(dst) or os.path.exists(dst):
            continue
        os.symlink(os.path.join(REPO, name), dst)
    os.makedirs(os.path.join(cs, "certs"), exist_ok=True)
    for name in ("fullchain.pem", "privkey.pem"):
        with open(os.path.join(cs, "certs", name), "w") as f:
            f.write("placeholder\n")
    with open(os.path.join(cs, "clashgate.env"), "w") as f:
        f.write(
            'MODE="no-cert"\nSERVER_IP="1.2.3.4"\nDOMAIN="ex.sslip.io"\n'
            'PANEL_PORT="25183"\nCONTROLLER_PORT="25184"\nMIHOMO_SECRET="test-secret"\n'
        )
    return prefix, cs


def snippet_env(prefix, cs, extra=None):
    env = os.environ.copy()
    env.update(
        CS_ROOT=cs,
        PYTHONPATH=os.path.join(cs, "panel") + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""),
        CLASHGATE_ROOT=prefix,
        MIHOMO_BIN=MIHOMO,
        SYSTEMCTL="true",
        UFW_BIN="false",
        FIREWALL_CMD_BIN="false",
        PYTHONDONTWRITEBYTECODE="1",
    )
    if extra:
        env.update(extra)
    return env


class CoreShSnippetTest(unittest.TestCase):
    def test_snippet_is_the_importlib_loader(self):
        src = core_sh_seed_snippet()
        self.assertIn("importlib.util", src)
        self.assertIn("cg_panel_seed", src)
        self.assertIn("ensure_seeded", src)
        self.assertIn('os.environ["CS_ROOT"]', src)

    def test_seed_routing_snippet_writes_fragments(self):
        tmp = tempfile.mkdtemp(prefix="cg-seed-")
        try:
            prefix, cs = install_prefix(tmp)
            r = subprocess.run(
                [sys.executable, "-c", core_sh_seed_snippet()],
                env=snippet_env(prefix, cs),
                cwd=cs,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                r.returncode, 0,
                "seed_routing snippet failed:\nstdout:\n%s\nstderr:\n%s" % (r.stdout, r.stderr),
            )
            for rel in (
                "routing.json",
                "routing.rule-providers.yaml",
                "routing.proxy-groups.yaml",
                "routing.rules.yaml",
            ):
                path = os.path.join(cs, rel)
                self.assertTrue(os.path.isfile(path), "missing " + path)
            # rule-providers may be an empty file when the default seed has none
            for rel in ("routing.json", "routing.proxy-groups.yaml", "routing.rules.yaml"):
                path = os.path.join(cs, rel)
                self.assertGreater(os.path.getsize(path), 0, "empty " + path)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_legacy_importlib_load_without_sys_modules_preinsert(self):
        """core.sh used to exec_module without sys.modules[name] = m; panel.py must still alias."""
        legacy = (
            "import os,importlib.util; "
            'p=os.path.join(os.environ["CS_ROOT"],"panel","panel.py"); '
            'spec=importlib.util.spec_from_file_location("cg_panel_seed", p); '
            "m=importlib.util.module_from_spec(spec); "
            "spec.loader.exec_module(m); "
            "m.get_routing().ensure_seeded(force=False)"
        )
        tmp = tempfile.mkdtemp(prefix="cg-legacy-")
        try:
            prefix, cs = install_prefix(tmp)
            r = subprocess.run(
                [sys.executable, "-c", legacy],
                env=snippet_env(prefix, cs),
                cwd=cs,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                r.returncode, 0,
                "legacy importlib load failed:\nstdout:\n%s\nstderr:\n%s" % (r.stdout, r.stderr),
            )
            self.assertTrue(os.path.isfile(os.path.join(cs, "routing.json")))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_importlib_and_import_panel_are_the_same_module(self):
        tmp = tempfile.mkdtemp(prefix="cg-alias-")
        try:
            prefix, cs = install_prefix(tmp)
            # Same load as core.sh, then prove the alias and that `import panel` is not a second copy.
            code = (
                core_sh_seed_snippet()
                + "\n"
                + "import sys, panel as P, cg_cert\n"
                "assert sys.modules['panel'] is m, 'sys.modules[panel] is not the importlib module'\n"
                "assert P is m, 'import panel loaded a second copy'\n"
                "assert m.__name__ == 'cg_panel_seed'\n"
                "assert cg_cert._panel() is m, 'cg_cert._panel() did not get the importlib module'\n"
                "print('alias-ok')\n"
            )
            r = subprocess.run(
                [sys.executable, "-c", code],
                env=snippet_env(prefix, cs),
                cwd=cs,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                r.returncode, 0,
                "alias check failed:\nstdout:\n%s\nstderr:\n%s" % (r.stdout, r.stderr),
            )
            self.assertIn("alias-ok", r.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class ScriptEntryPointsTest(unittest.TestCase):
    def test_hash_password_cli(self):
        """scripts/lib/panel.sh and clashgate.sh pipe the password to: python3 panel.py hash-password"""
        tmp = tempfile.mkdtemp(prefix="cg-hash-")
        try:
            prefix, cs = install_prefix(tmp)
            r = subprocess.run(
                [sys.executable, os.path.join(cs, "panel", "panel.py"), "hash-password"],
                input="testpass12\n",
                env=snippet_env(prefix, cs),
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(r.stdout.strip().startswith("pbkdf2_sha256$"), r.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_shell_seed_routing_and_assemble_pass_mihomo_t(self):
        """Dry-run of the install render path: seed_routing + assemble_config + mihomo -t."""
        if not os.path.isfile(MIHOMO) or not os.access(MIHOMO, os.X_OK):
            self.skipTest("mihomo binary not found at " + MIHOMO)
        tmp = tempfile.mkdtemp(prefix="cg-render-")
        script = os.path.join(tmp, "run.sh")
        try:
            prefix, cs = install_prefix(tmp)
            # MODE=no-cert avoids certctl/self-sign. chown is stubbed (no mihomo user here).
            with open(script, "w") as f:
                f.write(r"""#!/usr/bin/env bash
set -euo pipefail
chown() { return 0; }
# shellcheck source=/dev/null
. "$REPO/scripts/lib/common.sh"
# shellcheck source=/dev/null
. "$REPO/scripts/lib/core.sh"
CS_ROOT=$CS
LIB_DIR=$CS
CONF_DIR=$CS
CONF=$CS/config.yaml
STATE=$CS/nodes.tsv
FRAG_CONTROLLER=$CS/controller.yaml
FRAG_REALITY=$CS/listeners.reality.yaml
FRAG_EXTRA=$CS/listeners.extra.yaml
FRAG_PROXIES=$CS/proxies.extra.yaml
FRAG_PROVIDERS=$CS/providers.extra.yaml
FRAG_CLUSTER_PROXIES=$CS/proxies.cluster.yaml
FRAG_CLUSTER_LISTENERS=$CS/listeners.cluster.yaml
FRAG_RULE_PROVIDERS=$CS/routing.rule-providers.yaml
FRAG_PROXY_GROUPS=$CS/routing.proxy-groups.yaml
FRAG_RULES=$CS/routing.rules.yaml
ROUTING_JSON=$CS/routing.json
ROUTING_DIR=$CS/routing
CUSTOM_CONF=$CS/custom_config.yaml
CLIENT_DIR=$CS/client
BIN=$MIHOMO_BIN
MODE=no-cert
SERVER_IP=1.2.3.4
PANEL_PORT=25183
CONTROLLER_PORT=25184
MIHOMO_SECRET=test-secret
export CS_ROOT CLASHGATE_ROOT PYTHONPATH MIHOMO_BIN SYSTEMCTL=true UFW_BIN=false FIREWALL_CMD_BIN=false
export PYTHONDONTWRITEBYTECODE=1
seed_routing
# Empty node/inbound fragments, as on a fresh tree before render_server writes listeners.
: > "$FRAG_REALITY"
: > "$FRAG_EXTRA"
: > "$FRAG_PROXIES"
: > "$FRAG_PROVIDERS"
: > "$FRAG_CLUSTER_PROXIES"
: > "$FRAG_CLUSTER_LISTENERS"
render_controller
assemble_config
validate_conf
echo "render-ok"
""")
            env = snippet_env(prefix, cs, extra={"REPO": REPO, "CS": cs})
            r = subprocess.run(
                ["bash", script],
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                r.returncode, 0,
                "shell seed_routing/assemble/validate failed:\nstdout:\n%s\nstderr:\n%s" % (r.stdout, r.stderr),
            )
            self.assertIn("render-ok", r.stdout)
            self.assertTrue(os.path.isfile(os.path.join(cs, "config.yaml")))
            self.assertTrue(os.path.getsize(os.path.join(cs, "config.yaml")) > 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class ShellIpv6RenderTest(unittest.TestCase):
    def test_shell_assemble_ipv6_only_passes_mihomo_t(self):
        """IPv6-only server: core.sh assemble_config listens on "::" and uses the system resolver."""
        if not os.path.isfile(MIHOMO) or not os.access(MIHOMO, os.X_OK):
            self.skipTest("mihomo binary not found at " + MIHOMO)
        src = open(os.path.join(HERE, "test_seed_load.py"), encoding="utf-8").read()
        body = src[src.index('f.write(r"""#!/usr/bin/env bash'):]
        script_text = body[body.index('r"""') + 4:body.index('""")')]
        script_text = script_text.replace("SERVER_IP=1.2.3.4", "SERVER_IP=2001:db8::10")
        script_text = script_text.replace(': > "$FRAG_REALITY"\n',
                                          'printf \'  - name: r\\n    type: vless\\n    port: 31555\\n    listen: 0.0.0.0\\n    users:\\n      - username: user\\n        uuid: 9d1c1c8e-4f1e-4d0b-9a57-2a1f0d6b7e11\\n        flow: xtls-rprx-vision\\n    reality-config:\\n      dest: www.apple.com:443\\n      private-key: aGVsbG8taGVsbG8taGVsbG8taGVsbG8taGVsbG8tMXI\\n      short-id:\\n        - 0123abcd\\n      server-names:\\n        - www.apple.com\\n\' > "$FRAG_REALITY"\n')
        tmp = tempfile.mkdtemp(prefix="cg-render6-")
        try:
            prefix, cs = install_prefix(tmp)
            script = os.path.join(tmp, "run.sh")
            with open(script, "w") as f:
                f.write(script_text)
            env = snippet_env(prefix, cs, extra={"REPO": REPO, "CS": cs})
            r = subprocess.run(["bash", script], env=env, capture_output=True, text=True)
            conf = open(os.path.join(cs, "config.yaml"), encoding="utf-8").read() if os.path.isfile(os.path.join(cs, "config.yaml")) else ""
            self.assertEqual(r.returncode, 0, "stdout:\n%s\nstderr:\n%s\nconfig:\n%s" % (r.stdout, r.stderr, conf))
            self.assertIn('listen: "::"', conf)
            self.assertIn("    - system\n", conf)
            self.assertNotIn("1.1.1.1", conf[conf.index("\ndns:"):conf.index("\ndns:") + 400])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


CERT_FAKE_CERTCTL = r"""#!/usr/bin/env bash
# certctl stand-in: records its arguments, drops the old domain's acme.sh record like the real one,
# then fails (FAKE_CERT_RC=1) or writes a self-signed certificate for the DOMAIN now in clashgate.env.
echo "$*" >> "$FAKE_CS/certctl.args"
rm -rf "$FAKE_CS/acme.sh/old.example.com_ecc"
if [[ ${FAKE_CERT_RC:-0} != 0 ]]; then echo "certctl: 证书申请失败（测试）"; exit 1; fi
d=$(sed -n 's/^DOMAIN="\(.*\)"$/\1/p' "$FAKE_CS/clashgate.env")
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes -days 2 -subj "/CN=$d" \
  -addext "subjectAltName=DNS:$d" -keyout "$FAKE_CS/certs/privkey.pem" -out "$FAKE_CS/certs/fullchain.pem" >/dev/null 2>&1
echo "certctl: ok"
"""

CERT_HARNESS = r"""
chown() { return 0; }
systemctl() { return 0; }
ss() { return 0; }   # nothing listens on this test host as far as the script can tell
verify() { log "检查运行状态"; }
open_firewall() { return 0; }
has_tty() { return 1; }
CS_ROOT=$CS; LIB_DIR=$CS; CONF_DIR=$CS; CS_ETC=$CS
CONF=$CS/config.yaml; STATE=$CS/nodes.tsv; ENV_FILE=$CS/clashgate.env
PANEL_CFG=$CS/panel.json; PANEL_SESSIONS=$CS/sessions.json; ACME_HOME=$CS/acme.sh
FRAG_CONTROLLER=$CS/controller.yaml; FRAG_REALITY=$CS/listeners.reality.yaml; FRAG_EXTRA=$CS/listeners.extra.yaml
FRAG_PROXIES=$CS/proxies.extra.yaml; FRAG_PROVIDERS=$CS/providers.extra.yaml
FRAG_CLUSTER_PROXIES=$CS/proxies.cluster.yaml; FRAG_CLUSTER_LISTENERS=$CS/listeners.cluster.yaml
FRAG_RULE_PROVIDERS=$CS/routing.rule-providers.yaml; FRAG_PROXY_GROUPS=$CS/routing.proxy-groups.yaml
FRAG_RULES=$CS/routing.rules.yaml; ROUTING_JSON=$CS/routing.json; ROUTING_DIR=$CS/routing
CUSTOM_CONF=$CS/custom_config.yaml; CLIENT_DIR=$CS/client; BIN=$MIHOMO_BIN
export CS_ROOT CLASHGATE_ROOT PYTHONPATH MIHOMO_BIN SYSTEMCTL=true UFW_BIN=false FIREWALL_CMD_BIN=false
export PYTHONDONTWRITEBYTECODE=1
ACTION_ARG=new.example.com
do_cert || exit $?   # as the dispatcher runs it (errexit off inside)
"""


CERT_TTY_HARNESS = CERT_HARNESS.replace("has_tty() { return 1; }", r'''has_tty() { return 0; }
IFS='|' read -r -a ANS <<< "$CERT_ANSWERS"; AI_FILE=$(mktemp); echo 0 > "$AI_FILE"
ask() {   # answers in order ("" = Enter); runs in $(...) subshells, so the index lives in a file
  builtin printf '%s\n' "$1" >&2
  local i; i=$(<"$AI_FILE"); builtin echo $((i + 1)) > "$AI_FILE"
  if ((i >= ${#ANS[@]})); then
    [[ -n $2 ]] || kill -TERM $$   # out of answers at a prompt without a default: stop, never loop
    builtin printf '%s' "$2"; return
  fi
  builtin printf '%s' "${ANS[i]:-$2}"
}''').replace("ACTION_ARG=new.example.com\n", "")


class CertCommandTest(unittest.TestCase):
    """`clashgate cert <domain>`: nothing changes when the certificate fails; otherwise the domain,
    nodes and credentials are new and the panel password is kept."""

    def _tree(self):
        tmp = tempfile.mkdtemp(prefix="cg-cert-")
        self.addCleanup(shutil.rmtree, tmp, True)
        prefix = os.path.join(tmp, "prefix")
        cs = os.path.join(prefix, "etc", "clashgate")
        os.makedirs(os.path.join(cs, "certs"))
        os.makedirs(os.path.join(cs, "acme.sh", "old.example.com_ecc"))
        with open(os.path.join(cs, "acme.sh", "old.example.com_ecc", "old.example.com.conf"), "w") as f:
            f.write("Le_Domain='old.example.com'\n")
        for name in ("panel", "resources"):
            os.symlink(os.path.join(REPO, name), os.path.join(cs, name))
        shutil.copytree(os.path.join(REPO, "scripts"), os.path.join(cs, "scripts"))
        fake = os.path.join(cs, "scripts", "certctl.sh")
        with open(fake, "w") as f:
            f.write(CERT_FAKE_CERTCTL)
        os.chmod(fake, 0o755)
        files = {
            "clashgate.env": 'MODE="auto-cert"\nCERT_MODE="port"\nTLS="internal"\nSERVER_IP="1.2.3.4"\n'
                             'DOMAIN="old.example.com"\nPANEL_PORT="25183"\nCONTROLLER_PORT="25184"\n'
                             'MIHOMO_SECRET="old-secret"\n',
            "panel.json": '{"username": "admin", "password_hash": "HASH", "port": 25183, "sub_token": "' + "a" * 48 + '"}\n',
            "nodes.tsv": "VlessReality\t30001\tuuid-old\tpriv\tpub\tsid\twww.apple.com\tdec\tenc\n",
            "inbounds.json": '[{"name": "old-ss"}]\n',
            "listeners.extra.yaml": '  - {"name": "old-ss", "type": "shadowsocks"}\n',
            "config.yaml": "old-config\n",
            "certs/fullchain.pem": "old-cert\n",
            "certs/privkey.pem": "old-key\n",
        }
        for rel, body in files.items():
            with open(os.path.join(cs, rel), "w") as f:
                f.write(body)
        return prefix, cs, files

    def _run(self, prefix, cs, rc, answers=None):
        src = open(os.path.join(REPO, "scripts", "cmd", "clashgate.sh"), encoding="utf-8").read()
        src = re.sub(r"(?m)^CS_HOME=.*$", "CS_HOME=" + REPO, src, count=1)
        src = src[: src.index('\nACTION=""\n')]
        script = os.path.join(os.path.dirname(prefix), "run.sh")
        with open(script, "w", encoding="utf-8") as f:
            f.write(src + (CERT_HARNESS if answers is None else CERT_TTY_HARNESS))
        env = snippet_env(prefix, cs, extra={"CS": cs, "FAKE_CS": cs, "FAKE_CERT_RC": str(rc), "CLASHGATE_LANG": "zh",
                                             "CERT_ANSWERS": "|".join(answers or [])})
        return subprocess.run(["bash", script], env=env, capture_output=True, text=True, timeout=180)

    def test_failed_certificate_changes_nothing(self):
        prefix, cs, files = self._tree()
        r = self._run(prefix, cs, 1)
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("证书申请失败", r.stderr)
        for rel, body in files.items():
            with open(os.path.join(cs, rel)) as f:
                self.assertEqual(f.read(), body, rel)
        self.assertTrue(os.path.isfile(os.path.join(cs, "acme.sh", "old.example.com_ecc", "old.example.com.conf")))

    def test_new_domain_resets_nodes_and_credentials(self):
        if not os.path.isfile(MIHOMO) or not os.access(MIHOMO, os.X_OK):
            self.skipTest("mihomo binary not found at " + MIHOMO)
        import json
        prefix, cs, _ = self._tree()
        r = self._run(prefix, cs, 0)
        self.assertEqual(r.returncode, 0, "stdout:\n%s\nstderr:\n%s" % (r.stdout, r.stderr))
        read = lambda rel: open(os.path.join(cs, rel)).read()
        self.assertIn("reissue", read("certctl.args"))
        env = read("clashgate.env")
        self.assertIn('DOMAIN="new.example.com"', env)
        self.assertNotIn('MIHOMO_SECRET="old-secret"', env)
        panel = json.loads(read("panel.json"))
        self.assertEqual(panel["password_hash"], "HASH")
        self.assertRegex(panel["sub_token"], r"^[0-9a-f]{48}$")
        self.assertNotEqual(panel["sub_token"], "a" * 48)
        nodes = [l.split("\t") for l in read("nodes.tsv").splitlines() if l]
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0][0], "VlessReality")
        self.assertNotEqual(nodes[0][2], "uuid-old")
        self.assertEqual(json.loads(read("inbounds.json")), [])
        self.assertEqual(read("listeners.extra.yaml"), "")
        self.assertNotIn("old-ss", read("config.yaml"))
        self.assertIn("https://new.example.com:25183\n", r.stdout)   # the panel URL
        self.assertNotIn("/sub/", r.stdout)   # the subscription link is not printed
        self.assertIn("[6/6]", r.stdout)

    def test_interactive_switches_the_certificate_method(self):
        """The menu asks for the method first (Enter keeps it); a failed request also restores CERT_MODE."""
        if not os.path.isfile(MIHOMO) or not os.access(MIHOMO, os.X_OK):
            self.skipTest("mihomo binary not found at " + MIHOMO)
        prefix, cs, files = self._tree()
        env_path = os.path.join(cs, "clashgate.env")
        with open(env_path, "w") as f:
            f.write(files["clashgate.env"].replace('CERT_MODE="port"', 'CERT_MODE="dns"') + 'CF_TOKEN="tok"\n')
        dns_env = open(env_path).read()
        r = self._run(prefix, cs, 1, answers=["1", "new.example.com", "y"])
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("请输入 [1/2/3]（回车沿用当前：DNS API 模式）：", r.stderr)
        self.assertEqual(open(env_path).read(), dns_env)   # restored: still DNS API mode
        r = self._run(prefix, cs, 0, answers=["1", "new.example.com", "y"])
        self.assertEqual(r.returncode, 0, "stdout:\n%s\nstderr:\n%s" % (r.stdout, r.stderr))
        env = open(env_path).read()
        self.assertIn('CERT_MODE="port"', env)
        self.assertIn('DOMAIN="new.example.com"', env)
        self.assertIn("确定更换为 new.example.com？节点和订阅链接会重新生成 [y/N]：", r.stderr)
        self.assertNotIn("Cloudflare API Token", r.stderr)   # port mode: no token prompt
        # A "n" at the confirmation changes nothing.
        before = open(env_path).read()
        r = self._run(prefix, cs, 0, answers=["", "other.example.com", "n"])
        self.assertEqual(r.returncode, 0)
        self.assertIn("已取消", r.stdout)
        self.assertEqual(open(env_path).read(), before)


if __name__ == "__main__":
    unittest.main()
