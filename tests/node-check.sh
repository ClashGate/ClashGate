#!/usr/bin/env bash
# Pre-release node check: import a ClashGate subscription into a local Mihomo client and test every node.
#
#   CG_SUB_URL='https://<domain>:<panel-port>/sub/<token>/mihomo.yaml' tests/node-check.sh
#   tests/node-check.sh - <<<"$SUB_URL"            # URL on stdin
#   tests/node-check.sh --file mihomo.yaml          # an already downloaded subscription
#
# The subscription URL is a secret: it is never printed, logged or passed on a command line
# (curl reads it from stdin). Only the client's `proxies:` are used; the local core gets its own
# minimal config (no TUN, no DNS hijack, listeners on 127.0.0.1 only), so the box's network is untouched.
# For every node: the controller delay API (GET /proxies/<name>/delay) and a real request through the
# node (curl via the local mixed port). Exit 0 = all nodes pass, 1 = a node failed, 2 = setup error.
#
# Env: MIHOMO_BIN (core binary; default: download the pinned official release into the temp dir),
#      NODE_CHECK_URL (default https://www.gstatic.com/generate_204), NODE_CHECK_TIMEOUT (ms, default 5000).
set -euo pipefail
MIHOMO_VERSION=v1.19.34   # keep in step with tests/run.sh
TEST_URL=${NODE_CHECK_URL:-https://www.gstatic.com/generate_204}
TIMEOUT_MS=${NODE_CHECK_TIMEOUT:-5000}
GROUP=CG-NODE-CHECK

die() { echo "node-check: $*" >&2; exit 2; }
for c in curl python3 gunzip; do command -v "$c" >/dev/null || die "missing $c"; done

SUB_FILE="" SUB_URL=${CG_SUB_URL:-}
case ${1:-} in
  --file) [[ -f ${2:-} ]] || die "--file needs a readable file"; SUB_FILE=$2 ;;
  -) IFS= read -r SUB_URL || true ;;
  "") ;;
  -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
  *) SUB_URL=$1 ;;
esac
[[ -n $SUB_FILE || -n $SUB_URL ]] || die "no subscription: set CG_SUB_URL, pass '-' (stdin) or --file"

WORK=$(mktemp -d "${TMPDIR:-/tmp}/cg-node-check.XXXXXX")
chmod 700 "$WORK"
CORE_PID=""
cleanup() { [[ -n $CORE_PID ]] && kill "$CORE_PID" 2>/dev/null; wait 2>/dev/null; [[ -n ${NODE_CHECK_DEBUG:-} ]] && tail -n 20 "$WORK/core.log" >&2; rm -rf "$WORK"; }
trap cleanup EXIT

# 1. Subscription
if [[ -n $SUB_URL ]]; then
  [[ $SUB_URL =~ ^https?://([^/:]+) ]] || die "subscription URL must start with http(s)://"
  echo "subscription: ${BASH_REMATCH[1]} (path hidden)"
  # URL goes through curl's config on stdin, so it never shows up in the process list.
  printf 'url = "%s"\n' "${SUB_URL//\"/\\\"}" \
    | curl -fsS --max-time 30 -A "clashgate-node-check" -o "$WORK/sub.yaml" -K - \
    || die "subscription download failed"
else
  cp "$SUB_FILE" "$WORK/sub.yaml"
  echo "subscription: local file"
fi

# 2. Core binary (official MetaCubeX release)
if [[ -z ${MIHOMO_BIN:-} ]]; then
  case $(uname -m) in x86_64) a=amd64 ;; aarch64|arm64) a=arm64 ;; *) die "unsupported arch $(uname -m)" ;; esac
  MIHOMO_BIN=$WORK/core
  curl -fsSL --max-time 120 "https://github.com/MetaCubeX/mihomo/releases/download/${MIHOMO_VERSION}/mihomo-linux-${a}-${MIHOMO_VERSION}.gz" \
    | gunzip > "$MIHOMO_BIN" || die "core download failed"
  chmod +x "$MIHOMO_BIN"
fi
echo "core: $("$MIHOMO_BIN" -v | head -1 | cut -c1-60)"

# 3. Local client config: the subscription's proxies + one select group over all of them.
read -r MIXED_PORT CTL_PORT SECRET < <(python3 - <<'PY'
import secrets, socket
ports = []
for _ in range(2):
    s = socket.socket(); s.bind(("127.0.0.1", 0)); ports.append(s.getsockname()[1]); s.close()
print(ports[0], ports[1], secrets.token_hex(16))
PY
)
WORK=$WORK MIXED_PORT=$MIXED_PORT CTL_PORT=$CTL_PORT SECRET=$SECRET GROUP=$GROUP python3 - <<'PY' || exit 2
import os, re, sys
src = open(os.path.join(os.environ["WORK"], "sub.yaml"), encoding="utf-8").read().splitlines()
block, inside = [], False
for line in src:
    if re.match(r"^proxies:\s*(#.*)?$", line):
        inside = True; block.append("proxies:"); continue
    if inside:
        if re.match(r"^[A-Za-z_\"']", line):   # next top-level key
            break
        block.append(line)
if len(block) < 2 or not any(l.strip().startswith("-") for l in block):
    sys.exit("node-check: no block-style `proxies:` list found in the subscription")
e = os.environ
cfg = f"""mixed-port: {e['MIXED_PORT']}
bind-address: 127.0.0.1
allow-lan: false
mode: rule
log-level: warning
ipv6: true
external-controller: 127.0.0.1:{e['CTL_PORT']}
secret: "{e['SECRET']}"
profile:
  store-selected: false
  store-fake-ip: false
""" + "\n".join(block) + f"""
proxy-groups:
  - name: {e['GROUP']}
    type: select
    include-all-proxies: true
rules:
  - MATCH,{e['GROUP']}
"""
open(os.path.join(e["WORK"], "config.yaml"), "w", encoding="utf-8").write(cfg)
PY

"$MIHOMO_BIN" -d "$WORK" -f "$WORK/config.yaml" -t >"$WORK/t.log" 2>&1 \
  || { grep -iE "error|fatal" "$WORK/t.log" | tail -5 >&2; die "core rejected the generated config"; }
"$MIHOMO_BIN" -d "$WORK" -f "$WORK/config.yaml" >"$WORK/core.log" 2>&1 &
CORE_PID=$!

API=http://127.0.0.1:$CTL_PORT
api() { curl -fsS --max-time 30 -H "Authorization: Bearer $SECRET" "$@"; }
for _ in $(seq 50); do api "$API/version" >/dev/null 2>&1 && break; sleep 0.2; done
api "$API/version" >/dev/null 2>&1 || { tail -5 "$WORK/core.log" >&2; die "core did not start"; }

# 4. Test each node
mapfile -t NODES < <(api "$API/proxies" | python3 -c '
import json, sys
skip = {"Direct", "Reject", "RejectDrop", "Pass", "PassRule", "Compatible", "Selector", "URLTest", "Fallback", "LoadBalance", "Relay"}
for n, p in json.load(sys.stdin)["proxies"].items():
    if p.get("type") not in skip:
        print(str(p.get("type")) + "\t" + n)')
(( ${#NODES[@]} )) || die "the subscription has no nodes"

enc() { python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$1"; }
qurl=$(enc "$TEST_URL")
echo "test URL: $TEST_URL   nodes: ${#NODES[@]}"
printf '%-28s %-12s %-12s %s\n' NODE TYPE DELAY "REQUEST (via node)"
fail=0
for row in "${NODES[@]}"; do
  type=${row%%$'\t'*} name=${row#*$'\t'}
  n=$(enc "$name")
  d=$(api "$API/proxies/$n/delay?url=$qurl&timeout=$TIMEOUT_MS" 2>/dev/null \
      | python3 -c 'import json,sys; print(json.load(sys.stdin).get("delay",""))' 2>/dev/null || true)
  if [[ $d =~ ^[0-9]+$ ]] && (( d > 0 )); then delay="${d} ms"; ok_d=1; else delay="FAIL"; ok_d=0; fi
  body=$(python3 -c 'import json,sys; print(json.dumps({"name": sys.argv[1]}))' "$name")
  api -X PUT -H 'Content-Type: application/json' -d "$body" "$API/proxies/$GROUP" >/dev/null 2>&1 || true
  r=$(curl -sS -o /dev/null -w '%{http_code} %{time_total}' --max-time $(( TIMEOUT_MS / 1000 + 5 )) \
      --proxy "socks5h://127.0.0.1:$MIXED_PORT" "$TEST_URL" 2>/dev/null || true)
  code=${r%% *}
  if [[ $code =~ ^(2|3)[0-9][0-9]$ ]]; then
    req="HTTP $code $(awk -v t="${r#* }" 'BEGIN { printf "%d ms", t * 1000 }')"; ok_r=1
  else req="FAIL (${code:-000})"; ok_r=0; fi
  if (( ok_d && ok_r )); then mark=PASS; else mark=FAIL; fail=1; fi
  printf '%-28s %-12s %-12s %-24s %s\n' "${name:0:28}" "$type" "$delay" "$req" "$mark"
done
echo
if (( fail )); then echo "node-check: FAILED (see FAIL rows)"; exit 1; fi
echo "node-check: all ${#NODES[@]} nodes passed"
