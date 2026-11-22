<script setup>
// 1.44: one spinner for every busy state (cluster overlay, buttons). An arc that grows and shrinks
// while it turns; currentColor, so it follows the text colour (and the skins). Reduced motion: the
// global rule stops it on a still arc, the button text still says what runs.
defineProps({
  size: { type: Number, default: 16 },
  light: { type: Boolean, default: false },     // on a primary (blue) button
  inherit: { type: Boolean, default: false },   // the button's own text colour (e.g. a red 移除)
})
</script>

<template>
  <svg
    class="cg-spinner"
    :class="{ 'is-light': light, 'is-inherit': inherit }"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    aria-hidden="true"
  >
    <circle class="cg-spinner-track" cx="12" cy="12" r="9.5" stroke-width="2.5" />
    <circle class="cg-spinner-arc" cx="12" cy="12" r="9.5" stroke-width="2.5" stroke-linecap="round" />
  </svg>
</template>
