<h1 align="center">ClashGate</h1>

<p align="center"><a href="README.md">中文</a> · <b>English</b></p>

<p align="center">ClashGate · a simple, safe proxy server on the Mihomo core</p>

<p align="center">
  <img alt="Platform: Linux" src="https://img.shields.io/badge/platform-Ubuntu%20%7C%20Debian%20%7C%20Rocky%20%7C%20Alma%20%7C%20Fedora%20%7C%20CentOS-blue" />
  <img alt="Init: systemd" src="https://img.shields.io/badge/init-systemd-blue" />
  <img alt="Version: v1.22" src="https://img.shields.io/badge/version-v1.22-1d6fe0" />
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-green" /></a>
</p>

## Design

Simple and safe. The last mile of the Mihomo ecosystem.

## What it does

- **One command to a working server**: deploy a Mihomo server on a common Linux VPS; the installer prints a ready-to-use client config.
- **Two install modes**:
  - No-certificate mode: just a server; VLESS Reality nodes are generated for you. The quickest start.
  - Auto-certificate mode: add a domain and get a Let's Encrypt certificate that renews itself, plus an HTTPS admin panel and a subscription link.
- **Three ways to get the certificate**: port mode (validated over port 80), Cloudflare DNS (no port 80 needed), or upload your own. Switch any time in the panel.
- **Many protocols**: VLESS Reality, Shadowsocks, Hysteria2, Snell v6, AnyTLS, TUIC, TrustTunnel, ShadowQUIC, Mieru and Sudoku, added in a few clicks.
- **Subscription link**: import it into Mihomo / Clash clients; when nodes change, clients just refresh the subscription.
- **Server-side routing**: send different sites through different exits with rules in the panel; advanced users can swap in their own server config.
- **Cluster**: link several ClashGate servers so one subscription link carries the nodes of all of them.
- **Low maintenance**: check for updates in one click or turn on auto-update; core updates and certificate renewals are handled for you, and a runtime dashboard (Zashboard) is included.
- **Multi-language**: the admin panel speaks 中文, English, Русский and فارسی; the installer and command line speak Chinese and English.

## System requirements

- Linux (x86_64 / arm64 / armv7) with systemd, run as root.
- Recommended: Debian 11+, Ubuntu 20.04+, Rocky / Alma 8+, Fedora.
- Auto-certificate mode (with the admin panel) needs Python 3.9 or newer. On Rocky / Alma 8 a newer Python is installed automatically; older systems (such as CentOS 7) can only use no-certificate mode.
- Auto-certificate mode also needs a domain pointing at the server. On Cloudflare, set that record to grey cloud (DNS only).

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/ClashGate/ClashGate/main/install.sh | CLASHGATE_LANG=en bash
```

## Commands

Run `clashgate` for the menu, or:

```text
clashgate [status | info | sub | reset-sub | passwd | reset-password | reset-secret | cert | restart | log | update | uninstall | install | help]
```

## Layout

Everything is under `/etc/clashgate/`:

- `config.yaml`: the server config in use
- `certs/`: `fullchain.pem` and `privkey.pem`
- `client/`: client subscription snippets
- `panel/`: the admin panel

## Acknowledgements

- [Mihomo](https://github.com/MetaCubeX/mihomo) — proxy core
- [acme.sh](https://github.com/acmesh-official/acme.sh) — certificate issue and deploy
- [Zashboard](https://github.com/Zephyruso/zashboard) — runtime dashboard
- [Vue](https://github.com/vuejs/core) — panel UI
- [Tailwind CSS](https://github.com/tailwindlabs/tailwindcss) — styling
- [Lucide](https://github.com/lucide-icons/lucide) — icons

## License

For learning and research on networking and automation. Obey local law. [MIT License](LICENSE)
