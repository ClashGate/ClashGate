// Pure frontend validators and cert-path rewrite helpers.
// Behaviour is unchanged; tests/test_panel.py mirrors node-name and cert-path slices.
import { t } from '../i18n.js'

// CG_NODE_NAME: mirror of validate_node_name() in panel.py (tests/test_panel.py compares both).
const CG_NODE_NAME_MAX = 15
// Control characters, line/paragraph separators, zero-width and bidi-override characters.
const CG_NODE_NAME_BAD = /[\x00-\x1f\x7f-\x9f\u200b-\u200f\u2028-\u202e\u2060-\u2064\u2066-\u2069\ufeff]/
const CG_RESERVED_PROXY_NAMES = ['DIRECT', 'REJECT', 'REJECT-DROP', 'PASS', 'COMPATIBLE', 'GLOBAL']
function nodeNameError(raw) {
  const name = String(raw == null ? '' : raw).trim()
  if (!name) return t('本机名称不能为空')
  if (Array.from(name).length > CG_NODE_NAME_MAX) return t('本机名称最多 {n} 个字符', { n: CG_NODE_NAME_MAX })
  if (CG_NODE_NAME_BAD.test(name)) return t('本机名称不能包含换行、控制字符或不可见字符')
  if (CG_RESERVED_PROXY_NAMES.includes(name.toUpperCase())) return t('「{name}」是内核保留名称，请换一个', { name })
  return ''
}
// end node-name

function clusterUrlError(raw) {
  const s = String(raw || '').trim()
  if (!s) return t('请填写对方面板地址')
  if (/^http:\/\//i.test(s)) return t('面板地址必须以 https:// 开头')
  let u = null
  try {
    u = new URL(/^[a-z][a-z0-9+.-]*:\/\//i.test(s) ? s : `https://${s}`)
  } catch {
    u = null
  }
  if (!u || u.protocol !== 'https:' || !u.hostname || u.username || u.password) {
    return t('面板地址格式不对，例如 https://example.com:8443')
  }
  return ''
}

// Mirror of rewrite_cert_paths_in_yaml() in panel.py (keep in sync): point certificate /
// private-key file paths under top-level `listeners:` / `tls:` at this server's certs.
// Returns { text, changed } where changed counts paths that differ (relative ones included).
const CG_CERT_PATH = '/etc/clashgate/certs/fullchain.pem'
const CG_KEY_PATH = '/etc/clashgate/certs/privkey.pem'
function isCertPathValue(val) {
  const v = String(val || '').trim().replace(/^['"]|['"]$/g, '')
  if (!v || v[0] === '|' || v[0] === '>' || v.startsWith('-----') || /^[A-Za-z0-9+/]{42,43}=$/.test(v)) return false
  return /^(\/|\.\/|\.\.\/|~)/.test(v) || /\.(pem|crt|cer|key)$/i.test(v)
}
function fixCertPaths(raw) {
  const lines = String(raw || '').split(/\r?\n/)
  let top = ''
  let inReality = false
  let realityIndent = 0
  let changed = 0
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const stripped = line.replace(/^ +/, '')
    const indent = line.length - stripped.length
    if (!stripped || stripped.charAt(0) === '#') continue
    if (indent === 0 && stripped.charAt(0) !== '-') {
      // `- item` at column 0 stays in its section
      const mt = stripped.match(/^([A-Za-z0-9_-]+)\s*:/)
      top = mt ? mt[1] : ''
    }
    if (inReality && indent <= realityIndent) inReality = false
    if (/^(?:-\s+)?reality-config\s*:/.test(stripped)) {
      inReality = true
      realityIndent = indent
      continue
    }
    if ((top !== 'listeners' && top !== 'tls') || inReality) continue
    const m = stripped.match(/^((?:-\s+)?(certificate|private-key)\s*:\s*)([^#\n]+?)(\s*(?:#.*)?)$/)
    if (!m || !isCertPathValue(m[3])) continue
    const target = m[2] === 'certificate' ? CG_CERT_PATH : CG_KEY_PATH
    if (m[3].trim().replace(/^['"]|['"]$/g, '') !== target) {
      changed++
      lines[i] = line.slice(0, indent) + m[1] + target + (m[4] || '')
    }
  }
  return { text: lines.join('\n'), changed }
}

// end cert-path

const CLASSICAL_RULE_TYPES = new Set([
  'DOMAIN', 'DOMAIN-SUFFIX', 'DOMAIN-KEYWORD', 'DOMAIN-REGEX',
  'GEOSITE', 'GEOIP', 'IP-CIDR', 'IP-CIDR6', 'IP-ASN',
  'SRC-IP-CIDR', 'SRC-PORT', 'DST-PORT', 'PROCESS-NAME', 'PROCESS-PATH',
  'NETWORK', 'UID', 'IN-NAME', 'IN-TYPE',
])

function validateClassicalRulesPaste(rulesRaw) {
  const lines = String(rulesRaw || '').split(/\n/)
  const kept = []
  for (const rawLine of lines) {
    let line = rawLine.trim()
    if (!line || line.startsWith('#')) continue
    if (line.startsWith('- ')) line = line.slice(2).trim()
    else if (line.startsWith('-')) line = line.slice(1).trim()
    if (!line) continue
    const upper = line.toUpperCase()
    if (upper.startsWith('RULE-SET,')) {
      return { ok: false, msg: t('新建分流组请粘贴 DOMAIN / IP 等经典规则；外部分流规则集请用「引入外部分流」') }
    }
    if (upper.startsWith('MATCH,')) {
      return { ok: false, msg: t('MATCH 由系统自动生成，请勿粘贴') }
    }
    const parts = line.split(',').map((p) => p.trim()).filter((p, i, arr) => p || i < arr.length - 1)
    if (parts.length < 2) {
      return { ok: false, msg: t('规则格式无效：{line}（示例：- DOMAIN-SUFFIX,example.com）', { line: rawLine.trim() }) }
    }
    const rtype = parts[0].toUpperCase()
    if (!CLASSICAL_RULE_TYPES.has(rtype)) {
      return {
        ok: false,
        msg: t('不支持的规则类型「{type}」。请使用 DOMAIN-SUFFIX / DOMAIN-KEYWORD / IP-CIDR 等经典规则', { type: parts[0] }),
      }
    }
    kept.push(line)
  }
  if (!kept.length) {
    return { ok: false, msg: t('请至少粘贴一条分流规则（如 - DOMAIN-SUFFIX,example.com）') }
  }
  return { ok: true, lines: kept }
}

function validateHttpUrl(url) {
  const u = String(url || '').trim()
  if (!u) return { ok: false, msg: t('请填写外部规则集 URL') }
  if (!/^https?:\/\//i.test(u)) return { ok: false, msg: t('外部规则集 URL 必须以 http(s):// 开头') }
  try {
    const parsed = new URL(u)
    if (!parsed.hostname) return { ok: false, msg: t('外部规则集 URL 无效') }
  } catch {
    return { ok: false, msg: t('外部规则集 URL 无效') }
  }
  return { ok: true }
}


export {
  CG_NODE_NAME_MAX,
  CG_NODE_NAME_BAD,
  CG_RESERVED_PROXY_NAMES,
  nodeNameError,
  clusterUrlError,
  CG_CERT_PATH,
  CG_KEY_PATH,
  isCertPathValue,
  fixCertPaths,
  CLASSICAL_RULE_TYPES,
  validateClassicalRulesPaste,
  validateHttpUrl,
}
