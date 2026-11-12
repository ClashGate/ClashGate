"""i18n parity: every zh UI string used by App.vue has en/ru/fa entries, no unused UI entries,
server message tables (panel/i18n_en.py, locales/*.json "server") cover the same keys, and
{placeholders} match. Exit 1 on any problem."""
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, "panel", "web", "src")
sys.path.insert(0, os.path.join(REPO, "panel"))
import i18n_en  # noqa: E402

app = open(os.path.join(SRC, "App.vue"), encoding="utf-8").read()
js = open(os.path.join(SRC, "i18n.js"), encoding="utf-8").read()
EN = json.loads(re.search(r"export const EN = (\{.*?\n\})", js, re.S).group(1))
loc = {l: json.load(open(os.path.join(SRC, "locales", f"{l}.json"), encoding="utf-8")) for l in ("ru", "fa")}
CJK = re.compile(r"[\u4e00-\u9fff]")

used = set(re.findall(r"\bt\(\s*'((?:[^'\\]|\\.)*)'", app))
used |= set(re.findall(r"(?:desc|lockedNote): '([^']*)'", app))  # strings passed through t(var)
used |= set(re.findall(r"\bt\(\s*\"((?:[^\"\\]|\\.)*)\"", app))
# Server-provided status labels rendered via t(state.status.state_txt)
panel_py = open(os.path.join(REPO, "panel", "panel.py"), encoding="utf-8").read()
state_zh = re.search(r"^STATE_ZH = \{(.*?)\}\n", panel_py, re.M | re.S).group(1)
used |= set(re.findall(r'\("([^"]+)", "(?:ok|bad|warn)"\)', state_zh))
used = {k for k in used if CJK.search(k)}

problems = []
ui = {"en": EN, "ru": loc["ru"]["ui"], "fa": loc["fa"]["ui"]}
for lang, d in ui.items():
    for k in sorted(used - set(d)):
        problems.append(f"ui[{lang}] missing: {k}")
    for k in sorted(set(d) - used):
        problems.append(f"ui[{lang}] unused: {k}")

srv_keys = {k for k, _ in i18n_en.TABLE}
for lang in ("ru", "fa"):
    sk = set(loc[lang]["server"])
    for k in sorted(srv_keys - sk):
        problems.append(f"server[{lang}] missing: {k}")
    for k in sorted(sk - srv_keys):
        problems.append(f"server[{lang}] not in i18n_en.TABLE: {k}")

PH_UI = re.compile(r"\{(\w+)\}")
for lang, d in ui.items():
    for k, v in d.items():
        if set(PH_UI.findall(k)) != set(PH_UI.findall(v)):
            problems.append(f"ui[{lang}] placeholder mismatch: {k} => {v}")
srv = {"en": dict(i18n_en.TABLE), "ru": loc["ru"]["server"], "fa": loc["fa"]["server"]}
for lang, d in srv.items():
    for k, v in d.items():
        if k.count("{}") != len(re.findall(r"\{\d*\}", v)):
            problems.append(f"server[{lang}] placeholder mismatch: {k} => {v}")

for p in problems:
    print(p)
print(f"i18n: {len(used)} UI strings, {len(srv_keys)} server strings, {len(problems)} problem(s)")
sys.exit(1 if problems else 0)
