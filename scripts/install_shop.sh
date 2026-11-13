#!/usr/bin/env bash
# install the OpenTelemetry demo shop into ns "shop" (plan §3.3). Safe to re-run.
set -euo pipefail

cd "$(dirname "$0")/.."

RELEASE=my-otel-demo
NS=shop
# pinned: released 2026-10-21, app version 3.1.0
CHART_VERSION=0.42.6
# services the agent may act on (config/services.yaml, actable: true)
ACTABLE=(payment checkout cart frontend recommendation ad email)

kubectl config use-context k3d-oncall

helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts >/dev/null 2>&1 || true
helm repo update open-telemetry

# helm 4 applies server-side; chaos-panel and the agent own fields they patched (flagd-config data),
# so a re-install would stop on a conflict. A (re)install makes the chart the source of truth again.
helm upgrade --install "$RELEASE" open-telemetry/opentelemetry-demo \
  --version "$CHART_VERSION" -n "$NS" -f k8s/values.yaml --wait --timeout 15m --force-conflicts

# chart has no strategy key; zero-downtime rollouts on actable services
for d in "${ACTABLE[@]}"; do
  kubectl -n "$NS" patch deployment "$d" --type merge \
    -p '{"spec":{"strategy":{"type":"RollingUpdate","rollingUpdate":{"maxUnavailable":0,"maxSurge":1}}}}'
done

for d in "${ACTABLE[@]}"; do
  kubectl -n "$NS" rollout status deployment "$d" --timeout 5m
done

kubectl -n "$NS" get deploy
# fresh healthy shop: chaos panel re-snapshots it on next start
rm -f data/healthy_snapshot.json
echo "shop installed"
