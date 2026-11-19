"""Shell (CLI / installer) i18n: i18n.ru.tsv covers every key of i18n.en.tsv with matching placeholders,
and help, the management menu, the install / certificate prompts and common labels print no Chinese
in en / ru runs (zh runs stay Chinese). Runs bash; no root, no network, nothing installed."""
import os
import re
import subprocess
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LIB = os.path.join(REPO, "scripts", "lib")
CJK = re.compile(r"[\u3000-\u303f\u4e00-\u9fff\uff00-\uffef]")
PH = re.compile(r"%-?\d*s")
problems = []


def table(lang):
    out = {}
    with open(os.path.join(LIB, f"i18n.{lang}.tsv"), encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.rstrip("\n")
            if not line:
                continue
            k, sep, v = line.partition("\t")
            if not sep or not v or "\t" in v:
                problems.append(f"i18n.{lang}.tsv:{n}: malformed line")
                continue
            if k in out:
                problems.append(f"i18n.{lang}.tsv:{n}: duplicate key {k!r}")
            out[k] = v
    return out


en, ru = table("en"), table("ru")
for k, v in en.items():
    r = ru.get(k)
    if r is None:
        problems.append(f"ru missing: {k!r}")
        continue
    for lang, val in (("en", v), ("ru", r)):
        if CJK.search(val):
            problems.append(f"{lang} value has Chinese: {k!r} -> {val!r}")
    if PH.findall(v) != PH.findall(r):
        problems.append(f"ru placeholders differ: {k!r}")
    if v.endswith("\\n") != r.endswith("\\n"):
        problems.append(f"ru trailing newline differs: {k!r}")

# Static: every Chinese message the scripts print is in the table (so en / ru never fall back to Chinese).
# printf / ask formats are looked up as-is; expanded messages (die / warn / info / log / echo "...$x...") by %s pattern.
def _norm(s):
    s = re.sub(r"\$\((?:[^()]|\([^()]*\))*\)", "%s", s)
    s = re.sub(r"\$\{[^}]*\}|\$[A-Za-z_][A-Za-z0-9_]*|\$\d", "%s", s)
    return s.replace('\\"', '"').replace("\\$", "$")


_pats = [re.compile("^" + ".*".join(re.escape(p) for p in k.split("%s")) + "$", re.S) for k in en if "%s" in k]
SCRIPTS = [os.path.join(REPO, "scripts", "cmd", "clashgate.sh"), os.path.join(REPO, "scripts", "certctl.sh")] + sorted(
    os.path.join(LIB, f) for f in os.listdir(LIB) if f.endswith(".sh") and f != "i18n.sh")
for path in SCRIPTS:
    rel = os.path.relpath(path, REPO)
    for n, line in enumerate(open(path, encoding="utf-8"), 1):
        line = line.split("{ # ")[0]   # trailing comment after a function header
        if line.lstrip().startswith("#") or "builtin printf" in line or "'\\''" in line:
            continue
        for m in re.finditer(r"\b(?:printf|ask)\s+'([^']*)'", line):
            if CJK.search(m.group(1)) and m.group(1) not in en:
                problems.append(f"{rel}:{n}: not in i18n.en.tsv: {m.group(1)!r}")
        for m in re.finditer(r'\b(?:warn|die|info|log|echo|ask|say|err)\s+"((?:[^"\\]|\\.)*)"', line):
            msg = _norm(m.group(1))
            if CJK.search(msg) and msg not in en and not any(p.match(msg) for p in _pats):
                problems.append(f"{rel}:{n}: not in i18n.en.tsv: {msg!r}")

# Harness: the real clashgate.sh functions (dispatcher cut off) with tty / system calls stubbed.
src = open(os.path.join(REPO, "scripts", "cmd", "clashgate.sh"), encoding="utf-8").read()
src = re.sub(r"(?m)^CS_HOME=.*$", f"CS_HOME={REPO}", src, count=1)
src = src[: src.index('\nACTION=""\n')]
HARNESS = r'''
set +e; trap - ERR
has_tty() { return 0; }
ANS=("$@"); AI_FILE=$(mktemp); echo 0 > "$AI_FILE"
# ask runs in $(...) subshells: keep the answer index in a file. Out of answers -> stop (no endless re-prompt).
ask() {
  printf '%s\n' "$1" >&2
  local i; i=$(<"$AI_FILE"); builtin echo $((i + 1)) > "$AI_FILE"
  if ((i >= ${#ANS[@]})); then [[ $2 != "" ]] && { builtin printf '%s' "$2"; return; }; kill -TERM $$; fi
  builtin printf '%s' "${ANS[i]}"
}
require_installed() { :; }; load_env() { :; }; svc_state() { printf '%s' "$(L 运行中 running)"; }
cert_issuer() { :; }
case $CASE in
  help) usage ;;
  menu-nocert) MODE=no-cert; do_menu ;;
  menu-cert) MODE=auto-cert; DOMAIN=example.com; do_menu ;;
  install-port|install-dns|install-manual|install-nocert) interactive_setup; mode_label; echo; cert_mode_label; echo; tls_label; echo ;;
esac
'''
cases = {
    "help": [],
    "menu-nocert": ["0"],
    "menu-cert": ["0"],
    "install-nocert": ["1"],
    "install-port": ["2", "1", "*.bad", "example.com"],
    "install-dns": ["2", "2", "bad domain", "*.example.com", "tok en", "token123"],
    "install-manual": ["3", "example.com"],
}
with tempfile.TemporaryDirectory() as td:
    script = os.path.join(td, "h.sh")
    with open(script, "w", encoding="utf-8") as f:
        f.write(src + HARNESS)
    for lang in ("zh", "en", "ru"):
        for case, answers in cases.items():
            env = dict(os.environ, CLASHGATE_LANG=lang, CASE=case, LC_ALL="C.UTF-8")
            try:
                p = subprocess.run(["bash", script, *answers], env=env, capture_output=True, text=True, timeout=60)
            except subprocess.TimeoutExpired:
                problems.append(f"{lang}/{case}: timed out")
                continue
            out = p.stdout + p.stderr
            if len(out.strip()) < 20:
                problems.append(f"{lang}/{case}: no output ({p.returncode}): {out!r}")
                continue
            if lang == "zh":
                if not CJK.search(out):
                    problems.append(f"zh/{case}: no Chinese output")
                continue
            for line in out.splitlines():
                # The language picker / menu entry name the other languages on purpose.
                stripped = line.replace("语言 / ", "").replace("中文", "")
                if CJK.search(stripped):
                    problems.append(f"{lang}/{case}: Chinese leaked: {line.strip()!r}")
            if lang == "ru" and not re.search(r"[А-Яа-яЁё]", out):
                problems.append(f"ru/{case}: no Russian output")

# Saved language (installer picker / `clashgate lang`) is used without CLASHGATE_LANG; CLASHGATE_LANG wins for one run.
with tempfile.TemporaryDirectory() as td:
    envf = os.path.join(td, "clashgate.env")
    with open(envf, "w") as f:
        f.write('MODE="auto-cert"\nCLASHGATE_LANG="ru"\n')
    base = {k: v for k, v in os.environ.items() if k not in ("CLASHGATE_LANG", "LANG", "LC_ALL")}
    cg = os.path.join(REPO, "scripts", "cmd", "clashgate.sh")
    for extra, want in (({}, "Использование"), ({"CLASHGATE_LANG": "en"}, "Usage:"), ({"CLASHGATE_LANG": "zh"}, "用法")):
        out = subprocess.run(["bash", cg, "help"], env=dict(base, CS_LANG_FILE=envf, **extra),
                             capture_output=True, text=True, timeout=60).stdout
        if want not in out:
            problems.append(f"saved language ru with {extra or 'no override'}: expected {want!r}")
    out = subprocess.run(["bash", cg, "help"], env=dict(base, LANG="ru_RU.UTF-8", CS_LANG_FILE=os.path.join(td, "none")),
                         capture_output=True, text=True, timeout=60).stdout
    if "Использование" not in out:
        problems.append("LANG=ru_RU.UTF-8 should default to Russian")

# certctl.sh (run by the installer, the renew timer and the panel) speaks the same language; the panel pins zh.
with tempfile.TemporaryDirectory() as td:
    etc = os.path.join(td, "etc", "clashgate")
    os.makedirs(etc)
    cc = os.path.join(REPO, "scripts", "certctl.sh")
    base = {k: v for k, v in os.environ.items() if k not in ("CLASHGATE_LANG", "LANG", "LC_ALL", "CS_LANG_FILE")}

    def certctl(action, **env):
        p = subprocess.run(["bash", cc, action], env=dict(base, CLASHGATE_ROOT=td, **env),
                           capture_output=True, text=True, timeout=60)
        return p.returncode, p.stdout + p.stderr

    rc, out = certctl("renew", CLASHGATE_LANG="en")   # no env file yet
    if rc == 0 or "Missing config file" not in out:
        problems.append(f"certctl en without env file: {out!r}")
    with open(os.path.join(etc, "clashgate.env"), "w") as f:
        f.write('DOMAIN="example.com"\nCERT_MODE="port"\nCLASHGATE_LANG="ru"\n')
    runs = {
        "zh": ("用法", {"CLASHGATE_LANG": "zh"}),
        "en": ("Usage: certctl.sh", {"CLASHGATE_LANG": "en"}),
        "ru": ("Использование", {}),   # saved language (the renew timer has no CLASHGATE_LANG)
    }
    for lang, (want, env) in runs.items():
        for action in ("bogus", "deploy"):
            rc, out = certctl(action, **env)
            if rc == 0 or not out.startswith("certctl: "):
                problems.append(f"certctl {lang}/{action}: unexpected {rc} {out!r}")
            if lang != "zh" and CJK.search(out):
                problems.append(f"certctl {lang}/{action}: Chinese leaked: {out!r}")
            if lang == "zh" and not CJK.search(out):
                problems.append(f"certctl zh/{action}: not Chinese: {out!r}")
            if action == "bogus" and want not in out:
                problems.append(f"certctl {lang}: expected {want!r} in {out!r}")

for p in problems:
    print(" -", p)
print(f"shell i18n: {len(en)} en keys, {len(ru)} ru keys, {len(problems)} problem(s)")
sys.exit(1 if problems else 0)
