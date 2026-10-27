#!/usr/bin/env bash
# clashgate 管理命令（安装后链接为 /usr/local/bin/clashgate）
# 不带参数：已安装 -> 管理菜单（中文/English）；未安装 -> 安装。clashgate help 查看全部子命令。
set -Eeuo pipefail

ORIG_ARGS=("$@")
CS_HOME=$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/../.." && pwd)
for _lib in common core cert panel; do
  # shellcheck source=/dev/null
  . "$CS_HOME/scripts/lib/$_lib.sh"
done
trap 'die "第 $LINENO 行执行失败：$BASH_COMMAND"' ERR
if [[ -n ${CS_BOOTSTRAP_TMP:-} ]]; then trap 'rm -rf "$CS_BOOTSTRAP_TMP"' EXIT; fi

usage() {
  if [[ $CS_LANG == en ]]; then
    cat <<EOF
ClashGate (clashgate) - proxy server management command (v$CS_VERSION)

Usage: clashgate [subcommand]
  (no argument)     open the interactive menu
  status            show status (services, ports, certificate)
  info              show node config (proxies snippet, client config dir, subscription link)
  sub               show the subscription link (certificate modes)
  reset-sub         change the subscription link; the old link stops working immediately
  passwd            change the panel password (custom)
  reset-password    reset the panel password (random)
  reset-secret      reset the Zashboard API secret (random)
  cert              request / renew / validate the certificate now
  restart           restart the core
  update            update core + scripts and panel (update core / update self updates only one)
  log               show recent logs
  uninstall         uninstall
  install           reinstall (choose the mode when prompted)
  help              show this help

Language: set CLASHGATE_LANG=en|zh (default: zh, or en when LANG starts with en)
One-click install: curl -fsSL $INSTALL_RAW_URL | bash
EOF
    return 0
  fi
  cat <<EOF
ClashGate (clashgate) —— 代理服务端管理命令 (v$CS_VERSION)

用法：clashgate [子命令]
  （不带参数）       打开交互菜单
  status            查看运行状态（服务、端口、证书）
  info              查看节点配置（proxies 片段、客户端配置目录、订阅链接）
  sub               查看订阅链接（证书模式）
  reset-sub         更换订阅链接，旧链接立即失效
  passwd            修改面板密码（自定义）
  reset-password    重置面板密码（随机生成）
  reset-secret      重置 Zashboard API 密钥（随机生成）
  cert              立即申请 / 续期 / 校验证书
  restart           重启内核
  update            更新内核 + 自身脚本与面板（update core / update self 只更新其一）
  log               查看最近日志
  uninstall         卸载
  install           重新安装（按提示选择模式）
  help              显示本帮助

语言：CLASHGATE_LANG=en|zh（默认中文；LANG 以 en 开头时为英文）
一键安装：curl -fsSL $INSTALL_RAW_URL | bash
EOF
}

interactive_setup() {
  has_tty || return 0
  local menu=0 c
  if ((!MODE_SET)); then
    menu=1
    printf '\n\033[1mClashGate v%s 一键安装\033[0m\n\n' "$CS_VERSION"
    printf '请选择安装模式：\n'
    printf '  1) 无证书模式（默认）：仅 VLESS Reality 节点，安装后输出客户端配置\n'
    printf '  2) 自动证书模式：自动申请 Let'\''s Encrypt 证书（端口模式 / DNS API），提供 HTTPS 管理面板和订阅链接\n'
    printf '  3) 手动证书模式：使用自备域名证书，校验通过后提供 HTTPS 管理面板和订阅链接\n'
    while :; do
      c=$(ask '请输入 [1/2/3]（回车默认 1）：' 1)
      case $c in
        1) MODE=no-cert; break ;;
        2) MODE=auto-cert; break ;;
        3) MODE=auto-cert; CERT_MODE=manual; CERT_MODE_SET=1; break ;;
        *) printf '请输入 1、2 或 3\n' ;;
      esac
    done
  fi
  [[ $MODE == auto-cert ]] || return 0
  if ((!CERT_MODE_SET)) && ((menu)); then
    printf '\n请选择证书方式：\n'
    printf '  1) 端口模式（默认）：申请/续期时临时占用 80 端口（需将域名解析到本机并放行 TCP 80）\n'
    printf '  2) DNS API 模式：使用 Cloudflare API Token 验证（无需占用 80/443 端口，支持 *.泛域名）\n'
    while :; do
      c=$(ask '请输入 [1/2]（回车默认 1）：' 1)
      case $c in
        1) CERT_MODE=port; break ;;
        2) CERT_MODE=dns; break ;;
        *) printf '请输入 1 或 2\n' ;;
      esac
    done
  fi
  if [[ $CERT_MODE == manual ]]; then
    while [[ -z $DOMAIN || ! ${DOMAIN,,} =~ $WILDCARD_DOMAIN_RE ]]; do
      [[ -n $DOMAIN ]] && printf '域名格式不正确：%s\n' "$DOMAIN"
      DOMAIN=$(ask '请输入证书对应的域名（如 example.com）：' '')
    done
    printf '手动证书目录路径：\033[1;36m%s/certs/\033[0m（安装过程中将提示放入 fullchain.pem 与 privkey.pem 并检测有效性）\n' "$CONF_DIR"
  elif [[ $CERT_MODE == dns ]]; then
    while [[ -z $DOMAIN || ! ${DOMAIN,,} =~ $WILDCARD_DOMAIN_RE ]]; do
      [[ -n $DOMAIN ]] && printf '域名格式不正确：%s\n' "$DOMAIN"
      DOMAIN=$(ask '请输入域名（如 example.com 或 *.example.com）：' '')
    done
    while [[ -z $CF_TOKEN || $CF_TOKEN =~ [[:space:]\"\'] ]]; do
      [[ -n $CF_TOKEN ]] && printf 'API Token 不能包含空格或引号\n'
      CF_TOKEN=$(ask '请输入 Cloudflare API Token（需具备该域名的 DNS 编辑权限）：' '')
    done
  else
    while [[ -z $DOMAIN || ! ${DOMAIN,,} =~ $DOMAIN_RE ]]; do
      if [[ $DOMAIN == \*.* ]]; then
        printf '通配符域名仅支持「DNS API 模式」或「手动证书模式」，请输入具体域名\n'
      elif [[ -n $DOMAIN ]]; then
        printf '域名格式不正确：%s\n' "$DOMAIN"
      fi
      DOMAIN=$(ask '请输入域名（需已将 A 记录解析到本机）：' '')
    done
  fi
  ((menu)) || return 0   # 开发用隐藏参数 -d 启动时不再追问
  [[ -n $PANEL_PORT ]] || PANEL_PORT=$(rand_port)
  [[ -n $CONTROLLER_PORT ]] || CONTROLLER_PORT=$(rand_port)
  printf '已分配管理面板随机空闲高端口：%s\n' "$PANEL_PORT"
  printf '已分配 Zashboard 控制接口随机空闲高端口：%s\n' "$CONTROLLER_PORT"
  # 证书通知邮箱默认直接跳过，不再询问
  return 0
}

check_existing() {
  [[ -f $STATE ]] || return 0
  if has_tty; then
    [[ $(ask '检测到已安装 ClashGate，是否卸载后重新安装？节点和密钥都会重新生成 [y/N]：' n) == [yY]* ]] \
      || { printf '已取消。查看现有节点：clashgate info\n'; exit 0; }
  else
    die "已安装（存在 $STATE）。查看节点：clashgate info；如需重装请在终端中运行 clashgate install"
  fi
  printf '正在卸载旧的安装……\n'
  ( CS_IN_REINSTALL=1 do_uninstall ) >/dev/null
}

# ------------------------------------------------------------ verify / output
verify() {
  log "检查运行状态"
  sleep 2
  systemctl is-active --quiet mihomo || { journalctl -u mihomo -n 20 --no-pager >&2; die "mihomo 服务未能启动"; }
  local name port rest ss_out
  ss_out=$(ss -ltn 2>/dev/null || true)
  while IFS=$'\t' read -r name port rest; do
    grep -q ":$port " <<<"$ss_out" || die "节点 $name 未在端口 $port 监听"
    info "监听中：$name :$port"
  done < "$STATE"
  [[ $MODE == auto-cert ]] || return 0
  grep -q ":$CONTROLLER_PORT " <<<"$ss_out" || die "Mihomo 控制接口未在端口 $CONTROLLER_PORT 监听"
  info "Zashboard：$(zashboard_url) 正常"
  local i h p sub_body
  h=$(panel_host); p=$(panel_port)
  for ((i = 0; i < 10; i++)); do panel_https_ok /healthz >/dev/null && break; sleep 1; done
  ((i < 10)) || { journalctl -u clashgate -n 20 --no-pager >&2; die "面板未在 $p 端口响应 HTTPS"; }
  info "面板：$(panel_url)（端口 $p）正常（面板自身 HTTPS，证书与 Mihomo 共用）"
  sub_body=$(panel_https_ok "/sub/$SUB_TOKEN/mihomo.yaml" || true)
  grep -q 'proxies:' <<<"$sub_body" || die "订阅接口没有返回 mihomo 配置"
  [[ $(curl -sk -o /dev/null -w '%{http_code}' --resolve "$h:$p:127.0.0.1" \
    "$(panel_url)/sub/wrongtoken0000000000000000/mihomo.yaml") == 404 ]] || die "订阅接口未拒绝错误的 token"
  info "订阅链接：$(sub_url) 正常"
}

print_summary() {
  printf '\n\033[1;32m✔ 安装完成！（ClashGate v%s）\033[0m\n\n' "$CS_VERSION"
  printf '请在云服务商的防火墙 / 安全组放行以下 TCP 端口：'
  if [[ $MODE == auto-cert ]]; then
    [[ ${CERT_MODE:-port} == port ]] && printf ' 80'
    [[ $PANEL_PORT == 80 && ${CERT_MODE:-port} == port ]] || printf ' %s' "$PANEL_PORT"
    printf ' %s' "$CONTROLLER_PORT"
  fi
  awk -F'\t' '{printf " %s", $2}' "$STATE"; printf '\n'
  if [[ $MODE == auto-cert ]]; then
    printf '\n\033[1mmihomo 订阅链接\033[0m（导入 mihomo / Clash 客户端即可；链接即凭证，泄露后执行 clashgate reset-sub 更换）：\n'
    printf '  \033[1;36m%s\033[0m\n' "$(sub_url)"
    if [[ ${CERT_MODE:-port} != manual && $TLS != production ]]; then
      printf '  注意：当前为%s，客户端可能拒绝下载订阅\n' "$(tls_label)"
    fi
    printf '\n\033[1m管理面板\033[0m\n'
    printf '  地址：%s\n  端口：%s（随机空闲高端口，请确保防火墙已放行 TCP %s）\n  用户名：admin\n' "$(panel_url)" "$(panel_port)" "$(panel_port)"
    [[ -n $PANEL_PASS ]] && printf '  密码：%s（仅显示一次；可用 clashgate passwd 修改）\n' "$PANEL_PASS"
    printf '  证书方式：%s\n' "$(cert_mode_label)"
    printf '  证书：%s\n' "$(tls_label)"
    if [[ ${CERT_MODE:-port} != manual ]] && cert_is_temp; then
      printf '  \033[1;33m证书尚未签发成功，当前为临时自签证书；检查配置后可执行 clashgate cert 立即重试\033[0m\n'
    fi
    printf '\n统一安装目录：%s（本地客户端备份：%s）\n' "$CS_ROOT" "$CLIENT_DIR"
  else
    printf '\n\033[1m客户端 proxies 片段\033[0m\n'
    cat "$CLIENT_DIR/proxies.yaml"
    printf '\n\033[1m客户端配置目录\033[0m：%s\n' "$CLIENT_DIR"
    printf '  - mihomo-client.yaml（完整 mihomo 客户端配置）\n  - proxies.yaml（仅节点片段）\n'
  fi
  printf '\n管理：运行 \033[1mclashgate\033[0m 打开中文管理菜单（clashgate help 查看全部子命令）\n'
  if ((${#WARNINGS[@]})); then
    printf '\n\033[1;33m需要注意：\033[0m\n'; printf '  - %s\n' "${WARNINGS[@]}"
  fi
}

# ------------------------------------------------------------ actions
do_install() {
  check_os
  if [[ $CS_HOME -ef $LIB_DIR ]]; then # 从已安装副本运行（clashgate install）：先复制出来，避免重装时删掉自己
    local tmp
    tmp=$(mktemp -d /tmp/clashgate.XXXXXX)
    for d in install.sh uninstall.sh panel resources scripts; do cp -r "$LIB_DIR/$d" "$tmp/"; done
    CS_BOOTSTRAP_TMP=$tmp CS_DEFAULT_ACTION=install exec bash "$tmp/scripts/cmd/clashgate.sh" "${ORIG_ARGS[@]}"
  fi
  interactive_setup
  check_existing
  if [[ $MODE == auto-cert ]]; then
    TOTAL=$([[ ${CERT_MODE:-port} == manual ]] && echo 10 || echo 11)
  fi
  install_deps
  [[ $MODE == auto-cert ]] && preflight_cert
  detect_ip
  if [[ $MODE == auto-cert ]]; then check_dns; fi   # 尽早检查，解析不对可在装任何东西前退出
  [[ $MODE == auto-cert && -z $MIHOMO_SECRET ]] && MIHOMO_SECRET=$(openssl rand -base64 32 | tr -dc 'A-Za-z0-9' | head -c 20)
  save_env
  install_core; ensure_user; log "安装 ClashGate 文件"; install_files; gen_nodes
  if [[ $MODE == auto-cert ]]; then
    if [[ ${CERT_MODE:-port} == manual ]]; then
      setup_manual_cert
    else
      install_acme; issue_cert
    fi
  fi
  render_server; render_client; setup_service
  if [[ $MODE == auto-cert ]]; then
    setup_panel
  fi
  open_firewall
  verify
  print_summary
}

# clashgate update [core|self]：默认同时更新 Mihomo 内核与 clashgate 自身（脚本、面板、模板、unit）
do_update() {
  require_installed; load_env
  local what=${UPDATE_WHAT:-all}
  STEP=0; TOTAL=$([[ $what == all ]] && echo 4 || echo 3)
  install_deps
  [[ $what == self ]] || install_core
  [[ $what == core ]] || update_self
  log "重启服务"
  validate_conf || die "配置未通过校验（mihomo -t），未重启"
  systemctl restart mihomo
  [[ $MODE == auto-cert ]] && systemctl restart clashgate
  sleep 1
  info "Mihomo：$(svc_state mihomo)"
  return 0
}

update_self() {
  log "更新 ClashGate 脚本与面板"
  local tmp
  tmp=$(mktemp -d /tmp/clashgate.XXXXXX)
  fetch_repo "$tmp"
  CS_HOME=$tmp install_files   # 替换 /etc/clashgate 下的代码子目录；保留配置与证书
  rm -rf "$tmp"
  install -m 644 "$LIB_DIR/scripts/init/mihomo.service" "$UNIT"
  if [[ $MODE == auto-cert ]]; then
    install -m 644 "$LIB_DIR/scripts/init/clashgate.service" /etc/systemd/system/
    if [[ ${CERT_MODE:-port} != manual ]]; then
      install -m 644 "$LIB_DIR/scripts/init/clashgate-cert.service" \
        "$LIB_DIR/scripts/init/clashgate-cert.timer" /etc/systemd/system/
    fi
  fi
  systemctl daemon-reload
  if [[ $MODE == auto-cert && ${CERT_MODE:-port} != manual ]]; then
    systemctl enable clashgate-cert.timer >/dev/null 2>&1 || true
    systemctl restart clashgate-cert.timer || true   # 让新的触发规则立即生效
  fi
  # 用新模板重新组装配置；校验失败则回滚
  cp -a "$CONF" "$CONF.bak"
  render_controller
  save_env
  assemble_config
  if validate_conf; then rm -f "$CONF.bak"; else mv -f "$CONF.bak" "$CONF"; warn "新模板生成的配置未通过校验，已保留原配置"; fi
  render_client >/dev/null 2>&1 || true
  info "ClashGate 已更新到 GitHub main 最新版"
}

do_cert() { # 立即申请 / 续期 / 校验证书
  require_installed; load_env; require_panel
  if [[ ${CERT_MODE:-port} == manual ]]; then
    printf '正在校验手动证书（%s/certs/）……\n' "$CONF_DIR"
    check_manual_cert_files || return 1
    systemctl restart mihomo || true
    printf '手动证书正常：%s，到期 %s（剩余 %s 天）\n' "$(cert_issuer)" "$(cert_enddate)" "$(cert_days_left)"
    return 0
  fi
  printf '正在申请 / 续期证书（%s，%s，%s）……\n' "$DOMAIN" "$(cert_mode_label)" "$(tls_label)"
  if ! "$LIB_DIR/scripts/certctl.sh" renew; then
    if [[ ${CERT_MODE:-port} == dns ]]; then
      printf '\033[1;31m申请 / 续期失败\033[0m：请确认 Cloudflare API Token 具备 %s 的 DNS 编辑权限\n' "${DOMAIN#\*.}"
    else
      printf '\033[1;31m申请 / 续期失败\033[0m：请确认域名 A 记录指向 %s（没有指向别处的 AAAA 记录）、云防火墙放行 TCP 80、80 端口未被占用\n' "$SERVER_IP"
    fi
    return 1
  fi
  if cert_is_temp; then printf '\033[1;31m证书仍未签发\033[0m，请检查配置后重试\n'; return 1; fi
  printf '证书正常：%s，到期 %s（剩余 %s 天；到期前 30 天内自动续期）\n' "$(cert_issuer)" "$(cert_enddate)" "$(cert_days_left)"
}

do_status() {
  require_installed; load_env
  printf '\033[1m运行状态（ClashGate v%s）\033[0m\n' "$CS_VERSION"
  printf '  安装模式：%s\n' "$(mode_label)"
  printf '  统一目录：%s\n' "$CS_ROOT"
  printf '  Mihomo：%s  %s\n' "$(svc_state mihomo)" "$("$BIN" -v 2>/dev/null | head -n1 | awk '{print $3}')"
  if [[ $MODE == auto-cert ]]; then
    if [[ ${CERT_MODE:-port} == manual ]]; then
      printf '  面板：%s（%s，端口 %s）\n' "$(svc_state clashgate)" "$(panel_url)" "$(panel_port)"
    else
      printf '  面板：%s（%s，端口 %s）    证书自动续期：%s\n' "$(svc_state clashgate)" "$(panel_url)" "$(panel_port)" "$(svc_state clashgate-cert.timer)"
    fi
    printf '  Zashboard：%s（端口 %s，API 密钥：%s）\n' "$(zashboard_url)" "$(controller_port)" "${MIHOMO_SECRET:-—}"
    printf '  域名：%s（证书：%s）\n' "$DOMAIN" "$(tls_label)"
    if cert_is_temp; then
      printf '  证书：\033[1;31m尚未签发\033[0m（临时自签证书；可执行 clashgate cert 重试）\n'
    elif [[ -f $CONF_DIR/certs/fullchain.pem ]]; then
      local days; days=$(cert_days_left)
      printf '  证书到期：%s（%s，剩余 %s 天）\n' "$(cert_enddate)" "$(cert_issuer)" "$days"
      if [[ -n $days ]] && ((days < 14)); then
        printf '  \033[1;33m证书即将到期\033[0m：请及时续期或更新证书（clashgate cert）\n'
      fi
    else
      printf '  证书：\033[1;31m缺失\033[0m（执行 clashgate cert）\n'
    fi
    if [[ ${CERT_MODE:-port} != manual ]]; then
      printf '  上次自动续期：%s\n' "$(cert_last_run)"
    fi
  fi
  printf '  节点端口：\n'
  local name port rest
  while IFS=$'\t' read -r name port rest; do
    [[ -n $name ]] || continue
    if ss -ltun | grep -q ":$port "; then printf '    %-18s %-6s \033[1;32m监听中\033[0m\n' "$name" "$port"
    else printf '    %-18s %-6s \033[1;31m未监听\033[0m\n' "$name" "$port"; fi
  done < <(cat "$STATE" 2>/dev/null; jq -r '.[] | "\(.name)\t\(.port)"' "$CS_ETC/inbounds.json" 2>/dev/null)
}

do_info() {
  [[ -f $STATE ]] || die "尚未安装"
  load_env
  detect_ip
  echo "proxies:"
  while IFS=$'\t' read -r name port uuid priv pub sid sni dec enc; do
    [[ -n $name ]] || continue
    echo "    - $(proxy_line "$name" "$port" "$uuid" "$pub" "$sid" "$sni" "${enc:-}")"
  done < "$STATE"
  if [[ -f $CS_ETC/inbounds.json ]]; then
    jq -rc '.[] | (.name // .client.name) as $n | .client | del(.["skip-cert-verify"]) | .name = $n' "$CS_ETC/inbounds.json" 2>/dev/null | while IFS= read -r c; do
      [[ -n $c ]] && echo "    - $c"
    done
  fi
  printf '客户端配置目录：%s\n' "$CLIENT_DIR"
  if [[ $MODE == auto-cert ]]; then
    SUB_TOKEN=$(panel_cfg_get sub_token)
    printf '管理面板：%s（端口 %s，用户名 admin）\n' "$(panel_url)" "$(panel_port)"
    printf 'Zashboard：%s（端口 %s，API 密钥：%s）\n' "$(zashboard_url)" "$(controller_port)" "${MIHOMO_SECRET:-—}"
    [[ -n $SUB_TOKEN ]] && printf '订阅链接：%s\n' "$(sub_url)"
  fi
  return 0
}

do_sub() {
  require_installed; load_env; require_panel
  SUB_TOKEN=$(panel_cfg_get sub_token)
  [[ -n $SUB_TOKEN ]] || die "未找到订阅 token，可执行 clashgate reset-sub 生成"
  printf 'mihomo 订阅链接（链接即凭证，请勿外泄）：\n  %s\n' "$(sub_url)"
}

do_reset_sub() {
  load_env
  [[ $MODE == auto-cert && -f $PANEL_CFG ]] || die "订阅链接仅在自动证书或手动证书模式下提供"
  PANEL_HASH=$(panel_cfg_get password_hash)
  SUB_TOKEN=$(new_sub_token)
  write_panel_cfg
  systemctl restart clashgate
  printf '新的订阅链接（旧链接已失效）：\n  %s\n' "$(sub_url)"
}

do_passwd() {
  require_installed; load_env; require_panel
  has_tty || die "需要在终端中运行；或使用 clashgate reset-password 随机重置"
  local p1 p2
  while :; do
    printf '请输入新密码（至少 8 位）：' >/dev/tty; read -rs p1 </dev/tty; printf '\n' >/dev/tty
    printf '请再次输入：' >/dev/tty; read -rs p2 </dev/tty; printf '\n' >/dev/tty
    if [[ $p1 != "$p2" ]]; then printf '两次输入不一致，请重试\n'
    elif ((${#p1} < 8)); then printf '密码太短，至少 8 位\n'
    else break; fi
  done
  PANEL_HASH=$(printf '%s\n' "$p1" | python3 "$LIB_DIR/panel/panel.py" hash-password)
  SUB_TOKEN=$(panel_cfg_get sub_token)
  write_panel_cfg
  systemctl restart clashgate
  printf '面板密码已修改。登录地址：%s（用户名 admin）\n' "$(panel_url)"
}

do_reset_password() {
  load_env
  [[ $MODE == auto-cert && -f $PANEL_CFG ]] || die "未安装管理面板（仅证书模式提供）"
  set_panel_password
  systemctl restart clashgate
  printf '管理面板：%s\n用户名：admin\n新密码：%s\n' "$(panel_url)" "$PANEL_PASS"
}

do_reset_secret() {
  require_installed; load_env; require_panel
  MIHOMO_SECRET=$(openssl rand -base64 32 | tr -dc 'A-Za-z0-9' | head -c 20)
  save_env
  render_controller
  assemble_config
  validate_conf || die "当前配置未通过校验（mihomo -t），未重启"
  systemctl restart mihomo
  sleep 1
  printf 'Zashboard：%s\n新的 API 密钥（Secret）：%s\n' "$(zashboard_url)" "$MIHOMO_SECRET"
}

do_restart() {
  require_installed
  validate_conf || die "当前配置未通过校验（mihomo -t），未重启"
  systemctl restart mihomo
  sleep 1
  printf 'Mihomo：%s\n' "$(svc_state mihomo)"
}

do_log() {
  require_installed; load_env
  journalctl -u mihomo -n 50 --no-pager
  [[ $MODE == auto-cert ]] && { echo; journalctl -u clashgate -u clashgate-cert -n 30 --no-pager; }
  return 0
}

do_menu() {
  require_installed; load_env
  has_tty || { usage; return 0; }
  local items=() labels=() i c
  items+=(status info);          labels+=("查看运行状态" "查看节点配置")
  if [[ $MODE == auto-cert ]]; then
    items+=(sub reset-sub passwd reset-password reset-secret cert)
    labels+=("查看订阅链接" "更换订阅链接" "修改面板密码（自定义）" "重置面板密码（随机）" "重置 Zashboard 密钥（随机）" "立即申请 / 续期 / 校验证书")
  fi
  items+=(restart log update uninstall); labels+=("重启 Mihomo" "查看日志" "更新（内核 + 脚本）" "卸载")
  while :; do
    printf '\n\033[1mClashGate v%s 管理菜单\033[0m（%s' "$CS_VERSION" "$([[ $MODE == auto-cert ]] && echo "$(mode_label) · $DOMAIN" || echo '无证书模式')"
    printf '）  Mihomo：%s\n' "$(svc_state mihomo)"
    for i in "${!items[@]}"; do printf '  %d) %s\n' "$((i + 1))" "${labels[$i]}"; done
    printf '  0) 退出\n'
    c=$(ask '请选择：' 0)
    [[ $c == 0 ]] && return 0
    if [[ $c =~ ^[0-9]+$ ]] && ((c >= 1 && c <= ${#items[@]})); then
      printf '\n'
      ( STEP=0; "do_${items[$((c - 1))]//-/_}" ) || true
      [[ ${items[$((c - 1))]} == uninstall && ! -f $STATE ]] && return 0
      ask '按回车返回菜单……' '' >/dev/null
    else
      printf '无效选项：%s\n' "$c"
    fi
  done
}

do_uninstall() {
  load_env
  if [[ ${CS_IN_REINSTALL:-0} != 1 ]] && has_tty; then
    [[ $(ask '确定卸载 ClashGate？所有节点、证书和配置都会被删除 [y/N]：' n) == [yY]* ]] || { echo "已取消"; return 0; }
  fi
  systemctl disable --now clashgate clashgate-cert.timer clashgate-cert.service 2>/dev/null || true
  rm -f /etc/systemd/system/clashgate.service /etc/systemd/system/clashgate-cert.{service,timer}
  systemctl disable --now mihomo 2>/dev/null || true
  rm -f "$UNIT" "$BIN" /usr/local/bin/mihomo "$SELF_BIN" /run/clashgate-cert.lock
  systemctl daemon-reload
  local cert_bak="" acme_bak=""
  if [[ ${CS_IN_REINSTALL:-0} == 1 && -d $CONF_DIR/certs ]] && ! cert_is_temp; then
    cert_bak=$(mktemp -d)
    cp -a "$CONF_DIR/certs/." "$cert_bak/" 2>/dev/null || true
  fi
  if [[ ${CS_IN_REINSTALL:-0} == 1 && -d $ACME_HOME ]]; then
    # 重装时保留 acme.sh 账户与已签发证书：同一域名直接复用，避免触发 Let's Encrypt 频率限制（同域名每周 5 张）
    acme_bak=$(mktemp -d)
    cp -a "$ACME_HOME/." "$acme_bak/" 2>/dev/null || true
  fi
  rm -rf "$CS_ROOT"
  if [[ -n $cert_bak || -n $acme_bak ]]; then
    install -d -m 775 "$CS_ROOT"
    if [[ -n $cert_bak ]]; then
      install -d -m 750 "$CONF_DIR/certs"
      cp -a "$cert_bak/." "$CONF_DIR/certs/" 2>/dev/null || true
      rm -rf "$cert_bak"
    fi
    if [[ -n $acme_bak ]]; then
      install -d -m 700 "$ACME_HOME"
      cp -a "$acme_bak/." "$ACME_HOME/" 2>/dev/null || true
      rm -rf "$acme_bak"
    fi
  fi
  if id mihomo >/dev/null 2>&1; then userdel -f mihomo 2>/dev/null || true; fi
  echo "已卸载：Mihomo、管理面板、证书（含 acme.sh）、配置和客户端文件。"
}

ACTION=""
while (($#)); do
  case "$1" in
    install|update|uninstall|info|status|sub|passwd|restart|log|menu|reset-password|reset-secret|reset-sub|cert) ACTION=$1 ;;
    core|self) [[ $ACTION == update ]] || die "未知参数：$1"; UPDATE_WHAT=$1 ;;
    help) usage; exit 0 ;;
    # 以下为开发/测试用隐藏参数，不写入用户文档
    -d|--domain) DOMAIN=${2:?缺少域名}; MODE=auto-cert; MODE_SET=1; shift ;;
    --cert-mode)
      case ${2:-} in port|dns|manual) CERT_MODE=$2; CERT_MODE_SET=1; MODE=auto-cert; MODE_SET=1 ;; *) die "未知证书方式：${2:-}（可选 port|dns|manual）" ;; esac
      shift ;;
    --manual-cert) CERT_MODE=manual; CERT_MODE_SET=1; MODE=auto-cert; MODE_SET=1 ;;
    --cf-token) CF_TOKEN=${2:?缺少 Cloudflare API Token}; CERT_MODE=dns; CERT_MODE_SET=1; MODE=auto-cert; MODE_SET=1; shift ;;
    --panel-port) PANEL_PORT=${2:?缺少面板端口}; shift ;;
    --controller-port) CONTROLLER_PORT=${2:?缺少控制端口}; shift ;;
    --staging|--tls-staging) TLS=staging ;;
    --production|--tls-production) TLS=production ;;
    --tls-internal) TLS=internal ;;
    -h|--help) usage; exit 0 ;;
    *) die "未知参数：$1（查看帮助：-h）" ;;
  esac
  shift
done

# 无子命令：由 install.sh 调用 -> 安装；已安装时直接运行 clashgate -> 管理菜单；未安装 -> 安装
if [[ -z $ACTION ]]; then
  if [[ -n ${CS_DEFAULT_ACTION:-} ]]; then ACTION=$CS_DEFAULT_ACTION
  elif [[ -f $STATE ]]; then ACTION=menu
  else ACTION=install; fi
fi
need_root
"do_${ACTION//-/_}" || exit $?   # 子命令自己已提示失败原因，不再触发 ERR trap 的「第 N 行执行失败」
