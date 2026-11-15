// Panel state, API calls, and form handlers shared by App.vue and page components.
// Extracted from App.vue without changing behaviour.
import { ref, reactive, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { t, lang, setLang, LANGS, langLabel } from '../i18n.js'
import { theme, setTheme } from '../theme.js'

let _panel

export function usePanel() {
  if (_panel) return _panel

  const boot = window.__CS_BOOT__ || {
    page: 'dashboard',
    initial_tab: 'inbounds',
    version: '',
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
    custom_config_saved: false,
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
    routing: { ok: true, custom_mode: false, groups: [], error: '' },
    cluster: { node_name: '', node_name_set: false, node_name_max: 20, locked: false, self_url: '', members: [], pending: [] },
  }

  const pageMode = ref(boot.page || 'dashboard')
  const isXmas = computed(() => theme.value === 'christmas')
  const state = reactive({
    version: boot.version || '',
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
    custom_config_saved: !!boot.custom_config_saved,
    custom_config_raw: boot.custom_config_raw || '',
    pending_reload_count: Number(boot.pending_reload_count || (boot.status && boot.status.pending_reload_count) || 0),
    pending_reload_items: Array.isArray(boot.pending_reload_items) ? boot.pending_reload_items : [],
    status: { ...(boot.status || {}) },
    inbounds: Array.isArray(boot.inbounds) ? boot.inbounds : [],
    all_proxies_yaml: boot.all_proxies_yaml || '',
    proxies: Array.isArray(boot.proxies) ? boot.proxies : [],
    providers: Array.isArray(boot.providers) ? boot.providers : [],
    routing: boot.routing && typeof boot.routing === 'object' ? boot.routing : { ok: true, custom_mode: false, groups: [], error: '' },
    cluster: normalizeCluster(boot.cluster),
    custom_server_enabled: !!boot.custom_server_enabled,
    auto_update: !!boot.auto_update,
    update_channel: boot.update_channel === 'test' ? 'test' : 'stable',
    update_channel_label: boot.update_channel_label || (boot.update_channel === 'test' ? '测试' : '正式'),
    masque: {
      status: (boot.masque && boot.masque.status) || 'idle',
      name: (boot.masque && boot.masque.name) || '⛅️ Cloudflare-MASQUE',
      endpoint: (boot.masque && boot.masque.endpoint) || '',
      yaml: (boot.masque && boot.masque.yaml) || '',
      error: (boot.masque && boot.masque.error) || '',
    },
    update_check: {
      core: {
        checked_at: 0,
        current: '',
        latest: '',
        has_update: false,
        ...((boot.update_check && boot.update_check.core) || {}),
      },
      panel: {
        checked_at: 0,
        current: '',
        latest: '',
        has_update: false,
        ...((boot.update_check && boot.update_check.panel) || {}),
      },
    },
  })

  function normalizeCluster(c) {
    const src = c && typeof c === 'object' ? c : {}
    return {
      node_name: String(src.node_name || ''),
      node_name_set: !!src.node_name_set,
      node_name_max: Number(src.node_name_max || 20),
      locked: !!src.locked,
      self_url: String(src.self_url || ''),
      members: Array.isArray(src.members) ? src.members : [],
      pending: Array.isArray(src.pending) ? src.pending : [],
    }
  }

  const showPendingDiff = ref(false)
  const showVersionPanel = ref(false)
  const showTrafficDetail = ref(false)
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
    if (langOpen.value && target && target.closest && !target.closest('.cg-lang, .cg-lang-menu')) {
      langOpen.value = false
    }
  }

  function handleKeydown(ev) {
    if (!ev || ev.key !== 'Escape') return
    if (langOpen.value) langOpen.value = false
    else if (confirmDialog.show) closeConfirmDialog()
    else if (renameDialog.show) closeRenameDialog()
    else if (showPasswordModal.value) closePasswordModal()
    else if (showSubQrModal.value) showSubQrModal.value = false
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
    cancelText: '',
    tone: 'amber',
    onConfirm: null,
    onCancel: null,
  })

  // onCancel (optional): a second action on the left button (e.g. "keep my config");
  // ✕ / Escape / backdrop only close the dialog and run nothing.
  function openConfirmDialog({ title, message, confirmText, cancelText = '', tone = 'amber', onConfirm, onCancel = null }) {
    confirmDialog.title = title || t('确认操作')
    confirmDialog.message = message || ''
    confirmDialog.confirmText = confirmText || t('确认')
    confirmDialog.cancelText = cancelText
    confirmDialog.tone = tone
    confirmDialog.onConfirm = onConfirm || null
    confirmDialog.onCancel = onCancel
    confirmDialog.show = true
  }

  function closeConfirmDialog() {
    confirmDialog.show = false
    confirmDialog.onConfirm = null
    confirmDialog.onCancel = null
  }

  async function cancelConfirmDialog() {
    const fn = confirmDialog.onCancel
    closeConfirmDialog()
    if (typeof fn === 'function') {
      await fn()
    }
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
    if (op === 'add') return t('+ 添加节点「{name}」（端口 {port}）', { name, port })
    if (op === 'delete') return t('- 删除节点「{name}」', { name })
    if (op === 'reset-password') return t('~ 重置密码「{name}」', { name })
    if (op === 'reset-secret') return t('~ 重置 API 密钥')
    if (op === 'reset-sub') return t('~ 更换订阅链接')
    if (op === 'add-proxy') return t('+ 添加服务端出站「{name}」', { name })
    if (op === 'delete-proxy') return t('- 删除服务端出站「{name}」', { name })
    if (op === 'add-provider') return t('+ 导入订阅源「{name}」', { name })
    if (op === 'delete-provider') return t('- 删除订阅源「{name}」', { name })
    if (op === 'add-routing') return t('+ 添加分流组「{name}」', { name })
    if (op === 'import-routing') return t('+ 引入分流组「{name}」', { name })
    if (op === 'delete-routing') return t('- 删除分流组「{name}」', { name })
    if (op === 'rename-routing') return item.detail || t('~ 更新分流组「{name}」', { name })
    if (op === 'reorder-routing') return t('~ 调整分流顺序')
    if (op === 'update-routing') return t('~ 更新分流组「{name}」', { name })
    return item.detail || ''
  }

  const topbarVersionText = computed(() => {
    const mv = String(state.mihomo_version || (state.status && state.status.mihomo_version) || '').trim()
    return mv ? `v${state.version} · mihomo ${mv}` : `v${state.version}`
  })

  const pageTitle = computed(() => {
    const titles = {
      inbounds: t('首页'),
      outbounds: t('服务端出站'),
      routing: t('服务端分流'),
      readable: t('节点转换'),
      certs: t('HTTPS 证书'),
      advanced: t('自定义服务端'),
      settings: t('设置'),
      cluster: t('集群'),
    }
    return titles[activeTab.value] || t('首页')
  })

  const coreUpdate = computed(() => state.update_check.core || {})
  const panelUpdate = computed(() => state.update_check.panel || {})

  // update-state: pure helpers (mirrored by tests/test_panel.py)
  // Versions compare as integer tuples like the backend's parse_version_tuple (1.15 > 1.14, 1.15.0 == 1.15).
  function cgVersionTuple(v) {
    const nums = (String(v || '').trim().replace(/^v/i, '').match(/\d+/g) || ['0']).map(Number)
    while (nums.length > 1 && nums[nums.length - 1] === 0) nums.pop()
    return nums
  }
  function cgVersionNewer(a, b) {
    const x = cgVersionTuple(a), y = cgVersionTuple(b)
    for (let i = 0; i < Math.max(x.length, y.length); i++) {
      const d = (x[i] || 0) - (y[i] || 0)
      if (d) return d > 0
    }
    return false
  }
  // The badge is shown only for a version strictly newer than what is installed now,
  // and never while an upgrade is running or the page is about to reload after one.
  function cgShowUpdate(slot, installed, upgrading) {
    if (upgrading || !slot || !slot.has_update) return false
    if (!slot.latest || !installed) return true
    return cgVersionNewer(slot.latest, installed)
  }
  // After an upgrade lands, the cached check result describes the old build: drop it.
  function cgSlotAfterUpgrade(slot, version) {
    return { ...(slot || {}), current: version || (slot && slot.current) || '', has_update: false }
  }
  // end update-state

  const upgradeInProgress = ref(false)
  const panelHasUpdate = computed(() =>
    cgShowUpdate(panelUpdate.value, state.version, upgradeInProgress.value || busyKey.value === '/action/upgrade-self')
  )
  const coreHasUpdate = computed(() =>
    cgShowUpdate(coreUpdate.value, state.mihomo_version, upgradeInProgress.value || busyKey.value === '/action/update-core')
  )

  function versionLabel(v) {
    const s = String(v || '').trim()
    if (!s) return ''
    return /^v/i.test(s) ? s : `v${s}`
  }

  function updateHint(v) {
    const label = versionLabel(v)
    return label ? t('有新版本 {v}', { v: label }) : t('有新版本')
  }

  function applyUpdateCheck(src) {
    if (!src || typeof src !== 'object') return
    state.update_check = {
      core: mergeUpdateSlot(state.update_check.core, src.core),
      panel: mergeUpdateSlot(state.update_check.panel, src.panel),
    }
  }

  function mergeUpdateSlot(prev, next) {
    const base = {
      checked_at: 0,
      current: '',
      latest: '',
      has_update: false,
      ...(prev || {}),
    }
    if (!next || typeof next !== 'object') return base
    const prevTs = Number(base.checked_at || 0)
    const nextTs = Number(next.checked_at || 0)
    if (!nextTs || nextTs < prevTs) return base
    return {
      ...base,
      ...next,
      checked_at: nextTs,
      has_update: !!next.has_update,
    }
  }

  const converterPlaceholder = computed(
    () => t('在此粘贴节点配置，例如：') + '\n- {"name":"VlessReality","type":"vless","server":"1.2.3.4","port":28443,...}'
  )

  const VALID_TABS = ['inbounds', 'outbounds', 'routing', 'cluster', 'readable', 'certs', 'advanced', 'settings']
  const TAB_PATHS = {
    inbounds: '/',
    outbounds: '/outbounds',
    routing: '/routing',
    cluster: '/cluster',
    readable: '/readable',
    advanced: '/advanced',
    certs: '/certs',
    settings: '/settings',
  }

  function detectInitialTab() {
    if (boot.initial_tab && VALID_TABS.includes(boot.initial_tab)) {
      return boot.initial_tab
    }
    return tabFromPath()
  }

  function tabFromPath() {
    const p = window.location.pathname
    if (p === '/settings') return 'settings'
    if (p === '/certs' || p === '/cert') return 'certs'
    if (p === '/advanced' || p === '/custom-config') return 'advanced'
    if (p === '/readable' || p === '/convert') return 'readable'
    if (p === '/outbounds') return 'outbounds'
    if (p === '/routing') return 'routing'
    if (p === '/cluster') return 'cluster'
    return 'inbounds'
  }

  const activeTab = ref(detectInitialTab())
  watch(activeTab, () => {
    maskAllSensitive()
    nextTick(scrollActiveNavIntoView)
  })

  function scrollActiveNavIntoView() {
    const el = document.querySelector('.cg-mobile-nav .cg-nav.is-active')
    if (el && typeof el.scrollIntoView === 'function') {
      el.scrollIntoView({ block: 'nearest', inline: 'nearest' })
    }
  }

  const busyKey = ref('')
  const copiedKey = ref('')
  const langOpen = ref(false)
  const langMenuStyle = ref({})
  const toast = reactive({ show: false, msg: '', ok: true })
  let toastTimer = null

  function toggleLangMenu(ev) {
    if (langOpen.value) {
      langOpen.value = false
      return
    }
    const btn = ev.currentTarget
    const rect = btn.getBoundingClientRect()
    const width = 168
    const rtl = document.documentElement.dir === 'rtl'
    let left = rtl ? rect.left : rect.right - width
    left = Math.max(8, Math.min(left, window.innerWidth - width - 8))
    langMenuStyle.value = {
      top: `${Math.round(rect.bottom + 6)}px`,
      left: `${Math.round(left)}px`,
      width: `${width}px`,
    }
    langOpen.value = true
  }

  function pickLang(code) {
    setLang(code)
    langOpen.value = false
  }

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
      lockedNote: '已锁定安全默认：默认启用 VLESS Encryption (vless-x25519)。SNI 可自填，留空从内置域名池随机抽取',
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
      label: 'Snell V6',
      defaultName: 'SnellV6',
      desc: '轻量高效的私有协议，内置基于 PSK 的流量整形',
      lockedNote: '已锁定安全默认：PSK 自动随机生成，流量整形使用 v6 默认模式',
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
      lockedNote: '已锁定安全默认：伪装地址 (JLS) 可自填，留空从内置域名池随机抽取，拥塞控制默认 bbr',
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
    sni: '',
  })

  const currentProtocol = computed(() => PROTOCOL_MAP[inboundForm.kind] || PROTOCOLS[0])
  const currentDefaultName = computed(() => DEFAULT_NAMES[inboundForm.kind] || 'VlessReality')
  // Protocols that show one extra option field (SNI or a select) in the add-node form.
  const PROTOCOL_HAS_OPTION = new Set(['vless-reality', 'shadowquic', 'tuic', 'trusttunnel', 'mieru', 'http', 'socks'])
  const sniEditable = computed(() =>
    inboundForm.kind === 'vless-reality' || inboundForm.kind === 'shadowquic'
  )

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
    mode: state.cert_mode === 'dns' ? 'dns' : 'port',
    cf_token: state.cf_token || '',
  })
  const certRegenLock = ref(false)

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
  const certBaselineMode = computed(() => (certModeValue.value === 'dns' ? 'dns' : 'port'))
  const certModeDirty = computed(() => {
    if (certModeValue.value === 'manual') return certModeForm.mode === 'dns' || certModeForm.mode === 'port'
    if (certModeForm.mode !== certBaselineMode.value) return true
    if (certModeForm.mode === 'dns' && (certModeForm.cf_token || '') !== (state.cf_token || '')) return true
    return false
  })
  const certRegenDisabled = computed(() => !certModeDirty.value || certRegenLock.value || busyKey.value === '/action/cert-mode')

  async function submitCertMode() {
    if (busyKey.value || certRegenLock.value || !certModeDirty.value) return
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
    certRegenLock.value = true
    maskAllSensitive()
    try {
      await postAction(
        '/action/cert-mode',
        {
          cert_mode: certModeForm.mode,
          cf_token: certModeForm.cf_token,
        },
        '/action/cert-mode'
      )
    } finally {
      certRegenLock.value = false
      maskAllSensitive()
    }
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
        busyKey.value = ''
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

  function toggleVersionPanel() {
    showVersionPanel.value = !showVersionPanel.value
  }

  async function checkUpdateAndPrompt() {
    const res = await postAction('/action/check-update', {}, '/action/check-update', { silentToast: true })
    if (!res || !res.ok) return
    const hasUpdate = !!res.has_update
    state.update_check.panel = {
      checked_at: Math.floor(Date.now() / 1000),
      current: res.current_version || state.version,
      latest: res.latest_version || '',
      has_update: hasUpdate,
    }
    if (hasUpdate) {
      const latest = res.latest_version || t('最新版')
      const current = res.current_version || state.version
      openConfirmDialog({
        title: t('检查更新'),
        message: t('检测到新版本 v{latest}（当前版本 v{current}），是否立即升级？', { latest, current }),
        confirmText: t('立即升级'),
        tone: 'emerald',
        onConfirm: () => postAction('/action/upgrade-self', {}, '/action/upgrade-self'),
      })
      return
    }
    if (res.msg) showToast(res.msg, true)
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
          if (data.custom_server_enabled !== undefined) state.custom_server_enabled = !!data.custom_server_enabled
          if (data.auto_update !== undefined) state.auto_update = !!data.auto_update
          if (data.update_channel !== undefined) state.update_channel = data.update_channel === 'test' ? 'test' : 'stable'
          if (data.update_channel_label !== undefined) state.update_channel_label = data.update_channel_label || state.update_channel_label
          if (data.masque) {
            state.masque = {
              status: data.masque.status || state.masque.status,
              name: data.masque.name || state.masque.name,
              endpoint: data.masque.endpoint || '',
              yaml: data.masque.yaml || '',
              error: data.masque.error || '',
            }
          }
          if (data.update_check) applyUpdateCheck(data.update_check)
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
    if (newState.custom_config_saved !== undefined) state.custom_config_saved = !!newState.custom_config_saved
    if (newState.custom_server_enabled !== undefined) state.custom_server_enabled = !!newState.custom_server_enabled
    if (newState.auto_update !== undefined) state.auto_update = !!newState.auto_update
    if (newState.update_channel !== undefined) state.update_channel = newState.update_channel === 'test' ? 'test' : 'stable'
    if (newState.update_channel_label !== undefined) {
      state.update_channel_label = newState.update_channel_label || state.update_channel_label
    }
    if (newState.masque && typeof newState.masque === 'object') {
      state.masque = {
        status: newState.masque.status || 'idle',
        name: newState.masque.name || '⛅️ Cloudflare-MASQUE',
        endpoint: newState.masque.endpoint || '',
        yaml: newState.masque.yaml || '',
        error: newState.masque.error || '',
      }
    }
    if (newState.update_check) applyUpdateCheck(newState.update_check)
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
    if (newState.routing && typeof newState.routing === 'object') state.routing = newState.routing
    if (newState.cluster && typeof newState.cluster === 'object') {
      state.cluster = normalizeCluster(newState.cluster)
      // Keep what the user is typing; follow the server only while the field is untouched.
      if (nodeNameInput.value === nodeNameSaved.value) nodeNameInput.value = state.cluster.node_name
      nodeNameSaved.value = state.cluster.node_name
    }
  }

  function formatFetchError(err) {
    const raw = String((err && err.message) || err || '')
    if (/NetworkError|Failed to fetch|Load failed|network/i.test(raw)) {
      return t('网络连接中断或服务正在重启，请稍后刷新页面查看状态')
    }
    return t('请求异常：{raw}', { raw })
  }

  async function postAction(url, params = {}, key = url, opts = {}) {
    if (busyKey.value) return null
    busyKey.value = key
    const versionBefore = state.version
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
      if (!opts.silentToast) showToast(data.msg || (data.ok ? t('操作成功') : t('操作失败')), !!data.ok)
      if (url === '/action/upgrade-self' && data.ok) await reloadPanelAfterUpgrade(versionBefore)
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
          if ((url === '/action/reload' || url === '/action/restart') && Number(stData.pending_reload_count || 0) === 0) {
            showToast(t('已重载配置并更新客户端订阅'), true)
            return { ok: true, state: stData }
          }
        }
      } catch {}
      if (url === '/action/upgrade-self') {
        await reloadPanelAfterUpgrade(versionBefore)
        return null
      }
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
      sni: sniEditable.value ? inboundForm.sni.trim() : '',
      req_id: pendingAddReqId,
    }
    const res = await postAction('/inbounds/add', payload, 'add-inbound')
    pendingAddReqId = ''
    if (res && res.ok) {
      inboundForm.port = ''
      inboundForm.sni = ''
      inboundForm.name = currentDefaultName.value
    }
  }

  function resetInboundPassword(item) {
    if (!item || !item.reset_url) return
    openConfirmDialog({
      title: t('重置密码'),
      message: t('确定重置节点「{name}」的密码？点顶部「重载配置」后生效，客户端需要重新更新订阅。', { name: item.name }),
      confirmText: t('确认重置'),
      tone: 'amber',
      onConfirm: () => postAction(item.reset_url, {}, `rst-${item.key}`),
    })
  }

  function deleteInbound(item) {
    if (!item || !item.delete_url) return
    openConfirmDialog({
      title: t('删除节点'),
      message: t('确定删除节点「{name}」？点顶部「重载配置」后生效。', { name: item.name }),
      confirmText: t('确认删除'),
      tone: 'rose',
      onConfirm: () => postAction(item.delete_url, {}, `del-${item.key}`),
    })
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
    const subUrl = providerForm.sub_url.trim()
    if (!subUrl) {
      showToast(t('请填写订阅链接'), false)
      return
    }
    if (!/^https?:\/\/\S+$/i.test(subUrl)) {
      showToast(t('订阅链接必须以 http(s):// 开头'), false)
      return
    }
    const provName = providerForm.provider_name.trim()
    if (provName && !/^[A-Za-z0-9._-]{1,48}$/.test(provName)) {
      showToast(t('订阅源名称仅限 1-48 位字母、数字及 . _ -'), false)
      return
    }
    if (provName && state.providers.some((p) => p && p.name === provName)) {
      showToast(t('订阅源「{name}」已存在，请换一个名称或先删除原订阅源', { name: provName }), false)
      return
    }
    const res = await postAction(
      '/providers/add',
      {
        sub_url: subUrl,
        provider_name: provName,
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
      title: t('删除订阅源'),
      message: t('确定删除订阅源「{name}」？', { name }),
      confirmText: t('确认删除'),
      tone: 'rose',
      onConfirm: () => postAction('/providers/delete', { name }, `del-prov-${name}`),
    })
  }

  async function submitAddProxies() {
    if (!proxiesRaw.value.trim()) {
      showToast(t('请先粘贴节点配置'), false)
      return
    }
    const res = await postAction('/proxies/add', { proxies_raw: proxiesRaw.value }, 'add-proxies')
    if (res && res.ok) {
      proxiesRaw.value = ''
    }
  }

  function deleteProxy(name) {
    openConfirmDialog({
      title: t('删除服务端出站'),
      message: t('确定删除服务端出站「{name}」？', { name }),
      confirmText: t('确认删除'),
      tone: 'rose',
      onConfirm: () => postAction('/proxies/delete', { name }, `del-proxy-${name}`),
    })
  }

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

  const nodeNameInput = ref(state.cluster.node_name)
  const nodeNameSaved = ref(state.cluster.node_name)
  const nodeNameLength = computed(() => Array.from(String(nodeNameInput.value || '').trim()).length)
  // Only the over-limit hint is shown while typing; other errors appear on save.
  const nodeNameOverLimit = computed(() => nodeNameLength.value > CG_NODE_NAME_MAX)
  const nodeNameHint = computed(() => (
    nodeNameOverLimit.value ? t('本机名称最多 {n} 个字符', { n: CG_NODE_NAME_MAX }) : ''
  ))

  async function saveNodeName() {
    if (busyKey.value) return
    if (nodeNameOverLimit.value) return
    const err = nodeNameError(nodeNameInput.value)
    if (err) {
      showToast(err, false)
      return
    }
    await postAction('/action/settings', { node_name: nodeNameInput.value.trim() }, 'save-node-name')
  }

  const clusterForm = reactive({ url: '', password: '' })
  const clusterTouched = reactive({ url: false, password: false })

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

  const clusterUrlErr = computed(() => clusterUrlError(clusterForm.url))
  const clusterPwErr = computed(() => (clusterForm.password ? '' : t('请填写对方面板密码')))

  async function submitAddCluster() {
    if (busyKey.value) return
    clusterTouched.url = true
    clusterTouched.password = true
    const err = clusterUrlErr.value || clusterPwErr.value
    if (err) {
      showToast(err, false)
      return
    }
    const res = await postAction(
      '/cluster/add',
      { url: clusterForm.url.trim(), password: clusterForm.password },
      'cluster-add'
    )
    if (res && res.ok) {
      clusterForm.url = ''
      clusterForm.password = ''
      clusterTouched.url = false
      clusterTouched.password = false
    } else {
      clusterForm.password = ''
    }
  }

  function removeClusterMember(m) {
    openConfirmDialog({
      title: t('移出集群'),
      message: t('确定把「{name}」移出集群？集群里所有面板都会删除和它的互联，它自己也会退出集群。', { name: m.name }),
      confirmText: t('确认移出'),
      tone: 'rose',
      onConfirm: () => postAction('/cluster/remove', { id: m.id }, `cl-rm-${m.id}`),
    })
  }

  const listSep = computed(() => ({ zh: '、', fa: '، ' })[lang.value] || ', ')

  function syncCluster() {
    return postAction('/cluster/sync', {}, 'cluster-sync')
  }

  function leaveCluster() {
    openConfirmDialog({
      title: t('退出集群'),
      message: t('确定让本机退出集群？本机和所有成员之间的互联都会删除，其他成员之间的互联保持不变。'),
      confirmText: t('确认退出'),
      tone: 'rose',
      onConfirm: () => postAction('/cluster/leave', {}, 'cluster-leave'),
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
    if (busyKey.value) return
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
        cache: 'no-store',
      })
      if (res.status === 401) {
        window.location.href = '/login'
        return
      }
      const data = await res.json().catch(() => ({ ok: false, msg: `HTTP ${res.status}` }))
      if (!res.ok || !data.ok) {
        converterError.value = data.msg || t('配置解析失败，请检查格式是否正确')
        return
      }
      converterOutput.value = mode === 'single' ? data.single : data.readable
      showToast(t('已成功转换 {count} 个节点为{kind}', { count: data.count, kind: mode === 'single' ? t('单行配置') : t('多行易读 YAML') }), true)
    } catch (e) {
      converterError.value = formatFetchError(e)
    } finally {
      busyKey.value = ''
    }
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

  // autoFix: the server rewrites the paths (and reports how many); `shown` is what the
  // editor keeps if the save fails (a failed save returns the old server state).
  async function saveCustomConfig(text, autoFix, shown = text) {
    customConfigText.value = shown
    const res = await postAction(
      '/config/custom',
      { custom_config_raw: text, auto_fix_certs: autoFix ? '1' : '0' },
      'save-custom'
    )
    if (!res || !res.ok) customConfigText.value = shown
  }

  async function submitCustomConfig() {
    const raw = customConfigText.value || ''
    if (!raw.trim()) {
      showToast(t('请先粘贴完整的服务端配置'), false)
      return
    }
    const fixed = fixCertPaths(raw)
    if (fixed.changed > 0) {
      openConfirmDialog({
        title: t('自动配置证书路径？'),
        message: t('检测到 {n} 处证书路径不是本项目的证书路径（或是相对路径）。项目目录之外的证书，内核可能无法读取，建议自动配置为本项目证书（/etc/clashgate/certs/）。', { n: fixed.changed }),
        confirmText: t('自动配置并保存'),
        cancelText: t('保持我的配置'),
        tone: 'emerald',
        onConfirm: () => saveCustomConfig(raw, true, fixed.text),
        onCancel: () => saveCustomConfig(raw, false),
      })
      return
    }
    await saveCustomConfig(raw, false)
  }

  function resetTemplateConfig() {
    openConfirmDialog({
      title: t('恢复默认服务端模板'),
      message: t('确定恢复默认服务端模板？这将还原内置标准服务端模板，并重新生成一个默认 VlessReality 节点（同时同步至客户端订阅）。'),
      confirmText: t('恢复默认服务端模板'),
      tone: 'rose',
      onConfirm: () => postAction('/config/reset-template', {}, 'reset-template'),
    })
  }

  async function resumeUpgradeIfRunning() {
    // Page opened/refreshed mid-upgrade: keep tracking it and auto-refresh when done.
    try {
      const res = await fetch('/api/upgrade-status', {
        headers: { Accept: 'application/json', 'X-Requested-With': 'fetch' },
        credentials: 'same-origin',
        cache: 'no-store',
      })
      if (!res.ok) return
      const d = await res.json()
      const age = Date.now() / 1000 - Number(d.started_at || 0)
      if (d && d.state === 'running' && age < 600) reloadPanelAfterUpgrade(d.from || state.version)
    } catch {}
  }

  async function reloadPanelAfterUpgrade(previousVersion) {
    // Upgrade runs detached on the server; the panel restarts during it.
    // Poll status (tolerating connection drops) until done, then report + reload.
    // Once we decide to reload, the page stays in the "upgrading" state until the browser
    // replaces it: location.reload() returns at once and the old page keeps rendering for a
    // moment, which used to flash the stale "update available" badge.
    const deadline = Date.now() + 360000
    let sawDown = false
    let stage = ''
    let reloading = false
    const reloadSoon = async (ms, version) => {
      reloading = true
      if (version) {
        state.version = version
        state.update_check = { ...state.update_check, panel: cgSlotAfterUpgrade(state.update_check.panel, version) }
      }
      await new Promise((r) => setTimeout(r, ms))
      window.location.reload()
    }
    upgradeInProgress.value = true
    try {
      while (Date.now() < deadline) {
        await new Promise((r) => setTimeout(r, 2000))
        let d = null
        try {
          const res = await fetch('/api/upgrade-status', {
            headers: { Accept: 'application/json', 'X-Requested-With': 'fetch' },
            credentials: 'same-origin',
            cache: 'no-store',
          })
          if (res.status === 401) { reloading = true; window.location.reload(); return }
          if (!res.ok) { sawDown = true; continue }
          d = await res.json()
        } catch {
          sawDown = true
          if (stage !== 'restart') { stage = 'restart'; showToast(t('面板正在重启，请稍候……'), true) }
          continue
        }
        // Panel came back on a different version: the upgrade landed even if the
        // status file is missing/unreadable (older builds wrote invalid JSON).
        if (d && d.version && previousVersion && d.version !== previousVersion && d.state !== 'running') {
          d = { state: 'done', rc: 0, version: d.version }
        }
        if (d && d.state === 'running' && d.version && previousVersion && d.version !== previousVersion && sawDown) {
          d = { state: 'done', rc: 0, version: d.version }
        }
        if (!d || d.state !== 'done') continue
        if (Number(d.rc) === 0) {
          showToast(t('升级成功！当前版本 {v}，即将刷新页面', { v: d.version || '' }), true)
          await reloadSoon(800, d.version)
          return
        }
        showToast(t('升级失败：{msg}', { msg: d.tail || `exit ${d.rc}` }), false)
        if (d.version && previousVersion && d.version !== previousVersion) {
          await reloadSoon(2500, d.version)
        }
        return
      }
      showToast(t('升级超时，正在刷新页面……'), false)
      await reloadSoon(1500, '')
    } finally {
      if (!reloading) upgradeInProgress.value = false
    }
  }


  const createRoutingForm = reactive({ name: '', rules_raw: '' })
  const importRoutingForm = reactive({ name: '', url: '' })

  const routingGroups = computed(() => {
    const g = state.routing && Array.isArray(state.routing.groups) ? state.routing.groups : []
    return g
  })

  const CLASSICAL_RULE_TYPES = new Set([
    'DOMAIN', 'DOMAIN-SUFFIX', 'DOMAIN-KEYWORD', 'DOMAIN-REGEX',
    'GEOSITE', 'GEOIP', 'IP-CIDR', 'IP-CIDR6', 'IP-ASN',
    'SRC-IP-CIDR', 'SRC-PORT', 'DST-PORT', 'PROCESS-NAME', 'PROCESS-PATH',
    'NETWORK', 'UID', 'IN-NAME', 'IN-TYPE',
  ])

  function routingNameTaken(name, exceptId = '') {
    const n = String(name || '').trim()
    return routingGroups.value.some((g) => g && g.name === n && g.id !== exceptId)
  }

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

  async function createRoutingGroup() {
    const name = createRoutingForm.name.trim()
    if (!name) {
      showToast(t('请填写分流组名称'), false)
      return
    }
    if (routingNameTaken(name)) {
      showToast(t('分流组名称已存在：{name}', { name }), false)
      return
    }
    const check = validateClassicalRulesPaste(createRoutingForm.rules_raw)
    if (!check.ok) {
      showToast(check.msg, false)
      return
    }
    const res = await postAction(
      '/routing/add',
      { name, rules_raw: createRoutingForm.rules_raw },
      'routing-add',
    )
    if (res && res.ok) {
      createRoutingForm.name = ''
      createRoutingForm.rules_raw = ''
    }
  }

  async function importRoutingGroup() {
    const name = importRoutingForm.name.trim()
    const url = importRoutingForm.url.trim()
    if (!name) {
      showToast(t('请填写分流组名称'), false)
      return
    }
    if (routingNameTaken(name)) {
      showToast(t('分流组名称已存在：{name}', { name }), false)
      return
    }
    const urlCheck = validateHttpUrl(url)
    if (!urlCheck.ok) {
      showToast(urlCheck.msg, false)
      return
    }
    const res = await postAction('/routing/import', { name, url }, 'routing-import')
    if (res && res.ok) {
      importRoutingForm.name = ''
      importRoutingForm.url = ''
    }
  }

  function confirmDeleteRouting(g) {
    if (!g || !g.deletable) {
      showToast(t('该分流组不可删除'), false)
      return
    }
    openConfirmDialog({ tone: 'rose', confirmText: t('确认删除'),
      title: t('删除分流组'),
      message: t('确定删除分流组「{name}」？', { name: g.name }),
      onConfirm: () => postAction('/routing/delete', { id: g.id }, `routing-del-${g.id}`),
    })
  }

  async function renameRouting(g) {
    if (!g) return
    renameDialog.id = g.id
    renameDialog.oldName = g.name
    renameDialog.name = g.name
    renameDialog.show = true
    nextTick(() => { const el = document.getElementById('rename-input'); if (el) { el.focus(); el.select() } })
  }

  const renameDialog = reactive({ show: false, id: '', oldName: '', name: '' })
  function closeRenameDialog() { renameDialog.show = false }
  async function acceptRenameDialog() {
    const trimmed = String(renameDialog.name || '').trim()
    if (!trimmed) {
      showToast(t('请填写分流组名称'), false)
      return
    }
    if (routingNameTaken(trimmed, renameDialog.id)) {
      showToast(t('分流组名称已存在：{name}', { name: trimmed }), false)
      return
    }
    const id = renameDialog.id
    renameDialog.show = false
    if (trimmed === renameDialog.oldName) return
    await postAction('/routing/rename', { id, name: trimmed }, `routing-rename-${id}`)
  }

  const routingPanelOpen = ref('')
  const routingRuleDraft = reactive({})
  const routingProvForm = reactive({ provider: '', url: '' })

  function isLocalRoutingGroup(g) {
    return g && (g.kind === 'local' || (!g.kind && !(g.rule_providers || []).length))
  }

  function toggleRoutingPanel(g) {
    if (!g) return
    if (routingPanelOpen.value === g.id) {
      routingPanelOpen.value = ''
      return
    }
    routingPanelOpen.value = g.id
    if (isLocalRoutingGroup(g)) {
      const lines = Array.isArray(g.classical_rules) ? g.classical_rules : []
      routingRuleDraft[g.id] = lines.map((r) => `- ${r}`).join('\n')
    } else {
      routingProvForm.provider = ''
      routingProvForm.url = ''
    }
  }

  async function saveLocalRoutingRules(g) {
    if (!g) return
    const raw = routingRuleDraft[g.id] || ''
    const check = validateClassicalRulesPaste(raw)
    if (!check.ok) {
      showToast(check.msg, false)
      return
    }
    await postAction('/routing/rules', { id: g.id, rules_raw: raw }, `routing-rules-${g.id}`)
  }

  async function addRoutingProvider(g) {
    const provider = routingProvForm.provider.trim()
    const url = routingProvForm.url.trim()
    if (!provider) {
      showToast(t('请填写规则集名称（英文）'), false)
      return
    }
    if (!/^[A-Za-z0-9_.-]{1,64}$/.test(provider)) {
      showToast(t('规则集名称只能用英文字母、数字、- _ .'), false)
      return
    }
    const urlCheck = validateHttpUrl(url)
    if (!urlCheck.ok) {
      showToast(urlCheck.msg, false)
      return
    }
    const res = await postAction('/routing/provider/add', { id: g.id, provider, url }, 'routing-prov-add')
    if (res && res.ok) { routingProvForm.provider = ''; routingProvForm.url = '' }
  }

  function deleteRoutingProvider(g, p) {
    if (!g || !p) {
      showToast(t('规则集不存在'), false)
      return
    }
    openConfirmDialog({ tone: 'rose', confirmText: t('确认删除'),
      title: t('删除规则集'),
      message: t('确定删除规则集「{name}」？', { name: p.name }),
      onConfirm: () => postAction('/routing/provider/delete', { id: g.id, provider: p.name }, `routing-prov-del-${p.name}`),
    })
  }

  const routingDragIdx = ref(-1)
  const routingDragOver = ref(-1)

  function onRoutingDragStart(idx, ev) {
    routingDragIdx.value = idx
    try { ev.dataTransfer.effectAllowed = 'move'; ev.dataTransfer.setData('text/plain', String(idx)) } catch (_) {}
  }

  async function onRoutingDrop(idx) {
    const from = routingDragIdx.value
    routingDragIdx.value = -1
    routingDragOver.value = -1
    if (from < 0 || from === idx) return
    if (busyKey.value) return
    const before = routingGroups.value.slice()
    const groups = before.slice()
    const [moved] = groups.splice(from, 1)
    groups.splice(idx, 0, moved)
    if (state.routing && Array.isArray(state.routing.groups)) state.routing.groups = groups
    const res = await postAction('/routing/reorder', { order: JSON.stringify(groups.map((g) => g.id)) }, 'routing-reorder')
    if (!(res && res.ok) && !(res && res.state && res.state.routing) && state.routing) state.routing.groups = before
  }

  // Pages that are locked in the current mode, with the toast that explains why.
  function tabLockedMsg(tab) {
    if (tab === 'advanced' && !state.custom_server_enabled) return t('高级功能请到设置页开启')
    if ((tab === 'routing' || tab === 'cluster') && state.custom_server_enabled) {
      return t('已启用自定义服务端配置，请自行修改相关配置')
    }
    return ''
  }

  function selectTab(tab) {
    if (!VALID_TABS.includes(tab)) return
    const locked = tabLockedMsg(tab)
    if (locked) {
      showToast(locked, false)
      return
    }
    activeTab.value = tab
    const targetPath = TAB_PATHS[tab] || '/'
    try {
      if (window.location.pathname !== targetPath) {
        window.history.pushState({ tab }, '', targetPath)
      }
    } catch {}
  }

  async function toggleCustomServer() {
    const next = !state.custom_server_enabled
    if (!next && state.custom_config_mode) {
      openConfirmDialog({
        title: t('关闭自定义服务端'),
        message: t('关闭后，服务端将切换回面板生成的默认配置（默认服务端模板）并立即重载。你的自定义配置会保留在服务器上，重新开启后可一键恢复。'),
        confirmText: t('关闭并切换'),
        tone: 'amber',
        onConfirm: () => applyCustomServer(false),
      })
      return
    }
    await applyCustomServer(next)
  }

  async function applyCustomServer(next) {
    const res = await postAction(
      '/action/settings',
      { custom_server_enabled: next ? '1' : '0' },
      '/action/settings'
    )
    if (res && res.ok && !next && activeTab.value === 'advanced') selectTab('inbounds')
    if (res && res.ok && next && (activeTab.value === 'routing' || activeTab.value === 'cluster')) selectTab('inbounds')
  }

  async function toggleAutoUpdate() {
    const next = !state.auto_update
    await postAction(
      '/action/settings',
      { auto_update: next ? '1' : '0' },
      '/action/settings'
    )
  }

  function setUpdateChannel(channel) {
    const next = channel === 'test' ? 'test' : 'stable'
    if (next === 'test' && state.update_channel !== 'test') {
      openConfirmDialog({
        title: t('切换到测试通道'),
        message: t('测试版可能不稳定，可能出现功能异常或兼容性问题。切换后将立即更新到测试通道最新版本，确定切换？'),
        confirmText: t('确认切换'),
        tone: 'amber',
        onConfirm: () => applyUpdateChannel(next),
      })
      return
    }
    if (next === 'stable' && state.update_channel !== 'stable') {
      openConfirmDialog({
        title: t('切换到正式通道'),
        message: t('切换到正式通道并立即更新到正式版最新版本，确定切换？'),
        confirmText: t('确认切换'),
        tone: 'amber',
        onConfirm: () => applyUpdateChannel(next),
      })
      return
    }
    return applyUpdateChannel(next)
  }

  async function applyUpdateChannel(next) {
    const prev = state.update_channel
    // Always POST so legacy Beat installs migrate env to ClashGate/ClashGate@branch even if UI already shows 测试.
    const res = await postAction(
      '/action/settings',
      { update_channel: next },
      '/action/settings'
    )
    if (res && res.ok) {
      state.update_channel = next
      state.update_channel_label = next === 'test' ? t('测试') : t('正式')
      // Every real channel switch pulls that channel's latest build right away.
      if (prev !== next) {
        showToast(t('已切换通道，正在更新到该通道最新版本……'), true)
        await postAction('/action/upgrade-self', {}, '/action/upgrade-self')
      }
    }
  }

  function masqueNodeName(name) {
    const n = String(name || 'Cloudflare-MASQUE').trim()
    return n.startsWith('⛅️') ? n : `⛅️ ${n}`
  }

  function masqueYamlNamed(yaml, name) {
    const raw = String(yaml || '').trim().replace(/^-+\s*/, '')
    try {
      const obj = JSON.parse(raw)
      obj.name = name
      return '- ' + JSON.stringify(obj)
    } catch {
      return yaml
    }
  }

  async function addMasqueOutbound() {
    if (!state.masque.yaml) return
    const name = masqueNodeName(state.masque.name)
    if (state.proxies.some((p) => p && (p.name === name || p.name === String(state.masque.name || '').trim()))) {
      showToast(t('请勿重复加入'), false)
      return
    }
    await postAction('/proxies/add', { proxies_raw: masqueYamlNamed(state.masque.yaml, name) }, 'add-masque')
  }

  async function retryMasque() {
    const res = await postAction('/action/masque-register', {}, '/action/masque-register')
    if (res && res.ok && !(res.state && res.state.masque)) state.masque = { ...state.masque, status: 'pending', error: '' }
  }

  onMounted(() => {
    if (boot.flash_msg) {
      showToast(boot.flash_msg, boot.flash_ok !== false)
    }
    const lockedMsg = tabLockedMsg(activeTab.value)
    if (lockedMsg) {
      activeTab.value = 'inbounds'
      try { window.history.replaceState({ tab: 'inbounds' }, '', '/') } catch {}
      showToast(lockedMsg, false)
    }
    window.addEventListener('popstate', () => {
      const next = tabFromPath()
      const locked = tabLockedMsg(next)
      if (locked) {
        activeTab.value = 'inbounds'
        try { window.history.replaceState({ tab: 'inbounds' }, '', '/') } catch {}
        showToast(locked, false)
        return
      }
      activeTab.value = next
    })
    resumeUpgradeIfRunning()
    window.addEventListener('blur', maskAllSensitive)
    document.addEventListener('visibilitychange', handleVisibilityChange)
    document.addEventListener('pointerdown', handleDocumentPointerDown)
    document.addEventListener('keydown', handleKeydown)
    nextTick(scrollActiveNavIntoView)
    if (pageMode.value === 'dashboard') {
      statePollTimer = setInterval(refreshServerStateSilent, 15000)
    }
  })

  onUnmounted(() => {
    if (statePollTimer) clearInterval(statePollTimer)
    window.removeEventListener('blur', maskAllSensitive)
    document.removeEventListener('visibilitychange', handleVisibilityChange)
    document.removeEventListener('pointerdown', handleDocumentPointerDown)
    document.removeEventListener('keydown', handleKeydown)
  })

  return (_panel = {
    boot,
    pageMode,
    isXmas,
    state,
    normalizeCluster,
    showPendingDiff,
    showVersionPanel,
    showTrafficDetail,
    showSubQrModal,
    zbUrlRevealed,
    zbSecretRevealed,
    subUrlRevealed,
    cfTokenRevealed,
    zbUrlEl,
    zbSecretEl,
    subUrlEl,
    cfTokenEl,
    revealZbUrl,
    revealZbSecret,
    revealSubUrl,
    revealCfToken,
    maskAllSensitive,
    handleDocumentPointerDown,
    handleKeydown,
    handleVisibilityChange,
    showPasswordModal,
    passwordForm,
    openPasswordModal,
    closePasswordModal,
    submitChangePassword,
    confirmDialog,
    openConfirmDialog,
    closeConfirmDialog,
    cancelConfirmDialog,
    acceptConfirmDialog,
    confirmDiscardPending,
    formatPendingItem,
    topbarVersionText,
    pageTitle,
    coreUpdate,
    panelUpdate,
    cgVersionTuple,
    cgVersionNewer,
    cgShowUpdate,
    cgSlotAfterUpgrade,
    upgradeInProgress,
    panelHasUpdate,
    coreHasUpdate,
    versionLabel,
    updateHint,
    applyUpdateCheck,
    mergeUpdateSlot,
    converterPlaceholder,
    VALID_TABS,
    TAB_PATHS,
    detectInitialTab,
    tabFromPath,
    activeTab,
    scrollActiveNavIntoView,
    busyKey,
    copiedKey,
    langOpen,
    langMenuStyle,
    toast,
    toastTimer,
    toggleLangMenu,
    pickLang,
    showToast,
    PROTOCOLS,
    DEFAULT_NAMES,
    PROTOCOL_MAP,
    inboundForm,
    currentProtocol,
    currentDefaultName,
    PROTOCOL_HAS_OPTION,
    sniEditable,
    providerForm,
    proxiesRaw,
    customConfigText,
    converterInput,
    converterOutput,
    converterError,
    certModeForm,
    certRegenLock,
    certModeValue,
    certModeLabel,
    certDomainDisplay,
    certIssuerDisplay,
    certExpiresDisplay,
    certDaysValue,
    certIsTemp,
    certBaselineMode,
    certModeDirty,
    certRegenDisabled,
    submitCertMode,
    trafficDisplay,
    trafficDetail,
    updateCoreDirect,
    toggleVersionPanel,
    checkUpdateAndPrompt,
    statePollTimer,
    refreshServerStateSilent,
    applyServerState,
    formatFetchError,
    postAction,
    copyRaw,
    pendingAddReqId,
    submitAddInbound,
    resetInboundPassword,
    deleteInbound,
    resetSubUrl,
    resetZbSecret,
    submitAddProvider,
    deleteProvider,
    submitAddProxies,
    deleteProxy,
    CG_NODE_NAME_MAX,
    CG_NODE_NAME_BAD,
    CG_RESERVED_PROXY_NAMES,
    nodeNameError,
    nodeNameInput,
    nodeNameSaved,
    nodeNameLength,
    nodeNameOverLimit,
    nodeNameHint,
    saveNodeName,
    clusterForm,
    clusterTouched,
    clusterUrlError,
    clusterUrlErr,
    clusterPwErr,
    submitAddCluster,
    removeClusterMember,
    listSep,
    syncCluster,
    leaveCluster,
    loadFileInto,
    fillCurrentInboundsToConverter,
    convertConfigFormat,
    CG_CERT_PATH,
    CG_KEY_PATH,
    isCertPathValue,
    fixCertPaths,
    saveCustomConfig,
    submitCustomConfig,
    resetTemplateConfig,
    resumeUpgradeIfRunning,
    reloadPanelAfterUpgrade,
    createRoutingForm,
    importRoutingForm,
    routingGroups,
    CLASSICAL_RULE_TYPES,
    routingNameTaken,
    validateClassicalRulesPaste,
    validateHttpUrl,
    createRoutingGroup,
    importRoutingGroup,
    confirmDeleteRouting,
    renameRouting,
    renameDialog,
    closeRenameDialog,
    acceptRenameDialog,
    routingPanelOpen,
    routingRuleDraft,
    routingProvForm,
    isLocalRoutingGroup,
    toggleRoutingPanel,
    saveLocalRoutingRules,
    addRoutingProvider,
    deleteRoutingProvider,
    routingDragIdx,
    routingDragOver,
    onRoutingDragStart,
    onRoutingDrop,
    tabLockedMsg,
    selectTab,
    toggleCustomServer,
    applyCustomServer,
    toggleAutoUpdate,
    setUpdateChannel,
    applyUpdateChannel,
    masqueNodeName,
    masqueYamlNamed,
    addMasqueOutbound,
    retryMasque,
  })
}
