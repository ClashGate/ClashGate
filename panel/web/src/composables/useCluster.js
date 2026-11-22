// Panel state and actions for the cluster page and this server's name.
// Split out of usePanel.js: `p` carries the shared state and helpers usePanel creates first.
import { ref, reactive, computed } from 'vue'
import { t, lang } from '../i18n.js'
import { CG_NODE_NAME_MAX, nodeNameError, clusterUrlError } from './validation.js'

export function useCluster(p) {
  const { busyKey, openConfirmDialog, postAction, showToast, state } = p

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
    const res = await postAction(
      '/cluster/add',
      { url: clusterForm.url.trim(), password: clusterForm.password },
      'cluster-add'
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
      onConfirm: () => postAction('/cluster/remove', { id: m.id }, `cl-rm-${m.id}`),
    })
  }

  const listSep = computed(() => ({ zh: '、', fa: '، ' })[lang.value] || ', ')

  function syncCluster() {
    return postAction('/cluster/sync', {}, 'cluster-sync')
  }

  function leaveCluster() {
    openConfirmDialog({
      title: t('退出集群'),
      message: t('确定让本机退出集群？本机和所有成员之间的互联都会删除，其他成员之间的互联保持不变。'),
      confirmText: t('确认退出'),
      tone: 'rose',
      onConfirm: () => postAction('/cluster/leave', {}, 'cluster-leave'),
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
  }
}
