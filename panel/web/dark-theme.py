#!/usr/bin/env python3
"""Generate src/theme-dark.css: the 「深色」 (dark) panel skin, active on <html data-theme="dark">
(Settings > 皮肤; the default skin stays light).

Every colour in src/style.css and every Tailwind colour the templates use is mapped with one rule
(OKLCH lightness inverted, accents kept), so the dark look follows the light one without a second
hand-written theme. Run it after changing colours in style.css or adding an arbitrary colour class
(bg-[#...]) to a template:

    python3 panel/web/dark-theme.py

tests/test_panel.py fails while the committed file is out of date. Stdlib only."""
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src")
OUT = os.path.join(SRC, "theme-dark.css")
PFX = 'html[data-theme="dark"]'
PAGE_BG = "#0f1318"   # page background: below the cards (#ffffff maps to the card colour)

# Tailwind's default palette entries the templates use (Tailwind v4 theme values). The project's own
# slate / emerald (blue) scales are read from the @theme block in style.css.
TAILWIND = {
    "--color-amber-50": "oklch(98.7% .022 95.277)",
    "--color-amber-100": "oklch(96.2% .059 95.617)",
    "--color-amber-200": "oklch(92.4% .12 95.746)",
    "--color-amber-300": "oklch(87.9% .169 91.605)",
    "--color-amber-400": "oklch(82.8% .189 84.429)",
    "--color-amber-500": "oklch(76.9% .188 70.08)",
    "--color-amber-700": "oklch(55.5% .163 48.998)",
    "--color-amber-800": "oklch(47.3% .137 46.201)",
    "--color-amber-900": "oklch(41.4% .112 45.904)",
    "--color-amber-950": "oklch(27.9% .077 45.635)",
    "--color-green-600": "oklch(62.7% .194 149.214)",
    "--color-rose-50": "oklch(96.9% .015 12.422)",
    "--color-rose-100": "oklch(94.1% .03 12.58)",
    "--color-rose-200": "oklch(89.2% .058 10.001)",
    "--color-rose-300": "oklch(81% .117 11.638)",
    "--color-rose-500": "oklch(64.5% .246 16.439)",
    "--color-rose-600": "oklch(58.6% .253 17.585)",
    "--color-rose-700": "oklch(51.4% .222 16.935)",
    "--color-rose-950": "oklch(27.1% .105 12.094)",
    "--color-sky-50": "oklch(97.7% .013 236.62)",
    "--color-sky-100": "oklch(95.1% .026 236.824)",
    "--color-sky-200": "oklch(90.1% .058 230.902)",
    "--color-sky-400": "oklch(74.6% .16 232.661)",
    "--color-sky-700": "oklch(50% .134 242.749)",
    "--color-sky-800": "oklch(44.3% .11 240.79)",
    "--color-sky-900": "oklch(39.1% .09 240.876)",
    "--color-teal-500": "oklch(70.4% .14 182.503)",
    "--color-violet-50": "oklch(96.9% .016 293.756)",
    "--color-violet-200": "oklch(89.4% .057 293.283)",
    "--color-violet-700": "oklch(49.1% .27 292.581)",
}


def _lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _gam(c):
    return 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055


def rgb_to_oklch(r, g, b):
    r, g, b = (_lin(x / 255) for x in (r, g, b))
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    L = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s
    A = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    B = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    return L, math.hypot(A, B), math.degrees(math.atan2(B, A)) % 360


def _lab_to_lin(L, C, H):
    A, B = C * math.cos(math.radians(H)), C * math.sin(math.radians(H))
    l = (L + 0.3963377774 * A + 0.2158037573 * B) ** 3
    m = (L - 0.1055613458 * A - 0.0638541728 * B) ** 3
    s = (L - 0.0894841775 * A - 1.2914855480 * B) ** 3
    return (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
            -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
            -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)


def oklch_to_rgb(L, C, H):
    ok = lambda t: all(-1e-4 <= x <= 1 + 1e-4 for x in t)
    rgb = _lab_to_lin(L, C, H)
    if not ok(rgb):   # out of sRGB: lower the chroma until it fits
        lo, hi = 0.0, C
        for _ in range(25):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if ok(_lab_to_lin(L, mid, H)) else (lo, mid)
        rgb = _lab_to_lin(L, lo, H)
    return tuple(max(0, min(255, round(_gam(max(0.0, min(1.0, x))) * 255))) for x in rgb)


def map_lch(L, C, H, text=True):
    """Light surfaces become dark ones and dark text light text. Mid-tone accents stay as they are
    (as text they only get lighter); neutrals get a faint slate-blue tint."""
    accent = C > 0.04 and 0.45 < L < (0.85 if C > 0.1 else 0.75)
    if accent and not text:
        return L, C, H
    inv = 1.10 - 0.89 * L
    Ln = max(inv, L) if accent else inv
    Ln = max(0.16, min(0.95, Ln))
    if C < 0.035 and Ln < 0.5:
        H = H if C > 0.006 else 255.0
        C = max(C * 1.3, 0.012)
    if Ln < 0.4:
        C = min(C, 0.07)
    return Ln, C, H


def _hexrgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def map_hex(h, text=True):
    return "#%02x%02x%02x" % oklch_to_rgb(*map_lch(*rgb_to_oklch(*_hexrgb(h)), text=text))


def map_oklch(s):
    m = re.fullmatch(r"oklch\(([\d.]+)%\s+([\d.]+)\s+([\d.]+)\)", s.strip())
    L, C, H = map_lch(float(m.group(1)) / 100, float(m.group(2)), float(m.group(3)))
    return f"oklch({L * 100:.1f}% {C:.3f} {H:.3f})"


SURFACE = map_hex("#ffffff", text=False)
HEX = re.compile(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b")
RGBA = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)")
SHADOW = ("box-shadow", "text-shadow", "filter")
TEXT = ("color", "fill", "stroke", "caret-color", "-webkit-text-fill-color", "outline-color", "text-decoration-color")


def map_value(prop, val):
    """Dark version of one declaration value, or None when it has no colour to change."""
    if "url(" in val:
        return None
    text = prop in TEXT
    shadow = prop in SHADOW
    changed = []

    def hexs(m):
        if text and m.group(0).lower() in ("#fff", "#ffffff"):
            return m.group(0)   # white text sits on a coloured button
        changed.append(1)
        return map_hex(m.group(0), text=text)

    def rgbas(m):
        r, g, b = (int(m.group(i)) for i in (1, 2, 3))
        a = float(m.group(4)) if m.group(4) else 1.0
        L, C, H = rgb_to_oklch(r, g, b)
        if shadow:
            if C > 0.04:
                return m.group(0)
            changed.append(1)
            return f"rgba(255, 255, 255, {round(a * 0.12, 3)})" if L > 0.7 else f"rgba(0, 0, 0, {round(min(0.6, a * 2.2), 3)})"
        if text and (r, g, b) == (255, 255, 255):
            return m.group(0)
        changed.append(1)
        r2, g2, b2 = oklch_to_rgb(*map_lch(L, C, H, text=text))
        return f"rgba({r2}, {g2}, {b2}, {a:g})"

    v = RGBA.sub(rgbas, HEX.sub(hexs, val))
    if prop.startswith("background") and re.search(r"(?<![\w-])white(?![\w-])", v):
        v = re.sub(r"(?<![\w-])white(?![\w-])", SURFACE, v)
        changed.append(1)
    return v if changed else None


def _blocks(css):
    i, out = 0, []
    while True:
        j = css.find("{", i)
        if j < 0:
            return out
        semi = css.find(";", i)
        if 0 <= semi < j and css[i:semi].strip().startswith("@"):
            i = semi + 1
            continue
        depth, k = 1, j + 1
        while depth and k < len(css):
            depth += {"{": 1, "}": -1}.get(css[k], 0)
            k += 1
        out.append((css[i:j].strip(), css[j + 1:k - 1]))
        i = k


def _split_top(sel):
    parts, depth, cur = [], 0, ""
    for ch in sel:
        depth += {"(": 1, ")": -1}.get(ch, 0)
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    return parts + [cur]


def _prefix(sel):
    out = []
    for s in (x.strip() for x in _split_top(sel)):
        if s.startswith(":root"):
            out.append(PFX + s[5:])
        elif re.match(r"html\b", s):
            out.append(PFX + s[4:])
        elif s.startswith("[dir"):
            out.append(PFX + s)
        elif s:
            out.append(PFX + " " + s)
    return ",\n".join(out)


def mirror(css):
    res = []
    for pre, body in _blocks(css):
        if pre.startswith(("@keyframes", "@theme", "@font-face")):
            continue
        if pre.startswith(("@media", "@supports")):
            inner = mirror(body)
            if inner:
                res.append(f"{pre} {{\n{inner}}}\n")
            continue
        if pre.startswith("@layer"):
            res.append(mirror(body))
            continue
        if pre.startswith("@"):
            continue
        decls = []
        for d in body.split(";"):
            if ":" not in d:
                continue
            p, v = (x.strip() for x in d.split(":", 1))
            if not p or p.startswith("--"):
                continue
            mv = map_value(p, v)
            if mv is not None:
                decls.append(f"  {p}: {mv};")
        if decls:
            res.append(_prefix(pre) + " {\n" + "\n".join(decls) + "\n}\n")
    return "".join(res)


def _esc(cls):
    return re.sub(r"([:/\[\]#.%(),])", r"\\\1", cls)


PSEUDO = {"hover": ":hover", "focus": ":focus", "focus-visible": ":focus-visible", "active": ":active"}
PROP = {"bg": "background-color", "text": "color", "border": "border-color"}


def class_rules(sources):
    """Template classes with a colour that no theme variable covers: bg-white, bg-[#hex], text-[#hex], overlays."""
    toks = set(re.findall(r"[A-Za-z0-9_:\-\[\]#/.%]+", sources))
    rules = []
    for c in sorted(toks):
        m = re.fullmatch(r"((?:[\w-]+:)*)(bg|text|border)-(white|\[#[0-9a-fA-F]{3,6}\]|slate-9\d\d)(?:/(\d+))?", c)
        if not m:
            continue
        variants = [v for v in m.group(1).split(":") if v]
        if any(v not in PSEUDO for v in variants):
            continue
        kind, color, alpha = m.group(2), m.group(3), m.group(4)
        if color == "white":
            if kind == "text":
                continue   # white text stays white
            value = SURFACE
        elif color.startswith("slate-9"):
            if kind != "bg" or not alpha:
                continue
            rules.append(f"{PFX} .{_esc(c)} {{ background-color: rgba(0, 0, 0, 0.55); }}")   # modal backdrop
            continue
        else:
            value = map_hex(color[1:-1], text=(kind == "text"))
        if alpha:
            r, g, b = _hexrgb(value)
            value = f"rgba({r}, {g}, {b}, {int(alpha) / 100:g})"
        sel = f"{PFX} .{_esc(c)}" + "".join(PSEUDO[v] for v in variants)
        rules.append(f"{sel} {{ {PROP[kind]}: {value}; }}")
    return "\n".join(rules) + "\n"


def theme_vars(style_css):
    theme = re.search(r"@theme\s*\{(.*?)\}", style_css, re.S).group(1)
    lines = []
    for name, val in re.findall(r"(--color-(?:slate|emerald)-\d+):\s*(#[0-9a-fA-F]{3,6})", theme):
        lines.append(f"  {name}: {map_hex(val)};")
    for name, val in TAILWIND.items():
        lines.append(f"  {name}: {map_oklch(val)};")
    return "\n".join(lines)


def build():
    with open(os.path.join(SRC, "style.css"), encoding="utf-8") as f:
        style = re.sub(r"/\*.*?\*/", "", f.read(), flags=re.S)
    sources = []
    for dirpath, _, files in os.walk(SRC):
        if os.path.basename(dirpath) == "locales":
            continue
        for fn in sorted(files):
            if fn.endswith((".vue", ".js")):
                with open(os.path.join(dirpath, fn), encoding="utf-8") as f:
                    sources.append(f.read())
    return (
        "/* Generated by panel/web/dark-theme.py from style.css and the templates; do not edit by hand. */\n"
        f"{PFX} {{\n  color-scheme: dark;\n  background: {PAGE_BG};\n{theme_vars(style)}\n}}\n"
        + class_rules("\n".join(sources))
        + mirror(style)
        + f"{PFX} body {{\n  background: {PAGE_BG};\n}}\n"
    )


if __name__ == "__main__":
    css = build()
    if "--check" in sys.argv:
        with open(OUT, encoding="utf-8") as f:
            sys.exit(0 if f.read() == css else 1)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(css)
    print(f"wrote {OUT}")
