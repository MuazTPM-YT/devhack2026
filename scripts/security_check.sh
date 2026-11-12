#!/usr/bin/env bash
# run the §6.5.5 security table as the agent; prints each command, its real output, PASS/FAIL.
# needs agent.kubeconfig + reader.kubeconfig (scripts/make_kubeconfigs.sh). real patches touch payment
# (no-op image patch + restartedAt). IMAGE_OK overrides the approved image (default: payment's current one).
set -uo pipefail
cd "$(dirname "$0")/.."

A=(kubectl --kubeconfig agent.kubeconfig -n shop)
R=(kubectl --kubeconfig reader.kubeconfig -n shop)
fails=0

# run cmd, PASS when output matches the expected regex
check() {
  local name=$1 want=$2 out
  shift 2
  out=$("$@" 2>&1)
  if grep -qE "$want" <<<"$out"; then echo "PASS | $name"; else echo "FAIL | $name"; fails=$((fails + 1)); fi
  echo "  \$ $*"
  sed 's/^/  > /' <<<"$out"
}

check "agent can-i delete deployment/payment: no" '^no$' "${A[@]}" auth can-i delete deployment/payment
check "agent can-i get secrets: no" '^no$' "${A[@]}" auth can-i get secrets
check "agent can-i patch deployment/valkey-cart: no" '^no$' "${A[@]}" auth can-i patch deployment/valkey-cart
check "agent can-i create pods: no" '^no$' "${A[@]}" auth can-i create pods
check "agent can-i patch deployment/payment: yes" '^yes$' "${A[@]}" auth can-i patch deployment/payment
check "reader can-i patch deployment/payment: no" '^no$' "${R[@]}" auth can-i patch deployment/payment

img=${IMAGE_OK:-$("${A[@]}" get deploy payment -o jsonpath='{.spec.template.spec.containers[0].image}')}
replicas=$("${A[@]}" get deploy payment -o jsonpath='{.spec.replicas}')
p_image_ok="[{\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/0/image\",\"value\":\"$img\"}]"
p_image_evil='[{"op":"replace","path":"/spec/template/spec/containers/0/image","value":"evil/image:latest"}]'
p_sa='{"spec":{"template":{"spec":{"serviceAccountName":"oncall-agent"}}}}'
p_restart="{\"spec\":{\"template\":{\"metadata\":{\"annotations\":{\"kubectl.kubernetes.io/restartedAt\":\"$(date -u +%FT%TZ)\"}}}}}"

# same patch rows twice: server dry run first (must save nothing), then for real
for mode in --dry-run=server ""; do
  tag=${mode:-real}
  rv_before=$("${A[@]}" get deploy payment -o jsonpath='{.metadata.resourceVersion}')
  check "[$tag] image -> approved ($img): allowed" 'patched' "${A[@]}" patch deploy payment $mode --type=json -p "$p_image_ok"
  check "[$tag] serviceAccountName: denied by policy" 'agent may not change the service account' "${A[@]}" patch deploy payment $mode --type=merge -p "$p_sa"
  check "[$tag] image -> evil/image:latest: denied" 'image must come from an approved source' "${A[@]}" patch deploy payment $mode --type=json -p "$p_image_evil"
  check "[$tag] restartedAt annotation: allowed" 'patched' "${A[@]}" patch deploy payment $mode --type=merge -p "$p_restart"
  check "[$tag] scale to 5: denied" 'replicas must stay between 1 and 3' "${A[@]}" patch deploy payment $mode --subresource=scale --type=merge -p '{"spec":{"replicas":5}}'
  check "[$tag] scale to current ($replicas): allowed" 'patched' "${A[@]}" patch deploy payment $mode --subresource=scale --type=merge -p "{\"spec\":{\"replicas\":$replicas}}"
  if [ "$tag" != real ]; then
    rv_after=$("${A[@]}" get deploy payment -o jsonpath='{.metadata.resourceVersion}')
    check "[$tag] nothing saved (resourceVersion $rv_before)" '^same$' bash -c "[ '$rv_before' = '$rv_after' ] && echo same || echo 'changed to $rv_after'"
  fi
done

echo "MANUAL | real rollback_deploy through the executor after a bad deploy: needs gateway executor (Phase 1)"
echo "fails: $fails"
[ "$fails" -eq 0 ]
