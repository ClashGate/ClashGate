<h1 align="center">ClashGate</h1>

<p align="center"><b>中文</b> · <a href="README.en.md">English</a></p>

<p align="center">ClashGate · 采用 Mihomo 核心简单安全的代理服务端</p>

<p align="center">
  <img alt="Platform: Linux" src="https://img.shields.io/badge/platform-Ubuntu%20%7C%20Debian%20%7C%20Rocky%20%7C%20Alma%20%7C%20Fedora%20%7C%20CentOS-blue" />
  <img alt="Init: systemd" src="https://img.shields.io/badge/init-systemd-blue" />
  <img alt="Version: v1.05" src="https://img.shields.io/badge/version-v1.05-14614d" />
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-green" /></a>
</p>

## 设计哲学

简单，安全，打通 Mihomo 生态的最后一公里。

ClashGate 不做大而全的控制台。一台 VPS 只需要知道三件事：入站怎么听、出站怎么走、证书放在哪。安全参数内置锁定，改动先记成草稿，点一次「重载配置」再生效。

## 能做什么

- **安装三选一**：无证书（直接给出 VLESS Reality）、自动证书（Let's Encrypt，端口验证或 Cloudflare DNS）、手动证书。
- **面板很短**：首页、出站节点、节点转换、HTTPS 证书。自定义服务端默认关闭，到设置里打开。修改密码也在设置里。
- **先草稿，后重载**：增删节点、换订阅、重置密钥都先记下来。点顶部「重载配置」后写入服务端，并更新客户端订阅。
- **证书按切换生成**：没改模式时按钮是灰的。切换后重新生成证书；Token 无效或 80 端口被占用，会把原因返回到面板。

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
