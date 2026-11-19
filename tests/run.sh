#!/usr/bin/env bash
# ClashGate test suite: shell lint, panel unit tests (mihomo -t), cluster e2e, i18n parity, frontend build.
#   tests/run.sh            # everything
#   tests/run.sh --no-build # skip the frontend build check
# MIHOMO_BIN overrides the core binary; otherwise the pinned version is downloaded to tests/.cache.
set -euo pipefail
cd "$(dirname "$0")/.."
MIHOMO_VERSION=v1.19.34
BUILD=1
[[ ${1:-} == --no-build ]] && BUILD=0
step() { printf '\n== %s\n' "$*"; }

step "bash -n"
mapfile -t SH < <(git ls-files '*.sh')
for f in "${SH[@]}"; do bash -n "$f"; done
echo "ok (${#SH[@]} files)"

step "shellcheck"
if command -v shellcheck >/dev/null; then
  # SC2034: globals defined in sourced libs and used by other files.
  shellcheck -S warning -e SC2034 "${SH[@]}" && echo ok
else
  echo "shellcheck not installed; skipped" >&2
  [[ -z ${CI:-} ]] || exit 1
fi

step "mihomo ${MIHOMO_VERSION}"
if [[ -z ${MIHOMO_BIN:-} ]]; then
  MIHOMO_BIN=tests/.cache/mihomo
  if ! { [[ -x $MIHOMO_BIN ]] && "$MIHOMO_BIN" -v | grep -q "$MIHOMO_VERSION"; }; then
    mkdir -p tests/.cache
    case $(uname -m) in x86_64) a=amd64 ;; aarch64|arm64) a=arm64 ;; *) echo "unsupported arch" >&2; exit 1 ;; esac
    curl -fsSL "https://github.com/MetaCubeX/mihomo/releases/download/${MIHOMO_VERSION}/mihomo-linux-${a}-${MIHOMO_VERSION}.gz" \
      | gunzip > "$MIHOMO_BIN"
    chmod +x "$MIHOMO_BIN"
  fi
fi
export MIHOMO_BIN
"$MIHOMO_BIN" -v | head -1

step "panel tests"
python3 -m unittest discover -s tests -v

step "cluster end-to-end (two local panels over HTTPS)"
if command -v openssl >/dev/null && command -v ss >/dev/null && command -v curl >/dev/null; then
  python3 tests/cluster_e2e.py
else
  echo "openssl/ss/curl missing; skipped" >&2
  [[ -z ${CI:-} ]] || exit 1
fi

step "i18n parity"
python3 tests/check_i18n.py

if [[ $BUILD == 1 ]]; then
  step "frontend build (committed panel/dist must match)"
  (cd panel/web && { [[ -d node_modules ]] || npm ci --no-audit --no-fund; } && npm run build)
  git diff --exit-code --stat -- panel/dist
  echo ok
fi
echo; echo "all tests passed"
