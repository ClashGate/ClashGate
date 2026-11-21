// ClashGate panel skins. 'default' is the standard blue look; the choice is kept in localStorage
// (per browser) and applied to <html data-theme> by an inline <head> script before first paint.
import { ref } from 'vue'

const KEY = 'clashgate_theme'
export const THEMES = ['default', 'christmas']

function detect() {
  try {
    const v = window.localStorage.getItem(KEY) || ''
    return THEMES.includes(v) ? v : 'default'
  } catch {
    return 'default'
  }
}

function apply(v) {
  const el = document.documentElement
  if (v === 'default') delete el.dataset.theme
  else el.dataset.theme = v
}

export const theme = ref(detect())
apply(theme.value)

export function setTheme(v) {
  theme.value = THEMES.includes(v) ? v : 'default'
  try {
    if (theme.value === 'default') window.localStorage.removeItem(KEY)
    else window.localStorage.setItem(KEY, theme.value)
  } catch {}
  apply(theme.value)
}
