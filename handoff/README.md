# ClashGate 智能体交接文档

本文档面向后续接手开发的智能体，说明产品原则、仓库结构、发布流程与必须遵守的约定，以便无缝接管后续版本。当前版本 **1.31**，下一版本号为 **1.32**。公开仓库：https://github.com/ClashGate/ClashGate

---

## 1. 项目定位与产品原则

ClashGate 是给小白用的 Mihomo 代理服务端，重点是简单，不追求 100% 功能。

- **替用户做选择**。不要自行增加选项、子命令、解释性旁白或额外职责范围。事情越多，bug 越多。
- **对外输出与文档保持最少**。不要解释“为什么”；解释过多是错误。
- **安装时一次性装好所有依赖**（包括地理数据 `geoip.metadb`、`GeoSite.dat`、`ASN.mmdb`），不能等到用户用到某功能才报错。
- **更新必须自动修好已有安装**，不能要求用户再执行手工步骤。
- **UI 粗糙处直接改**，不必先问。卡片与表单保持对称。强调色 `#1d6fe0`。品牌图标为猫。
- **管理面板语言**：中文 / English / Русский / فارسی，默认中文。安装程序与命令行：中文 / English / Русский（`clashgate lang` 或 `CLASHGATE_LANG`）。
- 许可证：MIT。

---

## 2. 架构与目录

统一安装目录是 `/etc/clashgate`。管理命令是 `/usr/local/bin/clashgate`（指向已安装的 `scripts/cmd/clashgate.sh`）。内核二进制是 `/etc/clashgate/mihomo`，以 `mihomo` 用户运行。面板在证书模式下自行提供 HTTPS（与内核共用 `/etc/clashgate/certs`），**不用 Caddy，也不用反向代理**。

### 安装模式

- **无证书模式**（`MODE=no-cert`）：只生成 VLESS Reality 节点，安装后输出客户端配置。
- **自动证书模式**（`MODE=auto-cert`）：需要域名；用 Let's Encrypt 申请并续期证书，提供 HTTPS 管理面板和订阅链接。
- **手动证书模式**（`MODE=auto-cert` 且 `CERT_MODE=manual`）：使用用户自备证书，校验通过后同样提供面板和订阅。

证书方式（`CERT_MODE`，均可在面板「HTTPS 证书」页切换）：

| 值 | 名称 | 说明 |
| --- | --- | --- |
| `port` | 端口模式（默认） | 申请/续期时临时占用 80 端口 |
| `dns` | DNS API 模式 | Cloudflare API Token，不必开放 80，支持 `*.` 泛域名 |
| `manual` | 手动证书 | 用户把证书放到 `/etc/clashgate/certs/`，不申请、不续期 |

默认证书来源是 Let's Encrypt 正式环境（`TLS=production`）。不要给用户签发“正式自签证书”当生产方案。申请失败时 `certctl.sh` 可写入临时自签证书，只为让面板和内核先起来；`TLS=internal` 仅开发用，不走 ACME。

订阅地址：`https://<域名>:<面板端口>/sub/<token>/mihomo.yaml`（文件名 `mihomo.yaml` 可以保留）。

入站协议（面板可添加）：VLESS Reality、Shadowsocks、Hysteria2、Snell v6、AnyTLS、TUIC、TrustTunnel、ShadowQUIC、Mieru、Sudoku、HTTP、SOCKS5。

### systemd 服务

| 单元 | 作用 |
| --- | --- |
| `mihomo.service` | 内核。启动前执行 `mihomo -t -d /etc/clashgate -f /etc/clashgate/config.yaml` |
| `clashgate.service` | 管理面板（仅证书模式）。`python3 /etc/clashgate/panel/panel.py serve --config /etc/clashgate/panel.json` |
| `clashgate-cert.service` / `clashgate-cert.timer` | 每小时调用 `certctl.sh renew` |

### 仓库目录（源码）

| 路径 | 作用 |
| --- | --- |
| `install.sh` | 一键安装入口。`curl\|bash` 时从 GitHub 下载对应分支 tarball，再交给 `scripts/cmd/clashgate.sh` 执行安装。语言：`CLASHGATE_LANG=zh\|en\|ru` 或交互选择，写入 `/etc/clashgate/clashgate.env` |
| `uninstall.sh` | 等同于 `clashgate uninstall` |
| `scripts/cmd/clashgate.sh` | CLI 与安装/更新/卸载主流程 |
| `scripts/lib/common.sh` | 版本常量、路径、环境持久化、`install_files`、更新通道 |
| `scripts/lib/core.sh` | 依赖、下载内核、`ensure_geodata`、渲染配置、systemd、本机防火墙放行（若启用了 ufw/firewalld） |
| `scripts/lib/cert.sh` | 证书预检、DNS 检查、手动证书、调用 acme 申请 |
| `scripts/lib/acme.sh` | 固定版本安装 acme.sh（3.1.6，目录 `/etc/clashgate/acme.sh`） |
| `scripts/lib/panel.sh` | 面板 unit、订阅 URL、面板密码 |
| `scripts/lib/i18n.sh`、`i18n.en.tsv`、`i18n.ru.tsv` | 安装程序与 CLI 的翻译 |
| `scripts/certctl.sh` | `issue` / `renew` / `deploy`；面板调用时输出固定为中文，便于解析失败原因。CLI 语言随 `CLASHGATE_LANG` |
| `scripts/init/` | 上述三个 systemd 单元（及 cert timer）的模板 |
| `panel/panel.py` | 面板入口（Python 3.9+，只用标准库）。子命令：`serve`、`hash-password`、`cluster-leave`（卸载时退出集群） |
| `panel/cg_http.py` | HTTPS 服务与 API（含 `do_check_update`） |
| `panel/cg_config.py` | 节点/入站/配置生成、`ensure_geodata`、`validate_config`（`mihomo -t`） |
| `panel/cg_update.py` | 流量统计、内核更新、面板自升级、通道检查 |
| `panel/cg_cluster.py` | 集群协议 |
| `panel/cg_cert.py` | 把配置里的证书路径改写到本项目证书 |
| `panel/cg_yaml.py` | YAML 读写 |
| `panel/cg_masque.py` | Cloudflare MASQUE 注册 |
| `panel/cg_qr.py` | 二维码 |
| `panel/routing_mgr.py` | 服务端分流：`/etc/clashgate/routing/` + `routing.json`，组装进模板 |
| `panel/i18n_en.py` | 服务端 API 文案英译（源字符串保持中文） |
| `panel/web/` | Vue 3 + Tailwind 前端源码（`package.json` 的 version 为 `1.31.0`） |
| `panel/dist/` | **已提交的构建产物**。改前端后必须 `cd panel/web && npm ci && npm run build`，并把 `panel/dist` 的变更一并提交（CI 用 `git diff --exit-code -- panel/dist` 校验） |
| `resources/server.yaml.tpl`、`resources/client.yaml.tpl` | 服务端 / 客户端配置模板 |
| `resources/routing/` | 默认分流组（节点选择、漏网之鱼） |
| `resources/brand/logo.png` | 品牌图标 |
| `tests/` | 测试（见第 7 节） |
| `.github/workflows/ci.yml` | 每次 push / PR 跑 `tests/run.sh` |
| `handoff/` | 本交接文档。不列入 `CS_TREE_PARTS`，不会安装到机器上 |

`install_files` 只会原子替换这些顶层项（`CS_TREE_PARTS`）：`install.sh`、`uninstall.sh`、`panel`、`resources`、`scripts`。配置、证书、内核二进制和地理数据会保留。

### 运行时重要路径（均在 `/etc/clashgate`）

`config.yaml`（当前服务端配置）、`custom_config.yaml`（用户自定义整份配置）、`clashgate.env`、`panel.json`、`certs/fullchain.pem` 与 `privkey.pem`、`client/`、`nodes.tsv`、各类 `*.yaml` 片段（controller / listeners / proxies / routing / cluster）、`inbounds.json`、`cluster.json`、`routing.json`、`routing/`、地理数据文件。

---

## 3. 当前 CLI 命令（v1.31）

不带参数：已安装则打开管理菜单，未安装则进入安装。`clashgate help` 查看全部子命令。

| 命令 | 说明 |
| --- | --- |
| `clashgate status` | 查看运行状态 |
| `clashgate info` | 查看节点配置 |
| `clashgate log` | 查看最近日志 |
| `clashgate restart` | 校验配置后重启内核 |
| `clashgate sub` | 查看订阅链接（仅证书模式） |
| `clashgate reset-sub` | 更换订阅链接，旧链接立即失效（仅证书模式） |
| `clashgate reset-password` | 随机重置面板密码（仅证书模式） |
| `clashgate update` | 同时更新内核、脚本与面板（面板「升级」与自动更新也调用它） |
| `clashgate lang [zh\|en\|ru]` | 切换并保存命令行语言（不带参数则从列表选择） |
| `clashgate install` | 重新安装（按提示选择模式） |
| `clashgate uninstall` | 卸载：若在集群中则先退出集群，然后删除安装。**不管防火墙端口**（不要再加关闭放行端口的逻辑） |
| `clashgate help` | 帮助 |

已删除、不要加回来：`clashgate passwd`、`clashgate reset-secret`、`clashgate cert`，以及拆开的 `update core` / `update self`。改面板密码、重置 Zashboard 密钥、管理证书，都在面板里完成。

开发/测试用隐藏参数（不要写入用户文档）：`--domain`、`--cert-mode port|dns|manual`、`--cf-token`、`--panel-port`、`--controller-port`、`--staging` / `--tls-staging`、`--production`、`--tls-internal`。测试证书时用 staging 或复用已有证书，**禁止在测试中向 Let's Encrypt 正式环境重新签发**。

---

## 4. Mihomo 相关约定

- 遵循 [Mihomo 官方文档](https://wiki.metacubex.one/en/)。
- **下游名称不要出现 “mihomo”**（用户可见的产品名是 ClashGate）。订阅文件名 `mihomo.yaml` 可以保留；内核二进制、`mihomo.service`、内核家目录属于内核自身，不在此列。
- **禁止** 在下发的客户端配置里写 `skip-cert-verify`（生成时会删掉该字段；测试也会检查源码中不得出现 `skip-cert-verify: true`）。
- **不要做 CDN 模式**。
- Mihomo v1.19 使用 `geoip.metadb`（不是只依赖旧的 `country.mmdb`）。安装和 `clashgate update` 都会调用 `ensure_geodata`，用系统 curl 预先下载 `geoip.metadb`、`GeoSite.dat`、`ASN.mmdb` 到 `/etc/clashgate`。面板启动和 `validate_config` 也会补齐缺失文件。
- 面板与脚本做 `mihomo -t` 时，必须在临时目录里**链接**这些地理数据（以及 certs、ruleset 等），不能让内核在校验阶段自己下载（它的内置 DNS 此时可能解析失败）。

测试套件钉死的内核版本见 `tests/run.sh` 中的 `MIHOMO_VERSION`（当前 `v1.19.34`）。

---

## 5. 分支与发布流程

仓库默认对外分支是 `main`（正式）。`test` 是测试通道。

1. 在 `test` 上开发并推送。**每次推到 `test` 的功能/修复都必须升版本号**（文字或文档-only 改动除外，见下）。
2. 项目负责人在真实机器上验收（负责人自己在面板点「检查更新」）。
3. **只有负责人明确同意后，才能推 `main`。** 未验收通过的版本号作废，不得复用。

版本号按**每一段的整数**比较（`parse_version_tuple`）：`1.09 < 1.10 < 1.31`。**永远不要写成 `1.1` 或 `1.2`**（会排在 `1.09` 前面）。下一个是 `1.32`、`1.33`，依此类推。

提交说明用英文。**禁止 force push。**

**文字或文档-only 改动**：不跑测试、不等 CI，可以直接推。`test` 与 `main` 已经分叉，不要用合并来带文档；在两个分支上分别提交同一文件。此类改动**不要升版本号**。本次 `handoff/` 即按此规则处理。

### 把已验收的 `test` 合入 `main`（分支已分叉，不能快进）

在 `origin/main` 上建 worktree，然后：

```bash
git merge --no-ff --no-commit -s ours origin/test
git read-tree -m -u origin/test
git checkout origin/main -- .github
```

再把默认分支改回 `main`：

- `install.sh` 头部 URL：`.../ClashGate/main/install.sh`
- `install.sh` 中 `${REPO_BRANCH:-main}`
- `scripts/lib/common.sh` 中 `REPO_BRANCH=${REPO_BRANCH:-main}`

（`test` 分支上这三处默认值是 `test`，合入时必须改回来，否则正式安装会去拉 `test`。）

然后 commit，`git push origin HEAD:main`。不要 force push。

`test` 与 `main` 的内容差异通常只有上述默认分支，以及 `.github`（保留 `main` 上的工作流历史）。

---

## 6. 版本号修改位置与检查更新

升版本时必须同时改下列位置（以 1.31 为例）：

| 位置 | 写法 |
| --- | --- |
| `README.md`、`README.en.md` 的 version badge | `v1.31` |
| `panel/panel.py` 文件头 docstring 与 `VERSION` | `v1.31` / `"1.31"` |
| `panel/routing_mgr.py` 文件头 docstring | `1.31` |
| `panel/web/package.json` 与 `package-lock.json` | `1.31.0`（三段） |
| `scripts/lib/common.sh` 的 `CS_VERSION` | `1.31` |
| 同文件 `CS_SOURCE_SHA` | `YYYYMMDD-vX.YY`（如 `20261120-v1.31`） |
| `tests/test_panel.py` 的版本顺序列表 | 把新版本追加进 `order` |
| `tests/golden/subscription.yaml` 首行注释 | `Generated by ClashGate v1.31...` |

`common.sh` 与 `panel.py` 顶部的版本比较注释也要跟着改到新版本，并写明下一个版本号。

### 面板「检查更新」机制

`panel/cg_update.py` 的 `fetch_channel_tip()`：

1. 按当前通道解析仓库与分支：正式 → `ClashGate/ClashGate@main`，测试 → `ClashGate/ClashGate@test`。
2. 先请求 GitHub commits API 取该分支 tip SHA，再读取该 commit 上的 `scripts/lib/common.sh` 原文（避免 raw 按分支名读取时被缓存约 5 分钟）。失败则回退到按分支名读取。
3. 从文件中解析 `CS_VERSION`（以及 `CS_SOURCE_SHA`）。
4. `check_panel_update()` 用 `parse_version_tuple` 比较，只有**严格更新**的版本才算有更新。

`POST /action/check-update` 由 `cg_http.py` 的 `do_check_update` 处理；异常时返回 **400**，文案为「检查更新失败：无法连接 GitHub 获取最新版本（…）」。服务器必须能访问 GitHub。

面板升级实际执行的是脱离面板进程的 `clashgate update`（更新会重启面板服务本身，不能在请求内同步跑完）。

---

## 7. 测试

本地一次性跑完全部测试：

```bash
tests/run.sh            # 全量（含前端构建校验）
tests/run.sh --no-build # 跳过前端构建
```

流程：`bash -n` 全部脚本 → `shellcheck`（警告级，排除 SC2034；CI 中没有 shellcheck 则失败）→ 如无 `MIHOMO_BIN` 则下载钉死版本的内核到 `tests/.cache` → 预下载地理数据到 `tests/.cache/geo` → `python3 -m unittest discover -s tests -v` → `python3 tests/cluster_e2e.py` → 前后端 i18n 对账 → 前端 `npm run build` 且 `panel/dist` 必须与提交内容一致。

主要测试文件：`tests/test_panel.py`（假的 `/etc/clashgate` 树 + `mihomo -t`）、`tests/test_seed_load.py`（脚本 import 面板的路径）、`tests/cluster_e2e.py`（本机多面板 HTTPS 集群，使用一次性 CA，不申请真实证书）、`tests/check_i18n.py`、`tests/check_shell_i18n.py`。`tests/node-check.sh` 是发版前用订阅在本地客户端测节点，不是 CI 的一部分。

CI：`.github/workflows/ci.yml`，`ubuntu-24.04`，Node 24，每次 push 和 pull request 执行 `tests/run.sh`。修改 `.github` 需要带 `workflow` 权限的 token；若 `git push` 被拒，改用 GitHub 网页编辑该文件。

测试**不得**向 Let's Encrypt 正式环境重新签发证书：用 `--staging` / 复用已有证书 / 测试夹具中的一次性 CA。重装会保留 acme.sh 账户和已签发证书，避免触发频率限制。

---

## 8. 版本历史摘要（近期）

| 版本 | 要点 |
| --- | --- |
| 1.24 | 安装程序与 CLI 语言 zh/en/ru，新增 `clashgate lang` |
| 1.25 | `certctl` 输出跟随 CLI 语言；面板调用时固定中文以便解析 |
| 1.26 | README「常用命令」改为分组表格 |
| 1.27 | 删除「系统要求」；「一键安装」只保留命令本身 |
| 1.28 | 只保留 `clashgate update`，去掉 `update core` / `update self` |
| 1.29 | 删除 CLI 的 `passwd`、`reset-secret`、`cert`；卸载只负责退出集群，不再关闭防火墙端口 |
| 1.30 | 安装过程检查步骤默认只打标题，失败才输出细节；结尾摘要缩短 |
| 1.31 | 安装/更新预下载地理数据；校验临时目录链接地理文件；面板补齐缺失文件；Reality SNI 随机池去掉 yahoo |

下一版本：**1.32**。

---

## 9. 暂缓 / 不要做

- **AI 配置助手**：已暂缓，除非负责人明确要求，否则不要做。
- **根目录 README / README.en.md 禁止提及历史测试仓库或其它内部仓库名。** 代码里对旧测试仓库安装有兼容逻辑，不要删，但不要写进用户文档。
- 不要主动加功能、加选项、加子命令或扩大职责。没被要求的事不要做。
- 不要改用户文档的语气去“讲清楚原理”；保持短。本交接文档是给智能体的，不要把其中的流程说明搬进 README。
- 本仓库是公开的：不要把私人服务器地址、域名、密码、账号或内部工具细节写进仓库。
