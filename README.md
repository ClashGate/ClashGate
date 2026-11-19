<h1 align="center">ClashGate</h1>

<p align="center"><b>中文</b> · <a href="README.en.md">English</a></p>

<p align="center">ClashGate · 采用 Mihomo 核心简单安全的代理服务端</p>

<p align="center">
  <img alt="Platform: Linux" src="https://img.shields.io/badge/platform-Ubuntu%20%7C%20Debian%20%7C%20Rocky%20%7C%20Alma%20%7C%20Fedora%20%7C%20CentOS-blue" />
  <img alt="Init: systemd" src="https://img.shields.io/badge/init-systemd-blue" />
  <img alt="Version: v1.22" src="https://img.shields.io/badge/version-v1.22-1d6fe0" />
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-green" /></a>
</p>

## 设计哲学

简单，安全，打通 Mihomo 生态的最后一公里。

## 能做什么

- **一条命令装好服务端**：在常见 Linux VPS 上一键部署 Mihomo 服务端，装完直接输出客户端可用的配置。
- **两种安装模式**：
  - 无证书模式：只要一台服务器，自动生成 VLESS Reality 节点，最快上手；
  - 自动证书模式：再准备一个域名，自动申请并续期 Let's Encrypt 证书，额外提供 HTTPS 管理面板和订阅链接。
- **三种证书方式**：端口模式（通过 80 端口验证）、Cloudflare DNS（不用开放 80 端口）、手动上传自己的证书，都能在面板里随时切换。
- **多种协议**：VLESS Reality、Shadowsocks、Hysteria2、Snell v6、AnyTLS、TUIC、TrustTunnel、ShadowQUIC、Mieru、Sudoku，在面板里点几下即可添加。
- **订阅链接**：Mihomo / Clash 系客户端直接导入，节点有变动时客户端更新订阅即可，不用手动拼配置。
- **服务端分流**：在面板中按规则把不同网站分到不同出口；高级用户也可以换成自己的服务端配置。
- **集群**：把多台 ClashGate 服务器连在一起，一个订阅链接同时包含所有服务器的节点。
- **省心维护**：面板一键检查更新，可开启自动更新；内核更新、证书续期都会自动处理，还有运行状态面板（Zashboard）。
- **多语言界面**：管理面板支持中文、English、Русский、فارسی，安装程序和命令行支持中文和 English。

## 系统要求

- 带 systemd 的 Linux（x86_64 / arm64 / armv7），需要 root 权限；
- 推荐 Debian 11+、Ubuntu 20.04+、Rocky / Alma 8+、Fedora；
- 自动证书模式（带管理面板）需要 Python 3.9 或更高版本：Rocky / Alma 8 会自动安装新版 Python；更老的系统（如 CentOS 7）只能使用无证书模式；
- 自动证书模式还需要一个解析到本服务器的域名。使用 Cloudflare 时请把这条记录设为灰云（DNS only）。

## 一键安装

```bash
curl -fsSL https://raw.githubusercontent.com/ClashGate/ClashGate/main/install.sh | bash
```

## 常用命令

直接执行 `clashgate` 打开菜单，或：

```text
clashgate [status | info | sub | reset-sub | passwd | reset-password | reset-secret | cert | restart | log | update | uninstall | install | help]
```

## 目录

都在 `/etc/clashgate/`：

- `config.yaml`：当前服务端配置
- `certs/`：`fullchain.pem` 与 `privkey.pem`
- `client/`：客户端订阅片段
- `panel/`：管理面板

## 致谢

- [Mihomo](https://github.com/MetaCubeX/mihomo) — 代理核心
- [acme.sh](https://github.com/acmesh-official/acme.sh) — 证书申请与部署
- [Zashboard](https://github.com/Zephyruso/zashboard) — 运行状态面板
- [Vue](https://github.com/vuejs/core) — 面板界面
- [Tailwind CSS](https://github.com/tailwindlabs/tailwindcss) — 样式
- [Lucide](https://github.com/lucide-icons/lucide) — 图标

## 许可

仅供网络与自动化技术学习研究，请遵守所在地法律。[MIT License](LICENSE)
