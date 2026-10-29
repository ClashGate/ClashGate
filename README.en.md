<h1 align="center">ClashGate</h1>

<p align="center"><a href="README.md">中文</a> · <b>English</b></p>

<p align="center">ClashGate · a simple, safe proxy server on the Mihomo core</p>

<p align="center">
  <img alt="Platform: Linux" src="https://img.shields.io/badge/platform-Ubuntu%20%7C%20Debian%20%7C%20Rocky%20%7C%20Alma%20%7C%20Fedora%20%7C%20CentOS-blue" />
  <img alt="Init: systemd" src="https://img.shields.io/badge/init-systemd-blue" />
  <img alt="Version: v1.06" src="https://img.shields.io/badge/version-v1.06-14614d" />
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-green" /></a>
</p>

## Design

Simple and safe. The last mile of the Mihomo ecosystem.

## What it does

- **One-command proxy server**: deploy a Mihomo server on a common Linux VPS with a single command, ready to use.
- **Client subscription included**: get a config you can import straight into Mihomo / Clash clients—no hand-assembled YAML.
- **Many protocols**: add VLESS Reality, Shadowsocks, Hysteria2, Snell, AnyTLS, TUIC, TrustTunnel, ShadowQUIC, Mieru, or Sudoku in one click.
- **Server-side routing**: when you need custom outbound routing, replace the built-in template with your own Mihomo server config.

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
