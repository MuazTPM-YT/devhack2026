#!/usr/bin/env bash
# demo stack in one go: cluster check, 5 services, UI. up | down | status | logs
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN="$ROOT/data/demo"   # data/ is gitignored
CONTEXT=k3d-oncall
# start order: gateway first (brain and notifier talk to it), observer last (it posts incidents to brain)
SERVICES=(gateway:7003 brain:7002 notifier:7005 chaos:7004 observer:7001)
UI_PORT=3000

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

up() {
  [ -f .env ] || { echo "FAIL  .env missing (copy .env.example and fill it)" >&2; exit 1; }
  if ! kubectl --context "$CONTEXT" get ns shop >/dev/null 2>&1; then
    echo "cluster $CONTEXT not answering, starting it"
    k3d cluster start oncall
  fi
  echo "cluster $CONTEXT ok"
  # observer reads metrics through 9090; 8080 is the shop itself, for the audience
  launch pf-prometheus 9090 kubectl --context "$CONTEXT" -n shop port-forward svc/prometheus 9090:9090
  launch pf-shop 8080 kubectl --context "$CONTEXT" -n shop port-forward svc/frontend-proxy 8080:8080
  for entry in "${SERVICES[@]}"; do
    name=${entry%%:*} port=${entry##*:}
    launch "$name" "$port" uv run --locked --env-file .env \
      uvicorn "$name.main:app" --host 127.0.0.1 --port "$port"
  done
  [ -d ui/node_modules ] || (cd ui && npm ci)
  # the UI reads CHAOS_URL, GATEWAY_URL, OBSERVER_URL from the environment
  launch ui "$UI_PORT" bash -c 'set -a; . ./.env; set +a; cd ui && exec npm run dev'
  echo
  echo "UI      http://localhost:$UI_PORT"
  echo "shop    http://localhost:8080"
  echo "logs    scripts/demo.sh logs   (files in $RUN)"
  echo "stop    scripts/demo.sh down"
}

down() {
  for name in ui observer chaos notifier brain gateway pf-shop pf-prometheus; do
    if alive "$name"; then
      kill -- "-$(cat "$RUN/$name.pid")" 2>/dev/null || true
      echo "DOWN  $name"
    fi
    rm -f "$RUN/$name.pid"
  done
}

status() {
  for entry in pf-prometheus:9090 pf-shop:8080 "${SERVICES[@]}" "ui:$UI_PORT"; do
    name=${entry%%:*} port=${entry##*:}
    if serving "$port"; then echo "UP    $name :$port"; else echo "DOWN  $name :$port"; fi
  done
}

case "${1:-}" in
  up) up ;;
  down) down ;;
  status) status ;;
  logs) tail -n 20 -F "$RUN"/*.log ;;
  *) echo "usage: $0 up | down | status | logs" >&2; exit 2 ;;
esac
