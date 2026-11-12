# Muaz [M]: state

Update this file at the end of every session. Newest facts on top of each
section. Only my own work here; cross-team facts go in
`team/SHARED_CONTEXT.md`.

**Last updated:** 2026-11-13
**Current phase:** 0 (files written, real-cluster checks blocked)
**Branch:** `muaz/phase0-security` (not pushed)

## Done (with proof)

- Replies to Q1 to Q10 and schema proposal Q11 (for T) in
  `team/SHARED_CONTEXT.md`. Proof: commit `99b0ab5`.
- Local pre-test only (throwaway k3d cluster `oncall-test`, k3s v1.35.5,
  dummy `payment` Deployment on `payment:v1` with 2 replicas, `valkey-cart`,
  `flagd-config`). This is **not** the §6.5.5 table; the real shop was not
  used. Results of `./scripts/security_check.sh`: 15 PASS, 4 FAIL.
  - PASS: can-i delete deployment/payment `no`, get secrets `no`, patch
    deployment/valkey-cart `no`, create pods `no`, patch deployment/payment
    `yes`; reader patch deployment/payment `no`.
  - PASS (dry run and real): approved image patch `patched (no change)`;
    serviceAccountName `denied request: agent may not change the service account`;
    `evil/image:latest` `denied request: image must come from an approved source`;
    restartedAt `patched`; server dry run left resourceVersion `476` unchanged.
  - FAIL (dry run and real): both scale rows. `cannot get resource
    "deployments/scale"`. Cause: `kubectl patch --subresource=scale` does a GET
    first, and the agent Role grants only `patch` on `deployments/scale`.
    The admission rule itself was not reached.
  - Extra dry-run spot checks: env patch `patched`, memory limit patch
    `patched`, add volume `DENIED: agent may not change volumes`,
    hostNetwork `DENIED`, replicas 4 via deployment `DENIED: replicas must
    stay between 1 and 3`, patch flagd-config `patched`.
  - Both policies report empty `status.typeChecking` (no CEL type warnings).
- `scripts/make_kubeconfigs.sh` and `scripts/security_check.sh`. Proof:
  `bash -n` OK; on the test cluster it wrote `agent.kubeconfig` and
  `reader.kubeconfig` with mode `-rw-------`; both are git-ignored
  (`git status` clean after). Commit `e8dd9cf`.
- `k8s/rbac-reader.yaml`, `k8s/rbac-agent.yaml`, `k8s/admission-policy.yaml`
  (2 policies), `k8s/admission-binding.yaml` (2 bindings). Proof: YAML parses;
  `kubectl apply --dry-run=client -f k8s/` OK; applied to the test cluster.
  Commit `3445006`.
- `config/policy.yaml`, `config/queries.yaml`. Proof: YAML parses. Commit
  `43177b1`. Approver ids moved to env `ONCALL_APPROVER_IDS`; `p95_ms_all` added.
- `.gitignore`, `.env.example` (T's files, created with OK). Commit `f0158f4`.

## In progress

- nothing

## Blocked / waiting on

- **§6.5.5 security acceptance table: BLOCKED.** A's cluster is not up. No
  row is passed. Run `kubectl apply -f k8s/`, `./scripts/make_kubeconfigs.sh`,
  `./scripts/security_check.sh` on it.
- Row "real `rollback_deploy` through the executor": needs the gateway
  executor (Phase 1).
- Scale rows: need a decision from Muaz: add `get` on `deployments/scale`
  to the agent Role (read-only, same data the agent already reads), or test
  the scale subresource without kubectl. Touches permissions, so not changed.
- VERIFY values from A: Deployment names, `flagd-config` name, image prefixes.
- Schemas (C1): waiting on T's reply to Q11.
- Q replies need the other owners to answer `agreed`.

## Next

1. Fix the scale rows after Muaz decides; re-run the pre-test.
2. Run the §6.5.5 table on A's cluster; paste the output here.
3. Fill my VERIFY rows (Jaeger API paths, MCP transport, JSON Patch content
   type, Claude model id + price).
4. Phase 1: SQLite schema, detector, journal.

## Notes for my next session

- The test cluster `oncall-test` was deleted at session end. Recreate with
  `k3d cluster create oncall-test --servers 1 --k3s-arg "--disable=traefik@server:*" --kubeconfig-update-default=false --kubeconfig-switch-context=false`
  so the default kube context stays `kind-muaz-foss`.
- Admission CEL pattern: `has(new) == has(old) && (!has(new) || new == old)`.
