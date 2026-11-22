// Panel state and actions for the server-side routing page.
// Split out of usePanel.js: `p` carries the shared state and helpers usePanel creates first.
import { ref, reactive, computed, nextTick } from 'vue'
import { t } from '../i18n.js'
import { validateClassicalRulesPaste, validateHttpUrl } from './validation.js'

export function useRouting(p) {
  const { busyKey, openConfirmDialog, postAction, showToast, state } = p

  const createRoutingForm = reactive({ name: '', rules_raw: '' })
  const importRoutingForm = reactive({ name: '', url: '' })

  const routingGroups = computed(() => {
    const g = state.routing && Array.isArray(state.routing.groups) ? state.routing.groups : []
    return g
  })

  function routingNameTaken(name, exceptId = '') {
    const n = String(name || '').trim()
    return routingGroups.value.some((g) => g && g.name === n && g.id !== exceptId)
  }

  async function createRoutingGroup() {
    const name = createRoutingForm.name.trim()
    if (!name) {
      showToast(t('请填写分流组名称'), false)
      return
    }
    if (routingNameTaken(name)) {
      showToast(t('分流组名称已存在：{name}', { name }), false)
      return
    }
    const check = validateClassicalRulesPaste(createRoutingForm.rules_raw)
    if (!check.ok) {
      showToast(check.msg, false)
      return
    }
    const res = await postAction(
      '/routing/add',
      { name, rules_raw: createRoutingForm.rules_raw },
      'routing-add',
    )
    if (res && res.ok) {
      createRoutingForm.name = ''
      createRoutingForm.rules_raw = ''
    }
  }

  async function importRoutingGroup() {
    const name = importRoutingForm.name.trim()
    const url = importRoutingForm.url.trim()
    if (!name) {
      showToast(t('请填写分流组名称'), false)
      return
    }
    if (routingNameTaken(name)) {
      showToast(t('分流组名称已存在：{name}', { name }), false)
      return
    }
    const urlCheck = validateHttpUrl(url)
    if (!urlCheck.ok) {
      showToast(urlCheck.msg, false)
      return
    }
    const res = await postAction('/routing/import', { name, url }, 'routing-import')
    if (res && res.ok) {
      importRoutingForm.name = ''
      importRoutingForm.url = ''
    }
  }

  function confirmDeleteRouting(g) {
    if (!g || !g.deletable) {
      showToast(t('该分流组不可删除'), false)
      return
    }
    openConfirmDialog({ tone: 'rose', confirmText: t('确认删除'),
      title: t('删除分流组'),
      message: t('确定删除分流组「{name}」？', { name: g.name }),
      onConfirm: () => postAction('/routing/delete', { id: g.id }, `routing-del-${g.id}`),
    })
  }

  async function renameRouting(g) {
    if (!g) return
    renameDialog.id = g.id
    renameDialog.oldName = g.name
    renameDialog.name = g.name
    renameDialog.show = true
    nextTick(() => { const el = document.getElementById('rename-input'); if (el) { el.focus(); el.select() } })
  }

  const renameDialog = reactive({ show: false, id: '', oldName: '', name: '' })
  function closeRenameDialog() { renameDialog.show = false }
  async function acceptRenameDialog() {
    const trimmed = String(renameDialog.name || '').trim()
    if (!trimmed) {
      showToast(t('请填写分流组名称'), false)
      return
    }
    if (routingNameTaken(trimmed, renameDialog.id)) {
      showToast(t('分流组名称已存在：{name}', { name: trimmed }), false)
      return
    }
    const id = renameDialog.id
    renameDialog.show = false
    if (trimmed === renameDialog.oldName) return
    await postAction('/routing/rename', { id, name: trimmed }, `routing-rename-${id}`)
  }

  const routingPanelOpen = ref('')
  const routingRuleDraft = reactive({})
  const routingProvForm = reactive({ provider: '', url: '' })

  function isLocalRoutingGroup(g) {
    return g && (g.kind === 'local' || (!g.kind && !(g.rule_providers || []).length))
  }

  function toggleRoutingPanel(g) {
    if (!g) return
    if (routingPanelOpen.value === g.id) {
      routingPanelOpen.value = ''
      return
    }
    routingPanelOpen.value = g.id
    if (isLocalRoutingGroup(g)) {
      const lines = Array.isArray(g.classical_rules) ? g.classical_rules : []
      routingRuleDraft[g.id] = lines.map((r) => `- ${r}`).join('\n')
    } else {
      routingProvForm.provider = ''
      routingProvForm.url = ''
    }
  }

  async function saveLocalRoutingRules(g) {
    if (!g) return
    const raw = routingRuleDraft[g.id] || ''
    const check = validateClassicalRulesPaste(raw)
    if (!check.ok) {
      showToast(check.msg, false)
      return
    }
    await postAction('/routing/rules', { id: g.id, rules_raw: raw }, `routing-rules-${g.id}`)
  }

  async function addRoutingProvider(g) {
    const provider = routingProvForm.provider.trim()
    const url = routingProvForm.url.trim()
    if (!provider) {
      showToast(t('请填写规则集名称（英文）'), false)
      return
    }
    if (!/^[A-Za-z0-9_.-]{1,64}$/.test(provider)) {
      showToast(t('规则集名称只能用英文字母、数字、- _ .'), false)
      return
    }
    const urlCheck = validateHttpUrl(url)
    if (!urlCheck.ok) {
      showToast(urlCheck.msg, false)
      return
    }
    const res = await postAction('/routing/provider/add', { id: g.id, provider, url }, 'routing-prov-add')
    if (res && res.ok) { routingProvForm.provider = ''; routingProvForm.url = '' }
  }

  function deleteRoutingProvider(g, p) {
    if (!g || !p) {
      showToast(t('规则集不存在'), false)
      return
    }
    openConfirmDialog({ tone: 'rose', confirmText: t('确认删除'),
      title: t('删除规则集'),
      message: t('确定删除规则集「{name}」？', { name: p.name }),
      onConfirm: () => postAction('/routing/provider/delete', { id: g.id, provider: p.name }, `routing-prov-del-${p.name}`),
    })
  }

  const routingDragIdx = ref(-1)
  const routingDragOver = ref(-1)

  function onRoutingDragStart(idx, ev) {
    routingDragIdx.value = idx
    try { ev.dataTransfer.effectAllowed = 'move'; ev.dataTransfer.setData('text/plain', String(idx)) } catch (_) {}
  }

  async function onRoutingDrop(idx) {
    const from = routingDragIdx.value
    routingDragIdx.value = -1
    routingDragOver.value = -1
    if (from < 0 || from === idx) return
    if (busyKey.value) return
    const before = routingGroups.value.slice()
    const groups = before.slice()
    const [moved] = groups.splice(from, 1)
    groups.splice(idx, 0, moved)
    if (state.routing && Array.isArray(state.routing.groups)) state.routing.groups = groups
    const res = await postAction('/routing/reorder', { order: JSON.stringify(groups.map((g) => g.id)) }, 'routing-reorder')
    if (!(res && res.ok) && !(res && res.state && res.state.routing) && state.routing) state.routing.groups = before
  }

  // Up / down buttons: the same reorder without dragging (touch screens, keyboard).
  function moveRoutingGroup(idx, delta) {
    const to = idx + delta
    if (to < 0 || to >= routingGroups.value.length) return
    routingDragIdx.value = idx
    return onRoutingDrop(to)
  }

  return {
    createRoutingForm,
    importRoutingForm,
    routingGroups,
    routingNameTaken,
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
    moveRoutingGroup,
  }
}
