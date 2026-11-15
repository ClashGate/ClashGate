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
</template>
