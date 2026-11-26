# ClashGate Agent Handoff Guide

This document is for agents taking over ClashGate development. It covers product principles, repository layout, the release process, and rules you must follow, so later versions can be handed off seamlessly. Current version: **1.48**. Next version number: **1.49**. Public repository: https://github.com/ClashGate/ClashGate

---

## 1. Product positioning and principles

ClashGate is a Mihomo proxy server for beginners. Simplicity matters more than 100% feature coverage.

- **Make choices for users.** Do not add options, subcommands, explanatory asides, or extra scope on your own. The more you take on, the more bugs you get.
- **Keep user-facing output and docs minimal.** Do not explain “why”; over-explaining is a mistake.
- **The installer must set up every dependency up front** (including geo data `geoip.metadb`, `GeoSite.dat`, and `ASN.mmdb`). Users must not hit errors later when they first use a feature.
- **Updates must fix existing installs automatically.** Do not require a manual step.
- **Panel skins:** 默认 (default, light), 深色 (dark), 玻璃 (glass, frosted translucent cards, hand-written `src/theme-glass.css`; every rule starts with `html[data-theme="glass"]` and keeps the no-backdrop-filter / reduced-transparency fallbacks) and 圣诞 (christmas), picked in Settings and kept per browser (`theme.js`, `<html data-theme>`). The default stays light; do not make another skin the default. `src/theme-dark.css` is generated: after changing colours in `style.css` or adding an arbitrary colour class (`bg-[#...]`), run `python3 panel/web/dark-theme.py` (a test fails while it is out of date).
- **Content-Security-Policy** (`CSP` in `panel/cg_http.py`): no inline scripts except `_THEME_JS` (allowed by its hash). Put new browser code in the Vite bundle; page data goes into the `cs-boot` JSON block.
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

Inbound protocols the panel can add: VLESS Reality, VLESS Encryption, Shadowsocks, Hysteria2, Snell v6, AnyTLS, TUIC, TrustTunnel, ShadowQUIC, Mieru, Sudoku, HTTP, SOCKS5. Custom server mode also offers VLESS XHTTP (`CUSTOM_ONLY_TYPES`).

### systemd units

| Unit | Role |
| --- | --- |
| `mihomo.service` | Core. Runs `mihomo -t -d /etc/clashgate -f /etc/clashgate/config.yaml` before start |
| `clashgate.service` | Admin panel (certificate modes only). `python3 /etc/clashgate/panel/panel.py serve --config /etc/clashgate/panel.json` |
| `clashgate-cert.service` / `clashgate-cert.timer` | Calls `certctl.sh auto` daily (renew; after failed requests it backs off: 1, 2, then every 3 days; 1.47) |

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
| `panel/web/` | Vue 3 + Tailwind frontend source (`package.json` version is `1.48.0`). `src/composables/usePanel.js` holds the shared core (boot data, toast, dialogs, `postAction`, server-state sync, tabs); each page's state and actions are in `src/composables/use*.js` and receive the core through one `shared` object |
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

## 3. Current CLI commands (v1.48)

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
| `clashgate cert [domain]` | Change the domain (certificate modes only). In a terminal it first asks for the certificate method (port / DNS API / manual; Enter keeps the current one), then the domain, then the token or the certificate files; one short y/N confirmation. Gets the new certificate first (manual mode: from `/etc/clashgate/certs.new/`); if that fails, nothing changes. Then, like a reinstall: leaves the cluster, deletes every inbound node and creates one new default VLESS Reality node, and rotates the subscription token and the Zashboard API secret. Keeps the panel password and port, server outbounds and routing. Refuses while panel drafts are pending or the custom server config is on |
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

Version numbers are compared as **integers per segment** (`parse_version_tuple`): `1.09 < 1.10 < 1.48`. **Never write `1.1` or `1.2`** (they sort before `1.09`). The next numbers are `1.39`, `1.40`, and so on.

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
| 1.37 | Added `clashgate cert [domain]` (menu: 「更换域名证书」): change the domain; the new certificate comes first and a failure changes nothing; then the cluster is left, the inbound nodes are reset to one new VLESS Reality node and the subscription token / Zashboard secret are rotated. Panel UI: nodes deleted in the draft stay listed as 「待删除」 until applied; routing groups get up / down buttons (dragging does not work on touch screens); the four modals are real dialogs (focus moves in, Tab stays inside, focus returns; ✕ has a label); Zashboard card moved to the home page; Settings order: password, update channel, auto update, core, panel version (new, with 检查更新), skin, custom server last; the tab title shows the pending count; new opt-in 「深色」 skin (owner request); the cluster works in custom-server mode: `custom_conf_with_cluster` replaces only the cluster listeners / member outbounds in the user's file (on every cluster change and when a custom config is saved), the user's proxy-groups decide whether members are used; a change the user's file rejects (e.g. a group naming a member that renames) is rolled back |
| 1.38 | DNS API mode checks before asking Let's Encrypt that the token can see the domain's Cloudflare zone (clear message instead of acme.sh's `invalid domain`); `clashgate status` counts only the core's sockets; the home page shows a certificate alert only when the certificate is temporary, missing, expired or under 14 days; a typed Reality SNI must answer TLS 1.3 from the server; the Settings 面板版本 card is gone (the home status rail has it); Content-Security-Policy: scripts only from the panel plus the hashed skin snippet, boot data is a JSON block read by `src/boot.js`; cluster members are exits only: each cluster inbound has `proxy: DIRECT`, so traffic from another panel never follows this server's rules and A -> B -> A cannot loop (Mihomo's loopback detector only catches a core dialing itself); existing links get it on the first panel start after the update (`refresh_cluster_fragments`), in custom-server mode too (the user's file gets it back on every cluster change / save even if it was deleted by hand) |
| 1.39 | Installer and panel core update pick the Mihomo build by x86-64 level from `/proc/cpuinfo` (v3 / plain / v2 / v1 / compatible, best first) and silently try the next one when `-v` fails (no message: it is a one-click installer, the user only sees 「已安装」): the plain amd64 build needs an x86-64-v3 CPU and stopped installs on older VPS CPUs ("can only be run on AMD64 processors with v3 microarchitecture support"); the test scripts use the `amd64-compatible` build. Cluster add / check / remove / leave run in the background from the page (`async=1`, `/api/cluster-task-status`); a blocking overlay shows the current step (connecting, the other panel reloading, this panel reloading, notifying members) and the seconds, and comes back after a page reload; other panels and the CLI still get a blocking answer. A click while another action is running now says so instead of doing nothing |
| 1.40 | Cluster: a 等待互联 entry (a panel the members know but this panel could not link with) records the members that reported it (`via`) and goes away with them (`_prune_pending`, also on load, so a stale entry from 1.39 disappears once its members are gone); the page can dismiss one (「忽略」, `/cluster/dismiss`; the next 检查 tries again). 检查 asks every member that knows a missing panel, not only the first, and says which member cannot reach it (「X 现在也连不上它：…」) instead of the generic 「对方面板没有响应集群请求」; asking a member for a ticket retries a timeout once (`ClusterTimeout`). Add / 检查 run in two phases (`cluster_batch`): first every link is exchanged and only saved (this panel stages its changes; `join` / `connect` with `defer=1` make the other panels stage theirs), then this panel sends `/api/cluster/apply` to every panel it touched (one reload each) and reloads itself once. A panel that reports a failed apply has undone its side and the new link with it is dropped here; one that does not answer applies by itself after `CLUSTER_STAGE_TTL` (180 s), and a panel start also applies links that are saved but missing from the config (`refresh_cluster_fragments`); panels before 1.40 ignore `defer` and answer 401 to `/api/cluster/apply`, which counts as done. If the final local reload fails, the links made in the operation are undone on both sides. Links authenticate with their own keys, so changing a panel password never drops them (now said under the password field; e2e covers it). Members that failed (badge 「连接失败」, was 「联系不上」) or miss links get 「重试」 next to 「移除」 (`/cluster/retry`: asks that member again, then a full 检查); 等待互联 rows get 「重试」 (检查) next to 「忽略」. The custom-server note on the cluster page is gone (owner request) |
| 1.41 | config.yaml and the panel's fragments write every listener / outbound as multi-line YAML (`render_extra`, `render_cluster_*` use `dump_yaml_proxies`); before, panel inbounds and cluster entries were one JSON object per line. On the first start `reformat_flow_entries` rewrites `listeners.extra.yaml` and the live config.yaml (only the format: both parsed and compared, `mihomo -t` on a copy, no reload; skipped with drafts and in custom mode) and `refresh_cluster_fragments` compares entries instead of text (format-only differences rewrite the fragments, no reload). `yaml_scalar` quotes strings a YAML reader would take as numbers (1e5, 0x1f, 1:30, .inf, y/n) or that start with `@` / backtick; the Reality short-id is quoted (an all-digit id like 01234567 lost its leading zero). 退出集群 drops the links here first (one reload) and tells the members from a thread (a member not reached drops its link at its next 检查). Only the first 添加到集群 shows the blocking overlay (title + seconds + step, no extra text); 检查 / 重试 / 移除 / 退出 run behind their own button (「检查中…」 with a small spinner, `clusterBusy`), the rest of the panel stays usable. 恢复默认服务端模板 says what happens, keeps the user's file as `custom_config.yaml.saved` and turns custom server off afterwards |
| 1.42 | One cluster inbound per panel: `cg-cluster-in` (one port, one VLESS Encryption key pair, saved as `inbound` in cluster.json by `ensure_cluster_inbound`), every member is one user (its own UUID, `link["in"] = {"uuid"}`) in it. Adding a member adds a user, removing one deletes that user; the port and keys never change (the port stays reserved while no member uses it). The pairing requests are unchanged (each side still sends port / uuid / encryption), so 1.42 pairs with older panels. Links made before 1.42 (`link["in"]` has a port: `_link_legacy`) keep their dedicated inbound until `cluster_migrate_links` moves them: it sends the member its new node (`/api/cluster/node`, staged, applied with the batch's `/api/cluster/apply`) and drops the old inbound here; it runs during 检查 and in the background after a start (`start_cluster_migration`, every 15 min while old links remain); a member before 1.42 answers 401 and keeps its link as it is |
| 1.43 | Fewer core restarts: `reload_core` sends `systemctl reload` (SIGHUP; Mihomo applies the file in place: unchanged listeners keep their connections, the controller is rebuilt, new connections wait during the switch) and waits for the expected ports before judging; it restarts only when the reload is refused (core not running) or the ports never come up. 应用配置 used to check the ports right after the signal, before the core had applied the file, so adding an inbound nearly always ended in a restart. Hot reload now also for the cluster, custom server save / off, 恢复默认服务端模板, the template refresh, the Snell migration and `clashgate update` when the core binary did not change. Still a restart: a new core binary, renewed certificates (listeners keep the certificate they loaded), `clashgate restart`, a failed reload's rollback. `clashgate update` checks the core version first (`update_core`): already the latest, no download; the version could not be fetched (API tried twice, then the releases/latest redirect) or the download failed: the panel update goes on, a warning at the end and `core_update_failed`, which `/api/upgrade-status` reports (`core_failed`) so the page says the core was not updated. The panel's 更新内核 gets the same retry / redirect fallback and tries the next build when one download fails. The cluster page's 检查 is shown with no members too (another panel may have added this one), and opening the page runs it once by itself (`autoCheckCluster`: quiet, no toast, at most every 30 s, not while something else runs) |
| 1.44 | Custom server: the add-node form shows the options the safe defaults lock as optional fields (`ADV_FIELDS` in `useInbounds.js`: passwords, usernames, Shadowsocks cipher, UUID / Short ID / Reality key / VLESS Encryption on-off, Hysteria2 obfs, Snell PSK, Sudoku AEAD / table), sent as `adv_*`; `build_inbound(..., advanced=True)` uses them only in custom mode, validates them, and keeps the defaults for blank ones. The 安全默认策略 badge and the 已锁定安全默认 notes are hidden in custom mode. Settings: turning custom server off always asks; with a custom config in use the message says it restores the default server template. 退出集群 is clickable during 检查 / 重试 and takes over: `_cluster_job` sets `_CLUSTER_CANCEL` instead of refusing, the check stops at its next step / change (`ClusterCancelled`, staged changes are not applied, the leave applies once) and does not overwrite the leave's status. New loading visuals: `CgSpinner.vue`, the cluster add overlay has a progress bar and lists the steps done so far. New 关于 page (`/about`, from Settings): version, a short changelog (`CHANGELOG` in `AboutPage.vue`: one line per version, newest first; add the new version there on every release), credits mihomo and Xray with their GitHub links. Home page: Zashboard on the right with 添加节点 under it (without a certificate 添加节点 moves up) |

| 1.45 | New inbound `vless-enc` (VLESS Encryption on plain TCP, the minimal config: one user with `flow: xtls-rprx-vision` and an ML-KEM-768 `decryption` from `mihomo generate vless-mlkem768`; UDP via XUDP inside the TCP stream; firewall TCP only). Custom server only: `vless-xhttp` (VLESS over XHTTP with the certificate and VLESS Encryption; plain optional fields: host (blank = the panel domain), path (blank = random), mode, VLESS Encryption on/off, UUID; the panel does not set up a CDN for the user). `listener_to_inbound` keeps the stored client of an unchanged `vless-enc` / `vless-xhttp` node (the ML-KEM client key cannot be rebuilt from the listener), and `derive_vless_encryption` derives the client key of an ML-KEM seed with `mihomo generate vless-mlkem768 <seed>`. New nodes only: TUIC drops `reduce-rtt`, ShadowQUIC sets `zero-rtt: false` and drops `quic-version-probe` / `max-idle-time` / `disable-mtu-discovery`, HTTP / SOCKS5 default to TLS when a certificate exists, Hysteria2 has no Salamander obfuscation by default (standard HTTP/3 with the real certificate; reset keeps the node's choice). TUIC is labelled without “v5”. The cluster page checks by itself at most every 30 minutes (was 30 s; the time is kept in localStorage). Settings: the 关于 card has no subtitle. Custom-mode add-node form: every select starts on its default option (`advDefaults`; `''` is never sent), and the VLESS encryption switch is labelled 量子加密 so it is not confused with the VLESS Encryption protocol. |
| 1.46 | UI polish. The add-node card keeps one height in custom server mode too (the invisible copies under `cg-stack` include each protocol's optional fields). Every busy button shows `CgSpinner` (light on primary, inherit on red / amber buttons), the core-update icon turns into the spinner, and copy buttons show a check mark while they say 已复制. Row actions on the outbound, cluster and routing pages use the shared `cg-btn-sm cg-btn-secondary` / `cg-btn-danger` (new `cg-btn-xs` for the rule-provider list) instead of hand-made sky / slate / rose buttons. The protocol tag in the node list is neutral (the status pill is the only colour), and the hidden subscription / Zashboard links show an eye icon. New opt-in skin 玻璃 (`glass`, `theme-glass.css`): frosted translucent cards over a fixed soft colour field (backdrop-filter blur + saturate, white rim and top highlight); only large surfaces blur; no refraction; falls back to near-opaque white without backdrop-filter or with prefers-reduced-transparency. `_THEME_JS` (and so its CSP hash) lists it. 关于: a GitHub link to the project (`REPO_URL`), and the credits show mihomo's and Xray's own logos (`public/assets/mihomo.png`, `xray.png`: the MetaCubeX and XTLS GitHub organisation pictures, bundled because the CSP allows images from the panel only). |
| 1.47 | Node list: a node in the draft (added / new password, not applied) gets no `single_config` / `readable_config` and is left out of `all_proxies_yaml`; 复制配置 / 复制全部配置 show 「请先点顶部「应用配置」再复制」 instead of copying draft credentials. The default and custom modes are two separate states: entering custom mode (`apply_custom_config`, from the default mode) keeps the default mode's nodes / inbounds / outbounds / providers (`*.tplbak`) and its controller port / secret (`DEFAULT_ENV_BAK`) aside; turning custom server off (`disable_custom_config`) saves the custom config as `custom_config.yaml.saved` and brings the default mode back exactly as it was. Nothing made in custom mode goes into the default mode and nothing of the default mode goes into the custom config. Routing groups are default-mode only (custom mode never touches them). Fallbacks: no saved default state or it fails `mihomo -t` -> one new VlessReality node, routing kept; that fails too -> 恢复默认服务端模板. HTTPS page: in DNS mode a changed token makes the button 「更新 Cloudflare API Token」 (`/action/cert-token`, `do_cert_token`): the token is checked against Cloudflare (`cf_token_check`, the zone lookup of certctl's `cf_zone_check`) and saved, no new certificate; `/action/cert-mode` with the same mode and a new token takes that path too. The certificate timer runs daily (`certctl.sh auto`, was hourly `renew`); after n failed requests in a row it waits min(n, 3) days. `certctl.sh` writes `/etc/clashgate/cert-failed` (epoch, mode, failures in a row, its messages and acme.sh output, token masked) when an issue / renew fails and removes it after a success; the HTTPS page shows the short reason (`cert_failure_state`, `cert_failure_reason`) until then, never for manual certificates. The panel's 立即申请 / 续期 is never held back. |
| 1.48 | No temporary certificate any more (it trained users to click through browser warnings). Install: a wrong domain record (`check_dns`, port mode) stops before anything is installed (no "continue anyway?"); the certificate is requested right after `install_files`, before `gen_nodes`, and a failed request stops the install with the reason (`issue_cert` dies), so `$STATE` does not exist yet and rerunning the install command is a clean install. `certctl.sh selfsign` is gone (`selfsign()` stays for `TLS=internal`, development only). `render_controller` never creates one: missing files are put back from acme.sh's `live/` copy, else it stops with the reason. A temporary certificate left by an older version is still recognised (`is_temp`, panel `certIsTemp`) and replaced by the daily renewal or 立即申请 / 续期. |

Next version: **1.49**.

---

## 9. Deferred / do not

- **Keep the 关于 changelog short and current.** On every version bump add one line at the top of `CHANGELOG` in `panel/web/src/pages/AboutPage.vue` (tests check that it starts with `VERSION`) and keep at most 8 entries.
- **Shadowsocks keeps `aes-256-gcm` as its default** (owner: it is for old clients). New bare (no TLS) nodes should be VLESS Encryption, not SS. No 0-RTT defaults on new protocols.
- **VLESS XHTTP stays in the custom server mode, as plain fields.** Do not add CDN wizards, hints or auto-filled CDN settings (owner: advanced users set it up themselves).
- **Hysteria2 obfuscation stays off by default** (Salamander drops the HTTP/3 cover); it is an option in custom server mode.
- **Buttons use the shared classes** (`cg-btn-primary`, `cg-btn-sm cg-btn-secondary` / `cg-btn-danger`); a busy button shows `CgSpinner` next to its 「…中…」 text (tests check this).
- **Default mode and custom mode never mix** (owner decision, 1.47): the default mode is for beginners and must stay stable. Do not carry nodes, outbounds or settings from the custom config into the default mode, or the other way round.
- **The certificate timer stays daily with back-off** (at most every 3 days after failures); do not make it hourly again.
- **Changing only the Cloudflare API Token never requests a certificate.** Let's Encrypt allows few certificates per week; the token is checked against Cloudflare and saved, renewals use it.
- **Never fall back to a temporary or self-signed certificate** (owner decision, 1.48). The three certificate setups are: no certificate (no-cert mode), a certificate the script requests (port / DNS API), or the user's own (manual). If a certificate cannot be had, stop and say why.
- **Do not restart the core to apply a config.** Use `reload_core` (hot reload, waits for the ports). Restart only for a new binary or new certificates.
- **One cluster inbound per panel.** Do not go back to an inbound per link; a new member is a user in `cg-cluster-in`. Key rotation is not built in (owner: not needed); if it is ever added, rotate the shared keys and send every member its new node with `/api/cluster/node`.
- **Do not write one-JSON-object-per-line entries into config.yaml or its fragments.** Use `dump_yaml_proxies` / `dump_yaml_map`; tests compare parsed entries (`_section_items`, `_conf_cluster_entries`), not text.
- **Do not block the page for routine cluster actions.** Only the first add shows the overlay; 检查 / 重试 / 移除 / 退出 run in the background behind their button.
- **Do not reload a core in the middle of a cluster add / 检查.** Exchange every link first (staged, `defer=1`), then apply once per panel (`/api/cluster/apply`); a new cluster step that changes links must run inside `cluster_batch`.
- **AI config assistant:** deferred. Do not build it unless the owner explicitly asks.
- **Cluster: no multi-hop relays.** A cluster member is an exit only: every cluster inbound keeps `proxy: DIRECT` (`cluster_listeners`), so traffic from another panel leaves directly and A -> B -> A cannot loop (Mihomo's loopback detector only catches a core dialing itself). Do not remove it, and do not add chained relays (A -> B -> C); the owner decided they are not needed.
- **The root `README.md` / `README.en.md` must not mention the historical test repository or any other internal repository name.** Compatibility logic for older installs from that repository exists in the code; do not delete it, but do not put it in user docs.
- Do not add features, options, subcommands, or extra scope on your own. Do not do work that was not requested.
- Do not rewrite user docs to “explain the design”; keep them short. This handoff guide is for agents; do not copy its process notes into the README.
- This repository is public: do not put private server addresses, domains, passwords, accounts, or internal tooling details in the repo.
