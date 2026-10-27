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

install_core() {
  log "安装最新稳定版 Mihomo 内核"
  install -d -m 775 "$CS_ROOT"
  local a rel tag url tmp
  a=$(arch)
  rel=$(curl -fsSL --retry 3 "$REPO_API") || die "无法获取 Mihomo 版本信息（请确认服务器可以访问 GitHub）"
  tag=$(jq -r .tag_name <<<"$rel")
  # stable "latest" endpoint already excludes prereleases; plain build name: mihomo-linux-<arch>-<tag>.gz
  url=$(jq -r --arg n "mihomo-linux-${a}-${tag}.gz" '.assets[] | select(.name==$n) | .browser_download_url' <<<"$rel")
  [[ -n "$url" ]] || die "版本 $tag 中没有找到 mihomo-linux-${a}-${tag}.gz"
  tmp=$(mktemp)
  curl -fsSL --retry 3 -o "$tmp" "$url" || die "下载失败：$url"
  gzip -dc "$tmp" > "$BIN.new" && rm -f "$tmp"
  chmod 755 "$BIN.new"
  "$BIN.new" -v >/dev/null || die "下载的 Mihomo 无法运行"
  mv "$BIN.new" "$BIN"
  ln -sfn "$BIN" /usr/local/bin/mihomo
  info "已安装 $tag -> $BIN"
}

detect_ip() {
  [[ -n "$SERVER_IP" ]] && return
  for u in https://api.ipify.org https://ifconfig.me https://ipv4.icanhazip.com; do
    SERVER_IP=$(curl -fsS -4 --max-time 5 "$u" 2>/dev/null | tr -d '[:space:]') && [[ -n "$SERVER_IP" ]] && return
  done
  if has_tty; then
    while [[ ! $SERVER_IP =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; do
      SERVER_IP=$(ask '无法自动探测公网 IP，请手动输入本机公网 IPv4：' '')
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
  install -d -m 775 -o root -g mihomo "$CONF_DIR"
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

validate_conf() {
  local d rc=0 f
  d=$(mktemp -d)
  mkdir -p "$d/ui"   # 避免 mihomo -t 校验时临时下载 external-ui
  [[ -d $CONF_DIR/certs ]] && ln -s "$CONF_DIR/certs" "$d/certs"
  [[ -d $CONF_DIR/ruleset ]] && ln -s "$CONF_DIR/ruleset" "$d/ruleset"
  for f in "$CONF_DIR"/*.mmdb "$CONF_DIR"/*.dat; do
    [[ -f $f ]] && ln -s "$f" "$d/$(basename "$f")"
  done
  SAFE_PATHS="$CONF_DIR" "$BIN" -t -d "$d" -f "$CONF" >/dev/null || rc=$?
  if ((rc == 0)) && [[ -f $d/country.mmdb && ! -L $d/country.mmdb && -d $CONF_DIR ]]; then
    cp -a "$d/country.mmdb" "$CONF_DIR/country.mmdb" 2>/dev/null || true
    chown mihomo:mihomo "$CONF_DIR/country.mmdb" 2>/dev/null || true
  fi
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

# config.yaml = custom_config.yaml (if active) OR template with @@CONTROLLER@@, @@PROXY_PROVIDERS@@, @@PROXIES@@, and @@LISTENERS@@.
# Mirrors assemble_config() in panel/panel.py.
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
  awk -v c="$FRAG_CONTROLLER" -v pv="$FRAG_PROVIDERS" -v p="$FRAG_PROXIES" -v r="$FRAG_REALITY" -v e="$FRAG_EXTRA" '
    /^@@CONTROLLER@@$/ { while ((getline l < c) > 0) print l; next }
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
      if (!has) print "proxies: []"
      next
    }
    /^@@LISTENERS@@$/  { while ((getline l < r) > 0) print l; while ((getline l < e) > 0) print l; next }
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
        - $sid
      server-names:
        - $sni
"
  done < "$STATE"
  printf '%s' "$listeners" > "$FRAG_REALITY"
  [[ -f $FRAG_EXTRA ]] || : > "$FRAG_EXTRA"
  [[ -f $FRAG_PROXIES ]] || : > "$FRAG_PROXIES"
  [[ -f $FRAG_PROVIDERS ]] || : > "$FRAG_PROVIDERS"
  chmod 640 "$FRAG_REALITY" "$FRAG_EXTRA" "$FRAG_PROXIES" "$FRAG_PROVIDERS"
  chown root:mihomo "$FRAG_REALITY" "$FRAG_EXTRA" "$FRAG_PROXIES" "$FRAG_PROVIDERS" "$STATE"
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
  P="$p_arg" N="$n_arg" awk \
    '/^@@PROXIES@@$/{print ENVIRON["P"]; next} /^@@PROXY_NAMES@@$/{print ENVIRON["N"]; next} {gsub(/\/dns-query#[^"'\''[:space:]]*/, "/dns-query"); print}' \
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
    for p in "${ports[@]}"; do ufw allow "$p" >/dev/null 2>&1 || true; done
    info "检测到 ufw 已启用，已放行：${ports[*]}"
  elif command -v firewall-cmd >/dev/null 2>&1 && firewall-cmd --state >/dev/null 2>&1; then
    for p in "${ports[@]}"; do firewall-cmd --permanent --add-port="$p" >/dev/null 2>&1 || true; done
    firewall-cmd --reload >/dev/null 2>&1 || true
    info "检测到 firewalld 已启用，已放行：${ports[*]}"
  fi
}

setup_service() {
  log "配置 systemd 服务"
  install -m 644 "$LIB_DIR/scripts/init/mihomo.service" "$UNIT"
  systemctl daemon-reload
  systemctl enable mihomo >/dev/null 2>&1
  systemctl restart mihomo
}
