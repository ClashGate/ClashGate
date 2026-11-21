// Panel state and actions for the core / panel update checks and upgrades.
// Split out of usePanel.js: `p` carries the shared state and helpers usePanel creates first.
import { ref, computed } from 'vue'
import { t } from '../i18n.js'

export function useUpdates(p) {
  const { applyServerState, busyKey, openConfirmDialog, postAction, showToast, showVersionPanel, state } = p

  const coreUpdate = computed(() => state.update_check.core || {})
  const panelUpdate = computed(() => state.update_check.panel || {})

  // update-state: pure helpers (mirrored by tests/test_panel.py)
  // Versions compare as integer tuples like the backend's parse_version_tuple (1.15 > 1.14, 1.15.0 == 1.15).
  function cgVersionTuple(v) {
    const nums = (String(v || '').trim().replace(/^v/i, '').match(/\d+/g) || ['0']).map(Number)
    while (nums.length > 1 && nums[nums.length - 1] === 0) nums.pop()
    return nums
  }
  function cgVersionNewer(a, b) {
    const x = cgVersionTuple(a), y = cgVersionTuple(b)
    for (let i = 0; i < Math.max(x.length, y.length); i++) {
      const d = (x[i] || 0) - (y[i] || 0)
      if (d) return d > 0
    }
    return false
  }
  // The badge is shown only for a version strictly newer than what is installed now,
  // and never while an upgrade is running or the page is about to reload after one.
  function cgShowUpdate(slot, installed, upgrading) {
    if (upgrading || !slot || !slot.has_update) return false
    if (!slot.latest || !installed) return true
    return cgVersionNewer(slot.latest, installed)
  }
  // After an upgrade lands, the cached check result describes the old build: drop it.
  function cgSlotAfterUpgrade(slot, version) {
    return { ...(slot || {}), current: version || (slot && slot.current) || '', has_update: false }
  }
  // end update-state

  const upgradeInProgress = ref(false)
  const panelHasUpdate = computed(() =>
    cgShowUpdate(panelUpdate.value, state.version, upgradeInProgress.value || busyKey.value === '/action/upgrade-self')
  )
  const coreHasUpdate = computed(() =>
    cgShowUpdate(coreUpdate.value, state.mihomo_version, upgradeInProgress.value || busyKey.value === '/action/update-core')
  )

  function versionLabel(v) {
    const s = String(v || '').trim()
    if (!s) return ''
    return /^v/i.test(s) ? s : `v${s}`
  }

  function updateHint(v) {
    const label = versionLabel(v)
    return label ? t('有新版本 {v}', { v: label }) : t('有新版本')
  }

  function applyUpdateCheck(src) {
    if (!src || typeof src !== 'object') return
    state.update_check = {
      core: mergeUpdateSlot(state.update_check.core, src.core),
      panel: mergeUpdateSlot(state.update_check.panel, src.panel),
    }
  }

  function mergeUpdateSlot(prev, next) {
    const base = {
      checked_at: 0,
      current: '',
      latest: '',
      has_update: false,
      ...(prev || {}),
    }
    if (!next || typeof next !== 'object') return base
    const prevTs = Number(base.checked_at || 0)
    const nextTs = Number(next.checked_at || 0)
    if (!nextTs || nextTs < prevTs) return base
    return {
      ...base,
      ...next,
      checked_at: nextTs,
      has_update: !!next.has_update,
    }
  }

  function confirmUpdateCore() {
    if (busyKey.value) return
    openConfirmDialog({
      title: t('更新内核'),
      message: t('将下载最新的 Mihomo 内核并重启。重启时所有连接会中断几秒钟，客户端会自动重连。'),
      confirmText: t('确认更新'),
      tone: 'amber',
      onConfirm: () => updateCoreDirect(),
    })
  }

  async function updateCoreDirect() {
    if (busyKey.value) return
    busyKey.value = '/action/update-core'
    const body = new URLSearchParams({ csrf: state.csrf, async: '1' }).toString()
    try {
      const startRes = await fetch('/action/update-core', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'X-Requested-With': 'fetch',
          Accept: 'application/json',
        },
        body,
        credentials: 'same-origin',
        cache: 'no-store',
      })
      if (startRes.status === 401) {
        window.location.href = '/login'
        return
      }
      const startData = await startRes.json().catch(() => null)
      if (startData && startData.running === false) {
        busyKey.value = ''
        if (startData.state) applyServerState(startData.state)
        showToast(startData.msg || (startData.ok ? t('内核更新成功') : t('更新内核失败')), !!startData.ok)
        return
      }
    } catch {
      // Fall through to poll /api/update-core-status
    }

    const deadline = Date.now() + 180000
    while (Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, 1200))
      try {
        const pollRes = await fetch('/api/update-core-status', {
          headers: { Accept: 'application/json', 'X-Requested-With': 'fetch' },
          credentials: 'same-origin',
          cache: 'no-store',
        })
        if (pollRes.status === 401) {
          window.location.href = '/login'
          return
        }
        if (!pollRes.ok) continue
        const pollData = await pollRes.json()
        if (pollData && pollData.running === false) {
          if (pollData.state) applyServerState(pollData.state)
          showToast(pollData.msg || (pollData.ok ? t('内核更新成功') : t('更新内核失败')), !!pollData.ok)
          busyKey.value = ''
          return
        }
      } catch {
        // Transient connection drop while mihomo restarts — keep polling
      }
    }
    busyKey.value = ''
    showToast(t('更新内核等待超时，请刷新页面查看内核版本状态'), false)
  }

  function toggleVersionPanel() {
    showVersionPanel.value = !showVersionPanel.value
  }

  async function checkUpdateAndPrompt() {
    const res = await postAction('/action/check-update', {}, '/action/check-update', { silentToast: true })
    if (!res || !res.ok) return
    const hasUpdate = !!res.has_update
    state.update_check.panel = {
      checked_at: Math.floor(Date.now() / 1000),
      current: res.current_version || state.version,
      latest: res.latest_version || '',
      has_update: hasUpdate,
    }
    if (hasUpdate) {
      const latest = res.latest_version || t('最新版')
      const current = res.current_version || state.version
      openConfirmDialog({
        title: t('检查更新'),
        message: t('检测到新版本 v{latest}（当前版本 v{current}），是否立即升级？', { latest, current }),
        confirmText: t('立即升级'),
        tone: 'emerald',
        onConfirm: () => postAction('/action/upgrade-self', {}, '/action/upgrade-self'),
      })
      return
    }
    if (res.msg) showToast(res.msg, true)
  }

  async function resumeUpgradeIfRunning() {
    // Page opened/refreshed mid-upgrade: keep tracking it and auto-refresh when done.
    try {
      const res = await fetch('/api/upgrade-status', {
        headers: { Accept: 'application/json', 'X-Requested-With': 'fetch' },
        credentials: 'same-origin',
        cache: 'no-store',
      })
      if (!res.ok) return
      const d = await res.json()
      const age = Date.now() / 1000 - Number(d.started_at || 0)
      if (d && d.state === 'running' && age < 600) reloadPanelAfterUpgrade(d.from || state.version)
    } catch {}
  }

  async function reloadPanelAfterUpgrade(previousVersion) {
    // Upgrade runs detached on the server; the panel restarts during it.
    // Poll status (tolerating connection drops) until done, then report + reload.
    // Once we decide to reload, the page stays in the "upgrading" state until the browser
    // replaces it: location.reload() returns at once and the old page keeps rendering for a
    // moment, which used to flash the stale "update available" badge.
    const deadline = Date.now() + 360000
    let sawDown = false
    let stage = ''
    let reloading = false
    const reloadSoon = async (ms, version) => {
      reloading = true
      if (version) {
        state.version = version
        state.update_check = { ...state.update_check, panel: cgSlotAfterUpgrade(state.update_check.panel, version) }
      }
      await new Promise((r) => setTimeout(r, ms))
      window.location.reload()
    }
    upgradeInProgress.value = true
    try {
      while (Date.now() < deadline) {
        await new Promise((r) => setTimeout(r, 2000))
        let d = null
        try {
          const res = await fetch('/api/upgrade-status', {
            headers: { Accept: 'application/json', 'X-Requested-With': 'fetch' },
            credentials: 'same-origin',
            cache: 'no-store',
          })
          if (res.status === 401) { reloading = true; window.location.reload(); return }
          if (!res.ok) { sawDown = true; continue }
          d = await res.json()
        } catch {
          sawDown = true
          if (stage !== 'restart') { stage = 'restart'; showToast(t('面板正在重启，请稍候……'), true) }
          continue
        }
        // Panel came back on a different version: the upgrade landed even if the
        // status file is missing/unreadable (older builds wrote invalid JSON).
        if (d && d.version && previousVersion && d.version !== previousVersion && d.state !== 'running') {
          d = { state: 'done', rc: 0, version: d.version }
        }
        if (d && d.state === 'running' && d.version && previousVersion && d.version !== previousVersion && sawDown) {
          d = { state: 'done', rc: 0, version: d.version }
        }
        if (!d || d.state !== 'done') continue
        if (Number(d.rc) === 0) {
          showToast(t('升级成功！当前版本 {v}，即将刷新页面', { v: d.version || '' }), true)
          await reloadSoon(800, d.version)
          return
        }
        showToast(t('升级失败：{msg}', { msg: d.tail || `exit ${d.rc}` }), false)
        if (d.version && previousVersion && d.version !== previousVersion) {
          await reloadSoon(2500, d.version)
        }
        return
      }
      showToast(t('升级超时，正在刷新页面……'), false)
      await reloadSoon(1500, '')
    } finally {
      if (!reloading) upgradeInProgress.value = false
    }
  }

  return {
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
    confirmUpdateCore,
    updateCoreDirect,
    toggleVersionPanel,
    checkUpdateAndPrompt,
    resumeUpgradeIfRunning,
    reloadPanelAfterUpgrade,
  }
}
