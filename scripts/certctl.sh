#!/usr/bin/env bash
# clashgate 证书管理（自动证书模式，acme.sh）
#   certctl.sh issue    申请证书并部署到 /etc/clashgate/certs（安装时调用）
#   certctl.sh renew    续期（acme.sh --cron）；首次申请未成功时重新申请（面板调用）
#   certctl.sh auto     同 renew，由每天一次的 systemd timer 调用；连续失败时逐渐放慢重试（最慢 3 天一次）
#   certctl.sh deploy   acme.sh 签发 / 续期后的 reloadcmd：复制证书给 Mihomo 与面板，有变化时按需重启 Mihomo
#   certctl.sh selfsign 写入临时自签证书（正式证书申请失败时兜底，让面板和 Mihomo 先跑起来）
#
# 申请方式（CERT_MODE）：
#   port  端口模式（默认）：申请/续期时临时使用 80 端口
#   dns   DNS API 模式：使用 Cloudflare API Token（CF_Token），无需占用 80/443 端口，支持 *.泛域名
#   manual 手动证书：用户自己把证书放进 /etc/clashgate/certs/；这里只校验，不申请、不续期
# 证书来源（TLS）：
#   production  Let's Encrypt 正式证书（默认）
#   staging     Let's Encrypt 测试证书
#   internal    本机自签证书（开发用，不走 ACME）
# 部署结果：/etc/clashgate/certs/{fullchain,privkey}.pem（root:mihomo 0640），Mihomo 入站与面板共用。
# 退出码：0 = 证书已就绪，1 = 失败。
# 申请 / 续期失败时把原因写进 /etc/clashgate/cert-failed（面板「HTTPS 证书」页显示），成功后删除；
# 格式：失败时间（epoch）、证书方式、连续失败次数，之后是提示和 acme.sh 输出。
set -Eeuo pipefail

CS_ROOT=${CLASHGATE_ROOT:-}/etc/clashgate
ENV_FILE=$CS_ROOT/clashgate.env
ACME_HOME=$CS_ROOT/acme.sh             # acme.sh 程序、账户与证书（--home）
LIVE=$ACME_HOME/live                   # acme.sh 安装证书的位置（--fullchain-file / --key-file）
SELF=$CS_ROOT/scripts/certctl.sh
DEST=$CS_ROOT/certs
MIHOMO_CONF=$CS_ROOT/config.yaml
LOCK_FILE=/run/clashgate-cert.lock
# 1.47: why the last request (timer / install / panel) failed, for the panel's HTTPS page: epoch, mode,
# then the Chinese messages and acme.sh output. Removed after a successful run.
FAILED_FILE=$CS_ROOT/cert-failed
RUN_LOG=
TEMP_CN="clashgate temporary certificate"
CA_LE=https://acme-v02.api.letsencrypt.org/directory
CA_LE_TEST=https://acme-staging-v02.api.letsencrypt.org/directory

# 输出语言与 clashgate 命令行一致（CLASHGATE_LANG > 已保存的语言 > LANG）；面板调用时固定为中文，便于解析失败原因
CS_LANG_FILE=${CS_LANG_FILE:-$ENV_FILE}
# shellcheck source=lib/i18n.sh
. "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/lib/i18n.sh"
say() { _tr_msg "$*"; builtin echo "certctl: $REPLY"; }
err() {
  [[ -n $RUN_LOG ]] && builtin echo "certctl: $*" >>"$RUN_LOG"   # untranslated, so the panel can parse it
  _tr_msg "$*"; builtin echo "certctl: $REPLY" >&2
}

[[ -r $ENV_FILE ]] || { err "缺少配置文件 $ENV_FILE"; exit 1; }
# shellcheck disable=SC1090
. "$ENV_FILE"
[[ -n "${DOMAIN:-}" ]] || { err "未设置 DOMAIN"; exit 1; }
if [[ ${REPO_NAME:-ClashGate} == ClashGateBeat ]]; then
  TLS=${TLS:-staging}
else
  TLS=${TLS:-production}
fi
CERT_MODE=${CERT_MODE:-port}
BASE_DOMAIN=${DOMAIN#\*.}
ACTION=${1:-renew}
FORCE_ISSUE=0
if [[ $ACTION == reissue ]]; then
  ACTION=issue
  FORCE_ISSUE=1
fi
AUTO=0
if [[ $ACTION == auto ]]; then   # the daily timer: renew, with back-off after failures (below)
  ACTION=renew
  AUTO=1
fi

trap 'err "第 $LINENO 行执行失败：$BASH_COMMAND"' ERR

# 只有 Mihomo 配置里引用了证书才需要重启；面板按文件变化自动换证书，不需要重启。
restart_mihomo() {
  systemctl is-active --quiet mihomo || return 0
  grep -qE "($DEST/|certs/)" "$MIHOMO_CONF" 2>/dev/null || return 0
  systemctl restart mihomo && say "已重启 Mihomo 以加载新证书" || err "重启 Mihomo 失败"
}

pubkey_sum() { openssl pkey "$@" -pubout -outform DER 2>/dev/null | openssl dgst -sha256 -r | cut -d' ' -f1; }

valid_pair() { # valid_pair <crt> <key>：证书未过期、包含本域名、与私钥匹配
  local crt=$1 key=$2 a b
  [[ -s $crt && -s $key ]] || { err "证书文件为空：$crt"; return 1; }
  openssl x509 -noout -checkend 0 -in "$crt" >/dev/null 2>&1 || { err "证书已过期或无法解析：$crt"; return 1; }
  openssl x509 -noout -checkhost "$BASE_DOMAIN" -in "$crt" 2>/dev/null | grep -q 'does match' \
    || { err "证书不包含域名 $BASE_DOMAIN：$crt"; return 1; }
  a=$(openssl x509 -noout -pubkey -in "$crt" 2>/dev/null | pubkey_sum -pubin)
  b=$(pubkey_sum -in "$key")
  [[ -n $a && $a == "$b" ]] || { err "证书与私钥不匹配：$crt"; return 1; }
}

deploy() { # deploy <crt> <key> -> 有变化返回 0，未变化 / 无效返回 1（无效时保留原证书）
  local crt=$1 key=$2
  valid_pair "$crt" "$key" || return 1
  install -d -m 750 -o root -g mihomo "$DEST"
  if cmp -s "$crt" "$DEST/fullchain.pem" && cmp -s "$key" "$DEST/privkey.pem"; then return 1; fi
  install -m 640 -o root -g mihomo "$crt" "$DEST/fullchain.pem.new"
  install -m 640 -o root -g mihomo "$key" "$DEST/privkey.pem.new"
  mv -f "$DEST/privkey.pem.new" "$DEST/privkey.pem"
  mv -f "$DEST/fullchain.pem.new" "$DEST/fullchain.pem"
  local end; end=$(openssl x509 -noout -enddate -in "$DEST/fullchain.pem" | cut -d= -f2)
  say "证书已更新 -> $DEST（到期：$end）"
}

deploy_live() { # acme.sh 输出 -> /etc/clashgate/certs；重复调用无副作用
  [[ -f $LIVE/fullchain.pem && -f $LIVE/privkey.pem ]] || { err "$LIVE 中没有证书"; return 1; }
  if deploy "$LIVE/fullchain.pem" "$LIVE/privkey.pem"; then restart_mihomo; fi
  return 0
}

selfsign() { # selfsign <dir> <CN> <days>
  local d=$1 san="DNS:$BASE_DOMAIN"
  [[ $DOMAIN != "$BASE_DOMAIN" ]] && san+=",DNS:$DOMAIN"
  install -d -m 700 "$d"
  openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes -days "$3" \
    -subj "/CN=$2" -addext "subjectAltName=$san" \
    -keyout "$d/$BASE_DOMAIN.key" -out "$d/$BASE_DOMAIN.crt" >/dev/null 2>&1
  chmod 600 "$d/$BASE_DOMAIN.key"
}

is_temp() { [[ -f $DEST/fullchain.pem ]] && openssl x509 -noout -subject -in "$DEST/fullchain.pem" 2>/dev/null | grep -q "$TEMP_CN"; }

case $ACTION in
  selfsign)
    is_temp || [[ ! -f $DEST/fullchain.pem ]] || exit 0   # 已有真实证书时不覆盖
    tmp=$(mktemp -d)
    selfsign "$tmp" "$TEMP_CN" 30
    deploy "$tmp/$BASE_DOMAIN.crt" "$tmp/$BASE_DOMAIN.key" || true
    rm -rf "$tmp"
    exit 0 ;;
  deploy)   # 由 acme.sh 在持有锁的 issue / renew 过程中调用，这里不能再加锁
    deploy_live; exit $? ;;
  issue|renew|reissue) ;;
  *) err "用法：certctl.sh issue|renew|reissue|deploy|selfsign"; exit 1 ;;
esac

# 安装、定时续期和面板可能同时运行：串行化
exec 9>"$LOCK_FILE"
flock -w 600 9 || { err "另一个证书任务仍在运行"; exit 1; }

if [[ $CERT_MODE == manual ]]; then
  valid_pair "$DEST/fullchain.pem" "$DEST/privkey.pem" || exit 1
  chown root:mihomo "$DEST/fullchain.pem" "$DEST/privkey.pem" 2>/dev/null || true
  chmod 640 "$DEST/fullchain.pem" "$DEST/privkey.pem"
  end=$(openssl x509 -noout -enddate -in "$DEST/fullchain.pem" | cut -d= -f2)
  say "手动证书校验正常：$DEST（到期：$end）"
  exit 0
fi

if [[ $TLS == internal ]]; then   # 开发用：本机自签，不走 ACME
  d=$ACME_HOME/internal
  if [[ ! -f $d/$BASE_DOMAIN.crt ]] || ! openssl x509 -checkend $((30 * 86400)) -noout -in "$d/$BASE_DOMAIN.crt" >/dev/null 2>&1; then
    selfsign "$d" "clashgate internal CA" 90
  fi
  if deploy "$d/$BASE_DOMAIN.crt" "$d/$BASE_DOMAIN.key" && [[ $ACTION == renew ]]; then restart_mihomo; fi
  exit 0
fi

# 1.47: the daily timer slows down after failed requests: after n failures in a row it waits min(n, 3)
# days from the last one (2 h early is fine: the timer starts at a random time of day). The panel and
# the installer always run. Exits before the result trap below, so the failure record stays as it is.
if ((AUTO)) && [[ -f $FAILED_FILE ]]; then
  last_at='' fails=''
  { read -r last_at; read -r _; read -r fails; } <"$FAILED_FILE" 2>/dev/null || true
  if [[ $last_at =~ ^[0-9]+$ && $fails =~ ^[0-9]+$ ]] && ((fails > 0)); then
    wait_days=$((fails < 3 ? fails : 3))
    if (($(date +%s) - last_at < wait_days * 86400 - 7200)); then
      exit 0
    fi
  fi
fi

# 1.47: from here on a failure is a failed certificate request: keep its reason for the panel
RUN_LOG=$(mktemp)
record_result() {
  local rc=$1
  if ((rc == 0)); then
    rm -f "$FAILED_FILE"
  else
    local fails=''
    [[ -f $FAILED_FILE ]] && fails=$(sed -n '3p' "$FAILED_FILE" 2>/dev/null)
    [[ $fails =~ ^[0-9]+$ ]] || fails=0
    {
      date +%s
      builtin echo "$CERT_MODE"
      builtin echo $((fails + 1))   # failures in a row (the daily timer backs off on it)
      while IFS= read -r line; do   # the token never goes into the file (quoted pattern: literal match)
        [[ -n ${CF_TOKEN:-} ]] && line=${line//"$CF_TOKEN"/***}
        builtin echo "$line"
      done < <(tail -n 80 "$RUN_LOG")
    } >"$FAILED_FILE.new" 2>/dev/null && chmod 600 "$FAILED_FILE.new" && mv -f "$FAILED_FILE.new" "$FAILED_FILE"
  fi
  rm -f "$RUN_LOG"
}
trap 'record_result $?' EXIT

ACME=$ACME_HOME/acme.sh
# 手动证书模式安装的机器没有 acme.sh：从面板切换到自动证书时按固定版本补装（同 lib/cert.sh install_acme）
# shellcheck source=lib/acme.sh
. "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/lib/acme.sh"
ensure_acme() {
  local ver
  ver=$(sed -n 's/^ACMESH_VERSION=\([0-9.]*\).*/\1/p' "$CS_ROOT/scripts/lib/common.sh" 2>/dev/null | head -n1)
  ver=${ver:-3.1.6}
  say "未找到 acme.sh，正在安装 v$ver"
  acme_fetch_install "$ACME_HOME" "$ver" "${EMAIL:-}"
}
[[ -x $ACME ]] || ensure_acme || { err "未找到 $ACME，自动安装失败（可执行 clashgate update 后重试）"; exit 1; }
if [[ $CERT_MODE == dns && -n ${CF_TOKEN:-} ]]; then
  export CF_Token=$CF_TOKEN
fi
acme() { # acme.sh 签发成功时会把整张证书 PEM 打到输出里：去掉，日志更易读（同时留一份给失败原因）
  "$ACME" --home "$ACME_HOME" "$@" 2>&1 | sed -u '/-----BEGIN CERTIFICATE-----/,/-----END CERTIFICATE-----/d' | tee -a "$RUN_LOG"
  return "${PIPESTATUS[0]}"
}

case $TLS in
  staging) server=letsencrypt_test api=$CA_LE_TEST ;;
  *)       server=letsencrypt      api=$CA_LE ;;
esac
if [[ -n "${CS_ACME_SERVER:-}" ]]; then server=$CS_ACME_SERVER api=$CS_ACME_SERVER; fi   # 开发用：本地 pebble 等
extra=()
[[ -n "${CS_ACME_INSECURE:-}" ]] && extra+=(--insecure)

# DNS API 模式：申请前确认 Token 能在 Cloudflare 里找到域名所在的区域（acme.sh 的 dns_cf 也是这样找的，
# 找不到时它只报 invalid domain）。连不上 Cloudflare API 时不拦，交给 acme.sh。
cf_zone_check() {
  local d=$BASE_DOMAIN resp code body
  [[ -z ${CS_DNS_HOOK:-} && -z ${CS_ACME_SERVER:-} ]] || return 0   # 开发 / 测试用的 DNS 钩子
  while [[ $d == *.* ]]; do
    resp=$(curl -sS --max-time 15 -w '\n%{http_code}' -H "Authorization: Bearer $CF_TOKEN" \
      "https://api.cloudflare.com/client/v4/zones?name=$d&per_page=1" 2>/dev/null) || return 0
    code=${resp##*$'\n'}; body=${resp%$'\n'*}
    case $code in
      200) ;;
      400|401|403) err "Cloudflare API Token 无效或已过期，请重新创建（需要该域名的 Zone.DNS 编辑权限）"; return 1 ;;
      *) return 0 ;;
    esac
    if grep -q '"result":\[{' <<<"${body//[[:space:]]/}"; then return 0; fi
    d=${d#*.}
  done
  err "这个 Cloudflare 账号里找不到 $BASE_DOMAIN 所在的域名：请确认域名已添加到该账号、Token 能访问它，或改用端口模式"
  return 1
}
if [[ $ACTION == issue && $CERT_MODE == dns && -n ${CF_TOKEN:-} ]]; then
  cf_zone_check || exit 1
fi

# 换过域名重装后，acme.sh 里可能还留着旧域名：删掉，免得 --cron 每天为它申请失败
for d in "$ACME_HOME"/*.*/; do
  [[ -d $d ]] || continue
  n=$(basename "$d"); n=${n%_ecc}
  [[ $n == "$BASE_DOMAIN" ]] && continue
  [[ -f $d/$n.conf ]] || continue
  rm -rf "$d" "${d%/}.ari" && say "已移除旧域名的证书记录：$n"
done

dns_hook=${CS_DNS_HOOK:-dns_cf}
if [[ $CERT_MODE == dns ]]; then want_webroot=$dns_hook; else want_webroot=no; fi

conf=$ACME_HOME/${BASE_DOMAIN}_ecc/$BASE_DOMAIN.conf
saved() { [[ -f $conf ]] || return 0; sed -n "s/^$1='\(.*\)'\$/\1/p" "$conf" | tail -n1; }
saved_api=$(saved Le_API)
saved_webroot=$(saved Le_Webroot)
issued=0
[[ -n $(saved Le_CertCreateTime) && -f $ACME_HOME/${BASE_DOMAIN}_ecc/fullchain.cer ]] && issued=1

# 已签发过且来自同一 CA / 同一申请方式：交给 acme.sh 判断是否到期（默认剩 30 天内续期，支持 ARI），续期成功会调用 reloadcmd
if [[ $ACTION == renew ]] && ((issued)) && [[ $saved_api == "$api" && $saved_webroot == "$want_webroot" ]] && ! is_temp; then
  rc=0
  acme --cron "${extra[@]}" || rc=$?
  deploy_live || true   # 自愈：/etc/clashgate/certs 被误删 / 改动时重新部署（无变化时什么也不做）
  ((rc == 0)) || err "续期失败；当前证书仍可用到 $(openssl x509 -noout -enddate -in "$DEST/fullchain.pem" 2>/dev/null | cut -d= -f2)"
  exit "$rc"
fi

mode_args=()
if [[ $CERT_MODE == dns ]]; then
  [[ -n ${CF_TOKEN:-} ]] || { err "DNS API 模式缺少 Cloudflare API Token"; exit 1; }
  mode_args=(--dns "$dns_hook")
  [[ -n ${CS_DNSSLEEP:-} ]] && mode_args+=(--dnssleep "$CS_DNSSLEEP")
  mode_zh="DNS API 模式"
else
  # 端口模式：standalone 需要临时占用 80 端口
  busy=$(ss -Hltnp 'sport = :80' 2>/dev/null || true)
  if [[ -n $busy ]]; then
    err "80 端口被占用，无法申请证书（端口模式需要临时使用 80 端口）："
    builtin echo "$busy" >&2
    exit 1
  fi
  mode_args=(--standalone)
  mode_zh="端口模式"
fi

force=()
if ((FORCE_ISSUE)); then
  force=(--force); say "按面板请求重新签发证书"
elif [[ -n $saved_api && $saved_api != "$api" ]]; then
  force=(--force); say "已有证书来自其他 CA（$saved_api），重新签发"
elif [[ -n $saved_webroot && $saved_webroot != "$want_webroot" ]]; then
  force=(--force); say "证书申请方式已更改（$saved_webroot -> $want_webroot），重新签发"
fi

dom_args=(-d "$BASE_DOMAIN")
[[ $DOMAIN == \*.* ]] && dom_args+=(-d "$DOMAIN")

say "向 $server 申请 $DOMAIN 的证书（$mode_zh）"
install -d -m 700 "$LIVE"
inst=(--fullchain-file "$LIVE/fullchain.pem" --key-file "$LIVE/privkey.pem" --reloadcmd "$SELF deploy")
rc=0
acme --issue "${dom_args[@]}" "${mode_args[@]}" --server "$server" -k ec-256 "${inst[@]}" "${force[@]}" "${extra[@]}" || rc=$?
case $rc in
  0) ;;
  2) acme --install-cert -d "$BASE_DOMAIN" --ecc "${inst[@]}" >/dev/null || true ;;   # 证书仍有效，跳过签发
  *)
    if [[ $CERT_MODE == dns ]]; then
      err "证书申请失败（请检查 Cloudflare API Token 是否具备 $BASE_DOMAIN 的 DNS 编辑权限）"
    else
      err "证书申请失败（请检查域名 A/AAAA 记录是否指向本机、云防火墙是否放行 TCP 80）"
    fi
    exit 1 ;;
esac
deploy_live || true
if is_temp || ! valid_pair "$DEST/fullchain.pem" "$DEST/privkey.pem"; then
  err "证书已签发但未能部署到 $DEST"; exit 1
fi
exit 0
