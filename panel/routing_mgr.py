"""ClashGate 1.07 server-side routing (服务端分流).

Groups live as separate YAML files under /etc/clashgate/routing/, indexed by
routing.json. Assemble merges them into rule-providers / proxy-groups / rules
fragments substituted into server.yaml.tpl.

User-pasted classical rules (DOMAIN/IP/…) that target the group itself are
emitted as routing/<id>.rules.yaml (payload) + a type:file rule-provider and
a single RULE-SET line in main rules — not inlined one-by-one into config.yaml.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import urllib.error
import urllib.request


BUILTIN_ALWAYS_RULES_HEAD = [
    "DOMAIN,api64.ipify.org,DIRECT",
]
BUILTIN_PRIVATE_RULE = "GEOIP,private,DIRECT,no-resolve"

ROLE_SELECT = "select"
ROLE_POLICY = "policy"
ROLE_FINAL = "final"

_SAFE_ID = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,47}$")
_SAFE_NAME = re.compile(r"^[\w\u4e00-\u9fff .+\-🎯🚀🐟🤖📱🇨🇳⭐️⛅️]{1,64}$", re.UNICODE)



_CLASSICAL_TYPES = {
    "DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD", "DOMAIN-REGEX",
    "GEOSITE", "GEOIP", "IP-CIDR", "IP-CIDR6", "IP-ASN",
    "SRC-IP-CIDR", "SRC-PORT", "DST-PORT", "PROCESS-NAME", "PROCESS-PATH",
    "NETWORK", "UID", "IN-NAME", "IN-TYPE",
}


def parse_classical_rules_raw(rules_raw: str, group_name: str) -> list:
    """Parse beginner-pasted classical rule lines into Clash rule strings.

    Accepts lines like:
      - DOMAIN-SUFFIX,example.com
      DOMAIN-SUFFIX,example.com,SomeGroup
      DOMAIN-KEYWORD,foo
    Empty / comment lines are skipped. Missing proxy target gets group_name.
    RULE-SET / MATCH are rejected here (use import / system groups).
    """
    out = []
    for raw_line in (rules_raw or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("- "):
            line = line[2:].strip()
        elif line.startswith("-"):
            line = line[1:].strip()
        if not line:
            continue
        upper = line.upper()
        if upper.startswith("RULE-SET,"):
            raise ValueError("新建分流组请粘贴 DOMAIN / IP 等经典规则；外部分流规则集请用「引入外部分流」")
        if upper.startswith("MATCH,"):
            raise ValueError("MATCH 由系统自动生成，请勿粘贴")
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2:
            raise ValueError(f"规则格式无效：{raw_line.strip()}（示例：- DOMAIN-SUFFIX,example.com）")
        rtype = parts[0].upper()
        if rtype not in _CLASSICAL_TYPES:
            raise ValueError(
                f"不支持的规则类型「{parts[0]}」。请使用 DOMAIN-SUFFIX / DOMAIN-KEYWORD / IP-CIDR 等经典规则"
            )
        # Already has no-resolve + target
        if parts[-1] == "no-resolve" and len(parts) >= 3:
            target = parts[-2].strip('"')
            if target != group_name:
                parts[-2] = group_name
            out.append(",".join(parts))
            continue
        # Has a proxy-looking last field (not a pure matcher value for GEOIP etc.)
        # Classical forms: TYPE,value[,target][,no-resolve]
        if len(parts) >= 3 and parts[-1] != "no-resolve":
            # treat last as target
            parts[-1] = group_name
            out.append(",".join(parts))
            continue
        if len(parts) == 2:
            out.append(f"{parts[0]},{parts[1]},{group_name}")
            continue
        # TYPE,value,no-resolve
        if len(parts) == 3 and parts[-1] == "no-resolve":
            out.append(f"{parts[0]},{parts[1]},{group_name},no-resolve")
            continue
        out.append(",".join(parts[:-1] + [group_name]) if len(parts) > 2 else f"{line},{group_name}")
    if not out:
        raise ValueError("请至少粘贴一条分流规则（如 - DOMAIN-SUFFIX,example.com）")
    return out


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "-", (name or "").strip()).strip("-").lower()
    if not s:
        s = "group"
    if not re.match(r"^[a-zA-Z]", s):
        s = "g-" + s
    return s[:48]


class RoutingManager:
    def __init__(
        self,
        *,
        routing_json: str,
        routing_dir: str,
        frag_rule_providers: str,
        frag_proxy_groups: str,
        frag_rules: str,
        seed_dir: str,
        parse_yaml_document,
        dump_yaml_map,
        yaml_scalar,
        atomic_write,
        extract_top_level_yaml_section,
        replace_top_level_yaml_section,
    ):
        self.routing_json = routing_json
        self.routing_dir = routing_dir
        self.frag_rule_providers = frag_rule_providers
        self.frag_proxy_groups = frag_proxy_groups
        self.frag_rules = frag_rules
        self.seed_dir = seed_dir
        self.parse_yaml_document = parse_yaml_document
        self.dump_yaml_map = dump_yaml_map
        self.yaml_scalar = yaml_scalar
        self.atomic_write = atomic_write
        self.extract_top_level_yaml_section = extract_top_level_yaml_section
        self.replace_top_level_yaml_section = replace_top_level_yaml_section

    # ----- seed / load / save -------------------------------------------------

    def seed_path(self, name: str) -> str:
        return os.path.join(self.seed_dir, name)

    def group_path(self, filename: str) -> str:
        return os.path.join(self.routing_dir, filename)

    def default_meta(self) -> dict:
        path = self.seed_path("defaults.json")
        with open(path) as f:
            return json.load(f)

    def ensure_seeded(self, force: bool = False) -> dict:
        """Copy English defaults into /etc/clashgate/routing if missing (or force)."""
        os.makedirs(self.routing_dir, mode=0o755, exist_ok=True)
        if force or not os.path.isfile(self.routing_json):
            meta = self.default_meta()
            for g in meta.get("groups") or []:
                src = self.seed_path(g["file"])
                dst = self.group_path(g["file"])
                if force or not os.path.isfile(dst):
                    shutil.copyfile(src, dst)
                    os.chmod(dst, 0o640)
            self.atomic_write(self.routing_json, json.dumps(meta, indent=2, ensure_ascii=False) + "\n", 0o600)
            self.regenerate_frags()
            return meta
        # Ensure every declared file exists; regenerate frags if any fragment missing.
        meta = self._read_meta_raw()
        changed = False
        for g in meta.get("groups") or []:
            dst = self.group_path(g["file"])
            if not os.path.isfile(dst):
                src = self.seed_path(g["file"])
                if os.path.isfile(src):
                    shutil.copyfile(src, dst)
                    os.chmod(dst, 0o640)
                    changed = True
        need_frags = (
            changed
            or not os.path.isfile(self.frag_rule_providers)
            or not os.path.isfile(self.frag_proxy_groups)
            or not os.path.isfile(self.frag_rules)
        )
        if need_frags:
            self.regenerate_frags(meta)
        return meta

    def load_meta(self) -> dict:
        if not os.path.isfile(self.routing_json):
            return self.ensure_seeded(force=False)
        with open(self.routing_json) as f:
            raw = json.load(f)
        if not isinstance(raw, dict) or not isinstance(raw.get("groups"), list):
            raise ValueError("routing.json 格式无效")
        return raw

    def _read_meta_raw(self) -> dict:
        with open(self.routing_json) as f:
            raw = json.load(f)
        if not isinstance(raw, dict) or not isinstance(raw.get("groups"), list):
            raise ValueError("routing.json 格式无效")
        return raw

    def save_meta(self, meta: dict):
        self.atomic_write(self.routing_json, json.dumps(meta, indent=2, ensure_ascii=False) + "\n", 0o600)

    def tracked_files(self) -> list:
        """Paths that participate in pending-reload baseline/discard."""
        out = [self.routing_json, self.frag_rule_providers, self.frag_proxy_groups, self.frag_rules]
        try:
            for name in os.listdir(self.routing_dir):
                if name.endswith((".yaml", ".yml")):
                    out.append(self.group_path(name))
        except FileNotFoundError:
            pass
        return out

    def is_tracked_path(self, path: str) -> bool:
        if path in (
            self.routing_json,
            self.frag_rule_providers,
            self.frag_proxy_groups,
            self.frag_rules,
        ):
            return True
        try:
            return os.path.commonpath([path, self.routing_dir]) == self.routing_dir and path.endswith(
                (".yaml", ".yml")
            )
        except ValueError:
            return False

    # ----- YAML group helpers -------------------------------------------------

    def read_group_raw(self, filename: str) -> str:
        with open(self.group_path(filename)) as f:
            return f.read()

    def write_group_raw(self, filename: str, raw: str):
        self.atomic_write(self.group_path(filename), raw if raw.endswith("\n") else raw + "\n", 0o640)

    def parse_group_doc(self, raw: str) -> dict:
        doc = self.parse_yaml_document(raw)
        if doc is None:
            return {"rule-providers": {}, "proxy-groups": [], "rules": []}
        if not isinstance(doc, dict):
            raise ValueError("分流 YAML 顶层必须是映射（rule-providers / proxy-groups / rules）")
        providers = doc.get("rule-providers") or {}
        groups = doc.get("proxy-groups")
        if groups is None and isinstance(doc.get("proxy-group"), dict):
            groups = [doc["proxy-group"]]
        if groups is None:
            groups = []
        if not isinstance(providers, dict):
            raise ValueError("rule-providers 必须是映射")
        if not isinstance(groups, list):
            raise ValueError("proxy-groups 必须是列表")
        rules = doc.get("rules") or []
        if not isinstance(rules, list):
            raise ValueError("rules 必须是列表")
        # Normalize rule entries to strings
        norm_rules = []
        for r in rules:
            if isinstance(r, str):
                norm_rules.append(r.strip())
            else:
                raise ValueError("rules 中的每条规则必须是字符串")
        for g in groups:
            if not isinstance(g, dict) or not g.get("name") or not g.get("type"):
                raise ValueError("proxy-groups 每项必须包含 name 与 type")
        for pname, pcfg in providers.items():
            if not isinstance(pcfg, dict):
                raise ValueError(f"rule-provider「{pname}」格式无效")
            if not pcfg.get("type"):
                raise ValueError(f"rule-provider「{pname}」缺少 type")
        return {"rule-providers": providers, "proxy-groups": groups, "rules": norm_rules}

    def dump_group_doc(self, doc: dict) -> str:
        lines = []
        providers = doc.get("rule-providers") or {}
        groups = doc.get("proxy-groups") or []
        rules = doc.get("rules") or []
        if providers:
            lines.append("rule-providers:")
            for name, cfg in providers.items():
                lines.append(f"  {self._key(name)}:")
                lines.extend(self.dump_yaml_map(cfg, indent=4, first_dash=False))
        if groups:
            if lines:
                lines.append("")
            lines.append("proxy-groups:")
            for g in groups:
                lines.extend(self.dump_yaml_map(g, indent=4, first_dash=True))
        if rules:
            if lines:
                lines.append("")
            lines.append("rules:")
            for r in rules:
                lines.append("  - " + self.yaml_scalar(r))
        return "\n".join(lines) + "\n"

    def _key(self, k: str) -> str:
        if re.fullmatch(r"[A-Za-z0-9._-]+", str(k)):
            return str(k)
        return json_dumps_str(str(k))

    def primary_group_name(self, doc: dict) -> str:
        groups = doc.get("proxy-groups") or []
        if not groups:
            raise ValueError("分流组缺少 proxy-groups")
        return str(groups[0]["name"])

    # ----- assemble fragments -------------------------------------------------

    def find_group(self, meta: dict, gid: str) -> dict | None:
        for g in meta.get("groups") or []:
            if g.get("id") == gid:
                return g
        return None

    def _rule_target(self, rule: str) -> str | None:
        parts = [p.strip() for p in str(rule).split(",")]
        if len(parts) < 2:
            return None
        if parts[-1] == "no-resolve" and len(parts) >= 3:
            return parts[-2].strip('"')
        return parts[-1].strip('"')

    def _strip_rule_target(self, rule: str, target: str) -> str:
        """Drop the proxy-group target so a classical rule-provider payload can use it."""
        parts = [p.strip() for p in str(rule).split(",")]
        if parts and parts[-1] == "no-resolve" and len(parts) >= 3 and parts[-2].strip('"') == target:
            return ",".join(parts[:-2] + ["no-resolve"])
        if len(parts) >= 2 and parts[-1].strip('"') == target:
            return ",".join(parts[:-1])
        return str(rule)

    def _file_provider_name(self, gid: str) -> str:
        return f"cg-file-{gid}"

    def _rules_payload_filename(self, gid: str) -> str:
        return f"{gid}.rules.yaml"

    def _write_classical_payload(self, filename: str, payload_rules: list):
        lines = ["payload:"]
        for r in payload_rules:
            lines.append("  - " + self.yaml_scalar(r))
        self.atomic_write(self.group_path(filename), "\n".join(lines) + "\n", 0o640)

    def _cleanup_generated_rule_files(self, keep_names: set):
        try:
            names = os.listdir(self.routing_dir)
        except FileNotFoundError:
            return
        for name in names:
            if not name.endswith(".rules.yaml"):
                continue
            if name in keep_names:
                continue
            try:
                os.remove(self.group_path(name))
            except OSError:
                pass

    def regenerate_frags(self, meta: dict = None) -> tuple[str, str, str]:
        """Assemble fragments.

        Classical DOMAIN/IP/… rules that target a group's own proxy name are
        written to routing/<id>.rules.yaml and introduced via a file
        rule-provider + RULE-SET (so main config.yaml stays short). Existing
        HTTP rule-providers (imported groups) and already-written RULE-SET
        lines are left unchanged.

        Edge case: a pasted rule whose target is a *different* proxy group
        (e.g. DIRECT) is kept inlined in main rules — safer than refusing the
        whole paste. Prefer putting only same-group classical rules in a group.
        """
        meta = meta or self.load_meta()
        providers: dict = {}
        proxy_groups: list = []
        policy_rules: list = []
        final_name = "🐟 漏网之鱼"
        select_name = "🚀 节点选择"
        generated_payloads: set = set()

        for g in meta.get("groups") or []:
            raw = self.read_group_raw(g["file"])
            doc = self.parse_group_doc(raw)
            # Sync stored name with YAML primary name
            try:
                gname = self.primary_group_name(doc)
            except ValueError:
                gname = g.get("name") or g["id"]
            g["name"] = gname
            for pname, pcfg in (doc.get("rule-providers") or {}).items():
                if pname in providers:
                    raise ValueError(f"rule-provider 名称冲突：{pname}")
                providers[pname] = pcfg
            for pg in doc.get("proxy-groups") or []:
                proxy_groups.append(pg)
            role = g.get("role") or ROLE_POLICY
            if role == ROLE_FINAL:
                final_name = gname
            elif role == ROLE_SELECT:
                select_name = gname

            own_classical: list = []
            passthrough: list = []
            for rule in doc.get("rules") or []:
                rs = str(rule).strip()
                if not rs:
                    continue
                upper = rs.upper()
                if role == ROLE_FINAL and upper.startswith("MATCH,"):
                    continue  # MATCH injected at end
                if upper.startswith("RULE-SET,"):
                    passthrough.append(rs)
                    continue
                if upper.startswith("MATCH,"):
                    passthrough.append(rs)
                    continue
                target = self._rule_target(rs)
                if role == ROLE_POLICY and target == gname:
                    own_classical.append(self._strip_rule_target(rs, gname))
                else:
                    # Foreign target (DIRECT / another group) or non-policy: keep inlined
                    passthrough.append(rs)

            if own_classical and role == ROLE_POLICY:
                gid = str(g.get("id") or _slugify(gname))
                pname = self._file_provider_name(gid)
                payload_file = self._rules_payload_filename(gid)
                if pname in providers:
                    raise ValueError(f"rule-provider 名称冲突：{pname}")
                self._write_classical_payload(payload_file, own_classical)
                generated_payloads.add(payload_file)
                # path relative to mihomo -d (/etc/clashgate)
                providers[pname] = {
                    "type": "file",
                    "behavior": "classical",
                    "path": f"./routing/{payload_file}",
                }
                policy_rules.append(f"RULE-SET,{pname},{gname}")
            policy_rules.extend(passthrough)

        self._cleanup_generated_rule_files(generated_payloads)

        rules = list(BUILTIN_ALWAYS_RULES_HEAD) + policy_rules
        rules.append(BUILTIN_PRIVATE_RULE)
        rules.append(f"MATCH,{final_name}")

        # Render fragments (with section headers for assemble substitution)
        if providers:
            rp_lines = ["rule-providers:"]
            for name, cfg in providers.items():
                rp_lines.append(f"  {self._key(name)}:")
                rp_lines.extend(self.dump_yaml_map(cfg, indent=4, first_dash=False))
            rp_block = "\n".join(rp_lines) + "\n"
        else:
            rp_block = ""

        if proxy_groups:
            pg_lines = ["proxy-groups:"]
            for pg in proxy_groups:
                pg_lines.extend(self.dump_yaml_map(pg, indent=4, first_dash=True))
            pg_block = "\n".join(pg_lines) + "\n"
        else:
            pg_block = "proxy-groups: []\n"

        ru_lines = ["rules:"]
        for r in rules:
            ru_lines.append("  - " + self.yaml_scalar(r))
        ru_block = "\n".join(ru_lines) + "\n"

        self.atomic_write(self.frag_rule_providers, rp_block, 0o640)
        self.atomic_write(self.frag_proxy_groups, pg_block, 0o640)
        self.atomic_write(self.frag_rules, ru_block, 0o640)
        # Persist any name sync
        self.save_meta(meta)
        return rp_block, pg_block, ru_block

    def read_frags(self) -> tuple[str, str, str]:
        self.ensure_seeded()
        def _read(p, default=""):
            try:
                with open(p) as f:
                    return f.read()
            except FileNotFoundError:
                return default
        return (
            _read(self.frag_rule_providers),
            _read(self.frag_proxy_groups),
            _read(self.frag_rules) or "rules:\n  - MATCH,Final\n",
        )

    # ----- public state for /api/state ----------------------------------------

    def public_state(self, custom_raw: str | None = None, custom_mode: bool = False) -> dict:
        if custom_mode:
            return self.public_state_from_custom(custom_raw or "")
        meta = self.ensure_seeded()
        groups = []
        for g in meta.get("groups") or []:
            if (g.get("role") or ROLE_POLICY) in (ROLE_SELECT, ROLE_FINAL):
                continue  # system groups are hidden from the beginner UI
            try:
                raw = self.read_group_raw(g["file"])
                doc = self.parse_group_doc(raw)
                err = ""
            except Exception as e:
                raw = ""
                try:
                    raw = self.read_group_raw(g["file"])
                except Exception:
                    pass
                doc = {"rule-providers": {}, "proxy-groups": [], "rules": []}
                err = str(e)
            gname = g.get("name") or g["id"]
            kind = self._infer_kind(g, doc) if not err else (g.get("kind") or "local")
            http_providers = [
                {
                    "name": str(pn),
                    "url": str((pc or {}).get("url") or ""),
                    "behavior": str((pc or {}).get("behavior") or "classical"),
                    "format": str((pc or {}).get("format") or "yaml"),
                    "type": str((pc or {}).get("type") or ""),
                }
                for pn, pc in (doc.get("rule-providers") or {}).items()
                if str((pc or {}).get("type") or "") == "http"
            ]
            classical = [] if err else self._classical_rules_for_ui(doc, gname)
            groups.append({
                "id": g["id"],
                "name": gname,
                "file": g["file"],
                "deletable": bool(g.get("deletable", True)),
                "role": g.get("role") or ROLE_POLICY,
                "kind": kind,
                "rule_providers_count": len(http_providers),
                "rule_providers": http_providers,
                "classical_rules": classical,
                "rules_count": len(classical) if kind == "local" else len(doc.get("rules") or []),
                "error": err,
            })
        return {
            "ok": True,
            "custom_mode": False,
            "groups": groups,
            "error": "",
        }

    def public_state_from_custom(self, raw: str) -> dict:
        try:
            providers = self.extract_top_level_yaml_section(raw, "rule-providers") or {}
            groups = self.extract_top_level_yaml_section(raw, "proxy-groups") or []
            rules = self.extract_top_level_yaml_section(raw, "rules") or []
            if not isinstance(providers, dict) or not isinstance(groups, list) or not isinstance(rules, list):
                raise ValueError("无法解析自定义配置中的 rule-providers / proxy-groups / rules")
        except Exception as e:
            return {
                "ok": False,
                "custom_mode": True,
                "groups": [],
                "error": f"自定义服务端分流无法解析：{e}",
            }
        # Present each proxy-group as a synthetic editable group (rules matched by group name)
        out_groups = []
        for idx, pg in enumerate(groups):
            if not isinstance(pg, dict) or not pg.get("name"):
                continue
            name = str(pg["name"])
            role = ROLE_POLICY
            deletable = True
            low = name.lower()
            if idx == 0 or "node select" in low or "节点选择" in name:
                role = ROLE_SELECT
                deletable = False
            if str(pg.get("type", "")).lower() == "select":
                # Final detection: referenced by MATCH
                for r in rules:
                    rs = str(r)
                    if rs.upper().startswith("MATCH,") and rs.split(",", 1)[-1].strip().strip('"') == name:
                        role = ROLE_FINAL
                        deletable = False
            gid = _slugify(name) or f"g{idx}"
            # Collect rules targeting this group (and providers referenced)
            own_rules = []
            for r in rules:
                rs = str(r)
                parts = [p.strip() for p in rs.split(",")]
                if len(parts) >= 2 and parts[-1].strip('"') == name and not rs.upper().startswith("GEOIP,PRIVATE"):
                    if not (rs.upper().startswith("DOMAIN,API64.IPIFY.ORG") or rs.upper().startswith("GEOIP,PRIVATE")):
                        own_rules.append(rs)
            # providers: include all for first policy group only to avoid dup; keep simple — attach none in custom view yaml builder
            doc = {"rule-providers": {}, "proxy-groups": [pg], "rules": [r for r in own_rules if not str(r).upper().startswith("MATCH,")]}
            if role == ROLE_SELECT and idx == 0:
                # Attach all rule-providers to a hidden bucket? Keep providers editable via first group's yaml in custom is messy.
                pass
            out_groups.append({
                "id": gid,
                "name": name,
                "file": f"{gid}.yaml",
                "deletable": deletable,
                "role": role,
                "yaml": self.dump_group_doc(doc),
                "rule_providers_count": 0,
                "rules_count": len(doc["rules"]),
                "error": "",
            })
        # Attach full rule-providers into a synthetic note on the state
        return {
            "ok": True,
            "custom_mode": True,
            "groups": out_groups,
            "rule_providers_yaml": self._dump_providers_only(providers),
            "rules_yaml": self._dump_rules_only([str(r) for r in rules]),
            "error": "",
        }

    def _dump_providers_only(self, providers: dict) -> str:
        if not providers:
            return ""
        lines = ["rule-providers:"]
        for name, cfg in providers.items():
            lines.append(f"  {self._key(name)}:")
            lines.extend(self.dump_yaml_map(cfg, indent=4, first_dash=False))
        return "\n".join(lines) + "\n"

    def _dump_rules_only(self, rules: list) -> str:
        lines = ["rules:"]
        for r in rules:
            lines.append("  - " + self.yaml_scalar(r))
        return "\n".join(lines) + "\n"

    # ----- mutations (template mode) ------------------------------------------

    def _validate_name(self, name: str):
        name = (name or "").strip()
        if not name:
            raise ValueError("分流组名称不能为空")
        if len(name) > 64:
            raise ValueError("分流组名称过长")
        return name

    def _unique_id(self, meta: dict, base: str) -> str:
        base = _slugify(base)
        ids = {g["id"] for g in meta["groups"]}
        if base not in ids:
            return base
        for i in range(2, 1000):
            cand = f"{base}-{i}"
            if cand not in ids:
                return cand
        return base + "-" + secrets.token_hex(3)

    def _unique_file(self, meta: dict, base: str) -> str:
        base = _slugify(base) + ".yaml"
        files = {g["file"] for g in meta["groups"]}
        if base not in files:
            return base
        stem = base[:-5]
        for i in range(2, 1000):
            cand = f"{stem}-{i}.yaml"
            if cand not in files:
                return cand
        return stem + "-" + secrets.token_hex(3) + ".yaml"

    def _insert_policy_group(self, meta: dict, name: str, doc: dict, kind: str = "local") -> dict:
        gid = self._unique_id(meta, name)
        filename = self._unique_file(meta, name)
        self.write_group_raw(filename, self.dump_group_doc(doc))
        groups = meta["groups"]
        final_idx = next((i for i, g in enumerate(groups) if g.get("role") == ROLE_FINAL), len(groups))
        entry = {
            "id": gid,
            "name": name,
            "file": filename,
            "deletable": True,
            "role": ROLE_POLICY,
            "kind": kind if kind in ("local", "external") else "local",
        }
        groups.insert(final_idx, entry)
        meta["groups"] = groups
        self.save_meta(meta)
        self.regenerate_frags(meta)
        return entry

    def _unique_provider_name(self, meta: dict, base: str) -> str:
        base = re.sub(r"[^A-Za-z0-9_.\-]+", "-", (base or "").strip()).strip("-")
        if not base or not re.match(r"^[A-Za-z]", base):
            base = _slugify(base or "rules")
        existing = set()
        for g in meta["groups"]:
            try:
                doc = self.parse_group_doc(self.read_group_raw(g["file"]))
            except Exception:
                continue
            existing.update((doc.get("rule-providers") or {}).keys())
        if base not in existing:
            return base
        for i in range(2, 1000):
            cand = f"{base}-{i}"
            if cand not in existing:
                return cand
        return base + "-" + secrets.token_hex(3)

    def add_group(self, name: str, yaml_raw: str = "", import_url: str = "", rules_raw: str = "") -> dict:
        """Create a local routing group from pasted classical rules (beginner path).

        Prefer rules_raw (DOMAIN-SUFFIX / IP-CIDR / …). Full yaml_raw is still
        accepted for advanced/compat callers but the panel no longer exposes it.
        import_url is ignored — use import_group().
        """
        del import_url
        meta = self.load_meta()
        name = self._validate_name(name)
        if any(g.get("name") == name for g in meta["groups"]):
            raise ValueError(f"分流组名称已存在：{name}")
        rules_raw = (rules_raw or "").strip()
        yaml_raw = (yaml_raw or "").strip()
        if rules_raw:
            classical = parse_classical_rules_raw(rules_raw, name)
            doc = {
                "rule-providers": {},
                "proxy-groups": [{
                    "name": name,
                    "type": "select",
                    "include-all": True,
                    "proxies": [self._select_name(meta), "DIRECT"],
                }],
                "rules": classical,
            }
            return self._insert_policy_group(meta, name, doc, kind="local")
        if not yaml_raw:
            raise ValueError("请粘贴至少一条分流规则（如 - DOMAIN-SUFFIX,example.com）")
        doc = self.parse_group_doc(yaml_raw)
        if doc["proxy-groups"]:
            doc["proxy-groups"][0]["name"] = name
        else:
            doc["proxy-groups"] = [{
                "name": name,
                "type": "select",
                "include-all": True,
                "proxies": [self._select_name(meta), "DIRECT"],
            }]
        doc["rules"] = [r for r in doc["rules"] if not str(r).upper().startswith("MATCH,")]
        return self._insert_policy_group(meta, name, doc, kind="local")

    def _select_name(self, meta: dict) -> str:
        for g in (meta or {}).get("groups") or []:
            if g.get("role") == ROLE_SELECT and g.get("name"):
                return str(g["name"])
        return "🚀 节点选择"

    def import_group(self, name: str, url: str = "", yaml_raw: str = "") -> dict:
        """Beginner import: wrap an external rule-provider URL as a new routing group.

        Does NOT download or parse remote YAML (typical rule lists are payload/classical
        files, not full proxy-groups documents).
        """
        del yaml_raw  # intentionally unused; no remote YAML / pasted YAML path
        meta = self.load_meta()
        name = self._validate_name(name)
        url = (url or "").strip()
        if not url:
            raise ValueError("请填写外部规则集 URL")
        if not re.match(r"^https?://", url):
            raise ValueError("外部规则集 URL 必须以 http(s):// 开头")
        if any(g.get("name") == name for g in meta["groups"]):
            raise ValueError(f"分流组名称已存在：{name}")
        pname = self._unique_provider_name(meta, name)
        doc = {
            "rule-providers": {
                pname: {
                    "type": "http",
                    "behavior": "classical",
                    "url": url,
                    "path": f"./ruleset/{pname}.yaml",
                    "interval": 86400,
                }
            },
            "proxy-groups": [{
                "name": name,
                "type": "select",
                "include-all": True,
                "proxies": [self._select_name(meta), "DIRECT"],
            }],
            "rules": [f"RULE-SET,{pname},{name}"],
        }
        return self._insert_policy_group(meta, name, doc, kind="external")

    def delete_group(self, gid: str) -> str:
        meta = self.load_meta()
        g = self.find_group(meta, gid)
        if not g:
            return ""
        if not g.get("deletable", True) or g.get("role") in (ROLE_SELECT, ROLE_FINAL):
            raise ValueError(f"分流组「{g.get('name')}」不可删除")
        path = self.group_path(g["file"])
        meta["groups"] = [x for x in meta["groups"] if x["id"] != gid]
        self.save_meta(meta)
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass
        self.regenerate_frags(meta)
        return g.get("name") or gid

    def rename_group(self, gid: str, new_name: str) -> tuple[str, str]:
        meta = self.load_meta()
        g = self.find_group(meta, gid)
        if not g:
            raise ValueError("分流组不存在")
        new_name = self._validate_name(new_name)
        old_name = g.get("name") or ""
        if new_name == old_name:
            return old_name, new_name
        if any(x.get("name") == new_name and x["id"] != gid for x in meta["groups"]):
            raise ValueError(f"分流组名称已存在：{new_name}")
        # Update this group's yaml
        doc = self.parse_group_doc(self.read_group_raw(g["file"]))
        for pg in doc["proxy-groups"]:
            if str(pg.get("name")) == old_name:
                pg["name"] = new_name
        doc["rules"] = [self._rewrite_rule_target(r, old_name, new_name) for r in doc["rules"]]
        self.write_group_raw(g["file"], self.dump_group_doc(doc))
        g["name"] = new_name
        # Rewrite references in other groups (proxies lists + rules)
        for other in meta["groups"]:
            if other["id"] == gid:
                continue
            odoc = self.parse_group_doc(self.read_group_raw(other["file"]))
            changed = False
            for pg in odoc["proxy-groups"]:
                proxies = pg.get("proxies")
                if isinstance(proxies, list):
                    new_proxies = [new_name if str(x) == old_name else x for x in proxies]
                    if new_proxies != proxies:
                        pg["proxies"] = new_proxies
                        changed = True
            new_rules = [self._rewrite_rule_target(r, old_name, new_name) for r in odoc["rules"]]
            if new_rules != odoc["rules"]:
                odoc["rules"] = new_rules
                changed = True
            if changed:
                self.write_group_raw(other["file"], self.dump_group_doc(odoc))
        self.save_meta(meta)
        self.regenerate_frags(meta)
        return old_name, new_name

    def _rewrite_rule_target(self, rule: str, old: str, new: str) -> str:
        parts = [p.strip() for p in str(rule).split(",")]
        if len(parts) >= 2 and parts[-1].strip('"') == old:
            parts[-1] = new
            return ",".join(parts)
        # no-resolve trailing
        if len(parts) >= 3 and parts[-1] == "no-resolve" and parts[-2].strip('"') == old:
            parts[-2] = new
            return ",".join(parts)
        return str(rule)

    def add_provider(self, gid: str, pname: str, url: str, behavior: str = "classical", fmt: str = "yaml") -> str:
        import re as _re
        meta = self.load_meta()
        g = self.find_group(meta, gid)
        if not g or g.get("role") in (ROLE_SELECT, ROLE_FINAL):
            raise ValueError("分流组不存在")
        pname = (pname or "").strip()
        if not _re.fullmatch(r"[A-Za-z0-9_.\-]{1,64}", pname):
            raise ValueError("规则集名称只能用英文字母、数字、- _ .")
        url = (url or "").strip()
        if not _re.match(r"^https?://", url):
            raise ValueError("规则集 URL 必须以 http(s):// 开头")
        if behavior not in ("classical", "domain", "ipcidr"):
            raise ValueError("规则类型无效")
        if fmt not in ("yaml", "text", "mrs"):
            raise ValueError("格式无效")
        for other in meta["groups"]:
            odoc = self.parse_group_doc(self.read_group_raw(other["file"]))
            if pname in (odoc.get("rule-providers") or {}):
                raise ValueError(f"规则集名称已存在：{pname}")
        doc = self.parse_group_doc(self.read_group_raw(g["file"]))
        ext = {"yaml": "yaml", "text": "list", "mrs": "mrs"}[fmt]
        cfg = {"type": "http", "behavior": behavior, "url": url, "path": f"./ruleset/{pname}.{ext}", "interval": 86400}
        if fmt != "yaml":
            cfg["format"] = fmt
        doc["rule-providers"][pname] = cfg
        gname = g.get("name") or gid
        doc["rules"].append(f"RULE-SET,{pname},{gname}")
        self.write_group_raw(g["file"], self.dump_group_doc(doc))
        self.regenerate_frags(meta)
        return gname

    def delete_provider(self, gid: str, pname: str) -> str:
        meta = self.load_meta()
        g = self.find_group(meta, gid)
        if not g or g.get("role") in (ROLE_SELECT, ROLE_FINAL):
            raise ValueError("分流组不存在")
        doc = self.parse_group_doc(self.read_group_raw(g["file"]))
        if pname not in doc["rule-providers"]:
            raise ValueError("规则集不存在")
        del doc["rule-providers"][pname]
        doc["rules"] = [r for r in doc["rules"] if not (r.upper().startswith("RULE-SET,") and r.split(",")[1].strip() == pname)]
        self.write_group_raw(g["file"], self.dump_group_doc(doc))
        self.regenerate_frags(meta)
        return g.get("name") or gid

    def reorder_groups(self, order: list) -> None:
        meta = self.load_meta()
        by_id = {g["id"]: g for g in meta["groups"]}
        policy_ids = {gid for gid, g in by_id.items() if g.get("role") not in (ROLE_SELECT, ROLE_FINAL)}
        order = [gid for gid in order if gid in by_id]
        if len(order) != len(set(order)) or not (set(order) == policy_ids or set(order) == set(by_id)):
            raise ValueError("分流顺序必须包含全部现有分流组")
        select = [g for g in meta["groups"] if g.get("role") == ROLE_SELECT]
        final = [g for g in meta["groups"] if g.get("role") == ROLE_FINAL]
        middle_ids = [gid for gid in order if by_id[gid].get("role") not in (ROLE_SELECT, ROLE_FINAL)]
        # Preserve select first / final last regardless of client order
        new_groups = list(select)
        for gid in middle_ids:
            new_groups.append(by_id[gid])
        # Any other non-select/non-final not listed? already checked set equality
        new_groups.extend(final)
        meta["groups"] = new_groups
        self.save_meta(meta)
        self.regenerate_frags(meta)

    def _infer_kind(self, g: dict, doc: dict) -> str:
        explicit = (g.get("kind") or "").strip()
        if explicit in ("local", "external"):
            return explicit
        providers = doc.get("rule-providers") or {}
        if any(str((pc or {}).get("type") or "") == "http" for pc in providers.values()):
            return "external"
        return "local"

    def _classical_rules_for_ui(self, doc: dict, gname: str) -> list:
        """Classical rules targeting this group, shown without the proxy target for editing."""
        out = []
        for rule in doc.get("rules") or []:
            rs = str(rule).strip()
            if not rs:
                continue
            upper = rs.upper()
            if upper.startswith("RULE-SET,") or upper.startswith("MATCH,"):
                continue
            target = self._rule_target(rs)
            if target == gname:
                out.append(self._strip_rule_target(rs, gname))
            else:
                # Keep foreign-target rules as-is so user can still see them
                out.append(rs)
        return out

    def update_group_rules(self, gid: str, rules_raw: str) -> str:
        """Replace a local group's classical rules from beginner paste text."""
        meta = self.load_meta()
        g = self.find_group(meta, gid)
        if not g or g.get("role") in (ROLE_SELECT, ROLE_FINAL):
            raise ValueError("分流组不存在")
        doc = self.parse_group_doc(self.read_group_raw(g["file"]))
        kind = self._infer_kind(g, doc)
        if kind != "local":
            raise ValueError("外部分流组请用规则集管理，不能粘贴经典规则")
        gname = g.get("name") or gid
        classical = parse_classical_rules_raw(rules_raw, gname)
        # Keep any RULE-SET lines that somehow exist; local groups normally have none
        keep = [r for r in (doc.get("rules") or []) if str(r).upper().startswith("RULE-SET,")]
        doc["rules"] = classical + keep
        doc["rule-providers"] = {}
        g["kind"] = "local"
        self.write_group_raw(g["file"], self.dump_group_doc(doc))
        self.save_meta(meta)
        self.regenerate_frags(meta)
        return gname

    def update_group_yaml(self, gid: str, yaml_raw: str) -> str:
        meta = self.load_meta()
        g = self.find_group(meta, gid)
        if not g:
            raise ValueError("分流组不存在")
        doc = self.parse_group_doc(yaml_raw)
        # Keep role constraints: select/final must keep a proxy-group; final may have MATCH in file but assembler ignores it
        if not doc["proxy-groups"]:
            raise ValueError("分流组必须包含 proxy-groups")
        # Force name to stay unless renamed via rename API — keep YAML primary name in sync with meta
        primary = self.primary_group_name(doc)
        # Allow yaml to rename only if not conflicting — simpler: force meta name into yaml
        expected = g.get("name")
        if primary != expected:
            doc["proxy-groups"][0]["name"] = expected
            doc["rules"] = [self._rewrite_rule_target(r, primary, expected) for r in doc["rules"]]
        if g.get("role") == ROLE_FINAL:
            doc["rules"] = [r for r in doc["rules"] if not str(r).upper().startswith("MATCH,")]
            doc["rules"].append(f"MATCH,{expected}")
        self.write_group_raw(g["file"], self.dump_group_doc(doc))
        self.regenerate_frags(meta)
        return expected

    def fetch_url(self, url: str) -> str:
        u = (url or "").strip()
        if not (u.startswith("https://") or u.startswith("http://")):
            raise ValueError("外部分流规则 URL 仅支持 http/https")
        req = urllib.request.Request(u, headers={"User-Agent": "ClashGate/1.07.6"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = resp.read(2_000_000)
        except urllib.error.URLError as e:
            raise ValueError(f"下载外部分流规则失败：{e}") from e
        text = data.decode("utf-8", "replace")
        # Validate parseable
        self.parse_group_doc(text)
        return text

    # ----- custom mode write-back ---------------------------------------------

    def apply_custom_routing_edit(self, custom_raw: str, groups_payload: list, rule_providers_yaml: str = "") -> str:
        """Rebuild rule-providers / proxy-groups / rules sections in a custom config string."""
        providers = {}
        if (rule_providers_yaml or "").strip():
            doc = self.parse_group_doc(
                rule_providers_yaml
                if "rule-providers:" in rule_providers_yaml
                else "rule-providers:\n" + rule_providers_yaml
            )
            # parse_group_doc expects full doc; if only providers, wrap
            providers = doc.get("rule-providers") or {}
        proxy_groups = []
        policy_rules = []
        final_name = None
        for g in groups_payload:
            doc = self.parse_group_doc(g.get("yaml") or "")
            for pname, pcfg in (doc.get("rule-providers") or {}).items():
                providers[pname] = pcfg
            for pg in doc.get("proxy-groups") or []:
                proxy_groups.append(pg)
            role = g.get("role") or ROLE_POLICY
            name = str((doc.get("proxy-groups") or [{}])[0].get("name") or g.get("name") or "")
            if role == ROLE_FINAL:
                final_name = name
            for r in doc.get("rules") or []:
                if str(r).upper().startswith("MATCH,"):
                    continue
                policy_rules.append(r)
        if not final_name and proxy_groups:
            final_name = str(proxy_groups[-1].get("name") or "🐟 漏网之鱼")
        rules = list(BUILTIN_ALWAYS_RULES_HEAD) + policy_rules
        rules.append(BUILTIN_PRIVATE_RULE)
        rules.append(f"MATCH,{final_name or '🐟 漏网之鱼'}")

        rp_block = self._dump_providers_only(providers)
        pg_lines = ["proxy-groups:"]
        for pg in proxy_groups:
            pg_lines.extend(self.dump_yaml_map(pg, indent=4, first_dash=True))
        pg_block = "\n".join(pg_lines) + "\n"
        ru_block = self._dump_rules_only(rules)

        updated = custom_raw
        updated = self.replace_top_level_yaml_section(updated, "rule-providers", rp_block)
        updated = self.replace_top_level_yaml_section(updated, "proxy-groups", pg_block)
        updated = self.replace_top_level_yaml_section(updated, "rules", ru_block)
        return updated


def json_dumps_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def parse_yaml_document_factory(parse_yaml_lines, strip_yaml_comment):
    def parse_yaml_document(raw: str):
        s = (raw or "").strip()
        if not s:
            return {}
        lines = []
        for raw_line in s.splitlines():
            cleaned = strip_yaml_comment(raw_line.expandtabs(2))
            if not cleaned.strip():
                continue
            ind = len(cleaned) - len(cleaned.lstrip(" "))
            lines.append((ind, cleaned.strip()))
        if not lines:
            return {}
        parsed, end_idx = parse_yaml_lines(lines, 0, 0)
        if end_idx < len(lines):
            raise ValueError(f"无法解析第 {end_idx + 1} 行附近：{lines[end_idx][1]}")
        return parsed

    return parse_yaml_document
