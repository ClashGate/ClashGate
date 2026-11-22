// Panel state and actions for the cluster page and this server's name.
// Split out of usePanel.js: `p` carries the shared state and helpers usePanel creates first.
import { ref, reactive, computed } from 'vue'
import { t, lang } from '../i18n.js'
import { postForm } from './api.js'
import { CG_NODE_NAME_MAX, nodeNameError, clusterUrlError } from './validation.js'

export function useCluster(p) {
  const { applyServerState, busyKey, openConfirmDialog, postAction, showToast, state } = p

  // Cluster operations run on the server in the background (adding a panel waits for both cores to
  // reload). While one runs, a full-page overlay shows the current step and blocks other clicks.
  const clusterTask = reactive({ show: false, kind: '', stage: '', elapsed: 0 })

  function taskTitle(kind) {
    if (kind === 'add') return t('正在添加到集群')
    if (kind === 'sync') return t('正在检查集群')
    if (kind === 'remove') return t('正在移出集群')
    if (kind === 'leave') return t('正在退出集群')
    return t('正在处理集群')
  }

  // expectId: the task this page started (null when the start request failed and the id is unknown).
  async function pollClusterTask(expectId = null) {
    const deadline = Date.now() + 15 * 60 * 1000
    while (Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, 1000))
      let d = null
      try {
        const res = await fetch('/api/cluster-task-status', {
          headers: { Accept: 'application/json', 'X-Requested-With': 'fetch' },
          credentials: 'same-origin',
          cache: 'no-store',
        })
        if (res.status === 401) {
          window.location.href = '/login'
          return null
        }
        if (!res.ok) continue
        d = await res.json()
      } catch {
        continue   // a dropped request: the task keeps running on the server
      }
      if (d.running) {
        if (expectId === null) expectId = d.id   // the start request was lost but the task did start
        if (d.kind) clusterTask.kind = d.kind
        clusterTask.stage = d.stage || ''
        clusterTask.elapsed = Number(d.elapsed || 0)
        continue
      }
      if (d.state) applyServerState(d.state)
      if (expectId === null || d.id !== expectId) {
        // Our start request never answered and nothing is running: do not show an older task's result.
        showToast(t('网络连接中断或服务正在重启，请稍后刷新页面查看状态'), false)
        return null
      }
      if (d.done) showToast(d.msg || (d.ok ? t('操作成功') : t('操作失败')), !!d.ok)
      return d
    }
    showToast(t('集群操作还没有结束，请稍后刷新页面查看'), false)
    return null
  }

  async function runClusterTask(url, params, key, kind) {
    if (busyKey.value) {
      showToast(t('上一个操作还在进行，请稍候'), false)
      return null
    }
    busyKey.value = key
    Object.assign(clusterTask, { show: true, kind, stage: '', elapsed: 0 })
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
        showToast(data.msg || (data.ok ? t('操作成功') : t('操作失败')), !!data.ok, data.detail)
        return data
      }
      return await pollClusterTask(data ? data.id : null)
    } finally {
      clusterTask.show = false
      busyKey.value = ''
    }
  }

  // After a reload while an operation is still running, show it again.
  async function resumeClusterTaskIfRunning() {
    try {
      const res = await fetch('/api/cluster-task-status', {
        headers: { Accept: 'application/json', 'X-Requested-With': 'fetch' },
        credentials: 'same-origin',
        cache: 'no-store',
      })
      if (!res.ok) return
      const d = await res.json()
      if (!d || !d.running || busyKey.value) return
      busyKey.value = 'cluster-task'
      Object.assign(clusterTask, { show: true, kind: d.kind || '', stage: d.stage || '', elapsed: Number(d.elapsed || 0) })
      try {
        await pollClusterTask(d.id)
      } finally {
        clusterTask.show = false
        busyKey.value = ''
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
    if (busyKey.value) return
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
      'add'
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

  function syncCluster() {
    return runClusterTask('/cluster/sync', {}, 'cluster-sync', 'sync')
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
    taskTitle,
    resumeClusterTaskIfRunning,
  }
}
