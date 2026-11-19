<script setup>
// Christmas skin decorations: hand-drawn inline SVG, purely decorative (aria-hidden, pointer-events: none).
defineProps({ kind: { type: String, default: 'scene' } })
// Deterministic snowflakes: left %, size px, fall seconds, delay seconds, drift px.
const FLAKES = [
  [3, 6, 14, 0, 18], [9, 4, 18, 6, -12], [15, 7, 16, 2, 22], [22, 5, 20, 9, -16], [28, 4, 15, 4, 14],
  [34, 6, 19, 11, -20], [41, 5, 17, 1, 16], [47, 7, 21, 7, -14], [53, 4, 16, 3, 20], [59, 6, 18, 10, -18],
  [65, 5, 15, 5, 12], [71, 7, 20, 0, -22], [77, 4, 17, 8, 18], [83, 6, 19, 2, -12], [89, 5, 16, 12, 16],
  [95, 6, 18, 6, -16], [12, 3, 22, 13, 10], [38, 3, 23, 15, -10], [62, 3, 21, 14, 12], [86, 3, 24, 16, -8],
]
</script>

<template>
  <div v-if="kind === 'snow'" class="cg-xmas-snow" aria-hidden="true">
    <span
      v-for="(f, i) in FLAKES"
      :key="i"
      :style="{ left: f[0] + '%', width: f[1] + 'px', height: f[1] + 'px', animationDuration: f[2] + 's', animationDelay: -f[3] + 's', '--drift': f[4] + 'px' }"
    ></span>
  </div>

  <!-- Santa hat that sits on the logo -->
  <svg v-else-if="kind === 'hat'" class="cg-xmas-hat" viewBox="0 0 44 36" aria-hidden="true" focusable="false">
    <path d="M6 27 C8 14 17 4 29 5 C35 5.5 39 10 40 17 L36 18 C34 13 31 11 28 12 C33 17 35 22 36 27 Z" fill="#e0413e" />
    <path d="M14 13 C18 8 23 6.5 28 7" fill="none" stroke="#f06a66" stroke-width="2.2" stroke-linecap="round" opacity=".8" />
    <circle cx="38.5" cy="19.5" r="4.6" fill="#ffffff" stroke="#e5e9ef" stroke-width="1" />
    <rect x="3" y="24.5" width="36" height="8.5" rx="4.25" fill="#ffffff" stroke="#e5e9ef" stroke-width="1" />
  </svg>

  <!-- Holly sprig (login card corner) -->
  <svg v-else-if="kind === 'holly'" class="cg-xmas-holly" viewBox="0 0 56 44" aria-hidden="true" focusable="false">
    <path d="M27 24 C21 16 13 14 4 16 C7 18 7 21 5 23 C9 23 11 25 10 28 C14 26 17 28 17 31 C20 28 24 27 27 24 Z" fill="#2a9a5a" />
    <path d="M27 24 C17 21 11 19 6 17.5" fill="none" stroke="#1d7a45" stroke-width="1.2" stroke-linecap="round" />
    <path d="M29 24 C35 15 43 12 52 13 C49 15.5 49.5 18.5 51.5 20.5 C47.5 21 45.5 23.5 46.5 26.5 C42.5 25 39.5 27 39.5 30 C36.5 27.5 32.5 27 29 24 Z" fill="#23864b" />
    <path d="M29 24 C38 19.5 44 16.5 49.5 14.5" fill="none" stroke="#17663a" stroke-width="1.2" stroke-linecap="round" />
    <circle cx="24" cy="28" r="4.2" fill="#e0413e" />
    <circle cx="31.5" cy="29" r="4.2" fill="#d23431" />
    <circle cx="27.5" cy="22.5" r="4.2" fill="#ef5350" />
    <circle cx="26.2" cy="21.2" r="1.2" fill="#ffffff" opacity=".75" />
    <circle cx="22.8" cy="26.8" r="1.1" fill="#ffffff" opacity=".65" />
  </svg>

  <!-- Winter scene: tree, snowman, gifts on a snowy hill -->
  <svg v-else class="cg-xmas-scene" viewBox="0 0 260 150" aria-hidden="true" focusable="false">
    <!-- hill -->
    <path d="M0 150 C6 131 24 122 60 119 C110 115 170 116 210 119 C240 121 254 131 260 150 Z" fill="#e3ebf4" />
    <path d="M2 150 C9 135 27 127 62 124.5 C112 121 170 122 208 124.5 C238 126.5 251 135 258 150 Z" fill="#ffffff" />

    <!-- Christmas tree -->
    <rect x="52" y="112" width="12" height="16" rx="2" fill="#9a6644" />
    <path d="M58 40 L86 80 H72 L94 108 H22 L44 80 H30 Z" fill="#23864b" stroke="#23864b" stroke-width="6" stroke-linejoin="round" />
    <path d="M58 40 L74 63 H64 L58 52 Z" fill="#2fa362" opacity=".8" />
    <path d="M33 80 Q45 86 58 82 Q71 78 83 80" fill="none" stroke="#ffffff" stroke-width="3" stroke-linecap="round" opacity=".85" />
    <path d="M26 106 Q42 112 58 106 Q74 100 90 106" fill="none" stroke="#ffffff" stroke-width="3" stroke-linecap="round" opacity=".85" />
    <path d="M58 26 l3.2 6.6 7.2 1 -5.2 5 1.2 7.2 -6.4 -3.4 -6.4 3.4 1.2 -7.2 -5.2 -5 7.2 -1 z" fill="#f5b82e" stroke="#e9a516" stroke-width="1" stroke-linejoin="round" />
    <circle cx="48" cy="70" r="3.6" fill="#e0413e" />
    <circle cx="66" cy="64" r="3.2" fill="#f5b82e" />
    <circle cx="70" cy="92" r="3.8" fill="#e0413e" />
    <circle cx="42" cy="97" r="3.2" fill="#f5b82e" />
    <circle cx="56" cy="88" r="3" fill="#ffffff" />
    <circle cx="80" cy="100" r="2.8" fill="#ffffff" />

    <!-- Snowman -->
    <g>
      <ellipse cx="156" cy="128" rx="26" ry="4" fill="#dfe7f0" />
      <circle cx="156" cy="106" r="22" fill="#ffffff" stroke="#d7e0ea" stroke-width="1.5" />
      <circle cx="156" cy="73" r="16" fill="#ffffff" stroke="#d7e0ea" stroke-width="1.5" />
      <circle cx="156" cy="47" r="13" fill="#ffffff" stroke="#d7e0ea" stroke-width="1.5" />
      <!-- arms -->
      <path d="M141 70 L120 58 M126 61.5 L121 54 M171 70 L191 60 M185 63 L191 55" fill="none" stroke="#8a5a3b" stroke-width="2.4" stroke-linecap="round" />
      <!-- scarf -->
      <path d="M143 58 Q156 64 169 58 L169 63 Q156 69 143 63 Z" fill="#e0413e" />
      <path d="M161 62 L165 78 L171 76 L166 61 Z" fill="#d23431" />
      <path d="M163 66 L168 65 M164.5 71 L169.5 70" stroke="#ffffff" stroke-width="1.4" stroke-linecap="round" opacity=".8" />
      <!-- hat -->
      <rect x="141" y="33" width="30" height="4.5" rx="2.2" fill="#2b3440" />
      <rect x="146" y="17" width="20" height="17" rx="2.5" fill="#2b3440" />
      <rect x="146" y="28" width="20" height="4" fill="#23864b" />
      <circle cx="162" cy="30" r="2.6" fill="#e0413e" />
      <!-- face -->
      <circle cx="151.5" cy="45" r="1.8" fill="#2b3440" />
      <circle cx="160.5" cy="45" r="1.8" fill="#2b3440" />
      <path d="M156 48.5 L166 51 L156 51.5 Z" fill="#f08a24" />
      <path d="M150.5 53 Q156 56.5 161.5 53" fill="none" stroke="#2b3440" stroke-width="1.5" stroke-linecap="round" />
      <circle cx="148" cy="50.5" r="2.2" fill="#ffb3b3" opacity=".7" />
      <circle cx="164" cy="50.5" r="2.2" fill="#ffb3b3" opacity=".7" />
      <!-- buttons -->
      <circle cx="156" cy="72" r="1.9" fill="#2b3440" />
      <circle cx="156" cy="80" r="1.9" fill="#2b3440" />
      <circle cx="156" cy="100" r="2" fill="#2b3440" />
    </g>

    <!-- Gifts -->
    <g>
      <rect x="196" y="98" width="34" height="29" rx="3" fill="#e0413e" />
      <rect x="194" y="92" width="38" height="9" rx="2.5" fill="#ef5350" />
      <rect x="210" y="92" width="6" height="35" fill="#23864b" />
      <path d="M213 92 C206 82 198 86 203 91 Z M213 92 C220 82 228 86 223 91 Z" fill="#2fa362" stroke="#23864b" stroke-width="1.2" stroke-linejoin="round" />
      <rect x="233" y="108" width="22" height="19" rx="2.5" fill="#2fa362" />
      <rect x="232" y="104" width="24" height="6.5" rx="2" fill="#37b06c" />
      <rect x="242" y="104" width="4.5" height="23" fill="#f5b82e" />
      <path d="M244 104 C239 97 234 100 238 103.5 Z M244 104 C249 97 254 100 250 103.5 Z" fill="#f5b82e" stroke="#e9a516" stroke-width="1" stroke-linejoin="round" />
      <rect x="182" y="113" width="15" height="14" rx="2" fill="#f5b82e" />
      <rect x="188" y="113" width="3.5" height="14" fill="#e0413e" />
    </g>

    <!-- sparkles -->
    <g fill="#9fc1e6">
      <circle cx="112" cy="30" r="2" />
      <circle cx="198" cy="40" r="1.6" />
      <circle cx="238" cy="70" r="2" />
      <circle cx="16" cy="54" r="1.6" />
      <circle cx="104" cy="72" r="1.4" />
    </g>
  </svg>
</template>
