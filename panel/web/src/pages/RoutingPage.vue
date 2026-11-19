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
<div class="space-y-4">
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
                <p class="text-xs text-slate-500 mt-1">{{ t('拖动调整顺序（与主配置一致），点顶部「应用配置」后生效。') }}</p>
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
</template>
