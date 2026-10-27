#!/usr/bin/env bash
# clashgate 卸载入口（等同于 clashgate uninstall）
set -Eeuo pipefail
HERE="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
exec bash "$HERE/scripts/cmd/clashgate.sh" uninstall "$@"
