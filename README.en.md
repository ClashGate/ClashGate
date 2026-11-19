<h1 align="center">ClashGate</h1>

<p align="center"><a href="README.md">中文</a> · <b>English</b></p>

<p align="center">ClashGate · a simple, safe proxy server on the Mihomo core</p>

<p align="center">
  <img alt="Platform: Linux" src="https://img.shields.io/badge/platform-Ubuntu%20%7C%20Debian%20%7C%20Rocky%20%7C%20Alma%20%7C%20Fedora%20%7C%20CentOS-blue" />
  <img alt="Init: systemd" src="https://img.shields.io/badge/init-systemd-blue" />
  <img alt="Version: v1.24" src="https://img.shields.io/badge/version-v1.24-1d6fe0" />
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
- **Multi-language**: the admin panel speaks 中文, English, Русский and فارسی; the installer and command line speak 中文, English and Русский (switch with `clashgate lang`).

## System requirements

- Linux (x86_64 / arm64 / armv7) with systemd, run as root.
- Recommended: Debian 11+, Ubuntu 20.04+, Rocky / Alma 8+, Fedora.
- Auto-certificate mode (with the admin panel) needs Python 3.9 or newer. On Rocky / Alma 8 a newer Python is installed automatically; older systems (such as CentOS 7) can only use no-certificate mode.
- Auto-certificate mode also needs a domain pointing at the server. On Cloudflare, set that record to grey cloud (DNS only).

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/ClashGate/ClashGate/main/install.sh | bash
```

The installer first asks for a language (1 中文 / 2 English / 3 Русский). Press Enter for the default: the saved language, or one guessed from the system `LANG`. Then it asks for the install mode, the certificate method and the domain. The language you pick is saved: every later `clashgate` command uses it, and the admin panel opens in it the first time (a browser that already picked a language keeps its own choice).

- To skip the language question: `curl -fsSL …/install.sh | CLASHGATE_LANG=en bash` (`zh` / `en` / `ru`).
- Without an interactive terminal (for example in automation) nothing is asked; `CLASHGATE_LANG` or the system `LANG` is used.
- Persian (فارسی) is available in the admin panel only. Terminals show right-to-left text poorly, so the installer and command line don't offer it.

## Commands

After installing, run `clashgate` with no argument (or `clashgate menu`) to open the interactive menu; each menu entry is one of the subcommands below. `clashgate help` lists them all. Every command except `help` needs root. Commands marked "certificate modes" work only in auto-certificate or manual-certificate mode (the modes with the admin panel).

### Install and update

| Command | What it does | When to use it | Notes |
| --- | --- | --- | --- |
| `curl -fsSL …/install.sh \| bash` | One-click install | First install on a server | Pick a language, then a mode: 1 no-certificate (VLESS Reality nodes only), 2 auto-certificate (Let's Encrypt, port mode or Cloudflare DNS API), 3 manual certificate (your own certificate). Certificate modes get random free high ports for the panel and Zashboard; at the end the installer prints the subscription link, the panel URL and a password shown only once |
| `clashgate install` | Reinstall | To switch install mode, or regenerate every node | Asks first, then uninstalls and installs again: nodes and keys are regenerated, and the server leaves its cluster first if it is in one. An issued certificate and the acme.sh account for the same domain are kept and reused, so usually nothing is requested again. Terminal only |
| `clashgate update` | Update core + scripts and panel | To upgrade to the latest version | Downloads the latest code of the current update channel and replaces the scripts, panel and templates (config, certificates and nodes are kept), rebuilds the config, checks it with `mihomo -t` and restarts; if the new config fails the check, the old one is kept. Switch the update channel in the panel under Settings: stable (GitHub `main` branch) or test (`test` branch) |
| `clashgate update core` | Update only the Mihomo core | To upgrade just the core | Downloads the latest stable Mihomo, checks the config and restarts |
| `clashgate update self` | Update only the scripts and panel | To update ClashGate but keep the core | Same as `update` without the core |

Examples:

```bash
clashgate update          # core + scripts and panel
clashgate update core     # core only
```

### Service

| Command | What it does | When to use it | Notes |
| --- | --- | --- | --- |
| `clashgate status` | Show status | Routine checks, troubleshooting | Install mode, Mihomo state and version, panel URL and port, certificate expiry and the last auto-renewal, Zashboard URL and API secret, and whether each node port is listening |
| `clashgate restart` | Restart the core | After editing the config by hand, or when nodes misbehave | Checks the current config with `mihomo -t` first and does not restart if it fails (so the service is never taken down) |
| `clashgate log` | Show recent logs | Debugging connections, certificates or the panel | Last 50 lines of the Mihomo log; in certificate modes also the last 30 lines of the panel and certificate jobs |

### Subscription and nodes

| Command | What it does | When to use it | Notes |
| --- | --- | --- | --- |
| `clashgate info` | Show node config | Setting up a client by hand, or finding the subscription link | Prints the `proxies` snippet of every node (including nodes added in the panel) and the client config directory `/etc/clashgate/client/`; in certificate modes also the panel, Zashboard and subscription link |
| `clashgate sub` | Show the subscription link | Importing into a Mihomo / Clash client (certificate modes) | The link is a credential; keep it private |
| `clashgate reset-sub` | Change the subscription link | The link leaked (certificate modes) | **Takes effect immediately**: the old link stops working at once (returns 404), and every client must switch to the new one |

### Certificate

| Command | What it does | When to use it | Notes |
| --- | --- | --- | --- |
| `clashgate cert` | Request / renew / validate the certificate now | The certificate was not issued during install, you replaced the certificate files, or you want to check it now (certificate modes) | Follows the current certificate method. **Port mode** uses port 80 briefly for validation (the domain A record must point to this server and TCP 80 must be open). **DNS API mode** validates with a Cloudflare API Token (no ports 80/443 needed; `*.wildcard` domains supported). **Manual certificate mode** only validates `fullchain.pem` and `privkey.pem` in `/etc/clashgate/certs/` (valid, covers the domain, matches the key) and restarts the core to load them. An issued automatic certificate is only renewed within 30 days of expiry; it is checked hourly anyway, so you rarely need this |

Switch the certificate method (port / DNS API / manual) in the panel on the HTTPS certificate page.

### Panel

| Command | What it does | When to use it | Notes |
| --- | --- | --- | --- |
| `clashgate passwd` | Change the panel password (custom) | To set your own password (certificate modes) | Type it twice in a terminal, at least 8 characters; every signed-in browser has to sign in again |
| `clashgate reset-password` | Reset the panel password (random) | You forgot the password (certificate modes) | Prints a new random 20-character password; every signed-in browser has to sign in again |
| `clashgate reset-secret` | Reset the Zashboard API secret (random) | The secret leaked, or you want a new one (certificate modes) | Generates a new secret and restarts the core; the old secret stops working at once, so reconnect Zashboard with the new one |

The username is always `admin`. `clashgate status` or `clashgate info` shows the panel URL and port.

### Language

| Command | What it does | When to use it | Notes |
| --- | --- | --- | --- |
| `clashgate lang` | Pick the CLI language from a list | To change the CLI language | Same as 「语言 / Language」 in the interactive menu |
| `clashgate lang zh\|en\|ru` | Switch the CLI language directly | Same, or from a script | Saved in `/etc/clashgate/clashgate.env` (`CLASHGATE_LANG`); every later command uses it, and the admin panel uses it as its default language (browsers that already picked one are not affected) |

To run a single command in another language: `CLASHGATE_LANG=en clashgate status` (that run only; nothing is saved).

### Uninstall

| Command | What it does | When to use it | Notes |
| --- | --- | --- | --- |
| `clashgate uninstall` | Uninstall | You no longer need ClashGate | Asks first. If the server is in a cluster it **leaves the cluster first** (the other members are told to remove it; any that could not be reached are listed so you can remove it from their panels by hand). It **closes the ports it opened in ufw / firewalld** (rules you added yourself are left alone), then deletes Mihomo, the admin panel, certificates (including acme.sh), config and client files. Remove any rules in your cloud provider's security group yourself |

### Environment variables

| Variable | Effect |
| --- | --- |
| `CLASHGATE_LANG=zh\|en\|ru` | Skips the language question during install; otherwise applies to that one command only (change the saved language with `clashgate lang`) |
| `REPO_BRANCH=test` | Installs from the `test` branch (test channel), e.g. `curl -fsSL …/install.sh \| REPO_BRANCH=test bash`; after install, switch the update channel in the panel under Settings |

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
