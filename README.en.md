<h1 align="center">ClashGate</h1>

<p align="center"><a href="README.md">中文</a> · <b>English</b></p>

<p align="center">
  ClashGate · a lightweight, modern VPS proxy server and admin console (v0.98)
</p>

<p align="center">
  <img alt="Platform: Linux" src="https://img.shields.io/badge/platform-Ubuntu%20%7C%20Debian%20%7C%20Rocky%20%7C%20Alma%20%7C%20Fedora%20%7C%20CentOS-blue" />
  <img alt="Init: systemd" src="https://img.shields.io/badge/init-systemd-blue" />
  <img alt="Version: v0.98" src="https://img.shields.io/badge/version-v0.98-10b981" />
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-green" /></a>
</p>

## ✨ Features

- **Three install modes**: **no-certificate mode** (default; outputs a VLESS Reality node directly), **auto-certificate mode** (automatically obtain a Let's Encrypt certificate, with port validation or Cloudflare DNS API validation and automatic renewal), and **manual certificate mode** (bring your own certificate in `/etc/clashgate/certs/`).
- **HTTPS admin panel (v0.98)**:
  - **Ready to use**: 12 inbound protocols (VLESS Reality, Hysteria2, Snell V5, Shadowsocks, AnyTLS, TUIC v5, TrustTunnel, ShadowQUIC, Mieru, Sudoku, HTTP, SOCKS5). Security parameters (ciphers, obfuscation, SNI pool, fingerprints, etc.) are built in and locked, with one-click **password / key reset**.
  - **Everything on the home page**: live proxied-traffic stats (GB), the subscription link (changeable in one click), inbound nodes, and the Zashboard console (with prefilled direct URL and API secret). The top bar offers one-click core update and version check.
  - **Two-way live sync**: external subscriptions (`proxy-providers`), outbound nodes (incl. `easytier` / `tailscale`), a readable-config converter, and custom server configs (certificate paths auto-fixed, one-click restore of the default VlessReality config). Changes are validated and then synced to the server and the client subscription.
  - **Draft-then-reload workflow**: adding / deleting nodes and resetting passwords only change the draft; the live config is written only when you click **Reload config**.
  - **Bilingual UI**: Chinese by default, one-click switch to English (remembered across refreshes).

## 📦 One-click install

Works on mainstream `systemd` Linux distributions (Ubuntu / Debian / Rocky / Alma / Fedora / CentOS; `root` required):

```bash
curl -fsSL https://raw.githubusercontent.com/ClashGate/ClashGate/main/install.sh | bash
```

English installer and CLI messages:

```bash
curl -fsSL https://raw.githubusercontent.com/ClashGate/ClashGate/main/install.sh | CLASHGATE_LANG=en bash
```

## 🌐 Language

- **Default is Chinese.** Use the `中文` / `English` toggle on the login page or in the top bar; the choice is stored in browser `localStorage` and a cookie (`clashgate_lang`), and the server localizes its messages accordingly.
- **Installer and `clashgate` command**: set `CLASHGATE_LANG=en` (or `zh`). When unset, English is used if `LC_ALL` / `LANG` starts with `en`; otherwise Chinese.

## ⌨️ Commands

Run `clashgate` to open the interactive menu, or use a subcommand:

```text
clashgate [status | info | sub | reset-sub | passwd | reset-password | reset-secret | cert | restart | log | update | uninstall | install | help]
```

## 📂 Directory layout

Everything lives under `/etc/clashgate/`:

- `config.yaml` / `custom_config.yaml`: server config
- `certs/`: TLS certificates (`fullchain.pem` / `privkey.pem`)
- `client/`: locally generated client configs and node snippets (`mihomo-client.yaml` / `proxies.yaml`)
- `panel/`: web admin panel

## ⚠️ Disclaimer & license

This project is for learning and research on networking and automation only; please comply with local laws and regulations. [MIT License](LICENSE)
