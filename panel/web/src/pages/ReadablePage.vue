<script setup>
import { t } from '../i18n.js'
import { usePanel } from '../composables/usePanel.js'

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
<div class="space-y-6">
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
</template>
