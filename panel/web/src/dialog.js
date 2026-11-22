// v-cg-dialog: on the panel of a modal (mounted when it opens, unmounted when it closes).
// Moves focus into the dialog ([data-autofocus] first, else the first control), keeps Tab inside it,
// and gives focus back to the control that opened it.
const FOCUSABLE = 'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

function focusables(el) {
  return Array.from(el.querySelectorAll(FOCUSABLE)).filter((x) => x.offsetParent !== null || x === document.activeElement)
}

export const vCgDialog = {
  mounted(el) {
    el.__cgPrev = document.activeElement
    const first = el.querySelector('[data-autofocus]') || focusables(el)[0] || el
    try { first.focus({ preventScroll: true }) } catch { first.focus() }
    el.__cgTrap = (ev) => {
      if (ev.key !== 'Tab') return
      const list = focusables(el)
      if (!list.length) { ev.preventDefault(); return }
      const head = list[0]
      const tail = list[list.length - 1]
      if (ev.shiftKey && (document.activeElement === head || !el.contains(document.activeElement))) {
        ev.preventDefault(); tail.focus()
      } else if (!ev.shiftKey && document.activeElement === tail) {
        ev.preventDefault(); head.focus()
      }
    }
    el.addEventListener('keydown', el.__cgTrap)
  },
  unmounted(el) {
    el.removeEventListener('keydown', el.__cgTrap)
    const prev = el.__cgPrev
    el.__cgPrev = null
    if (prev && typeof prev.focus === 'function' && document.contains(prev)) {
      try { prev.focus({ preventScroll: true }) } catch { prev.focus() }
    }
  },
}
