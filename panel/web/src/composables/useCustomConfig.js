// Panel state and actions for the custom server config page.
// Split out of usePanel.js: `p` carries the shared state and helpers usePanel creates first.
import { t } from '../i18n.js'
import { fixCertPaths } from './validation.js'

export function useCustomConfig(p) {
  const { activeTab, customConfigText, openConfirmDialog, postAction, selectTab, showToast } = p

  // cert-path helpers live in validation.js
  // autoFix: the server rewrites the paths (and reports how many); `shown` is what the
  // editor keeps if the save fails (a failed save returns the old server state).
  async function saveCustomConfig(text, autoFix, shown = text) {
    customConfigText.value = shown
    const res = await postAction(
      '/config/custom',
      { custom_config_raw: text, auto_fix_certs: autoFix ? '1' : '0' },
      'save-custom'
    )
    if (!res || !res.ok) customConfigText.value = shown
  }

  async function submitCustomConfig() {
    const raw = customConfigText.value || ''
    if (!raw.trim()) {
      showToast(t('请先粘贴完整的服务端配置'), false)
      return
    }
    const fixed = fixCertPaths(raw)
    if (fixed.changed > 0) {
      openConfirmDialog({
        title: t('自动配置证书路径？'),
        message: t('检测到 {n} 处证书路径不是本项目的证书路径（或是相对路径）。项目目录之外的证书，内核可能无法读取，建议自动配置为本项目证书（/etc/clashgate/certs/）。', { n: fixed.changed }),
        confirmText: t('自动配置并保存'),
        cancelText: t('保持我的配置'),
        tone: 'emerald',
        onConfirm: () => saveCustomConfig(raw, true, fixed.text),
        onCancel: () => saveCustomConfig(raw, false),
      })
      return
    }
    await saveCustomConfig(raw, false)
  }

  function resetTemplateConfig() {
    openConfirmDialog({
      title: t('恢复默认服务端模板'),
      message: t('服务端会换回内置模板，现有节点换成一个新的 VlessReality 节点，客户端需要更新订阅。完成后自动关闭自定义服务端，你的自定义配置会保留，重新开启后可以载入。'),
      confirmText: t('恢复并关闭自定义服务端'),
      tone: 'rose',
      onConfirm: async () => {
        const res = await postAction('/config/reset-template', {}, 'reset-template')
        if (res && res.ok && activeTab.value === 'advanced') selectTab('inbounds')   // the page is off now
      },
    })
  }

  return {
    saveCustomConfig,
    submitCustomConfig,
    resetTemplateConfig,
  }
}
