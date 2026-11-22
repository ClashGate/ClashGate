# shellcheck shell=bash
# clashgate Mihomo 相关：依赖、内核、Reality 节点、服务端/客户端配置、systemd

install_deps() {
  log "安装依赖"
  detect_pkg_mgr
  [[ -n $PKG_MGR ]] || die "未检测到受支持的包管理器（需要 apt / dnf / yum）"
  local missing=()
  for c in curl gzip tar jq openssl; do command -v "$c" >/dev/null || missing+=("$c"); done
  if ! command -v ss >/dev/null; then
    [[ $PKG_MGR == apt ]] && missing+=(iproute2) || missing+=(iproute)
  fi
  command -v flock >/dev/null || missing+=(util-linux)
  if [[ $MODE == auto-cert ]]; then
    command -v python3 >/dev/null || missing+=(python3)
    if [[ ${CERT_MODE:-port} != manual ]]; then
      command -v socat >/dev/null || missing+=(socat)     # acme.sh standalone 模式需要
      if ! command -v getent >/dev/null; then
        [[ $PKG_MGR == apt ]] && missing+=(libc-bin) || missing+=(glibc-common)
      fi
    fi
  fi
  if ((${#missing[@]})); then
    info "$PKG_MGR 安装：${missing[*]}"
    local i
    if [[ $PKG_MGR == apt ]]; then
      for i in 1 2 3; do apt-get update -qq >/dev/null 2>&1 && break; ((i < 3)) || die "apt-get update 失败，请检查软件源和网络"; sleep 5; done
      for i in 1 2 3; do
        DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${missing[@]}" ca-certificates >/dev/null 2>&1 && break
        ((i < 3)) || die "依赖安装失败：${missing[*]}"; sleep 5
      done
    else
      for i in 1 2 3; do
        "$PKG_MGR" install -y -q "${missing[@]}" ca-certificates >/dev/null 2>&1 && break
        "$PKG_MGR" install -y -q epel-release >/dev/null 2>&1 || true
        "$PKG_MGR" install -y -q "${missing[@]}" ca-certificates >/dev/null 2>&1 && break
        ((i < 3)) || die "依赖安装失败（$PKG_MGR）：${missing[*]}"; sleep 5
      done
    fi
  fi
}

# x86-64 microarchitecture level (1/2/3) from /proc/cpuinfo flags. Mihomo's plain amd64 build needs v3
# (AVX2 etc.); older CPUs and many VPS CPU models only have v1/v2 and fail with
# "This program can only be run on AMD64 processors with v3 microarchitecture support".
amd64_level() {
  local f x
  f=" $(grep -m1 -E '^flags' /proc/cpuinfo 2>/dev/null | cut -d: -f2) "
  for x in cx16 lahf_lm popcnt pni sse4_1 sse4_2 ssse3; do [[ $f == *" $x "* ]] || { echo 1; return; }; done
  for x in avx avx2 bmi1 bmi2 f16c fma abm movbe xsave; do [[ $f == *" $x "* ]] || { echo 2; return; }; done
  echo 3
}

# Release asset names to try for this machine, best first (each is checked with `-v` before use).
core_asset_candidates() { # <arch> <tag>
  local a=$1 tag=$2
  if [[ $a == amd64 ]]; then
    case $(amd64_level) in
      3) printf '%s\n' "amd64-v3" "amd64" "amd64-v2" "amd64-v1" "amd64-compatible" ;;
      2) printf '%s\n' "amd64-v2" "amd64-v1" "amd64-compatible" ;;
      *) printf '%s\n' "amd64-v1" "amd64-compatible" ;;
    esac | sed "s/.*/mihomo-linux-&-${tag}.gz/"
  else
    echo "mihomo-linux-${a}-${tag}.gz"
  fi
}

# Latest stable release: the GitHub API first (with the file list); if it fails (rate limit, a TLS
# reset like "unexpected eof while reading"), the tag from the releases/latest redirect, and the
# download URLs are built from the file names. Sets CORE_TAG and CORE_REL (API JSON, may be empty).
CORE_TAG=""; CORE_REL=""; CORE_ERR=""
core_latest() {
  CORE_TAG=""; CORE_REL=""
  local i rel loc
  for i in 1 2; do
    if rel=$(curl -fsSL --connect-timeout 10 --max-time 20 "$REPO_API" 2>/dev/null); then
      CORE_TAG=$(jq -r '.tag_name // empty' <<<"$rel" 2>/dev/null) || CORE_TAG=""
      if [[ $CORE_TAG =~ ^v[0-9]+(\.[0-9]+)+$ ]]; then CORE_REL=$rel; return 0; fi
    fi
    sleep 2
  done
  for i in 1 2; do
    loc=$(curl -fsSIL --connect-timeout 10 --max-time 20 -o /dev/null -w '%{url_effective}' \
      "https://github.com/MetaCubeX/mihomo/releases/latest" 2>/dev/null) || loc=""
    CORE_TAG=${loc##*/tag/}
    [[ $CORE_TAG =~ ^v[0-9]+(\.[0-9]+)+$ ]] && return 0
    CORE_TAG=""; sleep 2
  done
  return 1
}

# Download $CORE_TAG for this CPU and install it. The running core is only replaced by a file that
# runs here (`-v`). On failure nothing changes and CORE_ERR is download | run | nobuild.
core_download() {
  local a url tmp name tried=0 got=0
  a=$(arch)
  tmp=$(mktemp)
  while read -r name; do
    if [[ -n $CORE_REL ]]; then
      url=$(jq -r --arg n "$name" '.assets[] | select(.name==$n) | .browser_download_url' <<<"$CORE_REL" 2>/dev/null)
      [[ -n "$url" ]] || continue
    else
      url="https://github.com/MetaCubeX/mihomo/releases/download/${CORE_TAG}/${name}"
    fi
    tried=$((tried + 1))
    curl -fsSL --retry 3 --connect-timeout 15 -o "$tmp" "$url" 2>/dev/null || continue
    got=1
    gzip -dc "$tmp" > "$BIN.new" 2>/dev/null || { rm -f "$BIN.new"; continue; }
    chmod 755 "$BIN.new"
    if "$BIN.new" -v >/dev/null 2>&1; then
      rm -f "$tmp"
      mv "$BIN.new" "$BIN"
      ln -sfn "$BIN" /usr/local/bin/mihomo
      return 0
    fi
    rm -f "$BIN.new"   # this CPU cannot run that build: quietly try the next one
  done < <(core_asset_candidates "$a" "$CORE_TAG")
  rm -f "$tmp"
  if ((got)); then CORE_ERR=run; elif ((tried)) || [[ -z $CORE_REL ]]; then CORE_ERR=download; else CORE_ERR=nobuild; fi
  return 1
}

core_err_text() {
  case $CORE_ERR in
    run) echo "下载的 Mihomo 无法运行" ;;
    nobuild) echo "版本 $CORE_TAG 中没有找到适合 $(arch) 的 Mihomo 内核文件" ;;
    *) echo "下载 Mihomo 内核失败（请确认服务器可以访问 GitHub）" ;;
  esac
}

install_core() { # fresh install: a core is required
  log "安装最新稳定版 Mihomo 内核"
  install -d -m 1775 "$CS_ROOT"
  core_latest || die "无法获取 Mihomo 版本信息（请确认服务器可以访问 GitHub）"
  core_download || die "$(core_err_text)"
  info "已安装 $CORE_TAG -> $BIN"
}

# clashgate update: download the core only when it is not the latest. When the version cannot be
# fetched or the download fails, the panel update goes on and the end of the update says so
# (CORE_NOTE, also left in core_update_failed for the panel). CORE_UPDATED=1: a new binary.
CORE_UPDATED=0; CORE_NOTE=""
update_core() {
  log "检查 Mihomo 内核"
  install -d -m 1775 "$CS_ROOT"
  rm -f "$CS_ROOT/core_update_failed"
  local cur
  cur=$("$BIN" -v 2>/dev/null | grep -oE 'v[0-9]+(\.[0-9]+)+' | head -n1) || cur=""
  if ! core_latest; then
    CORE_NOTE="Mihomo 内核更新失败：无法获取最新版本信息，已跳过内核更新，面板照常更新（当前内核 ${cur:--}）"
    printf 'fetch\t%s\t\n' "${cur:--}" > "$CS_ROOT/core_update_failed"
    info "无法获取 Mihomo 最新版本信息，跳过内核更新"
    return 0
  fi
  if [[ -n $cur && $cur == "$CORE_TAG" ]]; then
    info "Mihomo 内核已是最新版本 $cur"
    return 0
  fi
  if core_download; then
    CORE_UPDATED=1
    info "已更新 Mihomo 内核：${cur:--} -> $CORE_TAG"
    return 0
  fi
  case $CORE_ERR in
    run) CORE_NOTE="Mihomo 内核更新失败：下载的内核无法在这台服务器上运行，已跳过内核更新，面板照常更新（当前内核 ${cur:--}，最新 $CORE_TAG）" ;;
    nobuild) CORE_NOTE="Mihomo 内核更新失败：最新版本没有适合这台服务器的内核文件，已跳过内核更新，面板照常更新（当前内核 ${cur:--}，最新 $CORE_TAG）" ;;
    *) CORE_NOTE="Mihomo 内核更新失败：下载失败，已跳过内核更新，面板照常更新（当前内核 ${cur:--}，最新 $CORE_TAG）" ;;
  esac
  printf '%s\t%s\t%s\n' "$CORE_ERR" "${cur:--}" "$CORE_TAG" > "$CS_ROOT/core_update_failed"
  info "Mihomo 内核下载失败，跳过内核更新"
  return 0
}

IPV4_RE='^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'
IPV6_RE='^[0-9A-Fa-f:]*:[0-9A-Fa-f:]+$'

detect_ip() { # 优先公网 IPv4；没有 IPv4 出口（纯 IPv6 服务器）时用公网 IPv6
  [[ -n "$SERVER_IP" ]] && return
  local u ip
  for u in https://api.ipify.org https://ifconfig.me https://ipv4.icanhazip.com; do
    ip=$(curl -fsS -4 --max-time 5 "$u" 2>/dev/null | tr -d '[:space:]') || continue
    [[ $ip =~ $IPV4_RE ]] && { SERVER_IP=$ip; return; }
  done
  for u in https://api64.ipify.org https://ipv6.icanhazip.com https://ifconfig.co; do
    ip=$(curl -fsS -6 --max-time 5 "$u" 2>/dev/null | tr -d '[:space:]') || continue
    [[ $ip =~ $IPV6_RE ]] && { SERVER_IP=$ip; return; }
  done
  if has_tty; then
    while [[ ! $SERVER_IP =~ $IPV4_RE && ! $SERVER_IP =~ $IPV6_RE ]]; do
      SERVER_IP=$(ask '无法自动探测公网 IP，请手动输入本机公网 IP（IPv4 或 IPv6）：' '')
    done
    return
  fi
  die "无法探测公网 IP，请检查服务器网络"
}

rand_port() {
  local p
  while :; do
    p=$((RANDOM % 20000 + 20000))
    grep -q "	$p	" "$STATE" 2>/dev/null && continue
    [[ $p == "${PANEL_PORT:-}" || $p == "${CONTROLLER_PORT:-}" ]] && continue
    ss -ltun 2>/dev/null | grep -q ":$p " && continue
    echo "$p"; return
  done
}

ensure_user() {
  local nologin=/usr/sbin/nologin
  [[ -x $nologin ]] || nologin=/sbin/nologin
  id mihomo >/dev/null 2>&1 || useradd --system --no-create-home --shell "$nologin" mihomo
  install -d -m 1775 -o root -g mihomo "$CONF_DIR"
  install -d -m 750 -o root -g mihomo "$CONF_DIR/certs"
  install -d -m 700 -o root -g root "$CLIENT_DIR"
}

gen_nodes() {
  log "生成 $NODES 个 VLESS Reality 节点"
  : > "$STATE.new"; chmod 640 "$STATE.new"
  local i kp priv pub vkp dec enc name sni
  for ((i = 1; i <= NODES; i++)); do
    kp=$("$BIN" generate reality-keypair)
    priv=$(awk '/PrivateKey/{print $2}' <<<"$kp")
    pub=$(awk '/PublicKey/{print $2}' <<<"$kp")
    [[ -n "$priv" && -n "$pub" ]] || { rm -f "$STATE.new"; die "Reality 密钥对生成失败"; }
    vkp=$("$BIN" generate vless-x25519)
    dec=$(sed -n 's/.*\[Server\][[:space:]]*decryption:[[:space:]]*"\([^"]*\)".*/\1/p' <<<"$vkp")
    enc=$(sed -n 's/.*\[Client\][[:space:]]*encryption:[[:space:]]*"\([^"]*\)".*/\1/p' <<<"$vkp")
    [[ -n "$dec" && -n "$enc" ]] || { rm -f "$STATE.new"; die "VLESS Encryption 密钥生成失败"; }
    name=$([[ $i -eq 1 ]] && echo "VlessReality" || echo "VlessReality-$i")
    sni=$(rand_sni)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$name" "$(rand_port)" \
      "$(cat /proc/sys/kernel/random/uuid)" "$priv" "$pub" "$(openssl rand -hex 4)" \
      "$sni" "$dec" "$enc" >> "$STATE.new"
  done
  mv -f "$STATE.new" "$STATE"
}

# GEOIP / GEOSITE / IP-ASN 规则用到的地理数据，用 Mihomo 默认查找的文件名放在内核目录（-d）。
# 安装和更新时用系统 curl 下好，mihomo -t 校验和运行都不再自己下载（它的内置 DNS 在校验时可能解析失败）。
GEO_FILES=("geoip.metadb country.mmdb" "GeoSite.dat geosite.dat" "ASN.mmdb GeoLite2-ASN.mmdb")
GEO_BASES=(https://testingcf.jsdelivr.net/gh/MetaCubeX/meta-rules-dat@release https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest)
GEO_FAILED=""
ensure_geodata() {
  local e name remote base ok
  for e in "${GEO_FILES[@]}"; do
    read -r name remote <<<"$e"
    [[ -s $CONF_DIR/$name ]] && continue
    [[ $name == geoip.metadb && -s $CONF_DIR/country.mmdb ]] && continue
    ok=0
    for base in "${GEO_BASES[@]}"; do
      if curl -fsSL --retry 2 --connect-timeout 10 --max-time 300 -o "$CONF_DIR/$name.tmp" "$base/$remote" \
        && (($(stat -c %s "$CONF_DIR/$name.tmp") > 1024)); then
        chmod 644 "$CONF_DIR/$name.tmp"; mv -f "$CONF_DIR/$name.tmp" "$CONF_DIR/$name"
        chown mihomo:mihomo "$CONF_DIR/$name" 2>/dev/null || true
        ok=1; break
      fi
    done
    rm -f "$CONF_DIR/$name.tmp"
    ((ok)) || { GEO_FAILED=$name; return 1; }
  done
}

validate_conf() {
  local d rc=0 f
  d=$(mktemp -d)
  mkdir -p "$d/ui"   # 避免 mihomo -t 校验时临时下载 external-ui
  [[ -d $CONF_DIR/certs ]] && ln -s "$CONF_DIR/certs" "$d/certs"
  [[ -d $CONF_DIR/ruleset ]] && ln -s "$CONF_DIR/ruleset" "$d/ruleset"
  for f in "$CONF_DIR"/*.mmdb "$CONF_DIR"/*.metadb "$CONF_DIR"/*.dat; do
    [[ -f $f ]] && ln -s "$f" "$d/$(basename "$f")"
  done
  SAFE_PATHS="$CONF_DIR" "$BIN" -t -d "$d" -f "$CONF" >/dev/null || rc=$?
  rm -rf "$d"
  return "$rc"
}

ensure_mihomo_secret() {
  [[ $MODE == auto-cert ]] || return 0
  local changed=0
  if [[ -z ${CONTROLLER_PORT:-} ]]; then
    CONTROLLER_PORT=$(rand_port)
    changed=1
  fi
  if [[ -z ${MIHOMO_SECRET:-} ]]; then
    MIHOMO_SECRET=$(openssl rand -base64 32 | tr -dc 'A-Za-z0-9' | head -c 20)
    changed=1
  fi
  ((changed)) && save_env
  return 0
}

render_controller() {
  if [[ $MODE == auto-cert ]]; then
    ensure_mihomo_secret
    if [[ ${CERT_MODE:-port} != manual ]]; then
      [[ -f $CONF_DIR/certs/fullchain.pem && -f $CONF_DIR/certs/privkey.pem ]] \
        || "$LIB_DIR/scripts/certctl.sh" selfsign >/dev/null
    fi
    cat > "$FRAG_CONTROLLER" <<EOF
external-controller-tls: "0.0.0.0:$CONTROLLER_PORT"
tls:
  certificate: $CONF_DIR/certs/fullchain.pem
  private-key: $CONF_DIR/certs/privkey.pem
external-controller-cors:
  allow-origins:
    - '*'
  allow-private-network: true
secret: "$MIHOMO_SECRET"
external-ui: ui
external-ui-url: "https://github.com/Zephyruso/zashboard/releases/latest/download/dist-cdn-fonts.zip"
EOF
  else
    echo "# No external-controller in no-cert mode." > "$FRAG_CONTROLLER"
  fi
  chmod 640 "$FRAG_CONTROLLER"; chown root:mihomo "$FRAG_CONTROLLER"
}

# Seed English default server routing groups and regenerate assemble fragments via panel.py.
seed_routing() {
  local seed="$LIB_DIR/resources/routing"
  [[ -d $seed ]] || return 0
  install -d -m 755 "$ROUTING_DIR"
  if [[ ! -f $ROUTING_JSON ]]; then
    install -m 600 "$seed/defaults.json" "$ROUTING_JSON"
  fi
  local f base
  for f in "$seed"/*.yaml; do
    [[ -f $f ]] || continue
    base=$(basename "$f")
    [[ -f $ROUTING_DIR/$base ]] || install -m 640 "$f" "$ROUTING_DIR/$base"
  done
  if [[ -f $LIB_DIR/panel/panel.py ]]; then
    CS_ROOT="$CS_ROOT" PYTHONPATH="$LIB_DIR/panel${PYTHONPATH:+:$PYTHONPATH}" "$(py_bin || echo python3)" -c \
      'import os,importlib.util,sys; p=os.path.join(os.environ["CS_ROOT"],"panel","panel.py"); spec=importlib.util.spec_from_file_location("cg_panel_seed", p); m=importlib.util.module_from_spec(spec); sys.modules[spec.name]=m; sys.modules.setdefault("panel", m); spec.loader.exec_module(m); m.get_routing().ensure_seeded(force=False)' \
      || warn "分流默认模板生成失败（可稍后在面板「服务端分流」中恢复）"
  fi
  [[ -f $FRAG_RULE_PROVIDERS ]] || : > "$FRAG_RULE_PROVIDERS"
  [[ -f $FRAG_PROXY_GROUPS ]] || printf '%s\n' 'proxy-groups: []' > "$FRAG_PROXY_GROUPS"
  [[ -f $FRAG_RULES ]] || printf '%s\n' 'rules:' '  - MATCH,🐟 漏网之鱼' > "$FRAG_RULES"
  chmod 640 "$FRAG_RULE_PROVIDERS" "$FRAG_PROXY_GROUPS" "$FRAG_RULES" 2>/dev/null || true
  chown root:mihomo "$FRAG_RULE_PROVIDERS" "$FRAG_PROXY_GROUPS" "$FRAG_RULES" "$ROUTING_JSON" 2>/dev/null || true
  chown -R root:mihomo "$ROUTING_DIR" 2>/dev/null || true
}

# config.yaml = custom / template with routing placeholders. Mirrors panel assemble_config().
assemble_config() {
  if [[ -s $CUSTOM_CONF ]]; then
    cp -f "$CUSTOM_CONF" "$CONF.new"
    chmod 640 "$CONF.new"; chown root:mihomo "$CONF.new"
    mv -f "$CONF.new" "$CONF"
    return 0
  fi
  [[ -f $FRAG_CONTROLLER ]] || render_controller
  [[ -f $FRAG_PROXIES ]] || : > "$FRAG_PROXIES"
  [[ -f $FRAG_PROVIDERS ]] || : > "$FRAG_PROVIDERS"
  seed_routing
  # IPv6-only server (SERVER_IP is IPv6): listen on "::" and use the system resolver with AAAA
  # (the IPv4 public DNS is unreachable there). Mirrors panel assemble_config() / DNS_IPV6_ONLY.
  local v6=0
  [[ ${SERVER_IP:-} == *:* ]] && v6=1
  awk -v c="$FRAG_CONTROLLER" -v pv="$FRAG_PROVIDERS" -v p="$FRAG_PROXIES" \
      -v rp="$FRAG_RULE_PROVIDERS" -v pg="$FRAG_PROXY_GROUPS" -v ru="$FRAG_RULES" \
      -v r="$FRAG_REALITY" -v e="$FRAG_EXTRA" \
      -v cp="$FRAG_CLUSTER_PROXIES" -v cl="$FRAG_CLUSTER_LISTENERS" -v v6="$v6" '
    function v6fix(s) {
      if (v6 == 1) {
        gsub(/listen: 0\.0\.0\.0/, "listen: \"::\"", s)
        gsub(/"listen": "0\.0\.0\.0"/, "\"listen\": \"::\"", s)
        gsub(/external-controller-tls: "0\.0\.0\.0:/, "external-controller-tls: \"[::]:", s)
      }
      return s
    }
    skipdns { if ($0 == "" || $0 ~ /^[[:space:]]/) next; skipdns = 0 }
    v6 == 1 && /^dns:$/ {
      print "dns:"
      print "  enable: true"
      print "  # 纯 IPv6 服务器：用本机系统 DNS 并解析 AAAA（服务商提供 DNS64 时也能访问只有 IPv4 的网站）"
      print "  ipv6: true"
      print "  enhanced-mode: redir-host"
      print "  respect-rules: false"
      print "  cache-algorithm: arc"
      print "  nameserver:"
      print "    - system"
      print ""
      skipdns = 1
      next
    }
    /^@@CONTROLLER@@$/ { while ((getline l < c) > 0) print v6fix(l); next }
    /^@@PROXY_PROVIDERS@@$/ {
      has = 0
      while ((getline l < pv) > 0) {
        if (l ~ /^[[:space:]]*$/) continue
        if (!has) { print "proxy-providers:"; has = 1 }
        print l
      }
      next
    }
    /^@@PROXIES@@$/    {
      has = 0
      while ((getline l < p) > 0) {
        if (l ~ /^[[:space:]]*$/) continue
        if (!has) { print "proxies:"; has = 1 }
        print l
      }
      while ((getline l < cp) > 0) {
        if (l ~ /^[[:space:]]*$/) continue
        if (!has) { print "proxies:"; has = 1 }
        print l
      }
      if (!has) print "proxies: []"
      next
    }
    /^@@RULE_PROVIDERS@@$/ { while ((getline l < rp) > 0) print l; next }
    /^@@PROXY_GROUPS@@$/   { while ((getline l < pg) > 0) print l; next }
    /^@@RULES@@$/          { while ((getline l < ru) > 0) print l; next }
    /^@@LISTENERS@@$/  {
      buf = ""
      while ((getline l < r) > 0) buf = buf v6fix(l) "\n"
      while ((getline l < e) > 0) buf = buf v6fix(l) "\n"
      while ((getline l < cl) > 0) buf = buf v6fix(l) "\n"
      if (buf ~ /[^[:space:]]/) { print "listeners:"; printf "%s", buf }
      else print "listeners: []"
      next
    }
    { print }' "$LIB_DIR/resources/server.yaml.tpl" > "$CONF.new"
  chmod 640 "$CONF.new"; chown root:mihomo "$CONF.new"
  mv -f "$CONF.new" "$CONF"
}

render_server() {
  log "写入服务端配置"
  render_controller
  local listeners="" name port uuid priv pub sid sni dec enc
  while IFS=$'\t' read -r name port uuid priv pub sid sni dec enc; do
    [[ -n $name ]] || continue
    listeners+="  - name: $name
    type: vless
    udp: true
    port: $port
    listen: 0.0.0.0
    users:
      - username: user
        uuid: $uuid
        flow: xtls-rprx-vision
"
    [[ -n ${dec:-} ]] && listeners+="    decryption: $dec
"
    listeners+="    reality-config:
      dest: $sni:443
      private-key: $priv
      short-id:
        - \"$sid\"
      server-names:
        - $sni
"
  done < "$STATE"
  printf '%s' "$listeners" > "$FRAG_REALITY"
  [[ -f $FRAG_EXTRA ]] || : > "$FRAG_EXTRA"
  [[ -f $FRAG_PROXIES ]] || : > "$FRAG_PROXIES"
  [[ -f $FRAG_PROVIDERS ]] || : > "$FRAG_PROVIDERS"
  seed_routing
  chmod 640 "$FRAG_REALITY" "$FRAG_EXTRA" "$FRAG_PROXIES" "$FRAG_PROVIDERS" "$FRAG_RULE_PROVIDERS" "$FRAG_PROXY_GROUPS" "$FRAG_RULES"
  chown root:mihomo "$FRAG_REALITY" "$FRAG_EXTRA" "$FRAG_PROXIES" "$FRAG_PROVIDERS" "$FRAG_RULE_PROVIDERS" "$FRAG_PROXY_GROUPS" "$FRAG_RULES" "$STATE"
  assemble_config
  validate_conf || die "生成的服务端配置未通过校验（mihomo -t）"
}

proxy_line() { # name port uuid pub sid sni [enc]
  local enc_part=""
  [[ -n ${7:-} ]] && enc_part=$(printf ',"encryption":"%s"' "$7")
  printf '{"name":"%s","type":"vless","server":"%s","port":%s,"uuid":"%s","tls":true,"flow":"xtls-rprx-vision","client-fingerprint":"safari"%s,"reality-opts":{"public-key":"%s","short-id":"%s"},"network":"tcp","udp":true,"servername":"%s"}' \
    "$1" "$SERVER_IP" "$2" "$3" "$enc_part" "$4" "$5" "$6"
}

render_client() {
  log "生成客户端配置"
  local proxies="" names="" name port uuid priv pub sid sni dec enc line cname p_arg n_arg
  while IFS=$'\t' read -r name port uuid priv pub sid sni dec enc; do
    [[ -n $name ]] || continue
    line=$(proxy_line "$name" "$port" "$uuid" "$pub" "$sid" "$sni" "${enc:-}")
    proxies+="  - $line"$'\n'
    names+="      - \"$name\""$'\n'
  done < "$STATE"
  if [[ -f $CS_ETC/inbounds.json ]]; then
    while IFS=$'\t' read -r line cname; do
      [[ -n $line ]] || continue
      proxies+="  - $line"$'\n'
      names+="      - $cname"$'\n'
    done < <(jq -r '.[] | (.name // .client.name) as $n | "\(.client | del(.["skip-cert-verify"]) | .name = $n | tojson)\t\($n | tojson)"' "$CS_ETC/inbounds.json" 2>/dev/null || true)
  fi
  install -d -m 700 "$CLIENT_DIR"
  p_arg="${proxies%$'\n'}"; [[ -n $p_arg ]] || p_arg="  []"
  n_arg="${names%$'\n'}";   [[ -n $n_arg ]] || n_arg='      - "DIRECT"'
  P="$p_arg" N="$n_arg" V="$CS_VERSION" awk \
    '/^@@PROXIES@@$/{print ENVIRON["P"]; next} /^@@PROXY_NAMES@@$/{print ENVIRON["N"]; next} {gsub(/@@VERSION@@/, ENVIRON["V"]); gsub(/\/dns-query#[^"'\''[:space:]]*/, "/dns-query"); print}' \
    "$LIB_DIR/resources/client.yaml.tpl" > "$CLIENT_DIR/mihomo-client.yaml"
  chmod 600 "$CLIENT_DIR/mihomo-client.yaml"
  { echo "proxies:"; printf '%s' "${proxies:-  []$'\n'}"; } > "$CLIENT_DIR/proxies.yaml"
  chmod 600 "$CLIENT_DIR/proxies.yaml"
}

open_firewall() { # 本机启用了 ufw 或 firewalld 时自动放行所需端口（云服务商安全组仍需自行放行）
  local p ports=()
  if [[ $MODE == auto-cert ]]; then
    [[ ${CERT_MODE:-port} == port ]] && ports+=(80/tcp)
    [[ $PANEL_PORT == 80 && ${CERT_MODE:-port} == port ]] || ports+=("$PANEL_PORT/tcp")
    ports+=("$CONTROLLER_PORT/tcp")
  fi
  while IFS=$'\t' read -r _ p _; do [[ -n $p ]] && ports+=("$p/tcp" "$p/udp"); done < "$STATE"
  if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q '^Status: active'; then
    local st; st=$(ufw status 2>/dev/null || true)
    for p in "${ports[@]}"; do
      grep -qE "^${p}[[:space:]]+ALLOW" <<<"$st" && continue   # 用户自己早已放行的规则
      ufw allow "$p" >/dev/null 2>&1 || true
    done
    info "检测到 ufw 已启用，已放行：${ports[*]}"
  elif command -v firewall-cmd >/dev/null 2>&1 && firewall-cmd --state >/dev/null 2>&1; then
    for p in "${ports[@]}"; do
      firewall-cmd --permanent --query-port="$p" >/dev/null 2>&1 && continue
      firewall-cmd --permanent --add-port="$p" >/dev/null 2>&1 || true
    done
    firewall-cmd --reload >/dev/null 2>&1 || true
    info "检测到 firewalld 已启用，已放行：${ports[*]}"
  fi
  return 0
}

setup_service() {
  log "配置 systemd 服务"
  install -m 644 "$LIB_DIR/scripts/init/mihomo.service" "$UNIT"
  systemctl daemon-reload
  systemctl enable mihomo >/dev/null 2>&1
  systemctl restart mihomo
}
