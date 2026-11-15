// Shared panel HTTP helpers. postAction in usePanel.js wraps postForm with UI state.
import { t } from '../i18n.js'

export function formatFetchError(err) {
  const raw = String((err && err.message) || err || '')
  if (/NetworkError|Failed to fetch|Load failed|network/i.test(raw)) {
    return t('网络连接中断或服务正在重启，请稍后刷新页面查看状态')
  }
  return t('请求异常：{raw}', { raw })
}

export async function postForm(url, params, { csrf, signal } = {}) {
  const body = new URLSearchParams({ csrf, ...params }).toString()
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      'X-Requested-With': 'fetch',
      Accept: 'application/json',
    },
    body,
    credentials: 'same-origin',
    cache: 'no-store',
    signal,
  })
  if (res.status === 401) {
    window.location.href = '/login'
    return { res, data: null, text: '', unauthorized: true }
  }
  const text = await res.text()
  let data = null
  try {
    data = JSON.parse(text)
  } catch {
    data = { ok: res.ok, msg: text || `HTTP ${res.status}` }
  }
  return { res, data, text }
}

export async function getJson(url) {
  const res = await fetch(url, {
    headers: { Accept: 'application/json', 'X-Requested-With': 'fetch' },
    credentials: 'same-origin',
    cache: 'no-store',
  })
  if (res.status === 401) {
    window.location.href = '/login'
    return null
  }
  return res.json()
}
