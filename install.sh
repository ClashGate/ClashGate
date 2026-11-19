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
REPO_TARBALL=${REPO_TARBALL:-https://github.com/$REPO_SLUG/archive/refs/heads/${REPO_BRANCH:-main}.tar.gz}
_src=${BASH_SOURCE[0]:-}
if [[ -n $_src && -f $_src ]]; then HERE="$(cd "$(dirname "$_src")" && pwd)"; else HERE=""; fi

# 语言 / Language / Язык：CLASHGATE_LANG=zh|en|ru 直接指定（跳过选择）；否则交互终端里先选择，
# 默认值取已保存的语言或 LANG/LC_ALL（en* -> English，ru* -> Русский，其余中文）。选择会保存，之后的 clashgate 命令沿用。
_norm() { case ${1:-} in en|EN|en_*|en-*) echo en ;; ru|RU|ru_*|ru-*) echo ru ;; zh|ZH|zh_*|zh-*) echo zh ;; esac; }
_lang=$(_norm "${CLASHGATE_LANG:-}")
if [[ -z $_lang ]]; then
  _def=$(sed -n 's/^CLASHGATE_LANG="\{0,1\}\([A-Za-z_-]*\)"\{0,1\}$/\1/p' /etc/clashgate/clashgate.env 2>/dev/null | tail -n1 || true)
  _def=$(_norm "$_def"); [[ -n $_def ]] || _def=$(_norm "${LC_ALL:-}"); [[ -n $_def ]] || _def=$(_norm "${LANG:-}"); _def=${_def:-zh}
  _lang=$_def
  if [[ -t 1 ]] && { : </dev/tty; } 2>/dev/null; then
    case $_def in en) _n=2 ;; ru) _n=3 ;; *) _n=1 ;; esac
    printf '\n\033[1mLanguage / 语言 / Язык\033[0m\n  1) 中文\n  2) English\n  3) Русский\n' >/dev/tty
    while :; do
      printf '[1/2/3] (Enter = %s): ' "$_n" >/dev/tty
      _c=""; read -r _c </dev/tty || true
      case ${_c:-$_n} in 1) _lang=zh; break ;; 2) _lang=en; break ;; 3) _lang=ru; break ;; esac
    done
  fi
  CS_LANG_PICKED=1; export CS_LANG_PICKED
fi
CLASHGATE_LANG=$_lang; export CLASHGATE_LANG
L() { case $_lang in en) printf '%s' "$2" ;; ru) printf '%s' "$3" ;; *) printf '%s' "$1" ;; esac; }
die() { printf '\033[1;31m%s\033[0m%s\n' "$(L 错误： 'Error: ' 'Ошибка: ')" "$*" >&2; exit 1; }

if [[ -n $HERE && -f $HERE/scripts/cmd/clashgate.sh ]]; then
  CS_DEFAULT_ACTION=install exec bash "$HERE/scripts/cmd/clashgate.sh" "$@"
fi

command -v curl >/dev/null || die "$(L "缺少 curl，请先安装（如 apt-get install -y curl 或 dnf/yum install -y curl）" "curl is missing; install it first (e.g. apt-get install -y curl or dnf/yum install -y curl)" "curl не найден; сначала установите его (например, apt-get install -y curl или dnf/yum install -y curl)")"
command -v tar >/dev/null || die "$(L "缺少 tar，请先安装（如 apt-get install -y tar 或 dnf/yum install -y tar）" "tar is missing; install it first (e.g. apt-get install -y tar or dnf/yum install -y tar)" "tar не найден; сначала установите его (например, apt-get install -y tar или dnf/yum install -y tar)")"
tmp=$(mktemp -d /tmp/clashgate.XXXXXX)
printf "$(L '正在从 GitHub (%s) 下载安装文件……' 'Downloading install files from GitHub (%s)...' 'Загрузка установочных файлов с GitHub (%s)...')"$'\n' "$REPO_SLUG"
curl -fsSL --retry 3 "$REPO_TARBALL" | tar -xz -C "$tmp" --strip-components=1 \
  || { rm -rf "$tmp"; die "$(L "下载失败：$REPO_TARBALL（请确认服务器可以访问 GitHub）" "Download failed: $REPO_TARBALL (make sure the server can reach GitHub)" "Ошибка загрузки: $REPO_TARBALL (убедитесь, что сервер может подключиться к GitHub)")"; }
[[ -f $tmp/scripts/cmd/clashgate.sh ]] || { rm -rf "$tmp"; die "$(L 下载的文件不完整 'The downloaded files are incomplete' 'Загруженные файлы неполные')"; }
CS_BOOTSTRAP_TMP=$tmp CS_DEFAULT_ACTION=install exec bash "$tmp/scripts/cmd/clashgate.sh" "$@"
