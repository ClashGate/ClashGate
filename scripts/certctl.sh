#!/usr/bin/env bash
# clashgate 证书管理（自动证书模式，acme.sh）
#   certctl.sh issue    申请证书并部署到 /etc/clashgate/certs（安装时调用）
#   certctl.sh renew    续期（acme.sh --cron）；首次申请未成功时重新申请（systemd timer / clashgate cert 调用）
#   certctl.sh deploy   acme.sh 签发 / 续期后的 reloadcmd：复制证书给 Mihomo 与面板，有变化时按需重启 Mihomo
#   certctl.sh selfsign 写入临时自签证书（正式证书申请失败时兜底，让面板和 Mihomo 先跑起来）
#
# 申请方式（CERT_MODE）：
#   port  端口模式（默认）：申请/续期时临时使用 80 端口
#   dns   DNS API 模式：使用 Cloudflare API Token（CF_Token），无需占用 80/443 端口，支持 *.泛域名
# 证书来源（TLS）：
#   production  Let's Encrypt 正式证书（默认）
#   staging     Let's Encrypt 测试证书
#   internal    本机自签证书（开发用，不走 ACME）
# 部署结果：/etc/clashgate/certs/{fullchain,privkey}.pem（root:mihomo 0640），Mihomo 入站与面板共用。
# 退出码：0 = 证书已就绪，1 = 失败。
set -Eeuo pipefail

CS_ROOT=${CLASHGATE_ROOT:-}/etc/clashgate
ENV_FILE=$CS_ROOT/clashgate.env
ACME_HOME=$CS_ROOT/acme.sh             # acme.sh 程序、账户与证书（--home）
LIVE=$ACME_HOME/live                   # acme.sh 安装证书的位置（--fullchain-file / --key-file）
SELF=$CS_ROOT/scripts/certctl.sh
DEST=$CS_ROOT/certs
MIHOMO_CONF=$CS_ROOT/config.yaml
LOCK_FILE=/run/clashgate-cert.lock
TEMP_CN="clashgate temporary certificate"
CA_LE=https://acme-v02.api.letsencrypt.org/directory
CA_LE_TEST=https://acme-staging-v02.api.letsencrypt.org/directory

[[ -r $ENV_FILE ]] || { echo "certctl: 缺少 $ENV_FILE" >&2; exit 1; }
# shellcheck disable=SC1090
. "$ENV_FILE"
[[ -n "${DOMAIN:-}" ]] || { echo "certctl: 未设置 DOMAIN" >&2; exit 1; }
if [[ ${REPO_NAME:-ClashGate} == ClashGateBeat ]]; then
  TLS=${TLS:-staging}
else
  TLS=${TLS:-production}
fi
CERT_MODE=${CERT_MODE:-port}
BASE_DOMAIN=${DOMAIN#\*.}
ACTION=${1:-renew}

say() { echo "certctl: $*"; }
err() { echo "certctl: $*" >&2; }
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
  say "证书已更新 -> $DEST（到期：$(openssl x509 -noout -enddate -in "$DEST/fullchain.pem" | cut -d= -f2)）"
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
  issue|renew) ;;
  *) err "用法：certctl.sh issue|renew|deploy|selfsign"; exit 1 ;;
esac

# 安装、定时续期和 clashgate cert 可能同时运行：串行化
exec 9>"$LOCK_FILE"
flock -w 600 9 || { err "另一个证书任务仍在运行"; exit 1; }

if [[ $CERT_MODE == manual ]]; then
  valid_pair "$DEST/fullchain.pem" "$DEST/privkey.pem" || exit 1
  chown root:mihomo "$DEST/fullchain.pem" "$DEST/privkey.pem" 2>/dev/null || true
  chmod 640 "$DEST/fullchain.pem" "$DEST/privkey.pem"
  say "手动证书校验正常：$DEST（到期：$(openssl x509 -noout -enddate -in "$DEST/fullchain.pem" | cut -d= -f2)）"
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

ACME=$ACME_HOME/acme.sh
[[ -x $ACME ]] || { err "未找到 $ACME（可执行 clashgate update 重新安装）"; exit 1; }
if [[ $CERT_MODE == dns && -n ${CF_TOKEN:-} ]]; then
  export CF_Token=$CF_TOKEN
fi
acme() { # acme.sh 签发成功时会把整张证书 PEM 打到输出里：去掉，日志更易读
  "$ACME" --home "$ACME_HOME" "$@" 2>&1 | sed -u '/-----BEGIN CERTIFICATE-----/,/-----END CERTIFICATE-----/d'
  return "${PIPESTATUS[0]}"
}

case $TLS in
  staging) server=letsencrypt_test api=$CA_LE_TEST ;;
  *)       server=letsencrypt      api=$CA_LE ;;
esac
if [[ -n "${CS_ACME_SERVER:-}" ]]; then server=$CS_ACME_SERVER api=$CS_ACME_SERVER; fi   # 开发用：本地 pebble 等
extra=()
[[ -n "${CS_ACME_INSECURE:-}" ]] && extra+=(--insecure)

# 换过域名重装后，acme.sh 里可能还留着旧域名：删掉，免得 --cron 每小时为它申请失败
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
    err "80 端口被占用，无法申请证书（端口模式需要临时使用 80 端口）：
$busy"
    exit 1
  fi
  mode_args=(--standalone)
  mode_zh="端口模式"
fi

force=()
if [[ -n $saved_api && $saved_api != "$api" ]]; then
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
