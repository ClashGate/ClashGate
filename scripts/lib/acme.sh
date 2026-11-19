# shellcheck shell=bash
# acme.sh 安装（固定版本，装到 --home，不改 root 的 crontab / profile）。
# 由 lib/cert.sh（安装时）和 certctl.sh（手动证书切到自动证书时补装）共用。
#   acme_fetch_install <home> <version> [email]   成功返回 0，失败返回 1（不打印、不退出）
acme_fetch_install() {
  local home=$1 ver=$2 email=${3:-} tmp opts=()
  tmp=$(mktemp -d)
  if ! curl -fsSL --retry 3 "https://github.com/acmesh-official/acme.sh/archive/refs/tags/$ver.tar.gz" \
      | tar -xz -C "$tmp" --strip-components=1; then
    rm -rf "$tmp"; return 1
  fi
  [[ -n $email ]] && opts+=(--accountemail "$email")
  install -d -m 700 "$home"
  ( cd "$tmp" && ./acme.sh --install --home "$home" --no-cron --no-profile "${opts[@]}" >/dev/null 2>&1 ) \
    || { rm -rf "$tmp"; return 1; }
  rm -rf "$tmp"
  chmod 700 "$home"
  [[ -x $home/acme.sh ]]
}
