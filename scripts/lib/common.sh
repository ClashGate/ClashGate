# shellcheck shell=bash
# clashgate 公共函数：常量、日志、交互、环境持久化、下载与安装文件

# shellcheck source=/dev/null
. "$(dirname "${BASH_SOURCE[0]}")/i18n.sh"   # CLASHGATE_LANG=en|zh；默认中文

CS_VERSION=1.07.8
CS_SOURCE_SHA=20261105-channel8
REPO_OWNER=${REPO_OWNER:-ClashGate}
REPO_NAME=${REPO_NAME:-ClashGate}
REPO_SLUG=${REPO_SLUG:-$REPO_OWNER/$REPO_NAME}
# Update channel: stable (正式) → ClashGate/ClashGate@main ; test (测试) → ClashGate/ClashGate@test
UPDATE_CHANNEL=${UPDATE_CHANNEL:-}
# Only a REPO_TARBALL given by the caller counts as a pin (the default below must not).
if [[ -n ${REPO_TARBALL:-} ]]; then REPO_TARBALL_PINNED=1; fi
REPO_BRANCH=${REPO_BRANCH:-test}
REPO_TARBALL=${REPO_TARBALL:-https://github.com/$REPO_SLUG/archive/refs/heads/$REPO_BRANCH.tar.gz}
INSTALL_RAW_URL=https://raw.githubusercontent.com/$REPO_SLUG/$REPO_BRANCH/install.sh
CS_ROOT=/etc/clashgate
SELF_BIN=/usr/local/bin/clashgate
BIN=$CS_ROOT/mihomo
CONF_DIR=$CS_ROOT
CONF=$CONF_DIR/config.yaml
STATE=$CONF_DIR/nodes.tsv                    # name port uuid private pub shortid sni dec enc
FRAG_CONTROLLER=$CONF_DIR/controller.yaml    # external-controller-tls + zashboard (cert modes)
FRAG_REALITY=$CONF_DIR/listeners.reality.yaml
FRAG_EXTRA=$CONF_DIR/listeners.extra.yaml    # owned by the panel
FRAG_PROXIES=$CONF_DIR/proxies.extra.yaml    # outbound proxies owned by the panel
FRAG_PROVIDERS=$CONF_DIR/providers.extra.yaml # outbound proxy-providers owned by the panel
FRAG_RULE_PROVIDERS=$CONF_DIR/routing.rule-providers.yaml
FRAG_PROXY_GROUPS=$CONF_DIR/routing.proxy-groups.yaml
FRAG_RULES=$CONF_DIR/routing.rules.yaml
ROUTING_JSON=$CS_ROOT/routing.json
ROUTING_DIR=$CS_ROOT/routing
CUSTOM_CONF=$CONF_DIR/custom_config.yaml     # user-supplied full server config (custom mode)
CLIENT_DIR=$CS_ROOT/client
UNIT=/etc/systemd/system/mihomo.service
LIB_DIR=$CS_ROOT
CS_ETC=$CS_ROOT
ENV_FILE=$CS_ETC/clashgate.env
PANEL_CFG=$CS_ETC/panel.json
ACME_HOME=$CS_ETC/acme.sh                    # acme.sh 安装目录（--home），账户与证书都在这里
ACMESH_VERSION=3.1.6                         # 固定版本，避免上游参数变动
REPO_API=https://api.github.com/repos/MetaCubeX/mihomo/releases/latest
REALITY_SNI_POOL=(
  www.microsoft.com
  www.apple.com
  addons.mozilla.org
  www.yahoo.com
  www.amd.com
  www.nvidia.com
  www.samsung.com
  www.cisco.com
  www.oracle.com
  www.lovelive-anime.jp
)
DOMAIN_RE='^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$'
WILDCARD_DOMAIN_RE='^(\*\.)?([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$'

PKG_MGR=""
MODE=no-cert MODE_SET=0 NODES=1 VPS_NAME="" SERVER_IP=""   # NODES：默认生成 1 个 Reality 节点，更多节点在面板添加
CERT_MODE=port CERT_MODE_SET=0 CF_TOKEN=""                 # CERT_MODE：port（端口模式）| dns（DNS API 模式）| manual（手动证书模式）
if [[ ${REPO_NAME:-ClashGate} == ClashGateBeat ]]; then
  TLS=${TLS:-staging}
else
  TLS=${TLS:-production}
fi
DOMAIN="" EMAIL="" PANEL_PORT=""                           # 默认 Let's Encrypt 证书（production）；面板端口随机选空闲高端口
CONTROLLER_PORT="" MIHOMO_SECRET=""                        # Mihomo external-controller-tls + zashboard 随机空闲高端口与密钥
PANEL_PASS="" PANEL_HASH="" SUB_TOKEN="" WARNINGS=()
STEP=0; TOTAL=8

log()  { _tr_msg "$*"; printf '\033[1;34m[%d/%d]\033[0m %s\n' "$((++STEP))" "$TOTAL" "$REPLY"; }

info() { _tr_msg "$*"; printf '    %s\n' "$REPLY"; }

warn() { _tr_msg "$*"; printf '\033[1;33m%s\033[0m%s\n' "$(L 警告： 'Warning: ')" "$REPLY" >&2; WARNINGS+=("$REPLY"); }

die()  { local m=$1 extra=""; shift; ((!$#)) || extra=$'\n'"$*"; _tr_msg "$m"; printf '\033[1;31m%s\033[0m%s%s\n' "$(L 错误： 'Error: ')" "$REPLY" "$extra" >&2; exit 1; }

need_root() { [[ $EUID -eq 0 ]] || die "请以 root 身份运行（可先执行 sudo -i 再运行安装命令）"; }

# ------------------------------------------------------------ one-click helpers
has_tty() { [[ -t 1 ]] && { : </dev/tty; } 2>/dev/null; }

ask() { # ask "提示" 默认值  -> 读取 /dev/tty（curl|bash 时 stdin 是脚本本身）
  local ans=""
  printf '%s' "$1" >/dev/tty
  read -r ans </dev/tty || true
  printf '%s' "${ans:-$2}"
}

detect_pkg_mgr() {
  if command -v apt-get >/dev/null 2>&1; then
    PKG_MGR=apt
  elif command -v dnf >/dev/null 2>&1; then
    PKG_MGR=dnf
  elif command -v yum >/dev/null 2>&1; then
    PKG_MGR=yum
  else
    PKG_MGR=""
  fi
}

check_os() {
  [[ "$(uname -s)" == Linux ]] || die "仅支持 Linux 系统（当前：$(uname -s)）"
  [[ -r /etc/os-release ]] || die "无法识别操作系统（缺少 /etc/os-release）"
  # shellcheck disable=SC1091
  . /etc/os-release
  local os_name="${PRETTY_NAME:-${ID:-未知}}"
  command -v systemctl >/dev/null 2>&1 || die "不支持当前系统（$os_name）：需要 systemd 作为服务管理器"
  detect_pkg_mgr
  [[ -n $PKG_MGR ]] || die "不支持当前系统（$os_name）：需要支持 apt / dnf / yum 的主流服务端发行版（Ubuntu / Debian / Rocky / AlmaLinux / Fedora / CentOS 等）"
}

rand_sni() {
  echo "${REALITY_SNI_POOL[$((RANDOM % ${#REALITY_SNI_POOL[@]}))]}"
}

arch() {
  case "$(uname -m)" in
    x86_64|amd64) echo amd64 ;;
    aarch64|arm64) echo arm64 ;;
    armv7l) echo armv7 ;;
    *) die "不支持的 CPU 架构：$(uname -m)" ;;
  esac
}

apply_update_channel() { # map UPDATE_CHANNEL → repo + branch (does not override explicit REPO_TARBALL pin)
  case ${UPDATE_CHANNEL:-} in
    stable|production|正式)
      UPDATE_CHANNEL=stable
      REPO_OWNER=ClashGate
      REPO_NAME=ClashGate
      REPO_BRANCH=main
      ;;
    test|beat|测试)
      UPDATE_CHANNEL=test
      REPO_OWNER=ClashGate
      REPO_NAME=ClashGate
      REPO_BRANCH=test
      ;;
  esac
  REPO_SLUG=${REPO_OWNER}/${REPO_NAME}
  if [[ -z ${REPO_TARBALL_PINNED:-} ]]; then
    REPO_TARBALL=https://github.com/$REPO_SLUG/archive/refs/heads/$REPO_BRANCH.tar.gz
  fi
  INSTALL_RAW_URL=https://raw.githubusercontent.com/$REPO_SLUG/$REPO_BRANCH/install.sh
}

load_env() { # persisted install settings; CLI flags given this run win
  [[ -r $ENV_FILE ]] || return 0
  local k v
  while IFS='=' read -r k v; do
    v=${v%\"}; v=${v#\"}
    case "$k" in
      VPS_NAME)   [[ -n $VPS_NAME ]]  || VPS_NAME=$v ;;
      SERVER_IP)  [[ -n $SERVER_IP ]] || SERVER_IP=$v ;;
      REPO_OWNER|REPO_NAME|REPO_SLUG|REPO_BRANCH|UPDATE_CHANNEL) printf -v "$k" '%s' "$v" ;;
      MODE|CERT_MODE|CF_TOKEN|DOMAIN|TLS|EMAIL|PANEL_PORT|CONTROLLER_PORT|MIHOMO_SECRET) printf -v "$k" '%s' "$v" ;;
    esac
  done < "$ENV_FILE"
  # Legacy Beat installs without UPDATE_CHANNEL keep ClashGateBeat until the panel sets a channel.
  if [[ -z ${UPDATE_CHANNEL:-} && ${REPO_NAME:-} == ClashGateBeat ]]; then
    REPO_BRANCH=${REPO_BRANCH:-main}
    REPO_SLUG=${REPO_SLUG:-$REPO_OWNER/$REPO_NAME}
    if [[ -z ${REPO_TARBALL_PINNED:-} ]]; then
      REPO_TARBALL=https://github.com/$REPO_SLUG/archive/refs/heads/$REPO_BRANCH.tar.gz
    fi
    INSTALL_RAW_URL=https://raw.githubusercontent.com/$REPO_SLUG/$REPO_BRANCH/install.sh
    return 0
  fi
  apply_update_channel
}

save_env() {
  install -d -m 775 "$CS_ROOT"
  umask 077
  cat > "$ENV_FILE" <<EOF
MODE="$MODE"
CERT_MODE="$CERT_MODE"
VPS_NAME="$VPS_NAME"
SERVER_IP="$SERVER_IP"
DOMAIN="$DOMAIN"
TLS="$TLS"
EMAIL="$EMAIL"
PANEL_PORT="$PANEL_PORT"
CONTROLLER_PORT="$CONTROLLER_PORT"
MIHOMO_SECRET="$MIHOMO_SECRET"
CF_TOKEN="$CF_TOKEN"
UPDATE_CHANNEL="${UPDATE_CHANNEL:-}"
REPO_OWNER="${REPO_OWNER:-ClashGate}"
REPO_NAME="${REPO_NAME:-ClashGate}"
REPO_SLUG="${REPO_SLUG:-$REPO_OWNER/$REPO_NAME}"
REPO_BRANCH="${REPO_BRANCH:-main}"
EOF
  # 开发用（不写入用户文档）：指向本地 pebble 等 ACME 测试服务，定时续期也沿用
  if [[ -n ${CS_ACME_SERVER:-} ]]; then printf 'CS_ACME_SERVER="%s"\n' "$CS_ACME_SERVER" >> "$ENV_FILE"; fi
  if [[ -n ${CS_ACME_INSECURE:-} ]]; then printf 'CS_ACME_INSECURE="%s"\n' "$CS_ACME_INSECURE" >> "$ENV_FILE"; fi
  if [[ -n ${CS_DNS_HOOK:-} ]]; then printf 'CS_DNS_HOOK="%s"\n' "$CS_DNS_HOOK" >> "$ENV_FILE"; fi
  if [[ -n ${CS_DNSSLEEP:-} ]]; then printf 'CS_DNSSLEEP="%s"\n' "$CS_DNSSLEEP" >> "$ENV_FILE"; fi
  chmod 600 "$ENV_FILE"
}

svc_state() {
  local st
  st=$(systemctl is-active "$1" 2>/dev/null || true)
  case $st in
    active)   printf '\033[1;32m%s\033[0m' "$(L 运行中 running)" ;;
    inactive) printf '\033[1;31m%s\033[0m' "$(L 已停止 stopped)" ;;
    failed)   printf '\033[1;31m%s\033[0m' "$(L 失败 failed)" ;;
    *)        printf '%s' "${st:-$(L 未知 unknown)}" ;;
  esac
}

require_installed() { [[ -f $STATE ]] || die "尚未安装，请先运行一键安装命令"; }

require_panel() { [[ $MODE == auto-cert && -f $PANEL_CFG ]] || die "该功能仅在自动证书或手动证书模式下提供（当前：无证书模式）"; }

tls_label() {
  if [[ ${CERT_MODE:-port} == manual ]]; then
    local iss
    iss=$(cert_issuer 2>/dev/null || true)
    printf '用户自备证书%s' "${iss:+（$iss）}"
    return 0
  fi
  if [[ ${REPO_NAME:-ClashGate} == ClashGateBeat && $TLS == staging ]]; then
    printf 'Let'"'"'s Encrypt 测试证书（staging）'
    return 0
  fi
  case $TLS in
    internal) printf '自签证书（仅开发调试）' ;;
    *)        printf 'Let'"'"'s Encrypt 证书' ;;
  esac
}

cert_mode_label() {
  case ${CERT_MODE:-port} in
    dns)    printf 'DNS API 模式' ;;
    manual) printf '手动证书模式' ;;
    *)      printf '端口模式' ;;
  esac
}

mode_label() {
  if [[ $MODE == auto-cert ]]; then
    if [[ ${CERT_MODE:-port} == manual ]]; then printf '手动证书模式'
    else printf '自动证书模式（%s）' "$(cert_mode_label)"; fi
  else
    printf '无证书模式'
  fi
}

record_update_source() { # persist channel tip id after a successful self-update
  local sha="" branch=${REPO_BRANCH:-main} slug=${REPO_SLUG:-ClashGate/ClashGate} channel=${UPDATE_CHANNEL:-}
  if [[ -f $LIB_DIR/scripts/lib/common.sh ]]; then
    sha=$(sed -n 's/^CS_SOURCE_SHA=//p' "$LIB_DIR/scripts/lib/common.sh" | head -n1)
    [[ -n $sha ]] && sha="$sha+$(sed -n 's/^CS_VERSION=//p' "$LIB_DIR/scripts/lib/common.sh" | head -n1)"
  fi
  if [[ -z $sha ]]; then
    sha=$(curl -fsSL --retry 2 -H 'Accept: application/vnd.github+json'       "https://api.github.com/repos/$slug/commits/$branch" 2>/dev/null       | sed -n 's/.*"sha": *"\([0-9a-f]\{40\}\)".*/\1/p' | head -n1)
  fi
  [[ -n $sha ]] || return 0
  umask 077
  cat > "$CS_ROOT/update_source.json" <<EOF
{"channel":"$channel","repo":"$slug","branch":"$branch","sha":"$sha","version":"$CS_VERSION","updated_at":$(date +%s)}
EOF
  chmod 600 "$CS_ROOT/update_source.json" 2>/dev/null || true
}

fetch_repo() { # 下载公开仓库当前通道分支到目录 $1（直连 GitHub，不用任何代理）
  local branch=${REPO_BRANCH:-main}
  printf '正在从 GitHub (%s @ %s) 下载安装文件……\n' "$REPO_SLUG" "$branch"
  curl -fsSL --retry 3 "$REPO_TARBALL" | tar -xz -C "$1" --strip-components=1 \
    || { rm -rf "$1"; die "下载失败：$REPO_TARBALL（请确认服务器可以访问 GitHub）"; }
  [[ -f $1/install.sh && -f $1/scripts/cmd/clashgate.sh ]] || { rm -rf "$1"; die "下载的文件不完整"; }
}

install_files() { # 把源码树 $CS_HOME 安装到统一目录 /etc/clashgate（保留已有配置/证书/内核）
  install -d -m 775 "$CS_ROOT"
  install -d -m 700 "$CLIENT_DIR"
  local stage=$CS_ROOT/.stage.$$ d
  rm -rf "$stage"; install -d -m 755 "$stage"
  for d in install.sh uninstall.sh panel resources scripts; do cp -r "$CS_HOME/$d" "$stage/"; done
  rm -rf "$stage/panel/__pycache__" "$stage/panel/web/node_modules"
  chmod 755 "$stage/install.sh" "$stage/uninstall.sh" "$stage/scripts/cmd/clashgate.sh" "$stage/scripts/certctl.sh" "$stage/panel/panel.py"
  for d in install.sh uninstall.sh panel resources scripts; do
    rm -rf "$CS_ROOT/$d.old"
    if [[ -e $CS_ROOT/$d ]]; then mv "$CS_ROOT/$d" "$CS_ROOT/$d.old"; fi
    mv "$stage/$d" "$CS_ROOT/$d"
    rm -rf "$CS_ROOT/$d.old"
  done
  rm -rf "$stage"
  ln -sfn "$CS_ROOT/scripts/cmd/clashgate.sh" "$SELF_BIN"
}
