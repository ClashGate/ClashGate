<h1 align="center">ClashGate</h1>

<p align="center"><b>中文</b> · <a href="README.en.md">English</a></p>

<p align="center">ClashGate · 采用 Mihomo 核心简单安全的代理服务端</p>

<p align="center">
  <img alt="Platform: Linux" src="https://img.shields.io/badge/platform-Ubuntu%20%7C%20Debian%20%7C%20Rocky%20%7C%20Alma%20%7C%20Fedora%20%7C%20CentOS-blue" />
  <img alt="Init: systemd" src="https://img.shields.io/badge/init-systemd-blue" />
  <img alt="Version: v1.06" src="https://img.shields.io/badge/version-v1.06-14614d" />
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-green" /></a>
</p>

## 设计哲学

简单，安全，打通 Mihomo 生态的最后一公里。

## 能做什么

- **一键部署代理服务端**：一条命令即可在常见 Linux VPS 上完成 Mihomo 服务端部署，开箱即用。
- **自带客户端订阅**：自动提供可直接导入 Mihomo / Clash 系客户端的配置，无需手动拼接。
- **支持多种协议**：VLESS Reality、Shadowsocks、Hysteria2、Snell、AnyTLS、TUIC、TrustTunnel、ShadowQUIC、Mieru、Sudoku 一键添加。
- **服务端支持分流**：需要自定义出站分流，可替换为自己的 Mihomo 服务端配置。

## 一键安装

支持带 systemd 的常见 Linux（Ubuntu / Debian / Rocky / Alma / Fedora / CentOS，需要 root）：

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
