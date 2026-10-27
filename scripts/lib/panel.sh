# shellcheck shell=bash
# clashgate 管理面板与订阅链接

panel_host() { printf '%s' "${DOMAIN#\*.}"; }

panel_port() {
  local p=${PANEL_PORT:-}
  [[ -n $p ]] || p=$(panel_cfg_get port)
  [[ -n $p ]] || p=$(rand_port)
  PANEL_PORT=$p
  printf '%s' "$p"
}

controller_port() {
  local p=${CONTROLLER_PORT:-}
  [[ -n $p ]] || p=$(rand_port)
  CONTROLLER_PORT=$p
  printf '%s' "$p"
}

panel_url() {
  local h p
  h=$(panel_host); p=$(panel_port)
  if [[ $p == 443 ]]; then printf 'https://%s' "$h"; else printf 'https://%s:%s' "$h" "$p"; fi
}

urlencode() {
  local s=${1:-} i c hex out=""
  local LC_ALL=C
  for ((i = 0; i < ${#s}; i++)); do
    c=${s:i:1}
    case "$c" in
      [a-zA-Z0-9.~_-]) out+="$c" ;;
      *) printf -v hex '%%%02X' "'$c"; out+="$hex" ;;
    esac
  done
  printf '%s' "$out"
}

zashboard_url() {
  local h p
  h=$(panel_host); p=$(controller_port)
  if [[ -n ${MIHOMO_SECRET:-} ]]; then
    printf 'https://%s:%s/ui/#/setup?hostname=%s&port=%s&secret=%s&https=true' \
      "$h" "$p" "$(urlencode "$h")" "$p" "$(urlencode "$MIHOMO_SECRET")"
  else
    printf 'https://%s:%s/ui/' "$h" "$p"
  fi
}

setup_panel() {
  log "配置管理面板"
  install -d -m 775 "$CS_ETC"
  [[ -f $CS_ETC/inbounds.json ]]  || { echo '[]' > "$CS_ETC/inbounds.json";  chmod 600 "$CS_ETC/inbounds.json"; }
  [[ -f $CS_ETC/proxies.json ]]   || { echo '[]' > "$CS_ETC/proxies.json";   chmod 600 "$CS_ETC/proxies.json"; }
  [[ -f $CS_ETC/providers.json ]] || { echo '{}' > "$CS_ETC/providers.json"; chmod 600 "$CS_ETC/providers.json"; }
  set_panel_password
  install -m 644 "$LIB_DIR/scripts/init/clashgate.service" /etc/systemd/system/clashgate.service
  systemctl daemon-reload
  systemctl enable clashgate >/dev/null 2>&1
  systemctl restart clashgate
}

panel_https_ok() { # 本机访问面板 HTTPS（跳过证书校验，只验证 HTTPS 通路）
  local h p
  h=$(panel_host); p=$(panel_port)
  curl -fsSk --max-time 10 --resolve "$h:$p:127.0.0.1" "https://$h:$p$1" 2>/dev/null
}

panel_cfg_get() { jq -r --arg k "$1" '.[$k] // empty' "$PANEL_CFG" 2>/dev/null || true; }

new_sub_token() { openssl rand -hex 24; }

sub_url() { printf '%s/sub/%s/mihomo.yaml' "$(panel_url)" "$SUB_TOKEN"; }

write_panel_cfg() { # PANEL_HASH + SUB_TOKEN -> panel.json (0600, root only)
  local p; p=$(panel_port)
  # 面板自己做 HTTPS（与 Mihomo 共用 /etc/clashgate/certs 证书），直接监听 0.0.0.0:$PANEL_PORT，不需要反代和 443
  jq -n --arg h "$PANEL_HASH" --arg t "$SUB_TOKEN" --argjson p "$p" \
    --arg c "$CONF_DIR/certs/fullchain.pem" --arg k "$CONF_DIR/certs/privkey.pem" \
    '{username:"admin", password_hash:$h, listen:"0.0.0.0", port:$p, tls_cert:$c, tls_key:$k, sub_token:$t}' > "$PANEL_CFG.new"
  chmod 600 "$PANEL_CFG.new"; mv -f "$PANEL_CFG.new" "$PANEL_CFG"
}

set_panel_password() { # new random password; keeps an existing subscription token
  PANEL_PASS=$(openssl rand -base64 32 | tr -dc 'A-Za-z0-9' | head -c 20)
  PANEL_HASH=$(printf '%s\n' "$PANEL_PASS" | python3 "$LIB_DIR/panel/panel.py" hash-password)
  [[ -n $SUB_TOKEN ]] || SUB_TOKEN=$(panel_cfg_get sub_token)
  [[ -n $SUB_TOKEN ]] || SUB_TOKEN=$(new_sub_token)
  write_panel_cfg
}
