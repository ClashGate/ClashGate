#!/usr/bin/env bash
# clashgate 管理命令（安装后链接为 /usr/local/bin/clashgate）
# 不带参数：已安装 -> 管理菜单（中文/English）；未安装 -> 安装。clashgate help 查看全部子命令。
set -Eeuo pipefail

ORIG_ARGS=("$@")
CS_HOME=$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/../.." && pwd)
for _lib in common acme core cert panel; do
  # shellcheck source=/dev/null
  . "$CS_HOME/scripts/lib/$_lib.sh"
done
trap 'die "执行中断：脚本第 $LINENO 行的命令没有成功（$BASH_COMMAND）。多数是网络或软件源暂时不可用，可以稍后重新运行；仍然失败时请带上以上输出到 GitHub Issues 反馈"' ERR
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
  reset-password    reset the panel password (random)
  cert [domain]     change the domain and get a new certificate; nodes and the subscription link are regenerated
  restart           restart the core
  update            update core, scripts and panel
  log               show recent logs
  lang [zh|en|ru]   switch and save the CLI language (no argument: choose from a list)
  uninstall         uninstall
  install           reinstall (choose the mode when prompted)
  help              show this help

Language: clashgate lang zh|en|ru saves it; CLASHGATE_LANG=zh|en|ru overrides it for one run
One-click install: curl -fsSL $INSTALL_RAW_URL | bash
EOF
    return 0
  fi
  if [[ $CS_LANG == ru ]]; then
    cat <<EOF
ClashGate (clashgate) - команда управления прокси-сервером (v$CS_VERSION)

Использование: clashgate [подкоманда]
  (без аргументов)  открыть интерактивное меню
  status            показать состояние (службы, порты, сертификат)
  info              показать конфигурацию узлов (фрагмент proxies, каталог клиента, ссылка подписки)
  sub               показать ссылку подписки (режимы с сертификатом)
  reset-sub         сменить ссылку подписки; старая ссылка сразу перестаёт работать
  reset-password    сбросить пароль панели (случайный)
  cert [домен]      сменить домен и получить новый сертификат; узлы и ссылка подписки создаются заново
  restart           перезапустить ядро
  update            обновить ядро, скрипты и панель
  log               показать последние журналы
  lang [zh|en|ru]   сменить и сохранить язык командной строки (без аргумента: выбор из списка)
  uninstall         удалить
  install           переустановить (режим выбирается в диалоге)
  help              показать эту справку

Язык: clashgate lang zh|en|ru сохраняет выбор; CLASHGATE_LANG=zh|en|ru действует только на один запуск
Установка одной командой: curl -fsSL $INSTALL_RAW_URL | bash
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
  reset-password    重置面板密码（随机生成）
  cert [域名]       更换域名并申请新证书，节点与订阅链接全部重新生成
  restart           重启内核
  update            更新内核、脚本与面板
  log               查看最近日志
  lang [zh|en|ru]   切换并保存命令行语言（不带参数时从列表选择）
  uninstall         卸载
  install           重新安装（按提示选择模式）
  help              显示本帮助

语言：clashgate lang zh|en|ru 切换并保存；CLASHGATE_LANG=zh|en|ru 只对本次运行生效
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
    [[ $(ask '检测到已安装 ClashGate，是否卸载后重新安装？节点和密钥都会重新生成（已加入集群时会先退出集群） [y/N]：' n) == [yY]* ]] \
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
  done < "$STATE"
  [[ $MODE == auto-cert ]] || return 0
  grep -q ":$CONTROLLER_PORT " <<<"$ss_out" || die "Mihomo 控制接口未在端口 $CONTROLLER_PORT 监听"
  local i h p sub_body
  h=$(panel_host); p=$(panel_port)
  for ((i = 0; i < 10; i++)); do panel_https_ok /healthz >/dev/null && break; sleep 1; done
  ((i < 10)) || { journalctl -u clashgate -n 20 --no-pager >&2; die "面板未在 $p 端口响应 HTTPS"; }
  sub_body=$(panel_https_ok "/sub/$SUB_TOKEN/mihomo.yaml" || true)
  grep -q 'proxies:' <<<"$sub_body" || die "订阅接口没有返回 mihomo 配置"
  [[ $(curl -sk -o /dev/null -w '%{http_code}' --resolve "$h:$p:127.0.0.1" \
    "$(panel_url)/sub/wrongtoken0000000000000000/mihomo.yaml") == 404 ]] || die "订阅接口未拒绝错误的 token"
}

print_summary() {
  local ports=()
  if [[ $MODE == auto-cert ]]; then
    [[ ${CERT_MODE:-port} == port ]] && ports+=(80)
    [[ $PANEL_PORT == 80 && ${CERT_MODE:-port} == port ]] || ports+=("$PANEL_PORT")
    ports+=("$CONTROLLER_PORT")
  fi
  mapfile -t -O "${#ports[@]}" ports < <(cut -f2 "$STATE")
  printf '\n\033[1;32m✔ 安装完成（ClashGate v%s）\033[0m\n' "$CS_VERSION"
  printf '请在云服务商防火墙放行 TCP 端口：%s\n' "${ports[*]}"
  if [[ $MODE == auto-cert ]]; then
    printf '订阅链接：\033[1;36m%s\033[0m\n' "$(sub_url)"
    printf '面板：%s\n用户名：admin\n' "$(panel_url)"
    [[ -n $PANEL_PASS ]] && printf '密码：%s（仅显示一次）\n' "$PANEL_PASS"
    if [[ ${CERT_MODE:-port} != manual ]] && cert_is_temp; then
      printf '\033[1;33m证书尚未签发成功，当前为临时自签证书；系统每小时自动重试，也可在面板「HTTPS 证书」页立即重试\033[0m\n'
    elif [[ ${CERT_MODE:-port} != manual && $TLS != production ]]; then
      printf '注意：当前为%s，客户端可能拒绝下载订阅\n' "$(tls_label)"
    fi
  else
    printf '节点配置（粘贴到客户端的 proxies）：\n'
    cat "$CLIENT_DIR/proxies.yaml"
  fi
  printf '运行 \033[1mclashgate\033[0m 打开菜单\n'
  if ((${#WARNINGS[@]})); then
    printf '\n\033[1;33m需要注意：\033[0m\n'; printf '  - %s\n' "${WARNINGS[@]}"
  fi
}

# ------------------------------------------------------------ actions
do_install() {
  # 安装语言：交互终端且没有 CLASHGATE_LANG / 已保存的语言时先选择（install.sh 已选过则跳过），选完用新语言重新运行
  if [[ -z ${CLASHGATE_LANG:-} && -z ${CS_LANG_PICKED:-} && -z ${CS_LANG_SAVED:-} ]] && has_tty; then
    CLASHGATE_LANG=$(pick_lang "$CS_LANG") CS_LANG_PICKED=1 exec bash "$CS_HOME/scripts/cmd/clashgate.sh" "${ORIG_ARGS[@]}"
  fi
  CS_LANG_SAVED=$CS_LANG   # 安装时使用的语言就是之后命令行（及面板默认）的语言
  check_os
  if [[ $CS_HOME -ef $LIB_DIR ]]; then # 从已安装副本运行（clashgate install）：先复制出来，避免重装时删掉自己
    local tmp
    tmp=$(mktemp -d /tmp/clashgate.XXXXXX)
    for d in "${CS_TREE_PARTS[@]}"; do cp -r "$LIB_DIR/$d" "$tmp/"; done
    CS_BOOTSTRAP_TMP=$tmp CS_DEFAULT_ACTION=install exec bash "$tmp/scripts/cmd/clashgate.sh" "${ORIG_ARGS[@]}"
  fi
  interactive_setup
  check_existing
  if [[ $MODE == auto-cert ]]; then
    TOTAL=$([[ ${CERT_MODE:-port} == manual ]] && echo 10 || echo 11)
  fi
  install_deps
  if [[ $MODE == auto-cert ]]; then ensure_python; fi
  [[ $MODE == auto-cert ]] && preflight_cert
  detect_ip
  if [[ $MODE == auto-cert ]]; then check_dns; fi   # 尽早检查，解析不对可在装任何东西前退出
  [[ $MODE == auto-cert && -z $MIHOMO_SECRET ]] && MIHOMO_SECRET=$(openssl rand -base64 32 | tr -dc 'A-Za-z0-9' | head -c 20)
  save_env
  install_core; ensure_user; log "安装 ClashGate 文件"; install_files; gen_nodes
  ensure_geodata || die "地理数据下载失败：$GEO_FAILED（请确认服务器可以访问 jsDelivr 或 GitHub）"
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

# clashgate update：同时更新 Mihomo 内核与 clashgate 自身（脚本、面板、模板、unit）；面板的「升级」与自动更新也调用它
do_update() {
  require_installed; load_env
  STEP=0; TOTAL=4
  install_deps
  if [[ $MODE == auto-cert ]]; then ensure_python; fi
  install_core
  ensure_geodata || warn "地理数据下载失败：$GEO_FAILED（请确认服务器可以访问 jsDelivr 或 GitHub）"
  update_self
  log "重启服务"
  validate_conf || die "配置未通过校验（mihomo -t），未重启"
  systemctl restart mihomo
  [[ $MODE == auto-cert ]] && systemctl restart clashgate
  sleep 1
  info "Mihomo：$(svc_state mihomo)"
  return 0
}

# Unapplied panel drafts: the fragments on disk already hold them, and only the panel's
# 「应用配置」 may make them live (it also clears the pending list and syncs the subscription).
has_panel_drafts() {
  [[ -s $CS_ROOT/pending_reload.json ]] || return 1
  python3 - "$CS_ROOT/pending_reload.json" <<'PY' 2>/dev/null
import json, sys
d = json.load(open(sys.argv[1]))
sys.exit(0 if isinstance(d, dict) and (d.get("items") or d.get("sub_token") or d.get("mihomo_secret")) else 1)
PY
}

update_self() {
  log "更新 ClashGate 脚本与面板"
  local tmp
  tmp=$(mktemp -d /tmp/clashgate.XXXXXX)
  fetch_repo "$tmp"
  CS_HOME=$tmp install_files   # 替换 /etc/clashgate 下的代码子目录；保留配置与证书
  chmod 1775 "$CONF_DIR" 2>/dev/null || true   # sticky: mihomo may not replace root-owned files
  rm -rf "$tmp"
  install -m 644 "$LIB_DIR/scripts/init/mihomo.service" "$UNIT"
  if [[ $MODE == auto-cert ]]; then
    install_panel_unit
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
  # With unapplied panel drafts keep the live config.yaml and client files as they are:
  # the next 「应用配置」 assembles them with the new template.
  render_controller
  save_env
  if ! has_panel_drafts; then
    cp -a "$CONF" "$CONF.bak"
    assemble_config
    if validate_conf; then rm -f "$CONF.bak"; else mv -f "$CONF.bak" "$CONF"; warn "新模板生成的配置未通过校验，已保留原配置"; fi
    ( render_client ) >/dev/null 2>&1 || true   # subshell: keep the step counter of `update` intact
    rm -f "$CS_ROOT/template_refresh"
  else
    : > "$CS_ROOT/template_refresh"   # the panel assembles it once the drafts are applied or discarded
  fi
  record_update_source || true
  local ch_label=正式
  [[ ${UPDATE_CHANNEL:-} == test || ( -z ${UPDATE_CHANNEL:-} && ${REPO_BRANCH:-main} == test ) ]] && ch_label=测试
  info "ClashGate 已更新到 GitHub ${REPO_BRANCH:-main} 最新版（通道：${ch_label}）"
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
      printf '  证书：\033[1;31m尚未签发\033[0m（临时自签证书；可在面板「HTTPS 证书」页重试）\n'
    elif [[ -f $CONF_DIR/certs/fullchain.pem ]]; then
      local days; days=$(cert_days_left)
      printf '  证书到期：%s（%s，剩余 %s 天）\n' "$(cert_enddate)" "$(cert_issuer)" "$days"
      if [[ -n $days ]] && ((days < 14)); then
        printf '  \033[1;33m证书即将到期\033[0m：请在面板「HTTPS 证书」页续期或更新证书\n'
      fi
    else
      printf '  证书：\033[1;31m缺失\033[0m（请在面板「HTTPS 证书」页处理）\n'
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

# A link change still waiting for the panel's 「应用配置」 would later replace the link set here.
drop_panel_sub_draft() {
  [[ -s $CS_ROOT/pending_reload.json ]] || return 0
  python3 - "$CS_ROOT/pending_reload.json" "$CS_ROOT/pending_baseline.json" <<'PY' 2>/dev/null || true
import json, os, sys
path, baseline = sys.argv[1], sys.argv[2]
d = json.load(open(path))
if not isinstance(d, dict) or not d.get("sub_token"):
    sys.exit(0)
d["sub_token"] = ""
d["items"] = [it for it in (d.get("items") or []) if not (isinstance(it, dict) and it.get("op") == "reset-sub")]
if not (d["items"] or d.get("mihomo_secret")):
    for p in (path, baseline):
        if os.path.exists(p):
            os.remove(p)
    sys.exit(0)
tmp = path + ".tmp"
with open(tmp, "w") as f:
    json.dump(d, f, indent=2, ensure_ascii=False)
    f.write("\n")
os.chmod(tmp, 0o600)
os.replace(tmp, path)
PY
}

do_reset_sub() {
  load_env
  [[ $MODE == auto-cert && -f $PANEL_CFG ]] || die "订阅链接仅在自动证书或手动证书模式下提供"
  PANEL_HASH=$(panel_cfg_get password_hash)
  SUB_TOKEN=$(new_sub_token)
  write_panel_cfg
  drop_panel_sub_draft
  systemctl restart clashgate
  printf '新的订阅链接（旧链接已失效）：\n  %s\n' "$(sub_url)"
}

do_reset_password() {
  load_env
  [[ $MODE == auto-cert && -f $PANEL_CFG ]] || die "未安装管理面板（仅证书模式提供）"
  set_panel_password
  rm -f "$PANEL_SESSIONS"   # sign out every browser that used the old password
  systemctl restart clashgate
  printf '管理面板：%s\n用户名：admin\n新密码：%s\n' "$(panel_url)" "$PANEL_PASS"
}

# clashgate cert [域名]：换一个域名并重新申请证书。新证书就绪之前什么都不改；之后像重装一样
# 退出集群、删除全部入站节点并生成新的默认 VLESS Reality 节点，订阅 token 与 Zashboard API 密钥一并更换。
# 面板密码、面板端口、服务端出站与分流保持不变。
CERT_BAK=""
CERT_FILES=()

cert_backup() { # 改动前的文件、证书与 acme.sh 记录（申请新证书时 certctl 会删掉旧域名的记录）
  # Subcommands run with errexit off (`do_x || exit`), so every step checks its own result.
  local f
  CERT_BAK=$(mktemp -d /tmp/clashgate-cert.XXXXXX) || return 1
  trap 'rm -rf "$CERT_BAK"' EXIT
  install -d -m 700 "$CERT_BAK/files" || return 1
  for f in "${CERT_FILES[@]}"; do
    if [[ -e $f ]]; then cp -a "$f" "$CERT_BAK/files/" || return 1; fi
  done
  if [[ -d $CONF_DIR/certs ]]; then cp -a "$CONF_DIR/certs" "$CERT_BAK/certs" || return 1; fi
  if [[ -d $ACME_HOME ]]; then cp -a "$ACME_HOME" "$CERT_BAK/acme" || return 1; fi
  return 0
}

cert_restore() {
  local f b
  for f in "${CERT_FILES[@]}"; do
    b=$CERT_BAK/files/$(basename "$f")
    if [[ -e $b ]]; then cp -a "$b" "$f"; else rm -f "$f"; fi
  done
  if [[ -d $CERT_BAK/certs ]]; then rm -rf "$CONF_DIR/certs"; cp -a "$CERT_BAK/certs" "$CONF_DIR/certs"; fi
  if [[ -d $CERT_BAK/acme ]]; then rm -rf "$ACME_HOME"; cp -a "$CERT_BAK/acme" "$ACME_HOME"; fi
  return 0
}

cert_domain_ok() { # 新域名格式（同安装：端口模式不支持通配符）
  if [[ ${CERT_MODE:-port} != port ]]; then
    if [[ $1 =~ $WILDCARD_DOMAIN_RE ]]; then return 0; fi
  elif [[ $1 == \*.* ]]; then
    printf '通配符域名仅支持「DNS API 模式」或「手动证书模式」，请输入具体域名\n'
    return 1
  elif [[ $1 =~ $DOMAIN_RE ]]; then
    return 0
  fi
  if [[ -n $1 ]]; then printf '域名格式不正确：%s\n' "$1"; fi
  return 1
}

cert_ask_domain() {
  local d
  while :; do
    case ${CERT_MODE:-port} in
      dns)    d=$(ask '请输入域名（如 example.com 或 *.example.com）：' '') ;;
      manual) d=$(ask '请输入证书对应的域名（如 example.com）：' '') ;;
      *)      d=$(ask '请输入域名（需已将 A 记录解析到本机）：' '') ;;
    esac
    d=${d,,}
    if cert_domain_ok "$d"; then break; fi
  done
  NEW_DOMAIN=$d
}

cert_dns_points_here() { # 端口模式：Let's Encrypt 要能通过新域名连到本机，解析不对就不去申请（省下申请次数）
  local ips
  if [[ $SERVER_IP == *:* ]]; then
    ips=$(getent ahostsv6 "$1" 2>/dev/null | awk '$1 !~ /^::ffff:/ {print $1}' | sort -u | tr '\n' ' ' || true)
  else
    ips=$(getent ahostsv4 "$1" 2>/dev/null | awk '{print $1}' | sort -u | tr '\n' ' ' || true)
  fi
  ips=${ips% }
  if [[ " ${ips,,} " == *" ${SERVER_IP,,} "* ]]; then return 0; fi
  die "域名 $1 没有解析到本机 $SERVER_IP（当前解析：${ips:-—}）。请先修改 DNS 记录（Cloudflare 请设为灰云 DNS only），生效后再运行"
}

do_cert() {
  require_installed; load_env; require_panel
  local old=$DOMAIN nd=$CONF_DIR/certs.new in_cluster=0 out rc=0 tok ports=()
  NEW_DOMAIN=${ACTION_ARG:-}
  if [[ -s $CUSTOM_CONF ]]; then die "已启用自定义服务端配置，请先在面板「设置」页关闭后再更换域名"; fi
  if has_panel_drafts; then die "面板里有尚未应用的修改，请先在面板点「应用配置」或「丢弃草稿」后再更换域名"; fi
  if [[ -z $NEW_DOMAIN ]]; then
    has_tty || die "请指定新域名：clashgate cert 新域名"
    cert_ask_domain
  fi
  NEW_DOMAIN=${NEW_DOMAIN,,}
  if ! cert_domain_ok "$NEW_DOMAIN" >&2; then exit 1; fi
  if [[ $NEW_DOMAIN == "$old" ]]; then die "新域名与当前域名相同：$old"; fi
  if [[ ${CERT_MODE:-port} == port && $TLS != internal ]]; then cert_dns_points_here "$NEW_DOMAIN"; fi
  if [[ ${CERT_MODE:-port} == dns ]] && has_tty; then
    while :; do
      tok=$(ask 'Cloudflare API Token（回车沿用当前的 Token）：' '')
      if [[ -z $tok || ! $tok =~ [[:space:]\"\'] ]]; then break; fi
      printf 'API Token 不能包含空格或引号\n'
    done
    if [[ -n $tok ]]; then CF_TOKEN=$tok; fi
  fi
  if [[ ${CERT_MODE:-port} == manual ]]; then
    if [[ ! -s $nd/fullchain.pem || ! -s $nd/privkey.pem ]]; then
      die "请先把新域名的证书放入 $nd/（fullchain.pem 与 privkey.pem），再运行 clashgate cert"
    fi
    if ! cert_pair_ok "$nd/fullchain.pem" "$nd/privkey.pem" "$NEW_DOMAIN"; then die "新证书校验未通过，没有做任何修改"; fi
  fi
  if has_tty; then
    printf '\n将把域名从 %s 更换为 %s：\n' "$old" "$NEW_DOMAIN"
    if [[ ${CERT_MODE:-port} == manual ]]; then
      printf '  1. 启用 %s 里的新证书\n' "$nd/"
    else
      printf '  1. 先为新域名申请证书，申请失败时什么都不改\n'
    fi
    printf '  2. 证书就绪后退出集群（已加入时），删除全部入站节点，重新生成一个 VLESS Reality 节点\n'
    printf '  3. 订阅链接和 Zashboard API 密钥一并更换，客户端需要重新导入订阅；面板密码和端口不变\n'
    if [[ $(ask '确定更换？[y/N]：' n) != [yY]* ]]; then echo "已取消"; return 0; fi
  fi

  STEP=0; TOTAL=6
  CERT_FILES=("$ENV_FILE" "$PANEL_CFG" "$STATE" "$CS_ETC/inbounds.json" "$FRAG_REALITY" "$FRAG_EXTRA" "$FRAG_CONTROLLER" "$CONF")
  cert_backup || die "无法备份当前配置，没有做任何修改"
  # 1. 新证书：申请失败就把一切恢复原样
  if [[ ${CERT_MODE:-port} == manual ]]; then
    log "启用 $NEW_DOMAIN 的新证书"
    install -d -m 750 "$CONF_DIR/certs"
    if ! cp -f "$nd/fullchain.pem" "$CONF_DIR/certs/fullchain.pem" || ! cp -f "$nd/privkey.pem" "$CONF_DIR/certs/privkey.pem"; then
      cert_restore
      die "无法写入新证书，已恢复原来的证书"
    fi
    chown root:mihomo "$CONF_DIR/certs" "$CONF_DIR/certs/fullchain.pem" "$CONF_DIR/certs/privkey.pem" 2>/dev/null || true
    chmod 640 "$CONF_DIR/certs/fullchain.pem" "$CONF_DIR/certs/privkey.pem"
    DOMAIN=$NEW_DOMAIN; save_env
  else
    log "申请 $NEW_DOMAIN 的证书（$(cert_mode_label)）"
    DOMAIN=$NEW_DOMAIN; save_env
    out=$("$LIB_DIR/scripts/certctl.sh" reissue 2>&1) || rc=$?
    ( umask 077; builtin printf '%s\n' "$out" > "$CS_ETC/cert-change.log" )
    if ((rc != 0)); then
      builtin printf '%s\n' "$out" | grep -iE '^certctl:|error|invalid|fail|timeout|refused|unauthorized|connection' | tail -n 8 >&2 || true
      cert_restore
      die "证书申请失败，域名、证书、节点和集群都没有改动（完整输出：$CS_ETC/cert-change.log）"
    fi
  fi
  # 2. 新凭据与新节点（同重装）；配置通不过校验就整体恢复
  SUB_TOKEN=$(new_sub_token)
  MIHOMO_SECRET=$(openssl rand -hex 10)
  PANEL_HASH=$(panel_cfg_get password_hash)
  if [[ -z $SUB_TOKEN || -z $MIHOMO_SECRET || -z $PANEL_HASH ]]; then
    cert_restore
    die "无法生成新的凭据，已恢复原来的域名和证书"
  fi
  save_env
  write_panel_cfg
  builtin printf '[]\n' > "$CS_ETC/inbounds.json"; chmod 600 "$CS_ETC/inbounds.json"
  : > "$FRAG_EXTRA"
  gen_nodes
  if ! ( render_server ); then
    cert_restore
    systemctl restart mihomo || true
    die "新配置未通过校验（mihomo -t），已恢复原来的域名、证书和节点"
  fi
  STEP=$((STEP + 1))   # render_server ran in a subshell
  # 3. 退出集群；没能通知到的成员也在本机删掉连接
  if [[ $(cluster_link_count) =~ ^[1-9] ]]; then
    in_cluster=1
    leave_cluster
    if [[ -f $CS_ROOT/cluster.json ]] && jq '.links = [] | .pending = []' "$CS_ROOT/cluster.json" > "$CS_ROOT/cluster.json.new"; then
      chmod 600 "$CS_ROOT/cluster.json.new"; mv -f "$CS_ROOT/cluster.json.new" "$CS_ROOT/cluster.json"
    fi
    rm -f "$CS_ROOT/cluster.json.new"
    : > "$FRAG_CLUSTER_PROXIES"; : > "$FRAG_CLUSTER_LISTENERS"
    assemble_config
    validate_conf || die "退出集群后的配置未通过校验（mihomo -t），请运行 clashgate restart 查看原因"
  fi
  render_client
  open_firewall
  log "重启服务"
  systemctl restart mihomo
  systemctl restart clashgate
  verify
  rm -rf "$nd"
  rm -f "$CS_ROOT/template_refresh"

  if [[ ${CERT_MODE:-port} == port ]]; then ports+=(80); fi
  if [[ ! ( $PANEL_PORT == 80 && ${CERT_MODE:-port} == port ) ]]; then ports+=("$PANEL_PORT"); fi
  ports+=("$CONTROLLER_PORT")
  mapfile -t -O "${#ports[@]}" ports < <(cut -f2 "$STATE")
  printf '\n\033[1;32m✔ 域名已更换为 %s\033[0m\n' "$NEW_DOMAIN"
  printf '请在云服务商防火墙放行 TCP 端口：%s\n' "${ports[*]}"
  printf '面板：%s（用户名 admin，密码不变）\n' "$(panel_url)"
  printf '订阅链接：\033[1;36m%s\033[0m\n' "$(sub_url)"
  printf '所有入站节点、订阅链接和 Zashboard API 密钥都已重新生成，请在客户端重新导入订阅\n'
  if ((in_cluster)); then printf '已退出集群，需要时请在面板「集群」页重新添加成员\n'; fi
  if ((${#WARNINGS[@]})); then
    printf '\n\033[1;33m需要注意：\033[0m\n'; printf '  - %s\n' "${WARNINGS[@]}"
  fi
  return 0
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

# clashgate lang [zh|en|ru]：切换并保存命令行语言（写入 clashgate.env 的 CLASHGATE_LANG）
do_lang() {
  require_installed
  local v=""
  if [[ -n ${LANG_ARG:-} ]]; then
    v=$(_cs_lang_norm "$LANG_ARG")
    [[ -n $v ]] || die "未知语言：$LANG_ARG（可选 zh|en|ru）"
  elif has_tty; then
    v=$(pick_lang "${CS_LANG_SAVED:-$CS_LANG}")
  else
    printf '当前命令行语言：%s。切换：clashgate lang zh|en|ru\n' "$(lang_name "$CS_LANG")"
    return 0
  fi
  save_cli_lang "$v"
  case $v in
    en) builtin printf 'CLI language set to English (saved; CLASHGATE_LANG=zh|en|ru still overrides it for one run)\n' ;;
    ru) builtin printf 'Язык командной строки: русский (сохранено; CLASHGATE_LANG=zh|en|ru по-прежнему действует на один запуск)\n' ;;
    *)  builtin printf '命令行语言已切换为中文（已保存；CLASHGATE_LANG=zh|en|ru 仍可临时覆盖本次运行）\n' ;;
  esac
  if [[ -n ${CLASHGATE_LANG:-} && $(_cs_lang_norm "$CLASHGATE_LANG") != "$v" ]]; then
    warn "当前终端设置了 CLASHGATE_LANG=$CLASHGATE_LANG，本终端里仍以它为准；unset CLASHGATE_LANG 后使用新语言"
  fi
}

do_menu() {
  require_installed; load_env
  has_tty || { usage; return 0; }
  local items=() labels=() i c item rc
  items+=(status info);          labels+=("查看运行状态" "查看节点配置")
  if [[ $MODE == auto-cert ]]; then
    items+=(sub reset-sub reset-password cert)
    labels+=("查看订阅链接" "更换订阅链接" "重置面板密码（随机）" "更换域名证书")
  fi
  items+=(restart log update lang uninstall); labels+=("重启内核" "查看日志" "更新内核 + 脚本与面板" "语言 / Language" "卸载")
  while :; do
    printf '\n\033[1mClashGate v%s 管理菜单\033[0m（%s' "$CS_VERSION" "$([[ $MODE == auto-cert ]] && echo "$(mode_label) · $DOMAIN" || echo '无证书模式')"
    printf '）  Mihomo：%s\n' "$(svc_state mihomo)"
    for i in "${!items[@]}"; do printf '  %d) %s\n' "$((i + 1))" "${labels[$i]}"; done
    printf '  0) 退出\n'
    c=$(ask '请选择：' 0)
    [[ $c == 0 ]] && return 0
    if [[ $c =~ ^[0-9]+$ ]] && ((c >= 1 && c <= ${#items[@]})); then
      item=${items[$((c - 1))]}; rc=0
      printf '\n'
      if [[ $item == lang ]]; then   # 换语言后用新语言重新打开菜单
        ( do_lang ) && exec env -u CLASHGATE_LANG bash "$CS_HOME/scripts/cmd/clashgate.sh" menu
        continue
      fi
      if [[ $item == reset-sub ]] && [[ $(ask '旧订阅链接会立即失效，确定更换？[y/N]：' n) != [yY]* ]]; then
        echo "已取消"; continue
      fi
      if [[ $item == reset-password ]] && [[ $(ask '确定重置面板密码？[y/N]：' n) != [yY]* ]]; then
        echo "已取消"; continue
      fi
      ( STEP=0; "do_${item//-/_}" ) || rc=$?
      [[ $item == uninstall && ! -f $STATE ]] && return 0
      ask '按回车返回菜单……' '' >/dev/null
      # 更新后用新版本的脚本、换域名后用新域名重新打开菜单
      if [[ $item == update || $item == cert ]] && ((rc == 0)); then exec bash "$CS_HOME/scripts/cmd/clashgate.sh" menu; fi
    else
      printf '无效选项：%s\n' "$c"
    fi
  done
}

cluster_link_count() { jq -r '(.links // []) | length' "$CS_ROOT/cluster.json" 2>/dev/null || echo 0; }

# 卸载 / 重装前先退出集群，让其他成员删掉指向这台服务器的连接；失败只提示，不影响卸载。
leave_cluster() {
  local n out missed py
  n=$(cluster_link_count); [[ $n =~ ^[0-9]+$ ]] && ((n > 0)) || return 0
  py=$(py_bin) || { warn "没能退出集群（找不到 Python 3.9+），请到其他成员的面板里手动删除这台服务器"; return 0; }
  info "正在退出集群（通知 $n 个成员）"
  if ! out=$(PYTHONPATH="$LIB_DIR/panel${PYTHONPATH:+:$PYTHONPATH}" timeout 180 "$py" "$LIB_DIR/panel/panel.py" cluster-leave 2>/dev/null); then
    warn "没能退出集群，请到其他成员的面板里手动删除这台服务器"
    return 0
  fi
  missed=${out#*$'\t'}
  if [[ -n $missed ]]; then warn "以下集群成员没收到退出通知，请到它们的面板里手动删除这台服务器：${missed//,/、}"; fi
  return 0
}

do_uninstall() {
  load_env
  local in_cluster=0
  [[ $(cluster_link_count) =~ ^[1-9] ]] && in_cluster=1
  if [[ ${CS_IN_REINSTALL:-0} != 1 ]] && has_tty; then
    if ((in_cluster)); then
      [[ $(ask '确定卸载 ClashGate？会先退出集群，然后删除所有节点、证书和配置 [y/N]：' n) == [yY]* ]] || { echo "已取消"; return 0; }
    else
      [[ $(ask '确定卸载 ClashGate？所有节点、证书和配置都会被删除 [y/N]：' n) == [yY]* ]] || { echo "已取消"; return 0; }
    fi
  fi
  ((in_cluster)) && leave_cluster
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
    install -d -m 1775 "$CS_ROOT"
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
    install|update|uninstall|info|status|sub|restart|log|menu|reset-password|reset-sub|lang|cert) ACTION=$1 ;;
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
    *)
      # one positional argument: the language for `lang`, the new domain for `cert`
      [[ ( $ACTION == lang || $ACTION == cert ) && -z ${ACTION_ARG:-} ]] || die "未知参数：$1（查看帮助：-h）"
      ACTION_ARG=$1; LANG_ARG=$1 ;;
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
