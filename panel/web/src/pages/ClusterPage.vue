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
</template>
