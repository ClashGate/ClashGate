<script setup>
import {
  House,
  ArrowUpRight,
  ArrowLeftRight,
  ShieldCheck,
  Server,
  Settings,
  LogOut,
  RefreshCw,
  ArrowUp,
  Languages,
  Cloud,
  Lock,
  Check,
  Waypoints,
  Network,
  ChevronRight,
  ChevronUp,
  ChevronDown,
  Eye,
  EyeOff,
  ExternalLink,
  Info,
} from 'lucide-vue-next'

const icons = {
  house: House,
  outbound: ArrowUpRight,
  convert: ArrowLeftRight,
  shield: ShieldCheck,
  server: Server,
  settings: Settings,
  logout: LogOut,
  refresh: RefreshCw,
  up: ArrowUp,
  lang: Languages,
  cloud: Cloud,
  lock: Lock,
  check: Check,
  routing: Waypoints,
  cluster: Network,
  chevron: ChevronRight,
  chevUp: ChevronUp,
  chevDown: ChevronDown,
  eye: Eye,
  eyeOff: EyeOff,
  external: ExternalLink,
  info: Info,
}

defineProps({
  name: { type: String, required: true },
  size: { type: Number, default: 16 },
})
</script>

<template>
  <component :is="icons[name]" :size="size" :stroke-width="1.75" class="shrink-0" aria-hidden="true" />
</template>
