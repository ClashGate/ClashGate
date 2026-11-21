// Panel state and actions for the node converter page.
// Split out of usePanel.js: `p` carries the shared state and helpers usePanel creates first.
import { ref } from 'vue'
import { t } from '../i18n.js'
import { formatFetchError } from './api.js'

export function useConverter(p) {
  const { busyKey, showToast, state } = p

  // Readable config converter state
  const converterInput = ref('')
  const converterOutput = ref('')
  const converterError = ref('')

  function loadFileInto(ev, targetRef) {
    const f = ev.target.files && ev.target.files[0]
    if (!f) return
    const r = new FileReader()
    r.onload = () => {
      targetRef.value = r.result || ''
    }
    r.readAsText(f)
    ev.target.value = ''
  }

  function fillCurrentInboundsToConverter() {
    if (!state.all_proxies_yaml) {
      showToast(t('当前暂无入站节点可载入'), false)
      return
    }
    converterInput.value = state.all_proxies_yaml
    convertConfigFormat('readable')
  }

  async function convertConfigFormat(mode = 'readable') {
    converterError.value = ''
    const raw = (converterInput.value || '').trim()
    if (!raw) {
      converterError.value = t('请先粘贴需要转换的节点配置（支持单行 JSON / Flow 或多行 YAML）')
      return
    }
    if (busyKey.value) return
    busyKey.value = `convert-${mode}`
    try {
      const body = new URLSearchParams({ csrf: state.csrf, raw }).toString()
      const res = await fetch('/api/convert-readable', {
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
      if (res.status === 401) {
        window.location.href = '/login'
        return
      }
      const data = await res.json().catch(() => ({ ok: false, msg: `HTTP ${res.status}` }))
      if (!res.ok || !data.ok) {
        converterError.value = data.msg || t('配置解析失败，请检查格式是否正确')
        return
      }
      converterOutput.value = mode === 'single' ? data.single : data.readable
      showToast(t('已成功转换 {count} 个节点为{kind}', { count: data.count, kind: mode === 'single' ? t('单行配置') : t('多行易读 YAML') }), true)
    } catch (e) {
      converterError.value = formatFetchError(e)
    } finally {
      busyKey.value = ''
    }
  }

  return {
    converterInput,
    converterOutput,
    converterError,
    loadFileInto,
    fillCurrentInboundsToConverter,
    convertConfigFormat,
  }
}
