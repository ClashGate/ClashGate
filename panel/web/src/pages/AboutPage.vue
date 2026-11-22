<script setup>
// 1.44: 关于 — version, the latest important changes (short), and the projects ClashGate is built on.
import { t } from '../i18n.js'
import { usePanel } from '../composables/usePanel.js'
import CgIcon from '../CgIcon.vue'

const { state, selectTab } = usePanel()

// Newest first; one line each. The current version is marked.
const CHANGELOG = [
  { v: '1.45', desc: '新增 VLESS Encryption 节点（替代 SS 的裸奔协议），自定义服务端下可添加 VLESS XHTTP；Hysteria2 默认不混淆，TUIC、ShadowQUIC 关闭 0-RTT，HTTP / SOCKS5 有证书时默认开启 TLS' },
  { v: '1.44', desc: '自定义服务端下可以自己填写节点的密码、加密方式等参数；检查集群时也能立即退出；新的加载动画和「关于」页面' },
  { v: '1.43', desc: '改配置改用热重载，不再频繁重启内核；更新时内核下载失败也不影响面板更新' },
  { v: '1.42', desc: '集群每台服务器只开一个入站，成员再多也只占一个端口' },
  { v: '1.41', desc: '服务端配置统一为多行 YAML，更易读；退出集群立即完成' },
  { v: '1.40', desc: '集群先交换节点再统一生效；连接失败的成员可以重试，等待互联的记录可以忽略' },
  { v: '1.39', desc: '安装时自动选择适合 CPU 的内核版本；集群操作显示进度' },
]

const CREDITS = [
  {
    name: 'mihomo',
    mark: 'M',
    repo: 'MetaCubeX/mihomo',
    url: 'https://github.com/MetaCubeX/mihomo',
    desc: 'ClashGate 的代理内核：入站、出站、分流和集群互联都由它运行',
  },
  {
    name: 'Xray',
    mark: 'X',
    repo: 'XTLS/Xray-core',
    url: 'https://github.com/XTLS/Xray-core',
    desc: 'VLESS、Reality 与 XTLS Vision 等协议的开创者',
  },
]
</script>

<template>
<div id="about-page" class="cg-about space-y-4">
  <section class="cg-about-hero cg-surface rounded-2xl p-6 sm:p-8">
    <div class="flex items-center gap-4 sm:gap-5">
      <img src="/assets/logo.png" alt="" class="cg-about-logo" />
      <div class="min-w-0">
        <h2 class="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">ClashGate</h2>
        <p class="text-sm text-slate-600 mt-1">{{ t('面向新手的一键 Mihomo 代理服务端') }}</p>
        <div class="flex flex-wrap items-center gap-2 mt-3">
          <span class="cg-about-pill is-main" dir="ltr">v{{ state.version }}</span>
          <span v-if="state.mihomo_version" class="cg-about-pill" dir="ltr">mihomo {{ state.mihomo_version }}</span>
        </div>
      </div>
    </div>
    <button type="button" class="cg-about-back" @click="selectTab('settings')">
      <CgIcon name="chevron" :size="14" class="rotate-180 rtl:rotate-0" />{{ t('返回设置') }}
    </button>
  </section>

  <div class="grid grid-cols-1 lg:grid-cols-5 gap-4 items-start">
    <section class="cg-surface rounded-2xl p-5 sm:p-6 lg:col-span-3">
      <h3 class="text-base font-bold text-slate-900 tracking-tight">{{ t('更新日志') }}</h3>
      <p class="text-xs text-slate-500 mt-1">{{ t('最近的重要更新') }}</p>
      <ol class="cg-timeline mt-5">
        <li v-for="(c, i) in CHANGELOG" :key="c.v" class="cg-timeline-item" :class="{ 'is-current': c.v === state.version || (i === 0 && !CHANGELOG.some((x) => x.v === state.version)) }">
          <span class="cg-timeline-dot" aria-hidden="true"></span>
          <div class="flex items-center gap-2">
            <span class="cg-timeline-ver" dir="ltr">v{{ c.v }}</span>
            <span v-if="c.v === state.version" class="cg-about-tag">{{ t('当前版本') }}</span>
          </div>
          <p class="text-sm text-slate-700 leading-relaxed mt-1">{{ t(c.desc) }}</p>
        </li>
      </ol>
    </section>

    <section class="cg-surface rounded-2xl p-5 sm:p-6 lg:col-span-2">
      <h3 class="text-base font-bold text-slate-900 tracking-tight">{{ t('鸣谢') }}</h3>
      <p class="text-xs text-slate-500 mt-1">{{ t('ClashGate 建立在这些开源项目之上') }}</p>
      <div class="mt-5 space-y-3">
        <a
          v-for="p in CREDITS"
          :key="p.name"
          :href="p.url"
          target="_blank"
          rel="noopener noreferrer"
          class="cg-credit"
        >
          <span class="cg-credit-mark" aria-hidden="true">{{ p.mark }}</span>
          <span class="min-w-0 flex-1">
            <span class="flex items-center gap-1.5">
              <span class="text-sm font-bold text-slate-900">{{ p.name }}</span>
              <CgIcon name="external" :size="13" class="cg-credit-go" />
            </span>
            <span class="block text-xs text-slate-500 font-mono mt-0.5" dir="ltr">github.com/{{ p.repo }}</span>
            <span class="block text-xs text-slate-600 leading-relaxed mt-1.5">{{ t(p.desc) }}</span>
          </span>
        </a>
      </div>
    </section>
  </div>
</div>
</template>
