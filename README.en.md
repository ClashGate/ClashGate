<h1 align="center">ClashGate</h1>

<p align="center"><a href="README.md">中文</a> · <b>English</b></p>

<p align="center">ClashGate · a simple, safe proxy server on the Mihomo core</p>

<p align="center">
  <img alt="Platform: Linux" src="https://img.shields.io/badge/platform-Ubuntu%20%7C%20Debian%20%7C%20Rocky%20%7C%20Alma%20%7C%20Fedora%20%7C%20CentOS-blue" />
  <img alt="Init: systemd" src="https://img.shields.io/badge/init-systemd-blue" />
  <img alt="Version: v1.04" src="https://img.shields.io/badge/version-v1.04-14614d" />
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-green" /></a>
</p>

## Design

Simple and safe. The last mile of the Mihomo ecosystem.

ClashGate is not a kitchen-sink console. A VPS needs three answers: what listens, what it dials, and where the certificate lives. Security defaults stay locked. Changes sit as a draft until you click **Reload config**.

## What it does

- **Three install modes**: no certificate (a VLESS Reality node, directly), automatic Let's Encrypt (port or Cloudflare DNS), or a certificate you bring yourself.
- **A short panel**: Home, Outbound nodes, Node converter, HTTPS certificate. Custom server stays off until you enable it in Settings. Password changes live there too.
- **Draft, then reload**: adding or removing nodes, rotating the subscription, and resetting keys are recorded first. **Reload config** writes the server and updates the client subscription.
- **Certificates regenerate on a real switch**: the button stays gray until the mode changes. A bad API token or an occupied port 80 is returned as an error, not a silent failure.

## Install

systemd Linux (Ubuntu / Debian / Rocky / Alma / Fedora / CentOS), as root:

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
