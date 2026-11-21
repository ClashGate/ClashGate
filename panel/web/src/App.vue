<script setup>
import { t, lang, setLang, LANGS, langLabel } from './i18n.js'
import CgIcon from './CgIcon.vue'
import XmasArt from './XmasArt.vue'
import { theme, setTheme } from './theme.js'
import { usePanel } from './composables/usePanel.js'
import InboundsPage from './pages/InboundsPage.vue'
import OutboundsPage from './pages/OutboundsPage.vue'
import RoutingPage from './pages/RoutingPage.vue'
import ClusterPage from './pages/ClusterPage.vue'
import ReadablePage from './pages/ReadablePage.vue'
import AdvancedPage from './pages/AdvancedPage.vue'
import CertsPage from './pages/CertsPage.vue'
import SettingsPage from './pages/SettingsPage.vue'

const {
  boot,
  pageMode,
  isXmas,
  state,
  normalizeCluster,
  showPendingDiff,
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
  toggleToastDetail,
  closeToast,
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
} = usePanel()
</script>

<template>
  <!-- Login -->
  <div v-if="pageMode === 'login'" class="cg-login">
    <template v-if="isXmas">
      <XmasArt kind="snow" />
      <div class="cg-xmas-login" aria-hidden="true"><XmasArt kind="scene" /></div>
    </template>
    <div class="cg-login-card">
      <XmasArt v-if="isXmas" kind="holly" />
      <div class="flex justify-end mb-4">
        <div class="cg-lang">
          <button
            type="button"
            class="cg-lang-btn"
            :aria-expanded="langOpen ? 'true' : 'false'"
            :aria-label="t('语言')"
            @click="toggleLangMenu"
          >
            <CgIcon name="lang" :size="14" />
            <span>{{ langLabel(lang) }}</span>
            <svg class="cg-lang-caret" viewBox="0 0 12 12" aria-hidden="true"><path d="M2.5 4.5 6 8l3.5-3.5" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </button>
        </div>
      </div>
      <div class="flex items-center gap-3.5 mb-7">
        <span class="cg-logo-wrap"><img src="/assets/logo.png" alt="" class="cg-logo" /><XmasArt v-if="isXmas" kind="hat" /></span>
        <div>
          <div class="flex items-center gap-2">
            <h1 class="cg-wordmark text-[22px] leading-none text-slate-900">ClashGate</h1>
            <span dir="ltr" class="px-2 py-0.5 text-[11px] font-medium rounded-full bg-slate-100 text-slate-600 border border-slate-200 tabular-nums">
              {{ topbarVersionText }}
            </span>
          </div>
          <p class="text-xs text-slate-500 mt-1.5">{{ t('采用 Mihomo 核心，简单安全。') }}</p>
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

  <!-- Dashboard -->
  <div v-else class="cg-app min-h-screen text-slate-900">
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
        id="cg-toast"
        role="status"
        aria-live="polite"
        class="fixed top-18 inset-x-4 sm:inset-x-auto sm:end-6 z-[60] sm:max-w-md rounded-2xl px-4 py-3 shadow-[0_10px_30px_-8px_rgba(15,23,42,0.14)] border text-sm font-medium bg-white/95 backdrop-blur-md"
        :class="
          toast.ok
            ? 'border-emerald-200/90 text-emerald-950'
            : 'border-rose-200/90 text-rose-950'
        "
      >
        <div class="flex items-center gap-2.5">
          <span
            class="w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold shrink-0"
            :class="toast.ok ? 'bg-emerald-500 text-white' : 'bg-rose-500 text-white'"
          >
            {{ toast.ok ? '✓' : '!' }}
          </span>
          <span class="cg-wrap leading-snug flex-1 min-w-0">{{ toast.msg }}</span>
          <button
            v-if="toast.detail"
            id="cg-toast-detail-toggle"
            type="button"
            class="shrink-0 px-2 py-0.5 rounded-md text-xs font-semibold border border-rose-200 bg-white hover:bg-rose-50 text-rose-700 cursor-pointer"
            :aria-expanded="toast.open ? 'true' : 'false'"
            @click="toggleToastDetail"
          >{{ toast.open ? t('收起') : t('详情') }}</button>
          <button
            v-if="toast.detail"
            type="button"
            class="shrink-0 w-6 h-6 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-100 cursor-pointer"
            :aria-label="t('关闭')"
            @click="closeToast"
          >✕</button>
        </div>
        <pre
          v-if="toast.detail && toast.open"
          id="cg-toast-detail"
          dir="ltr"
          class="mt-2.5 max-h-48 overflow-auto rounded-lg bg-slate-50 border border-slate-200/80 px-3 py-2 text-[11px] leading-relaxed text-slate-700 font-mono whitespace-pre-wrap break-all text-start"
        >{{ toast.detail }}</pre>
      </div>
    </transition>

    <!-- In-Panel Rename Modal -->
    <Transition name="cg-modal">
      <div
        v-if="renameDialog.show"
        id="rename-modal"
        class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/25 backdrop-blur-[2px]"
        @click.self="closeRenameDialog"
      >
        <div class="cg-modal-panel w-full max-w-md bg-white rounded-2xl border border-slate-200/90 p-6 shadow-[0_20px_50px_-12px_rgba(15,23,42,0.18)] space-y-4">
          <div class="flex items-center justify-between gap-2">
            <h3 class="text-base font-bold text-slate-900 tracking-tight">{{ t('重命名') }}</h3>
            <button type="button" @click="closeRenameDialog" class="text-slate-400 hover:text-slate-600 hover:bg-slate-100 text-sm w-7 h-7 flex items-center justify-center rounded-lg transition cursor-pointer">✕</button>
          </div>
          <label class="block text-xs font-medium text-slate-500">{{ t('新名称') }}
            <input id="rename-input" v-model="renameDialog.name" @keydown.enter.prevent="acceptRenameDialog" @keydown.esc="closeRenameDialog" class="cg-input mt-1 w-full h-10 px-3 rounded-xl border border-slate-200 text-sm" />
          </label>
          <div class="flex items-center justify-end gap-2.5 pt-2">
            <button type="button" @click="closeRenameDialog" class="px-4 py-2 rounded-xl text-xs font-medium bg-slate-100 hover:bg-slate-200/80 text-slate-700 transition cursor-pointer">{{ t('取消') }}</button>
            <button type="button" @click="acceptRenameDialog" :disabled="!String(renameDialog.name || '').trim()" class="cg-btn-primary px-4 py-2 rounded-xl text-xs font-semibold transition cursor-pointer">{{ t('确认') }}</button>
          </div>
        </div>
      </div>
    </Transition>

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
          <p class="text-sm text-slate-600 leading-relaxed cg-wrap">{{ confirmDialog.message }}</p>
          <div class="flex flex-wrap items-center justify-end gap-2.5 pt-2">
            <button
              type="button"
              @click="cancelConfirmDialog"
              class="px-4 py-2 rounded-xl text-xs font-medium bg-slate-100 hover:bg-slate-200/80 text-slate-700 transition cursor-pointer"
            >
              {{ confirmDialog.cancelText || t('取消') }}
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
              @click="showSubQrModal = false"
              class="px-4 py-2 rounded-xl text-xs font-medium bg-slate-100 hover:bg-slate-200/80 text-slate-700 transition cursor-pointer"
            >
              {{ t('关闭') }}
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <XmasArt v-if="isXmas" kind="snow" />
    <div class="cg-shell">
      <aside class="cg-side">
        <div class="cg-brand">
          <span class="cg-logo-wrap"><img src="/assets/logo.png" alt="" class="cg-logo" /><XmasArt v-if="isXmas" kind="hat" /></span>
          <div class="min-w-0">
            <div class="cg-wordmark text-[18px] leading-none text-[#1a2330]">ClashGate</div>
            <div class="cg-brand-sub">{{ t('简单安全的 Mihomo 服务端') }}</div>
          </div>
        </div>
        <div class="cg-nav-label">{{ t('导航') }}</div>
        <nav class="flex flex-col gap-1" aria-label="pages">
          <button type="button" class="cg-nav" :class="{ 'is-active': activeTab === 'inbounds' }" @click="selectTab('inbounds')">
            <CgIcon name="house" />{{ t('首页') }}
          </button>
          <button type="button" class="cg-nav" :class="{ 'is-active': activeTab === 'outbounds' }" @click="selectTab('outbounds')">
            <CgIcon name="outbound" />{{ t('服务端出站') }}
          </button>
          <button type="button" class="cg-nav" :class="state.custom_server_enabled ? 'is-locked' : { 'is-active': activeTab === 'routing' }" @click="selectTab('routing')">
            <CgIcon :name="state.custom_server_enabled ? 'lock' : 'routing'" />{{ t('服务端分流') }}
          </button>
          <button type="button" class="cg-nav" :class="state.custom_server_enabled ? 'is-locked' : { 'is-active': activeTab === 'cluster' }" @click="selectTab('cluster')">
            <CgIcon :name="state.custom_server_enabled ? 'lock' : 'cluster'" />{{ t('集群') }}
          </button>
          <button type="button" class="cg-nav" :class="{ 'is-active': activeTab === 'readable' }" @click="selectTab('readable')">
            <CgIcon name="convert" />{{ t('节点转换') }}
          </button>
          <button id="tab-certs" type="button" class="cg-nav" :class="{ 'is-active': activeTab === 'certs' }" @click="selectTab('certs')">
            <CgIcon name="shield" />{{ t('HTTPS 证书') }}
          </button>
          <button
            type="button"
            class="cg-nav"
            :class="state.custom_server_enabled ? { 'is-active': activeTab === 'advanced' } : 'is-locked'"
            @click="selectTab('advanced')"
          >
            <CgIcon :name="state.custom_server_enabled ? 'server' : 'lock'" />{{ t('自定义服务端') }}
          </button>
          <button type="button" class="cg-nav" :class="{ 'is-active': activeTab === 'settings' }" @click="selectTab('settings')">
            <CgIcon name="settings" />{{ t('设置') }}
          </button>
        </nav>
        <div v-if="isXmas" class="cg-xmas-side" aria-hidden="true"><XmasArt kind="scene" /></div>
      </aside>

      <div class="cg-column">
    <!-- Topbar -->
    <header class="sticky top-0 z-30 cg-top">
      <div class="cg-topbar px-4 sm:px-6 h-16 flex items-center justify-between gap-3">
        <div class="flex items-center gap-2.5 min-w-0 lg:hidden">
          <span class="cg-logo-wrap"><img src="/assets/logo.png" alt="" class="cg-logo" /><XmasArt v-if="isXmas" kind="hat" /></span>
          <span class="cg-wordmark text-[18px] text-slate-900">ClashGate</span>
        </div>
        <div class="hidden lg:block min-w-0">
          <div class="cg-page-title">{{ pageTitle }}</div>
        </div>

        <div class="cg-actions justify-end">
          <button
            type="button"
            :disabled="busyKey === '/action/reload'"
            @click="postAction('/action/reload', {}, '/action/reload')"
            class="px-3 py-1.5 rounded-lg text-xs font-semibold border disabled:opacity-50 transition cursor-pointer inline-flex items-center gap-1.5"
            :class="
              state.pending_reload_count > 0
                ? 'bg-amber-50 hover:bg-amber-100/80 border-amber-300/90 text-amber-900'
                : 'bg-white hover:bg-slate-50 border-slate-200 text-slate-800'
            "
          >
            <span>{{ busyKey === '/action/reload' ? t('应用中…') : t('应用配置') }}</span>
            <span
              v-if="state.pending_reload_count > 0"
              class="px-1.5 py-0.2 text-[10px] font-bold rounded-full bg-amber-500 text-white tabular-nums"
            >
              {{ state.pending_reload_count }}
            </span>
          </button>
          <button
            type="button"
            :disabled="busyKey === '/action/check-update' || busyKey === '/action/upgrade-self' || upgradeInProgress"
            @click="checkUpdateAndPrompt"
            class="cg-tool px-3 py-1.5 rounded-lg text-xs font-medium bg-white hover:bg-slate-50 border border-slate-200 disabled:opacity-50 text-slate-700 transition cursor-pointer inline-flex items-center gap-1.5"
            :class="{ 'is-update': panelHasUpdate }"
            :title="panelHasUpdate ? updateHint(panelUpdate.latest) : undefined"
          >
            <span>{{
              busyKey === '/action/upgrade-self' || upgradeInProgress
                ? t('升级中…')
                : busyKey === '/action/check-update'
                  ? t('检查中…')
                  : t('检查更新')
            }}</span>
            <CgIcon v-if="panelHasUpdate && busyKey !== '/action/check-update' && busyKey !== '/action/upgrade-self'" name="up" :size="13" />
          </button>
          <div class="cg-lang">
            <button
              type="button"
              class="cg-lang-btn"
              :aria-expanded="langOpen ? 'true' : 'false'"
              :aria-label="t('语言')"
              @click="toggleLangMenu"
            >
              <CgIcon name="lang" :size="14" />
              <span>{{ langLabel(lang) }}</span>
              <svg class="cg-lang-caret" viewBox="0 0 12 12" aria-hidden="true"><path d="M2.5 4.5 6 8l3.5-3.5" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </button>
          </div>
          <form method="post" action="/logout" class="inline">
            <input type="hidden" name="csrf" :value="state.csrf" />
            <button
              type="submit"
              class="px-2.5 py-1.5 rounded-lg text-xs font-medium bg-white hover:bg-rose-50 hover:text-rose-700 hover:border-rose-200 border border-slate-200 text-slate-600 transition cursor-pointer inline-flex items-center gap-1"
            >
              <CgIcon name="logout" :size="14" />
              {{ t('退出') }}
            </button>
          </form>
        </div>
      </div>
    </header>

    <!-- Main Container -->
    <main class="max-w-7xl w-full mx-auto px-4 sm:px-6 py-6 sm:py-7 space-y-6 flex-1">
      <!-- Status strip: homepage only -->
      <div v-show="activeTab === 'inbounds'" class="space-y-3">
        <div class="cg-rail">
          <div id="stat-card-status" class="cg-rail-cell">
            <span class="cg-rail-label">{{ t('运行状态') }}</span>
            <span class="cg-rail-value">
              <span class="cg-state-pill">
                <span
                  class="cg-live"
                  :class="state.status.state_cls === 'ok' ? 'is-ok' : state.status.state_cls === 'warn' ? 'is-warn' : 'is-bad'"
                ></span>
                <span>{{ t(state.status.state_txt || '未知') }}</span>
              </span>
              <span
                class="cg-stat-mode"
                :title="state.custom_config_mode ? t('自定义服务端') : t('默认服务端模板')"
              >{{ state.custom_config_mode ? t('自定义') : t('默认模板') }}</span>
            </span>
          </div>

          <article
            id="stat-card-pending-reload"
            role="button"
            tabindex="0"
            @click="showPendingDiff = !showPendingDiff"
            @keydown.enter.prevent="showPendingDiff = !showPendingDiff"
            class="cg-rail-cell is-action"
            :class="{ 'is-pending': state.pending_reload_count > 0 }"
            :aria-expanded="showPendingDiff ? 'true' : 'false'"
          >
            <span class="cg-rail-label">{{ t('待应用') }}</span>
            <span class="cg-rail-value">
              <span id="pending-reload-count" class="cg-pending-count">{{ state.pending_reload_count }}</span>
              <span v-if="state.pending_reload_count > 0" class="cg-rail-hint">
                {{ showPendingDiff ? t('收起') : t('有修改，点开查看') }}
              </span>
            </span>
          </article>

          <article
            id="stat-card-traffic"
            role="button"
            tabindex="0"
            @click="showTrafficDetail = !showTrafficDetail"
            @keydown.enter.prevent="showTrafficDetail = !showTrafficDetail"
            class="cg-rail-cell is-action"
            :aria-expanded="showTrafficDetail ? 'true' : 'false'"
          >
            <span class="cg-rail-label">{{ t('流量') }}</span>
            <span class="cg-rail-value">
              <bdi class="cg-rail-num" dir="ltr">{{ trafficDisplay }}</bdi>
            </span>
          </article>

          <div id="stat-card-version" class="cg-rail-cell">
            <span class="cg-rail-label">{{ t('版本') }}</span>
            <span class="cg-rail-value">
              <span class="cg-ver"><span class="cg-ver-k">{{ t('内核') }}</span><bdi dir="ltr">{{ versionLabel(state.mihomo_version) || '—' }}</bdi></span>
              <span class="cg-ver"><span class="cg-ver-k">{{ t('面板') }}</span><bdi dir="ltr">{{ versionLabel(state.version) || '—' }}</bdi></span>
              <span v-if="state.update_channel === 'test'" class="cg-chan">{{ t('测试') }}</span>
            </span>
          </div>
        </div>

        <Transition name="cg-collapse">
          <div
            v-if="showPendingDiff"
            id="pending-reload-diff-panel"
            class="rounded-2xl border px-4 py-3.5 text-xs space-y-2.5"
            :class="
              state.pending_reload_count > 0
                ? 'bg-amber-50/90 border-amber-200/90 text-amber-950'
                : 'bg-white border-slate-200/80 text-slate-600'
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
            <div v-if="state.pending_reload_items && state.pending_reload_items.length > 0" class="space-y-1">
              <div
                v-for="(it, idx) in state.pending_reload_items"
                :key="idx"
                class="px-3 py-1.5 rounded-xl bg-white/95 border border-amber-200/60 text-slate-800"
              >
                {{ formatPendingItem(it) }}
              </div>
            </div>
            <div v-else class="text-slate-500">{{ t('暂无待生效的变更') }}</div>
          </div>
        </Transition>

        <Transition name="cg-collapse">
          <div
            v-if="showTrafficDetail"
            id="traffic-detail-panel"
            class="rounded-2xl border border-slate-200/80 bg-white px-4 py-3 text-sm text-slate-700 tabular-nums"
          >
            <bdi dir="ltr">{{ trafficDetail }}</bdi>
          </div>
        </Transition>
      </div>

      <nav class="cg-mobile-nav lg:hidden" aria-label="pages">
        <button type="button" class="cg-nav" :class="{ 'is-active': activeTab === 'inbounds' }" @click="selectTab('inbounds')">
          <CgIcon name="house" :size="15" />{{ t('首页') }}
        </button>
        <button type="button" class="cg-nav" :class="{ 'is-active': activeTab === 'outbounds' }" @click="selectTab('outbounds')">
          <CgIcon name="outbound" :size="15" />{{ t('服务端出站') }}
        </button>
        <button type="button" class="cg-nav" :class="state.custom_server_enabled ? 'is-locked' : { 'is-active': activeTab === 'routing' }" @click="selectTab('routing')">
          <CgIcon :name="state.custom_server_enabled ? 'lock' : 'routing'" :size="15" />{{ t('服务端分流') }}
        </button>
        <button type="button" class="cg-nav" :class="state.custom_server_enabled ? 'is-locked' : { 'is-active': activeTab === 'cluster' }" @click="selectTab('cluster')">
          <CgIcon :name="state.custom_server_enabled ? 'lock' : 'cluster'" :size="15" />{{ t('集群') }}
        </button>
        <button type="button" class="cg-nav" :class="{ 'is-active': activeTab === 'readable' }" @click="selectTab('readable')">
          <CgIcon name="convert" :size="15" />{{ t('节点转换') }}
        </button>
        <button type="button" class="cg-nav" :class="{ 'is-active': activeTab === 'certs' }" @click="selectTab('certs')">
          <CgIcon name="shield" :size="15" />{{ t('HTTPS 证书') }}
        </button>
        <button
          type="button"
          class="cg-nav"
          :class="state.custom_server_enabled ? { 'is-active': activeTab === 'advanced' } : 'is-locked'"
          @click="selectTab('advanced')"
        >
          <CgIcon :name="state.custom_server_enabled ? 'server' : 'lock'" :size="15" />{{ t('自定义服务端') }}
        </button>
        <button type="button" class="cg-nav" :class="{ 'is-active': activeTab === 'settings' }" @click="selectTab('settings')">
          <CgIcon name="settings" :size="15" />{{ t('设置') }}
        </button>
      </nav>

      <!-- TAB 1 (HOMEPAGE): Zashboard + 客户端订阅 + 入站节点与添加节点 -->
      <Transition name="cg-tab" mode="out-in">
        <InboundsPage v-if="activeTab === 'inbounds'" key="inbounds" />

      <!-- TAB 2: 服务端出站与外部订阅 -->
        <OutboundsPage v-else-if="activeTab === 'outbounds'" key="outbounds" />

      <!-- TAB 3: 易读配置转换 (Dedicated Converter Page) -->

      <!-- TAB: 服务端分流 -->
        <RoutingPage v-else-if="activeTab === 'routing'" key="routing" />

        <!-- Cluster (集群): other ClashGate panels as hidden outbounds -->
        <ClusterPage v-else-if="activeTab === 'cluster'" key="cluster" />
        <ReadablePage v-else-if="activeTab === 'readable'" key="readable" />

      <!-- TAB 4: 自定义 mihomo 服务端配置 -->
        <AdvancedPage v-else-if="activeTab === 'advanced'" key="advanced" />

      <!-- TAB 5: HTTPS 证书管理 -->
        <CertsPage v-else-if="activeTab === 'certs'" key="certs" />

      <!-- Settings -->
        <SettingsPage v-else-if="activeTab === 'settings'" key="settings" />
      </Transition>
    </main>
    <div v-if="isXmas" class="cg-xmas-foot" aria-hidden="true"><XmasArt kind="scene" /></div>
      </div>
    </div>
  </div>
  <Teleport to="body">
    <div v-if="langOpen" class="cg-lang-menu" :style="langMenuStyle" role="listbox" :aria-label="t('语言')">
      <button
        v-for="code in LANGS"
        :key="code"
        type="button"
        role="option"
        class="cg-lang-item"
        :class="{ 'is-active': lang === code }"
        :aria-selected="lang === code ? 'true' : 'false'"
        @click="pickLang(code)"
      >
        <span dir="auto">{{ langLabel(code) }}</span>
        <CgIcon v-if="lang === code" name="check" :size="14" />
      </button>
    </div>
  </Teleport>
</template>
