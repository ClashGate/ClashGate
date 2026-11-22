// Panel state and actions for the settings page (password, custom server, auto update, channel).
// Split out of usePanel.js: `p` carries the shared state and helpers usePanel creates first.
import { ref, reactive } from 'vue'
import { t } from '../i18n.js'

export function useSettings(p) {
  const { activeTab, busyKey, openConfirmDialog, postAction, selectTab, showToast, state } = p

  // Change Password Modal state
  const showPasswordModal = ref(false)
  const passwordForm = reactive({
    current_password: '',
    new_password: '',
    confirm_password: '',
  })

  function openPasswordModal() {
    passwordForm.current_password = ''
    passwordForm.new_password = ''
    passwordForm.confirm_password = ''
    showPasswordModal.value = true
  }

  function closePasswordModal() {
    showPasswordModal.value = false
    passwordForm.current_password = ''
    passwordForm.new_password = ''
    passwordForm.confirm_password = ''
  }

  async function submitChangePassword() {
    if (busyKey.value) return
    if (!passwordForm.current_password) {
      showToast(t('请输入当前密码'), false)
      return
    }
    if (!passwordForm.new_password || passwordForm.new_password.length < 8) {
      showToast(t('新密码长度至少 8 位'), false)
      return
    }
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      showToast(t('两次输入的新密码不一致'), false)
      return
    }
    const res = await postAction(
      '/action/change-password',
      {
        current_password: passwordForm.current_password,
        new_password: passwordForm.new_password,
        confirm_password: passwordForm.confirm_password,
      },
      '/action/change-password'
    )
    if (res && res.ok) {
      closePasswordModal()
    }
  }

  async function toggleCustomServer() {
    const next = !state.custom_server_enabled
    if (!next && state.custom_config_mode) {
      openConfirmDialog({
        title: t('关闭自定义服务端'),
        message: t('关闭后，服务端将切换回面板生成的默认配置（默认服务端模板）并立即应用。你的自定义配置会保留在服务器上，重新开启后可一键恢复。'),
        confirmText: t('关闭并切换'),
        tone: 'amber',
        onConfirm: () => applyCustomServer(false),
      })
      return
    }
    await applyCustomServer(next)
  }

  async function applyCustomServer(next) {
    const res = await postAction(
      '/action/settings',
      { custom_server_enabled: next ? '1' : '0' },
      '/action/settings'
    )
    if (res && res.ok && !next && activeTab.value === 'advanced') selectTab('inbounds')
    if (res && res.ok && next && (activeTab.value === 'routing' || activeTab.value === 'cluster')) selectTab('inbounds')
  }

  async function toggleAutoUpdate() {
    const next = !state.auto_update
    await postAction(
      '/action/settings',
      { auto_update: next ? '1' : '0' },
      '/action/settings'
    )
  }

  function setUpdateChannel(channel) {
    const next = channel === 'test' ? 'test' : 'stable'
    if (next === 'test' && state.update_channel !== 'test') {
      openConfirmDialog({
        title: t('切换到测试通道'),
        message: t('测试版可能不稳定，可能出现功能异常或兼容性问题。切换后将立即更新到测试通道最新版本，确定切换？'),
        confirmText: t('确认切换'),
        tone: 'amber',
        onConfirm: () => applyUpdateChannel(next),
      })
      return
    }
    if (next === 'stable' && state.update_channel !== 'stable') {
      openConfirmDialog({
        title: t('切换到正式通道'),
        message: t('切换到正式通道并立即更新到正式版最新版本，确定切换？'),
        confirmText: t('确认切换'),
        tone: 'amber',
        onConfirm: () => applyUpdateChannel(next),
      })
      return
    }
    return applyUpdateChannel(next)
  }

  async function applyUpdateChannel(next) {
    const prev = state.update_channel
    // Always POST so legacy Beat installs migrate env to ClashGate/ClashGate@branch even if UI already shows 测试.
    const res = await postAction(
      '/action/settings',
      { update_channel: next },
      '/action/settings'
    )
    if (res && res.ok) {
      state.update_channel = next
      state.update_channel_label = next === 'test' ? t('测试') : t('正式')
      // Every real channel switch pulls that channel's latest build right away.
      if (prev !== next) {
        showToast(t('已切换通道，正在更新到该通道最新版本……'), true)
        await postAction('/action/upgrade-self', {}, '/action/upgrade-self')
      }
    }
  }

  return {
    showPasswordModal,
    passwordForm,
    openPasswordModal,
    closePasswordModal,
    submitChangePassword,
    toggleCustomServer,
    applyCustomServer,
    toggleAutoUpdate,
    setUpdateChannel,
    applyUpdateChannel,
  }
}
