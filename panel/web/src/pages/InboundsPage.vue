<script setup>
import { t } from '../i18n.js'
import CgIcon from '../CgIcon.vue'
import CgSpinner from '../CgSpinner.vue'
import { usePanel } from '../composables/usePanel.js'

const {
  boot,
  pageMode,
  isXmas,
  state,
  liveNodeCount,
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
  ADV_FIELDS,
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
<div class="cg-home">
          <!-- 客户端订阅链接 -->
            <section
              id="sub-card"
              class="cg-home-sub cg-surface-emerald rounded-2xl p-5 sm:p-6 flex flex-col gap-3.5"
            >
              <div class="flex items-center justify-between gap-3 flex-wrap">
                <div class="flex items-center gap-2.5">
                  <span class="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
                  <h2 class="text-base font-bold text-slate-900">{{ t('客户端订阅链接') }}</h2>
                  <span
                    class="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200/70"
                  >
                    {{ t('ACL4SSR 自动同步') }}
                  </span>
                </div>
                <div v-if="state.sub_url" class="cg-btn-row">
                  <button
                    type="button"
                    @click="copyRaw(state.sub_url, 'sub-url')"
                    class="cg-btn-primary cg-btn-sm"
                  >
                    <CgIcon v-if="copiedKey === 'sub-url'" name="check" :size="13" />{{ copiedKey === 'sub-url' ? t('已复制') : t('复制订阅链接') }}
                  </button>
                  <button
                    v-if="state.sub_url && state.sub_qr_data_url"
                    id="sub-qr-btn"
                    type="button"
                    @click="showSubQrModal = true"
                    class="cg-btn-sm cg-btn-secondary"
                  >
                    {{ t('二维码') }}
                  </button>
                  <button
                    type="button"
                    :disabled="busyKey === 'reset-sub'"
                    @click="resetSubUrl"
                    class="cg-btn-sm cg-btn-secondary"
                  >
                    <CgSpinner v-if="busyKey === 'reset-sub'" :size="13" />{{ busyKey === 'reset-sub' ? t('更换中…') : t('更换订阅链接') }}
                  </button>
                  <a
                    :href="state.sub_url"
                    target="_blank"
                    rel="noopener"
                    class="cg-btn-sm cg-btn-secondary"
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
                  class="cg-input px-3.5 py-2.5 rounded-xl bg-[#f5f8fd] hover:bg-emerald-50/50 border border-emerald-100 font-mono text-xs transition cursor-pointer flex items-center justify-between gap-3"
                  :class="subUrlRevealed ? 'text-slate-700 break-all select-all' : 'text-slate-500 tracking-widest select-none'"
                >
                  <span class="min-w-0">{{ !state.sub_url ? '/etc/clashgate/client/mihomo-client.yaml' : subUrlRevealed ? state.sub_url : '••••••••••••••••••••••••••••••••' }}</span>
                  <CgIcon v-if="state.sub_url" :name="subUrlRevealed ? 'eyeOff' : 'eye'" :size="14" class="text-slate-400" />
                </div>
              </div>

              <div class="mt-auto pt-0.5 min-h-[28px] text-xs text-slate-500 flex items-center gap-1.5">
                <span>{{ t('本地客户端备份：') }}</span>
                <code class="px-2.5 py-1 rounded-lg bg-slate-100 text-slate-700 font-mono text-xs">/etc/clashgate/client/</code>
              </div>
            </section>

          <!-- Zashboard 控制面板 -->
          <section
            v-if="state.mode !== 'no-cert'"
            id="zashboard-card"
            class="cg-home-zb cg-surface rounded-2xl p-5 sm:p-6 flex flex-col gap-3.5"
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
              <div class="cg-btn-row">
                <a
                  :href="state.zb_url || '#'"
                  target="_blank"
                  rel="noopener"
                  class="cg-btn-primary cg-btn-sm"
                >
                  {{ t('打开 Zashboard') }}
                </a>
                <button
                  type="button"
                  @click="copyRaw(state.zb_url, 'zb-url')"
                  class="cg-btn-sm cg-btn-secondary"
                >
                  <CgIcon v-if="copiedKey === 'zb-url'" name="check" :size="13" />{{ copiedKey === 'zb-url' ? t('已复制地址') : t('复制地址') }}
                </button>
                <a
                  href="/config/server.yaml"
                  target="_blank"
                  rel="noopener"
                  class="cg-btn-sm cg-btn-secondary"
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
                class="cg-input px-3.5 py-2.5 rounded-xl bg-[#f5f8fd] hover:bg-emerald-50/50 border border-emerald-100 font-mono text-xs transition cursor-pointer flex items-center justify-between gap-3"
                :class="zbUrlRevealed ? 'text-slate-700 break-all select-all' : 'text-slate-500 tracking-widest select-none'"
              >
                <span class="min-w-0">{{ !state.zb_url ? '—' : zbUrlRevealed ? state.zb_url : '••••••••••••••••••••••••••••••••' }}</span>
                <CgIcon v-if="state.zb_url" :name="zbUrlRevealed ? 'eyeOff' : 'eye'" :size="14" class="text-slate-400" />
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
                  class="cg-btn-sm cg-btn-secondary"
                >
                  <CgIcon v-if="copiedKey === 'zb-secret'" name="check" :size="13" />{{ copiedKey === 'zb-secret' ? t('已复制') : t('复制密钥') }}
                </button>
                <button
                  type="button"
                  :disabled="busyKey === 'reset-secret'"
                  @click="resetZbSecret"
                  class="cg-btn-sm cg-btn-secondary"
                >
                  <CgSpinner v-if="busyKey === 'reset-secret'" :size="13" />{{ busyKey === 'reset-secret' ? t('重置中…') : t('重置 API 密钥') }}
                </button>
              </div>
            </div>
          </section>

            <!-- Right, under Zashboard (1.44): Add Node Form -->
            <section class="cg-home-add cg-surface rounded-2xl p-5 sm:p-6" :class="{ 'is-first': state.mode === 'no-cert' }">
              <div class="flex items-center justify-between gap-2 mb-4">
                <h2 class="text-base font-bold text-slate-900 tracking-tight">{{ t('添加节点') }}</h2>
                <span v-if="!state.custom_server_enabled" class="px-2.5 py-0.5 text-xs font-medium rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200/60">
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
                    <!-- 1.45: customOnly protocols (VLESS XHTTP) are listed only with the custom server on -->
                    <template v-for="p in PROTOCOLS" :key="p.value">
                      <option v-if="!p.customOnly || state.custom_server_enabled" :value="p.value">
                        {{ p.label }}
                      </option>
                    </template>
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

                <!-- Protocol options + locked note (custom server: the optional fields), stacked over invisible
                     copies for every protocol, so the card keeps one height while the protocol changes (1.46:
                     in custom server mode too). -->
                <div class="cg-stack">
                  <div
                    v-for="p in PROTOCOLS.filter((x) => !x.customOnly || state.custom_server_enabled)"
                    :key="'opt-' + p.value"
                    class="cg-stack-ghost space-y-4"
                    aria-hidden="true"
                  >
                    <div v-if="PROTOCOL_HAS_OPTION.has(p.value)">
                      <div class="block text-xs font-semibold mb-1.5">&nbsp;</div>
                      <div class="h-10 border border-transparent"></div>
                    </div>
                    <div v-if="state.custom_server_enabled && (ADV_FIELDS[p.value] || []).length" class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div v-for="f in ADV_FIELDS[p.value]" :key="'ghost-' + p.value + f.key" :class="{ 'sm:col-span-2': f.wide }">
                        <div class="block text-xs font-semibold mb-1.5">{{ t(f.desc) }}</div>
                        <div class="h-10 border border-transparent"></div>
                      </div>
                    </div>
                    <div v-if="!state.custom_server_enabled" class="rounded-xl border px-3.5 py-2.5 text-xs leading-relaxed">{{ t(p.lockedNote) }}</div>
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
                          <option value="1">{{ state.certs_present ? t('启用 (默认)') : t('启用') }}</option>
                          <option value="0">{{ state.certs_present ? t('不启用') : t('不启用 (默认)') }}</option>
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
                          <option value="1">{{ state.certs_present ? t('启用 (默认)') : t('启用') }}</option>
                          <option value="0">{{ state.certs_present ? t('不启用') : t('不启用 (默认)') }}</option>
                        </select>
                      </div>
                    </template>

                    <!-- 1.44, custom server: the options the safe defaults lock can be typed in; blank = default -->
                    <div v-if="state.custom_server_enabled && (ADV_FIELDS[inboundForm.kind] || []).length" class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div v-for="f in ADV_FIELDS[inboundForm.kind]" :key="inboundForm.kind + f.key" :class="{ 'sm:col-span-2': f.wide }">
                        <label :for="'adv-' + f.key" class="block text-xs font-semibold text-slate-700 mb-1.5">{{ t(f.desc) }}</label>
                        <select
                          v-if="f.options"
                          :id="'adv-' + f.key"
                          v-model="inboundForm.adv[f.key]"
                          class="cg-input w-full h-10 px-3 rounded-xl border border-slate-200 bg-white text-sm text-slate-900"
                        >
                          <option v-for="o in f.options" :key="o.value" :value="o.value">{{ t(o.desc) }}</option>
                        </select>
                        <input
                          v-else
                          :id="'adv-' + f.key"
                          v-model="inboundForm.adv[f.key]"
                          dir="ltr"
                          autocomplete="off"
                          spellcheck="false"
                          :placeholder="f.key === 'host' ? t('留空使用本机域名') : t('留空自动生成')"
                          class="cg-input w-full h-10 px-3 rounded-xl border border-slate-200 bg-white text-sm text-slate-900 font-mono"
                        />
                      </div>
                    </div>

                    <!-- Locked security defaults notice (hidden in custom server mode) -->
                    <div v-if="!state.custom_server_enabled" class="rounded-xl bg-[#f1f6fe] border border-emerald-200/70 px-3.5 py-2.5 text-xs text-emerald-900 leading-relaxed">
                      {{ t(currentProtocol.lockedNote) }}
                    </div>
                  </div>
                </div>

                <button
                  type="submit"
                  :disabled="busyKey === 'add-inbound'"
                  class="cg-btn-primary w-full h-10 mt-1 rounded-xl disabled:opacity-50 text-sm font-semibold cursor-pointer inline-flex items-center justify-center gap-2"
                >
                  <CgSpinner v-if="busyKey === 'add-inbound'" :size="14" light />{{ busyKey === 'add-inbound' ? t('正在添加…') : t('添加入站节点') }}
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
                    :title="t('当前生效的节点数')"
                  >
                    {{ liveNodeCount }}
                  </span>
                </div>
                <div class="flex items-center gap-2">
                  <button
                    v-if="state.inbounds.length > 0"
                    type="button"
                    @click="copyRaw(state.all_proxies_yaml, 'all-proxies')"
                    class="cg-btn-sm cg-btn-secondary"
                  >
                    <CgIcon v-if="copiedKey === 'all-proxies'" name="check" :size="13" />{{ copiedKey === 'all-proxies' ? t('已复制全部') : t('复制全部配置') }}
                  </button>
                </div>
              </div>

              <div
                v-if="state.inbounds.length === 0"
                class="cg-empty py-6 px-4 rounded-2xl border border-dashed border-slate-200 bg-slate-50/40 text-center text-sm text-slate-500"
              >
                {{ t('暂无入站节点，请先添加节点') }}
              </div>

              <div v-else class="divide-y divide-slate-100 border border-slate-200/80 rounded-2xl overflow-hidden">
                <div
                  v-for="item in state.inbounds"
                  :key="item.key"
                  class="p-4 transition flex flex-wrap items-center justify-between gap-3"
                  :class="item.pending_delete ? 'bg-slate-50/70' : 'hover:bg-emerald-50/35'"
                >
                  <div class="space-y-1 min-w-0 flex-[1_1_12rem]">
                    <div class="flex items-center gap-2 flex-wrap">
                      <span
                        class="font-bold text-sm cg-wrap"
                        :class="item.pending_delete ? 'text-slate-400 line-through' : 'text-slate-900'"
                      >{{ item.name }}</span>
                      <!-- 1.46: the protocol tag is neutral, so the status pill next to it is the only colour -->
                      <span
                        class="px-2 py-0.5 text-[11px] font-semibold rounded-md bg-slate-100 text-slate-600 border border-slate-200/80"
                      >
                        {{ item.kind_label }}
                      </span>
                      <span
                        class="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-medium rounded-full"
                        :class="
                          item.pending_delete
                            ? 'bg-amber-50 text-amber-700 border border-amber-200/60'
                            : item.listening
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200/60'
                              : item.pending_reload
                                ? 'bg-amber-50 text-amber-700 border border-amber-200/60'
                                : 'bg-rose-50 text-rose-700 border border-rose-200/60'
                        "
                      >
                        <span
                          class="w-1.5 h-1.5 rounded-full"
                          :class="item.pending_delete || (!item.listening && item.pending_reload) ? 'bg-amber-500' : item.listening ? 'bg-emerald-500' : 'bg-rose-500'"
                        ></span>
                        {{ item.pending_delete ? t('待删除') : item.listening ? t('运行中') : item.pending_reload ? t('待应用') : t('未运行') }}
                      </span>
                    </div>
                    <div class="text-xs text-slate-500 tabular-nums">{{ t('端口') }} <bdi dir="ltr" class="font-mono">{{ item.port }}</bdi></div>
                  </div>

                  <div v-if="item.pending_delete" class="text-xs text-slate-500">
                    {{ t('点顶部「应用配置」后删除') }}
                  </div>
                  <!-- Actions: 复制配置 + 重置密码 + 删除 -->
                  <div v-else class="flex items-center gap-2 flex-wrap min-w-0 max-w-full">
                    <button
                      type="button"
                      @click="copyRaw(item.single_config, `single-${item.key}`)"
                      class="cg-btn-sm cg-btn-secondary"
                    >
                      <CgIcon v-if="copiedKey === `single-${item.key}`" name="check" :size="13" />{{ copiedKey === `single-${item.key}` ? t('已复制') : t('复制配置') }}
                    </button>
                    <button
                      v-if="item.can_reset_password"
                      type="button"
                      :disabled="busyKey === `rst-${item.key}`"
                      @click="resetInboundPassword(item)"
                      class="cg-btn-sm cg-btn-secondary"
                    >
                      <CgSpinner v-if="busyKey === `rst-${item.key}`" :size="13" />{{ busyKey === `rst-${item.key}` ? t('重置中…') : t('重置密码') }}
                    </button>
                    <button
                      type="button"
                      :disabled="busyKey === `del-${item.key}`"
                      @click="deleteInbound(item)"
                      class="cg-btn-sm cg-btn-danger"
                    >
                      <CgSpinner v-if="busyKey === `del-${item.key}`" :size="13" inherit />{{ busyKey === `del-${item.key}` ? t('删除中…') : t('删除') }}
                    </button>
                  </div>
                </div>
              </div>
            </section>
        </div>
</template>
