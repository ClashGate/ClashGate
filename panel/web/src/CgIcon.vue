<script setup>
import {
  House,
  ArrowUpRight,
  ArrowLeftRight,
  ShieldCheck,
  Server,
  Settings,
  KeyRound,
  LogOut,
  RefreshCw,
  ArrowUp,
  Languages,
  Cloud,
  Lock,
  Check,
  CircleAlert,
} from 'lucide-vue-next'

const icons = {
  house: House,
  outbound: ArrowUpRight,
  convert: ArrowLeftRight,
  shield: ShieldCheck,
  server: Server,
  settings: Settings,
  key: KeyRound,
  logout: LogOut,
  refresh: RefreshCw,
  up: ArrowUp,
  lang: Languages,
  cloud: Cloud,
  lock: Lock,
  check: Check,
  alert: CircleAlert,
}

defineProps({
  name: { type: String, required: true },
  size: { type: Number, default: 16 },
})
</script>

<template>
  <component :is="icons[name]" :size="size" :stroke-width="1.75" class="shrink-0" aria-hidden="true" />
</template>
