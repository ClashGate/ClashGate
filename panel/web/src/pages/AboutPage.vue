<script setup>
// 1.44: 关于 — version, the latest important changes (short), and the projects ClashGate is built on.
import { t } from '../i18n.js'
import { usePanel } from '../composables/usePanel.js'
import CgIcon from '../CgIcon.vue'

const { state, selectTab } = usePanel()

// Newest first; one line each. The current version is marked.
const CHANGELOG = [
  { v: '1.49', desc: '集群成员节点统一命名为「名称|Cluster」：退出或被移出集群时两边的节点都会删干净，成员改名时自定义配置里的代理组和规则跟着改，后台每小时核对一次；修复多处稳定性问题' },
  { v: '1.48', desc: '不再使用临时证书：域名解析不对或证书申请失败时直接停止安装并说明原因，修好后重新运行安装命令即可' },
  { v: '1.47', desc: '复制还没生效的节点时会提示先应用配置；默认模式和自定义模式的配置分开保存、互不影响；可以只更新 Cloudflare API Token，证书申请失败时显示原因；证书改为每天检查' },
  { v: '1.46', desc: '新增「玻璃」皮肤；按钮统一样式并显示加载动画，复制后显示对勾；添加节点卡片在自定义服务端下也不再跳动' },
  { v: '1.45', desc: '新增 VLESS Encryption 节点（替代 SS 的裸奔协议），自定义服务端下可添加 VLESS XHTTP；Hysteria2 默认不混淆，TUIC、ShadowQUIC 关闭 0-RTT，HTTP / SOCKS5 有证书时默认开启 TLS' },
  { v: '1.44', desc: '自定义服务端下可以自己填写节点的密码、加密方式等参数；检查集群时也能立即退出；新的加载动画和「关于」页面' },
  { v: '1.43', desc: '改配置改用热重载，不再频繁重启内核；更新时内核下载失败也不影响面板更新' },
  { v: '1.42', desc: '集群每台服务器只开一个入站，成员再多也只占一个端口' },
]

// Bundled under /assets: the page's CSP only loads images from this panel.
const REPO_URL = 'https://github.com/ClashGate/ClashGate'

const CREDITS = [
  {
    name: 'mihomo',
    logo: '/assets/mihomo.png',   // MetaCubeX's own logo (its GitHub organisation picture)
    repo: 'MetaCubeX/mihomo',
    url: 'https://github.com/MetaCubeX/mihomo',
    desc: 'ClashGate 的代理内核：入站、出站、分流和集群互联都由它运行',
  },
  {
    name: 'Xray',
    logo: '/assets/xray.png',     // XTLS's own logo (its GitHub organisation picture)
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
          <!-- 1.46: the project's own repository -->
          <a id="about-github" :href="REPO_URL" target="_blank" rel="noopener noreferrer" class="cg-about-pill is-link" dir="ltr">
            <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor" aria-hidden="true"><path d="M8 0c4.42 0 8 3.58 8 8a8.013 8.013 0 0 1-5.45 7.59c-.4.08-.55-.17-.55-.38 0-.27.01-1.13.01-2.2 0-.75-.25-1.23-.54-1.48 1.78-.2 3.65-.88 3.65-3.95 0-.88-.31-1.59-.82-2.15.08-.2.36-1.02-.08-2.12 0 0-.67-.22-2.2.82-.64-.18-1.32-.27-2-.27-.68 0-1.36.09-2 .27-1.53-1.03-2.2-.82-2.2-.82-.44 1.1-.16 1.92-.08 2.12-.51.56-.82 1.28-.82 2.15 0 3.06 1.86 3.75 3.64 3.95-.23.2-.44.55-.51 1.07-.46.21-1.61.55-2.33-.66-.15-.24-.6-.83-1.23-.82-.67.01-.27.38.01.53.34.19.73.9.82 1.13.16.45.68 1.31 2.69.94 0 .67.01 1.3.01 1.49 0 .21-.15.45-.55.38A7.995 7.995 0 0 1 0 8c0-4.42 3.58-8 8-8Z" /></svg>
            GitHub
            <CgIcon name="external" :size="12" class="cg-credit-go" />
          </a>
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
          <img :src="p.logo" alt="" width="40" height="40" loading="lazy" class="cg-credit-mark" />
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
