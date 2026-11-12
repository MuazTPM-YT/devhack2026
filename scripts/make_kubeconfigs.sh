#!/usr/bin/env bash
# mint 72 h SA tokens, write agent.kubeconfig + reader.kubeconfig (git-ignored). run with admin kubeconfig.
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077

server=$(kubectl config view --raw --minify -o jsonpath='{.clusters[0].cluster.server}')
ca=$(kubectl config view --raw --minify -o jsonpath='{.clusters[0].cluster.certificate-authority-data}')
[ -n "$server" ] || { echo "make_kubeconfigs: no cluster server in current kubeconfig" >&2; exit 1; }
[ -n "$ca" ] || { echo "make_kubeconfigs: no certificate-authority-data in current kubeconfig" >&2; exit 1; }

for pair in agent:oncall-agent reader:oncall-reader; do
  name=${pair%%:*}
  sa=${pair#*:}
  token=$(kubectl -n shop create token "$sa" --duration=72h)
  cat > "$name.kubeconfig" <<EOF
apiVersion: v1
kind: Config
clusters:
- name: oncall
  cluster: {server: "$server", certificate-authority-data: "$ca"}
users:
- name: $sa
  user: {token: "$token"}
contexts:
- name: $sa
  context: {cluster: oncall, user: $sa, namespace: shop}
current-context: $sa
EOF
  echo "wrote $name.kubeconfig for $sa (72h)"
done
