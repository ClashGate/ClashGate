<script setup>
import { t, lang, setLang, LANGS, langLabel } from './i18n.js'
import CgIcon from './CgIcon.vue'
import XmasArt from './XmasArt.vue'
import { theme, setTheme } from './theme.js'
import { usePanel } from './composables/usePanel.js'

const {
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
        role="status"
        aria-live="polite"
        class="fixed top-18 inset-x-4 sm:inset-x-auto sm:end-6 z-[60] sm:max-w-md rounded-2xl px-4 py-3 shadow-[0_10px_30px_-8px_rgba(15,23,42,0.14)] border flex items-center gap-2.5 text-sm font-medium bg-white/95 backdrop-blur-md"
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
        <span class="cg-wrap leading-snug">{{ toast.msg }}</span>
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
            :disabled="busyKey === '/action/update-core'"
            @click="updateCoreDirect"
            class="cg-tool px-3 py-1.5 rounded-lg text-xs font-semibold border disabled:opacity-50 cursor-pointer inline-flex items-center gap-1.5 bg-white hover:bg-slate-50 border-slate-200 text-slate-800"
            :class="{ 'is-update': coreHasUpdate }"
            :title="coreHasUpdate ? updateHint(coreUpdate.latest) : undefined"
          >
            <CgIcon name="refresh" :size="14" />
            <span>{{ busyKey === '/action/update-core' ? t('更新内核中…') : t('更新内核') }}</span>
            <CgIcon v-if="coreHasUpdate" name="up" :size="13" />
          </button>
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
          <article
            id="stat-card-status"
            role="button"
            tabindex="0"
            @click="toggleVersionPanel"
            @keydown.enter.prevent="toggleVersionPanel"
            class="cg-rail-cell"
          >
            <span
              class="cg-live"
              :class="state.status.state_cls === 'ok' ? 'is-ok' : state.status.state_cls === 'warn' ? 'is-warn' : 'is-bad'"
            ></span>
            <span class="cg-rail-label">{{ t('运行状态') }}</span>
            <span class="cg-rail-strong">{{ t(state.status.state_txt || '未知') }}</span>
            <span class="cg-stat-mode">{{ state.custom_config_mode ? t('自定义服务端') : t('默认服务端模板') }}</span>
          </article>

          <article
            id="stat-card-pending-reload"
            role="button"
            tabindex="0"
            @click="showPendingDiff = !showPendingDiff"
            @keydown.enter.prevent="showPendingDiff = !showPendingDiff"
            class="cg-rail-cell"
            :class="{ 'is-pending': state.pending_reload_count > 0 }"
          >
            <span class="cg-rail-label">{{ t('待重载') }}</span>
            <span v-if="state.pending_reload_count > 0" class="cg-rail-hint is-inline">
              {{ showPendingDiff ? t('收起') : t('有修改，点开查看') }}
            </span>
            <span id="pending-reload-count" class="cg-rail-num">{{ state.pending_reload_count }}</span>
          </article>

          <article
            id="stat-card-traffic"
            role="button"
            tabindex="0"
            @click="showTrafficDetail = !showTrafficDetail"
            @keydown.enter.prevent="showTrafficDetail = !showTrafficDetail"
            class="cg-rail-cell"
          >
            <span class="cg-rail-label">{{ t('流量') }}</span>
            <span class="cg-rail-num" dir="ltr">{{ trafficDisplay }}</span>
          </article>
        </div>

        <Transition name="cg-collapse">
          <div
            v-if="showVersionPanel"
            id="version-panel"
            class="rounded-2xl border border-slate-200/80 bg-white px-4 py-3 text-sm text-slate-800 flex flex-wrap items-center gap-x-6 gap-y-1"
          >
            <span class="font-semibold">{{ t('Mihomo 内核') }} <bdi dir="ltr">{{ versionLabel(state.mihomo_version) || '—' }}</bdi></span>
            <span class="font-semibold">{{ t('面板') }} <bdi dir="ltr">{{ versionLabel(state.version) || '—' }}</bdi><span v-if="state.update_channel === 'test'" class="text-amber-700">{{ t('（测试）') }}</span></span>
          </div>
        </Transition>

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
        <div v-if="activeTab === 'inbounds'" key="inbounds" class="cg-home">
          <!-- 客户端订阅链接 -->
            <section
              id="sub-card"
              class="cg-home-sub cg-surface-emerald rounded-2xl p-5 sm:p-6 flex flex-col gap-3.5"
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
                    {{ t('查看配置') }}
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
                  class="cg-input px-3.5 py-2.5 rounded-xl bg-[#f5f8fd] hover:bg-emerald-50/50 border border-emerald-100 font-mono text-xs transition cursor-pointer"
                  :class="subUrlRevealed ? 'text-slate-700 break-all select-all' : 'text-slate-500 tracking-widest select-none'"
                >
                  {{ !state.sub_url ? '/etc/clashgate/client/mihomo-client.yaml' : subUrlRevealed ? state.sub_url : '••••••••••••••••••••••••••••••••' }}
                </div>
              </div>

              <div class="mt-auto pt-0.5 min-h-[28px] text-xs text-slate-500 flex items-center gap-1.5">
                <span>{{ t('本地客户端备份：') }}</span>
                <code class="px-2.5 py-1 rounded-lg bg-slate-100 text-slate-700 font-mono text-xs">/etc/clashgate/client/</code>
              </div>
            </section>

            <!-- Right: Locked-Default Add Node Form -->
            <section class="cg-home-add cg-surface rounded-2xl p-5 sm:p-6">
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
                  <!-- Stable height: every protocol's text is laid out invisibly in the same cell, so the card
                       keeps the size of the longest one in any language and width. -->
                  <div class="cg-stack mt-2">
                    <p v-for="p in PROTOCOLS" :key="'desc-' + p.value" class="cg-stack-ghost text-xs font-medium flex items-center gap-1.5" aria-hidden="true">
                      <span class="inline-block w-1.5 h-1.5 shrink-0"></span>
                      <span>{{ p.label }}：{{ t(p.desc) }}</span>
                    </p>
                    <p id="protocol-desc" class="text-xs font-medium text-emerald-700 flex items-center gap-1.5">
                      <span class="inline-block w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0"></span>
                      <span>{{ currentProtocol.label }}：{{ t(currentProtocol.desc) }}</span>
                    </p>
                  </div>
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

                <!-- Protocol options + locked note, stacked over invisible copies for every protocol (stable height). -->
                <div class="cg-stack">
                  <div v-for="p in PROTOCOLS" :key="'opt-' + p.value" class="cg-stack-ghost space-y-4" aria-hidden="true">
                    <div v-if="PROTOCOL_HAS_OPTION.has(p.value)">
                      <div class="block text-xs font-semibold mb-1.5">&nbsp;</div>
                      <div class="h-10 border border-transparent"></div>
                    </div>
                    <div class="rounded-xl border px-3.5 py-2.5 text-xs leading-relaxed">{{ t(p.lockedNote) }}</div>
                  </div>
                  <div class="space-y-4">
                    <div v-if="sniEditable">
                      <label for="sni" class="block text-xs font-semibold text-slate-700 mb-1.5">SNI</label>
                      <input
                        id="sni"
                        v-model="inboundForm.sni"
                        name="sni"
                        autocomplete="off"
                        spellcheck="false"
                        :placeholder="t('留空从内置域名池随机抽取')"
                        class="cg-input w-full h-10 px-3 rounded-xl border border-slate-200 bg-white text-sm text-slate-900"
                      />
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
                    <div class="rounded-xl bg-[#f1f6fe] border border-emerald-200/70 px-3.5 py-2.5 text-xs text-emerald-900 leading-relaxed">
                      {{ t(currentProtocol.lockedNote) }}
                    </div>
                  </div>
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

          <!-- 入站节点 -->
            <section class="cg-home-in cg-surface rounded-2xl p-5 sm:p-6">
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
                class="cg-empty py-6 px-4 rounded-2xl border border-dashed border-slate-200 bg-slate-50/40 text-center text-sm text-slate-500"
              >
                {{ t('暂无入站节点，请在上方添加节点') }}
              </div>

              <div v-else class="divide-y divide-slate-100 border border-slate-200/80 rounded-2xl overflow-hidden">
                <div
                  v-for="item in state.inbounds"
                  :key="item.key"
                  class="p-4 hover:bg-emerald-50/35 transition flex flex-wrap items-center justify-between gap-3"
                >
                  <div class="space-y-1 min-w-0 flex-[1_1_12rem]">
                    <div class="flex items-center gap-2 flex-wrap">
                      <span class="font-bold text-sm text-slate-900 cg-wrap">{{ item.name }}</span>
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
                        {{ item.listening ? t('运行中') : item.pending_reload ? t('待重载') : t('未运行') }}
                      </span>
                    </div>
                    <div class="text-xs text-slate-500 tabular-nums">{{ t('端口') }} <bdi dir="ltr" class="font-mono">{{ item.port }}</bdi></div>
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
                      {{ busyKey === `del-${item.key}` ? t('删除中…') : t('删除') }}
                    </button>
                  </div>
                </div>
              </div>
            </section>
        </div>

      <!-- TAB 2: 服务端出站与外部订阅 -->
        <div v-else-if="activeTab === 'outbounds'" key="outbounds" class="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
          <div class="space-y-4 min-w-0">
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
                  {{ t('端口') }} <bdi dir="ltr">{{ state.controller_port }}</bdi> {{ state.controller_listening ? t('运行中') : t('未运行') }}
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
                  {{ t('查看 Mihomo 服务端配置') }}
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
                class="cg-input px-3.5 py-2.5 rounded-xl bg-[#f5f8fd] hover:bg-emerald-50/50 border border-emerald-100 font-mono text-xs transition cursor-pointer"
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
          <!-- 服务端手工出站节点 (proxies) -->
          <section class="cg-surface rounded-2xl p-5 sm:p-6 space-y-4">
            <div class="flex items-center gap-2.5">
              <h2 class="text-base font-bold text-slate-900 tracking-tight">{{ t('服务端出站 (proxies)') }}</h2>
              <span
                class="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200/60 tabular-nums"
              >
                {{ state.proxies.length }}
              </span>
            </div>

            <div
              v-if="state.proxies.length === 0"
              class="cg-empty py-6 px-4 rounded-2xl border border-dashed border-slate-200 bg-slate-50/40 text-center text-xs text-slate-500"
            >
              {{ t('暂无手工服务端出站，在下方粘贴单行 JSON 或多行 YAML 即可添加') }}
            </div>

            <div
              v-else
              class="divide-y divide-slate-100 border border-slate-200/80 rounded-2xl overflow-hidden"
            >
              <div
                v-for="p in state.proxies"
                :key="p.name"
                class="p-4 flex flex-wrap items-center justify-between gap-3 hover:bg-emerald-50/25 transition"
              >
                <div class="space-y-1 min-w-0 flex-[1_1_12rem]">
                  <div class="flex items-center gap-2 flex-wrap">
                    <span class="font-bold text-sm text-slate-900 cg-wrap">{{ p.name }}</span>
                    <span
                      class="px-2 py-0.5 text-[11px] font-semibold rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200/60"
                    >
                      {{ p.type }}
                    </span>
                  </div>
                  <div class="text-xs text-slate-500 font-mono tabular-nums cg-wrap" dir="ltr">{{ p.endpoint }}</div>
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
                    {{ busyKey === `del-proxy-${p.name}` ? t('删除中…') : t('删除') }}
                  </button>
                </div>
              </div>
            </div>

            <form @submit.prevent="submitAddProxies" class="space-y-3">
              <textarea
                v-model="proxiesRaw"
                name="proxies_raw"
                rows="5"
                :placeholder="t('粘贴单行 JSON / Flow 或多行 YAML 格式的 Mihomo 节点配置（含 easytier、tailscale 等）…')"
                class="cg-input w-full p-3.5 rounded-xl border border-slate-200 bg-[#f7f9fc] font-mono text-xs text-slate-900 focus:bg-white"
              ></textarea>
              <div class="flex items-center gap-2.5 flex-wrap">
                <button
                  type="submit"
                  :disabled="busyKey === 'add-proxies'"
                  class="cg-btn-primary px-4 py-2 rounded-xl disabled:opacity-50 text-xs font-semibold cursor-pointer"
                >
                  {{ busyKey === 'add-proxies' ? t('添加中…') : t('添加服务端出站') }}
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
          <div class="space-y-4 min-w-0">
          <!-- Cloudflare MASQUE preset -->
          <section class="cg-surface cg-feature rounded-2xl p-5 sm:p-6">
            <div class="flex flex-wrap items-center justify-between gap-4">
              <div class="flex items-start gap-2.5 min-w-0 flex-[1_1_14rem]">
                <span class="mt-0.5 inline-flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-slate-700 shrink-0">
                  <CgIcon name="cloud" :size="16" />
                </span>
                <div class="min-w-0">
                  <div class="flex items-center gap-2 flex-wrap">
                    <h2 class="text-base font-bold text-slate-900 tracking-tight">{{ t('Cloudflare MASQUE') }}</h2>
                    <span
                      v-if="state.masque.status === 'pending' || state.masque.status === 'error'"
                      class="px-2.5 py-0.5 text-xs font-semibold rounded-full border"
                      :class="
                        state.masque.status === 'error'
                          ? 'bg-rose-50 text-rose-700 border-rose-200/80'
                          : 'bg-slate-50 text-slate-600 border-slate-200'
                      "
                    >
                      {{ state.masque.status === 'error' ? t('注册失败') : t('后台注册中') }}
                    </span>
                  </div>
                  <p class="text-xs text-slate-500 mt-1 leading-relaxed">
                    {{ t('通过 Cloudflare 注册 MASQUE 节点。') }}
                  </p>
                  <div v-if="state.masque.status === 'ok'" class="mt-2.5 font-mono text-xs text-slate-600 break-all">
                    {{ masqueNodeName(state.masque.name) }} · {{ state.masque.endpoint }}
                  </div>
                </div>
              </div>
              <button
                v-if="state.masque.status === 'ok'"
                type="button"
                :disabled="busyKey === 'add-masque'"
                @click="addMasqueOutbound"
                class="cg-btn-primary px-3.5 py-1.5 rounded-lg text-xs font-semibold disabled:opacity-50 cursor-pointer shrink-0"
              >
                {{ busyKey === 'add-masque' ? t('添加中…') : t('加入服务端出站') }}
              </button>
              <button
                v-else
                type="button"
                :disabled="state.masque.status === 'pending' || busyKey === '/action/masque-register'"
                @click="retryMasque"
                class="cg-btn-primary px-3.5 py-1.5 rounded-lg text-xs font-semibold disabled:opacity-50 cursor-pointer shrink-0"
              >
                {{
                  state.masque.status === 'pending' || busyKey === '/action/masque-register'
                    ? t('注册中…')
                    : state.masque.status === 'error'
                      ? t('重新注册')
                      : t('注册 MASQUE')
                }}
              </button>
            </div>
            <div v-if="state.masque.status === 'error'" class="mt-3">
              <p class="text-xs text-rose-700 leading-relaxed break-all">{{ state.masque.error || t('注册失败') }}</p>
            </div>
            <p v-else-if="state.masque.status === 'pending'" class="text-xs text-slate-500 mt-3">{{ t('正在向 Cloudflare 注册，完成后这里会出现「加入服务端出站」。') }}</p>
          </section>
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
              class="cg-empty py-6 px-4 rounded-2xl border border-dashed border-slate-200 bg-slate-50/40 text-center text-xs text-slate-500"
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
                class="p-4 flex flex-wrap items-center justify-between gap-3 hover:bg-emerald-50/25 transition"
              >
                <div class="min-w-0 space-y-1 flex-[1_1_12rem]">
                  <div class="flex items-center gap-2 flex-wrap">
                    <span class="font-bold text-sm text-slate-900 cg-wrap">{{ prov.name }}</span>
                    <span dir="ltr" class="text-xs font-mono text-slate-500 bg-slate-100 px-2 py-0.5 rounded-md">{{ prov.path }}</span>
                  </div>
                  <div dir="ltr" class="text-xs text-slate-400 font-mono truncate text-start">{{ prov.url }}</div>
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
                    {{ busyKey === `del-prov-${prov.name}` ? t('删除中…') : t('删除') }}
                  </button>
                </div>
              </div>
            </div>

            <form @submit.prevent="submitAddProvider" class="flex flex-wrap gap-3 items-end">
              <div class="flex-[3_1_16rem] min-w-0">
                <label class="block text-xs font-semibold text-slate-700 mb-1.5">{{ t('订阅链接 (HTTP / HTTPS)') }}</label>
                <input
                  v-model="providerForm.sub_url"
                  name="sub_url"
                  placeholder="https://example.com/sub.yaml?token=..."
                  dir="ltr"
                  class="cg-input w-full h-10 px-3 rounded-xl border border-slate-200 bg-white text-sm text-slate-900"
                />
              </div>
              <div class="flex-[1_1_9rem] min-w-0">
                <label class="block text-xs font-semibold text-slate-700 mb-1.5">{{ t('名称 (选填)') }}</label>
                <input
                  v-model="providerForm.provider_name"
                  name="provider_name"
                  :placeholder="t('默认 sub')"
                  class="cg-input w-full h-10 px-3 rounded-xl border border-slate-200 bg-white text-sm text-slate-900"
                />
              </div>
              <div class="flex-[1_0_auto]">
                <button
                  type="submit"
                  :disabled="busyKey === 'add-provider'"
                  class="cg-btn-primary w-full h-10 px-4 rounded-xl disabled:opacity-50 text-xs font-semibold cursor-pointer whitespace-nowrap"
                >
                  {{ busyKey === 'add-provider' ? t('导入中…') : t('导入订阅') }}
                </button>
              </div>
            </form>
          </section>
          </div>
        </div>

      <!-- TAB 3: 易读配置转换 (Dedicated Converter Page) -->

      <!-- TAB: 服务端分流 -->
        <div v-else-if="activeTab === 'routing'" key="routing" class="space-y-4">
          <div v-if="state.custom_server_enabled" class="rounded-xl bg-amber-50 border border-amber-200 px-4 py-3 text-sm font-semibold text-amber-800">
            {{ t('已启用自定义服务端配置，请自行修改相关配置') }}
          </div>
          <div class="space-y-4" :class="state.custom_server_enabled ? 'opacity-50 pointer-events-none select-none' : ''" :inert="state.custom_server_enabled || undefined" :aria-disabled="state.custom_server_enabled ? 'true' : undefined">
            <p v-if="state.routing && state.routing.error" class="text-sm text-rose-600 bg-rose-50 border border-rose-200 rounded-xl px-3 py-2">
              {{ state.routing.error || t('自定义模式下分流解析失败') }}
            </p>

          <section class="cg-surface rounded-2xl p-5 sm:p-6 space-y-4">
            <div class="flex items-start justify-between gap-3 flex-wrap">
              <div>
                <h3 class="text-sm font-bold text-slate-900">{{ t('分流组') }}</h3>
                <p class="text-xs text-slate-500 mt-1">{{ t('拖动调整顺序（与主配置一致），点顶部「重载配置」后生效。') }}</p>
              </div>
            </div>
            <div
              v-if="routingGroups.length === 0"
              class="cg-empty rounded-xl border border-dashed border-slate-200 bg-slate-50/80 px-4 py-10 text-center space-y-2"
            >
              <div class="text-sm font-semibold text-slate-700">{{ t('暂无分流组') }}</div>
              <p class="text-xs text-slate-500 max-w-md mx-auto leading-relaxed">{{ t('还没有自定义分流。用下方「引入外部分流」挂规则集，或「新建分流组」粘贴本地规则。') }}</p>
            </div>
            <div v-else class="space-y-2">
              <div
                v-for="(g, idx) in routingGroups"
                :key="g.id"
                draggable="true"
                class="rounded-xl border bg-white px-3.5 py-3 cursor-move select-none transition hover:border-slate-300 hover:shadow-sm"
                :class="[routingDragOver === idx ? 'border-sky-400 ring-2 ring-sky-100' : 'border-slate-200', routingDragIdx === idx ? 'opacity-50' : '']"
                @dragstart="onRoutingDragStart(idx, $event)"
                @dragover.prevent="routingDragOver = idx"
                @dragleave="routingDragOver === idx && (routingDragOver = -1)"
                @drop.prevent="onRoutingDrop(idx)"
                @dragend="routingDragIdx = -1; routingDragOver = -1"
              >
                <div class="flex items-center gap-2 flex-wrap">
                  <span class="text-slate-400 text-lg leading-none" aria-hidden="true">⋮⋮</span>
                  <span class="text-xs text-slate-400 tabular-nums w-5">{{ idx + 1 }}</span>
                  <div class="min-w-0 flex-1">
                    <div class="flex items-center gap-2 min-w-0">
                      <div class="font-semibold text-slate-900 truncate">{{ g.name }}</div>
                      <span
                        class="shrink-0 px-1.5 py-0.5 rounded-md text-[10px] font-semibold border"
                        :class="isLocalRoutingGroup(g) ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-violet-50 text-violet-700 border-violet-200'"
                      >{{ isLocalRoutingGroup(g) ? t('本地规则') : t('外部分流') }}</span>
                    </div>
                    <div class="text-[11px] text-slate-500 mt-0.5">
                      <template v-if="isLocalRoutingGroup(g)">{{ t('{n} 条规则', { n: (g.classical_rules || []).length }) }}</template>
                      <template v-else>{{ t('{n} 个规则集', { n: (g.rule_providers || []).length }) }}</template>
                    </div>
                    <div v-if="g.error" class="text-xs text-rose-600 mt-1">{{ g.error }}</div>
                  </div>
                  <div class="flex items-center gap-1.5 flex-wrap">
                    <button
                      v-if="!state.custom_config_mode"
                      type="button"
                      class="px-2 py-1 rounded-lg text-xs bg-sky-50 hover:bg-sky-100 text-sky-800 border border-sky-200"
                      @click.stop="toggleRoutingPanel(g)"
                    >{{ isLocalRoutingGroup(g) ? t('编辑规则') : t('规则集') }}</button>
                    <button type="button" class="px-2 py-1 rounded-lg text-xs bg-slate-100 hover:bg-slate-200 text-slate-700" @click.stop="renameRouting(g)">{{ t('重命名') }}</button>
                    <button
                      v-if="g.deletable"
                      type="button"
                      class="px-2 py-1 rounded-lg text-xs bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200"
                      :disabled="busyKey === `routing-del-${g.id}`"
                      @click.stop="confirmDeleteRouting(g)"
                    >{{ busyKey === `routing-del-${g.id}` ? t('删除中…') : t('删除') }}</button>
                  </div>
                </div>

                <div
                  v-if="routingPanelOpen === g.id && isLocalRoutingGroup(g)"
                  class="mt-3 space-y-2 border-t border-slate-100 pt-3"
                  draggable="true"
                  @dragstart.stop.prevent
                >
                  <p class="text-xs text-slate-500">{{ t('每行一条经典规则，例如 - DOMAIN-SUFFIX,example.com。保存后写入本地规则文件，由主配置引入。') }}</p>
                  <textarea
                    v-model="routingRuleDraft[g.id]"
                    rows="6"
                    class="cg-input w-full px-3 py-2 rounded-xl border border-slate-200 text-xs font-mono"
                    :placeholder="'- DOMAIN-SUFFIX,example.com\n- DOMAIN-KEYWORD,openai'"
                  ></textarea>
                  <div class="flex justify-end">
                    <button
                      type="button"
                      class="cg-btn-primary h-9 px-3 rounded-xl text-xs font-semibold"
                      :disabled="busyKey === `routing-rules-${g.id}`"
                      @click="saveLocalRoutingRules(g)"
                    >{{ busyKey === `routing-rules-${g.id}` ? t('保存中…') : t('保存规则') }}</button>
                  </div>
                </div>

                <div
                  v-else-if="routingPanelOpen === g.id"
                  class="mt-3 space-y-2 border-t border-slate-100 pt-3"
                  draggable="true"
                  @dragstart.stop.prevent
                >
                  <div v-if="!(g.rule_providers || []).length" class="text-xs text-slate-500">{{ t('暂无规则集') }}</div>
                  <div v-for="p in (g.rule_providers || [])" :key="p.name" class="flex items-center gap-2 text-xs">
                    <span class="font-semibold text-slate-800 shrink-0">{{ p.name }}</span>
                    <span dir="ltr" class="text-slate-500 truncate flex-1 min-w-0 text-start">{{ p.url }}</span>
                    <button type="button" class="px-2 py-0.5 rounded-lg bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 disabled:opacity-50 shrink-0" :disabled="busyKey === `routing-prov-del-${p.name}`" @click="deleteRoutingProvider(g, p)">{{ busyKey === `routing-prov-del-${p.name}` ? t('删除中…') : t('删除') }}</button>
                  </div>
                  <p class="text-xs text-slate-500">{{ t('可再为此分流组追加一个规则集（名称 + URL）。新建整组请用下方「引入外部分流」。') }}</p>
                  <div class="grid grid-cols-1 sm:grid-cols-4 gap-2">
                    <input v-model="routingProvForm.provider" :placeholder="t('规则集名称（英文）')" class="cg-input h-9 px-3 rounded-xl border border-slate-200 text-xs" />
                    <input v-model="routingProvForm.url" dir="ltr" placeholder="https://" class="cg-input sm:col-span-2 h-9 px-3 rounded-xl border border-slate-200 text-xs font-mono" />
                    <button type="button" class="cg-btn-primary h-9 px-3 rounded-xl text-xs font-semibold" :disabled="busyKey === 'routing-prov-add'" @click="addRoutingProvider(g)">{{ busyKey === 'routing-prov-add' ? t('添加中…') : t('添加规则集') }}</button>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <div
            class="grid grid-cols-1 md:grid-cols-2 gap-4"
            v-if="!(state.routing && state.routing.error && state.custom_config_mode)"
          >
            <section class="cg-surface rounded-2xl p-5 sm:p-6 space-y-3 h-full flex flex-col">
              <div>
                <div class="flex items-center gap-2">
                  <span class="inline-flex h-6 w-6 items-center justify-center rounded-lg bg-violet-50 text-violet-700 text-[11px] font-bold border border-violet-200/70">URL</span>
                  <h3 class="text-sm font-bold text-slate-900">{{ t('引入外部分流') }}</h3>
                </div>
                <p class="text-xs text-slate-500 mt-1.5 leading-relaxed">{{ t('只填名称和规则集 URL。会写入 rule-providers、proxy-groups，并在 rules 里加 RULE-SET（不下载远程内容）。') }}</p>
              </div>
              <label class="block text-xs font-medium text-slate-500">{{ t('分流组名称') }}
                <input v-model="importRoutingForm.name" class="cg-input mt-1 w-full h-10 px-3 rounded-xl border border-slate-200 text-sm" :placeholder="t('例如 AI')" />
              </label>
              <label class="block text-xs font-medium text-slate-500">{{ t('规则集 URL') }}
                <input v-model="importRoutingForm.url" dir="ltr" class="cg-input mt-1 w-full h-10 px-3 rounded-xl border border-slate-200 text-sm font-mono" placeholder="https://" />
              </label>
              <div class="mt-auto pt-1">
                <button
                  type="button"
                  class="cg-btn-primary w-full sm:w-auto px-3.5 py-2 rounded-xl text-xs font-semibold"
                  :disabled="busyKey === 'routing-import'"
                  @click="importRoutingGroup"
                >
                  {{ busyKey === 'routing-import' ? t('引入中…') : t('引入外部分流') }}
                </button>
              </div>
            </section>

            <section class="cg-surface rounded-2xl p-5 sm:p-6 space-y-3 h-full flex flex-col">
              <div>
                <div class="flex items-center gap-2">
                  <span class="inline-flex h-6 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700 text-[10px] font-bold border border-emerald-200/70 px-1.5">{{ t('本地') }}</span>
                  <h3 class="text-sm font-bold text-slate-900">{{ t('新建分流组') }}</h3>
                </div>
                <p class="text-xs text-slate-500 mt-1.5 leading-relaxed">{{ t('粘贴 DOMAIN-SUFFIX / DOMAIN-KEYWORD / IP-CIDR 等经典规则，保存为本地规则文件并由主配置引入。') }}</p>
              </div>
              <label class="block text-xs font-medium text-slate-500">{{ t('分流组名称') }}
                <input v-model="createRoutingForm.name" class="cg-input mt-1 w-full h-10 px-3 rounded-xl border border-slate-200 text-sm" :placeholder="t('例如 MyRules')" />
              </label>
              <label class="block text-xs font-medium text-slate-500 flex-1">{{ t('规则（每行一条）') }}
                <textarea
                  v-model="createRoutingForm.rules_raw"
                  rows="5"
                  class="cg-input mt-1 w-full px-3 py-2 rounded-xl border border-slate-200 text-xs font-mono min-h-[7.5rem]"
                  :placeholder="'- DOMAIN-SUFFIX,example.com\n- DOMAIN-KEYWORD,openai\n- IP-CIDR,1.1.1.1/32'"
                ></textarea>
              </label>
              <div class="pt-1">
                <button
                  type="button"
                  class="cg-btn-primary w-full sm:w-auto px-3.5 py-2 rounded-xl text-xs font-semibold"
                  :disabled="busyKey === 'routing-add'"
                  @click="createRoutingGroup"
                >
                  {{ busyKey === 'routing-add' ? t('创建中…') : t('新建分流组') }}
                </button>
              </div>
            </section>
          </div>
          </div>
        </div>

        <!-- Cluster (集群): other ClashGate panels as hidden outbounds -->
        <div v-else-if="activeTab === 'cluster'" key="cluster" class="space-y-4">
          <div v-if="state.custom_server_enabled" class="rounded-xl bg-amber-50 border border-amber-200 px-4 py-3 text-sm font-semibold text-amber-800">
            {{ t('已启用自定义服务端配置，请自行修改相关配置') }}
          </div>
          <div
            class="space-y-4"
            :class="state.custom_server_enabled ? 'opacity-50 pointer-events-none select-none' : ''"
            :inert="state.custom_server_enabled || undefined"
            :aria-disabled="state.custom_server_enabled ? 'true' : undefined"
          >
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
              <div class="space-y-4 min-w-0">
                <section class="cg-surface rounded-2xl p-5 sm:p-6 space-y-4" data-cg-card="node-name">
                  <div>
                    <h2 class="text-base font-bold text-slate-900 tracking-tight">{{ t('本机名称') }}</h2>
                    <p class="text-xs text-slate-500 mt-1 leading-relaxed">{{ t('其他面板添加本机后，会用这个名字显示本机。') }}</p>
                  </div>
                  <form @submit.prevent="saveNodeName" novalidate>
                    <div class="flex items-stretch gap-2" data-cg-row="node-name">
                      <div class="relative flex-1 min-w-0">
                        <input
                          id="node-name"
                          v-model="nodeNameInput"
                          name="node_name"
                          dir="auto"
                          autocomplete="off"
                          spellcheck="false"
                          :aria-label="t('本机名称')"
                          :aria-invalid="nodeNameOverLimit ? 'true' : undefined"
                          :aria-describedby="nodeNameHint ? 'node-name-help' : undefined"
                          class="cg-input w-full h-10 ps-3 pe-16 rounded-xl border bg-white text-sm text-slate-900"
                          :class="nodeNameOverLimit ? 'border-rose-300' : 'border-slate-200'"
                        />
                        <span
                          class="pointer-events-none absolute inset-y-0 end-3 flex items-center text-xs tabular-nums"
                          :class="nodeNameOverLimit ? 'text-rose-500' : 'text-slate-400'"
                          dir="ltr"
                          aria-hidden="true"
                        >{{ nodeNameLength }}/{{ CG_NODE_NAME_MAX }}</span>
                      </div>
                      <button
                        type="submit"
                        :disabled="!!busyKey || nodeNameOverLimit || (state.cluster.node_name_set && nodeNameInput.trim() === state.cluster.node_name)"
                        class="cg-btn-primary h-10 min-w-[5.5rem] px-5 rounded-xl disabled:opacity-50 text-sm font-semibold cursor-pointer shrink-0"
                      >{{ busyKey === 'save-node-name' ? t('保存中…') : t('保存') }}</button>
                    </div>
                    <!-- Hint is omitted until the input is over the 15-character limit, so the card stays tight. -->
                    <div
                      v-if="nodeNameHint"
                      id="node-name-help"
                      class="mt-2 text-xs leading-5 text-rose-600"
                      role="alert"
                      aria-live="polite"
                    >{{ nodeNameHint }}</div>
                  </form>
                </section>

                <section class="cg-surface rounded-2xl p-5 sm:p-6 space-y-4" data-cg-card="cluster-add">
                  <div>
                    <h2 class="text-base font-bold text-slate-900 tracking-tight">{{ t('添加面板到集群') }}</h2>
                    <p class="text-xs text-slate-500 mt-1 leading-relaxed">
                      {{ t('填写另一台 VPS 上 ClashGate 面板的地址和密码。两边会互相生成 VLESS 后量子加密节点，并写入各自的服务端出站，名称就是对方的本机名称。') }}
                    </p>
                  </div>
                  <form @submit.prevent="submitAddCluster" class="space-y-3" novalidate>
                    <div>
                      <label for="cl-url" class="block text-xs font-semibold text-slate-700 mb-1.5">{{ t('对方面板地址') }}</label>
                      <input
                        id="cl-url"
                        v-model="clusterForm.url"
                        name="url"
                        dir="ltr"
                        autocomplete="off"
                        spellcheck="false"
                        placeholder="https://example.com:8443"
                        @blur="clusterTouched.url = true"
                        :aria-invalid="clusterTouched.url && clusterUrlErr ? 'true' : undefined"
                        class="cg-input w-full h-10 px-3 rounded-xl border bg-white text-sm text-slate-900"
                        :class="clusterTouched.url && clusterUrlErr ? 'border-rose-300' : 'border-slate-200'"
                      />
                      <p v-if="clusterTouched.url && clusterUrlErr" class="text-xs text-rose-600 mt-1">{{ clusterUrlErr }}</p>
                    </div>
                    <div>
                      <label for="cl-pw" class="block text-xs font-semibold text-slate-700 mb-1.5">{{ t('对方面板密码') }}</label>
                      <input
                        id="cl-pw"
                        v-model="clusterForm.password"
                        name="password"
                        type="password"
                        autocomplete="new-password"
                        @blur="clusterTouched.password = true"
                        :aria-invalid="clusterTouched.password && clusterPwErr ? 'true' : undefined"
                        class="cg-input w-full h-10 px-3 rounded-xl border bg-white text-sm text-slate-900"
                        :class="clusterTouched.password && clusterPwErr ? 'border-rose-300' : 'border-slate-200'"
                      />
                      <p v-if="clusterTouched.password && clusterPwErr" class="text-xs text-rose-600 mt-1">{{ clusterPwErr }}</p>
                      <p v-else class="text-xs text-slate-500 mt-1">{{ t('密码只用这一次，不会保存在任何一台面板上。') }}</p>
                    </div>
                    <button
                      type="submit"
                      :disabled="!!busyKey || !state.cluster.self_url"
                      class="cg-btn-primary h-10 px-5 rounded-xl disabled:opacity-50 text-sm font-semibold cursor-pointer"
                    >{{ busyKey === 'cluster-add' ? t('正在和对方面板互联…') : t('添加到集群') }}</button>
                  </form>
                  <div class="rounded-xl border border-slate-200/80 bg-slate-50/60 px-3.5 py-3 space-y-1">
                    <div class="text-xs font-semibold text-slate-700">{{ t('本机面板地址') }}</div>
                    <div v-if="state.cluster.self_url" class="text-xs text-slate-600 font-mono cg-wrap" dir="ltr">{{ state.cluster.self_url }}</div>
                    <div v-else class="text-xs text-amber-700">{{ t('本机没有可用的面板地址（域名或服务器 IP），其他面板无法连回本机') }}</div>
                    <p class="text-xs text-slate-500 leading-relaxed">{{ t('对方会通过这个地址连回本机，并校验 HTTPS 证书。') }}</p>
                  </div>
                  <ul class="text-xs text-slate-500 leading-relaxed space-y-1 list-disc ps-4">
                    <li>{{ t('已经在集群里的面板会自动和新面板互联，不需要再输入密码。') }}</li>
                    <li>{{ t('对方面板需要 ClashGate 1.14 或更高版本，并使用有效的 HTTPS 证书。') }}</li>
                    <li>{{ t('添加后立即生效，不需要点「重载配置」。') }}</li>
                    <li>{{ t('这些出站不会出现在节点列表和客户端订阅里，可以在 Zashboard 的分流策略组里选择它们作为出口。') }}</li>
                  </ul>
                </section>
              </div>

              <div class="space-y-4 min-w-0">
                <section class="cg-surface rounded-2xl p-5 sm:p-6 space-y-4" data-cg-card="cluster-members">
                  <div class="flex items-start justify-between gap-3">
                    <div class="min-w-0">
                      <div class="flex items-center gap-2.5" data-cg-title-row>
                        <h2 class="text-base font-bold text-slate-900 tracking-tight">{{ t('集群成员') }}</h2>
                        <span class="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-sky-50 text-sky-700 border border-sky-200/70 tabular-nums">{{ state.cluster.members.length }}</span>
                      </div>
                      <p class="text-xs text-slate-500 mt-1 leading-relaxed">{{ t('集群里每两台面板之间都有一条双向的 VLESS 后量子加密连接。') }}</p>
                    </div>
                    <button
                      v-if="state.cluster.members.length || state.cluster.pending.length"
                      type="button"
                      :disabled="!!busyKey"
                      @click="syncCluster"
                      class="-my-1 h-8 px-3 rounded-xl text-xs font-semibold bg-white hover:bg-sky-50 text-slate-700 border border-slate-200/90 disabled:opacity-50 transition cursor-pointer shrink-0"
                    >{{ busyKey === 'cluster-sync' ? t('检查中…') : t('检查') }}</button>
                  </div>
                  <div
                    v-if="state.cluster.members.length === 0 && state.cluster.pending.length === 0"
                    class="cg-empty py-6 px-4 rounded-2xl border border-dashed border-slate-200 bg-slate-50/40 text-center text-xs text-slate-500"
                  >{{ t('本机还没有加入集群') }}</div>
                  <div v-else class="divide-y divide-slate-100 border border-slate-200/80 rounded-2xl overflow-hidden">
                    <div v-for="m in state.cluster.members" :key="m.id" class="p-4 flex items-center justify-between gap-3">
                      <div class="space-y-1 min-w-0 flex-1">
                        <div class="flex items-center gap-2 flex-wrap">
                          <span class="font-bold text-sm text-slate-900 cg-wrap" dir="auto">{{ m.name }}</span>
                          <span
                            v-if="m.ok === false"
                            class="px-2 py-0.5 text-[11px] font-semibold rounded-md bg-amber-50 text-amber-800 border border-amber-200/80"
                          >{{ t('联系不上') }}</span>
                          <span
                            v-else-if="m.missing && m.missing.length"
                            class="px-2 py-0.5 text-[11px] font-semibold rounded-md bg-amber-50 text-amber-800 border border-amber-200/80"
                          >{{ t('互联不完整') }}</span>
                          <span v-else class="px-2 py-0.5 text-[11px] font-semibold rounded-md bg-sky-50 text-sky-700 border border-sky-200/70">{{ t('双向互联') }}</span>
                        </div>
                        <div class="text-xs text-slate-500 font-mono cg-wrap" dir="ltr">{{ m.url }}</div>
                        <p v-if="m.ok === false && m.error" class="text-xs text-amber-700 cg-wrap">{{ m.error }}</p>
                        <p v-else-if="m.missing && m.missing.length" class="text-xs text-amber-700 cg-wrap">
                          {{ t('还没和「{names}」互联，点「检查」重试', { names: m.missing.join(listSep) }) }}
                        </p>
                      </div>
                      <button
                        type="button"
                        :disabled="!!busyKey"
                        @click="removeClusterMember(m)"
                        class="h-8 px-3 rounded-xl text-xs font-medium text-rose-600 hover:bg-rose-50 border border-rose-200/80 disabled:opacity-50 transition cursor-pointer shrink-0"
                      >{{ busyKey === `cl-rm-${m.id}` ? t('移除中…') : t('移除') }}</button>
                    </div>
                    <div v-for="p in state.cluster.pending" :key="'p-' + p.url + p.name" class="p-4 space-y-1">
                      <div class="flex items-center gap-2 flex-wrap">
                        <span class="font-bold text-sm text-slate-900 cg-wrap" dir="auto">{{ p.name }}</span>
                        <span class="px-2 py-0.5 text-[11px] font-semibold rounded-md bg-slate-100 text-slate-700 border border-slate-200">{{ t('等待互联') }}</span>
                      </div>
                      <div class="text-xs text-slate-500 font-mono cg-wrap" dir="ltr">{{ p.url }}</div>
                      <p v-if="p.error" class="text-xs text-amber-700 cg-wrap">{{ p.error }}</p>
                    </div>
                  </div>
                  <div v-if="state.cluster.members.length" class="flex justify-end">
                    <button
                      type="button"
                      :disabled="!!busyKey"
                      @click="leaveCluster"
                      class="h-8 px-3 rounded-xl text-xs font-medium text-rose-600 hover:bg-rose-50 border border-rose-200/80 disabled:opacity-50 transition cursor-pointer"
                    >{{ busyKey === 'cluster-leave' ? t('正在退出…') : t('退出集群') }}</button>
                  </div>
                </section>
              </div>
            </div>
          </div>
        </div>
        <div v-else-if="activeTab === 'readable'" key="readable" class="space-y-6">
          <section class="cg-surface rounded-2xl p-5 sm:p-6 space-y-5">
            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <div class="flex items-center gap-2.5">
                  <h2 class="text-base font-bold text-slate-900 tracking-tight">{{ t('节点转换') }}</h2>
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
                <div class="flex flex-wrap items-center justify-between gap-2">
                  <label class="text-xs font-semibold text-slate-700">{{ t('输入节点配置（单行 JSON / 多行 YAML）') }}</label>
                  <div class="flex items-center gap-2 flex-wrap">
                    <button
                      type="button"
                      :disabled="busyKey.startsWith('convert-')"
                      @click="convertConfigFormat('readable')"
                      class="cg-btn-primary px-3 py-1 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50"
                    >
                      {{ t('转换为易读配置') }}
                    </button>
                    <button
                      type="button"
                      :disabled="busyKey.startsWith('convert-')"
                      @click="convertConfigFormat('single')"
                      class="px-3 py-1 rounded-lg text-xs font-medium bg-slate-100 hover:bg-slate-200 text-slate-700 transition cursor-pointer disabled:opacity-50"
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
                  class="cg-input w-full p-3.5 rounded-xl border border-slate-200 bg-[#f7f9fc] font-mono text-xs text-slate-900 leading-relaxed focus:bg-white"
                ></textarea>
              </div>

              <div class="space-y-2">
                <div class="flex items-center justify-between">
                  <label class="text-xs font-semibold text-slate-700">{{ t('转换结果') }}</label>
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
                  class="w-full p-3.5 rounded-xl border border-slate-200 bg-[#f7f9fc] font-mono text-xs text-slate-800 leading-relaxed focus:outline-none"
                ></textarea>
              </div>
            </div>
          </section>
        </div>

      <!-- TAB 4: 自定义 mihomo 服务端配置 -->
        <div v-else-if="activeTab === 'advanced'" key="advanced" class="space-y-6">
          <section class="cg-surface rounded-2xl p-5 sm:p-6 space-y-5">
            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div class="space-y-1">
                <div class="flex items-center gap-2.5 flex-wrap">
                  <h2 class="text-base font-bold text-slate-900 tracking-tight">{{ t('自定义服务端') }}</h2>
                  <span
                    class="px-2.5 py-0.5 text-xs font-semibold rounded-full"
                    :class="
                      state.custom_config_mode
                        ? 'bg-amber-50 text-amber-700 border border-amber-200/70'
                        : 'bg-emerald-50 text-emerald-700 border border-emerald-200/70'
                    "
                  >
                    {{ state.custom_config_mode ? t('当前：自定义配置') : t('当前：默认服务端模板') }}
                  </span>
                </div>
                <p class="text-xs text-slate-500">
                  {{ t('您可以直接粘贴或编辑整份自备的 Mihomo 服务端配置文件（') }}<code dir="ltr" class="font-mono">config.yaml</code>{{ t('），校验通过后立即生效。普通用户无需修改此页。') }}
                </p>
              </div>

              <!-- 恢复标准模板 -->
              <button
                type="button"
                :disabled="busyKey === 'reset-template'"
                @click="resetTemplateConfig"
                class="px-4 py-2 rounded-xl text-xs font-semibold text-rose-700 bg-rose-50 hover:bg-rose-100 border border-rose-200/90 disabled:opacity-50 transition cursor-pointer shrink-0"
              >
                {{ busyKey === 'reset-template' ? t('正在恢复默认服务端模板…') : t('恢复默认服务端模板') }}
              </button>
            </div>

            <!-- 证书路径提示与说明 -->
            <div class="rounded-2xl bg-amber-50/90 border border-amber-200/90 p-4 text-xs text-amber-950 leading-relaxed space-y-1.5">
              <div class="font-bold text-amber-900">{{ t('⚠️ 醒目提醒：Mihomo 证书目录与相对路径说明') }}</div>
              <div>
                {{ t('1. 本系统已将 Mihomo 运行目录（') }}<code dir="ltr" class="font-mono font-semibold">-d</code>{{ t('）、配置文件与证书统一收纳在') }}
                <code dir="ltr" class="font-mono font-semibold">/etc/clashgate</code>{{ t('，证书实际位于') }}
                <code dir="ltr" class="font-mono font-semibold">/etc/clashgate/certs/fullchain.pem</code> {{ t('与') }}
                <code dir="ltr" class="font-mono font-semibold">/etc/clashgate/certs/privkey.pem</code>{{ t('（相对路径即') }}
                <code dir="ltr" class="font-mono font-semibold">certs/fullchain.pem</code> {{ t('与') }}
                <code dir="ltr" class="font-mono font-semibold">certs/privkey.pem</code>）。
              </div>
              <div>{{ t('2. 点击「更新 Mihomo 服务端配置」时会自动检查证书路径；如有其他证书路径或相对路径，会先询问是否改为本项目证书。') }}</div>
            </div>

            <div
              v-if="state.custom_config_saved"
              class="rounded-xl bg-sky-50 border border-sky-200/80 px-4 py-2.5 text-xs text-sky-900 leading-relaxed"
            >
              {{ t('编辑框中是你上次保存的自定义配置，点击「更新 Mihomo 服务端配置」即可恢复。') }}
            </div>

            <form @submit.prevent="submitCustomConfig" class="space-y-3.5">
              <textarea
                id="custom-config-raw"
                v-model="customConfigText"
                name="custom_config_raw"
                rows="16"
                :placeholder="t('在此粘贴完整的 Mihomo 服务端 YAML 配置…')"
                class="cg-input w-full p-4 rounded-2xl border border-slate-200 bg-[#f7f9fc] text-slate-800 font-mono text-xs leading-relaxed focus:bg-white"
              ></textarea>
              <div class="flex items-center gap-2.5 flex-wrap">
                <button
                  type="submit"
                  :disabled="busyKey === 'save-custom'"
                  class="cg-btn-primary px-4 py-2 rounded-xl disabled:opacity-50 text-xs font-semibold cursor-pointer"
                >
                  {{ busyKey === 'save-custom' ? t('正在校验并更新…') : t('更新 Mihomo 服务端配置') }}
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

      <!-- TAB 5: HTTPS 证书管理 -->
        <div v-else-if="activeTab === 'certs'" key="certs" id="certs-panel" class="space-y-6">
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
              class="rounded-xl bg-[#f1f6fe] border border-emerald-200/80 px-4 py-3 text-xs text-emerald-900 leading-relaxed"
            >
              {{ t('当前为手动证书模式。手动证书请直接替换 /etc/clashgate/certs/ 下的 fullchain.pem 与 privkey.pem 文件。') }}
            </div>

            <!-- 证书信息字段网格 -->
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5">
              <div class="rounded-xl bg-[#f7f9fc] border border-slate-200/80 p-3.5">
                <div class="text-xs font-medium text-slate-500">{{ t('域名') }}</div>
                <div id="cert-domain" dir="ltr" class="mt-1.5 text-sm font-bold text-slate-900 font-mono break-all text-start">
                  {{ certDomainDisplay }}
                </div>
              </div>

              <div class="rounded-xl bg-[#f7f9fc] border border-slate-200/80 p-3.5">
                <div class="text-xs font-medium text-slate-500">{{ t('当前模式') }}</div>
                <div id="cert-current-mode" class="mt-1.5 text-sm font-bold text-slate-900">
                  {{ certModeLabel }}
                </div>
              </div>

              <div class="rounded-xl bg-[#f7f9fc] border border-slate-200/80 p-3.5">
                <div class="text-xs font-medium text-slate-500">{{ t('颁发者') }}</div>
                <div id="cert-issuer" class="mt-1.5 text-sm font-bold text-slate-900 break-all">
                  {{ certIssuerDisplay }}
                </div>
              </div>

              <div class="rounded-xl bg-[#f7f9fc] border border-slate-200/80 p-3.5">
                <div class="text-xs font-medium text-slate-500">{{ t('过期时间') }}</div>
                <div id="cert-expires" dir="ltr" class="mt-1.5 text-sm font-bold text-slate-900 font-mono tabular-nums text-start">
                  {{ certExpiresDisplay }}
                </div>
              </div>

              <div
                class="rounded-xl border p-3.5"
                :class="
                  certDaysValue !== null && certDaysValue < 14
                    ? 'bg-amber-50/80 border-amber-200/90'
                    : 'bg-[#f7f9fc] border-slate-200/80'
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
                  {{ certDaysValue !== null ? t('{n} 天', { n: certDaysValue }) : '—' }}
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
                  <h2 class="text-base font-bold text-slate-900 tracking-tight">{{ t('切换并重新生成证书') }}</h2>
                </div>
                <p class="text-xs text-slate-500 mt-1 leading-relaxed">
                  {{ t('只有和当前模式不同时才能点击。切换后会立刻重新生成证书，Token 错误或 80 端口被占用会返回具体原因。') }}
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
                    dir="ltr"
                    :placeholder="t('请输入或粘贴具备 Zone.DNS 编辑权限的 Cloudflare API Token')"
                    @click="revealCfToken"
                    @blur="cfTokenRevealed = false"
                    class="cg-input w-full h-10 px-3.5 rounded-xl border border-emerald-100 bg-[#f5f8fd] hover:bg-emerald-50/50 focus:bg-white font-mono text-xs transition"
                    :class="cfTokenRevealed ? 'text-slate-800' : 'text-slate-600 tracking-widest'"
                  />
                </div>

                <button
                  id="cert-mode-submit"
                  type="submit"
                  :disabled="certRegenDisabled"
                  class="cg-btn-primary w-full h-10 rounded-xl disabled:opacity-40 disabled:cursor-not-allowed text-sm font-semibold cursor-pointer"
                >
                  {{ certRegenLock || busyKey === '/action/cert-mode' ? t('正在重新生成证书…') : t('切换并重新生成证书') }}
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
                  <ul class="mt-1.5 ms-4 space-y-1 list-disc text-slate-600">
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
                  {{ t('创建后复制生成的 Token，粘贴到左侧输入框。模式与当前不同时，按钮才会亮起，点击后切换并重新生成证书（Token 只显示一次）。') }}
                </li>
              </ol>

              <div class="rounded-xl bg-[#f1f6fe] border border-emerald-200/70 px-3.5 py-2.5 text-xs text-emerald-900 leading-relaxed">
                {{ t('DNS 模式不需要占用 80 端口，也不要求灰云（可开启橙云代理）；Token 仅保存在本机') }}
                <code class="font-mono font-semibold">/etc/clashgate/clashgate.env</code>。
              </div>
            </section>
          </div>
        </div>

      <!-- Settings -->
        <div v-else-if="activeTab === 'settings'" key="settings" class="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
          <section class="cg-surface rounded-2xl p-5 sm:p-6 space-y-4">
            <div class="flex items-center justify-between gap-4">
              <div>
                <h2 class="text-base font-bold text-slate-900 tracking-tight">{{ t('自定义服务端') }}</h2>
                <p class="text-xs text-slate-500 mt-1 leading-relaxed max-w-xl">
                  {{ t('高级功能，打开后可自由编辑 Mihomo 服务端配置。') }}
                </p>
              </div>
              <button
                type="button"
                role="switch"
                :aria-checked="state.custom_server_enabled ? 'true' : 'false'"
                :disabled="busyKey === '/action/settings'"
                @click="toggleCustomServer"
                class="cg-switch"
                :class="{ 'is-on': state.custom_server_enabled }"
              >
                <span></span>
              </button>
            </div>
          </section>

          <section class="cg-surface rounded-2xl p-5 sm:p-6">
            <div class="flex items-center justify-between gap-4">
              <div>
                <h2 class="text-base font-bold text-slate-900 tracking-tight">{{ t('自动更新') }}</h2>
                <p class="text-xs text-slate-500 mt-1 leading-relaxed max-w-xl">
                  {{ t('打开后每周自动更新面板。更新面板时会同时更新 Mihomo 内核。') }}
                </p>
              </div>
              <button
                type="button"
                role="switch"
                :aria-checked="state.auto_update ? 'true' : 'false'"
                :disabled="busyKey === '/action/settings'"
                @click="toggleAutoUpdate"
                class="cg-switch"
                :class="{ 'is-on': state.auto_update }"
              >
                <span></span>
              </button>
            </div>
          </section>

          <section class="cg-surface rounded-2xl p-5 sm:p-6">
            <div class="flex items-center justify-between gap-4">
              <div class="min-w-0">
                <h2 class="text-base font-bold text-slate-900 tracking-tight">{{ t('更新通道') }}</h2>
                <p class="text-xs mt-1 leading-relaxed" :class="state.update_channel === 'test' ? 'text-amber-700' : 'text-slate-500'">
                  {{ state.update_channel === 'test' ? t('当前为测试通道') : t('当前为正式通道') }} · {{ t('测试版可能不稳定，请谨慎使用。') }}
                </p>
              </div>
              <div class="flex shrink-0 rounded-lg border border-slate-200 p-0.5 bg-white">
                <button
                  type="button"
                  class="px-2.5 py-1 rounded-md text-xs font-semibold transition cursor-pointer"
                  :class="state.update_channel === 'stable' ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-50'"
                  :disabled="busyKey === '/action/settings'"
                  @click="setUpdateChannel('stable')"
                >{{ t('正式') }}</button>
                <button
                  type="button"
                  class="px-2.5 py-1 rounded-md text-xs font-semibold transition cursor-pointer"
                  :class="state.update_channel === 'test' ? 'bg-amber-500 text-white' : 'text-slate-600 hover:bg-slate-50'"
                  :disabled="busyKey === '/action/settings'"
                  @click="setUpdateChannel('test')"
                >{{ t('测试') }}</button>
              </div>
            </div>
          </section>

          <section class="cg-surface rounded-2xl">
            <button
              type="button"
              class="w-full p-5 sm:p-6 text-start rounded-2xl hover:bg-[#f7f9fc] transition cursor-pointer"
              @click="openPasswordModal"
            >
              <h2 class="text-base font-bold text-slate-900 tracking-tight">{{ t('修改面板密码') }}</h2>
              <p class="text-xs text-slate-500 mt-1 leading-relaxed">{{ t('更新当前登录密码。') }}</p>
            </button>
          </section>

          <section class="cg-surface rounded-2xl p-5 sm:p-6">
            <div class="flex items-center justify-between gap-4">
              <div class="min-w-0">
                <h2 class="text-base font-bold text-slate-900 tracking-tight">{{ t('皮肤') }}</h2>
                <p class="text-xs text-slate-500 mt-1 leading-relaxed">{{ t('只改变面板外观，保存在当前浏览器。') }}</p>
              </div>
              <div class="flex shrink-0 rounded-lg border border-slate-200 p-0.5 bg-white" role="radiogroup" :aria-label="t('皮肤')">
                <button
                  type="button"
                  role="radio"
                  :aria-checked="theme === 'default' ? 'true' : 'false'"
                  class="px-2.5 py-1 rounded-md text-xs font-semibold transition cursor-pointer"
                  :class="theme === 'default' ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-50'"
                  @click="setTheme('default')"
                >{{ t('默认') }}</button>
                <button
                  type="button"
                  role="radio"
                  :aria-checked="theme === 'christmas' ? 'true' : 'false'"
                  class="px-2.5 py-1 rounded-md text-xs font-semibold transition cursor-pointer"
                  :class="theme === 'christmas' ? 'bg-emerald-600 text-white' : 'text-slate-600 hover:bg-slate-50'"
                  @click="setTheme('christmas')"
                >{{ t('圣诞') }}</button>
              </div>
            </div>
          </section>
        </div>
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
