// Panel state, API calls, and form handlers shared by App.vue and page components.
// Core state (boot data, toast, dialogs, postAction, server-state sync, tabs) lives here; each page's
// own state and actions are in the use*.js modules next to this file and receive the shared core.
import { ref, reactive, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { t, lang, setLang, LANGS, langLabel } from '../i18n.js'
import { theme, setTheme } from '../theme.js'
import { formatFetchError, postForm } from './api.js'
import {
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
} from './validation.js'
import { useCerts } from './useCerts.js'
import { useRouting } from './useRouting.js'
import { useCluster } from './useCluster.js'
import { useConverter } from './useConverter.js'
import { useCustomConfig } from './useCustomConfig.js'
import { useOutbounds } from './useOutbounds.js'
import { useInbounds } from './useInbounds.js'
import { useUpdates } from './useUpdates.js'
import { useSettings } from './useSettings.js'

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
    if (cfTokenRevealed.value && target && target.closest && !target.closest('#cf-token-wrap')) {
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
      message: t('确定丢弃所有待应用草稿？丢弃后未生效的变更将全部撤销，回到当前线上配置。'),
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
  const toast = reactive({ show: false, msg: '', ok: true, detail: '', open: false })
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

  // detail: raw program output for a failed action, shown folded under 「详情」. A toast with details
  // stays longer, and stays open while the user reads them.
  function showToast(msg, ok = true, detail = '') {
    if (!msg) return
    toast.msg = msg
    toast.ok = ok
    toast.detail = ok ? '' : String(detail || '')
    toast.open = false
    toast.show = true
    armToastTimer(toast.detail ? 12000 : 4500)
  }

  function armToastTimer(ms) {
    if (toastTimer) clearTimeout(toastTimer)
    toastTimer = setTimeout(() => {
      if (!toast.open) toast.show = false
    }, ms)
  }

  function toggleToastDetail() {
    toast.open = !toast.open
    if (!toast.open) armToastTimer(4500)
  }

  function closeToast() {
    toast.open = false
    toast.show = false
  }

  const customConfigText = ref(state.custom_config_raw || '')

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

  // Home status rail ---------------------------------------------------------------------------
  // Same units as the server's format_traffic_detail (1024-based).
  function fmtBytes(b) {
    const n = Math.max(0, Number(b) || 0)
    if (n >= 1024 ** 4) return `${(n / 1024 ** 4).toFixed(2)} TB`
    if (n >= 1024 ** 3) return `${(n / 1024 ** 3).toFixed(2)} GB`
    if (n >= 1024 ** 2) return `${(n / 1024 ** 2).toFixed(1)} MB`
    if (n >= 1024) return `${(n / 1024).toFixed(0)} KB`
    return `${Math.round(n)} B`
  }

  const trafficUp = computed(() => fmtBytes(state.status && state.status.traffic_up_bytes))
  const trafficDown = computed(() => fmtBytes(state.status && state.status.traffic_down_bytes))

  // Current speed: the difference between two state refreshes (every 15 s while the page is open).
  const trafficRate = ref(null)
  let trafficSample = null
  function noteTrafficSample() {
    const s = state.status || {}
    if (s.traffic_up_bytes === undefined || s.traffic_down_bytes === undefined) return
    const up = Number(s.traffic_up_bytes) || 0
    const down = Number(s.traffic_down_bytes) || 0
    const now = Date.now()
    const prev = trafficSample
    if (prev && now - prev.at < 3000) return   // an action answer right after a poll: keep the older sample
    trafficSample = { up, down, at: now }
    if (!prev) return
    const dt = (now - prev.at) / 1000
    if (dt > 120 || up < prev.up || down < prev.down) {
      trafficRate.value = null   // too old to mean "now", or the counters were reset
      return
    }
    trafficRate.value = { up: fmtBytes((up - prev.up) / dt), down: fmtBytes((down - prev.down) / dt) }
  }

  const coreTone = computed(() => {
    const s = state.status || {}
    if (s.state_cls === 'bad') return 'bad'
    if (s.state_cls === 'warn') return 'warn'
    const total = Number(s.live_total)
    if (total > 0 && Number(s.live_up) < total) return 'warn'
    return 'ok'
  })

  const nodesOnlineText = computed(() => {
    const s = state.status || {}
    const total = s.live_total === undefined || s.live_total === null ? Number(s.inbound_total || 0) : Number(s.live_total)
    const up = s.live_up === undefined || s.live_up === null ? Number(s.inbound_listening || 0) : Number(s.live_up)
    if (!total) return t('还没有节点')
    return t('节点 {up}/{total} 在线', { up, total })
  })

  const uptimeText = computed(() => {
    const sec = Number(state.status && state.status.uptime_s)
    if (!Number.isFinite(sec) || sec < 0 || state.status.uptime_s === null || state.status.uptime_s === undefined) return ''
    const d = Math.floor(sec / 86400)
    const h = Math.floor((sec % 86400) / 3600)
    const m = Math.floor((sec % 3600) / 60)
    if (d > 0) return t('已运行 {d} 天 {h} 小时', { d, h })
    if (h > 0) return t('已运行 {h} 小时 {m} 分钟', { h, m })
    return t('已运行 {m} 分钟', { m: Math.max(1, m) })
  })

  // Nodes the core serves now (same count as 「节点 x/y 在线」 on the status rail).
  const liveNodeCount = computed(() => {
    const total = state.status && state.status.live_total
    if (total !== undefined && total !== null) return Number(total)
    return state.inbounds.filter((i) => !i.pending_reload || i.pending_delete).length
  })

  function togglePendingDiff() {
    if (state.pending_reload_count > 0) showPendingDiff.value = !showPendingDiff.value
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
      if (res.status === 401) {
        // Session expired (password changed elsewhere, or 7 days passed): show the login page.
        window.location.href = '/login'
        return
      }
      if (res.ok) {
        const data = await res.json()
        if (data) {
          if (data.mihomo_version) state.mihomo_version = data.mihomo_version
          if (data.pending_reload_count !== undefined) {
            state.pending_reload_count = Number(data.pending_reload_count || 0)
            if (state.pending_reload_count === 0) showPendingDiff.value = false
          }
          if (Array.isArray(data.pending_reload_items)) {
            state.pending_reload_items = data.pending_reload_items
          }
          // Node status (running / pending) changes when a config is applied elsewhere.
          if (Array.isArray(data.inbounds)) state.inbounds = data.inbounds
          if (data.status) {
            Object.assign(state.status, data.status)
            if (data.status.mihomo_version) state.mihomo_version = data.status.mihomo_version
            noteTrafficSample()
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
      noteTrafficSample()
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

  async function postAction(url, params = {}, key = url, opts = {}) {
    if (busyKey.value) {
      // A click while another action is still running used to do nothing at all.
      if (!opts.silentToast) showToast(t('上一个操作还在进行，请稍候'), false)
      return null
    }
    busyKey.value = key
    const versionBefore = state.version
    const ctrl = window.AbortController ? new AbortController() : null
    const timer = ctrl ? setTimeout(() => ctrl.abort(), 120000) : null
    try {
      const { data, unauthorized } = await postForm(url, params, {
        csrf: state.csrf,
        signal: ctrl ? ctrl.signal : undefined,
      })
      if (timer) clearTimeout(timer)
      if (unauthorized) return null
      if (data.state) {
        applyServerState(data.state)
      } else {
        if (data.zb_url) state.zb_url = data.zb_url
        if (data.sub_url) state.sub_url = data.sub_url
      }
      if (!opts.silentToast) showToast(data.msg || (data.ok ? t('操作成功') : t('操作失败')), !!data.ok, data.detail)
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
          if (url === '/action/reload' && Number(stData.pending_reload_count || 0) === 0) {
            showToast(t('已应用配置并更新客户端订阅'), true)
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

  // 「应用配置」 with nothing pending still rebuilds the config and reloads the core: ask first.
  function applyConfig() {
    if (busyKey.value) return
    if (state.pending_reload_count > 0) return postAction('/action/reload', {}, '/action/reload')
    openConfirmDialog({
      title: t('应用配置'),
      message: t('当前没有待应用的修改。仍要重新生成服务端配置并重载内核吗？已有连接可能会短暂中断。'),
      confirmText: t('仍然应用'),
      tone: 'amber',
      onConfirm: () => postAction('/action/reload', {}, '/action/reload'),
    })
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

  function resetSubUrl() {
    openConfirmDialog({
      title: t('更换订阅链接'),
      message: t('确定更换订阅链接？需点击顶部「应用配置」后新订阅链接才会生效（应用后旧链接失效）。在服务器上执行 clashgate reset-sub 则会立即更换。'),
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
      message: t('确定重置 Zashboard API 密钥？需点击顶部「应用配置」后直连地址才会更新。'),
      confirmText: t('确认重置'),
      tone: 'amber',
      onConfirm: async () => {
        maskAllSensitive()
        await postAction('/action/reset-secret', {}, 'reset-secret')
        maskAllSensitive()
      },
    })
  }

  // Pages that are locked in the current mode, with the toast that explains why.
  function tabLockedMsg(tab) {
    if (tab === 'advanced' && !state.custom_server_enabled) return t('高级功能请到设置页开启')
    if (tab === 'routing' && state.custom_server_enabled) {
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
    if (pageMode.value === 'dashboard') {
      resumeCertTaskIfRunning()
      resumeClusterTaskIfRunning()
    }
    window.addEventListener('blur', maskAllSensitive)
    document.addEventListener('visibilitychange', handleVisibilityChange)
    document.addEventListener('pointerdown', handleDocumentPointerDown)
    document.addEventListener('keydown', handleKeydown)
    nextTick(scrollActiveNavIntoView)
    if (pageMode.value === 'dashboard') {
      // Tab title shows the pending count, e.g. "(3) ClashGate", so other open tabs show it too.
      const baseTitle = document.title || 'ClashGate'
      watch(
        () => state.pending_reload_count,
        (n) => { document.title = n > 0 ? `(${n}) ${baseTitle}` : baseTitle },
        { immediate: true }
      )
      noteTrafficSample()   // first sample: the page's own boot data
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

  // Page-specific state and actions live in their own modules and share the state above.
  const shared = { activeTab, applyServerState, busyKey, customConfigText, maskAllSensitive, openConfirmDialog, postAction, selectTab, showToast, showVersionPanel, state }
  const {
    certModeForm,
    certRegenLock,
    certModeValue,
    certModeLabel,
    certDomainDisplay,
    certIssuerDisplay,
    certExpiresDisplay,
    certDaysValue,
    certIsTemp,
    certAlert,
    certBaselineMode,
    certModeDirty,
    certRegenDisabled,
    certTaskElapsed,
    resumeCertTaskIfRunning,
    confirmCertRenew,
    submitCertMode,
  } = useCerts(shared)
  const {
    createRoutingForm,
    importRoutingForm,
    routingGroups,
    routingNameTaken,
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
    moveRoutingGroup,
  } = useRouting(shared)
  const {
    nodeNameInput,
    nodeNameSaved,
    nodeNameLength,
    nodeNameOverLimit,
    nodeNameHint,
    saveNodeName,
    clusterForm,
    clusterTouched,
    clusterUrlErr,
    clusterPwErr,
    submitAddCluster,
    removeClusterMember,
    listSep,
    syncCluster,
    leaveCluster,
    clusterTask,
    taskTitle,
    resumeClusterTaskIfRunning,
    dismissPending,
  } = useCluster(shared)
  const {
    converterInput,
    converterOutput,
    converterError,
    loadFileInto,
    fillCurrentInboundsToConverter,
    convertConfigFormat,
  } = useConverter(shared)
  const {
    saveCustomConfig,
    submitCustomConfig,
    resetTemplateConfig,
  } = useCustomConfig(shared)
  const {
    providerForm,
    proxiesRaw,
    submitAddProvider,
    deleteProvider,
    submitAddProxies,
    deleteProxy,
    masqueNodeName,
    masqueYamlNamed,
    addMasqueOutbound,
    retryMasque,
  } = useOutbounds(shared)
  const {
    PROTOCOLS,
    DEFAULT_NAMES,
    PROTOCOL_MAP,
    inboundForm,
    currentProtocol,
    currentDefaultName,
    PROTOCOL_HAS_OPTION,
    sniEditable,
    pendingAddReqId,
    submitAddInbound,
    resetInboundPassword,
    deleteInbound,
  } = useInbounds(shared)
  const {
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
    confirmUpdateCore,
    updateCoreDirect,
    toggleVersionPanel,
    checkUpdateAndPrompt,
    resumeUpgradeIfRunning,
    reloadPanelAfterUpgrade,
  } = useUpdates(shared)
  const {
    showPasswordModal,
    passwordForm,
    openPasswordModal,
    closePasswordModal,
    submitChangePassword,
    toggleCustomServer,
    applyCustomServer,
    toggleAutoUpdate,
    setUpdateChannel,
    applyUpdateChannel,
  } = useSettings(shared)

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
    certTaskElapsed,
    certModeValue,
    certModeLabel,
    certDomainDisplay,
    certIssuerDisplay,
    certExpiresDisplay,
    certDaysValue,
    certIsTemp,
    certAlert,
    certBaselineMode,
    certModeDirty,
    certRegenDisabled,
    submitCertMode,
    trafficDisplay,
    trafficDetail,
    trafficUp,
    trafficDown,
    trafficRate,
    coreTone,
    nodesOnlineText,
    uptimeText,
    liveNodeCount,
    togglePendingDiff,
    updateCoreDirect,
    confirmUpdateCore,
    confirmCertRenew,
    toggleToastDetail,
    closeToast,
    toggleVersionPanel,
    checkUpdateAndPrompt,
    statePollTimer,
    refreshServerStateSilent,
    applyServerState,
    formatFetchError,
    postAction,
    applyConfig,
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
    clusterTask,
    taskTitle,
    dismissPending,
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
    moveRoutingGroup,
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
