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


if __name__ == "__main__":
    unittest.main()
