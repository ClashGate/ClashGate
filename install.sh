#!/usr/bin/env bash
# ClashGate 一键安装入口
#
#   curl -fsSL https://raw.githubusercontent.com/ClashGate/ClashGate/main/install.sh | bash
#
# 通过 curl|bash 运行时只有本文件：先从公开仓库下载完整文件（直连 GitHub，不使用任何代理），
# 再交给 scripts/cmd/clashgate.sh 执行安装（按提示选择模式、填写域名）。
set -Eeuo pipefail

REPO_OWNER=${REPO_OWNER:-ClashGate}
REPO_NAME=${REPO_NAME:-ClashGate}
REPO_SLUG=${REPO_SLUG:-$REPO_OWNER/$REPO_NAME}
REPO_TARBALL=${REPO_TARBALL:-https://github.com/$REPO_SLUG/archive/refs/heads/main.tar.gz}
_src=${BASH_SOURCE[0]:-}
if [[ -n $_src && -f $_src ]]; then HERE="$(cd "$(dirname "$_src")" && pwd)"; else HERE=""; fi

# CLASHGATE_LANG=en|zh（默认中文；未设时 LANG/LC_ALL 以 en 开头则英文）
case ${CLASHGATE_LANG:-${LC_ALL:-${LANG:-}}} in en*|EN*) _en=1 ;; *) _en=0 ;; esac
L() { if ((_en)); then printf '%s' "$2"; else printf '%s' "$1"; fi; }
die() { printf '\033[1;31m%s\033[0m%s\n' "$(L 错误： 'Error: ')" "$*" >&2; exit 1; }

if [[ -n $HERE && -f $HERE/scripts/cmd/clashgate.sh ]]; then
  CS_DEFAULT_ACTION=install exec bash "$HERE/scripts/cmd/clashgate.sh" "$@"
fi

command -v curl >/dev/null || die "$(L "缺少 curl，请先安装（如 apt-get install -y curl 或 dnf/yum install -y curl）" "curl is missing; install it first (e.g. apt-get install -y curl or dnf/yum install -y curl)")"
command -v tar >/dev/null || die "$(L "缺少 tar，请先安装（如 apt-get install -y tar 或 dnf/yum install -y tar）" "tar is missing; install it first (e.g. apt-get install -y tar or dnf/yum install -y tar)")"
tmp=$(mktemp -d /tmp/clashgate.XXXXXX)
printf "$(L '正在从 GitHub (%s) 下载安装文件……' 'Downloading install files from GitHub (%s)...')"$'\n' "$REPO_SLUG"
curl -fsSL --retry 3 "$REPO_TARBALL" | tar -xz -C "$tmp" --strip-components=1 \
  || { rm -rf "$tmp"; die "$(L "下载失败：$REPO_TARBALL（请确认服务器可以访问 GitHub）" "Download failed: $REPO_TARBALL (make sure the server can reach GitHub)")"; }
[[ -f $tmp/scripts/cmd/clashgate.sh ]] || { rm -rf "$tmp"; die "$(L 下载的文件不完整 'The downloaded files are incomplete')"; }
CS_BOOTSTRAP_TMP=$tmp CS_DEFAULT_ACTION=install exec bash "$tmp/scripts/cmd/clashgate.sh" "$@"
