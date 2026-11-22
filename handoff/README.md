# ClashGate Agent Handoff Guide

This document is for agents taking over ClashGate development. It covers product principles, repository layout, the release process, and rules you must follow, so later versions can be handed off seamlessly. Current version: **1.37**. Next version number: **1.38**. Public repository: https://github.com/ClashGate/ClashGate

---

## 1. Product positioning and principles

ClashGate is a Mihomo proxy server for beginners. Simplicity matters more than 100% feature coverage.

- **Make choices for users.** Do not add options, subcommands, explanatory asides, or extra scope on your own. The more you take on, the more bugs you get.
- **Keep user-facing output and docs minimal.** Do not explain “why”; over-explaining is a mistake.
- **The installer must set up every dependency up front** (including geo data `geoip.metadb`, `GeoSite.dat`, and `ASN.mmdb`). Users must not hit errors later when they first use a feature.
- **Updates must fix existing installs automatically.** Do not require a manual step.
- **Panel skins:** 默认 (default, light), 深色 (dark) and 圣诞 (christmas), picked in Settings and kept per browser (`theme.js`, `<html data-theme>`). The default stays light; do not make another skin the default. `src/theme-dark.css` is generated: after changing colours in `style.css` or adding an arbitrary colour class (`bg-[#...]`), run `python3 panel/web/dark-theme.py` (a test fails while it is out of date).
- **Fix rough UI spots directly**; do not ask first. Keep cards and forms symmetric. Accent color is `#1d6fe0`. The brand icon is a cat.
- **Panel languages:** Chinese / English / Русский / فارسی, default Chinese. Installer and CLI: Chinese / English / Русский (`clashgate lang` or `CLASHGATE_LANG`).
- **Development language** (dev docs, code comments, commit messages) is English. User-facing content is currently mainly Chinese, with i18n in progress.
- License: MIT.

---

## 2. Architecture and layout

The unified install directory is `/etc/clashgate`. The management command is `/usr/local/bin/clashgate` (a symlink to the installed `scripts/cmd/clashgate.sh`). The core binary is `/etc/clashgate/mihomo`, running as the `mihomo` user. In certificate modes the panel serves HTTPS itself (sharing `/etc/clashgate/certs` with the core). **Do not use Caddy or a reverse proxy.**

### Install modes

- **No-certificate mode** (`MODE=no-cert`): generates only VLESS Reality nodes and prints a client config after install.
- **Automatic-certificate mode** (`MODE=auto-cert`): requires a domain; obtains and renews a Let's Encrypt certificate, and provides the HTTPS admin panel and a subscription URL.
- **Manual-certificate mode** (`MODE=auto-cert` and `CERT_MODE=manual`): uses a certificate the user supplies; after validation, the panel and subscription are provided the same way.

Certificate methods (`CERT_MODE`; all can be switched on the panel's 「HTTPS 证书」 (HTTPS certificate) page):

| Value | Name | Notes |
| --- | --- | --- |
| `port` | 端口模式 (port mode, default) | Temporarily binds port 80 during issue/renew |
| `dns` | DNS API 模式 (DNS API mode) | Cloudflare API Token; port 80 not required; supports `*.` wildcards |
| `manual` | 手动证书 (manual certificate) | User places the cert in `/etc/clashgate/certs/`; no issue or renew |

The default certificate source is the Let's Encrypt production environment (`TLS=production`). Do not issue a “production self-signed certificate” as the user-facing solution. If issuance fails, `certctl.sh` may write a temporary self-signed certificate only so the panel and core can start; `TLS=internal` is for development only and does not use ACME.

Subscription URL: `https://<domain>:<panel-port>/sub/<token>/mihomo.yaml` (the filename `mihomo.yaml` is allowed).

Inbound protocols the panel can add: VLESS Reality, Shadowsocks, Hysteria2, Snell v6, AnyTLS, TUIC, TrustTunnel, ShadowQUIC, Mieru, Sudoku, HTTP, SOCKS5.

### systemd units

| Unit | Role |
| --- | --- |
| `mihomo.service` | Core. Runs `mihomo -t -d /etc/clashgate -f /etc/clashgate/config.yaml` before start |
| `clashgate.service` | Admin panel (certificate modes only). `python3 /etc/clashgate/panel/panel.py serve --config /etc/clashgate/panel.json` |
| `clashgate-cert.service` / `clashgate-cert.timer` | Calls `certctl.sh renew` hourly |

### Repository layout (source)

| Path | Role |
| --- | --- |
| `install.sh` | One-click install entry. When run via `curl\|bash`, downloads the branch tarball from GitHub, then hands off to `scripts/cmd/clashgate.sh` to install. Language: `CLASHGATE_LANG=zh\|en\|ru` or an interactive prompt, saved to `/etc/clashgate/clashgate.env` |
| `uninstall.sh` | Same as `clashgate uninstall` |
| `scripts/cmd/clashgate.sh` | CLI and the main install / update / uninstall flow |
| `scripts/lib/common.sh` | Version constants, paths, env persistence, `install_files`, update channels |
| `scripts/lib/core.sh` | Dependencies, core download, `ensure_geodata`, config rendering, systemd, opening the host firewall if ufw/firewalld is enabled |
| `scripts/lib/cert.sh` | Certificate preflight, DNS check, manual certs, ACME issuance |
| `scripts/lib/acme.sh` | Pins and installs acme.sh 3.1.6 under `/etc/clashgate/acme.sh` |
| `scripts/lib/panel.sh` | Panel unit, subscription URL, panel password |
| `scripts/lib/i18n.sh`, `i18n.en.tsv`, `i18n.ru.tsv` | Installer and CLI translations |
| `scripts/certctl.sh` | `issue` / `renew` / `deploy`. When the panel invokes it, output is fixed to Chinese so failure reasons can be parsed. CLI language follows `CLASHGATE_LANG` |
| `scripts/init/` | Templates for the systemd units above (including the cert timer) |
| `panel/panel.py` | Panel entry point (Python 3.9+, stdlib only). Subcommands: `serve`, `hash-password`, `cluster-leave` (leave the cluster on uninstall) |
| `panel/cg_http.py` | HTTPS server and API (including `do_check_update`) |
| `panel/cg_config.py` | Node / inbound / config generation, `ensure_geodata`, `validate_config` (`mihomo -t`) |
| `panel/cg_update.py` | Traffic stats, core updates, panel self-upgrade, channel checks |
| `panel/cg_cluster.py` | Cluster protocol |
| `panel/cg_cert.py` | Rewrites certificate paths in a config to this project's certificates |
| `panel/cg_yaml.py` | YAML read/write |
| `panel/cg_masque.py` | Cloudflare MASQUE registration |
| `panel/cg_qr.py` | QR codes |
| `panel/routing_mgr.py` | Server-side routing: `/etc/clashgate/routing/` + `routing.json`, assembled into the template |
| `panel/i18n_en.py` | English translations of server API messages (source strings stay Chinese) |
| `panel/web/` | Vue 3 + Tailwind frontend source (`package.json` version is `1.37.0`). `src/composables/usePanel.js` holds the shared core (boot data, toast, dialogs, `postAction`, server-state sync, tabs); each page's state and actions are in `src/composables/use*.js` and receive the core through one `shared` object |
| `panel/dist/` | **Committed build output.** After frontend changes, run `cd panel/web && npm ci && npm run build` and commit the `panel/dist` updates (CI checks `git diff --exit-code -- panel/dist`) |
| `resources/server.yaml.tpl`, `resources/client.yaml.tpl` | Server / client config templates |
| `resources/routing/` | Default routing groups (节点选择 / node select, 漏网之鱼 / final / unmatched) |
| `resources/brand/logo.png` | Brand icon |
| `tests/` | Tests (see section 7) |
| `.github/workflows/ci.yml` | Runs `tests/run.sh` on every push and pull request |
| `handoff/` | This handoff guide. Not in `CS_TREE_PARTS`, so it is not installed onto machines |

`install_files` atomically replaces only these top-level items (`CS_TREE_PARTS`): `install.sh`, `uninstall.sh`, `panel`, `resources`, `scripts`. Config, certificates, the core binary, and geo data are kept.

### Important runtime paths (all under `/etc/clashgate`)

`config.yaml` (current server config), `custom_config.yaml` (user-supplied full server config), `clashgate.env`, `panel.json`, `certs/fullchain.pem` and `privkey.pem`, `client/`, `nodes.tsv`, various `*.yaml` fragments (controller / listeners / proxies / routing / cluster), `inbounds.json`, `cluster.json`, `routing.json`, `routing/`, and the geo data files.

---

## 3. Current CLI commands (v1.37)

With no argument: opens the management menu if already installed, otherwise starts install. `clashgate help` lists every subcommand.

| Command | Description |
| --- | --- |
| `clashgate status` | Show running status |
| `clashgate info` | Show node configuration |
| `clashgate log` | Show recent logs |
| `clashgate restart` | Validate the config, then restart the core |
| `clashgate sub` | Show the subscription URL (certificate modes only) |
| `clashgate reset-sub` | Rotate the subscription URL; the old URL stops working immediately (certificate modes only) |
| `clashgate reset-password` | Reset the panel password to a random value (certificate modes only) |
| `clashgate cert [domain]` | Change the domain (certificate modes only). Gets the new certificate first (manual mode: from `/etc/clashgate/certs.new/`); if that fails, nothing changes. Then, like a reinstall: leaves the cluster, deletes every inbound node and creates one new default VLESS Reality node, and rotates the subscription token and the Zashboard API secret. Keeps the panel password and port, server outbounds and routing. Refuses while panel drafts are pending or the custom server config is on |
| `clashgate update` | Update the core, scripts, and panel together (the panel's 「升级」 (Upgrade) action and auto-update also call this) |
| `clashgate lang [zh\|en\|ru]` | Switch and save the CLI language (no argument: choose from a list) |
| `clashgate install` | Reinstall (choose the mode when prompted) |
| `clashgate uninstall` | Uninstall: leave the cluster first if linked, then delete the install. **Do not touch firewall ports** (do not add logic that closes ports that were opened) |
| `clashgate help` | Help |

Removed; do not add them back: `clashgate passwd`, `clashgate reset-secret`, and the split `update core` / `update self` commands. Changing the panel password and resetting the Zashboard secret are done in the panel; certificate renewal and the certificate method are on the panel's 「HTTPS 证书」 page. `clashgate cert` came back in 1.37 with a different job (changing the domain, see above) at the owner's request.

Hidden flags for development and testing (do not put these in user docs): `--domain`, `--cert-mode port|dns|manual`, `--cf-token`, `--panel-port`, `--controller-port`, `--staging` / `--tls-staging`, `--production`, `--tls-internal`. For certificate tests, use staging or reuse an existing certificate. **Do not re-issue certificates against the Let's Encrypt production environment in tests.**

---

## 4. Mihomo conventions

- Follow the [official Mihomo docs](https://wiki.metacubex.one/en/).
- **Do not put “mihomo” in downstream names** (the user-visible product name is ClashGate). The subscription filename `mihomo.yaml` is allowed; the core binary, `mihomo.service`, and the core's home directory belong to the core itself and are out of scope.
- **Never** put `skip-cert-verify` in issued client configs (generation strips the field; tests also check that sources must not contain `skip-cert-verify: true`).
- **Do not add a CDN mode.**
- **IPv6-only servers:** the installer prefers a public IPv4 and falls back to IPv6 (`SERVER_IP`). When `SERVER_IP` is IPv6, both `core.sh assemble_config` and the panel's `assemble_config()` rewrite `0.0.0.0` listeners / controller to `::` and replace the template's `dns:` block with `DNS_IPV6_ONLY` (system resolver, AAAA); the panel listens on `::`. Keep the two assemblers in sync. GitHub has no IPv6, so such servers need NAT64/DNS64 (or similar) to install.
- **Firewall:** install and the panel only ever *open* ports in ufw / firewalld; nothing closes them (node deletion, cluster changes, uninstall).
- Mihomo v1.19 uses `geoip.metadb` (do not rely only on the older `country.mmdb`). Install and `clashgate update` both call `ensure_geodata`, which pre-downloads `geoip.metadb`, `GeoSite.dat`, and `ASN.mmdb` into `/etc/clashgate` with system curl. Panel startup and `validate_config` also fill in any missing files.
- When the panel or scripts run `mihomo -t`, they must **symlink** these geo files (and certs, ruleset, and similar) into the temporary directory. The core must not download them during validation (its built-in DNS may fail to resolve at that point).

The core version pinned by the test suite is `MIHOMO_VERSION` in `tests/run.sh` (currently `v1.19.34`).

---

## 5. Branches and release process

The public default branch is `main` (stable). `test` is the test channel.

1. Develop and push on `test`. **Every feature or fix pushed to `test` must bump the version** (copy- or docs-only changes are the exception; see below).
2. The project owner verifies on a real machine (the owner clicks 「检查更新」 (Check for updates) in the panel).
3. **Push to `main` only after the owner explicitly agrees.** A version that fails acceptance is retired and must not be reused.

Version numbers are compared as **integers per segment** (`parse_version_tuple`): `1.09 < 1.10 < 1.37`. **Never write `1.1` or `1.2`** (they sort before `1.09`). The next numbers are `1.38`, `1.39`, and so on.

Commit messages are in English. **Never force push.**

**Copy- or docs-only changes:** do not run tests, do not wait for CI, and push directly. `test` and `main` have already diverged, so do not merge just to carry a doc; commit the same file separately on each branch. These changes **must not bump the version.** The `handoff/` directory follows this rule.

### Merging an accepted `test` into `main` (the branches have diverged; a fast-forward is not possible)

Create a worktree on `origin/main`, then:

```bash
git merge --no-ff --no-commit -s ours origin/test
git read-tree -m -u origin/test
git checkout origin/main -- .github
```

Then set the default branch back to `main`:

- `install.sh` header URL: `.../ClashGate/main/install.sh`
- `install.sh`: `${REPO_BRANCH:-main}`
- `scripts/lib/common.sh`: `REPO_BRANCH=${REPO_BRANCH:-main}`

(On the `test` branch these three defaults are `test`. They must be changed back on merge, or a stable install will pull from `test`.)

Then commit and `git push origin HEAD:main`. Do not force push.

The usual content difference between `test` and `main` is only those default-branch values, plus `.github` (keep the workflow history that is already on `main`).

---

## 6. Version bump locations and the update check

When bumping a version, update all of the following at the same time (1.31 as the example):

| Location | Form |
| --- | --- |
| Version badges in `README.md` and `README.en.md` | `v1.31` |
| `panel/panel.py` file-header docstring and `VERSION` | `v1.31` / `"1.31"` |
| `panel/routing_mgr.py` file-header docstring | `1.31` |
| `panel/web/package.json` and `package-lock.json` | `1.31.0` (three segments) |
| `CS_VERSION` in `scripts/lib/common.sh` | `1.31` |
| `CS_SOURCE_SHA` in the same file | `YYYYMMDD-vX.YY` (e.g. `20261120-v1.31`) |
| Version order list in `tests/test_panel.py` | Append the new version to `order` |
| First-line comment in `tests/golden/subscription.yaml` | `Generated by ClashGate v1.31...` |

Also update the version-comparison comments at the top of `common.sh` and `panel.py` to the new version, and name the next version number.

### Panel 「检查更新」 (Check for updates) mechanism

`fetch_channel_tip()` in `panel/cg_update.py`:

1. Resolve the repo and branch for the active channel: 正式 (stable) → `ClashGate/ClashGate@main`; 测试 (test) → `ClashGate/ClashGate@test`.
2. First call the GitHub commits API for that branch's tip SHA, then read `scripts/lib/common.sh` at that commit (raw reads by branch name can be cached for about five minutes). On failure, fall back to reading by branch name.
3. Parse `CS_VERSION` (and `CS_SOURCE_SHA`) from the file.
4. `check_panel_update()` compares with `parse_version_tuple`; only a **strictly newer** version counts as an update.

`POST /action/check-update` is handled by `do_check_update` in `cg_http.py`. On exception it returns **400** with the message 「检查更新失败：无法连接 GitHub 获取最新版本（…）」 (Update check failed: cannot reach GitHub for the latest version (…)). The server must be able to reach GitHub.

A panel upgrade actually runs `clashgate update` detached from the panel process (the update restarts the panel service itself, so it cannot finish synchronously inside the request).

---

## 7. Tests

Run the full local suite in one shot:

```bash
tests/run.sh            # everything (including the frontend build check)
tests/run.sh --no-build # skip the frontend build
```

Flow: `bash -n` on every script → `shellcheck` (warning level, excluding SC2034; missing shellcheck is a failure in CI) → if `MIHOMO_BIN` is unset, download the pinned core into `tests/.cache` → pre-download geo data into `tests/.cache/geo` → `python3 -m unittest discover -s tests -v` → `python3 tests/cluster_e2e.py` → frontend and shell i18n parity checks → frontend `npm run build`, and `panel/dist` must match what is committed.

Main test files: `tests/test_panel.py` (a throw-away `/etc/clashgate` tree + `mihomo -t`), `tests/test_seed_load.py` (script paths that import the panel), `tests/cluster_e2e.py` (multi-panel HTTPS cluster on one machine, using a throw-away CA; no real certificates are issued), `tests/check_i18n.py`, `tests/check_shell_i18n.py`. `tests/node-check.sh` is a pre-release check that imports a subscription into a local client; it is not part of CI.

CI: `.github/workflows/ci.yml`, `ubuntu-24.04`, Node 24, runs `tests/run.sh` on every push and pull request. Editing `.github` needs a token with the `workflow` scope; if `git push` is rejected, edit the file in the GitHub web UI.

Tests **must not** re-issue certificates against the Let's Encrypt production environment: use `--staging`, reuse an existing certificate, or the throw-away CA in the test fixtures. A reinstall keeps the acme.sh account and already-issued certificates, which avoids rate limits.

---

## 8. Recent version history

| Version | Highlights |
| --- | --- |
| 1.24 | Installer and CLI languages zh/en/ru; added `clashgate lang` |
| 1.25 | `certctl` output follows the CLI language; when the panel invokes it, output is fixed to Chinese so it can be parsed |
| 1.26 | README 「常用命令」 (Common commands) rewritten as grouped tables |
| 1.27 | Removed 「系统要求」 (System requirements); 「一键安装」 (One-click install) keeps only the command itself |
| 1.28 | Only `clashgate update` remains; dropped `update core` / `update self` |
| 1.29 | Removed the CLI `passwd`, `reset-secret`, and `cert` commands; uninstall only leaves the cluster and no longer closes firewall ports |
| 1.30 | Install checks print only the step header unless a check fails; the final summary is shorter |
| 1.31 | Pre-download geo data on install/update; the validation temp dir links geo files; the panel fills in missing files; yahoo removed from the Reality SNI pool |
| 1.32 | Added three opt-in panel skins (Airmail, Metro map, Departures); rolled back in 1.34 |
| 1.33 | Redesigned the opt-in skins (Bento, Console, Flow) and removed the duplicate copy button in the subscription QR modal; rolled back in 1.34 |
| 1.34 | Reverts the opt-in panel skins to restore the 1.31 UI; keeps only the removal of the duplicate copy button in the subscription QR modal |
| 1.35 | `clashgate update` keeps the live config while panel drafts are pending; the panel clears drafts that an older update already made live |
| 1.36 | Node status counts only the core's own sockets; a manual inbound port held by another program is rejected; `/api/*` answers 401 when the session expired; certificate issue / mode switch runs as a background job the page polls (with elapsed time); `clashgate reset-sub` drops a pending panel link change; the CLI menu confirms link / password resets and reopens after `update`; the panel never closes firewall ports; an update that waited for panel drafts lands once they are applied or discarded; IPv6-only servers; 「应用配置」 asks first when nothing is pending; the global login cap spares sources that signed in before; `usePanel.js` split into per-page composables; home status rail redesigned (live nodes online + core uptime, pending count or 「已全部生效」, traffic split + speed between two refreshes, per-component update shortcuts); the page links `/assets/app.js` and `style.css` with a `?v=<content hash>` (cached for a year, ETag / 304 otherwise) instead of inlining ~450 kB on every visit |
| 1.37 | Added `clashgate cert [domain]` (menu: 「更换域名证书」): change the domain; the new certificate comes first and a failure changes nothing; then the cluster is left, the inbound nodes are reset to one new VLESS Reality node and the subscription token / Zashboard secret are rotated. Panel UI: nodes deleted in the draft stay listed as 「待删除」 until applied; routing groups get up / down buttons (dragging does not work on touch screens); the four modals are real dialogs (focus moves in, Tab stays inside, focus returns; ✕ has a label); Zashboard card moved to the home page; Settings order: password, update channel, auto update, core, panel version (new, with 检查更新), skin, custom server last; the tab title shows the pending count; new opt-in 「深色」 skin (owner request) |

Next version: **1.38**.

---

## 9. Deferred / do not

- **AI config assistant:** deferred. Do not build it unless the owner explicitly asks.
- **The root `README.md` / `README.en.md` must not mention the historical test repository or any other internal repository name.** Compatibility logic for older installs from that repository exists in the code; do not delete it, but do not put it in user docs.
- Do not add features, options, subcommands, or extra scope on your own. Do not do work that was not requested.
- Do not rewrite user docs to “explain the design”; keep them short. This handoff guide is for agents; do not copy its process notes into the README.
- This repository is public: do not put private server addresses, domains, passwords, accounts, or internal tooling details in the repo.
