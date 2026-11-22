// Panel state and actions for the cluster page and this server's name.
// Split out of usePanel.js: `p` carries the shared state and helpers usePanel creates first.
import { ref, reactive, computed } from 'vue'
import { t, lang } from '../i18n.js'
import { postForm } from './api.js'
import { CG_NODE_NAME_MAX, nodeNameError, clusterUrlError } from './validation.js'

export function useCluster(p) {
  const { applyServerState, busyKey, openConfirmDialog, postAction, showToast, state } = p

  // Cluster operations run on the server in the background. Only the first 添加到集群 shows a
  // blocking overlay with the current step (it waits for both cores); 检查 / 重试 / 移除 / 退出 run
  // quietly: their own button says so (clusterBusy), the rest of the panel stays usable, and the
  // result arrives as a toast.
  const clusterTask = reactive({ show: false, kind: '', stage: '', elapsed: 0 })
  const clusterBusy = ref('')

  async function fetchClusterTask() {
    const res = await fetch('/api/cluster-task-status', {
      headers: { Accept: 'application/json', 'X-Requested-With': 'fetch' },
      credentials: 'same-origin',
      cache: 'no-store',
    })
    if (res.status === 401) {
      window.location.href = '/login'
      return { gone: true }
    }
    return res.ok ? res.json() : null
  }

  // expectId: the task this page started (null when the start request failed and the id is unknown).
  // quiet (the automatic 检查 when the cluster page opens): no toasts, the list shows the result.
  async function pollClusterTask(expectId = null, quiet = false) {
    const toast = (msg, ok) => { if (!quiet) showToast(msg, ok) }
    const deadline = Date.now() + 15 * 60 * 1000
    while (Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, 1000))
      let d = null
      try {
        d = await fetchClusterTask()
      } catch {
        continue   // a dropped request: the task keeps running on the server
      }
      if (!d) continue
      if (d.gone) return null
      if (d.running) {
        if (expectId === null) expectId = d.id   // the start request was lost but the task did start
        clusterTask.stage = d.stage || ''
        clusterTask.elapsed = Number(d.elapsed || 0)
        continue
      }
      if (d.state) applyServerState(d.state)
      if (expectId === null || d.id !== expectId) {
        // Our start request never answered and nothing is running: do not show an older task's result.
        toast(t('网络连接中断或服务正在重启，请稍后刷新页面查看状态'), false)
        return null
      }
      if (d.done) toast(d.msg || (d.ok ? t('操作成功') : t('操作失败')), !!d.ok)
      return d
    }
    toast(t('集群操作还没有结束，请稍后刷新页面查看'), false)
    return null
  }

  async function runClusterTask(url, params, key, kind, { overlay = false, quiet = false } = {}) {
    if (clusterBusy.value || (overlay && busyKey.value)) {
      if (!quiet) showToast(t('上一个操作还在进行，请稍候'), false)
      return null
    }
    clusterBusy.value = key
    if (overlay) {
      busyKey.value = key
      Object.assign(clusterTask, { show: true, kind, stage: '', elapsed: 0 })
    }
    try {
      let data = null
      try {
        const r = await postForm(url, { ...params, async: '1' }, { csrf: state.csrf })
        if (r.unauthorized) return null
        data = r.data
      } catch {
        data = null   // the request may still have started: follow the task status
      }
      if (data && !data.running) {   // refused before starting (another operation, bad input)
        if (data.state) applyServerState(data.state)
        if (!quiet) showToast(data.msg || (data.ok ? t('操作成功') : t('操作失败')), !!data.ok, data.detail)
        return data
      }
      return await pollClusterTask(data ? data.id : null, quiet)
    } finally {
      clusterBusy.value = ''
      if (overlay) {
        clusterTask.show = false
        busyKey.value = ''
      }
    }
  }

  // After a page reload while an operation is still running: the overlay again for an add, the busy
  // button for the others.
  async function resumeClusterTaskIfRunning() {
    try {
      const d = await fetchClusterTask()
      if (!d || !d.running || clusterBusy.value || busyKey.value) return
      const overlay = d.kind === 'add'
      clusterBusy.value = ({ add: 'cluster-add', sync: 'cluster-sync', leave: 'cluster-leave' })[d.kind] || 'cluster-task'
      if (overlay) {
        busyKey.value = clusterBusy.value
        Object.assign(clusterTask, { show: true, kind: d.kind, stage: d.stage || '', elapsed: Number(d.elapsed || 0) })
      }
      try {
        await pollClusterTask(d.id)
      } finally {
        clusterBusy.value = ''
        if (overlay) {
          clusterTask.show = false
          busyKey.value = ''
        }
      }
    } catch {}
  }

  // node-name validators live in validation.js

  const nodeNameInput = ref(state.cluster.node_name)
  const nodeNameSaved = ref(state.cluster.node_name)
  const nodeNameLength = computed(() => Array.from(String(nodeNameInput.value || '').trim()).length)
  // Only the over-limit hint is shown while typing; other errors appear on save.
  const nodeNameOverLimit = computed(() => nodeNameLength.value > CG_NODE_NAME_MAX)
  const nodeNameHint = computed(() => (
    nodeNameOverLimit.value ? t('本机名称最多 {n} 个字符', { n: CG_NODE_NAME_MAX }) : ''
  ))

  async function saveNodeName() {
    if (busyKey.value) return
    if (nodeNameOverLimit.value) return
    const err = nodeNameError(nodeNameInput.value)
    if (err) {
      showToast(err, false)
      return
    }
    await postAction('/action/settings', { node_name: nodeNameInput.value.trim() }, 'save-node-name')
  }

  const clusterForm = reactive({ url: '', password: '' })
  const clusterTouched = reactive({ url: false, password: false })

  const clusterUrlErr = computed(() => clusterUrlError(clusterForm.url))
  const clusterPwErr = computed(() => (clusterForm.password ? '' : t('请填写对方面板密码')))

  async function submitAddCluster() {
    if (busyKey.value || clusterBusy.value) return
    clusterTouched.url = true
    clusterTouched.password = true
    const err = clusterUrlErr.value || clusterPwErr.value
    if (err) {
      showToast(err, false)
      return
    }
    const res = await runClusterTask(
      '/cluster/add',
      { url: clusterForm.url.trim(), password: clusterForm.password },
      'cluster-add',
      'add',
      { overlay: true }
    )
    if (res && res.ok) {
      clusterForm.url = ''
      clusterForm.password = ''
      clusterTouched.url = false
      clusterTouched.password = false
    } else {
      clusterForm.password = ''
    }
  }

  function removeClusterMember(m) {
    openConfirmDialog({
      title: t('移出集群'),
      message: t('确定把「{name}」移出集群？集群里所有面板都会删除和它的互联，它自己也会退出集群。', { name: m.name }),
      confirmText: t('确认移出'),
      tone: 'rose',
      onConfirm: () => runClusterTask('/cluster/remove', { id: m.id }, `cl-rm-${m.id}`, 'remove'),
    })
  }

  const listSep = computed(() => ({ zh: '、', fa: '، ' })[lang.value] || ', ')

  // 检查. Also with no members: another panel may have added this one since the page was loaded.
  function syncCluster() {
    return runClusterTask('/cluster/sync', {}, 'cluster-sync', 'sync')
  }

  // Opening the cluster page checks once by itself (quietly, the button shows 「检查中…」), at most
  // every 30 seconds and never while something else runs.
  let lastAutoCheck = 0
  function autoCheckCluster() {
    if (busyKey.value || clusterBusy.value || document.hidden) return null
    if (Date.now() - lastAutoCheck < 30000) return null
    lastAutoCheck = Date.now()
    return runClusterTask('/cluster/sync', {}, 'cluster-sync', 'sync', { quiet: true })
  }

  // 「重试」 on a member that failed (or whose links are incomplete).
  function retryClusterMember(m) {
    return runClusterTask('/cluster/retry', { id: m.id }, `cl-rt-${m.id}`, 'retry')
  }

  // Hide a 等待互联 entry; the next 检查 tries that panel again.
  function dismissPending(p) {
    return postAction('/cluster/dismiss', { id: p.id }, `cl-dm-${p.id}`)
  }

  function leaveCluster() {
    openConfirmDialog({
      title: t('退出集群'),
      message: t('确定让本机退出集群？本机和所有成员之间的互联都会删除，其他成员之间的互联保持不变。'),
      confirmText: t('确认退出'),
      tone: 'rose',
      onConfirm: () => runClusterTask('/cluster/leave', {}, 'cluster-leave', 'leave'),
    })
  }

  return {
    nodeNameInput,
    nodeNameSaved,
    nodeNameLength,
    nodeNameOverLimit,
    nodeNameHint,
    saveNodeName,
    clusterForm,
    clusterTouched,
    clusterUrlErr,
    clusterPwErr,
    submitAddCluster,
    removeClusterMember,
    listSep,
    syncCluster,
    leaveCluster,
    clusterTask,
    clusterBusy,
    resumeClusterTaskIfRunning,
    dismissPending,
    retryClusterMember,
    autoCheckCluster,
  }
}
