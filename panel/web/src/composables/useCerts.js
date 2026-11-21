// Panel state and actions for the HTTPS certificate page.
// Split out of usePanel.js: `p` carries the shared state and helpers usePanel creates first.
import { ref, reactive, computed } from 'vue'
import { t } from '../i18n.js'
import { postForm } from './api.js'

export function useCerts(p) {
  const { applyServerState, busyKey, maskAllSensitive, openConfirmDialog, showToast, state } = p

  // HTTPS Certificate management state
  const certModeForm = reactive({
    mode: state.cert_mode === 'dns' || state.cert_mode === 'manual' ? state.cert_mode : 'port',
    cf_token: state.cf_token || '',
  })
  const certRegenLock = ref(false)

  const certModeValue = computed(() => state.cert_mode || (state.status && state.status.cert_mode) || 'port')
  const certModeLabel = computed(() => {
    if (state.mode === 'no-cert' && !state.certs_present && !state.domain) {
      return t('无证书模式')
    }
    const m = certModeValue.value
    if (m === 'dns') return t('Cloudflare DNS')
    if (m === 'manual') return t('手动证书')
    return t('端口模式')
  })
  const certDomainDisplay = computed(() => state.domain || (state.status && state.status.domain) || '—')
  const certIssuerDisplay = computed(() => (state.status && state.status.cert_issuer) || state.cert_issuer || '—')
  const certExpiresDisplay = computed(() => (state.status && state.status.cert_expires) || state.cert_expires || '—')
  const certDaysValue = computed(() => {
    const d = state.status && state.status.cert_days !== undefined ? state.status.cert_days : state.cert_days
    return d === null || d === undefined || d === '' ? null : Number(d)
  })
  const certIsTemp = computed(() => /clashgate temporary/i.test(certIssuerDisplay.value))
  const certBaselineMode = computed(() => (certModeValue.value === 'dns' ? 'dns' : 'port'))
  const certModeDirty = computed(() => {
    // Manual: always clickable, so replaced files can be re-checked and loaded.
    if (certModeForm.mode === 'manual') return true
    if (certModeValue.value === 'manual') return certModeForm.mode === 'dns' || certModeForm.mode === 'port'
    if (certModeForm.mode !== certBaselineMode.value) return true
    if (certModeForm.mode === 'dns' && (certModeForm.cf_token || '') !== (state.cf_token || '')) return true
    return false
  })
  const certRegenDisabled = computed(() => !certModeDirty.value || certRegenLock.value || busyKey.value === '/action/cert-mode')

  // Certificate jobs run in the background on the server (up to ~3 minutes): start, then poll.
  const certTaskElapsed = ref(0)

  async function pollCertTask(key) {
    const deadline = Date.now() + 300000
    while (Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, 1500))
      let d = null
      try {
        const res = await fetch('/api/cert-task-status', {
          headers: { Accept: 'application/json', 'X-Requested-With': 'fetch' },
          credentials: 'same-origin',
          cache: 'no-store',
        })
        if (res.status === 401) {
          window.location.href = '/login'
          return
        }
        if (!res.ok) continue
        d = await res.json()
      } catch {
        continue
      }
      if (d.running) {
        certTaskElapsed.value = Number(d.elapsed || 0)
        continue
      }
      if (d.state) applyServerState(d.state)
      if (d.done) showToast(d.msg || (d.ok ? t('操作成功') : t('操作失败')), !!d.ok, d.detail)
      else showToast(t('没能拿到证书任务的结果，请刷新页面查看证书状态'), false)
      return
    }
    showToast(t('没能拿到证书任务的结果，请刷新页面查看证书状态'), false)
  }

  async function runCertTask(url, params, key) {
    if (busyKey.value) return
    busyKey.value = key
    certRegenLock.value = true
    certTaskElapsed.value = 0
    try {
      let data = null
      try {
        const r = await postForm(url, { ...params, async: '1' }, { csrf: state.csrf })
        if (r.unauthorized) return
        data = r.data
      } catch {
        data = null   // the request may still have started: follow the task status
      }
      if (data && !data.running) {
        if (data.state) applyServerState(data.state)
        showToast(data.msg || (data.ok ? t('操作成功') : t('操作失败')), !!data.ok, data.detail)
        return
      }
      await pollCertTask(key)
    } finally {
      busyKey.value = ''
      certRegenLock.value = false
      certTaskElapsed.value = 0
    }
  }

  // After a page reload while a certificate job is still running, keep showing it.
  async function resumeCertTaskIfRunning() {
    try {
      const res = await fetch('/api/cert-task-status', {
        headers: { Accept: 'application/json', 'X-Requested-With': 'fetch' },
        credentials: 'same-origin',
        cache: 'no-store',
      })
      if (!res.ok) return
      const d = await res.json()
      if (!d || !d.running || busyKey.value) return
      busyKey.value = '/action/cert'
      certRegenLock.value = true
      certTaskElapsed.value = Number(d.elapsed || 0)
      try {
        await pollCertTask('/action/cert')
      } finally {
        busyKey.value = ''
        certRegenLock.value = false
        certTaskElapsed.value = 0
      }
    } catch {}
  }

  function confirmCertRenew() {
    if (busyKey.value || certRegenLock.value) return
    openConfirmDialog({
      title: t('立即申请 / 续期'),
      message: t("将马上向 Let's Encrypt 申请证书（证书还有效且不急着续期时会直接跳过）。同一域名每周最多签发 5 张，请不要反复点击。"),
      confirmText: t('立即申请'),
      tone: 'amber',
      onConfirm: () => runCertTask('/action/cert', {}, '/action/cert'),
    })
  }

  function submitCertMode() {
    if (busyKey.value || certRegenLock.value || !certModeDirty.value) return
    if (certModeForm.mode === 'dns') {
      const tok = certModeForm.cf_token
      if (!tok) {
        showToast(t('请输入 Cloudflare API Token'), false)
        return
      }
      if (/[\s"'`$\\]/.test(tok)) {
        showToast(t('API Token 不能包含空格或引号'), false)
        return
      }
    }
    if (certModeForm.mode === 'manual') {
      openConfirmDialog({
        title: certModeValue.value === 'manual' ? t('重新校验证书') : t('切换到手动证书'),
        message: t('将检查 /etc/clashgate/certs/ 里的证书和私钥，通过后启用，内核会重启几秒钟。检查不通过时保持原来的证书不变。'),
        confirmText: t('开始校验'),
        tone: 'amber',
        onConfirm: () => doSubmitCertMode(),
      })
      return
    }
    openConfirmDialog({
      title: t('切换并重新生成证书'),
      message: t("将马上向 Let's Encrypt 重新申请证书。同一域名每周最多签发 5 张，失败几次后可能要等一周，请确认设置无误再继续。申请失败时保持原来的证书和模式不变。"),
      confirmText: t('确认切换'),
      tone: 'amber',
      onConfirm: () => doSubmitCertMode(),
    })
  }

  async function doSubmitCertMode() {
    if (busyKey.value || certRegenLock.value || !certModeDirty.value) return
    maskAllSensitive()
    try {
      await runCertTask(
        '/action/cert-mode',
        {
          cert_mode: certModeForm.mode,
          cf_token: certModeForm.cf_token,
        },
        '/action/cert-mode'
      )
    } finally {
      maskAllSensitive()
    }
  }

  return {
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
    certTaskElapsed,
    resumeCertTaskIfRunning,
    confirmCertRenew,
    submitCertMode,
  }
}
