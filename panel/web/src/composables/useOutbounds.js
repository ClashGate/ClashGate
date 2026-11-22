// Panel state and actions for the server outbounds page (proxies, subscriptions, MASQUE).
// Split out of usePanel.js: `p` carries the shared state and helpers usePanel creates first.
import { ref, reactive } from 'vue'
import { t } from '../i18n.js'

export function useOutbounds(p) {
  const { openConfirmDialog, postAction, showToast, state } = p

  const providerForm = reactive({
    sub_url: '',
    provider_name: '',
  })

  const proxiesRaw = ref('')

  async function submitAddProvider() {
    const subUrl = providerForm.sub_url.trim()
    if (!subUrl) {
      showToast(t('请填写订阅链接'), false)
      return
    }
    if (!/^https?:\/\/\S+$/i.test(subUrl)) {
      showToast(t('订阅链接必须以 http(s):// 开头'), false)
      return
    }
    const provName = providerForm.provider_name.trim()
    if (provName && !/^[A-Za-z0-9._-]{1,48}$/.test(provName)) {
      showToast(t('订阅源名称仅限 1-48 位字母、数字及 . _ -'), false)
      return
    }
    if (provName && state.providers.some((p) => p && p.name === provName)) {
      showToast(t('订阅源「{name}」已存在，请换一个名称或先删除原订阅源', { name: provName }), false)
      return
    }
    const res = await postAction(
      '/providers/add',
      {
        sub_url: subUrl,
        provider_name: provName,
      },
      'add-provider'
    )
    if (res && res.ok) {
      providerForm.sub_url = ''
      providerForm.provider_name = ''
    }
  }

  function deleteProvider(name) {
    openConfirmDialog({
      title: t('删除订阅源'),
      message: t('确定删除订阅源「{name}」？', { name }),
      confirmText: t('确认删除'),
      tone: 'rose',
      onConfirm: () => postAction('/providers/delete', { name }, `del-prov-${name}`),
    })
  }

  async function submitAddProxies() {
    if (!proxiesRaw.value.trim()) {
      showToast(t('请先粘贴节点配置'), false)
      return
    }
    const res = await postAction('/proxies/add', { proxies_raw: proxiesRaw.value }, 'add-proxies')
    if (res && res.ok) {
      proxiesRaw.value = ''
    }
  }

  function deleteProxy(name) {
    openConfirmDialog({
      title: t('删除服务端出站'),
      message: t('确定删除服务端出站「{name}」？', { name }),
      confirmText: t('确认删除'),
      tone: 'rose',
      onConfirm: () => postAction('/proxies/delete', { name }, `del-proxy-${name}`),
    })
  }

  function masqueNodeName(name) {
    const n = String(name || 'Cloudflare-MASQUE').trim()
    return n.startsWith('⛅️') ? n : `⛅️ ${n}`
  }

  function masqueYamlNamed(yaml, name) {
    const raw = String(yaml || '').trim().replace(/^-+\s*/, '')
    try {
      const obj = JSON.parse(raw)
      obj.name = name
      return '- ' + JSON.stringify(obj)
    } catch {
      return yaml
    }
  }

  async function addMasqueOutbound() {
    if (!state.masque.yaml) return
    const name = masqueNodeName(state.masque.name)
    if (state.proxies.some((p) => p && (p.name === name || p.name === String(state.masque.name || '').trim()))) {
      showToast(t('请勿重复加入'), false)
      return
    }
    await postAction('/proxies/add', { proxies_raw: masqueYamlNamed(state.masque.yaml, name) }, 'add-masque')
  }

  async function retryMasque() {
    const res = await postAction('/action/masque-register', {}, '/action/masque-register')
    if (res && res.ok && !(res.state && res.state.masque)) state.masque = { ...state.masque, status: 'pending', error: '' }
  }

  return {
    providerForm,
    proxiesRaw,
    submitAddProvider,
    deleteProvider,
    submitAddProxies,
    deleteProxy,
    masqueNodeName,
    masqueYamlNamed,
    addMasqueOutbound,
    retryMasque,
  }
}
