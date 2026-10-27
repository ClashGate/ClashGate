<script setup>
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'

const boot = window.__CS_BOOT__ || {
  page: 'dashboard',
  initial_tab: 'inbounds',
  version: '0.96',
  mihomo_version: '',
  csrf: '',
  login_error: '',
  flash_msg: '',
  flash_ok: true,
  sub_url: '',
  zb_url: '',
  mihomo_secret: '',
  srv_cfg_url: '/config/server.yaml',
  controller_port: 0,
  controller_listening: false,
  certs_present: true,
  custom_config_mode: false,
  custom_config_raw: '',
  status: {
    active: 'active',
    state_txt: '运行中',
    state_cls: 'ok',
    mihomo_version: '',
    inbound_total: 0,
    inbound_listening: 0,
    outbound_nodes_count: 0,
    outbound_providers_count: 0,
    cert_days: null,
    cert_hours: null,
    cert_expires: '',
    traffic_up_bytes: 0,
    traffic_down_bytes: 0,
    traffic_total_bytes: 0,
    traffic_total_gb: 0,
    traffic_display: '0.00 GB',
    traffic_detail: '↑ 0 B · ↓ 0 B',
  },
  inbounds: [],
  all_proxies_yaml: '',
  proxies: [],
  providers: [],
}

const pageMode = ref(boot.page || 'dashboard')
const state = reactive({
  version: boot.version || '0.96',
  mihomo_version: boot.mihomo_version || (boot.status && boot.status.mihomo_version) || '',
  csrf: boot.csrf || '',
  sub_url: boot.sub_url || '',
  zb_url: boot.zb_url || '',
  mihomo_secret: boot.mihomo_secret || '',
  srv_cfg_url: boot.srv_cfg_url || '/config/server.yaml',
  controller_port: boot.controller_port || 0,
  controller_listening: !!boot.controller_listening,
  certs_present: boot.certs_present !== false,
  custom_config_mode: !!boot.custom_config_mode,
  custom_config_raw: boot.custom_config_raw || '',
  status: { ...(boot.status || {}) },
  inbounds: Array.isArray(boot.inbounds) ? boot.inbounds : [],
  all_proxies_yaml: boot.all_proxies_yaml || '',
  proxies: Array.isArray(boot.proxies) ? boot.proxies : [],
  providers: Array.isArray(boot.providers) ? boot.providers : [],
})

const topbarVersionText = computed(() => {
  const mv = String(state.mihomo_version || (state.status && state.status.mihomo_version) || '').trim()
  return mv ? `v${state.version} · mihomo ${mv}` : `v${state.version}`
})

const VALID_TABS = ['inbounds', 'outbounds', 'readable', 'advanced']
const TAB_PATHS = {
  inbounds: '/',
  outbounds: '/outbounds',
  readable: '/readable',
  advanced: '/advanced',
}

function detectInitialTab() {
  if (boot.initial_tab && VALID_TABS.includes(boot.initial_tab)) {
    return boot.initial_tab
  }
  const p = window.location.pathname
  if (p === '/advanced' || p === '/custom-config') return 'advanced'
  if (p === '/readable' || p === '/convert') return 'readable'
  if (p === '/outbounds') return 'outbounds'
  return 'inbounds'
}

const activeTab = ref(detectInitialTab())
const busyKey = ref('')
const copiedKey = ref('')
const toast = reactive({ show: false, msg: '', ok: true })
let toastTimer = null

function showToast(msg, ok = true) {
  if (!msg) return
  toast.msg = msg
  toast.ok = ok
  toast.show = true
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toast.show = false
  }, 4500)
}

const PROTOCOLS = [
  {
    value: 'vless-reality',
    label: 'VLESS Reality',
    defaultName: 'VlessReality',
    desc: '免证书的新一代协议',
    lockedNote: '已锁定安全默认：默认启用 VLESS Encryption (vless-x25519)，SNI 从内置域名池随机抽取',
  },
  {
    value: 'hysteria2',
    label: 'Hysteria2',
    defaultName: 'Hysteria2',
    desc: '新一代 UDP 协议',
    lockedNote: '已锁定安全默认：混淆密码 (Salamander) 默认随机生成，不可手动关闭',
  },
  {
    value: 'shadowsocks',
    label: 'Shadowsocks',
    defaultName: 'Shadowsocks',
    desc: '经典轻量级加密协议，默认锁定 aes-256-gcm',
    lockedNote: '已锁定安全默认：加密算法固定为 aes-256-gcm，密码自动随机生成',
  },
  {
    value: 'snell',
    label: 'Snell V5',
    defaultName: 'SnellV5',
    desc: '轻量高效的私有协议，内置随机 TLS 伪装',
    lockedNote: '已锁定安全默认：混淆模式固定为 tls，伪装 Host 从内置池随机抽取',
  },
  {
    value: 'anytls',
    label: 'AnyTLS',
    defaultName: 'AnyTLS',
    desc: '内置随机填充与随机指纹的新一代 TLS 协议',
    lockedNote: '已锁定安全默认：客户端 TLS 指纹与长度填充策略均自动随机生成',
  },
  {
    value: 'shadowquic',
    label: 'ShadowQUIC',
    defaultName: 'ShadowQUIC',
    desc: '免证书的新一代 QUIC 协议，内置随机 JLS 伪装',
    lockedNote: '已锁定安全默认：伪装地址 (JLS) 从内置域名池随机抽取，拥塞控制默认 bbr',
  },
  {
    value: 'sudoku',
    label: 'Sudoku',
    defaultName: 'Sudoku',
    desc: '基于数独流量特征变换与 chacha20 加密的抗审查协议',
    lockedNote: '已锁定安全默认：AEAD 加密固定为 chacha20-poly1305，密钥对自动生成',
  },
  {
    value: 'tuic',
    label: 'TUIC v5',
    defaultName: 'TUICv5',
    desc: '基于 QUIC 的低延迟零握手机制 UDP 协议',
    lockedNote: '已启用安全默认：UUID 与密码随机生成，开启 0-RTT 与 native UDP 转发',
  },
  {
    value: 'trusttunnel',
    label: 'TrustTunnel',
    defaultName: 'TrustTunnel',
    desc: '基于标准 HTTP/2 与 HTTP/3 的高隐蔽 TLS 隧道协议',
    lockedNote: '已启用安全默认：强随机密码与 TLS 证书加密传输',
  },
  {
    value: 'mieru',
    label: 'Mieru',
    defaultName: 'Mieru',
    desc: '抗深度包检测（DPI）的混淆传输代理协议',
    lockedNote: '已启用安全默认：强随机密码与抗 DPI 流量混淆',
  },
  {
    value: 'http',
    label: 'HTTP',
    defaultName: 'HTTP',
    desc: '通用 HTTP / HTTPS 代理协议',
    lockedNote: '已启用安全默认：鉴权密码自动随机生成',
  },
  {
    value: 'socks',
    label: 'SOCKS5',
    defaultName: 'SOCKS5',
    desc: '通用 SOCKS5 代理协议，支持 UDP 转发',
    lockedNote: '已启用安全默认：鉴权密码自动随机生成，默认开启 UDP',
  },
]

const DEFAULT_NAMES = Object.fromEntries(PROTOCOLS.map((p) => [p.value, p.defaultName]))
const PROTOCOL_MAP = Object.fromEntries(PROTOCOLS.map((p) => [p.value, p]))

const inboundForm = reactive({
  kind: 'vless-reality',
  name: 'VlessReality',
  port: '',
  tuic_cc: 'bbr',
  tt_cc: 'bbr',
  mieru_transport: 'TCP',
  http_tls: '0',
  socks_tls: '0',
})

const currentProtocol = computed(() => PROTOCOL_MAP[inboundForm.kind] || PROTOCOLS[0])
const currentDefaultName = computed(() => DEFAULT_NAMES[inboundForm.kind] || 'VlessReality')

watch(
  () => inboundForm.kind,
  (newKind, oldKind) => {
    const oldDefault = DEFAULT_NAMES[oldKind] || ''
    const newDefault = DEFAULT_NAMES[newKind] || newKind
    if (!inboundForm.name.trim() || inboundForm.name.trim() === oldDefault) {
      inboundForm.name = newDefault
    }
  }
)

const providerForm = reactive({
  sub_url: '',
  provider_name: '',
})

const proxiesRaw = ref('')
const customConfigText = ref(state.custom_config_raw || '')

// Readable config converter state
const converterInput = ref('')
const converterOutput = ref('')
const converterError = ref('')

const trafficDisplay = computed(() => {
  const s = state.status || {}
  if (s.traffic_display) return s.traffic_display
  const gb = Number(s.traffic_total_gb || 0)
  return `${gb.toFixed(2)} GB`
})

const trafficDetail = computed(() => {
  const s = state.status || {}
  return s.traffic_detail || '↑ 0 B · ↓ 0 B'
})

async function updateCoreDirect() {
  if (busyKey.value) return
  busyKey.value = '/action/update-core'
  const body = new URLSearchParams({ csrf: state.csrf, async: '1' }).toString()
  try {
    const startRes = await fetch('/action/update-core', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-Requested-With': 'fetch',
        Accept: 'application/json',
      },
      body,
      credentials: 'same-origin',
      cache: 'no-store',
    })
    if (startRes.status === 401) {
      window.location.href = '/login'
      return
    }
    const startData = await startRes.json().catch(() => null)
    // If server finished synchronously (e.g. direct response with running === false)
    if (startData && startData.running === false) {
      if (startData.state) applyServerState(startData.state)
      showToast(startData.msg || (startData.ok ? '内核更新成功' : '更新内核失败'), !!startData.ok)
      return
    }
  } catch {
    // Even if starting the update blips the network, fall through to poll /api/update-core-status
  }

  const deadline = Date.now() + 180000
  while (Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, 1200))
    try {
      const pollRes = await fetch('/api/update-core-status', {
        headers: { Accept: 'application/json', 'X-Requested-With': 'fetch' },
        credentials: 'same-origin',
        cache: 'no-store',
      })
      if (pollRes.status === 401) {
        window.location.href = '/login'
        return
      }
      if (!pollRes.ok) continue
      const pollData = await pollRes.json()
      if (pollData && pollData.running === false) {
        if (pollData.state) applyServerState(pollData.state)
        showToast(pollData.msg || (pollData.ok ? '内核更新成功' : '更新内核失败'), !!pollData.ok)
        busyKey.value = ''
        return
      }
    } catch {
      // Transient connection drop while mihomo restarts — keep polling
    }
  }
  busyKey.value = ''
  showToast('更新内核等待超时，请刷新页面查看内核版本状态', false)
}

async function checkUpdateAndPrompt() {
  const res = await postAction('/action/check-update', {}, '/action/check-update')
  if (!res || !res.ok) return
  if (res.has_update) {
    const latest = res.latest_version || '最新版'
    const current = res.current_version || state.version
    if (window.confirm(`检测到新版本 v${latest}（当前版本 v${current}），是否立即升级？`)) {
      await postAction('/action/upgrade-self', {}, '/action/upgrade-self')
    }
  }
}

let statePollTimer = null

async function refreshServerStateSilent() {
  if (pageMode.value !== 'dashboard' || busyKey.value) return
  try {
    const res = await fetch('/api/state', {
      headers: { Accept: 'application/json', 'X-Requested-With': 'fetch' },
      credentials: 'same-origin',
      cache: 'no-store',
    })
    if (res.ok) {
      const data = await res.json()
      if (data) {
        if (data.mihomo_version) state.mihomo_version = data.mihomo_version
        if (data.status) {
          Object.assign(state.status, data.status)
          if (data.status.mihomo_version) state.mihomo_version = data.status.mihomo_version
        }
      }
    }
  } catch {}
}

function applyServerState(newState) {
  if (!newState) return
  if (newState.version) state.version = newState.version
  if (newState.mihomo_version) state.mihomo_version = newState.mihomo_version
  if (newState.csrf) state.csrf = newState.csrf
  if (newState.sub_url !== undefined) state.sub_url = newState.sub_url
  if (newState.zb_url !== undefined) state.zb_url = newState.zb_url
  if (newState.mihomo_secret !== undefined) state.mihomo_secret = newState.mihomo_secret
  if (newState.srv_cfg_url !== undefined) state.srv_cfg_url = newState.srv_cfg_url
  if (newState.controller_port !== undefined) state.controller_port = newState.controller_port
  if (newState.controller_listening !== undefined) state.controller_listening = newState.controller_listening
  if (newState.certs_present !== undefined) state.certs_present = newState.certs_present
  if (newState.custom_config_mode !== undefined) state.custom_config_mode = newState.custom_config_mode
  if (newState.custom_config_raw !== undefined) {
    state.custom_config_raw = newState.custom_config_raw
    customConfigText.value = newState.custom_config_raw
  }
  if (newState.status) {
    Object.assign(state.status, newState.status)
    if (newState.status.mihomo_version) state.mihomo_version = newState.status.mihomo_version
  }
  if (Array.isArray(newState.inbounds)) state.inbounds = newState.inbounds
  if (newState.all_proxies_yaml !== undefined) state.all_proxies_yaml = newState.all_proxies_yaml
  if (Array.isArray(newState.proxies)) state.proxies = newState.proxies
  if (Array.isArray(newState.providers)) state.providers = newState.providers
}

function formatFetchError(err) {
  const raw = String((err && err.message) || err || '')
  if (/NetworkError|Failed to fetch|Load failed|network/i.test(raw)) {
    return '网络连接中断或服务正在重启，请稍后刷新页面查看状态'
  }
  return `请求异常：${raw}`
}

async function postAction(url, params = {}, key = url) {
  if (busyKey.value) return null
  busyKey.value = key
  const body = new URLSearchParams({ csrf: state.csrf, ...params }).toString()
  const ctrl = window.AbortController ? new AbortController() : null
  const timer = ctrl ? setTimeout(() => ctrl.abort(), 120000) : null
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-Requested-With': 'fetch',
        Accept: 'application/json',
      },
      body,
      credentials: 'same-origin',
      cache: 'no-store',
      signal: ctrl ? ctrl.signal : undefined,
    })
    if (timer) clearTimeout(timer)
    if (res.status === 401) {
      window.location.href = '/login'
      return null
    }
    const text = await res.text()
    let data = null
    try {
      data = JSON.parse(text)
    } catch {
      data = { ok: res.ok, msg: text || `HTTP ${res.status}` }
    }
    if (data.state) {
      applyServerState(data.state)
    } else {
      if (data.zb_url) state.zb_url = data.zb_url
      if (data.sub_url) state.sub_url = data.sub_url
    }
    showToast(data.msg || (data.ok ? '操作成功' : '操作失败'), !!data.ok)
    return data
  } catch (err) {
    if (timer) clearTimeout(timer)
    if (err && err.name === 'AbortError') {
      showToast('请求超时（120s），请稍后刷新查看状态', false)
      return null
    }
    // If reload / restart momentarily dropped proxy connection, re-sync state via GET /api/state
    try {
      await new Promise((r) => setTimeout(r, 900))
      const stRes = await fetch('/api/state', {
        headers: { Accept: 'application/json', 'X-Requested-With': 'fetch' },
        credentials: 'same-origin',
        cache: 'no-store',
      })
      if (stRes.ok) {
        const stData = await stRes.json()
        applyServerState(stData)
        if (url === '/action/reload' || url === '/action/restart') {
          showToast('已重载配置并更新客户端订阅', true)
          return { ok: true, state: stData }
        }
      }
    } catch {}
    showToast(formatFetchError(err), false)
    return null
  } finally {
    busyKey.value = ''
  }
}

async function copyRaw(text, key) {
  if (!text) return
  const done = () => {
    copiedKey.value = key
    setTimeout(() => {
      if (copiedKey.value === key) copiedKey.value = ''
    }, 1600)
  }
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text)
      done()
      return
    }
  } catch {
    // fallback below
  }
  const ta = document.createElement('textarea')
  ta.value = text
  ta.style.position = 'fixed'
  ta.style.opacity = '0'
  document.body.appendChild(ta)
  ta.select()
  try {
    document.execCommand('copy')
    done()
  } catch {}
  document.body.removeChild(ta)
}

let pendingAddReqId = ''

async function submitAddInbound() {
  if (busyKey.value) return
  if (!pendingAddReqId) {
    pendingAddReqId = `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
  }
  const payload = {
    kind: inboundForm.kind,
    name: inboundForm.name.trim() || currentDefaultName.value,
    port: inboundForm.port.trim(),
    tuic_cc: inboundForm.tuic_cc,
    tt_cc: inboundForm.tt_cc,
    mieru_transport: inboundForm.mieru_transport,
    http_tls: inboundForm.http_tls,
    socks_tls: inboundForm.socks_tls,
    req_id: pendingAddReqId,
  }
  const res = await postAction('/inbounds/add', payload, 'add-inbound')
  pendingAddReqId = ''
  if (res && res.ok) {
    inboundForm.port = ''
    inboundForm.name = currentDefaultName.value
  }
}

async function resetInboundPassword(item) {
  if (!item.reset_url) return
  await postAction(item.reset_url, {}, `rst-${item.key}`)
}

async function deleteInbound(item) {
  await postAction(item.delete_url, {}, `del-${item.key}`)
}

async function resetSubUrl() {
  if (!window.confirm('确定更换订阅链接？更换后原订阅链接将立即失效。')) return
  await postAction('/action/reset-sub', {}, 'reset-sub')
}

async function resetZbSecret() {
  if (!window.confirm('确定重置 Zashboard API 密钥？重置后直连地址将同步更新。')) return
  await postAction('/action/reset-secret', {}, 'reset-secret')
}

async function submitAddProvider() {
  if (!providerForm.sub_url.trim()) return
  const res = await postAction(
    '/providers/add',
    {
      sub_url: providerForm.sub_url.trim(),
      provider_name: providerForm.provider_name.trim(),
    },
    'add-provider'
  )
  if (res && res.ok) {
    providerForm.sub_url = ''
    providerForm.provider_name = ''
  }
}

async function deleteProvider(name) {
  if (!window.confirm(`确定删除订阅源「${name}」？`)) return
  await postAction('/providers/delete', { name }, `del-prov-${name}`)
}

async function submitAddProxies() {
  if (!proxiesRaw.value.trim()) return
  const res = await postAction('/proxies/add', { proxies_raw: proxiesRaw.value }, 'add-proxies')
  if (res && res.ok) {
    proxiesRaw.value = ''
  }
}

async function deleteProxy(name) {
  if (!window.confirm(`确定删除出站节点「${name}」？`)) return
  await postAction('/proxies/delete', { name }, `del-proxy-${name}`)
}

function loadFileInto(ev, targetRef) {
  const f = ev.target.files && ev.target.files[0]
  if (!f) return
  const r = new FileReader()
  r.onload = () => {
    targetRef.value = r.result || ''
  }
  r.readAsText(f)
  ev.target.value = ''
}

function fillCurrentInboundsToConverter() {
  if (!state.all_proxies_yaml) {
    showToast('当前暂无入站节点可载入', false)
    return
  }
  converterInput.value = state.all_proxies_yaml
  convertConfigFormat('readable')
}

async function convertConfigFormat(mode = 'readable') {
  converterError.value = ''
  const raw = (converterInput.value || '').trim()
  if (!raw) {
    converterError.value = '请先粘贴需要转换的节点配置（支持单行 JSON / Flow 或多行 YAML）'
    return
  }
  busyKey.value = `convert-${mode}`
  try {
    const body = new URLSearchParams({ csrf: state.csrf, raw }).toString()
    const res = await fetch('/api/convert-readable', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-Requested-With': 'fetch',
        Accept: 'application/json',
      },
      body,
      credentials: 'same-origin',
    })
    const data = await res.json()
    if (!res.ok || !data.ok) {
      converterError.value = data.msg || '配置解析失败，请检查格式是否正确'
      return
    }
    converterOutput.value = mode === 'single' ? data.single : data.readable
    showToast(`已成功转换 ${data.count} 个节点为${mode === 'single' ? '单行配置' : '多行易读 YAML'}`, true)
  } catch (e) {
    converterError.value = `转换请求异常：${(e && e.message) || e}`
  } finally {
    busyKey.value = ''
  }
}

function autoFixCertPaths() {
  const certPath = '/etc/clashgate/certs/fullchain.pem'
  const keyPath = '/etc/clashgate/certs/privkey.pem'
  const lines = (customConfigText.value || '').split(/\r?\n/)
  let inReality = false
  let realityIndent = 0
  let inProviders = false
  let provIndent = 0
  let changed = 0

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const stripped = line.replace(/^ +/, '')
    const indent = line.length - stripped.length
    if (stripped && stripped.charAt(0) !== '#') {
      if (inReality && indent <= realityIndent) inReality = false
      if (inProviders && indent <= provIndent) inProviders = false
      if (/^reality-config\s*:/.test(stripped)) {
        inReality = true
        realityIndent = indent
        continue
      }
      if (/^proxy-providers\s*:/.test(stripped)) {
        inProviders = true
        provIndent = indent
        continue
      }
      if (inProviders && indent === provIndent + 2 && /^default\s*:\s*(#.*)?$/.test(stripped)) {
        lines[i] = line.slice(0, indent) + stripped.replace(/^default(\s*:)/, 'default-sub$1')
        changed++
        continue
      }
      const mc = stripped.match(/^((?:-\s+)?certificate\s*:\s*)([^#\n]+?)(\s*(?:#.*)?)$/)
      if (mc) {
        const cv = mc[2].trim().replace(/^['"]|['"]$/g, '')
        if (cv !== certPath) changed++
        lines[i] = line.slice(0, indent) + mc[1] + certPath + (mc[3] || '')
        continue
      }
      if (!inReality) {
        const mk = stripped.match(/^((?:-\s+)?private-key\s*:\s*)([^#\n]+?)(\s*(?:#.*)?)$/)
        if (mk) {
          const kv = mk[2].trim().replace(/^['"]|['"]$/g, '')
          if (kv.indexOf('/') >= 0 || kv.indexOf('.') >= 0 || /key|pem/i.test(kv)) {
            if (kv !== keyPath) changed++
            lines[i] = line.slice(0, indent) + mk[1] + keyPath + (mk[3] || '')
            continue
          }
        }
      }
    }
  }
  customConfigText.value = lines.join('\n')
  showToast(`已自动修正 ${changed} 处证书路径，请点击「更新 mihomo 服务端配置」保存生效。`, true)
}

async function submitCustomConfig() {
  if (!customConfigText.value.trim()) return
  await postAction('/config/custom', { custom_config_raw: customConfigText.value }, 'save-custom')
}

async function resetTemplateConfig() {
  if (
    !window.confirm(
      '确定恢复默认配置？这将还原内置默认服务端模板，并重新生成一个默认 VlessReality 节点（同时同步至客户端订阅）。'
    )
  )
    return
  await postAction('/config/reset-template', {}, 'reset-template')
}

function selectTab(tab) {
  if (!VALID_TABS.includes(tab)) return
  activeTab.value = tab
  const targetPath = TAB_PATHS[tab] || '/'
  try {
    if (window.location.pathname !== targetPath) {
      window.history.pushState({ tab }, '', targetPath)
    }
  } catch {}
}

onMounted(() => {
  if (boot.flash_msg) {
    showToast(boot.flash_msg, boot.flash_ok !== false)
  }
  window.addEventListener('popstate', () => {
    activeTab.value = detectInitialTab()
  })
  if (pageMode.value === 'dashboard') {
    statePollTimer = setInterval(refreshServerStateSilent, 15000)
  }
})

onUnmounted(() => {
  if (statePollTimer) clearInterval(statePollTimer)
})
</script>

<template>
  <!-- Login View (Bright, clean, welcoming light-green SaaS style) -->
  <div
    v-if="pageMode === 'login'"
    class="min-h-screen flex items-center justify-center p-6 bg-gradient-to-br from-[#f0fdf6] via-[#f8fcf9] to-[#e6faef]"
  >
    <div
      class="w-full max-w-md bg-white rounded-3xl shadow-[0_12px_40px_-10px_rgba(16,185,129,0.14)] border border-emerald-100 p-8 sm:p-9"
    >
      <div class="flex items-center gap-3.5 mb-7">
        <div
          class="w-12 h-12 rounded-2xl bg-gradient-to-tr from-emerald-500 to-teal-400 text-white flex items-center justify-center font-bold text-lg shadow-md shadow-emerald-500/20"
        >
          CG
        </div>
        <div>
          <div class="flex items-center gap-2">
            <h1 class="text-xl font-bold text-slate-900 tracking-tight">ClashGate</h1>
            <span
              class="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200/80"
            >
              {{ topbarVersionText }}
            </span>
          </div>
          <p class="text-xs text-slate-500 mt-0.5">服务端管理控制台 · 请登录</p>
        </div>
      </div>

      <div
        v-if="boot.login_error"
        class="mb-5 rounded-xl bg-rose-50 border border-rose-200 px-4 py-3 text-sm text-rose-700 font-medium"
      >
        {{ boot.login_error }}
      </div>

      <form method="post" action="/login" class="space-y-4">
        <div>
          <label for="u" class="block text-xs font-semibold text-slate-700 mb-1.5">管理员账号</label>
          <input
            id="u"
            name="username"
            value="admin"
            autocomplete="username"
            required
            class="w-full h-10 px-3.5 rounded-xl border border-slate-200 bg-slate-50/60 focus:bg-white text-sm text-slate-900 focus:outline-none focus:border-emerald-500 focus:ring-3 focus:ring-emerald-500/15 transition"
          />
        </div>
        <div>
          <label for="p" class="block text-xs font-semibold text-slate-700 mb-1.5">面板密码</label>
          <input
            id="p"
            name="password"
            type="password"
            autocomplete="current-password"
            placeholder="请输入面板密码"
            required
            autofocus
            class="w-full h-10 px-3.5 rounded-xl border border-slate-200 bg-slate-50/60 focus:bg-white text-sm text-slate-900 focus:outline-none focus:border-emerald-500 focus:ring-3 focus:ring-emerald-500/15 transition"
          />
        </div>
        <button
          type="submit"
          class="w-full h-10 mt-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-sm shadow-sm shadow-emerald-600/20 transition cursor-pointer"
        >
          登 录
        </button>
      </form>
    </div>
  </div>

  <!-- Dashboard View (Bright, airy, light-green modern SaaS console) -->
  <div v-else class="min-h-screen bg-[#f6faf8] text-slate-900 flex flex-col">
    <!-- Toast Notification -->
    <transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0 -translate-y-2"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 -translate-y-2"
    >
      <div
        v-if="toast.show"
        class="fixed top-18 right-6 z-50 max-w-md rounded-2xl px-4 py-3 shadow-lg border flex items-center gap-2.5 text-sm font-medium bg-white"
        :class="
          toast.ok
            ? 'border-emerald-200 text-emerald-950 shadow-emerald-500/10'
            : 'border-rose-200 text-rose-950 shadow-rose-500/10'
        "
      >
        <span
          class="w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold shrink-0"
          :class="toast.ok ? 'bg-emerald-500 text-white' : 'bg-rose-500 text-white'"
        >
          {{ toast.ok ? '✓' : '!' }}
        </span>
        <span class="break-all">{{ toast.msg }}</span>
      </div>
    </transition>

    <!-- Bright Topbar -->
    <header class="sticky top-0 z-30 bg-white/90 backdrop-blur-md border-b border-emerald-100/90 text-slate-900">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
        <div class="flex items-center gap-3">
          <div
            class="w-9 h-9 rounded-xl bg-gradient-to-tr from-emerald-500 to-teal-400 text-white flex items-center justify-center font-bold text-sm shadow-sm shadow-emerald-500/20"
          >
            CG
          </div>
          <span class="font-bold text-base tracking-tight text-slate-900">ClashGate</span>
          <span
            class="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200/80"
          >
            {{ topbarVersionText }}
          </span>
        </div>

        <div class="flex items-center gap-2 flex-wrap">
          <button
            type="button"
            :disabled="busyKey === '/action/update-core'"
            @click="updateCoreDirect"
            class="px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white shadow-xs shadow-emerald-600/15 transition cursor-pointer"
          >
            {{ busyKey === '/action/update-core' ? '更新内核中…' : '更新内核' }}
          </button>
          <button
            type="button"
            :disabled="busyKey === '/action/reload'"
            @click="postAction('/action/reload', {}, '/action/reload')"
            class="px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-emerald-50 hover:bg-emerald-100/80 border border-emerald-200/80 disabled:opacity-50 text-emerald-800 transition cursor-pointer"
          >
            {{ busyKey === '/action/reload' ? '重载中…' : '重载配置' }}
          </button>
          <button
            type="button"
            :disabled="busyKey === '/action/check-update' || busyKey === '/action/upgrade-self'"
            @click="checkUpdateAndPrompt"
            class="px-3.5 py-1.5 rounded-xl text-xs font-medium bg-white hover:bg-slate-50 border border-slate-200 disabled:opacity-50 text-slate-700 transition cursor-pointer"
          >
            {{
              busyKey === '/action/upgrade-self'
                ? '升级中…'
                : busyKey === '/action/check-update'
                  ? '检查中…'
                  : '检查更新'
            }}
          </button>
          <form method="post" action="/logout" class="inline">
            <input type="hidden" name="csrf" :value="state.csrf" />
            <button
              type="submit"
              class="px-3 py-1.5 rounded-xl text-xs font-medium bg-white hover:bg-rose-50 hover:text-rose-600 hover:border-rose-200 border border-slate-200 text-slate-600 transition cursor-pointer"
            >
              退出
            </button>
          </form>
        </div>
      </div>
    </header>

    <!-- Main Container -->
    <main class="max-w-7xl w-full mx-auto px-4 sm:px-6 py-6 space-y-6 flex-1">
      <!-- Concise Status Strip -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div
          class="bg-white rounded-2xl border border-emerald-100/90 p-4 sm:p-5 shadow-[0_2px_10px_-4px_rgba(16,185,129,0.08)] flex items-center justify-between"
        >
          <div>
            <div class="text-xs font-medium text-slate-500">运行状态</div>
            <div class="mt-1.5 flex items-center gap-2">
              <span
                class="w-2.5 h-2.5 rounded-full"
                :class="{
                  'bg-emerald-500 ring-4 ring-emerald-500/20': state.status.state_cls === 'ok',
                  'bg-amber-500 ring-4 ring-amber-500/20': state.status.state_cls === 'warn',
                  'bg-rose-500 ring-4 ring-rose-500/20':
                    state.status.state_cls !== 'ok' && state.status.state_cls !== 'warn',
                }"
              ></span>
              <span class="text-lg font-bold text-slate-900">{{ state.status.state_txt || '未知' }}</span>
            </div>
          </div>
          <span
            class="px-2.5 py-1 text-xs font-semibold rounded-lg"
            :class="
              state.custom_config_mode
                ? 'bg-amber-50 text-amber-700 border border-amber-200/60'
                : 'bg-emerald-50 text-emerald-700 border border-emerald-200/60'
            "
          >
            {{ state.custom_config_mode ? '自定义模式' : '标准模板' }}
          </span>
        </div>

        <div
          class="bg-white rounded-2xl border border-emerald-100/90 p-4 sm:p-5 shadow-[0_2px_10px_-4px_rgba(16,185,129,0.08)]"
        >
          <div class="text-xs font-medium text-slate-500">入站监听</div>
          <div class="mt-1.5 flex items-baseline gap-1.5">
            <span class="text-lg font-bold text-slate-900">{{ state.status.inbound_listening ?? 0 }}</span>
            <span class="text-xs text-slate-500">/ {{ state.status.inbound_total ?? 0 }} 个端口运行中</span>
          </div>
        </div>

        <div
          class="bg-white rounded-2xl border border-emerald-100/90 p-4 sm:p-5 shadow-[0_2px_10px_-4px_rgba(16,185,129,0.08)]"
        >
          <div class="text-xs font-medium text-slate-500">服务端出站</div>
          <div class="mt-1.5 flex items-baseline gap-1.5">
            <span class="text-lg font-bold text-slate-900">
              {{ (state.status.outbound_nodes_count ?? 0) + (state.status.outbound_providers_count ?? 0) }}
            </span>
            <span class="text-xs text-slate-500">
              {{ state.status.outbound_nodes_count ?? 0 }} 节点 · {{ state.status.outbound_providers_count ?? 0 }} 订阅源
            </span>
          </div>
        </div>

        <div
          class="bg-white rounded-2xl border border-emerald-100/90 p-4 sm:p-5 shadow-[0_2px_10px_-4px_rgba(16,185,129,0.08)]"
        >
          <div class="text-xs font-medium text-slate-500">已代理流量</div>
          <div class="mt-1.5 flex items-baseline gap-1.5">
            <span class="text-lg font-bold text-slate-900">{{ trafficDisplay }}</span>
            <span class="text-xs text-slate-400 truncate">{{ trafficDetail }}</span>
          </div>
        </div>
      </div>

      <!-- Segmented Navigation Bar -->
      <div
        class="flex items-center gap-1.5 bg-white p-1.5 rounded-2xl border border-emerald-100/90 shadow-xs flex-wrap w-fit"
      >
        <button
          type="button"
          @click="selectTab('inbounds')"
          class="px-4 py-2 rounded-xl text-sm font-semibold transition cursor-pointer"
          :class="
            activeTab === 'inbounds'
              ? 'bg-emerald-600 text-white shadow-xs'
              : 'text-slate-600 hover:text-emerald-800 hover:bg-emerald-50/60'
          "
        >
          首页 · 入站与面板
        </button>
        <button
          type="button"
          @click="selectTab('outbounds')"
          class="px-4 py-2 rounded-xl text-sm font-semibold transition cursor-pointer"
          :class="
            activeTab === 'outbounds'
              ? 'bg-emerald-600 text-white shadow-xs'
              : 'text-slate-600 hover:text-emerald-800 hover:bg-emerald-50/60'
          "
        >
          服务端出站
        </button>
        <button
          type="button"
          @click="selectTab('readable')"
          class="px-4 py-2 rounded-xl text-sm font-semibold transition cursor-pointer"
          :class="
            activeTab === 'readable'
              ? 'bg-emerald-600 text-white shadow-xs'
              : 'text-slate-600 hover:text-emerald-800 hover:bg-emerald-50/60'
          "
        >
          易读配置转换
        </button>
        <button
          type="button"
          @click="selectTab('advanced')"
          class="px-4 py-2 rounded-xl text-sm font-semibold transition cursor-pointer"
          :class="
            activeTab === 'advanced'
              ? 'bg-emerald-600 text-white shadow-xs'
              : 'text-slate-600 hover:text-emerald-800 hover:bg-emerald-50/60'
          "
        >
          自定义服务端配置
        </button>
      </div>

      <!-- TAB 1 (HOMEPAGE): Zashboard (Fixed on Home) + 客户端订阅 + 入站节点与添加节点 -->
      <div v-show="activeTab === 'inbounds'" class="space-y-6">
        <!-- Top Fixed Core Cards: Zashboard 控制面板 & 客户端订阅链接 -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <!-- Zashboard 控制面板（固定首页展示：URL + 密钥卡片） -->
          <section
            id="zashboard-card"
            class="bg-white rounded-2xl border border-emerald-200/80 p-5 sm:p-6 shadow-[0_2px_12px_-4px_rgba(16,185,129,0.1)] flex flex-col justify-between space-y-4"
          >
            <div class="flex items-center justify-between gap-3 flex-wrap">
              <div class="flex items-center gap-2.5">
                <span class="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
                <h2 class="text-base font-bold text-slate-900">Zashboard 控制面板</h2>
                <span
                  class="inline-flex items-center gap-1 px-2.5 py-0.5 text-xs font-semibold rounded-full"
                  :class="
                    state.controller_listening
                      ? 'bg-emerald-50 text-emerald-700 border border-emerald-200/70'
                      : 'bg-amber-50 text-amber-700 border border-amber-200/70'
                  "
                >
                  端口 :{{ state.controller_port }} {{ state.controller_listening ? '运行中' : '未运行' }}
                </span>
              </div>
              <div class="flex items-center gap-2 flex-wrap">
                <a
                  :href="state.zb_url || '#'"
                  target="_blank"
                  rel="noopener"
                  class="px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow-xs shadow-emerald-600/15 transition"
                >
                  打开 Zashboard
                </a>
                <button
                  type="button"
                  @click="copyRaw(state.zb_url, 'zb-url')"
                  class="px-3 py-1.5 rounded-xl text-xs font-semibold bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-200/80 transition cursor-pointer"
                >
                  {{ copiedKey === 'zb-url' ? '已复制地址' : '复制地址' }}
                </button>
                <a
                  href="/config/server.yaml"
                  target="_blank"
                  rel="noopener"
                  class="px-3 py-1.5 rounded-xl text-xs font-medium bg-slate-100 hover:bg-slate-200/80 text-slate-700 transition"
                >
                  查看Mihomo服务端配置
                </a>
              </div>
            </div>

            <div class="space-y-2.5">
              <div>
                <div class="text-xs font-medium text-slate-500 mb-1">免填密钥直连地址 (HTTPS)</div>
                <div
                  id="zb-url"
                  class="px-3.5 py-2 rounded-xl bg-[#f6faf8] border border-emerald-100 font-mono text-xs text-slate-700 break-all select-all"
                >
                  {{ state.zb_url || '—' }}
                </div>
              </div>

              <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-1">
                <div class="flex items-center gap-2 min-w-0">
                  <span class="text-xs font-medium text-slate-500 shrink-0">API 密钥 (Secret)：</span>
                  <code
                    id="zb-secret"
                    class="px-2.5 py-1 rounded-lg bg-slate-100 text-slate-800 font-mono text-xs break-all select-all"
                  >
                    {{ state.mihomo_secret || '—' }}
                  </code>
                </div>
                <div class="flex items-center gap-2 shrink-0">
                  <button
                    v-if="state.mihomo_secret"
                    type="button"
                    @click="copyRaw(state.mihomo_secret, 'zb-secret')"
                    class="px-2.5 py-1 rounded-lg text-xs font-medium bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 transition cursor-pointer"
                  >
                    {{ copiedKey === 'zb-secret' ? '已复制' : '复制密钥' }}
                  </button>
                  <button
                    type="button"
                    :disabled="busyKey === 'reset-secret'"
                    @click="resetZbSecret"
                    class="px-2.5 py-1 rounded-lg text-xs font-medium bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-200/80 disabled:opacity-50 transition cursor-pointer"
                  >
                    {{ busyKey === 'reset-secret' ? '重置中…' : '重置 API 密钥' }}
                  </button>
                </div>
              </div>
            </div>
          </section>

          <!-- 客户端订阅链接 -->
          <section
            class="bg-white rounded-2xl border border-emerald-200/80 p-5 sm:p-6 shadow-[0_2px_12px_-4px_rgba(16,185,129,0.1)] flex flex-col justify-between space-y-4"
          >
            <div class="flex items-center justify-between gap-3 flex-wrap">
              <div class="flex items-center gap-2.5">
                <span class="w-2.5 h-2.5 rounded-full bg-teal-500"></span>
                <h2 class="text-base font-bold text-slate-900">客户端订阅链接</h2>
                <span
                  class="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200/70"
                >
                  ACL4SSR 自动同步
                </span>
              </div>
              <div v-if="state.sub_url" class="flex items-center gap-2 flex-wrap">
                <button
                  type="button"
                  @click="copyRaw(state.sub_url, 'sub-url')"
                  class="px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow-xs shadow-emerald-600/15 transition cursor-pointer"
                >
                  {{ copiedKey === 'sub-url' ? '已复制' : '复制订阅链接' }}
                </button>
                <button
                  type="button"
                  :disabled="busyKey === 'reset-sub'"
                  @click="resetSubUrl"
                  class="px-3 py-1.5 rounded-xl text-xs font-semibold bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-200/80 disabled:opacity-50 transition cursor-pointer"
                >
                  {{ busyKey === 'reset-sub' ? '更换中…' : '更换订阅链接' }}
                </button>
                <a
                  :href="state.sub_url"
                  target="_blank"
                  rel="noopener"
                  class="px-3 py-1.5 rounded-xl text-xs font-medium bg-slate-100 hover:bg-slate-200/80 text-slate-700 transition"
                >
                  预览
                </a>
              </div>
            </div>

            <div class="space-y-2.5">
              <div>
                <div class="text-xs font-medium text-slate-500 mb-1">
                  导入 Clash / Mihomo 客户端即可使用
                </div>
                <div
                  id="sub-url"
                  class="px-3.5 py-2.5 rounded-xl bg-[#f6faf8] border border-emerald-100 font-mono text-xs text-slate-700 break-all select-all"
                >
                  {{ state.sub_url || '/etc/clashgate/client/mihomo-client.yaml' }}
                </div>
              </div>
              <div class="text-xs text-slate-500 flex items-center justify-between gap-2 pt-1">
                <span>本地客户端备份：<code class="font-mono text-slate-700">/etc/clashgate/client/</code></span>
                <button
                  type="button"
                  @click="selectTab('readable')"
                  class="text-emerald-700 hover:text-emerald-600 font-semibold cursor-pointer"
                >
                  前往易读配置转换 →
                </button>
              </div>
            </div>
          </section>
        </div>

        <!-- 入站节点列表 & 添加节点表单 -->
        <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          <!-- Left: Inbound Nodes List -->
          <section class="lg:col-span-7 bg-white rounded-2xl border border-slate-200/80 p-5 sm:p-6 shadow-xs">
            <div class="flex items-center justify-between gap-2 mb-4">
              <div class="flex items-center gap-2.5">
                <h2 class="text-base font-bold text-slate-900">入站节点</h2>
                <span
                  class="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200/60"
                >
                  {{ state.inbounds.length }}
                </span>
              </div>
              <div class="flex items-center gap-2">
                <button
                  v-if="state.inbounds.length > 0"
                  type="button"
                  @click="copyRaw(state.all_proxies_yaml, 'all-proxies')"
                  class="px-3 py-1.5 rounded-xl text-xs font-semibold bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-200/80 transition cursor-pointer"
                >
                  {{ copiedKey === 'all-proxies' ? '已复制全部' : '复制全部配置' }}
                </button>
              </div>
            </div>

            <div v-if="state.inbounds.length === 0" class="py-12 text-center text-sm text-slate-400">
              暂无入站节点，请在右侧添加节点
            </div>

            <div v-else class="divide-y divide-slate-100 border border-slate-200/75 rounded-2xl overflow-hidden">
              <div
                v-for="item in state.inbounds"
                :key="item.key"
                class="p-4 hover:bg-emerald-50/30 transition flex flex-col sm:flex-row sm:items-center justify-between gap-3"
              >
                <div class="space-y-1 min-w-0">
                  <div class="flex items-center gap-2 flex-wrap">
                    <span class="font-bold text-sm text-slate-900 break-all">{{ item.name }}</span>
                    <span
                      class="px-2 py-0.5 text-xs font-semibold rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200/60"
                    >
                      {{ item.kind_label }}
                    </span>
                    <span
                      class="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full"
                      :class="
                        item.listening
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200/60'
                          : item.pending_reload
                          ? 'bg-amber-50 text-amber-700 border border-amber-200/60'
                          : 'bg-rose-50 text-rose-700 border border-rose-200/60'
                      "
                    >
                      <span
                        class="w-1.5 h-1.5 rounded-full"
                        :class="item.listening ? 'bg-emerald-500' : item.pending_reload ? 'bg-amber-500' : 'bg-rose-500'"
                      ></span>
                      {{ item.listening ? '运行中' : item.pending_reload ? '重载配置生效' : '未运行' }}
                    </span>
                  </div>
                  <div class="text-xs text-slate-500 font-mono">端口 :{{ item.port }}</div>
                </div>

                <!-- Actions: 复制配置 + 重置密码 + 删除 -->
                <div class="flex items-center gap-2 shrink-0 flex-wrap">
                  <button
                    type="button"
                    @click="copyRaw(item.single_config, `single-${item.key}`)"
                    class="px-3 py-1.5 rounded-xl text-xs font-medium bg-white hover:bg-emerald-50 hover:text-emerald-800 hover:border-emerald-200 text-slate-700 border border-slate-200/90 transition cursor-pointer"
                  >
                    {{ copiedKey === `single-${item.key}` ? '已复制' : '复制配置' }}
                  </button>
                  <button
                    v-if="item.can_reset_password"
                    type="button"
                    :disabled="busyKey === `rst-${item.key}`"
                    @click="resetInboundPassword(item)"
                    class="px-3 py-1.5 rounded-xl text-xs font-medium bg-amber-50/80 hover:bg-amber-100 text-amber-800 border border-amber-200/80 disabled:opacity-50 transition cursor-pointer"
                  >
                    {{ busyKey === `rst-${item.key}` ? '重置中…' : '重置密码' }}
                  </button>
                  <button
                    type="button"
                    :disabled="busyKey === `del-${item.key}`"
                    @click="deleteInbound(item)"
                    class="px-3 py-1.5 rounded-xl text-xs font-medium text-rose-600 hover:bg-rose-50 border border-rose-200/80 disabled:opacity-50 transition cursor-pointer"
                  >
                    删除
                  </button>
                </div>
              </div>
            </div>
          </section>

          <!-- Right: Locked-Default Add Node Form -->
          <section class="lg:col-span-5 bg-white rounded-2xl border border-slate-200/80 p-5 sm:p-6 shadow-xs">
            <div class="flex items-center justify-between gap-2 mb-4">
              <h2 class="text-base font-bold text-slate-900">添加节点</h2>
              <span class="px-2.5 py-0.5 text-xs font-medium rounded-full bg-emerald-50 text-emerald-700">
                安全默认策略
              </span>
            </div>

            <form @submit.prevent="submitAddInbound" class="space-y-4">
              <div>
                <label for="kind" class="block text-xs font-semibold text-slate-700 mb-1.5">协议类型</label>
                <select
                  id="kind"
                  v-model="inboundForm.kind"
                  name="kind"
                  class="w-full h-10 px-3 rounded-xl border border-slate-200 bg-white text-sm text-slate-900 focus:outline-none focus:border-emerald-500 focus:ring-3 focus:ring-emerald-500/15"
                >
                  <option v-for="p in PROTOCOLS" :key="p.value" :value="p.value">
                    {{ p.label }}
                  </option>
                </select>
                <!-- One-line concise Chinese description right below protocol selector -->
                <p id="protocol-desc" class="mt-2 text-xs font-medium text-emerald-700 flex items-center gap-1.5">
                  <span class="inline-block w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0"></span>
                  <span>{{ currentProtocol.label }}：{{ currentProtocol.desc }}</span>
                </p>
              </div>

              <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label for="nm" class="block text-xs font-semibold text-slate-700 mb-1.5">节点名称</label>
                  <input
                    id="nm"
                    v-model="inboundForm.name"
                    name="name"
                    :placeholder="`默认 ${currentDefaultName}`"
                    class="w-full h-10 px-3 rounded-xl border border-slate-200 bg-white text-sm text-slate-900 focus:outline-none focus:border-emerald-500 focus:ring-3 focus:ring-emerald-500/15"
                  />
                </div>
                <div>
                  <label for="port" class="block text-xs font-semibold text-slate-700 mb-1.5">监听端口</label>
                  <input
                    id="port"
                    v-model="inboundForm.port"
                    name="port"
                    inputmode="numeric"
                    placeholder="留空随机端口"
                    class="w-full h-10 px-3 rounded-xl border border-slate-200 bg-white text-sm text-slate-900 focus:outline-none focus:border-emerald-500 focus:ring-3 focus:ring-emerald-500/15"
                  />
                </div>
              </div>

              <!-- Non-locked protocol options (TUIC / TrustTunnel / Mieru / HTTP / SOCKS5) -->
              <template v-if="inboundForm.kind === 'tuic'">
                <div>
                  <label class="block text-xs font-semibold text-slate-700 mb-1.5">拥塞控制</label>
                  <select
                    v-model="inboundForm.tuic_cc"
                    name="tuic_cc"
                    class="w-full h-10 px-3 rounded-xl border border-slate-200 bg-white text-sm text-slate-900 focus:outline-none focus:border-emerald-500"
                  >
                    <option value="bbr">bbr (默认)</option>
                    <option value="cubic">cubic</option>
                    <option value="new_reno">new_reno</option>
                  </select>
                </div>
              </template>

              <template v-else-if="inboundForm.kind === 'trusttunnel'">
                <div>
                  <label class="block text-xs font-semibold text-slate-700 mb-1.5">拥塞控制</label>
                  <select
                    v-model="inboundForm.tt_cc"
                    name="tt_cc"
                    class="w-full h-10 px-3 rounded-xl border border-slate-200 bg-white text-sm text-slate-900 focus:outline-none focus:border-emerald-500"
                  >
                    <option value="bbr">bbr (默认)</option>
                    <option value="cubic">cubic</option>
                  </select>
                </div>
              </template>

              <template v-else-if="inboundForm.kind === 'mieru'">
                <div>
                  <label class="block text-xs font-semibold text-slate-700 mb-1.5">传输协议</label>
                  <select
                    v-model="inboundForm.mieru_transport"
                    name="mieru_transport"
                    class="w-full h-10 px-3 rounded-xl border border-slate-200 bg-white text-sm text-slate-900 focus:outline-none focus:border-emerald-500"
                  >
                    <option value="TCP">TCP (默认)</option>
                    <option value="UDP">UDP</option>
                  </select>
                </div>
              </template>

              <template v-else-if="inboundForm.kind === 'http'">
                <div>
                  <label class="block text-xs font-semibold text-slate-700 mb-1.5">启用 TLS</label>
                  <select
                    v-model="inboundForm.http_tls"
                    name="http_tls"
                    class="w-full h-10 px-3 rounded-xl border border-slate-200 bg-white text-sm text-slate-900 focus:outline-none focus:border-emerald-500"
                  >
                    <option value="0">不启用 (默认)</option>
                    <option value="1">启用</option>
                  </select>
                </div>
              </template>

              <template v-else-if="inboundForm.kind === 'socks'">
                <div>
                  <label class="block text-xs font-semibold text-slate-700 mb-1.5">启用 TLS</label>
                  <select
                    v-model="inboundForm.socks_tls"
                    name="socks_tls"
                    class="w-full h-10 px-3 rounded-xl border border-slate-200 bg-white text-sm text-slate-900 focus:outline-none focus:border-emerald-500"
                  >
                    <option value="0">不启用 (默认)</option>
                    <option value="1">启用</option>
                  </select>
                </div>
              </template>

              <!-- Locked security defaults notice -->
              <div class="rounded-xl bg-[#f4fbf7] border border-emerald-200/70 px-3.5 py-2.5 text-xs text-emerald-900">
                {{ currentProtocol.lockedNote }}
              </div>

              <button
                type="submit"
                :disabled="busyKey === 'add-inbound'"
                class="w-full h-10 mt-1 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-sm font-semibold shadow-xs shadow-emerald-600/15 transition cursor-pointer"
              >
                {{ busyKey === 'add-inbound' ? '正在添加…' : '添加入站节点' }}
              </button>
            </form>
          </section>
        </div>
      </div>

      <!-- TAB 2: 服务端出站与外部订阅 -->
      <div v-show="activeTab === 'outbounds'" class="space-y-6">
        <!-- 导入外部订阅 (proxy-providers) -->
        <section class="bg-white rounded-2xl border border-slate-200/80 p-5 sm:p-6 shadow-xs space-y-4">
          <div class="flex items-center gap-2.5">
            <h2 class="text-base font-bold text-slate-900">外部订阅源 (proxy-providers)</h2>
            <span
              class="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200/60"
            >
              {{ state.providers.length }}
            </span>
          </div>

          <div
            v-if="state.providers.length > 0"
            class="divide-y divide-slate-100 border border-slate-200/75 rounded-2xl overflow-hidden"
          >
            <div
              v-for="prov in state.providers"
              :key="prov.name"
              class="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-emerald-50/20"
            >
              <div class="min-w-0 space-y-1">
                <div class="flex items-center gap-2">
                  <span class="font-bold text-sm text-slate-900">{{ prov.name }}</span>
                  <span class="text-xs font-mono text-slate-500">{{ prov.path }}</span>
                </div>
                <div class="text-xs text-slate-400 font-mono truncate">{{ prov.url }}</div>
              </div>
              <div class="flex items-center gap-2 shrink-0">
                <button
                  type="button"
                  @click="copyRaw(prov.yaml, `prov-${prov.name}`)"
                  class="px-3 py-1.5 rounded-xl text-xs font-medium bg-white hover:bg-emerald-50 text-slate-700 border border-slate-200/90 transition cursor-pointer"
                >
                  {{ copiedKey === `prov-${prov.name}` ? '已复制' : '复制配置' }}
                </button>
                <button
                  type="button"
                  :disabled="busyKey === `del-prov-${prov.name}`"
                  @click="deleteProvider(prov.name)"
                  class="px-3 py-1.5 rounded-xl text-xs font-medium text-rose-600 hover:bg-rose-50 border border-rose-200/80 disabled:opacity-50 transition cursor-pointer"
                >
                  删除
                </button>
              </div>
            </div>
          </div>

          <form @submit.prevent="submitAddProvider" class="grid grid-cols-1 sm:grid-cols-12 gap-3 items-end">
            <div class="sm:col-span-7">
              <label class="block text-xs font-semibold text-slate-700 mb-1.5">订阅链接 (HTTP / HTTPS)</label>
              <input
                v-model="providerForm.sub_url"
                name="sub_url"
                placeholder="https://example.com/sub.yaml?token=..."
                required
                class="w-full h-10 px-3 rounded-xl border border-slate-200 bg-white text-sm text-slate-900 focus:outline-none focus:border-emerald-500 focus:ring-3 focus:ring-emerald-500/15"
              />
            </div>
            <div class="sm:col-span-3">
              <label class="block text-xs font-semibold text-slate-700 mb-1.5">名称 (选填)</label>
              <input
                v-model="providerForm.provider_name"
                name="provider_name"
                placeholder="默认 sub"
                class="w-full h-10 px-3 rounded-xl border border-slate-200 bg-white text-sm text-slate-900 focus:outline-none focus:border-emerald-500 focus:ring-3 focus:ring-emerald-500/15"
              />
            </div>
            <div class="sm:col-span-2">
              <button
                type="submit"
                :disabled="busyKey === 'add-provider'"
                class="w-full h-10 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-semibold shadow-xs shadow-emerald-600/15 transition cursor-pointer"
              >
                {{ busyKey === 'add-provider' ? '导入中…' : '导入订阅' }}
              </button>
            </div>
          </form>
        </section>

        <!-- 服务端手工出站节点 (proxies) -->
        <section class="bg-white rounded-2xl border border-slate-200/80 p-5 sm:p-6 shadow-xs space-y-4">
          <div class="flex items-center gap-2.5">
            <h2 class="text-base font-bold text-slate-900">服务端出站节点 (proxies)</h2>
            <span
              class="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200/60"
            >
              {{ state.proxies.length }}
            </span>
          </div>

          <div
            v-if="state.proxies.length > 0"
            class="divide-y divide-slate-100 border border-slate-200/75 rounded-2xl overflow-hidden"
          >
            <div
              v-for="p in state.proxies"
              :key="p.name"
              class="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-emerald-50/20"
            >
              <div class="space-y-1 min-w-0">
                <div class="flex items-center gap-2 flex-wrap">
                  <span class="font-bold text-sm text-slate-900 break-all">{{ p.name }}</span>
                  <span
                    class="px-2 py-0.5 text-xs font-semibold rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200/60"
                  >
                    {{ p.type }}
                  </span>
                </div>
                <div class="text-xs text-slate-500 font-mono">{{ p.endpoint }}</div>
              </div>
              <div class="flex items-center gap-2 shrink-0 flex-wrap">
                <button
                  type="button"
                  @click="copyRaw(p.single_config, `p-single-${p.name}`)"
                  class="px-3 py-1.5 rounded-xl text-xs font-medium bg-white hover:bg-emerald-50 text-slate-700 border border-slate-200/90 transition cursor-pointer"
                >
                  {{ copiedKey === `p-single-${p.name}` ? '已复制' : '复制配置' }}
                </button>
                <button
                  type="button"
                  :disabled="busyKey === `del-proxy-${p.name}`"
                  @click="deleteProxy(p.name)"
                  class="px-3 py-1.5 rounded-xl text-xs font-medium text-rose-600 hover:bg-rose-50 border border-rose-200/80 disabled:opacity-50 transition cursor-pointer"
                >
                  删除
                </button>
              </div>
            </div>
          </div>

          <form @submit.prevent="submitAddProxies" class="space-y-3">
            <textarea
              v-model="proxiesRaw"
              name="proxies_raw"
              rows="5"
              placeholder="粘贴单行 JSON / Flow 或多行 YAML 格式的 mihomo 节点配置（含 easytier、tailscale 等）…"
              class="w-full p-3.5 rounded-xl border border-slate-200 bg-[#f8faf9] font-mono text-xs text-slate-900 focus:bg-white focus:outline-none focus:border-emerald-500 focus:ring-3 focus:ring-emerald-500/15"
            ></textarea>
            <div class="flex items-center gap-2.5 flex-wrap">
              <button
                type="submit"
                :disabled="busyKey === 'add-proxies'"
                class="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-semibold shadow-xs shadow-emerald-600/15 transition cursor-pointer"
              >
                {{ busyKey === 'add-proxies' ? '添加中…' : '添加出站节点' }}
              </button>
              <label
                class="px-3.5 py-2 rounded-xl bg-slate-100 hover:bg-slate-200/80 text-slate-700 text-xs font-medium transition cursor-pointer"
              >
                从文件载入
                <input
                  type="file"
                  accept=".yaml,.yml,.json,.txt"
                  class="hidden"
                  @change="(e) => loadFileInto(e, proxiesRaw)"
                />
              </label>
            </div>
          </form>
        </section>
      </div>

      <!-- TAB 3: 易读配置转换 (Dedicated Converter Page) -->
      <div v-show="activeTab === 'readable'" class="space-y-6">
        <section class="bg-white rounded-2xl border border-slate-200/80 p-5 sm:p-6 shadow-xs space-y-5">
          <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <div class="flex items-center gap-2.5">
                <h2 class="text-base font-bold text-slate-900">易读配置转换</h2>
                <span
                  class="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200/70"
                >
                  单行 JSON ⇄ 多行 YAML
                </span>
              </div>
              <p class="text-xs text-slate-500 mt-1">
                在此粘贴单行 JSON / Flow 节点配置或多行 YAML，一键转换为结构清晰的多行易读 YAML 格式。
              </p>
            </div>
            <div class="flex items-center gap-2 flex-wrap">
              <button
                type="button"
                @click="fillCurrentInboundsToConverter"
                class="px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-200/80 transition cursor-pointer"
              >
                载入当前入站节点
              </button>
              <button
                type="button"
                @click="
                  converterInput = '';
                  converterOutput = '';
                  converterError = ''
                "
                class="px-3 py-1.5 rounded-xl text-xs font-medium bg-slate-100 hover:bg-slate-200 text-slate-700 transition cursor-pointer"
              >
                清空
              </button>
            </div>
          </div>

          <div
            v-if="converterError"
            class="rounded-xl bg-rose-50 border border-rose-200 px-4 py-3 text-xs text-rose-700 font-medium"
          >
            {{ converterError }}
          </div>

          <div class="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <div class="space-y-2">
              <div class="flex items-center justify-between">
                <label class="text-xs font-semibold text-slate-700">输入节点配置（单行 JSON / 多行 YAML）</label>
                <div class="flex items-center gap-2">
                  <button
                    type="button"
                    :disabled="busyKey === 'convert-readable'"
                    @click="convertConfigFormat('readable')"
                    class="px-3 py-1 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white transition cursor-pointer"
                  >
                    转换为易读配置
                  </button>
                  <button
                    type="button"
                    :disabled="busyKey === 'convert-single'"
                    @click="convertConfigFormat('single')"
                    class="px-3 py-1 rounded-lg text-xs font-medium bg-slate-100 hover:bg-slate-200 text-slate-700 transition cursor-pointer"
                  >
                    转换为单行配置
                  </button>
                </div>
              </div>
              <textarea
                id="converter-input"
                v-model="converterInput"
                rows="14"
                placeholder='在此粘贴节点配置，例如：&#10;- {"name":"VlessReality","type":"vless","server":"1.2.3.4","port":28443,...}'
                class="w-full p-3.5 rounded-xl border border-slate-200 bg-[#f8faf9] font-mono text-xs text-slate-900 leading-relaxed focus:bg-white focus:outline-none focus:border-emerald-500 focus:ring-3 focus:ring-emerald-500/15"
              ></textarea>
            </div>

            <div class="space-y-2">
              <div class="flex items-center justify-between">
                <label class="text-xs font-semibold text-slate-700">转换结果（易读 YAML）</label>
                <button
                  type="button"
                  :disabled="!converterOutput"
                  @click="copyRaw(converterOutput, 'conv-out')"
                  class="px-3.5 py-1 rounded-lg text-xs font-semibold bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-200/80 disabled:opacity-40 transition cursor-pointer"
                >
                  {{ copiedKey === 'conv-out' ? '已复制结果' : '复制转换结果' }}
                </button>
              </div>
              <textarea
                id="converter-output"
                v-model="converterOutput"
                readonly
                rows="14"
                placeholder="点击「转换为易读配置」后在此显示多行 YAML 结果…"
                class="w-full p-3.5 rounded-xl border border-slate-200 bg-[#f8faf9] font-mono text-xs text-slate-800 leading-relaxed focus:outline-none"
              ></textarea>
            </div>
          </div>
        </section>
      </div>

      <!-- TAB 4: 自定义 mihomo 服务端配置 -->
      <div v-show="activeTab === 'advanced'" class="space-y-6">
        <section class="bg-white rounded-2xl border border-slate-200/80 p-5 sm:p-6 shadow-xs space-y-5">
          <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div class="space-y-1">
              <div class="flex items-center gap-2.5 flex-wrap">
                <h2 class="text-base font-bold text-slate-900">自定义 mihomo 服务端配置</h2>
                <span
                  class="px-2.5 py-0.5 text-xs font-semibold rounded-full"
                  :class="
                    state.custom_config_mode
                      ? 'bg-amber-50 text-amber-700 border border-amber-200/70'
                      : 'bg-emerald-50 text-emerald-700 border border-emerald-200/70'
                  "
                >
                  {{ state.custom_config_mode ? '当前：自定义配置模式' : '当前：标准模板模式' }}
                </span>
              </div>
              <p class="text-xs text-slate-500">
                您可以直接粘贴或编辑整份自备的 mihomo 服务端配置文件（<code class="font-mono">config.yaml</code>），校验通过后立即应用，并自动同步刷新入站 Listeners 列表与客户端订阅。普通用户无需修改此页。
              </p>
            </div>

            <!-- 恢复默认配置（始终可见：一点即还原模板配置，并生成一个默认 VlessReality 节点） -->
            <button
              type="button"
              :disabled="busyKey === 'reset-template'"
              @click="resetTemplateConfig"
              class="px-4 py-2 rounded-xl text-xs font-semibold text-rose-700 bg-rose-50 hover:bg-rose-100 border border-rose-200/90 disabled:opacity-50 transition cursor-pointer shrink-0"
            >
              {{ busyKey === 'reset-template' ? '正在恢复默认配置…' : '恢复默认配置' }}
            </button>
          </div>

          <!-- 证书路径提示与说明 -->
          <div class="rounded-2xl bg-amber-50/90 border border-amber-200/90 p-4 text-xs text-amber-950 leading-relaxed space-y-1.5">
            <div class="font-bold text-amber-900">⚠️ 醒目提醒：Mihomo 证书目录与相对路径说明</div>
            <div>
              1. 本系统已将 Mihomo 运行目录（<code class="font-mono font-semibold">-d</code>）、配置文件与证书统一收纳在
              <code class="font-mono font-semibold">/etc/clashgate</code>，证书实际位于
              <code class="font-mono font-semibold">/etc/clashgate/certs/fullchain.pem</code> 与
              <code class="font-mono font-semibold">/etc/clashgate/certs/privkey.pem</code>（相对路径即
              <code class="font-mono font-semibold">certs/fullchain.pem</code> 与
              <code class="font-mono font-semibold">certs/privkey.pem</code>）。
            </div>
            <div>
              2. 若您的自备配置中填写了其他证书路径或相对路径，请点击下方
              <b class="font-semibold">「自动修改证书路径」</b> 按钮一键修正为本机证书路径，随后点击
              <b class="font-semibold">「更新 mihomo 服务端配置」</b> 校验并生效。
            </div>
          </div>

          <form @submit.prevent="submitCustomConfig" class="space-y-3.5">
            <textarea
              id="custom-config-raw"
              v-model="customConfigText"
              name="custom_config_raw"
              rows="16"
              placeholder="在此粘贴完整的 mihomo 服务端 YAML 配置…"
              class="w-full p-4 rounded-2xl border border-slate-200 bg-[#f8faf9] text-slate-800 font-mono text-xs leading-relaxed focus:bg-white focus:outline-none focus:border-emerald-500 focus:ring-3 focus:ring-emerald-500/15"
            ></textarea>
            <div class="flex items-center gap-2.5 flex-wrap">
              <button
                type="button"
                @click="autoFixCertPaths"
                class="px-4 py-2 rounded-xl bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-200 text-xs font-semibold transition cursor-pointer"
              >
                自动修改证书路径
              </button>
              <button
                type="submit"
                :disabled="busyKey === 'save-custom'"
                class="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-semibold shadow-xs shadow-emerald-600/15 transition cursor-pointer"
              >
                {{ busyKey === 'save-custom' ? '正在校验并更新…' : '更新 mihomo 服务端配置' }}
              </button>
              <label
                class="px-3.5 py-2 rounded-xl bg-slate-100 hover:bg-slate-200/80 text-slate-700 text-xs font-medium transition cursor-pointer"
              >
                从本地文件载入
                <input
                  type="file"
                  accept=".yaml,.yml,.txt"
                  class="hidden"
                  @change="(e) => loadFileInto(e, customConfigText)"
                />
              </label>
            </div>
          </form>
        </section>
      </div>
    </main>
  </div>
</template>
