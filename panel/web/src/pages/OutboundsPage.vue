<script setup>
import { t } from '../i18n.js'
import CgIcon from '../CgIcon.vue'
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
<div class="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
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
</template>
