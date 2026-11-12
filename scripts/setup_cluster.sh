#!/usr/bin/env bash
# k3d cluster "oncall" + namespace "shop" (plan §3.2). Safe to re-run.
set -euo pipefail

CLUSTER=oncall
# pinned so every rebuild gets the same k8s; must stay >= 1.30 for ValidatingAdmissionPolicy
K3S_IMAGE=rancher/k3s:v1.31.5-k3s1

for bin in docker k3d kubectl; do
  command -v "$bin" >/dev/null || { echo "missing: $bin" >&2; exit 1; }
done

if k3d cluster list "$CLUSTER" >/dev/null 2>&1; then
  echo "cluster $CLUSTER exists, skipping create"
else
  k3d cluster create "$CLUSTER" --servers 1 --image "$K3S_IMAGE" \
    --k3s-arg "--disable=traefik@server:*" --wait
fi

kubectl config use-context "k3d-$CLUSTER"
kubectl version
# no grep -q: early exit SIGPIPEs kubectl and pipefail reports failure
kubectl api-resources | grep -i validatingadmissionpolic >/dev/null \
  || { echo "ValidatingAdmissionPolicy API missing" >&2; exit 1; }

kubectl create namespace shop --dry-run=client -o yaml | kubectl apply -f -
echo "cluster $CLUSTER ready"
