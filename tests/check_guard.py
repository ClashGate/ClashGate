"""Run the golden/API checks without mihomo. Usage: python3 tests/check_guard.py

Windows has no os.chown and may open text files with a legacy encoding.
This shim is local-only; CI runs the same assertions from test_panel.py on Linux.
"""
import builtins
import os
import shutil
import sys
import tempfile

if not hasattr(os, "chown"):
    os.chown = lambda *a, **k: None

_open = builtins.open
_fdopen = os.fdopen


def _utf8_text(mode, kwargs):
    if "b" not in mode and "encoding" not in kwargs:
        kwargs["encoding"] = "utf-8"
    return kwargs


def _open_utf8(file, mode="r", *args, **kwargs):
    return _open(file, mode, *args, **_utf8_text(mode, kwargs))


def _fdopen_utf8(fd, mode="r", *args, **kwargs):
    return _fdopen(fd, mode, *args, **_utf8_text(mode, kwargs))


builtins.open = _open_utf8
os.fdopen = _fdopen_utf8

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ROOT = tempfile.mkdtemp(prefix="cg-guard-")
os.environ.update(CLASHGATE_ROOT=ROOT, SYSTEMCTL="true", UFW_BIN="false", FIREWALL_CMD_BIN="false")
CS = ROOT + "/etc/clashgate"
os.makedirs(CS + "/certs")
shutil.copytree(os.path.join(REPO, "resources"), CS + "/resources")
sys.path.insert(0, os.path.join(REPO, "panel"))
sys.path.insert(0, HERE)
import panel as P  # noqa: E402
import guardlib  # noqa: E402

with open(CS + "/clashgate.env", "w", newline="\n") as f:
    f.write(
        'MODE="auto-cert"\nSERVER_IP="1.2.3.4"\nDOMAIN="ex.sslip.io"\nPANEL_PORT="25183"\n'
        'CONTROLLER_PORT="25184"\nMIHOMO_SECRET="test-secret"\n'
    )
for name in ("fullchain.pem", "privkey.pem"):
    with open(CS + "/certs/" + name, "w", newline="\n") as f:
        f.write("placeholder\n")

guardlib.assert_surface(P)
guardlib.assert_goldens(P)
print("guard ok")
