<h1 align="center">ClashGate</h1>

<p align="center"><a href="README.md">中文</a> · <b>English</b></p>

<p align="center">ClashGate · a simple, safe proxy server on the Mihomo core</p>

<p align="center">
  <img alt="Platform: Linux" src="https://img.shields.io/badge/platform-Ubuntu%20%7C%20Debian%20%7C%20Rocky%20%7C%20Alma%20%7C%20Fedora%20%7C%20CentOS-blue" />
  <img alt="Init: systemd" src="https://img.shields.io/badge/init-systemd-blue" />
  <img alt="Version: v1.28" src="https://img.shields.io/badge/version-v1.28-1d6fe0" />
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-green" /></a>
</p>

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
- **Multi-language**: the admin panel speaks 中文, English, Русский and فارسی; the installer and command line speak 中文, English and Русский.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/ClashGate/ClashGate/main/install.sh | bash
```

## Commands

Run `clashgate` for the menu, or use a subcommand:

### Everyday

| Command | Description |
| --- | --- |
| `clashgate status` | Show status |
| `clashgate info` | Show node config |
| `clashgate log` | Show recent logs |
| `clashgate restart` | Check config, restart the core |

### Subscription and panel

| Command | Description |
| --- | --- |
| `clashgate sub` | Show the subscription link |
| `clashgate reset-sub` | New subscription link; old one stops at once |
| `clashgate passwd` | Change the panel password |
| `clashgate reset-password` | Reset the panel password (random) |
| `clashgate reset-secret` | Reset the Zashboard secret (random) |

Certificate modes only.

### Certificate

| Command | Description |
| --- | --- |
| `clashgate cert` | Request / renew / validate the certificate now |

### Update and maintenance

| Command | Description |
| --- | --- |
| `clashgate update` | Update core, scripts and panel |
| `clashgate lang zh\|en\|ru` | Switch the CLI language |
| `clashgate install` | Reinstall |
| `clashgate help` | List all subcommands |

### Uninstall

| Command | Description |
| --- | --- |
| `clashgate uninstall` | Uninstall (leaves the cluster, closes opened ports) |

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
