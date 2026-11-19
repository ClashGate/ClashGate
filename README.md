<h1 align="center">ClashGate</h1>

<p align="center"><b>中文</b> · <a href="README.en.md">English</a></p>

<p align="center">ClashGate · 采用 Mihomo 核心简单安全的代理服务端</p>

<p align="center">
  <img alt="Platform: Linux" src="https://img.shields.io/badge/platform-Ubuntu%20%7C%20Debian%20%7C%20Rocky%20%7C%20Alma%20%7C%20Fedora%20%7C%20CentOS-blue" />
  <img alt="Init: systemd" src="https://img.shields.io/badge/init-systemd-blue" />
  <img alt="Version: v1.24" src="https://img.shields.io/badge/version-v1.24-1d6fe0" />
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-green" /></a>
</p>

## 能做什么

- **一条命令装好服务端**：在常见 Linux VPS 上一键部署 Mihomo 服务端，装完直接输出客户端可用的配置。
- **两种安装模式**：
  - 无证书模式：只要一台服务器，自动生成 VLESS Reality 节点，最快上手；
  - 自动证书模式：再准备一个域名，自动申请并续期 Let's Encrypt 证书，额外提供 HTTPS 管理面板和订阅链接。
- **三种证书方式**：端口模式（通过 80 端口验证）、Cloudflare DNS（不用开放 80 端口）、手动上传自己的证书，都能在面板里随时切换。
- **多种协议**：VLESS Reality、Shadowsocks、Hysteria2、Snell v6、AnyTLS、TUIC、TrustTunnel、ShadowQUIC、Mieru、Sudoku，在面板里点几下即可添加。
- **订阅链接**：Mihomo / Clash 系客户端直接导入，节点有变动时客户端更新订阅即可，不用手动拼配置。
- **服务端分流**：在面板中按规则把不同网站分到不同出口；高级用户也可以换成自己的服务端配置。
- **集群**：把多台 ClashGate 服务器连在一起，一个订阅链接同时包含所有服务器的节点。
- **省心维护**：面板一键检查更新，可开启自动更新；内核更新、证书续期都会自动处理，还有运行状态面板（Zashboard）。
- **多语言界面**：管理面板支持中文、English、Русский、فارسی，安装程序和命令行支持中文、English、Русский（`clashgate lang` 切换）。

## 系统要求

- 带 systemd 的 Linux（x86_64 / arm64 / armv7），需要 root 权限；
- 推荐 Debian 11+、Ubuntu 20.04+、Rocky / Alma 8+、Fedora；
- 自动证书模式（带管理面板）需要 Python 3.9 或更高版本：Rocky / Alma 8 会自动安装新版 Python；更老的系统（如 CentOS 7）只能使用无证书模式；
- 自动证书模式还需要一个解析到本服务器的域名。使用 Cloudflare 时请把这条记录设为灰云（DNS only）。

## 一键安装

```bash
curl -fsSL https://raw.githubusercontent.com/ClashGate/ClashGate/main/install.sh | bash
```

安装开始时先选择语言（1 中文 / 2 English / 3 Русский，回车使用默认值：已保存的语言，或按系统 `LANG` 判断），然后按提示选择安装模式、证书方式并填写域名。选择的语言会保存下来，之后的 `clashgate` 命令都用这个语言；首次打开管理面板时也默认用它（浏览器里选过语言的以浏览器为准）。

- 想跳过语言选择：`curl -fsSL …/install.sh | CLASHGATE_LANG=en bash`（可选 `zh` / `en` / `ru`）；
- 没有交互终端（如自动化脚本）时不会提问，直接使用 `CLASHGATE_LANG` 或系统 `LANG`；
- 波斯语（فارسی）只在管理面板中提供，终端对从右到左文字显示不好，所以安装程序和命令行不提供。

## 常用命令

安装后执行 `clashgate`（不带参数，或 `clashgate menu`）打开交互菜单，菜单里的每一项都对应下面的一个子命令；`clashgate help` 列出全部子命令。除 `help` 外都需要 root 权限。标注「证书模式」的命令只在自动证书或手动证书模式（带管理面板）下可用。

### 安装与升级

| 命令 | 作用 | 什么时候用 | 说明 |
| --- | --- | --- | --- |
| `curl -fsSL …/install.sh \| bash` | 一键安装 | 第一次在服务器上安装 | 先选语言，再选模式：1 无证书模式（只有 VLESS Reality 节点）、2 自动证书模式（Let's Encrypt，端口模式或 Cloudflare DNS API）、3 手动证书模式（自备证书）。证书模式会随机分配面板和 Zashboard 的空闲高端口，安装完成后打印订阅链接、面板地址和一次性显示的密码 |
| `clashgate install` | 重新安装 | 想换安装模式，或想把节点全部重新生成 | 会先确认，然后卸载旧安装再重装：节点和密钥重新生成；已加入集群时先退出集群。同一域名已签发的证书和 acme.sh 账户会保留并复用，一般不会重新申请。只能在终端里运行 |
| `clashgate update` | 更新内核 + 脚本与面板 | 想升级到最新版本 | 下载当前更新通道的最新代码替换脚本、面板和模板（配置、证书、节点都保留），重新生成配置，通过 `mihomo -t` 校验后重启；新配置校验失败时保留原配置。更新通道在面板「设置」里切换：正式（GitHub `main` 分支）/ 测试（`test` 分支） |
| `clashgate update core` | 只更新 Mihomo 内核 | 只想升级内核 | 下载最新稳定版 Mihomo，校验配置后重启 |
| `clashgate update self` | 只更新脚本与面板 | 内核不想动，只更新 ClashGate | 同 `update`，但不更新内核 |

示例：

```bash
clashgate update          # 内核 + 脚本与面板
clashgate update core     # 只更新内核
```

### 服务

| 命令 | 作用 | 什么时候用 | 说明 |
| --- | --- | --- | --- |
| `clashgate status` | 查看运行状态 | 日常检查、排查问题 | 显示安装模式、Mihomo 运行状态与版本、面板地址和端口、证书到期时间与上次自动续期结果、Zashboard 地址与 API 密钥，以及每个节点端口是否在监听 |
| `clashgate restart` | 重启内核 | 手动改了配置，或节点异常 | 先用 `mihomo -t` 校验当前配置，校验不通过就不重启（避免把服务停掉） |
| `clashgate log` | 查看最近日志 | 排查连接、证书或面板问题 | 显示 Mihomo 最近 50 行日志；证书模式下再显示面板和证书任务最近 30 行 |

### 订阅与节点

| 命令 | 作用 | 什么时候用 | 说明 |
| --- | --- | --- | --- |
| `clashgate info` | 查看节点配置 | 手动配置客户端，或查看订阅链接 | 打印所有节点的 `proxies` 片段（含面板里添加的节点）、客户端配置目录 `/etc/clashgate/client/`；证书模式下还显示面板、Zashboard 和订阅链接 |
| `clashgate sub` | 查看订阅链接 | 把订阅导入 Mihomo / Clash 客户端（证书模式） | 链接本身就是凭证，不要外泄 |
| `clashgate reset-sub` | 更换订阅链接 | 订阅链接泄露了（证书模式） | **立即生效**：旧链接马上失效（返回 404），所有客户端都要改用新链接 |

### 证书

| 命令 | 作用 | 什么时候用 | 说明 |
| --- | --- | --- | --- |
| `clashgate cert` | 立即申请 / 续期 / 校验证书 | 安装时证书没签发成功、换了证书文件、想马上检查证书（证书模式） | 按当前证书方式处理：**端口模式**临时使用 80 端口验证（域名 A 记录要指向本机、放行 TCP 80）；**DNS API 模式**用 Cloudflare API Token 验证（不占用 80/443，支持 `*.泛域名`）；**手动证书模式**只校验 `/etc/clashgate/certs/` 里的 `fullchain.pem` 与 `privkey.pem`（是否有效、是否包含域名、与私钥是否匹配）并重启内核加载。自动证书已签发时，只在到期前 30 天内才会真正续期；平时每小时自动检查一次，一般不需要手动执行 |

证书方式（端口 / DNS API / 手动）可以在面板的「HTTPS 证书」页切换。

### 面板

| 命令 | 作用 | 什么时候用 | 说明 |
| --- | --- | --- | --- |
| `clashgate passwd` | 修改面板密码（自定义） | 想设置自己的密码（证书模式） | 需要在终端中输入两次，至少 8 位；修改后所有已登录的浏览器都要重新登录 |
| `clashgate reset-password` | 重置面板密码（随机） | 忘记面板密码（证书模式） | 生成 20 位随机密码并打印出来；所有已登录的浏览器都要重新登录 |
| `clashgate reset-secret` | 重置 Zashboard API 密钥（随机） | 密钥泄露，或想更换（证书模式） | 生成新密钥并重启内核，旧密钥立即失效，Zashboard 需要用新密钥重新连接 |

用户名固定为 `admin`。面板地址和端口可用 `clashgate status` 或 `clashgate info` 查看。

### 语言

| 命令 | 作用 | 什么时候用 | 说明 |
| --- | --- | --- | --- |
| `clashgate lang` | 从列表选择命令行语言 | 想换命令行语言 | 交互菜单里的「语言 / Language」也是这个功能 |
| `clashgate lang zh\|en\|ru` | 直接切换命令行语言 | 同上，或在脚本里设置 | 保存到 `/etc/clashgate/clashgate.env`（`CLASHGATE_LANG`），之后的命令都使用它，管理面板也把它作为默认语言（浏览器里选过语言的不受影响） |

临时用另一种语言运行一次：`CLASHGATE_LANG=en clashgate status`（只对这一次有效，不会保存）。

### 卸载

| 命令 | 作用 | 什么时候用 | 说明 |
| --- | --- | --- | --- |
| `clashgate uninstall` | 卸载 | 不再使用 ClashGate | 先确认；已加入集群时会**先退出集群**（通知其他成员删除这台服务器，没收到通知的成员会列出来，需要到它们的面板手动删除）；**关闭安装时在 ufw / firewalld 里放行的端口**（你原来自己放行的规则不动）；然后删除 Mihomo、管理面板、证书（含 acme.sh）、配置和客户端文件。云服务商安全组里的规则需要自己删除 |

### 环境变量

| 变量 | 作用 |
| --- | --- |
| `CLASHGATE_LANG=zh\|en\|ru` | 安装时跳过语言选择；平时只对当前这一次命令生效（保存的语言用 `clashgate lang` 修改） |
| `REPO_BRANCH=test` | 安装时从 `test` 分支（测试通道）下载，例如 `curl -fsSL …/install.sh \| REPO_BRANCH=test bash`；安装后的更新通道在面板「设置」里切换 |

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
