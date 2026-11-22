<script setup>
import { t } from '../i18n.js'
import { theme, setTheme } from '../theme.js'
import { usePanel } from '../composables/usePanel.js'
import CgIcon from '../CgIcon.vue'

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
  confirmUpdateCore,
} = usePanel()
</script>

<template>
<div id="settings-grid" class="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <section id="settings-password-card" class="cg-surface rounded-2xl flex">
            <button
              type="button"
              class="w-full p-5 sm:p-6 text-start rounded-2xl hover:bg-[#f7f9fc] transition cursor-pointer flex items-center justify-between gap-4"
              @click="openPasswordModal"
            >
              <span class="min-w-0 block">
                <span class="block text-base font-bold text-slate-900 tracking-tight">{{ t('修改面板密码') }}</span>
                <span class="block text-xs text-slate-500 mt-1 leading-relaxed">{{ t('更新当前登录密码。') }}</span>
              </span>
              <span class="cg-tool shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold border bg-white border-slate-200 text-slate-800 inline-flex items-center gap-1">
                <span>{{ t('修改') }}</span>
                <CgIcon name="chevron" :size="14" class="rtl:rotate-180" />
              </span>
            </button>
          </section>

          <section class="cg-surface rounded-2xl p-5 sm:p-6 flex flex-col justify-center">
            <div class="flex items-center justify-between gap-4">
              <div class="min-w-0">
                <h2 class="text-base font-bold text-slate-900 tracking-tight">{{ t('更新通道') }}</h2>
                <p class="text-xs mt-1 leading-relaxed" :class="state.update_channel === 'test' ? 'text-amber-700' : 'text-slate-500'">
                  {{ state.update_channel === 'test' ? t('当前为测试通道') : t('当前为正式通道') }} · {{ t('测试版可能不稳定，请谨慎使用。') }}
                </p>
              </div>
              <div class="flex shrink-0 rounded-lg border border-slate-200 p-0.5 bg-white" role="radiogroup" :aria-label="t('更新通道')">
                <button
                  type="button"
                  role="radio"
                  :aria-checked="state.update_channel === 'stable' ? 'true' : 'false'"
                  class="px-2.5 py-1 rounded-md text-xs font-semibold transition cursor-pointer"
                  :class="state.update_channel === 'stable' ? 'bg-emerald-600 text-white' : 'text-slate-600 hover:bg-slate-50'"
                  :disabled="busyKey === '/action/settings'"
                  @click="setUpdateChannel('stable')"
                >{{ t('正式') }}</button>
                <button
                  type="button"
                  role="radio"
                  :aria-checked="state.update_channel === 'test' ? 'true' : 'false'"
                  class="px-2.5 py-1 rounded-md text-xs font-semibold transition cursor-pointer"
                  :class="state.update_channel === 'test' ? 'bg-emerald-600 text-white' : 'text-slate-600 hover:bg-slate-50'"
                  :disabled="busyKey === '/action/settings'"
                  @click="setUpdateChannel('test')"
                >{{ t('测试') }}</button>
              </div>
            </div>
          </section>

          <section class="cg-surface rounded-2xl p-5 sm:p-6 flex flex-col justify-center">
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

          <section id="settings-core-card" class="cg-surface rounded-2xl p-5 sm:p-6 flex flex-col justify-center">
            <div class="flex items-center justify-between gap-4">
              <div class="min-w-0">
                <h2 class="text-base font-bold text-slate-900 tracking-tight">{{ t('内核版本') }}</h2>
                <p class="text-xs mt-1 leading-relaxed" :class="coreHasUpdate ? 'text-emerald-700' : 'text-slate-500'">
                  {{ t('Mihomo 内核') }} <bdi dir="ltr">{{ versionLabel(state.mihomo_version) || '—' }}</bdi>
                  · {{ coreHasUpdate ? updateHint(coreUpdate.latest) : t('更新时连接会短暂中断。') }}
                </p>
              </div>
              <button
                id="settings-update-core"
                type="button"
                :disabled="busyKey === '/action/update-core'"
                @click="confirmUpdateCore"
                class="cg-tool shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold border disabled:opacity-50 cursor-pointer inline-flex items-center gap-1.5 bg-white hover:bg-slate-50 border-slate-200 text-slate-800"
                :class="{ 'is-update': coreHasUpdate }"
              >
                <CgIcon name="refresh" :size="14" />
                <span>{{ busyKey === '/action/update-core' ? t('更新内核中…') : t('更新内核') }}</span>
              </button>
            </div>
          </section>

          <section class="cg-surface rounded-2xl p-5 sm:p-6 flex flex-col justify-center">
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
                  :class="theme === 'default' ? 'bg-emerald-600 text-white' : 'text-slate-600 hover:bg-slate-50'"
                  @click="setTheme('default')"
                >{{ t('默认') }}</button>
                <button
                  type="button"
                  role="radio"
                  :aria-checked="theme === 'dark' ? 'true' : 'false'"
                  class="px-2.5 py-1 rounded-md text-xs font-semibold transition cursor-pointer"
                  :class="theme === 'dark' ? 'bg-emerald-600 text-white' : 'text-slate-600 hover:bg-slate-50'"
                  @click="setTheme('dark')"
                >{{ t('深色') }}</button>
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

          <section class="cg-surface rounded-2xl p-5 sm:p-6 flex flex-col justify-center">
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

          <!-- 1.44: 关于 (version, recent changes, credits) -->
          <section id="settings-about-card" class="cg-surface rounded-2xl flex lg:col-span-2">
            <button
              type="button"
              class="w-full p-5 sm:p-6 text-start rounded-2xl hover:bg-[#f7f9fc] transition cursor-pointer flex items-center justify-between gap-4"
              @click="selectTab('about')"
            >
              <span class="min-w-0 flex items-center gap-3">
                <img src="/assets/logo.png" alt="" class="w-9 h-9 rounded-xl shrink-0" />
                <span class="min-w-0 block">
                  <span class="block text-base font-bold text-slate-900 tracking-tight">{{ t('关于 ClashGate') }}</span>
                  <span class="block text-xs text-slate-500 mt-1 leading-relaxed">{{ t('版本、最近的更新和鸣谢。') }}</span>
                </span>
              </span>
              <span class="cg-tool shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold border bg-white border-slate-200 text-slate-800 inline-flex items-center gap-1">
                <span dir="ltr">v{{ state.version }}</span>
                <CgIcon name="chevron" :size="14" class="rtl:rotate-180" />
              </span>
            </button>
          </section>
        </div>
</template>
