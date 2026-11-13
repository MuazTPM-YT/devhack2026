#!/usr/bin/env bash
# demo stack. up: all on one machine. shop: cluster + chaos + public tunnels on the shop machine.
# backend <bundle>: agent + UI on another machine, talking to the shop through those tunnels.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN="$ROOT/data/demo"   # data/ is gitignored
BUNDLE_DIR="$RUN/bundle"
REMOTE_DIR="$RUN/remote"
CONTEXT=k3d-oncall
# start order: gateway first (brain and notifier talk to it), observer last (it posts incidents to brain)
AGENT=(gateway:7003 brain:7002 notifier:7005 observer:7001)
UI_PORT=3000
TUNNELS=(tun-api tun-prometheus tun-shop tun-chaos)

cd "$ROOT"
mkdir -p "$RUN"

# any HTTP answer, even 404, means the port is serving
serving() { curl -s -o /dev/null --max-time 2 "http://127.0.0.1:$1/"; }

alive() { [ -f "$RUN/$1.pid" ] && kill -0 "$(cat "$RUN/$1.pid")" 2>/dev/null; }

# own session per process, so down can kill uv and its uvicorn child together
launch() {
  local name=$1 port=$2; shift 2
  if serving "$port"; then
    echo "SKIP  $name: port $port already serving"
    return
  fi
  setsid "$@" >"$RUN/$name.log" 2>&1 < /dev/null &
  echo $! >"$RUN/$name.pid"
  for _ in $(seq 1 60); do
    if serving "$port"; then echo "UP    $name :$port"; return; fi
    if ! alive "$name"; then
      echo "FAIL  $name died on start; last lines of $RUN/$name.log:" >&2
      tail -n 15 "$RUN/$name.log" >&2
      exit 1
    fi
    sleep 1
  done
  echo "FAIL  $name not serving on :$port after 60 s; see $RUN/$name.log" >&2
  exit 1
}

# quick tunnel (trycloudflare, no account); its random URL lands in $RUN/<name>.url
tunnel() {
  local name=$1 origin=$2; shift 2
  if alive "$name" && [ -s "$RUN/$name.url" ]; then
    echo "SKIP  $name: already open at $(cat "$RUN/$name.url")"
    return
  fi
  rm -f "$RUN/$name.url"
  setsid cloudflared tunnel --no-autoupdate --url "$origin" "$@" >"$RUN/$name.log" 2>&1 < /dev/null &
  echo $! >"$RUN/$name.pid"
  local url=""
  for _ in $(seq 1 60); do
    url=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$RUN/$name.log" | head -n 1 || true)
    [ -n "$url" ] && break
    alive "$name" || break
    sleep 1
  done
  if [ -z "$url" ]; then
    echo "FAIL  $name got no trycloudflare URL; see $RUN/$name.log" >&2
    exit 1
  fi
  # new hostnames take a few seconds to resolve; 000 = no answer yet, 530 = edge has no route yet
  local code=000
  for _ in $(seq 1 60); do
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$url/" || true)
    case "$code" in 000|530|502|1033) sleep 2 ;; *) break ;; esac
  done
  case "$code" in
    000|530|502|1033) echo "FAIL  $name at $url still answers $code after 2 min" >&2; exit 1 ;;
  esac
  echo "$url" >"$RUN/$name.url"
  echo "UP    $name $url -> $origin"
}

ensure_cluster() {
  if ! kubectl --context "$CONTEXT" get ns shop >/dev/null 2>&1; then
    echo "cluster $CONTEXT not answering, starting it"
    k3d cluster start oncall
  fi
  echo "cluster $CONTEXT ok"
}

# observer reads metrics through 9090; 8080 is the shop itself (and Jaeger under /jaeger/ui)
port_forwards() {
  launch pf-prometheus 9090 kubectl --context "$CONTEXT" -n shop port-forward svc/prometheus 9090:9090
  launch pf-shop 8080 kubectl --context "$CONTEXT" -n shop port-forward svc/frontend-proxy 8080:8080
}

# env_files are loaded in order, later wins; the UI reads CHAOS_URL, GATEWAY_URL, OBSERVER_URL
start_agent() {
  local env_args=() source_cmd="set -a"
  for file in "$@"; do
    env_args+=(--env-file "$file")
    source_cmd+="; . '$file'"
  done
  for entry in "${AGENT[@]}"; do
    name=${entry%%:*} port=${entry##*:}
    launch "$name" "$port" uv run --locked "${env_args[@]}" \
      uvicorn "$name.main:app" --host 127.0.0.1 --port "$port"
  done
  [ -d ui/node_modules ] || (cd ui && npm ci)
  launch ui "$UI_PORT" bash -c "$source_cmd; set +a; cd ui && exec npm run dev"
}

need_env() { [ -f .env ] || { echo "FAIL  .env missing (copy .env.example and fill it)" >&2; exit 1; }; }

up() {
  need_env
  ensure_cluster
  port_forwards
  launch chaos 7004 uv run --locked --env-file .env uvicorn chaos.main:app --host 127.0.0.1 --port 7004
  start_agent .env
  echo
  echo "UI      http://localhost:$UI_PORT"
  echo "shop    http://localhost:8080"
  echo "logs    scripts/demo.sh logs   (files in $RUN)"
  echo "stop    scripts/demo.sh down"
}

# least-privilege SA tokens (72 h) in kubeconfigs that point at the API tunnel; admin creds stay here
mint_kubeconfig() {
  local file=$1 sa=$2 server=$3 token
  token=$(kubectl --context "$CONTEXT" -n shop create token "$sa" --duration=72h)
  cat >"$file" <<EOF
apiVersion: v1
kind: Config
clusters:
- name: oncall
  cluster: {server: "$server"}
users:
- name: $sa
  user: {token: "$token"}
contexts:
- name: $sa
  context: {cluster: oncall, user: $sa, namespace: shop}
current-context: $sa
EOF
}

shop() {
  command -v cloudflared >/dev/null || { echo "FAIL  cloudflared not installed" >&2; exit 1; }
  ensure_cluster
  port_forwards
  # no .env: chaos must not chase a local OBSERVER_URL that does not exist on this machine
  launch chaos 7004 uv run --locked uvicorn chaos.main:app --host 127.0.0.1 --port 7004
  local api
  api=$(kubectl config view --raw --minify --context "$CONTEXT" -o jsonpath='{.clusters[0].cluster.server}')
  api=${api/0.0.0.0/127.0.0.1}
  # cloudflare's edge holds the public cert; the hop to the k3d API is local, so skip its self-signed cert
  tunnel tun-api "$api" --no-tls-verify
  tunnel tun-prometheus http://127.0.0.1:9090
  tunnel tun-shop http://127.0.0.1:8080
  tunnel tun-chaos http://127.0.0.1:7004
  local shop_url
  shop_url=$(cat "$RUN/tun-shop.url")
  rm -rf "$BUNDLE_DIR"
  (umask 077 && mkdir -p "$BUNDLE_DIR"
   mint_kubeconfig "$BUNDLE_DIR/agent.kubeconfig" oncall-agent "$(cat "$RUN/tun-api.url")"
   mint_kubeconfig "$BUNDLE_DIR/reader.kubeconfig" oncall-reader "$(cat "$RUN/tun-api.url")"
   cat >"$BUNDLE_DIR/remote.env" <<EOF
PROMETHEUS_URL=$(cat "$RUN/tun-prometheus.url")
JAEGER_URL=$shop_url/jaeger/ui
NEXT_PUBLIC_JAEGER_URL=$shop_url/jaeger/ui
CHAOS_URL=$(cat "$RUN/tun-chaos.url")
EOF
   tar -C "$BUNDLE_DIR" -czf "$RUN/shop-bundle.tgz" .)
  echo
  echo "shop     $shop_url"
  echo "chaos    $(cat "$RUN/tun-chaos.url")"
  echo "bundle   $RUN/shop-bundle.tgz"
  echo "         holds 72 h cluster tokens: copy it straight to the backend machine"
  echo "         (scp or USB), never paste it in chat. Tunnel URLs change on every shop start."
  echo "next     on the backend machine: scripts/demo.sh backend <path to shop-bundle.tgz>"
}

backend() {
  local bundle=${1:-}
  [ -f "$bundle" ] || { echo "usage: $0 backend <shop-bundle.tgz from 'demo.sh shop'>" >&2; exit 2; }
  need_env
  rm -rf "$REMOTE_DIR"
  (umask 077 && mkdir -p "$REMOTE_DIR" && tar -C "$REMOTE_DIR" -xzf "$bundle")
  printf 'AGENT_KUBECONFIG=%s\nREADER_KUBECONFIG=%s\n' \
    "$REMOTE_DIR/agent.kubeconfig" "$REMOTE_DIR/reader.kubeconfig" >>"$REMOTE_DIR/remote.env"
  if ! kubectl --kubeconfig "$REMOTE_DIR/reader.kubeconfig" get deploy >/dev/null 2>&1; then
    echo "FAIL  cannot reach the shop cluster through the bundle's API tunnel; is 'demo.sh shop' still up?" >&2
    exit 1
  fi
  echo "shop cluster reachable through tunnel"
  start_agent .env "$REMOTE_DIR/remote.env"
  echo
  echo "UI      http://localhost:$UI_PORT"
  echo "logs    scripts/demo.sh logs   (files in $RUN)"
  echo "stop    scripts/demo.sh down"
}

down() {
  for name in ui observer chaos notifier brain gateway "${TUNNELS[@]}" pf-shop pf-prometheus; do
    if alive "$name"; then
      kill -- "-$(cat "$RUN/$name.pid")" 2>/dev/null || true
      echo "DOWN  $name"
    fi
    rm -f "$RUN/$name.pid" "$RUN/$name.url"
  done
}

status() {
  for entry in pf-prometheus:9090 pf-shop:8080 chaos:7004 "${AGENT[@]}" "ui:$UI_PORT"; do
    name=${entry%%:*} port=${entry##*:}
    if serving "$port"; then echo "UP    $name :$port"; else echo "DOWN  $name :$port"; fi
  done
  for name in "${TUNNELS[@]}"; do
    if alive "$name"; then echo "UP    $name $(cat "$RUN/$name.url" 2>/dev/null)"; fi
  done
}

case "${1:-}" in
  up) up ;;
  shop) shop ;;
  backend) backend "${2:-}" ;;
  down) down ;;
  status) status ;;
  logs) tail -n 20 -F "$RUN"/*.log ;;
  *) echo "usage: $0 up | shop | backend <bundle.tgz> | down | status | logs" >&2; exit 2 ;;
esac
