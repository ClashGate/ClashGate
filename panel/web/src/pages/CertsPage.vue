<script setup>
import { t } from '../i18n.js'
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
  confirmCertRenew,
} = usePanel()
</script>

<template>
<div id="certs-panel" class="space-y-6">
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
              <button
                v-if="state.mode !== 'no-cert' && certModeValue !== 'manual'"
                id="cert-renew"
                type="button"
                :disabled="!!busyKey || certRegenLock"
                @click="confirmCertRenew"
                class="cg-tool shrink-0 self-start sm:self-auto px-3 py-1.5 rounded-lg text-xs font-semibold border disabled:opacity-50 cursor-pointer inline-flex items-center gap-1.5 bg-white hover:bg-slate-50 border-slate-200 text-slate-800"
              >
                <CgIcon name="refresh" :size="14" />
                <span>{{ busyKey === '/action/cert' ? t('正在申请证书…') : t('立即申请 / 续期') }}</span>
              </button>
            </div>

            <!-- 无证书空态说明 -->
            <div
              v-if="state.mode === 'no-cert' || !state.certs_present"
              id="cert-empty-notice"
              class="rounded-xl bg-amber-50/90 border border-amber-200/80 px-4 py-3 text-xs text-amber-900 leading-relaxed"
            >
              {{ t('当前为无证书模式或未检测到证书文件（/etc/clashgate/certs/fullchain.pem）。可在下方选择 Cloudflare DNS 或端口模式自动申请证书；已有自己的证书，也可以放好文件后选择「手动证书」。') }}
            </div>

            <!-- 手动证书提示 -->
            <div
              v-else-if="certModeValue === 'manual'"
              id="cert-manual-notice"
              class="rounded-xl bg-emerald-50 border border-emerald-200/80 px-4 py-3 text-xs text-emerald-900 leading-relaxed"
            >
              {{ t('当前为手动证书模式，证书不会自动续期。换新证书时，把新文件放进 /etc/clashgate/certs/，再在下方点「重新校验证书」。') }}
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

          <!-- 切换证书模式 & 右侧说明（Cloudflare API Token / 手动证书放置方法） -->
          <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <!-- Left: 切换 Cloudflare DNS 模式表单 -->
            <section id="cert-dns-form-card" class="lg:col-span-6 cg-surface rounded-2xl p-5 sm:p-6 space-y-4">
              <div>
                <div class="flex items-center gap-2.5">
                  <h2 class="text-base font-bold text-slate-900 tracking-tight">{{ t('切换证书模式') }}</h2>
                </div>
                <p class="text-xs text-slate-500 mt-1 leading-relaxed">
                  {{ t('自动证书（Cloudflare DNS / 端口模式）切换后会立刻重新申请，Token 错误或 80 端口被占用会返回具体原因。手动证书会先校验你放好的文件，通过后才切换。') }}
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
                    <option value="manual">{{ t('手动证书（使用自己的证书文件）') }}</option>
                  </select>
                </div>

                <div v-if="certModeForm.mode === 'dns'">
                  <label for="cf-token" class="block text-xs font-semibold text-slate-700 mb-1.5">
                    {{ t('Cloudflare API Token') }}
                  </label>
                  <div id="cf-token-wrap" class="relative">
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
                      class="cg-input w-full h-10 ps-3.5 pe-10 rounded-xl border border-emerald-100 bg-emerald-50/60 hover:bg-emerald-50 focus:bg-white font-mono text-xs transition"
                      :class="cfTokenRevealed ? 'text-slate-800' : 'text-slate-600 tracking-widest'"
                    />
                    <button
                      id="cf-token-eye"
                      type="button"
                      class="absolute inset-y-0 end-0 w-10 flex items-center justify-center rounded-e-xl text-slate-500 hover:text-slate-800 cursor-pointer"
                      :aria-label="cfTokenRevealed ? t('隐藏 Token') : t('显示 Token')"
                      :title="cfTokenRevealed ? t('隐藏 Token') : t('显示 Token')"
                      :aria-pressed="cfTokenRevealed ? 'true' : 'false'"
                      @click="cfTokenRevealed = !cfTokenRevealed"
                    >
                      <CgIcon :name="cfTokenRevealed ? 'eyeOff' : 'eye'" :size="16" />
                    </button>
                  </div>
                </div>

                <div
                  v-else-if="certModeForm.mode === 'manual'"
                  id="cert-manual-hint"
                  class="rounded-xl bg-emerald-50 border border-emerald-200/70 px-3.5 py-2.5 text-xs text-emerald-900 leading-relaxed"
                >
                  {{ t('先把证书和私钥放进 /etc/clashgate/certs/：证书 fullchain.pem（或 *.crt），私钥 privkey.pem（或 *.key）。放好后点下面的按钮。') }}
                </div>

                <button
                  id="cert-mode-submit"
                  type="submit"
                  :disabled="certRegenDisabled"
                  class="cg-btn-primary w-full h-10 rounded-xl disabled:opacity-40 disabled:cursor-not-allowed text-sm font-semibold cursor-pointer"
                >
                  {{
                    certModeForm.mode === 'manual'
                      ? certRegenLock || busyKey === '/action/cert-mode'
                        ? t('正在校验证书…')
                        : certModeValue === 'manual'
                          ? t('重新校验证书')
                          : t('校验并切换')
                      : certRegenLock || busyKey === '/action/cert-mode'
                        ? t('正在重新生成证书…')
                        : t('切换并重新生成证书')
                  }}
                </button>
              </form>
            </section>

            <!-- Right: 手动证书放置说明卡（选择手动证书时显示） -->
            <section
              v-if="certModeForm.mode === 'manual'"
              id="cert-manual-guide-card"
              class="lg:col-span-6 cg-surface rounded-2xl p-5 sm:p-6 space-y-3.5"
            >
              <div class="flex items-center gap-2.5">
                <h2 class="text-base font-bold text-slate-900 tracking-tight">{{ t('如何使用自己的证书') }}</h2>
              </div>
              <p class="text-xs text-slate-500">
                {{ t('适合已经在别处申请好证书的情况（例如云服务商或其他服务器上的证书）：') }}
              </p>

              <ol class="space-y-2.5 text-xs text-slate-700 leading-relaxed list-decimal list-inside">
                <li>
                  {{ t('准备证书文件（完整证书链）和对应的私钥，证书要包含当前域名 {domain}（泛域名证书也可以）。', { domain: certDomainDisplay }) }}
                </li>
                <li>
                  {{ t('用 SFTP 或 scp 把文件上传到服务器的 /etc/clashgate/certs/ 目录。文件名用 fullchain.pem 和 privkey.pem，或者直接用 .crt 和 .key 文件，面板会自动识别最新放入的那一份。') }}
                </li>
                <li>
                  {{ t('回到左侧点按钮。面板会检查证书是否过期、域名是否一致、私钥是否配对，通过后自动启用新证书。') }}
                </li>
              </ol>

              <div class="rounded-xl bg-emerald-50 border border-emerald-200/70 px-3.5 py-2.5 text-xs text-emerald-900 leading-relaxed">
                {{ t('手动证书不会自动续期。证书到期前请换上新文件，再点一次「重新校验证书」。') }}
              </div>
            </section>

            <!-- Right: 端口模式要求（选择端口模式时显示） -->
            <section
              v-else-if="certModeForm.mode === 'port'"
              id="cert-port-guide-card"
              class="lg:col-span-6 cg-surface rounded-2xl p-5 sm:p-6 space-y-3.5"
            >
              <div class="flex items-center gap-2.5">
                <h2 class="text-base font-bold text-slate-900 tracking-tight">{{ t('端口模式需要准备什么') }}</h2>
              </div>
              <p class="text-xs text-slate-500">
                {{ t("端口模式由 Let's Encrypt 通过 80 端口验证域名，申请前请确认：") }}
              </p>
              <ol class="space-y-2.5 text-xs text-slate-700 leading-relaxed list-decimal list-inside">
                <li>{{ t('域名 {domain} 的 A 记录指向本服务器的公网 IP；如果有 AAAA 记录，也要指向本机，否则请删掉。', { domain: certDomainDisplay }) }}</li>
                <li>{{ t('使用 Cloudflare 时，把这条记录设为灰云（DNS only），不要开启橙云代理。') }}</li>
                <li>{{ t('在云服务商的防火墙 / 安全组放行 TCP 80，并确保本机 80 端口没有被其他程序占用。') }}</li>
              </ol>
              <div class="rounded-xl bg-emerald-50 border border-emerald-200/70 px-3.5 py-2.5 text-xs text-emerald-900 leading-relaxed">
                {{ t('证书到期前 30 天会自动续期，续期时同样需要 80 端口。不方便开放 80 端口时，可以改用 Cloudflare DNS。') }}
              </div>
            </section>

            <!-- Right: 如何获取 Cloudflare API Token 说明卡 -->
            <section
              v-else
              id="cf-token-guide-card"
              class="lg:col-span-6 cg-surface rounded-2xl p-5 sm:p-6 space-y-3.5"
            >
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

              <div class="rounded-xl bg-emerald-50 border border-emerald-200/70 px-3.5 py-2.5 text-xs text-emerald-900 leading-relaxed">
                {{ t('DNS 模式申请证书不需要 80 端口，也不受 Cloudflare 橙云影响；但管理面板和订阅链接用的是随机端口，这条域名记录仍要设为灰云（DNS only）才能访问。Token 仅保存在本机') }}
                <code class="font-mono font-semibold">/etc/clashgate/clashgate.env</code>。
              </div>
            </section>
          </div>
        </div>
</template>
