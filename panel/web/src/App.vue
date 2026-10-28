<script setup>
import { ref, reactive, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { t, lang, setLang } from './i18n.js'

const boot = window.__CS_BOOT__ || {
  page: 'dashboard',
  initial_tab: 'inbounds',
  version: '1.03',
  mihomo_version: '',
  csrf: '',
  login_error: '',
  flash_msg: '',
  flash_ok: true,
  sub_url: '',
  sub_qr_data_url: '',
  zb_url: '',
  mihomo_secret: '',
  srv_cfg_url: '/config/server.yaml',
  controller_port: 0,
  controller_listening: false,
  certs_present: true,
  mode: 'auto-cert',
  cert_mode: 'port',
  domain: '',
  cf_token: '',
  cert_issuer: '',
  cert_expires: '',
  cert_days: null,
  cert_hours: null,
  custom_config_mode: false,
  custom_config_raw: '',
  pending_reload_count: 0,
  pending_reload_items: [],
  status: {
    active: 'active',
    state_txt: '运行中',
    state_cls: 'ok',
    mihomo_version: '',
    inbound_total: 0,
    inbound_listening: 0,
    outbound_nodes_count: 0,
    outbound_providers_count: 0,
    pending_reload_count: 0,
    mode: 'auto-cert',
    cert_mode: 'port',
    domain: '',
    cert_issuer: '',
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
  version: boot.version || '1.03',
  mihomo_version: boot.mihomo_version || (boot.status && boot.status.mihomo_version) || '',
  csrf: boot.csrf || '',
  sub_url: boot.sub_url || '',
  sub_qr_data_url: boot.sub_qr_data_url || '',
  zb_url: boot.zb_url || '',
  mihomo_secret: boot.mihomo_secret || '',
  srv_cfg_url: boot.srv_cfg_url || '/config/server.yaml',
  controller_port: boot.controller_port || 0,
  controller_listening: !!boot.controller_listening,
  certs_present: boot.certs_present !== false,
  mode: boot.mode || (boot.status && boot.status.mode) || 'auto-cert',
  cert_mode: boot.cert_mode || (boot.status && boot.status.cert_mode) || 'port',
  domain: boot.domain || (boot.status && boot.status.domain) || '',
  cf_token: boot.cf_token || '',
  cert_issuer: boot.cert_issuer || (boot.status && boot.status.cert_issuer) || '',
  cert_expires: boot.cert_expires || (boot.status && boot.status.cert_expires) || '',
  cert_days: boot.cert_days !== undefined ? boot.cert_days : (boot.status ? boot.status.cert_days : null),
  cert_hours: boot.cert_hours !== undefined ? boot.cert_hours : (boot.status ? boot.status.cert_hours : null),
  custom_config_mode: !!boot.custom_config_mode,
  custom_config_raw: boot.custom_config_raw || '',
  pending_reload_count: Number(boot.pending_reload_count || (boot.status && boot.status.pending_reload_count) || 0),
  pending_reload_items: Array.isArray(boot.pending_reload_items) ? boot.pending_reload_items : [],
  status: { ...(boot.status || {}) },
  inbounds: Array.isArray(boot.inbounds) ? boot.inbounds : [],
  all_proxies_yaml: boot.all_proxies_yaml || '',
  proxies: Array.isArray(boot.proxies) ? boot.proxies : [],
  providers: Array.isArray(boot.providers) ? boot.providers : [],
})

const showPendingDiff = ref(false)
const showSubQrModal = ref(false)

// Sensitive fields (Zashboard URL, API secret, Client subscription URL, Cloudflare API Token):
// masked by default, click field to reveal, auto-mask on blur / tab switch / outside click
const zbUrlRevealed = ref(false)
const zbSecretRevealed = ref(false)
const subUrlRevealed = ref(false)
const cfTokenRevealed = ref(false)
const zbUrlEl = ref(null)
const zbSecretEl = ref(null)
const subUrlEl = ref(null)
const cfTokenEl = ref(null)

function revealZbUrl() {
  if (!state.zb_url) return
  zbUrlRevealed.value = true
  nextTick(() => {
    if (zbUrlEl.value && typeof zbUrlEl.value.focus === 'function') {
      zbUrlEl.value.focus()
    }
  })
}

function revealZbSecret() {
  if (!state.mihomo_secret) return
  zbSecretRevealed.value = true
  nextTick(() => {
    if (zbSecretEl.value && typeof zbSecretEl.value.focus === 'function') {
      zbSecretEl.value.focus()
    }
  })
}

function revealSubUrl() {
  if (!state.sub_url) return
  subUrlRevealed.value = true
  nextTick(() => {
    if (subUrlEl.value && typeof subUrlEl.value.focus === 'function') {
      subUrlEl.value.focus()
    }
  })
}

function revealCfToken() {
  cfTokenRevealed.value = true
  nextTick(() => {
    if (cfTokenEl.value && typeof cfTokenEl.value.focus === 'function') {
      cfTokenEl.value.focus()
    }
  })
}

function maskAllSensitive() {
  zbUrlRevealed.value = false
  zbSecretRevealed.value = false
  subUrlRevealed.value = false
  cfTokenRevealed.value = false
}

function handleDocumentPointerDown(ev) {
  const target = ev && ev.target
  if (zbUrlRevealed.value && zbUrlEl.value && target && !zbUrlEl.value.contains(target)) {
    zbUrlRevealed.value = false
  }
  if (zbSecretRevealed.value && zbSecretEl.value && target && !zbSecretEl.value.contains(target)) {
    zbSecretRevealed.value = false
  }
  if (subUrlRevealed.value && subUrlEl.value && target && !subUrlEl.value.contains(target)) {
    subUrlRevealed.value = false
  }
  if (cfTokenRevealed.value && cfTokenEl.value && target && !cfTokenEl.value.contains(target)) {
    cfTokenRevealed.value = false
  }
}

function handleVisibilityChange() {
  if (document.hidden) {
    maskAllSensitive()
  }
}

// Change Password Modal state
const showPasswordModal = ref(false)
const passwordForm = reactive({
  current_password: '',
  new_password: '',
  confirm_password: '',
})

function openPasswordModal() {
  passwordForm.current_password = ''
  passwordForm.new_password = ''
  passwordForm.confirm_password = ''
  showPasswordModal.value = true
}

function closePasswordModal() {
  showPasswordModal.value = false
  passwordForm.current_password = ''
  passwordForm.new_password = ''
  passwordForm.confirm_password = ''
}

async function submitChangePassword() {
  if (busyKey.value) return
  if (!passwordForm.current_password) {
    showToast(t('请输入当前密码'), false)
    return
  }
  if (!passwordForm.new_password || passwordForm.new_password.length < 8) {
    showToast(t('新密码长度至少 8 位'), false)
    return
  }
  if (passwordForm.new_password !== passwordForm.confirm_password) {
    showToast(t('两次输入的新密码不一致'), false)
    return
  }
  const res = await postAction(
    '/action/change-password',
    {
      current_password: passwordForm.current_password,
      new_password: passwordForm.new_password,
      confirm_password: passwordForm.confirm_password,
    },
    '/action/change-password'
  )
  if (res && res.ok) {
    closePasswordModal()
  }
}

const confirmDialog = reactive({
  show: false,
  title: '',
  message: '',
  confirmText: '',
  tone: 'amber',
  onConfirm: null,
})

function openConfirmDialog({ title, message, confirmText, tone = 'amber', onConfirm }) {
  confirmDialog.title = title || t('确认操作')
  confirmDialog.message = message || ''
  confirmDialog.confirmText = confirmText || t('确认')
  confirmDialog.tone = tone
  confirmDialog.onConfirm = onConfirm || null
  confirmDialog.show = true
}

function closeConfirmDialog() {
  confirmDialog.show = false
  confirmDialog.onConfirm = null
}

async function acceptConfirmDialog() {
  const fn = confirmDialog.onConfirm
  closeConfirmDialog()
  if (typeof fn === 'function') {
    await fn()
  }
}

function confirmDiscardPending() {
  if (state.pending_reload_count <= 0) return
  openConfirmDialog({
    title: t('丢弃草稿'),
    message: t('确定丢弃所有待重载草稿？丢弃后未生效的变更将全部撤销，回到当前线上配置。'),
    confirmText: t('确认丢弃'),
    tone: 'rose',
    onConfirm: () => postAction('/action/discard-pending', {}, '/action/discard-pending'),
  })
}

function formatPendingItem(item) {
  if (!item) return ''
  const op = item.op || ''
  const name = item.name || ''
  const port = item.port
  if (op === 'add') {
    return lang.value === 'en'
      ? `+ Add node “${name}” (port ${port})`
      : `+ 添加节点「${name}」（端口 ${port}）`
  }
  if (op === 'delete') {
    return lang.value === 'en' ? `- Delete node “${name}”` : `- 删除节点「${name}」`
  }
  if (op === 'reset-password') {
    return lang.value === 'en' ? `~ Reset password “${name}”` : `~ 重置密码「${name}」`
  }
  if (op === 'reset-secret') {
    return lang.value === 'en' ? '~ Reset API secret' : '~ 重置 API 密钥'
  }
  if (op === 'reset-sub') {
    return lang.value === 'en' ? '~ Change subscription link' : '~ 更换订阅链接'
  }
  if (op === 'add-proxy') {
    return lang.value === 'en' ? `+ Add outbound node “${name}”` : `+ 添加出站节点「${name}」`
  }
  if (op === 'delete-proxy') {
    return lang.value === 'en' ? `- Delete outbound node “${name}”` : `- 删除出站节点「${name}」`
  }
  if (op === 'add-provider') {
    return lang.value === 'en' ? `+ Import provider “${name}”` : `+ 导入订阅源「${name}」`
  }
  if (op === 'delete-provider') {
    return lang.value === 'en' ? `- Delete provider “${name}”` : `- 删除订阅源「${name}」`
  }
  return item.detail || ''
}

const topbarVersionText = computed(() => {
  const mv = String(state.mihomo_version || (state.status && state.status.mihomo_version) || '').trim()
  return mv ? `v${state.version} · mihomo ${mv}` : `v${state.version}`
})

const converterPlaceholder = computed(
  () => t('在此粘贴节点配置，例如：') + '\n- {"name":"VlessReality","type":"vless","server":"1.2.3.4","port":28443,...}'
)

const VALID_TABS = ['inbounds', 'outbounds', 'readable', 'advanced', 'certs']
const TAB_PATHS = {
  inbounds: '/',
  outbounds: '/outbounds',
  readable: '/readable',
  advanced: '/advanced',
  certs: '/certs',
}

function detectInitialTab() {
  if (boot.initial_tab && VALID_TABS.includes(boot.initial_tab)) {
    return boot.initial_tab
  }
  const p = window.location.pathname
  if (p === '/certs' || p === '/cert') return 'certs'
  if (p === '/advanced' || p === '/custom-config') return 'advanced'
  if (p === '/readable' || p === '/convert') return 'readable'
  if (p === '/outbounds') return 'outbounds'
  return 'inbounds'
}

const activeTab = ref(detectInitialTab())
watch(activeTab, () => {
  maskAllSensitive()
})

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

// HTTPS Certificate management state
const certModeForm = reactive({
  mode: 'dns',
  cf_token: state.cf_token || '',
})

const certModeValue = computed(() => state.cert_mode || (state.status && state.status.cert_mode) || 'port')
const certModeLabel = computed(() => {
  if (state.mode === 'no-cert' && !state.certs_present && !state.domain) {
    return t('无证书模式')
  }
  const m = certModeValue.value
  if (m === 'dns') return t('Cloudflare DNS')
  if (m === 'manual') return t('手动证书')
  return t('端口模式')
})
const certDomainDisplay = computed(() => state.domain || (state.status && state.status.domain) || '—')
const certIssuerDisplay = computed(() => (state.status && state.status.cert_issuer) || state.cert_issuer || '—')
const certExpiresDisplay = computed(() => (state.status && state.status.cert_expires) || state.cert_expires || '—')
const certDaysValue = computed(() => {
  const d = state.status && state.status.cert_days !== undefined ? state.status.cert_days : state.cert_days
  return d === null || d === undefined || d === '' ? null : Number(d)
})
const certIsTemp = computed(() => /clashgate temporary/i.test(certIssuerDisplay.value))

async function submitCertMode() {
  if (busyKey.value) return
  if (certModeForm.mode === 'dns') {
    const tok = certModeForm.cf_token
    if (!tok) {
      showToast(t('请输入 Cloudflare API Token'), false)
      return
    }
    if (/[\s"']/.test(tok)) {
      showToast(t('API Token 不能包含空格或引号'), false)
      return
    }
  }
  maskAllSensitive()
  await postAction(
    '/action/cert-mode',
    {
      cert_mode: certModeForm.mode,
      cf_token: certModeForm.cf_token,
    },
    '/action/cert-mode'
  )
  maskAllSensitive()
}

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
    if (startData && startData.running === false) {
      if (startData.state) applyServerState(startData.state)
      showToast(startData.msg || (startData.ok ? t('内核更新成功') : t('更新内核失败')), !!startData.ok)
      return
    }
  } catch {
    // Fall through to poll /api/update-core-status
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
        showToast(pollData.msg || (pollData.ok ? t('内核更新成功') : t('更新内核失败')), !!pollData.ok)
        busyKey.value = ''
        return
      }
    } catch {
      // Transient connection drop while mihomo restarts — keep polling
    }
  }
  busyKey.value = ''
  showToast(t('更新内核等待超时，请刷新页面查看内核版本状态'), false)
}

async function checkUpdateAndPrompt() {
  const res = await postAction('/action/check-update', {}, '/action/check-update')
  if (!res || !res.ok) return
  if (res.has_update) {
    const latest = res.latest_version || t('最新版')
    const current = res.current_version || state.version
    openConfirmDialog({
      title: t('检查更新'),
      message: t('检测到新版本 v{latest}（当前版本 v{current}），是否立即升级？', { latest, current }),
      confirmText: t('立即升级'),
      tone: 'emerald',
      onConfirm: () => postAction('/action/upgrade-self', {}, '/action/upgrade-self'),
    })
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
        if (data.pending_reload_count !== undefined) {
          state.pending_reload_count = Number(data.pending_reload_count || 0)
        }
        if (Array.isArray(data.pending_reload_items)) {
          state.pending_reload_items = data.pending_reload_items
        }
        if (data.status) {
          Object.assign(state.status, data.status)
          if (data.status.mihomo_version) state.mihomo_version = data.status.mihomo_version
        }
        if (data.certs_present !== undefined) state.certs_present = data.certs_present
        if (data.mode !== undefined) state.mode = data.mode
        if (data.cert_mode !== undefined) state.cert_mode = data.cert_mode
        if (data.domain !== undefined) state.domain = data.domain
        if (data.cert_issuer !== undefined) state.cert_issuer = data.cert_issuer
        if (data.cert_expires !== undefined) state.cert_expires = data.cert_expires
        if (data.cert_days !== undefined) state.cert_days = data.cert_days
        if (data.cert_hours !== undefined) state.cert_hours = data.cert_hours
      }
    }
  } catch {}
}

function applyServerState(newState) {
  if (!newState) return
  if (newState.version) state.version = newState.version
  if (newState.mihomo_version) state.mihomo_version = newState.mihomo_version
  if (newState.csrf) state.csrf = newState.csrf
  if (newState.sub_url !== undefined) {
    if (newState.sub_url !== state.sub_url) subUrlRevealed.value = false
    state.sub_url = newState.sub_url
  }
  if (newState.sub_qr_data_url !== undefined) state.sub_qr_data_url = newState.sub_qr_data_url
  if (!state.sub_url || !state.sub_qr_data_url) showSubQrModal.value = false
  if (newState.zb_url !== undefined) {
    if (newState.zb_url !== state.zb_url) zbUrlRevealed.value = false
    state.zb_url = newState.zb_url
  }
  if (newState.mihomo_secret !== undefined) {
    if (newState.mihomo_secret !== state.mihomo_secret) zbSecretRevealed.value = false
    state.mihomo_secret = newState.mihomo_secret
  }
  if (newState.srv_cfg_url !== undefined) state.srv_cfg_url = newState.srv_cfg_url
  if (newState.controller_port !== undefined) state.controller_port = newState.controller_port
  if (newState.controller_listening !== undefined) state.controller_listening = newState.controller_listening
  if (newState.certs_present !== undefined) state.certs_present = newState.certs_present
  if (newState.mode !== undefined) state.mode = newState.mode
  if (newState.cert_mode !== undefined) state.cert_mode = newState.cert_mode
  if (newState.domain !== undefined) state.domain = newState.domain
  if (newState.cf_token !== undefined) {
    if (newState.cf_token !== state.cf_token) cfTokenRevealed.value = false
    state.cf_token = newState.cf_token
    if (newState.cf_token) certModeForm.cf_token = newState.cf_token
  }
  if (newState.cert_issuer !== undefined) state.cert_issuer = newState.cert_issuer
  if (newState.cert_expires !== undefined) state.cert_expires = newState.cert_expires
  if (newState.cert_days !== undefined) state.cert_days = newState.cert_days
  if (newState.cert_hours !== undefined) state.cert_hours = newState.cert_hours
  if (newState.custom_config_mode !== undefined) state.custom_config_mode = newState.custom_config_mode
  if (newState.custom_config_raw !== undefined) {
    state.custom_config_raw = newState.custom_config_raw
    customConfigText.value = newState.custom_config_raw
  }
  if (newState.pending_reload_count !== undefined) {
    state.pending_reload_count = Number(newState.pending_reload_count || 0)
    if (state.pending_reload_count === 0) showPendingDiff.value = false
  }
  if (Array.isArray(newState.pending_reload_items)) {
    state.pending_reload_items = newState.pending_reload_items
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
    return t('网络连接中断或服务正在重启，请稍后刷新页面查看状态')
  }
  return t('请求异常：{raw}', { raw })
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
    showToast(data.msg || (data.ok ? t('操作成功') : t('操作失败')), !!data.ok)
    return data
  } catch (err) {
    if (timer) clearTimeout(timer)
    if (err && err.name === 'AbortError') {
      showToast(t('请求超时（120s），请稍后刷新查看状态'), false)
      return null
    }
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
          showToast(t('已重载配置并更新客户端订阅'), true)
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

function resetSubUrl() {
  openConfirmDialog({
    title: t('更换订阅链接'),
    message: t('确定更换订阅链接？需点击顶部「重载配置」后新订阅链接才会生效（重载后旧链接失效）。'),
    confirmText: t('确认更换'),
    tone: 'amber',
    onConfirm: async () => {
      maskAllSensitive()
      await postAction('/action/reset-sub', {}, 'reset-sub')
      maskAllSensitive()
    },
  })
}

function resetZbSecret() {
  openConfirmDialog({
    title: t('重置 API 密钥'),
    message: t('确定重置 Zashboard API 密钥？需点击顶部「重载配置」后直连地址才会更新。'),
    confirmText: t('确认重置'),
    tone: 'amber',
    onConfirm: async () => {
      maskAllSensitive()
      await postAction('/action/reset-secret', {}, 'reset-secret')
      maskAllSensitive()
    },
  })
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

function deleteProvider(name) {
  openConfirmDialog({
    title: t('删除'),
    message: t('确定删除订阅源「{name}」？', { name }),
    confirmText: t('确认删除'),
    tone: 'rose',
    onConfirm: () => postAction('/providers/delete', { name }, `del-prov-${name}`),
  })
}

async function submitAddProxies() {
  if (!proxiesRaw.value.trim()) return
  const res = await postAction('/proxies/add', { proxies_raw: proxiesRaw.value }, 'add-proxies')
  if (res && res.ok) {
    proxiesRaw.value = ''
  }
}

function deleteProxy(name) {
  openConfirmDialog({
    title: t('删除'),
    message: t('确定删除出站节点「{name}」？', { name }),
    confirmText: t('确认删除'),
    tone: 'rose',
    onConfirm: () => postAction('/proxies/delete', { name }, `del-proxy-${name}`),
  })
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
    showToast(t('当前暂无入站节点可载入'), false)
    return
  }
  converterInput.value = state.all_proxies_yaml
  convertConfigFormat('readable')
}

async function convertConfigFormat(mode = 'readable') {
  converterError.value = ''
  const raw = (converterInput.value || '').trim()
  if (!raw) {
    converterError.value = t('请先粘贴需要转换的节点配置（支持单行 JSON / Flow 或多行 YAML）')
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
      converterError.value = data.msg || t('配置解析失败，请检查格式是否正确')
      return
    }
    converterOutput.value = mode === 'single' ? data.single : data.readable
    showToast(t('已成功转换 {count} 个节点为{kind}', { count: data.count, kind: mode === 'single' ? t('单行配置') : t('多行易读 YAML') }), true)
  } catch (e) {
    converterError.value = t('转换请求异常：{err}', { err: (e && e.message) || e })
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
  showToast(t('已自动修正 {changed} 处证书路径，请点击「更新 mihomo 服务端配置」保存生效。', { changed }), true)
}

async function submitCustomConfig() {
  if (!customConfigText.value.trim()) return
  await postAction('/config/custom', { custom_config_raw: customConfigText.value }, 'save-custom')
}

function resetTemplateConfig() {
  openConfirmDialog({
    title: t('恢复标准模板'),
    message: t('确定恢复标准模板？这将还原内置标准服务端模板，并重新生成一个默认 VlessReality 节点（同时同步至客户端订阅）。'),
    confirmText: t('恢复标准模板'),
    tone: 'rose',
    onConfirm: () => postAction('/config/reset-template', {}, 'reset-template'),
  })
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
  window.addEventListener('blur', maskAllSensitive)
  document.addEventListener('visibilitychange', handleVisibilityChange)
  document.addEventListener('pointerdown', handleDocumentPointerDown)
  if (pageMode.value === 'dashboard') {
    statePollTimer = setInterval(refreshServerStateSilent, 15000)
  }
})

onUnmounted(() => {
  if (statePollTimer) clearInterval(statePollTimer)
  window.removeEventListener('blur', maskAllSensitive)
  document.removeEventListener('visibilitychange', handleVisibilityChange)
  document.removeEventListener('pointerdown', handleDocumentPointerDown)
})
</script>

<template>
  <!-- Login View: Bright, refined Linear/Stripe-inspired light-green SaaS sign-in -->
  <div
    v-if="pageMode === 'login'"
    class="min-h-screen flex items-center justify-center p-6 bg-gradient-to-b from-[#f1fbf6] via-[#f7fbf9] to-[#edf8f2]"
  >
    <div
      class="cg-login-card relative overflow-hidden w-full max-w-[420px] bg-white rounded-3xl shadow-[0_2px_6px_rgba(15,23,42,0.03),0_20px_48px_-12px_rgba(16,185,129,0.14)] border border-emerald-100/90 p-8 sm:p-9"
    >
      <div class="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-emerald-400 via-emerald-500 to-teal-500"></div>
      <div class="flex justify-end -mt-1 mb-3">
        <button
          type="button"
          @click="setLang(lang === 'zh' ? 'en' : 'zh')"
          class="px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-50 hover:bg-emerald-50 hover:text-emerald-800 border border-slate-200/80 text-slate-600 transition cursor-pointer"
        >
          {{ lang === 'zh' ? 'English' : '中文' }}
        </button>
      </div>
      <div class="flex items-center gap-3.5 mb-7">
        <img
          src="/assets/logo.png"
          alt="ClashGate"
          class="w-12 h-12 rounded-2xl object-cover shadow-md shadow-emerald-500/15 ring-1 ring-emerald-500/10 bg-white"
        />
        <div>
          <div class="flex items-center gap-2">
            <h1 class="text-xl font-bold text-slate-900 tracking-tight">ClashGate</h1>
            <span
              class="px-2.5 py-0.5 text-[11px] font-semibold rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200/80 tabular-nums"
            >
              {{ topbarVersionText }}
            </span>
          </div>
          <p class="text-xs text-slate-500 mt-1">{{ t('服务端管理控制台 · 请登录') }}</p>
        </div>
      </div>

      <div
        v-if="boot.login_error"
        class="mb-5 rounded-xl bg-rose-50/90 border border-rose-200/90 px-4 py-3 text-xs text-rose-700 font-medium flex items-center gap-2"
      >
        <span class="w-4 h-4 rounded-full bg-rose-500 text-white text-[10px] font-bold flex items-center justify-center shrink-0">!</span>
        <span>{{ boot.login_error }}</span>
      </div>

      <form method="post" action="/login" class="space-y-4">
        <div>
          <label for="u" class="block text-xs font-semibold text-slate-700 mb-1.5">{{ t('管理员账号') }}</label>
          <input
            id="u"
            name="username"
            value="admin"
            autocomplete="username"
            required
            class="cg-input w-full h-10 px-3.5 rounded-xl border border-slate-200/90 bg-slate-50/50 focus:bg-white text-sm text-slate-900"
          />
        </div>
        <div>
          <label for="p" class="block text-xs font-semibold text-slate-700 mb-1.5">{{ t('面板密码') }}</label>
          <input
            id="p"
            name="password"
            type="password"
            autocomplete="current-password"
            :placeholder="t('请输入面板密码')"
            required
            autofocus
            class="cg-input w-full h-10 px-3.5 rounded-xl border border-slate-200/90 bg-slate-50/50 focus:bg-white text-sm text-slate-900"
          />
        </div>
        <button
          type="submit"
          class="cg-btn-primary w-full h-10 mt-2 rounded-xl font-semibold text-sm cursor-pointer"
        >
          {{ t('登 录') }}
        </button>
      </form>
    </div>
  </div>

  <!-- Dashboard View: Bright, airy, high-craft light-green SaaS console -->
  <div v-else class="min-h-screen text-slate-900 flex flex-col">
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
        class="fixed top-18 right-6 z-50 max-w-md rounded-2xl px-4 py-3 shadow-[0_10px_30px_-8px_rgba(15,23,42,0.14)] border flex items-center gap-2.5 text-sm font-medium bg-white/95 backdrop-blur-md"
        :class="
          toast.ok
            ? 'border-emerald-200/90 text-emerald-950'
            : 'border-rose-200/90 text-rose-950'
        "
      >
        <span
          class="w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold shrink-0"
          :class="toast.ok ? 'bg-emerald-500 text-white' : 'bg-rose-500 text-white'"
        >
          {{ toast.ok ? '✓' : '!' }}
        </span>
        <span class="break-all leading-snug">{{ toast.msg }}</span>
      </div>
    </transition>

    <!-- In-Panel Confirmation Modal -->
    <Transition name="cg-modal">
      <div
        v-if="confirmDialog.show"
        id="confirm-modal"
        class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/25 backdrop-blur-[2px]"
        @click.self="closeConfirmDialog"
      >
        <div
          class="cg-modal-panel w-full max-w-md bg-white rounded-2xl border border-slate-200/90 p-6 shadow-[0_20px_50px_-12px_rgba(15,23,42,0.18)] space-y-4"
        >
          <div class="flex items-center justify-between gap-2">
            <h3 class="text-base font-bold text-slate-900 tracking-tight">{{ confirmDialog.title }}</h3>
            <button
              type="button"
              @click="closeConfirmDialog"
              class="text-slate-400 hover:text-slate-600 hover:bg-slate-100 text-sm w-7 h-7 flex items-center justify-center rounded-lg transition cursor-pointer"
            >
              ✕
            </button>
          </div>
          <p class="text-sm text-slate-600 leading-relaxed">{{ confirmDialog.message }}</p>
          <div class="flex items-center justify-end gap-2.5 pt-2">
            <button
              type="button"
              @click="closeConfirmDialog"
              class="px-4 py-2 rounded-xl text-xs font-medium bg-slate-100 hover:bg-slate-200/80 text-slate-700 transition cursor-pointer"
            >
              {{ t('取消') }}
            </button>
            <button
              type="button"
              @click="acceptConfirmDialog"
              class="px-4 py-2 rounded-xl text-xs font-semibold transition cursor-pointer"
              :class="
                confirmDialog.tone === 'rose'
                  ? 'bg-rose-600 hover:bg-rose-500 text-white shadow-xs'
                  : confirmDialog.tone === 'emerald'
                    ? 'cg-btn-primary'
                    : 'bg-amber-500 hover:bg-amber-400 text-white shadow-xs'
              "
            >
              {{ confirmDialog.confirmText || t('确认') }}
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Change Password Modal -->
    <Transition name="cg-modal">
      <div
        v-if="showPasswordModal"
        id="change-password-modal"
        class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/25 backdrop-blur-[2px]"
        @click.self="closePasswordModal"
      >
        <div
          class="cg-modal-panel w-full max-w-md bg-white rounded-2xl border border-emerald-100/90 p-6 shadow-[0_20px_50px_-12px_rgba(15,23,42,0.18)] space-y-4"
        >
          <div class="flex items-start justify-between gap-2">
            <div>
              <h3 class="text-base font-bold text-slate-900 tracking-tight">{{ t('修改面板密码') }}</h3>
              <p class="text-xs text-slate-500 mt-1">{{ t('更新管理员账号 admin 的登录密码，修改后当前会话保持有效。') }}</p>
            </div>
            <button
              type="button"
              @click="closePasswordModal"
              class="text-slate-400 hover:text-slate-600 hover:bg-slate-100 text-sm w-7 h-7 flex items-center justify-center rounded-lg transition cursor-pointer"
            >
              ✕
            </button>
          </div>

          <form @submit.prevent="submitChangePassword" class="space-y-3.5 pt-1">
            <div>
              <label for="cp-current" class="block text-xs font-semibold text-slate-700 mb-1.5">{{ t('当前密码') }}</label>
              <input
                id="cp-current"
                v-model="passwordForm.current_password"
                name="current_password"
                type="password"
                autocomplete="current-password"
                :placeholder="t('请输入当前密码')"
                required
                class="cg-input w-full h-10 px-3.5 rounded-xl border border-slate-200 bg-slate-50/50 focus:bg-white text-sm text-slate-900"
              />
            </div>
            <div>
              <label for="cp-new" class="block text-xs font-semibold text-slate-700 mb-1.5">{{ t('新密码') }}</label>
              <input
                id="cp-new"
                v-model="passwordForm.new_password"
                name="new_password"
                type="password"
                autocomplete="new-password"
                :placeholder="t('请输入新密码（至少 8 位）')"
                required
                class="cg-input w-full h-10 px-3.5 rounded-xl border border-slate-200 bg-slate-50/50 focus:bg-white text-sm text-slate-900"
              />
            </div>
            <div>
              <label for="cp-confirm" class="block text-xs font-semibold text-slate-700 mb-1.5">{{ t('确认新密码') }}</label>
              <input
                id="cp-confirm"
                v-model="passwordForm.confirm_password"
                name="confirm_password"
                type="password"
                autocomplete="new-password"
                :placeholder="t('请再次输入新密码')"
                required
                class="cg-input w-full h-10 px-3.5 rounded-xl border border-slate-200 bg-slate-50/50 focus:bg-white text-sm text-slate-900"
              />
            </div>
            <div class="flex items-center justify-end gap-2.5 pt-2">
              <button
                type="button"
                @click="closePasswordModal"
                class="px-4 py-2 rounded-xl text-xs font-medium bg-slate-100 hover:bg-slate-200/80 text-slate-700 transition cursor-pointer"
              >
                {{ t('取消') }}
              </button>
              <button
                type="submit"
                :disabled="busyKey === '/action/change-password'"
                class="cg-btn-primary px-4 py-2 rounded-xl text-xs font-semibold disabled:opacity-50 cursor-pointer"
              >
                {{ busyKey === '/action/change-password' ? t('保存中…') : t('确认修改') }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </Transition>

    <!-- Subscription QR Code Modal (only for sub_url) -->
    <Transition name="cg-modal">
      <div
        v-if="showSubQrModal && state.sub_url && state.sub_qr_data_url"
        id="sub-qr-modal"
        class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/25 backdrop-blur-[2px]"
        @click.self="showSubQrModal = false"
      >
        <div
          class="cg-modal-panel w-full max-w-sm bg-white rounded-2xl border border-emerald-100/90 p-6 shadow-[0_20px_50px_-12px_rgba(15,23,42,0.18)] space-y-4"
        >
          <div class="flex items-center justify-between gap-2">
            <h3 class="text-base font-bold text-slate-900 tracking-tight">{{ t('订阅二维码') }}</h3>
            <button
              type="button"
              @click="showSubQrModal = false"
              class="text-slate-400 hover:text-slate-600 hover:bg-slate-100 text-sm w-7 h-7 flex items-center justify-center rounded-lg transition cursor-pointer"
            >
              ✕
            </button>
          </div>
          <div class="flex flex-col items-center gap-3 py-2">
            <img
              id="sub-qr"
              :src="state.sub_qr_data_url"
              :alt="t('订阅二维码')"
              class="w-48 h-48 rounded-2xl bg-white p-2.5 border border-emerald-200/80 shadow-xs"
            />
            <p class="text-xs text-slate-500 text-center">{{ t('扫码导入 Clash / Mihomo 订阅') }}</p>
          </div>
          <div class="flex items-center justify-end gap-2 pt-1">
            <button
              type="button"
              @click="copyRaw(state.sub_url, 'sub-url-modal')"
              class="px-3.5 py-2 rounded-xl text-xs font-semibold bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-200/80 transition cursor-pointer"
            >
              {{ copiedKey === 'sub-url-modal' ? t('已复制') : t('复制订阅链接') }}
            </button>
            <button
              type="button"
              @click="showSubQrModal = false"
              class="px-4 py-2 rounded-xl text-xs font-medium bg-slate-100 hover:bg-slate-200/80 text-slate-700 transition cursor-pointer"
            >
              {{ t('关闭') }}
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Frosted Topbar -->
    <header class="sticky top-0 z-30 bg-white/85 backdrop-blur-md border-b border-slate-200/80 text-slate-900">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
        <div class="flex items-center gap-3">
          <img
            src="/assets/logo.png"
            alt="ClashGate"
            class="w-9 h-9 rounded-xl object-cover shadow-xs shadow-emerald-500/15 ring-1 ring-emerald-500/10 bg-white"
          />
          <span class="font-bold text-base tracking-tight text-slate-900">ClashGate</span>
          <span
            class="px-2.5 py-0.5 text-[11px] font-semibold rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200/80 tabular-nums"
          >
            {{ topbarVersionText }}
          </span>
        </div>

        <div class="flex items-center gap-2 flex-wrap">
          <button
            type="button"
            :disabled="busyKey === '/action/update-core'"
            @click="updateCoreDirect"
            class="cg-btn-primary px-3.5 py-1.5 rounded-xl text-xs font-semibold disabled:opacity-50 cursor-pointer"
          >
            {{ busyKey === '/action/update-core' ? t('更新内核中…') : t('更新内核') }}
          </button>
          <button
            type="button"
            :disabled="busyKey === '/action/reload'"
            @click="postAction('/action/reload', {}, '/action/reload')"
            class="px-3.5 py-1.5 rounded-xl text-xs font-semibold border disabled:opacity-50 transition cursor-pointer inline-flex items-center gap-1.5"
            :class="
              state.pending_reload_count > 0
                ? 'bg-amber-50 hover:bg-amber-100/80 border-amber-300/90 text-amber-900'
                : 'bg-emerald-50/90 hover:bg-emerald-100/80 border-emerald-200/80 text-emerald-800'
            "
          >
            <span>{{ busyKey === '/action/reload' ? t('重载中…') : t('重载配置') }}</span>
            <span
              v-if="state.pending_reload_count > 0"
              class="px-1.5 py-0.2 text-[10px] font-bold rounded-full bg-amber-500 text-white tabular-nums"
            >
              {{ state.pending_reload_count }}
            </span>
          </button>
          <button
            type="button"
            :disabled="busyKey === '/action/check-update' || busyKey === '/action/upgrade-self'"
            @click="checkUpdateAndPrompt"
            class="px-3 py-1.5 rounded-xl text-xs font-medium bg-white hover:bg-slate-50 border border-slate-200/90 disabled:opacity-50 text-slate-700 transition cursor-pointer"
          >
            {{
              busyKey === '/action/upgrade-self'
                ? t('升级中…')
                : busyKey === '/action/check-update'
                  ? t('检查中…')
                  : t('检查更新')
            }}
          </button>
          <button
            id="change-password-btn"
            type="button"
            @click="openPasswordModal"
            class="px-3 py-1.5 rounded-xl text-xs font-medium bg-white hover:bg-emerald-50/70 hover:text-emerald-800 hover:border-emerald-200 border border-slate-200/90 text-slate-700 transition cursor-pointer"
          >
            {{ t('修改密码') }}
          </button>
          <button
            type="button"
            @click="setLang(lang === 'zh' ? 'en' : 'zh')"
            class="px-3 py-1.5 rounded-xl text-xs font-medium bg-white hover:bg-emerald-50/70 border border-slate-200/90 text-slate-600 transition cursor-pointer"
            :title="lang === 'zh' ? 'Switch to English' : '切换到中文'"
          >
            {{ lang === 'zh' ? 'English' : '中文' }}
          </button>
          <form method="post" action="/logout" class="inline">
            <input type="hidden" name="csrf" :value="state.csrf" />
            <button
              type="submit"
              class="px-3 py-1.5 rounded-xl text-xs font-medium bg-white hover:bg-rose-50 hover:text-rose-600 hover:border-rose-200 border border-slate-200/90 text-slate-600 transition cursor-pointer"
            >
              {{ t('退出') }}
            </button>
          </form>
        </div>
      </div>
    </header>

    <!-- Main Container -->
    <main class="max-w-7xl w-full mx-auto px-4 sm:px-6 py-6 sm:py-7 space-y-6 flex-1">
      <!-- Concise 4-Card Status Strip -->
      <div class="space-y-3">
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <!-- Card 1: 运行状态 -->
          <div
            id="stat-card-status"
            class="cg-surface cg-stat-card cg-stat-delay-1 rounded-2xl p-4 sm:p-5 flex items-center justify-between gap-2"
          >
            <div>
              <div class="text-xs font-medium text-slate-500">{{ t('运行状态') }}</div>
              <div class="mt-2 flex items-center gap-2">
                <span
                  class="w-2.5 h-2.5 rounded-full"
                  :class="{
                    'bg-emerald-500 ring-4 ring-emerald-500/15': state.status.state_cls === 'ok',
                    'bg-amber-500 ring-4 ring-amber-500/15': state.status.state_cls === 'warn',
                    'bg-rose-500 ring-4 ring-rose-500/15':
                      state.status.state_cls !== 'ok' && state.status.state_cls !== 'warn',
                  }"
                ></span>
                <span class="text-lg font-bold text-slate-900 tracking-tight">{{ t(state.status.state_txt || '未知') }}</span>
              </div>
            </div>
            <span
              class="px-2.5 py-1 text-xs font-semibold rounded-lg shrink-0"
              :class="
                state.custom_config_mode
                  ? 'bg-amber-50 text-amber-700 border border-amber-200/70'
                  : 'bg-emerald-50 text-emerald-700 border border-emerald-200/70'
              "
            >
              {{ state.custom_config_mode ? t('自定义模式') : t('标准模板') }}
            </span>
          </div>

          <!-- Card 2: 入站 · 出站（合并卡） -->
          <div
            id="stat-card-nodes"
            class="cg-surface cg-stat-card cg-stat-delay-2 rounded-2xl p-4 sm:p-5"
          >
            <div class="text-xs font-medium text-slate-500">{{ t('入站 · 出站') }}</div>
            <div class="mt-2 space-y-1 text-xs text-slate-600 tabular-nums">
              <div class="flex items-baseline gap-1.5">
                <span class="text-slate-400">{{ t('入站：') }}</span>
                <span class="text-sm font-bold text-slate-900">{{ state.inbounds.length }}</span>
                <span>{{ t('个节点运行中') }}</span>
              </div>
              <div class="flex items-baseline gap-1.5">
                <span class="text-slate-400">{{ t('出站：') }}</span>
                <span class="text-sm font-bold text-slate-900">{{ state.status.outbound_nodes_count ?? 0 }}</span>
                <span>{{ t('节点 ·') }} {{ state.status.outbound_providers_count ?? 0 }} {{ t('订阅源') }}</span>
              </div>
            </div>
          </div>

          <!-- Card 3: 待重载配置 -->
          <div
            id="stat-card-pending-reload"
            role="button"
            tabindex="0"
            @click="showPendingDiff = !showPendingDiff"
            @keydown.enter.prevent="showPendingDiff = !showPendingDiff"
            class="cg-stat-card cg-stat-delay-3 rounded-2xl border p-4 sm:p-5 transition cursor-pointer select-none flex items-center justify-between gap-2"
            :class="
              state.pending_reload_count > 0
                ? 'bg-amber-50/90 border-amber-300/90 shadow-[0_4px_16px_-6px_rgba(245,158,11,0.2)] hover:bg-amber-50'
                : 'cg-surface hover:border-emerald-200/90'
            "
          >
            <div>
              <div class="text-xs font-medium" :class="state.pending_reload_count > 0 ? 'text-amber-800' : 'text-slate-500'">
                {{ t('待重载配置') }}
              </div>
              <div class="mt-2 flex items-baseline gap-1.5 tabular-nums">
                <span
                  id="pending-reload-count"
                  class="text-lg font-bold tracking-tight"
                  :class="state.pending_reload_count > 0 ? 'text-amber-900' : 'text-slate-900'"
                >
                  {{ state.pending_reload_count }}
                </span>
                <span
                  class="text-xs"
                  :class="state.pending_reload_count > 0 ? 'text-amber-700 font-medium' : 'text-slate-500'"
                >
                  {{ state.pending_reload_count > 0 ? t('项待重载生效') : t('无待生效') }}
                </span>
              </div>
            </div>
            <span
              v-if="state.pending_reload_count > 0"
              class="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-full bg-amber-100/90 text-amber-800 border border-amber-300/80 shrink-0"
            >
              <span class="w-1.5 h-1.5 rounded-full bg-amber-500"></span>
              {{ showPendingDiff ? t('收起') : t('点击展开变更') }}
            </span>
          </div>

          <!-- Card 4: 已代理流量 -->
          <div
            id="stat-card-traffic"
            class="cg-surface cg-stat-card cg-stat-delay-4 rounded-2xl p-4 sm:p-5"
          >
            <div class="text-xs font-medium text-slate-500">{{ t('已代理流量') }}</div>
            <div class="mt-2 flex items-baseline gap-2 tabular-nums">
              <span class="text-lg font-bold text-slate-900 tracking-tight">{{ trafficDisplay }}</span>
              <span class="text-xs text-slate-400 truncate">{{ trafficDetail }}</span>
            </div>
          </div>
        </div>

        <!-- Expandable Pending Reload Diff Panel -->
        <Transition name="cg-collapse">
          <div
            v-if="showPendingDiff"
            id="pending-reload-diff-panel"
            class="rounded-2xl border px-4 py-3.5 text-xs space-y-2.5"
            :class="
              state.pending_reload_count > 0
                ? 'bg-amber-50/90 border-amber-200/90 text-amber-950 shadow-xs'
                : 'bg-white border-slate-200/80 text-slate-600 shadow-xs'
            "
          >
            <div class="flex items-center justify-between gap-2 flex-wrap">
              <div class="font-semibold flex items-center gap-2">
                <span
                  class="w-2 h-2 rounded-full"
                  :class="state.pending_reload_count > 0 ? 'bg-amber-500' : 'bg-emerald-500'"
                ></span>
                <span>{{ t('待生效变更明细') }}（{{ state.pending_reload_count }}）</span>
              </div>
              <div class="flex items-center gap-2 flex-wrap">
                <button
                  v-if="state.pending_reload_count > 0"
                  id="discard-pending-btn"
                  type="button"
                  :disabled="busyKey === '/action/discard-pending' || busyKey === '/action/reload'"
                  @click="confirmDiscardPending"
                  class="px-3 py-1 rounded-lg text-xs font-semibold bg-white hover:bg-rose-50 text-rose-600 border border-rose-200/90 disabled:opacity-50 transition cursor-pointer"
                >
                  {{ busyKey === '/action/discard-pending' ? t('丢弃中…') : t('丢弃草稿') }}
                </button>
              </div>
            </div>
            <div v-if="state.pending_reload_items && state.pending_reload_items.length > 0" class="space-y-1 font-mono">
              <div
                v-for="(it, idx) in state.pending_reload_items"
                :key="idx"
                class="px-3 py-1.5 rounded-xl bg-white/95 border border-amber-200/60 text-slate-800 flex items-center gap-2"
              >
                <span>{{ formatPendingItem(it) }}</span>
              </div>
            </div>
            <div v-else class="text-slate-500">
              {{ t('无待生效') }}
            </div>
          </div>
        </Transition>
      </div>

      <!-- Segmented Navigation Bar -->
      <div
        class="flex items-center gap-1 bg-white/95 p-1.5 rounded-2xl border border-slate-200/85 shadow-[0_1px_2px_rgba(15,23,42,0.03)] flex-wrap w-fit"
      >
        <button
          type="button"
          @click="selectTab('inbounds')"
          class="px-4 py-2 rounded-xl text-sm font-semibold transition cursor-pointer"
          :class="
            activeTab === 'inbounds'
              ? 'cg-btn-primary'
              : 'text-slate-600 hover:text-emerald-800 hover:bg-emerald-50/60'
          "
        >
          {{ t('首页 · 入站与面板') }}
        </button>
        <button
          type="button"
          @click="selectTab('outbounds')"
          class="px-4 py-2 rounded-xl text-sm font-semibold transition cursor-pointer"
          :class="
            activeTab === 'outbounds'
              ? 'cg-btn-primary'
              : 'text-slate-600 hover:text-emerald-800 hover:bg-emerald-50/60'
          "
        >
          {{ t('服务端出站') }}
        </button>
        <button
          type="button"
          @click="selectTab('readable')"
          class="px-4 py-2 rounded-xl text-sm font-semibold transition cursor-pointer"
          :class="
            activeTab === 'readable'
              ? 'cg-btn-primary'
              : 'text-slate-600 hover:text-emerald-800 hover:bg-emerald-50/60'
          "
        >
          {{ t('易读配置转换') }}
        </button>
        <button
          type="button"
          @click="selectTab('advanced')"
          class="px-4 py-2 rounded-xl text-sm font-semibold transition cursor-pointer"
          :class="
            activeTab === 'advanced'
              ? 'cg-btn-primary'
              : 'text-slate-600 hover:text-emerald-800 hover:bg-emerald-50/60'
          "
        >
          {{ t('自定义服务端配置') }}
        </button>
        <button
          id="tab-certs"
          type="button"
          @click="selectTab('certs')"
          class="px-4 py-2 rounded-xl text-sm font-semibold transition cursor-pointer"
          :class="
            activeTab === 'certs'
              ? 'cg-btn-primary'
              : 'text-slate-600 hover:text-emerald-800 hover:bg-emerald-50/60'
          "
        >
          {{ t('HTTPS 证书') }}
        </button>
      </div>

      <!-- TAB 1 (HOMEPAGE): Zashboard + 客户端订阅 + 入站节点与添加节点 -->
      <Transition name="cg-tab">
        <div v-show="activeTab === 'inbounds'" class="space-y-6">
          <!-- Top Fixed Core Cards: Zashboard 控制面板 & 客户端订阅链接 -->
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 items-stretch">
            <!-- Zashboard 控制面板 -->
            <section
              id="zashboard-card"
              class="cg-surface-emerald rounded-2xl p-5 sm:p-6 flex flex-col gap-3.5"
            >
              <div class="flex items-center justify-between gap-3 flex-wrap">
                <div class="flex items-center gap-2.5">
                  <span class="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
                  <h2 class="text-base font-bold text-slate-900">{{ t('Zashboard 控制面板') }}</h2>
                  <span
                    class="inline-flex items-center gap-1 px-2.5 py-0.5 text-xs font-semibold rounded-full tabular-nums"
                    :class="
                      state.controller_listening
                        ? 'bg-emerald-50 text-emerald-700 border border-emerald-200/70'
                        : 'bg-amber-50 text-amber-700 border border-amber-200/70'
                    "
                  >
                    {{ t('端口 :') }}{{ state.controller_port }} {{ state.controller_listening ? t('运行中') : t('未运行') }}
                  </span>
                </div>
                <div class="flex items-center gap-2 flex-wrap">
                  <a
                    :href="state.zb_url || '#'"
                    target="_blank"
                    rel="noopener"
                    class="cg-btn-primary px-3.5 py-1.5 rounded-xl text-xs font-semibold"
                  >
                    {{ t('打开 Zashboard') }}
                  </a>
                  <button
                    type="button"
                    @click="copyRaw(state.zb_url, 'zb-url')"
                    class="px-3 py-1.5 rounded-xl text-xs font-semibold bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-200/80 transition cursor-pointer"
                  >
                    {{ copiedKey === 'zb-url' ? t('已复制地址') : t('复制地址') }}
                  </button>
                  <a
                    href="/config/server.yaml"
                    target="_blank"
                    rel="noopener"
                    class="px-3 py-1.5 rounded-xl text-xs font-medium bg-slate-100 hover:bg-slate-200/80 text-slate-700 transition"
                  >
                    {{ t('查看Mihomo服务端配置') }}
                  </a>
                </div>
              </div>

              <div>
                <div class="text-xs font-medium text-slate-500 mb-1.5">{{ t('免填密钥直连地址 (HTTPS)') }}</div>
                <div
                  id="zb-url"
                  ref="zbUrlEl"
                  tabindex="0"
                  role="button"
                  :aria-expanded="zbUrlRevealed ? 'true' : 'false'"
                  @click="revealZbUrl"
                  @keydown.enter.prevent="zbUrlRevealed = !zbUrlRevealed"
                  @keydown.space.prevent="zbUrlRevealed = !zbUrlRevealed"
                  @blur="zbUrlRevealed = false"
                  class="cg-input px-3.5 py-2.5 rounded-xl bg-[#f6faf8] hover:bg-emerald-50/50 border border-emerald-100 font-mono text-xs transition cursor-pointer"
                  :class="zbUrlRevealed ? 'text-slate-700 break-all select-all' : 'text-slate-500 tracking-widest select-none'"
                >
                  {{ !state.zb_url ? '—' : zbUrlRevealed ? state.zb_url : '••••••••••••••••••••••••••••••••' }}
                </div>
              </div>

              <div class="mt-auto pt-0.5 min-h-[28px] flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div class="flex items-center gap-2 min-w-0">
                  <span class="text-xs font-medium text-slate-500 shrink-0">{{ t('API 密钥 (Secret)：') }}</span>
                  <code
                    id="zb-secret"
                    ref="zbSecretEl"
                    tabindex="0"
                    role="button"
                    :aria-expanded="zbSecretRevealed ? 'true' : 'false'"
                    @click="revealZbSecret"
                    @keydown.enter.prevent="zbSecretRevealed = !zbSecretRevealed"
                    @keydown.space.prevent="zbSecretRevealed = !zbSecretRevealed"
                    @blur="zbSecretRevealed = false"
                    class="cg-input px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-emerald-50/60 font-mono text-xs transition cursor-pointer"
                    :class="zbSecretRevealed ? 'text-slate-800 break-all select-all' : 'text-slate-500 tracking-widest select-none'"
                  >
                    {{ !state.mihomo_secret ? '—' : zbSecretRevealed ? state.mihomo_secret : '••••••••••••' }}
                  </code>
                </div>
                <div class="flex items-center gap-2 shrink-0">
                  <button
                    v-if="state.mihomo_secret"
                    type="button"
                    @click="copyRaw(state.mihomo_secret, 'zb-secret')"
                    class="px-2.5 py-1 rounded-lg text-xs font-medium bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 transition cursor-pointer"
                  >
                    {{ copiedKey === 'zb-secret' ? t('已复制') : t('复制密钥') }}
                  </button>
                  <button
                    type="button"
                    :disabled="busyKey === 'reset-secret'"
                    @click="resetZbSecret"
                    class="px-2.5 py-1 rounded-lg text-xs font-medium bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-200/80 disabled:opacity-50 transition cursor-pointer"
                  >
                    {{ busyKey === 'reset-secret' ? t('重置中…') : t('重置 API 密钥') }}
                  </button>
                </div>
              </div>
            </section>

            <!-- 客户端订阅链接 -->
            <section
              id="sub-card"
              class="cg-surface-emerald rounded-2xl p-5 sm:p-6 flex flex-col gap-3.5"
            >
              <div class="flex items-center justify-between gap-3 flex-wrap">
                <div class="flex items-center gap-2.5">
                  <span class="w-2.5 h-2.5 rounded-full bg-teal-500"></span>
                  <h2 class="text-base font-bold text-slate-900">{{ t('客户端订阅链接') }}</h2>
                  <span
                    class="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200/70"
                  >
                    {{ t('ACL4SSR 自动同步') }}
                  </span>
                </div>
                <div v-if="state.sub_url" class="flex items-center gap-2 flex-wrap">
                  <button
                    type="button"
                    @click="copyRaw(state.sub_url, 'sub-url')"
                    class="cg-btn-primary px-3.5 py-1.5 rounded-xl text-xs font-semibold cursor-pointer"
                  >
                    {{ copiedKey === 'sub-url' ? t('已复制') : t('复制订阅链接') }}
                  </button>
                  <button
                    v-if="state.sub_url && state.sub_qr_data_url"
                    id="sub-qr-btn"
                    type="button"
                    @click="showSubQrModal = true"
                    class="px-3 py-1.5 rounded-xl text-xs font-semibold bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-200/80 transition cursor-pointer"
                  >
                    {{ t('二维码') }}
                  </button>
                  <button
                    type="button"
                    :disabled="busyKey === 'reset-sub'"
                    @click="resetSubUrl"
                    class="px-3 py-1.5 rounded-xl text-xs font-semibold bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-200/80 disabled:opacity-50 transition cursor-pointer"
                  >
                    {{ busyKey === 'reset-sub' ? t('更换中…') : t('更换订阅链接') }}
                  </button>
                  <a
                    :href="state.sub_url"
                    target="_blank"
                    rel="noopener"
                    class="px-3 py-1.5 rounded-xl text-xs font-medium bg-slate-100 hover:bg-slate-200/80 text-slate-700 transition"
                  >
                    {{ t('预览') }}
                  </a>
                </div>
              </div>

              <div>
                <div class="text-xs font-medium text-slate-500 mb-1.5">
                  {{ t('导入 Clash / Mihomo 客户端即可使用') }}
                </div>
                <div
                  id="sub-url"
                  ref="subUrlEl"
                  tabindex="0"
                  role="button"
                  :aria-expanded="subUrlRevealed ? 'true' : 'false'"
                  @click="revealSubUrl"
                  @keydown.enter.prevent="subUrlRevealed = !subUrlRevealed"
                  @keydown.space.prevent="subUrlRevealed = !subUrlRevealed"
                  @blur="subUrlRevealed = false"
                  class="cg-input px-3.5 py-2.5 rounded-xl bg-[#f6faf8] hover:bg-emerald-50/50 border border-emerald-100 font-mono text-xs transition cursor-pointer"
                  :class="subUrlRevealed ? 'text-slate-700 break-all select-all' : 'text-slate-500 tracking-widest select-none'"
                >
                  {{ !state.sub_url ? '/etc/clashgate/client/mihomo-client.yaml' : subUrlRevealed ? state.sub_url : '••••••••••••••••••••••••••••••••' }}
                </div>
              </div>

              <div class="mt-auto pt-0.5 min-h-[28px] text-xs text-slate-500 flex items-center justify-between gap-2 flex-wrap">
                <div class="flex items-center gap-1.5">
                  <span>{{ t('本地客户端备份：') }}</span>
                  <code class="px-2.5 py-1 rounded-lg bg-slate-100 text-slate-700 font-mono text-xs">/etc/clashgate/client/</code>
                </div>
                <button
                  type="button"
                  @click="selectTab('readable')"
                  class="text-emerald-700 hover:text-emerald-600 font-semibold cursor-pointer"
                >
                  {{ t('前往易读配置转换 →') }}
                </button>
              </div>
            </section>
          </div>

          <!-- 入站节点列表 & 添加节点表单 -->
          <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            <!-- Left: Inbound Nodes List -->
            <section class="lg:col-span-7 cg-surface rounded-2xl p-5 sm:p-6">
              <div class="flex items-center justify-between gap-2 mb-4">
                <div class="flex items-center gap-2.5">
                  <h2 class="text-base font-bold text-slate-900 tracking-tight">{{ t('入站节点') }}</h2>
                  <span
                    class="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200/60 tabular-nums"
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
                    {{ copiedKey === 'all-proxies' ? t('已复制全部') : t('复制全部配置') }}
                  </button>
                </div>
              </div>

              <div
                v-if="state.inbounds.length === 0"
                class="py-12 px-4 rounded-2xl border border-dashed border-slate-200 bg-slate-50/40 text-center text-sm text-slate-400"
              >
                {{ t('暂无入站节点，请在右侧添加节点') }}
              </div>

              <div v-else class="divide-y divide-slate-100 border border-slate-200/80 rounded-2xl overflow-hidden">
                <div
                  v-for="item in state.inbounds"
                  :key="item.key"
                  class="p-4 hover:bg-emerald-50/35 transition flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                >
                  <div class="space-y-1 min-w-0">
                    <div class="flex items-center gap-2 flex-wrap">
                      <span class="font-bold text-sm text-slate-900 break-all">{{ item.name }}</span>
                      <span
                        class="px-2 py-0.5 text-[11px] font-semibold rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200/60"
                      >
                        {{ item.kind_label }}
                      </span>
                      <span
                        class="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-medium rounded-full"
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
                        {{ item.listening ? t('运行中') : item.pending_reload ? t('重载配置生效') : t('未运行') }}
                      </span>
                    </div>
                    <div class="text-xs text-slate-500 font-mono tabular-nums">{{ t('端口 :') }}{{ item.port }}</div>
                  </div>

                  <!-- Actions: 复制配置 + 重置密码 + 删除 -->
                  <div class="flex items-center gap-2 shrink-0 flex-wrap">
                    <button
                      type="button"
                      @click="copyRaw(item.single_config, `single-${item.key}`)"
                      class="px-3 py-1.5 rounded-xl text-xs font-medium bg-white hover:bg-emerald-50 hover:text-emerald-800 hover:border-emerald-200 text-slate-700 border border-slate-200/90 transition cursor-pointer"
                    >
                      {{ copiedKey === `single-${item.key}` ? t('已复制') : t('复制配置') }}
                    </button>
                    <button
                      v-if="item.can_reset_password"
                      type="button"
                      :disabled="busyKey === `rst-${item.key}`"
                      @click="resetInboundPassword(item)"
                      class="px-3 py-1.5 rounded-xl text-xs font-medium bg-amber-50/80 hover:bg-amber-100 text-amber-800 border border-amber-200/80 disabled:opacity-50 transition cursor-pointer"
                    >
                      {{ busyKey === `rst-${item.key}` ? t('重置中…') : t('重置密码') }}
                    </button>
                    <button
                      type="button"
                      :disabled="busyKey === `del-${item.key}`"
                      @click="deleteInbound(item)"
                      class="px-3 py-1.5 rounded-xl text-xs font-medium text-rose-600 hover:bg-rose-50 border border-rose-200/80 disabled:opacity-50 transition cursor-pointer"
                    >
                      {{ t('删除') }}
                    </button>
                  </div>
                </div>
              </div>
            </section>

            <!-- Right: Locked-Default Add Node Form -->
            <section class="lg:col-span-5 cg-surface rounded-2xl p-5 sm:p-6">
              <div class="flex items-center justify-between gap-2 mb-4">
                <h2 class="text-base font-bold text-slate-900 tracking-tight">{{ t('添加节点') }}</h2>
                <span class="px-2.5 py-0.5 text-xs font-medium rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200/60">
                  {{ t('安全默认策略') }}
                </span>
              </div>

              <form @submit.prevent="submitAddInbound" class="space-y-4">
                <div>
                  <label for="kind" class="block text-xs font-semibold text-slate-700 mb-1.5">{{ t('协议类型') }}</label>
                  <select
                    id="kind"
                    v-model="inboundForm.kind"
                    name="kind"
                    class="cg-input w-full h-10 px-3 rounded-xl border border-slate-200 bg-white text-sm text-slate-900"
                  >
                    <option v-for="p in PROTOCOLS" :key="p.value" :value="p.value">
                      {{ p.label }}
                    </option>
                  </select>
                  <p id="protocol-desc" class="mt-2 text-xs font-medium text-emerald-700 flex items-center gap-1.5">
                    <span class="inline-block w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0"></span>
                    <span>{{ currentProtocol.label }}：{{ t(currentProtocol.desc) }}</span>
                  </p>
                </div>

                <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label for="nm" class="block text-xs font-semibold text-slate-700 mb-1.5">{{ t('节点名称') }}</label>
                    <input
                      id="nm"
                      v-model="inboundForm.name"
                      name="name"
                      :placeholder="t('默认 {name}', { name: currentDefaultName })"
                      class="cg-input w-full h-10 px-3 rounded-xl border border-slate-200 bg-white text-sm text-slate-900"
                    />
                  </div>
                  <div>
                    <label for="port" class="block text-xs font-semibold text-slate-700 mb-1.5">{{ t('监听端口') }}</label>
                    <input
                      id="port"
                      v-model="inboundForm.port"
                      name="port"
                      inputmode="numeric"
                      :placeholder="t('留空随机端口')"
                      class="cg-input w-full h-10 px-3 rounded-xl border border-slate-200 bg-white text-sm text-slate-900 tabular-nums"
                    />
                  </div>
                </div>

                <!-- Non-locked protocol options (TUIC / TrustTunnel / Mieru / HTTP / SOCKS5) -->
                <template v-if="inboundForm.kind === 'tuic'">
                  <div>
                    <label class="block text-xs font-semibold text-slate-700 mb-1.5">{{ t('拥塞控制') }}</label>
                    <select
                      v-model="inboundForm.tuic_cc"
                      name="tuic_cc"
                      class="cg-input w-full h-10 px-3 rounded-xl border border-slate-200 bg-white text-sm text-slate-900"
                    >
                      <option value="bbr">{{ t('bbr (默认)') }}</option>
                      <option value="cubic">cubic</option>
                      <option value="new_reno">new_reno</option>
                    </select>
                  </div>
                </template>

                <template v-else-if="inboundForm.kind === 'trusttunnel'">
                  <div>
                    <label class="block text-xs font-semibold text-slate-700 mb-1.5">{{ t('拥塞控制') }}</label>
                    <select
                      v-model="inboundForm.tt_cc"
                      name="tt_cc"
                      class="cg-input w-full h-10 px-3 rounded-xl border border-slate-200 bg-white text-sm text-slate-900"
                    >
                      <option value="bbr">{{ t('bbr (默认)') }}</option>
                      <option value="cubic">cubic</option>
                    </select>
                  </div>
                </template>

                <template v-else-if="inboundForm.kind === 'mieru'">
                  <div>
                    <label class="block text-xs font-semibold text-slate-700 mb-1.5">{{ t('传输协议') }}</label>
                    <select
                      v-model="inboundForm.mieru_transport"
                      name="mieru_transport"
                      class="cg-input w-full h-10 px-3 rounded-xl border border-slate-200 bg-white text-sm text-slate-900"
                    >
                      <option value="TCP">{{ t('TCP (默认)') }}</option>
                      <option value="UDP">UDP</option>
                    </select>
                  </div>
                </template>

                <template v-else-if="inboundForm.kind === 'http'">
                  <div>
                    <label class="block text-xs font-semibold text-slate-700 mb-1.5">{{ t('启用 TLS') }}</label>
                    <select
                      v-model="inboundForm.http_tls"
                      name="http_tls"
                      class="cg-input w-full h-10 px-3 rounded-xl border border-slate-200 bg-white text-sm text-slate-900"
                    >
                      <option value="0">{{ t('不启用 (默认)') }}</option>
                      <option value="1">{{ t('启用') }}</option>
                    </select>
                  </div>
                </template>

                <template v-else-if="inboundForm.kind === 'socks'">
                  <div>
                    <label class="block text-xs font-semibold text-slate-700 mb-1.5">{{ t('启用 TLS') }}</label>
                    <select
                      v-model="inboundForm.socks_tls"
                      name="socks_tls"
                      class="cg-input w-full h-10 px-3 rounded-xl border border-slate-200 bg-white text-sm text-slate-900"
                    >
                      <option value="0">{{ t('不启用 (默认)') }}</option>
                      <option value="1">{{ t('启用') }}</option>
                    </select>
                  </div>
                </template>

                <!-- Locked security defaults notice -->
                <div class="rounded-xl bg-[#f4fbf7] border border-emerald-200/70 px-3.5 py-2.5 text-xs text-emerald-900 leading-relaxed">
                  {{ t(currentProtocol.lockedNote) }}
                </div>

                <button
                  type="submit"
                  :disabled="busyKey === 'add-inbound'"
                  class="cg-btn-primary w-full h-10 mt-1 rounded-xl disabled:opacity-50 text-sm font-semibold cursor-pointer"
                >
                  {{ busyKey === 'add-inbound' ? t('正在添加…') : t('添加入站节点') }}
                </button>
              </form>
            </section>
          </div>
        </div>
      </Transition>

      <!-- TAB 2: 服务端出站与外部订阅 -->
      <Transition name="cg-tab">
        <div v-show="activeTab === 'outbounds'" class="space-y-6">
          <!-- 导入外部订阅 (proxy-providers) -->
          <section class="cg-surface rounded-2xl p-5 sm:p-6 space-y-4">
            <div class="flex items-center gap-2.5">
              <h2 class="text-base font-bold text-slate-900 tracking-tight">{{ t('外部订阅源 (proxy-providers)') }}</h2>
              <span
                class="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200/60 tabular-nums"
              >
                {{ state.providers.length }}
              </span>
            </div>

            <div
              v-if="state.providers.length === 0"
              class="py-6 px-4 rounded-2xl border border-dashed border-slate-200 bg-slate-50/40 text-center text-xs text-slate-400"
            >
              {{ t('暂无外部订阅源，在下方粘贴 HTTP/HTTPS 订阅链接即可导入') }}
            </div>

            <div
              v-else
              class="divide-y divide-slate-100 border border-slate-200/80 rounded-2xl overflow-hidden"
            >
              <div
                v-for="prov in state.providers"
                :key="prov.name"
                class="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-emerald-50/25 transition"
              >
                <div class="min-w-0 space-y-1">
                  <div class="flex items-center gap-2">
                    <span class="font-bold text-sm text-slate-900">{{ prov.name }}</span>
                    <span class="text-xs font-mono text-slate-500 bg-slate-100 px-2 py-0.5 rounded-md">{{ prov.path }}</span>
                  </div>
                  <div class="text-xs text-slate-400 font-mono truncate">{{ prov.url }}</div>
                </div>
                <div class="flex items-center gap-2 shrink-0">
                  <button
                    type="button"
                    @click="copyRaw(prov.yaml, `prov-${prov.name}`)"
                    class="px-3 py-1.5 rounded-xl text-xs font-medium bg-white hover:bg-emerald-50 text-slate-700 border border-slate-200/90 transition cursor-pointer"
                  >
                    {{ copiedKey === `prov-${prov.name}` ? t('已复制') : t('复制配置') }}
                  </button>
                  <button
                    type="button"
                    :disabled="busyKey === `del-prov-${prov.name}`"
                    @click="deleteProvider(prov.name)"
                    class="px-3 py-1.5 rounded-xl text-xs font-medium text-rose-600 hover:bg-rose-50 border border-rose-200/80 disabled:opacity-50 transition cursor-pointer"
                  >
                    {{ t('删除') }}
                  </button>
                </div>
              </div>
            </div>

            <form @submit.prevent="submitAddProvider" class="grid grid-cols-1 sm:grid-cols-12 gap-3 items-end">
              <div class="sm:col-span-7">
                <label class="block text-xs font-semibold text-slate-700 mb-1.5">{{ t('订阅链接 (HTTP / HTTPS)') }}</label>
                <input
                  v-model="providerForm.sub_url"
                  name="sub_url"
                  placeholder="https://example.com/sub.yaml?token=..."
                  required
                  class="cg-input w-full h-10 px-3 rounded-xl border border-slate-200 bg-white text-sm text-slate-900"
                />
              </div>
              <div class="sm:col-span-3">
                <label class="block text-xs font-semibold text-slate-700 mb-1.5">{{ t('名称 (选填)') }}</label>
                <input
                  v-model="providerForm.provider_name"
                  name="provider_name"
                  :placeholder="t('默认 sub')"
                  class="cg-input w-full h-10 px-3 rounded-xl border border-slate-200 bg-white text-sm text-slate-900"
                />
              </div>
              <div class="sm:col-span-2">
                <button
                  type="submit"
                  :disabled="busyKey === 'add-provider'"
                  class="cg-btn-primary w-full h-10 rounded-xl disabled:opacity-50 text-xs font-semibold cursor-pointer"
                >
                  {{ busyKey === 'add-provider' ? t('导入中…') : t('导入订阅') }}
                </button>
              </div>
            </form>
          </section>

          <!-- 服务端手工出站节点 (proxies) -->
          <section class="cg-surface rounded-2xl p-5 sm:p-6 space-y-4">
            <div class="flex items-center gap-2.5">
              <h2 class="text-base font-bold text-slate-900 tracking-tight">{{ t('服务端出站节点 (proxies)') }}</h2>
              <span
                class="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200/60 tabular-nums"
              >
                {{ state.proxies.length }}
              </span>
            </div>

            <div
              v-if="state.proxies.length === 0"
              class="py-6 px-4 rounded-2xl border border-dashed border-slate-200 bg-slate-50/40 text-center text-xs text-slate-400"
            >
              {{ t('暂无手工出站节点，在下方粘贴单行 JSON 或多行 YAML 即可添加') }}
            </div>

            <div
              v-else
              class="divide-y divide-slate-100 border border-slate-200/80 rounded-2xl overflow-hidden"
            >
              <div
                v-for="p in state.proxies"
                :key="p.name"
                class="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-emerald-50/25 transition"
              >
                <div class="space-y-1 min-w-0">
                  <div class="flex items-center gap-2 flex-wrap">
                    <span class="font-bold text-sm text-slate-900 break-all">{{ p.name }}</span>
                    <span
                      class="px-2 py-0.5 text-[11px] font-semibold rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200/60"
                    >
                      {{ p.type }}
                    </span>
                  </div>
                  <div class="text-xs text-slate-500 font-mono tabular-nums">{{ p.endpoint }}</div>
                </div>
                <div class="flex items-center gap-2 shrink-0 flex-wrap">
                  <button
                    type="button"
                    @click="copyRaw(p.single_config, `p-single-${p.name}`)"
                    class="px-3 py-1.5 rounded-xl text-xs font-medium bg-white hover:bg-emerald-50 text-slate-700 border border-slate-200/90 transition cursor-pointer"
                  >
                    {{ copiedKey === `p-single-${p.name}` ? t('已复制') : t('复制配置') }}
                  </button>
                  <button
                    type="button"
                    :disabled="busyKey === `del-proxy-${p.name}`"
                    @click="deleteProxy(p.name)"
                    class="px-3 py-1.5 rounded-xl text-xs font-medium text-rose-600 hover:bg-rose-50 border border-rose-200/80 disabled:opacity-50 transition cursor-pointer"
                  >
                    {{ t('删除') }}
                  </button>
                </div>
              </div>
            </div>

            <form @submit.prevent="submitAddProxies" class="space-y-3">
              <textarea
                v-model="proxiesRaw"
                name="proxies_raw"
                rows="5"
                :placeholder="t('粘贴单行 JSON / Flow 或多行 YAML 格式的 mihomo 节点配置（含 easytier、tailscale 等）…')"
                class="cg-input w-full p-3.5 rounded-xl border border-slate-200 bg-[#f8faf9] font-mono text-xs text-slate-900 focus:bg-white"
              ></textarea>
              <div class="flex items-center gap-2.5 flex-wrap">
                <button
                  type="submit"
                  :disabled="busyKey === 'add-proxies'"
                  class="cg-btn-primary px-4 py-2 rounded-xl disabled:opacity-50 text-xs font-semibold cursor-pointer"
                >
                  {{ busyKey === 'add-proxies' ? t('添加中…') : t('添加出站节点') }}
                </button>
                <label
                  class="px-3.5 py-2 rounded-xl bg-slate-100 hover:bg-slate-200/80 text-slate-700 text-xs font-medium transition cursor-pointer"
                >
                  {{ t('从文件载入') }}
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
      </Transition>

      <!-- TAB 3: 易读配置转换 (Dedicated Converter Page) -->
      <Transition name="cg-tab">
        <div v-show="activeTab === 'readable'" class="space-y-6">
          <section class="cg-surface rounded-2xl p-5 sm:p-6 space-y-5">
            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <div class="flex items-center gap-2.5">
                  <h2 class="text-base font-bold text-slate-900 tracking-tight">{{ t('易读配置转换') }}</h2>
                  <span
                    class="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200/70"
                  >
                    {{ t('单行 JSON ⇄ 多行 YAML') }}
                  </span>
                </div>
                <p class="text-xs text-slate-500 mt-1">
                  {{ t('在此粘贴单行 JSON / Flow 节点配置或多行 YAML，一键转换为结构清晰的多行易读 YAML 格式。') }}
                </p>
              </div>
              <div class="flex items-center gap-2 flex-wrap">
                <button
                  type="button"
                  @click="fillCurrentInboundsToConverter"
                  class="px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-200/80 transition cursor-pointer"
                >
                  {{ t('载入当前入站节点') }}
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
                  {{ t('清空') }}
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
                  <label class="text-xs font-semibold text-slate-700">{{ t('输入节点配置（单行 JSON / 多行 YAML）') }}</label>
                  <div class="flex items-center gap-2">
                    <button
                      type="button"
                      :disabled="busyKey === 'convert-readable'"
                      @click="convertConfigFormat('readable')"
                      class="cg-btn-primary px-3 py-1 rounded-lg text-xs font-semibold cursor-pointer"
                    >
                      {{ t('转换为易读配置') }}
                    </button>
                    <button
                      type="button"
                      :disabled="busyKey === 'convert-single'"
                      @click="convertConfigFormat('single')"
                      class="px-3 py-1 rounded-lg text-xs font-medium bg-slate-100 hover:bg-slate-200 text-slate-700 transition cursor-pointer"
                    >
                      {{ t('转换为单行配置') }}
                    </button>
                  </div>
                </div>
                <textarea
                  id="converter-input"
                  v-model="converterInput"
                  rows="14"
                  :placeholder="converterPlaceholder"
                  class="cg-input w-full p-3.5 rounded-xl border border-slate-200 bg-[#f8faf9] font-mono text-xs text-slate-900 leading-relaxed focus:bg-white"
                ></textarea>
              </div>

              <div class="space-y-2">
                <div class="flex items-center justify-between">
                  <label class="text-xs font-semibold text-slate-700">{{ t('转换结果（易读 YAML）') }}</label>
                  <button
                    type="button"
                    :disabled="!converterOutput"
                    @click="copyRaw(converterOutput, 'conv-out')"
                    class="px-3.5 py-1 rounded-lg text-xs font-semibold bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-200/80 disabled:opacity-40 transition cursor-pointer"
                  >
                    {{ copiedKey === 'conv-out' ? t('已复制结果') : t('复制转换结果') }}
                  </button>
                </div>
                <textarea
                  id="converter-output"
                  v-model="converterOutput"
                  readonly
                  rows="14"
                  :placeholder="t('点击「转换为易读配置」后在此显示多行 YAML 结果…')"
                  class="w-full p-3.5 rounded-xl border border-slate-200 bg-[#f8faf9] font-mono text-xs text-slate-800 leading-relaxed focus:outline-none"
                ></textarea>
              </div>
            </div>
          </section>
        </div>
      </Transition>

      <!-- TAB 4: 自定义 mihomo 服务端配置 -->
      <Transition name="cg-tab">
        <div v-show="activeTab === 'advanced'" class="space-y-6">
          <section class="cg-surface rounded-2xl p-5 sm:p-6 space-y-5">
            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div class="space-y-1">
                <div class="flex items-center gap-2.5 flex-wrap">
                  <h2 class="text-base font-bold text-slate-900 tracking-tight">{{ t('自定义 mihomo 服务端配置') }}</h2>
                  <span
                    class="px-2.5 py-0.5 text-xs font-semibold rounded-full"
                    :class="
                      state.custom_config_mode
                        ? 'bg-amber-50 text-amber-700 border border-amber-200/70'
                        : 'bg-emerald-50 text-emerald-700 border border-emerald-200/70'
                    "
                  >
                    {{ state.custom_config_mode ? t('当前：自定义配置模式') : t('当前：标准模板模式') }}
                  </span>
                </div>
                <p class="text-xs text-slate-500">
                  {{ t('您可以直接粘贴或编辑整份自备的 mihomo 服务端配置文件（') }}<code class="font-mono">config.yaml</code>{{ t('），校验通过后立即应用，并自动同步刷新入站 Listeners 列表与客户端订阅。普通用户无需修改此页。') }}
                </p>
              </div>

              <!-- 恢复标准模板 -->
              <button
                type="button"
                :disabled="busyKey === 'reset-template'"
                @click="resetTemplateConfig"
                class="px-4 py-2 rounded-xl text-xs font-semibold text-rose-700 bg-rose-50 hover:bg-rose-100 border border-rose-200/90 disabled:opacity-50 transition cursor-pointer shrink-0"
              >
                {{ busyKey === 'reset-template' ? t('正在恢复标准模板…') : t('恢复标准模板') }}
              </button>
            </div>

            <!-- 证书路径提示与说明 -->
            <div class="rounded-2xl bg-amber-50/90 border border-amber-200/90 p-4 text-xs text-amber-950 leading-relaxed space-y-1.5">
              <div class="font-bold text-amber-900">{{ t('⚠️ 醒目提醒：Mihomo 证书目录与相对路径说明') }}</div>
              <div>
                {{ t('1. 本系统已将 Mihomo 运行目录（') }}<code class="font-mono font-semibold">-d</code>{{ t('）、配置文件与证书统一收纳在') }}
                <code class="font-mono font-semibold">/etc/clashgate</code>{{ t('，证书实际位于') }}
                <code class="font-mono font-semibold">/etc/clashgate/certs/fullchain.pem</code> {{ t('与') }}
                <code class="font-mono font-semibold">/etc/clashgate/certs/privkey.pem</code>{{ t('（相对路径即') }}
                <code class="font-mono font-semibold">certs/fullchain.pem</code> {{ t('与') }}
                <code class="font-mono font-semibold">certs/privkey.pem</code>）。
              </div>
              <div>
                {{ t('2. 若您的自备配置中填写了其他证书路径或相对路径，请点击下方') }}
                <b class="font-semibold">{{ t('「自动修改证书路径」') }}</b> {{ t('按钮一键修正为本机证书路径，随后点击') }}
                <b class="font-semibold">{{ t('「更新 mihomo 服务端配置」') }}</b> {{ t('校验并生效。') }}
              </div>
            </div>

            <form @submit.prevent="submitCustomConfig" class="space-y-3.5">
              <textarea
                id="custom-config-raw"
                v-model="customConfigText"
                name="custom_config_raw"
                rows="16"
                :placeholder="t('在此粘贴完整的 mihomo 服务端 YAML 配置…')"
                class="cg-input w-full p-4 rounded-2xl border border-slate-200 bg-[#f8faf9] text-slate-800 font-mono text-xs leading-relaxed focus:bg-white"
              ></textarea>
              <div class="flex items-center gap-2.5 flex-wrap">
                <button
                  type="button"
                  @click="autoFixCertPaths"
                  class="px-4 py-2 rounded-xl bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-200 text-xs font-semibold transition cursor-pointer"
                >
                  {{ t('自动修改证书路径') }}
                </button>
                <button
                  type="submit"
                  :disabled="busyKey === 'save-custom'"
                  class="cg-btn-primary px-4 py-2 rounded-xl disabled:opacity-50 text-xs font-semibold cursor-pointer"
                >
                  {{ busyKey === 'save-custom' ? t('正在校验并更新…') : t('更新 mihomo 服务端配置') }}
                </button>
                <label
                  class="px-3.5 py-2 rounded-xl bg-slate-100 hover:bg-slate-200/80 text-slate-700 text-xs font-medium transition cursor-pointer"
                >
                  {{ t('从本地文件载入') }}
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
      </Transition>

      <!-- TAB 5: HTTPS 证书管理 -->
      <Transition name="cg-tab">
        <div v-show="activeTab === 'certs'" id="certs-panel" class="space-y-6">
          <!-- 证书概览与状态 -->
          <section id="cert-status-card" class="cg-surface rounded-2xl p-5 sm:p-6 space-y-4">
            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div class="flex items-center gap-2.5 flex-wrap">
                <span
                  class="w-2.5 h-2.5 rounded-full"
                  :class="
                    !state.certs_present || !state.status.cert_expires
                      ? 'bg-slate-400'
                      : certIsTemp || (certDaysValue !== null && certDaysValue < 14)
                        ? 'bg-amber-500'
                        : 'bg-emerald-500'
                  "
                ></span>
                <h2 class="text-base font-bold text-slate-900 tracking-tight">{{ t('HTTPS 证书管理') }}</h2>
                <span
                  class="px-2.5 py-0.5 text-xs font-semibold rounded-full border"
                  :class="
                    !state.certs_present || !state.status.cert_expires
                      ? 'bg-slate-50 text-slate-600 border-slate-200/80'
                      : certIsTemp
                        ? 'bg-amber-50 text-amber-700 border-amber-200/80'
                        : certDaysValue !== null && certDaysValue < 14
                          ? 'bg-amber-50 text-amber-700 border-amber-200/80'
                          : 'bg-emerald-50 text-emerald-700 border-emerald-200/70'
                  "
                >
                  {{
                    !state.certs_present || !state.status.cert_expires
                      ? t('未检测到证书')
                      : certIsTemp
                        ? t('临时自签证书')
                        : certDaysValue !== null && certDaysValue < 14
                          ? t('即将过期')
                          : t('有效')
                  }}
                </span>
              </div>

              <div class="flex items-center gap-2 flex-wrap">
                <button
                  id="cert-renew-btn"
                  type="button"
                  :disabled="busyKey === '/action/cert'"
                  @click="postAction('/action/cert', {}, '/action/cert')"
                  class="px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-200/80 disabled:opacity-50 transition cursor-pointer"
                >
                  {{ busyKey === '/action/cert' ? t('检查续期中…') : t('立即检查 / 续期') }}
                </button>
              </div>
            </div>

            <!-- 无证书空态说明 -->
            <div
              v-if="state.mode === 'no-cert' || !state.certs_present"
              id="cert-empty-notice"
              class="rounded-xl bg-amber-50/90 border border-amber-200/80 px-4 py-3 text-xs text-amber-900 leading-relaxed"
            >
              {{ t('当前为无证书模式或未检测到证书文件（/etc/clashgate/certs/fullchain.pem）。如需启用自动证书，可在下方配置 Cloudflare DNS 模式并申请证书。') }}
            </div>

            <!-- 手动证书提示 -->
            <div
              v-else-if="certModeValue === 'manual'"
              id="cert-manual-notice"
              class="rounded-xl bg-[#f4fbf7] border border-emerald-200/80 px-4 py-3 text-xs text-emerald-900 leading-relaxed"
            >
              {{ t('当前为手动证书模式。手动证书请直接替换 /etc/clashgate/certs/ 下的 fullchain.pem 与 privkey.pem 文件，然后点击右上角「立即检查 / 续期」校验证书。') }}
            </div>

            <!-- 证书信息字段网格 -->
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5">
              <div class="rounded-xl bg-[#f8fbf9] border border-slate-200/80 p-3.5">
                <div class="text-xs font-medium text-slate-500">{{ t('域名') }}</div>
                <div id="cert-domain" class="mt-1.5 text-sm font-bold text-slate-900 font-mono break-all">
                  {{ certDomainDisplay }}
                </div>
              </div>

              <div class="rounded-xl bg-[#f8fbf9] border border-slate-200/80 p-3.5">
                <div class="text-xs font-medium text-slate-500">{{ t('当前模式') }}</div>
                <div id="cert-current-mode" class="mt-1.5 text-sm font-bold text-slate-900">
                  {{ certModeLabel }}
                </div>
              </div>

              <div class="rounded-xl bg-[#f8fbf9] border border-slate-200/80 p-3.5">
                <div class="text-xs font-medium text-slate-500">{{ t('颁发者') }}</div>
                <div id="cert-issuer" class="mt-1.5 text-sm font-bold text-slate-900 break-all">
                  {{ certIssuerDisplay }}
                </div>
              </div>

              <div class="rounded-xl bg-[#f8fbf9] border border-slate-200/80 p-3.5">
                <div class="text-xs font-medium text-slate-500">{{ t('过期时间') }}</div>
                <div id="cert-expires" class="mt-1.5 text-sm font-bold text-slate-900 font-mono tabular-nums">
                  {{ certExpiresDisplay }}
                </div>
              </div>

              <div
                class="rounded-xl border p-3.5"
                :class="
                  certDaysValue !== null && certDaysValue < 14
                    ? 'bg-amber-50/80 border-amber-200/90'
                    : 'bg-[#f8fbf9] border-slate-200/80'
                "
              >
                <div
                  class="text-xs font-medium"
                  :class="certDaysValue !== null && certDaysValue < 14 ? 'text-amber-800' : 'text-slate-500'"
                >
                  {{ t('剩余天数') }}
                </div>
                <div
                  id="cert-days"
                  class="mt-1.5 text-sm font-bold tabular-nums"
                  :class="certDaysValue !== null && certDaysValue < 14 ? 'text-amber-900' : 'text-slate-900'"
                >
                  {{ certDaysValue !== null ? `${certDaysValue} ${t('天')}` : '—' }}
                </div>
              </div>
            </div>
          </section>

          <!-- 切换到 Cloudflare DNS 续证模式 & 如何获取 API Token -->
          <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            <!-- Left: 切换 Cloudflare DNS 模式表单 -->
            <section id="cert-dns-form-card" class="lg:col-span-6 cg-surface rounded-2xl p-5 sm:p-6 space-y-4">
              <div>
                <div class="flex items-center gap-2.5">
                  <h2 class="text-base font-bold text-slate-900 tracking-tight">{{ t('切换到 Cloudflare DNS 续证模式') }}</h2>
                  <span
                    class="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200/70"
                  >
                    Cloudflare DNS
                  </span>
                </div>
                <p class="text-xs text-slate-500 mt-1 leading-relaxed">
                  {{ t('立即生效，无需点击顶栏重载配置。保存后将立即调用 acme.sh 申请或续期证书。') }}
                </p>
              </div>

              <form @submit.prevent="submitCertMode" class="space-y-4" novalidate>
                <div>
                  <label for="cert-mode-select" class="block text-xs font-semibold text-slate-700 mb-1.5">
                    {{ t('目标续证模式') }}
                  </label>
                  <select
                    id="cert-mode-select"
                    v-model="certModeForm.mode"
                    name="cert_mode"
                    class="cg-input w-full h-10 px-3 rounded-xl border border-slate-200 bg-white text-sm text-slate-900"
                  >
                    <option value="dns">{{ t('Cloudflare DNS（推荐，免 80 端口）') }}</option>
                    <option value="port">{{ t('端口模式') }}</option>
                  </select>
                </div>

                <div v-if="certModeForm.mode === 'dns'">
                  <label for="cf-token" class="block text-xs font-semibold text-slate-700 mb-1.5">
                    {{ t('Cloudflare API Token') }}
                  </label>
                  <input
                    id="cf-token"
                    ref="cfTokenEl"
                    v-model="certModeForm.cf_token"
                    name="cf_token"
                    :type="cfTokenRevealed ? 'text' : 'password'"
                    autocomplete="off"
                    spellcheck="false"
                    :placeholder="t('请输入或粘贴具备 Zone.DNS 编辑权限的 Cloudflare API Token')"
                    @click="revealCfToken"
                    @blur="cfTokenRevealed = false"
                    class="cg-input w-full h-10 px-3.5 rounded-xl border border-emerald-100 bg-[#f6faf8] hover:bg-emerald-50/50 focus:bg-white font-mono text-xs transition"
                    :class="cfTokenRevealed ? 'text-slate-800' : 'text-slate-600 tracking-widest'"
                  />
                </div>

                <button
                  id="cert-mode-submit"
                  type="submit"
                  :disabled="busyKey === '/action/cert-mode'"
                  class="cg-btn-primary w-full h-10 rounded-xl disabled:opacity-50 text-sm font-semibold cursor-pointer"
                >
                  {{ busyKey === '/action/cert-mode' ? t('正在切换并续证…') : t('切换并续证') }}
                </button>
              </form>
            </section>

            <!-- Right: 如何获取 Cloudflare API Token 说明卡 -->
            <section id="cf-token-guide-card" class="lg:col-span-6 cg-surface rounded-2xl p-5 sm:p-6 space-y-3.5">
              <div class="flex items-center gap-2.5">
                <h2 class="text-base font-bold text-slate-900 tracking-tight">{{ t('如何获取 Cloudflare API Token') }}</h2>
              </div>
              <p class="text-xs text-slate-500">
                {{ t('按以下步骤在 Cloudflare 创建仅限 DNS 编辑权限的 API Token：') }}
              </p>

              <ol class="space-y-2.5 text-xs text-slate-700 leading-relaxed list-decimal list-inside">
                <li>
                  {{ t('打开 Cloudflare Dashboard →') }}
                  <b class="font-semibold text-slate-900">My Profile</b> →
                  <b class="font-semibold text-slate-900">API Tokens</b>
                  {{ t('（直达：') }}<a
                    href="https://dash.cloudflare.com/profile/api-tokens"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="text-emerald-700 hover:text-emerald-600 underline underline-offset-2 font-mono break-all"
                  >https://dash.cloudflare.com/profile/api-tokens</a>）。
                </li>
                <li>
                  {{ t('点击') }} <b class="font-semibold text-slate-900">Create Token</b>{{ t('，选择模板') }}
                  <b class="font-semibold text-slate-900">Edit zone DNS</b>{{ t('，或自定义权限：') }}
                  <ul class="mt-1.5 ml-4 space-y-1 list-disc text-slate-600">
                    <li>
                      <b class="font-semibold text-slate-800">Permissions</b>：<code class="px-1.5 py-0.5 rounded bg-slate-100 font-mono">Zone</code> →
                      <code class="px-1.5 py-0.5 rounded bg-slate-100 font-mono">DNS</code> →
                      <code class="px-1.5 py-0.5 rounded bg-slate-100 font-mono">Edit</code>
                    </li>
                    <li>
                      <b class="font-semibold text-slate-800">Zone Resources</b>：<code class="px-1.5 py-0.5 rounded bg-slate-100 font-mono">Include</code> →
                      {{ t('选择当前面板域名所在 Zone（或具体域名）') }}
                    </li>
                  </ul>
                </li>
                <li>
                  {{ t('创建后复制生成的 Token，粘贴到左侧输入框并点击「切换并续证」（Token 仅显示一次，请妥善保存）。') }}
                </li>
              </ol>

              <div class="rounded-xl bg-[#f4fbf7] border border-emerald-200/70 px-3.5 py-2.5 text-xs text-emerald-900 leading-relaxed">
                {{ t('DNS 模式不需要占用 80 端口，也不要求灰云（可开启橙云代理）；Token 仅保存在本机') }}
                <code class="font-mono font-semibold">/etc/clashgate/clashgate.env</code>。
              </div>
            </section>
          </div>
        </div>
      </Transition>
    </main>
  </div>
</template>
