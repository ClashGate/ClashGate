"""ClashGate panel i18n (server side): translate Chinese API messages to English on request.

Source strings in panel.py stay Chinese (default). When the request language is "en"
(cookie clashgate_lang=en, or Accept-Language starting with en when no cookie), messages are
mapped through TABLE. "{}" is a placeholder; captured parts are translated recursively.
Unmapped text falls back to the original Chinese.
"""
import re

TABLE = [
    ("没有可用的随机端口", "No random port available"),
    ("Reality 密钥对生成失败：{}", "Failed to generate the Reality key pair: {}"),
    ("VLESS 加密密钥生成失败：{}", "Failed to generate the VLESS encryption keys: {}"),
    ("无法解析字段：{}", "Cannot parse field: {}"),
    ("YAML 列表缩进不一致：{}", "Inconsistent YAML list indentation: {}"),
    ("YAML 映射缩进不一致：{}", "Inconsistent YAML mapping indentation: {}"),
    ("无效的 YAML 行：{}", "Invalid YAML line: {}"),
    ("请输入 mihomo 节点配置（单行 JSON 或多行 YAML）", "Enter a mihomo node config (single-line JSON or multi-line YAML)"),
    ("不支持分享链接（如 vless://、ss://），请粘贴 mihomo 配置格式（JSON 或 YAML；若是订阅链接请在上方「导入外部订阅」中添加）",
     "Share links (vless://, ss://, ...) are not supported; paste the mihomo config format (JSON or YAML; for a subscription URL use “Import external subscription” above)"),
    ("节点配置为空", "The node config is empty"),
    ("无法解析第 {} 行附近的配置：{}", "Cannot parse the config near line {}: {}"),
    ("仅支持 mihomo 节点配置格式（单行 JSON 或多行 YAML）", "Only the mihomo node config format is supported (single-line JSON or multi-line YAML)"),
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
    ("请输入完整的 mihomo 服务端配置内容", "Enter the complete mihomo server config"),
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
    ("+ 添加出站节点「{}」", "+ Add outbound node “{}”"),
    ("- 删除出站节点「{}」", "- Delete outbound node “{}”"),
    ("+ 导入订阅源「{}」", "+ Import provider “{}”"),
    ("- 删除订阅源「{}」", "- Delete provider “{}”"),
    ("证书检查 / 续期完成。", "Certificate check / renewal finished."),
    ("证书申请 / 续期失败：{}", "Certificate request / renewal failed: {}"),
    ("发现新版本 v{}（当前 v{}）", "New version v{} found (current v{})"),
    ("当前已是最新版本（v{}）", "Already on the latest version (v{})"),
    ("检查更新失败：无法连接 GitHub 获取最新版本（{}）", "Update check failed: cannot reach GitHub for the latest version ({})"),
    ("升级失败：未找到 clashgate 管理脚本", "Upgrade failed: clashgate management script not found"),
    ("升级失败：{}", "Upgrade failed: {}"),
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
    ("已向服务端 proxies: 添加 {} 个节点（{}），已保存，请点顶部「重载配置」生效", "Added {} node(s) to server proxies: ({}). Saved; click “Reload config” at the top to apply"),
    ("删除服务端节点失败：{}", "Failed to delete the server node: {}"),
    ("导入订阅链接失败：{}", "Failed to import the subscription link: {}"),
    ("已导入订阅源「{}」（路径 {}）到服务端 proxy-providers:，已保存，请点顶部「重载配置」生效", "Imported provider “{}” (path {}) into server proxy-providers:. Saved; click “Reload config” at the top to apply"),
    ("删除订阅源失败：{}", "Failed to delete the provider: {}"),
    ("已删除订阅源「{}」，请点顶部「重载配置」生效", "Deleted provider “{}”. Click “Reload config” at the top to apply"),
    ("更新自定义服务端配置失败：{}", "Failed to update the custom server config: {}"),
    ("自定义 mihomo 服务端配置已通过校验并应用生效。", "The custom mihomo server config passed validation and is now in effect."),
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
]

_COMPILED = []
for _zh, _en in TABLE:
    _parts = _zh.split("{}")
    _rx = re.compile("(.*?)".join(re.escape(p) for p in _parts), re.S)
    _COMPILED.append((len("".join(_parts)), _rx, _zh, _en, len(_parts) - 1))
_COMPILED.sort(key=lambda x: -x[0])
_CJK = re.compile(r"[\u4e00-\u9fff]")


def _fill(en: str, caps):
    def sub(m):
        return caps[int(m.group(1))] if m.group(1) else None
    # positional {0}/{1} or sequential {}
    if re.search(r"\{\d+\}", en):
        return re.sub(r"\{(\d+)\}", lambda m: caps[int(m.group(1))], en)
    it = iter(caps)
    return re.sub(r"\{\}", lambda m: next(it, ""), en)


def tr(msg, lang="zh"):
    """Translate msg to English when lang == 'en'; otherwise return unchanged."""
    if lang != "en" or not isinstance(msg, str) or not _CJK.search(msg):
        return msg
    for _n, rx, _zh, en, ncap in _COMPILED:
        m = rx.fullmatch(msg)
        if m:
            return _fill(en, [tr(c, lang) for c in m.groups()])
    return msg


def detect_lang(cookie_header: str = "", accept_language: str = "") -> str:
    for part in (cookie_header or "").split(";"):
        k, _, v = part.strip().partition("=")
        if k == "clashgate_lang":
            return "en" if v.strip().lower().startswith("en") else "zh"
    return "zh"
