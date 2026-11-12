"""ClashGate panel i18n (server side): translate Chinese API messages to English on request.

Source strings in panel.py stay Chinese (default). When the request language is "en"
(cookie clashgate_lang=en, or Accept-Language starting with en when no cookie), messages are
mapped through TABLE. "{}" is a placeholder; captured parts are translated recursively.
Unmapped text falls back to the original Chinese.
"""
import json
import os
import re

TABLE = [
    ("SNI 无效，请填写域名，或留空从内置域名池随机抽取", "Invalid SNI. Enter a domain, or leave it blank to pick a random domain from the built-in pool"),
    ("Reality 密钥对生成失败：{}", "Failed to generate the Reality key pair: {}"),
    ("VLESS 加密密钥生成失败：{}", "Failed to generate the VLESS encryption keys: {}"),
    ("无法解析字段：{}", "Cannot parse field: {}"),
    ("YAML 列表缩进不一致：{}", "Inconsistent YAML list indentation: {}"),
    ("YAML 映射缩进不一致：{}", "Inconsistent YAML mapping indentation: {}"),
    ("无效的 YAML 行：{}", "Invalid YAML line: {}"),
    ("请输入 Mihomo 节点配置（单行 JSON 或多行 YAML）", "Enter a Mihomo node config (single-line JSON or multi-line YAML)"),
    ("节点配置为空", "The node config is empty"),
    ("无法解析第 {} 行附近的配置：{}", "Cannot parse the config near line {}: {}"),
    ("仅支持 Mihomo 节点配置格式（单行 JSON 或多行 YAML）", "Only the Mihomo node config format is supported (single-line JSON or multi-line YAML)"),
    ("未找到任何节点配置", "No node config found"),
    ("每个节点必须是键值对对象（需包含 name 与 type）", "Each node must be a key-value object (with name and type)"),
    ("节点缺少必填字段：{}", "Node is missing a required field: {}"),
    ("节点「{}」端口无效：{}", "Node “{}” has an invalid port: {}"),
    ("请输入有效的 HTTP/HTTPS 订阅链接", "Enter a valid HTTP/HTTPS subscription URL"),
    ("订阅源名称仅限 1-48 位字母、数字及 . _ -", "Provider name: 1-48 letters, digits and . _ - only"),
    ("未知的入站类型", "Unknown inbound type"),
    ("{} 启用 TLS 需要域名证书，未找到 {}（请先在服务器执行 clashgate cert）", "{} with TLS needs a domain certificate, but {} was not found (run clashgate cert on the server first)"),
    ("端口无效（1-65535）", "Invalid port (1-65535)"),
    ("端口 {} 已被占用", "Port {} is already in use"),
    ("名称仅限 1-48 位字母、数字及 . _ -", "Name: 1-48 letters, digits and . _ - only"),
    ("入站名称「{}」已存在", "Inbound name “{}” already exists"),
    ("TrustTunnel 用户名无效（1-32 位字母、数字及 . _ -）", "Invalid TrustTunnel username (1-32 letters, digits and . _ -)"),
    ("配置校验失败（mihomo -t）：{}", "Config validation failed (mihomo -t): {}"),
    ("重启失败：{}", "Restart failed: {}"),
    ("请输入完整的 Mihomo 服务端配置内容", "Enter the complete Mihomo server config"),
    ("不支持的 CPU 架构：{}", "Unsupported CPU architecture: {}"),
    ("GitHub 接口请求失败（HTTP {}）", "GitHub API request failed (HTTP {})"),
    ("无法连接 GitHub，请检查服务器网络（{}）", "Cannot reach GitHub; check the server network ({})"),
    ("未能从 GitHub 解析最新版本号", "Could not parse the latest version from GitHub"),
    ("解析 GitHub 返回的版本数据失败", "Failed to parse the version data returned by GitHub"),
    ("未能从 GitHub 获取 Mihomo 最新版本标签", "Could not get the latest Mihomo release tag from GitHub"),
    ("已是最新版本 {}，无需更新", "Already on the latest version {}; no update needed"),
    ("GitHub 版本 {} 中未找到 {}", "{1} not found in GitHub release {0}"),
    ("下载内核文件失败（HTTP {}）", "Failed to download the core file (HTTP {})"),
    ("下载内核文件超时或网络中断，请稍后重试（{}）", "Core download timed out or the network dropped; try again later ({})"),
    ("解压内核文件失败：{}", "Failed to extract the core file: {}"),
    ("下载的 Mihomo 内核无法运行：{}", "The downloaded Mihomo core cannot run: {}"),
    ("重启 Mihomo 失败：{}", "Failed to restart Mihomo: {}"),
    ("Snell V6 需要 Mihomo 内核 v{} 或更高版本，请先点击顶部「更新内核」", "Snell V6 needs Mihomo core v{} or later; click “Update core” at the top first"),
    ("配置校验失败（mihomo -t），已保留原内核：{}", "Config validation failed (mihomo -t); the current core was kept: {}"),
    ("重启 Mihomo 失败，已恢复原内核：{}", "Failed to restart Mihomo; the previous core was restored: {}"),
    ("Mihomo 内核已从 {} 更新至 {} 并重启生效。", "Mihomo core updated from {} to {} and restarted."),
    ("Mihomo 内核已更新至 {} 并重启生效。", "Mihomo core updated to {} and restarted."),
    ("正在后台检查并更新 Mihomo 内核，请稍候…", "Checking for and updating the Mihomo core in the background, please wait…"),
    ("更新内核失败：{}", "Core update failed: {}"),
    ("更新内核完成", "Core update finished"),
    ("更新内核失败", "Core update failed"),
    ("请求体过大（超过 8MB 限制）", "Request body too large (over the 8MB limit)"),
    ("登录会话已过期，请刷新页面重新登录", "Your session has expired; refresh the page and sign in again"),
    ("会话校验失败，请刷新页面重试", "Session check failed; refresh the page and try again"),
    ("会话校验失败", "Session check failed"),
    ("页面已过期，请刷新后重试。", "The page has expired; refresh and try again."),
    ("页面不存在", "Page not found"),
    ("请检查地址是否正确。", "Check that the address is correct."),
    ("返回控制台", "Back to console"),
    ("尝试次数过多，请 10 分钟后再试。", "Too many attempts; try again in 10 minutes."),
    ("用户名或密码错误。", "Wrong username or password."),
    ("登录 · ClashGate", "Sign in · ClashGate"),
    ("登 录", "Sign in"),
    ("重启", "restart"),
    ("重载", "reload"),
    ("配置校验未通过，未执行{}：{}", "Config validation failed; {} not performed: {}"),
    ("重载成功，服务端配置与客户端订阅已同步生效（Mihomo 当前状态：{}）", "Reload succeeded; the server config and client subscription are in effect (Mihomo state: {})"),
    ("重启成功，服务端配置与客户端订阅已同步生效（Mihomo 当前状态：{}）", "Restart succeeded; the server config and client subscription are in effect (Mihomo state: {})"),
    ("重载失败：{}（Mihomo 当前状态：{}）", "Reload failed: {} (Mihomo state: {})"),
    ("重启失败：{}（Mihomo 当前状态：{}）", "Restart failed: {} (Mihomo state: {})"),
    ("运行中", "running"), ("已停止", "stopped"), ("失败", "failed"), ("启动中", "starting"),
    ("停止中", "stopping"), ("重载中", "reloading"), ("未知", "unknown"),
    ("订阅链接已更换，旧订阅链接已失效。", "Subscription link changed; the old link is no longer valid."),
    ("已记录更换订阅链接，请点顶部「重载配置」生效（重载后旧订阅链接失效）。", "Subscription link change recorded; click “Reload config” at the top to apply (the old link will expire after reload)."),
    ("重置密钥失败：{}", "Failed to reset the secret: {}"),
    ("已重置 Zashboard API 密钥，链接已同步更新。", "Zashboard API secret reset; links updated."),
    ("已生成新 Zashboard API 密钥，请点顶部「重载配置」生效（重载后直连地址才会更新）。", "New Zashboard API secret generated; click “Reload config” at the top to apply (direct URL updates after reload)."),
    ("+ 添加节点「{}」（端口 {}）", "+ Add node “{}” (port {})"),
    ("- 删除节点「{}」", "- Delete node “{}”"),
    ("~ 重置密码「{}」", "~ Reset password “{}”"),
    ("~ 重置 API 密钥", "~ Reset API secret"),
    ("~ 更换订阅链接", "~ Change subscription link"),
    ("+ 添加服务端出站「{}」", "+ Add server outbound “{}”"),
    ("- 删除服务端出站「{}」", "- Delete server outbound “{}”"),
    ("+ 导入订阅源「{}」", "+ Import provider “{}”"),
    ("- 删除订阅源「{}」", "- Delete provider “{}”"),
    ("证书检查 / 续期完成。", "Certificate check / renewal finished."),
    ("证书申请 / 续期失败：{}", "Certificate request / renewal failed: {}"),
    ("发现新版本 v{}（当前 v{}）", "New version v{} found (current v{})"),
    ("当前已是最新版本（v{}）", "Already on the latest version (v{})"),
    ("发现新版本 v{}（当前 v{}，通道：{}）", "New version v{} found (current v{}, channel: {})"),
    ("发现新版本 v{}（当前 v{}，通道：{}，{}）", "New version v{} found (current v{}, channel: {}, {})"),
    ("当前已是最新版本（v{}，通道：{}）", "Already on the latest version (v{}, channel: {})"),
    ("已切换到测试通道，请点「检查更新」。", "Switched to the test channel. Click “Check for updates”."),
    ("已切换到正式通道，请点「检查更新」。", "Switched to the stable channel. Click “Check for updates”."),
    ("测试", "test"),
    ("正式", "stable"),
    ("版本检查失败：{}", "Version check failed: {}"),
    ("版本检查失败", "Version check failed"),
    ("检查更新失败：无法连接 GitHub 获取最新版本（{}）", "Update check failed: cannot reach GitHub for the latest version ({})"),
    ("升级失败：未找到 clashgate 管理脚本", "Upgrade failed: clashgate management script not found"),
    ("升级失败：{}", "Upgrade failed: {}"),
    ("已开始升级，完成后面板会自动重启并刷新（约 1 分钟）……", "Upgrade started. The panel will restart and refresh automatically when done (about 1 minute)…"),
    ("升级正在进行中，请稍候……", "An upgrade is already in progress, please wait…"),
    ("升级成功！ClashGate 与 Mihomo 内核已更新至最新版本。", "Upgrade succeeded! ClashGate and the Mihomo core are up to date."),
    ("已添加 {} 节点「{}」（端口 {}），已保存，请点顶部「重载配置」生效", "Added {} node “{}” (port {}). Saved; click “Reload config” at the top to apply"),
    ("节点名称重复，添加失败", "Duplicate node name; add failed"),
    ("添加失败：{}", "Add failed: {}"),
    ("节点删除成功，重载配置生效", "Node deleted; applies on reload"),
    ("删除失败：{}", "Delete failed: {}"),
    ("已删除", "Deleted"),
    ("已删除节点「{}」，请点顶部「重载配置」生效", "Deleted node “{}”. Click “Reload config” at the top to apply"),
    ("入站节点不存在", "Inbound node does not exist"),
    ("已重置节点「{}」的 UUID、Reality 私钥与 VLESS 加密密钥，重载配置生效", "Reset the UUID, Reality private key and VLESS encryption keys of node “{}”; applies on reload"),
    ("该入站协议无需密码，不支持重置密码", "This inbound protocol has no password; password reset is not supported"),
    ("重置密码失败：{}", "Failed to reset the password: {}"),
    ("密码重置成功，重载配置生效", "Password reset; applies on reload"),
    ("添加服务端 proxies 节点失败：{}", "Failed to add server proxies nodes: {}"),
    ("已添加 {} 个服务端出站（{}），已保存，请点顶部「重载配置」生效", "Added {} server outbound(s) ({}). Saved; click “Reload config” at the top to apply"),
    ("删除服务端节点失败：{}", "Failed to delete the server node: {}"),
    ("导入订阅链接失败：{}", "Failed to import the subscription link: {}"),
    ("已导入订阅源「{}」（路径 {}），已保存，请点顶部「重载配置」生效", "Imported provider “{}” (path {}). Saved; click “Reload config” at the top to apply"),
    ("删除订阅源失败：{}", "Failed to delete the provider: {}"),
    ("已删除订阅源「{}」，请点顶部「重载配置」生效", "Deleted provider “{}”. Click “Reload config” at the top to apply"),
    ("切换回默认服务端模板失败：{}", "Failed to switch back to the default server template: {}"),
    ("已关闭自定义服务端，已切换回默认服务端模板并重载生效。", "Custom server turned off; switched back to the default server template and reloaded."),
    ("已自动配置 {} 处证书路径，自定义 Mihomo 服务端配置已通过校验并应用生效。", "Auto-configured {} certificate path(s); the custom Mihomo server config passed validation and is now in effect."),
    ("已开启自定义服务端。上次的自定义配置已载入编辑框，点「更新 Mihomo 服务端配置」即可恢复。", "Custom server enabled. Your last custom config is loaded in the editor; click “Update Mihomo server config” to restore it."),
    ("证书文件不存在或无法读取：{}", "Certificate file not found or not readable: {}"),
    ("已关闭自定义服务端。原有节点无法用默认模板生成，已重置为默认服务端模板并生成新的 VlessReality 节点，请在客户端更新订阅。", "Custom server turned off. The previous nodes could not be built with the default template, so the server was reset to the default template with a new VlessReality node. Update the subscription in your client."),
    ("更新自定义服务端配置失败：{}", "Failed to update the custom server config: {}"),
    ("自定义 Mihomo 服务端配置已通过校验并应用生效。", "The custom Mihomo server config passed validation and is now in effect."),
    ("恢复默认配置失败：{}", "Failed to restore the default config: {}"),
    ("已恢复默认服务端配置，并生成默认 VlessReality 节点。", "Default server config restored and a default VlessReality node generated."),
    ("请先在服务器上执行 clashgate", "Run clashgate on the server first"),
    ("已丢弃待重载草稿", "Discarded pending draft"),
    ("丢弃草稿失败：{}", "Failed to discard draft: {}"),
    ("当前密码错误", "Current password is incorrect"),
    ("新密码长度至少 8 位", "New password must be at least 8 characters"),
    ("两次输入的新密码不一致", "The two new passwords do not match"),
    ("面板密码已修改", "Panel password updated"),
    ("密码太短（至少 8 位）", "Password too short (at least 8 characters)"),
    ("请输入 Cloudflare API Token", "Enter the Cloudflare API Token"),
    ("API Token 不能包含空格或引号", "The API Token must not contain spaces or quotes"),
    ("不支持的证书模式", "Unsupported certificate mode"),
    ("已切换为 Cloudflare DNS 续证模式，证书申请 / 续期完成。", "Switched to Cloudflare DNS renewal mode; certificate request / renewal finished."),
    ("已切换为端口续证模式，证书检查 / 续期完成。", "Switched to port renewal mode; certificate check / renewal finished."),
    ("未切换证书模式，未重新生成证书。", "Certificate mode was not changed, so the certificate was not regenerated."),
    ("已切换并重新生成证书。", "Switched mode and regenerated the certificate."),
    ("重新生成证书失败：80 端口被占用。端口模式需要临时使用 80 端口，请释放该端口，或改用 Cloudflare DNS。", "Certificate regeneration failed: port 80 is in use. Port mode needs port 80 briefly. Free it, or use Cloudflare DNS."),
    ("重新生成证书失败：Cloudflare API Token 无效，或没有该域名的 DNS 编辑权限。{}", "Certificate regeneration failed: the Cloudflare API Token is invalid or lacks DNS edit permission for this domain. {}"),
    ("重新生成证书失败：{}", "Certificate regeneration failed: {}"),
    ("设置项无效", "Invalid setting"),
    ("已开启自定义服务端。", "Custom server enabled."),
    ("已关闭自定义服务端。", "Custom server disabled."),
    ("已开启每周自动更新。更新面板时会同时更新 Mihomo 内核。", "Weekly automatic updates are on. Updating the panel also updates the Mihomo core."),
    ("已关闭每周自动更新。", "Weekly automatic updates are off."),
    ("设置已保存。", "Settings saved."),
    ("高级功能请到设置页开启", "This is an advanced feature. Enable it on the Settings page."),

    ("+ 添加服务端出站「{}」", "+ Add server outbound “{}”"),
    ("- 删除服务端出站「{}」", "- Delete server outbound “{}”"),
    ("+ 添加分流组「{}」", "+ Add routing group “{}”"),
    ("- 删除分流组「{}」", "- Delete routing group “{}”"),
    ("+ 引入分流组「{}」", "+ Import routing group “{}”"),
    ("~ 重命名分流组「{}」→「{}」", "~ Rename routing group “{}” → “{}”"),
    ("~ 调整分流顺序", "~ Reorder routing groups"),
    ("~ 更新分流组「{}」", "~ Update routing group “{}”"),
    ("恢复默认服务端模板", "Restore default server template"),
    ("加入服务端出站", "Add to server outbounds"),

    ("正在向 Cloudflare 注册 MASQUE，完成后点「加入服务端出站」。", "Registering a Cloudflare MASQUE node. Click “Add to server outbounds” when it is ready."),
    ("订阅源「{}」已存在，请换一个名称或先删除原订阅源", "Provider “{}” already exists; choose another name or delete the existing one first"),
    ("不支持分享链接（如 vless://、ss://），请粘贴 Mihomo 配置格式（JSON 或 YAML；订阅链接请在「外部订阅源」中导入）", "Share links (vless://, ss://, ...) are not supported; paste the Mihomo config format (JSON or YAML). Import subscription URLs under “External providers”."),
    ("没有可用的随机端口", "No free random port available"),
    ("请检查域名解析、Token 权限或 80 端口是否被占用", "Check the domain's DNS records, the token permissions, or whether port 80 is in use"),
    ("X25519 公钥生成失败", "Failed to generate the X25519 public key"),
    ("注册响应里没有边缘公钥", "The registration response has no edge public key"),
    ("边缘公钥格式无法识别", "Unrecognized edge public key format"),
    ("边缘公钥不是合法的 PEM 或 Base64", "The edge public key is not valid PEM or Base64"),
    ("Cloudflare 注册接口返回 {}：{}", "Cloudflare registration API returned {}: {}"),
    ("Cloudflare 注册接口返回格式异常", "Unexpected response format from the Cloudflare registration API"),
    ("Cloudflare 注册接口返回了无法解析的内容", "The Cloudflare registration API returned unparsable content"),
    ("无法连接 Cloudflare 注册接口：{}", "Cannot reach the Cloudflare registration API: {}"),
    ("Cloudflare 注册响应缺少设备 id 或 token", "The Cloudflare registration response lacks the device id or token"),
    ("注册成功但没有返回 MASQUE 接入地址", "Registered, but no MASQUE endpoint was returned"),
    ("注册成功但没有返回隧道 IPv4", "Registered, but no tunnel IPv4 was returned"),
    ("未能从 GitHub 解析通道提交", "Could not resolve the channel commit from GitHub"),
    ("已添加分流组「{}」，已保存，请点顶部「重载配置」生效", "Added routing group “{}”. Saved; click “Reload config” at the top to apply"),
    ("已引入分流组「{}」，已保存，请点顶部「重载配置」生效", "Imported routing group “{}”. Saved; click “Reload config” at the top to apply"),
    ("已删除分流组「{}」，请点顶部「重载配置」生效", "Deleted routing group “{}”; click “Reload config” at the top to apply"),
    ("已重命名分流组为「{}」，请点顶部「重载配置」生效", "Renamed the routing group to “{}”; click “Reload config” at the top to apply"),
    ("{}，请点顶部「重载配置」生效", "{}; click “Reload config” at the top to apply"),
    ("已调整分流顺序，请点顶部「重载配置」生效", "Routing order changed; click “Reload config” at the top to apply"),
    ("已更新分流组「{}」规则，请点顶部「重载配置」生效", "Updated the rules of routing group “{}”; click “Reload config” at the top to apply"),
    ("已更新分流组「{}」，请点顶部「重载配置」生效", "Updated routing group “{}”; click “Reload config” at the top to apply"),
    ("+ 分流组「{}」添加规则集「{}」", "+ Add rule set “{1}” to routing group “{0}”"),
    ("- 分流组「{}」删除规则集「{}」", "- Remove rule set “{1}” from routing group “{0}”"),
    ("~ 更新分流组「{}」规则", "~ Update rules of routing group “{}”"),
    ("请填写分流组名称", "Enter a routing group name"),
    ("请粘贴至少一条分流规则（如 - DOMAIN-SUFFIX,example.com）", "Paste at least one routing rule (e.g. - DOMAIN-SUFFIX,example.com)"),
    ("请至少粘贴一条分流规则（如 - DOMAIN-SUFFIX,example.com）", "Paste at least one routing rule (e.g. - DOMAIN-SUFFIX,example.com)"),
    ("请填写外部规则集 URL", "Enter an external rule-set URL"),
    ("缺少分流组 id", "Missing routing group id"),
    ("分流配置组装失败：{}", "Failed to assemble the routing config: {}"),
    ("添加分流组失败：{}", "Failed to add the routing group: {}"),
    ("引入分流规则失败：{}", "Failed to import routing rules: {}"),
    ("删除分流组失败：{}", "Failed to delete the routing group: {}"),
    ("重命名分流组失败：{}", "Failed to rename the routing group: {}"),
    ("修改规则集失败：{}", "Failed to change the rule set: {}"),
    ("调整分流顺序失败：{}", "Failed to change the routing order: {}"),
    ("更新分流规则失败：{}", "Failed to update routing rules: {}"),
    ("更新分流组失败：{}", "Failed to update the routing group: {}"),
    ("自定义配置模式下请在自定义服务端里修改", "In custom config mode, edit this on the Custom server page"),
    ("order 必须是数组", "order must be an array"),
    ("分流组不存在", "Routing group not found"),
    ("自定义分流无法解析", "Custom routing cannot be parsed"),
    ("新建分流组请粘贴 DOMAIN / IP 等经典规则；外部分流规则集请用「引入外部分流」", "For a new group paste classical rules such as DOMAIN / IP; for external rule sets use “Import external routing”"),
    ("MATCH 由系统自动生成，请勿粘贴", "MATCH is generated automatically; do not paste it"),
    ("规则格式无效：{}（示例：- DOMAIN-SUFFIX,example.com）", "Invalid rule: {} (example: - DOMAIN-SUFFIX,example.com)"),
    ("不支持的规则类型「{}」。请使用 DOMAIN-SUFFIX / DOMAIN-KEYWORD / IP-CIDR 等经典规则", "Unsupported rule type “{}”. Use classical rules such as DOMAIN-SUFFIX / DOMAIN-KEYWORD / IP-CIDR"),
    ("routing.json 格式无效", "routing.json is invalid"),
    ("分流 YAML 顶层必须是映射（rule-providers / proxy-groups / rules）", "The routing YAML top level must be a mapping (rule-providers / proxy-groups / rules)"),
    ("rule-providers 必须是映射", "rule-providers must be a mapping"),
    ("proxy-groups 必须是列表", "proxy-groups must be a list"),
    ("rules 必须是列表", "rules must be a list"),
    ("rules 中的每条规则必须是字符串", "Every entry in rules must be a string"),
    ("proxy-groups 每项必须包含 name 与 type", "Every proxy-groups entry needs name and type"),
    ("rule-provider「{}」格式无效", "rule-provider “{}” is invalid"),
    ("rule-provider「{}」缺少 type", "rule-provider “{}” has no type"),
    ("rule-provider 名称冲突：{}", "rule-provider name conflict: {}"),
    ("分流组缺少 proxy-groups", "The routing group has no proxy-groups"),
    ("分流组必须包含 proxy-groups", "A routing group must contain proxy-groups"),
    ("分流组名称不能为空", "The routing group name cannot be empty"),
    ("分流组名称过长", "The routing group name is too long"),
    ("分流组名称已存在：{}", "Routing group name already exists: {}"),
    ("外部规则集 URL 必须以 http(s):// 开头", "The external rule-set URL must start with http(s)://"),
    ("分流组「{}」不可删除", "Routing group “{}” cannot be deleted"),
    ("规则集名称只能用英文字母、数字、- _ .", "Rule-set names may only use letters, digits, - _ ."),
    ("规则集 URL 必须以 http(s):// 开头", "The rule-set URL must start with http(s)://"),
    ("规则类型无效", "Invalid rule type"),
    ("格式无效", "Invalid format"),
    ("规则集不存在", "Rule set not found"),
    ("规则集名称已存在：{}", "Rule-set name already exists: {}"),
    ("分流顺序必须包含全部现有分流组", "The routing order must include every existing group"),
    ("外部分流组请用规则集管理，不能粘贴经典规则", "External routing groups are managed with rule sets; classical rules cannot be pasted"),
    ("无法解析第 {} 行附近：{}", "Cannot parse near line {}: {}"),
    ("无法解析自定义配置中的 rule-providers / proxy-groups / rules", "Cannot parse rule-providers / proxy-groups / rules in the custom config"),
    ("自定义服务端分流无法解析：{}", "Custom server routing cannot be parsed: {}"),
    ("分流组「{}」添加规则集「{}」", "Added rule set “{1}” to routing group “{0}”"),
    ("分流组「{}」删除规则集「{}」", "Removed rule set “{1}” from routing group “{0}”"),
]

_COMPILED = []
for _zh, _en in TABLE:
    _parts = _zh.split("{}")
    _rx = re.compile("(.*?)".join(re.escape(p) for p in _parts), re.S)
    _COMPILED.append((len("".join(_parts)), _rx, _zh, _en, len(_parts) - 1))
_COMPILED.sort(key=lambda x: -x[0])
_CJK = re.compile(r"[\u4e00-\u9fff]")
_LANGS = ("zh", "en", "ru", "fa")


def _load_server(code: str) -> dict:
    path = os.path.join(os.path.dirname(__file__), "web", "src", "locales", f"{code}.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    server = data.get("server") if isinstance(data, dict) else {}
    return server if isinstance(server, dict) else {}


_EXTRA = {"ru": _load_server("ru"), "fa": _load_server("fa")}


def _fill(en: str, caps):
    def sub(m):
        return caps[int(m.group(1))] if m.group(1) else None
    # positional {0}/{1} or sequential {}
    if re.search(r"\{\d+\}", en):
        return re.sub(r"\{(\d+)\}", lambda m: caps[int(m.group(1))], en)
    it = iter(caps)
    return re.sub(r"\{\}", lambda m: next(it, ""), en)


def tr(msg, lang="zh"):
    """Translate a Chinese API message when lang is en, ru, or fa."""
    if lang not in ("en", "ru", "fa") or not isinstance(msg, str) or not _CJK.search(msg):
        return msg
    for _n, rx, zh, en, ncap in _COMPILED:
        m = rx.fullmatch(msg)
        if m:
            text = en if lang == "en" else (_EXTRA.get(lang, {}).get(zh) or en)
            return _fill(text, [tr(c, lang) for c in m.groups()])
    return msg


def detect_lang(cookie_header: str = "", accept_language: str = "") -> str:
    for part in (cookie_header or "").split(";"):
        k, _, v = part.strip().partition("=")
        if k == "clashgate_lang":
            code = v.strip().lower().split("-")[0]
            return code if code in _LANGS else "zh"
    first = (accept_language or "").split(",")[0].strip().lower().split(";")[0]
    code = first.split("-")[0]
    if code in ("en", "ru", "fa"):
        return code
    return "zh"
