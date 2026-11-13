#!/usr/bin/env bash
# shop machine, one command: build what is missing (cluster, shop, RBAC, bad payment image),
# then 'demo.sh shop' opens the tunnels and writes the bundle for the backend machine.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
CLUSTER=oncall
CONTEXT=k3d-$CLUSTER
RELEASE=my-otel-demo
BUNDLE=$ROOT/data/demo/shop-bundle.tgz

cd "$ROOT"

# say every missing tool at once, not one per run
check_tools() {
  local missing=()
  for bin in docker k3d kubectl helm cloudflared uv curl openssl tar; do
    command -v "$bin" >/dev/null || missing+=("$bin")
  done
  if [ ${#missing[@]} -gt 0 ]; then
    echo "FAIL  missing tools: ${missing[*]}" >&2
    echo "      install them, then run this script again" >&2
    exit 1
  fi
  docker info >/dev/null 2>&1 || {
    echo "FAIL  docker not answering: start it, or add your user to the docker group" >&2
    exit 1
  }
  echo "OK    tools"
}

# wake a stopped cluster; setup_cluster.sh makes a missing one and the shop namespace
ensure_cluster() {
  if k3d cluster list "$CLUSTER" >/dev/null 2>&1; then
    kubectl --context "$CONTEXT" get --raw /readyz >/dev/null 2>&1 || k3d cluster start "$CLUSTER"
  else
    echo "MAKE  cluster $CLUSTER"
    FRESH=1
  fi
  scripts/setup_cluster.sh
}

# helm install takes up to 15 min the first time (image pulls)
ensure_shop() {
  if helm --kube-context "$CONTEXT" -n shop status "$RELEASE" >/dev/null 2>&1; then
    echo "OK    shop installed"
  else
    echo "MAKE  shop (first install pulls many images, can take 15 min)"
    scripts/install_shop.sh
  fi
}

# apply is idempotent; agent and reader tokens in the bundle need these accounts
ensure_guards() {
  kubectl --context "$CONTEXT" apply \
    -f k8s/rbac-reader.yaml -f k8s/rbac-agent.yaml \
    -f k8s/admission-policy.yaml -f k8s/admission-binding.yaml >/dev/null
  echo "OK    RBAC + admission policy"
}

# chaos 'bad_image' fault rolls payment to this image; new cluster has none
ensure_bad_payment() {
  if [ "${FRESH:-0}" = 1 ] || ! docker image inspect payment:v2-bad >/dev/null 2>&1; then
    echo "MAKE  payment:v2-bad image"
    scripts/build_bad_payment.sh
  else
    echo "OK    payment:v2-bad image"
  fi
}

up() {
  check_tools
  # first uv run downloads python + deps; demo.sh gives chaos only 60 s to start
  uv sync --locked
  ensure_cluster
  ensure_shop
  ensure_guards
  ensure_bad_payment
  scripts/demo.sh shop
  echo
  echo "SEND  $BUNDLE to the backend machine (scp, USB, file share; not chat)."
  echo "      it holds 72 h cluster tokens and the chaos token."
  echo "      keep this terminal's machine awake; stop with: scripts/shop_machine.sh down"
}

case "${1:-up}" in
  up) up ;;
  down) scripts/demo.sh down ;;
  status) scripts/demo.sh status ;;
  logs) scripts/demo.sh logs ;;
  *) echo "usage: $0 [up | down | status | logs]" >&2; exit 2 ;;
esac
