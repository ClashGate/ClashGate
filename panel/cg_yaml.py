"""Mihomo YAML read/write helpers. Moved out of panel.py unchanged."""
import json
import re

STR_KEYS = {
    "name", "type", "server", "uuid", "password", "psk", "public-key", "private-key",
    "short-id", "servername", "sni", "cipher", "flow", "client-fingerprint",
    "username", "network", "path", "host", "mode", "plugin", "obfs", "fingerprint",
    "network-name", "network-secret", "state-dir", "control-url", "auth-key", "hostname",
    "key", "aead-method", "table-type", "congestion-controller", "udp-relay-mode",
    "decryption", "encryption", "ws-path", "grpc-service-name", "transport", "uri",
}

# ---------------------------------------------------------------- YAML / JSON proxy parser & serializer
def strip_yaml_comment(s: str) -> str:
    in_sq = in_dq = escaped = False
    for i, ch in enumerate(s):
        if escaped:
            escaped = False
            continue
        if ch == "\\" and in_dq:
            escaped = True
            continue
        if ch == "'" and not in_dq:
            in_sq = not in_sq
        elif ch == '"' and not in_sq:
            in_dq = not in_dq
        elif ch == "#" and not in_sq and not in_dq:
            if i == 0 or s[i - 1].isspace():
                return s[:i].rstrip()
    return s.rstrip()


def split_kv(line: str):
    in_sq = in_dq = escaped = False
    for i, ch in enumerate(line):
        if escaped:
            escaped = False
            continue
        if ch == "\\" and in_dq:
            escaped = True
            continue
        if ch == "'" and not in_dq:
            in_sq = not in_sq
        elif ch == '"' and not in_sq:
            in_dq = not in_dq
        elif ch == ":" and not in_sq and not in_dq:
            if i + 1 == len(line) or line[i + 1].isspace() or line[i + 1] in ('"', "'", "[", "{"):
                k = line[:i].strip()
                if (k.startswith('"') and k.endswith('"')) or (k.startswith("'") and k.endswith("'")):
                    k = k[1:-1]
                return k, ":", line[i + 1:].strip()
    return line, "", ""


def parse_scalar(val: str, key: str = ""):
    val = val.strip()
    if not val:
        return ""
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        if val.startswith('"'):
            try:
                return json.loads(val)
            except Exception:
                return val[1:-1]
        return val[1:-1].replace("''", "'")
    low = val.lower()
    if key not in STR_KEYS:
        if low == "true":
            return True
        if low == "false":
            return False
        if low in ("null", "~"):
            return None
        if re.fullmatch(r"-?(?:0|[1-9]\d*)", val):
            return int(val)
        if re.fullmatch(r"-?\d+\.\d+", val):
            return float(val)
    return val


def split_flow(s: str, sep: str = ",") -> list:
    parts, buf = [], []
    depth_c = depth_b = 0
    in_sq = in_dq = escaped = False
    for ch in s:
        if escaped:
            buf.append(ch)
            escaped = False
            continue
        if ch == "\\" and in_dq:
            buf.append(ch)
            escaped = True
            continue
        if ch == "'" and not in_dq:
            in_sq = not in_sq
        elif ch == '"' and not in_sq:
            in_dq = not in_dq
        elif not in_sq and not in_dq:
            if ch == "{":
                depth_c += 1
            elif ch == "}":
                depth_c -= 1
            elif ch == "[":
                depth_b += 1
            elif ch == "]":
                depth_b -= 1
            elif ch == sep and depth_c == 0 and depth_b == 0:
                parts.append("".join(buf).strip())
                buf = []
                continue
        buf.append(ch)
    if buf or s.endswith(sep):
        parts.append("".join(buf).strip())
    return [p for p in parts if p != ""]


def parse_flow_val(val: str, key: str = ""):
    val = val.strip()
    if val.startswith("{") and val.endswith("}"):
        try:
            obj = json.loads(val)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
        inner = val[1:-1].strip()
        if not inner:
            return {}
        out = {}
        for item in split_flow(inner, ","):
            if not item:
                continue
            k, sep, v = split_kv(item)
            if not sep:
                raise ValueError(f"无法解析字段：{item}")
            out[k] = parse_flow_val(v, k)
        return out
    if val.startswith("[") and val.endswith("]"):
        try:
            arr = json.loads(val)
            if isinstance(arr, list):
                return arr
        except Exception:
            pass
        inner = val[1:-1].strip()
        if not inner:
            return []
        return [parse_flow_val(x, key) for x in split_flow(inner, ",") if x != ""]
    return parse_scalar(val, key)


def parse_yaml_lines(lines: list, idx: int = 0, min_indent: int = 0):
    if idx >= len(lines):
        return None, idx
    ind0, txt0 = lines[idx]
    if ind0 < min_indent:
        return None, idx
    if txt0 == "-" or txt0.startswith("- "):
        arr = []
        seq_indent = ind0
        while idx < len(lines):
            ind, txt = lines[idx]
            if ind < seq_indent or not (txt == "-" or txt.startswith("- ")):
                break
            if ind != seq_indent:
                raise ValueError(f"YAML 列表缩进不一致：{txt}")
            rest = txt[1:].strip()
            idx += 1
            if not rest:
                sub, idx = parse_yaml_lines(lines, idx, seq_indent + 1)
                arr.append(sub)
            elif rest.startswith("{") and rest.endswith("}"):
                arr.append(parse_flow_val(rest))
            else:
                k, sep, v = split_kv(rest)
                if sep:
                    item_indent = ind + 2
                    virtual = [(item_indent, rest)]
                    while idx < len(lines) and lines[idx][0] >= item_indent:
                        virtual.append(lines[idx])
                        idx += 1
                    sub, _ = parse_yaml_lines(virtual, 0, item_indent)
                    arr.append(sub)
                else:
                    arr.append(parse_flow_val(rest))
        return arr, idx
    else:
        mapping = {}
        map_indent = ind0
        while idx < len(lines):
            ind, txt = lines[idx]
            if ind < map_indent:
                break
            if txt == "-" or txt.startswith("- "):
                break
            if ind != map_indent:
                raise ValueError(f"YAML 映射缩进不一致：{txt}")
            k, sep, v = split_kv(txt)
            if not sep:
                raise ValueError(f"无效的 YAML 行：{txt}")
            idx += 1
            if v in ("|", "|-", "|+", ">", ">-", ">+"):
                blk = []
                blk_indent = None
                while idx < len(lines) and lines[idx][0] > map_indent:
                    b_ind, b_txt = lines[idx]
                    if blk_indent is None:
                        blk_indent = b_ind
                    pad = " " * max(0, b_ind - blk_indent)
                    blk.append(pad + b_txt)
                    idx += 1
                mapping[k] = "\n".join(blk)
            elif v:
                mapping[k] = parse_flow_val(v, k)
            else:
                if idx < len(lines) and lines[idx][0] >= map_indent:
                    nxt_ind, nxt_txt = lines[idx]
                    if nxt_ind > map_indent or (nxt_ind == map_indent and (nxt_txt == "-" or nxt_txt.startswith("- "))):
                        sub, idx = parse_yaml_lines(lines, idx, map_indent)
                        mapping[k] = sub
                    else:
                        mapping[k] = ""
                else:
                    mapping[k] = ""
        return mapping, idx


def parse_mihomo_proxies(raw: str) -> list:
    """Parse single-line JSON/flow or multi-line YAML mihomo node configs; supports easytier/tailscale/etc."""
    s = (raw or "").strip()
    if not s:
        raise ValueError("请输入 Mihomo 节点配置（单行 JSON 或多行 YAML）")
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", s):
        raise ValueError("不支持分享链接（如 vless://、ss://），请粘贴 Mihomo 配置格式（JSON 或 YAML；订阅链接请在「外部订阅源」中导入）")
    parsed = None
    if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
        try:
            parsed = json.loads(s)
        except Exception:
            if "\n" not in s or (s.startswith("[") and s.endswith("]")):
                try:
                    parsed = parse_flow_val(s)
                except Exception:
                    parsed = None
    if parsed is None:
        lines = []
        for raw_line in s.splitlines():
            cleaned = strip_yaml_comment(raw_line.expandtabs(2))
            if not cleaned.strip():
                continue
            ind = len(cleaned) - len(cleaned.lstrip(" "))
            lines.append((ind, cleaned.strip()))
        if not lines:
            raise ValueError("节点配置为空")
        flow_candidates = []
        all_flow = True
        for _, txt in lines:
            t = txt[1:].strip() if (txt == "-" or txt.startswith("- ")) else txt
            if t.endswith(","):
                t = t[:-1].strip()
            if t.startswith("{") and t.endswith("}"):
                flow_candidates.append(t)
            else:
                all_flow = False
                break
        if all_flow and flow_candidates:
            parsed = [parse_flow_val(t) for t in flow_candidates]
        else:
            parsed, end_idx = parse_yaml_lines(lines, 0, 0)
            if end_idx < len(lines):
                raise ValueError(f"无法解析第 {end_idx + 1} 行附近的配置：{lines[end_idx][1]}")
    if isinstance(parsed, dict) and "proxies" in parsed and isinstance(parsed["proxies"], list):
        items = parsed["proxies"]
    elif isinstance(parsed, dict):
        items = [parsed]
    elif isinstance(parsed, list):
        items = parsed
    else:
        raise ValueError("仅支持 Mihomo 节点配置格式（单行 JSON 或多行 YAML）")
    if not items:
        raise ValueError("未找到任何节点配置")
    out = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("每个节点必须是键值对对象（需包含 name 与 type）")
        node = dict(item)
        for req in ("name", "type"):
            if req not in node or node[req] in ("", None):
                raise ValueError(f"节点缺少必填字段：{req}")
        node["name"] = str(node["name"]).strip()
        node["type"] = str(node["type"]).strip()
        if "server" in node and node["server"] not in ("", None):
            node["server"] = str(node["server"]).strip()
        if "port" in node and node["port"] not in ("", None):
            try:
                port = int(node["port"])
                if not 1 <= port <= 65535:
                    raise ValueError()
                node["port"] = port
            except Exception:
                nm, pt = node["name"], node["port"]
                raise ValueError(f"节点「{nm}」端口无效：{pt}")
        for k in list(node.keys()):
            if k in STR_KEYS and node[k] is not None and not isinstance(node[k], (dict, list)):
                node[k] = str(node[k])
        if "udp" not in node or node["udp"] is None:
            node["udp"] = True
        out.append(node)
    return out


_YAML_NON_STRING = re.compile(
    r"[-+]?(?:\d[\d_]*(?:\.[\d_]*)?(?:[eE][-+]?\d+)?|\.\d[\d_]*(?:[eE][-+]?\d+)?"
    r"|0[xX][0-9a-fA-F_]+|0[oO][0-7_]+|0[bB][01_]+|\.(?:inf|Inf|INF)|\d+(?::[0-5]?\d)+(?:\.\d*)?)"
    r"|\.(?:nan|NaN|NAN)")


def yaml_scalar(v, key: str = "") -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return "null"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if s == "":
        return '""'
    if (key in STR_KEYS and re.fullmatch(r"0\d+|-?\d+(\.\d+)?", s)) or s.lower() in (
        "true", "false", "null", "yes", "no", "on", "off", "~", "y", "n"
    ):
        return json.dumps(s, ensure_ascii=False)
    # A string a YAML reader would take as a number (1e5, 0x1f, 0o17, .inf, 1:30 ...) stays a string:
    # the same value written as one JSON line before 1.41 was always a string.
    if isinstance(v, str) and _YAML_NON_STRING.fullmatch(s):
        return json.dumps(s, ensure_ascii=False)
    # Plain only for safe text; `@` and backtick are reserved as a first character.
    if re.fullmatch(r"[A-Za-z0-9_./][A-Za-z0-9._/+@-]*", s):
        return s
    return json.dumps(s, ensure_ascii=False)


def dump_yaml_map(d: dict, indent: int = 4, first_dash: bool = False) -> list:
    priority = ("name", "type", "server", "port")
    keys = [k for k in priority if k in d] + [k for k in d if k not in priority]
    lines = []
    for idx, k in enumerate(keys):
        v = d[k]
        prefix = (" " * (indent - 2) + "- ") if (idx == 0 and first_dash) else (" " * indent)
        ks = k if re.fullmatch(r"[A-Za-z0-9._-]+", str(k)) else json.dumps(str(k), ensure_ascii=False)
        if isinstance(v, dict):
            if not v:
                lines.append(f"{prefix}{ks}: {{}}")
            else:
                lines.append(f"{prefix}{ks}:")
                lines.extend(dump_yaml_map(v, indent + 2, False))
        elif isinstance(v, list):
            if not v:
                lines.append(f"{prefix}{ks}: []")
            else:
                lines.append(f"{prefix}{ks}:")
                for elem in v:
                    if isinstance(elem, dict) and elem:
                        lines.extend(dump_yaml_map(elem, indent + 4, True))
                    elif isinstance(elem, (dict, list)):   # {} or a nested list: flow form
                        lines.append(" " * (indent + 2) + "- " + json.dumps(elem, ensure_ascii=False))
                    else:
                        lines.append(" " * (indent + 2) + "- " + yaml_scalar(elem, k))
        else:
            lines.append(f"{prefix}{ks}: {yaml_scalar(v, k)}")
    return lines


def dump_yaml_proxies(proxies: list) -> str:
    """Render a list of proxy dicts as multi-line YAML items (2-space indented `- `)."""
    lines = []
    for p in proxies:
        lines.extend(dump_yaml_map(p, indent=4, first_dash=True))
    return "\n".join(lines) + ("\n" if lines else "")


def expand_flow_items(raw: str, sections=None) -> str:
    """1.41: rewrite `  - {"name": ...}` list items (one JSON object per line, how listeners and the
    cluster entries were written before) as multi-line YAML, in the given top-level sections (None:
    every line, for a fragment). Everything else stays byte for byte."""
    out, sec = [], None
    for line in (raw or "").splitlines(keepends=True):
        s = line.rstrip("\r\n")
        if s and s[0] not in " \t-#":
            m = re.match(r"([A-Za-z0-9_-]+)\s*:", s)
            sec = m.group(1) if m else None
        m = re.fullmatch(r"( *)- (\{.*\})\s*", s)
        if m and (sections is None or sec in sections):
            try:
                obj = json.loads(m.group(2))
            except ValueError:
                obj = None
            if isinstance(obj, dict) and obj:
                out.append("\n".join(dump_yaml_map(obj, indent=len(m.group(1)) + 2, first_dash=True)) + "\n")
                continue
        out.append(line)
    return "".join(out)


def dump_yaml_providers(providers: dict) -> str:
    """Render proxy-providers dict as 2-space indented YAML mapping entries."""
    lines = []
    for name, cfg in providers.items():
        ks = name if re.fullmatch(r"[A-Za-z0-9._-]+", str(name)) else json.dumps(str(name), ensure_ascii=False)
        lines.append(f"  {ks}:")
        lines.extend(dump_yaml_map(cfg, indent=4, first_dash=False))
    return "\n".join(lines) + ("\n" if lines else "")


def build_proxy_provider(url: str, name: str = "", existing: dict = None) -> tuple:
    """Build a proxy-provider entry matching the 0.5 requirement structure."""
    u = (url or "").strip()
    if not re.match(r"^https?://\S+$", u):
        raise ValueError("请输入有效的 HTTP/HTTPS 订阅链接")
    raw_name = (name or "").strip()
    if not raw_name or raw_name.lower() == "default":
        # Note: Mihomo kernel forbids naming a proxy-provider literally 'default'
        # ("can not defined a provider called `default`"), while path ./default.yaml is valid.
        prov_name = "default-sub" if (existing and "sub" in existing and "default-sub" not in existing) else "sub"
        if raw_name.lower() == "default":
            prov_name = "default-sub"
        path = "./default.yaml" if not existing else f"./{prov_name}.yaml"
    else:
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,48}", raw_name):
            raise ValueError("订阅源名称仅限 1-48 位字母、数字及 . _ -")
        prov_name = raw_name
        path = f"./{prov_name}.yaml"
    if existing and prov_name in existing:
        raise ValueError(f"订阅源「{prov_name}」已存在，请换一个名称或先删除原订阅源")
    entry = {
        "type": "http",
        "url": u,
        "path": path,
        "interval": 3600,
        "proxy": "DIRECT",
        "health-check": {
            "enable": True,
            "url": "https://www.gstatic.com/generate_204",
            "interval": 300,
            "timeout": 5000,
            "lazy": True,
        },
    }
    return prov_name, entry

