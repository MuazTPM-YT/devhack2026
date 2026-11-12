# Muaz [M]: tasks

Read `team/muaz/ARCHITECTURE.md` first. Tick a box only with proof (test
output, command result). Record progress in `team/muaz/STATE.md`. Anything
another teammate needs goes in `team/SHARED_CONTEXT.md`.

Priority: P0 = minimum deliverable, P1 = to win, P2 = stretch.

## Phase 0: foundations

- [ ] P0 Agree shared schemas with T; `schemas/` imports cleanly (§5.2, C1)
- [ ] P0 VERIFY list with A: metric names, flag storage, Jaeger API paths; write results to `team/SHARED_CONTEXT.md` and `config/` (§3.3)
- [ ] P0 `config/policy.yaml`, `config/queries.yaml` (§4.2, §4.3)
- [ ] P0 `k8s/rbac-reader.yaml`, `k8s/rbac-agent.yaml`, `k8s/admission-policy.yaml`, `k8s/admission-binding.yaml` applied (§6.5)
- [ ] P0 `scripts/make_kubeconfigs.sh` writes `agent.kubeconfig`, `reader.kubeconfig` (git-ignored) (§3.5)
- [ ] P0 Security acceptance table passes, every row (§6.5.5)

## Phase 1: the spine, one failure end to end

- [ ] P0 SQLite schema, WAL mode (§5.1)
- [ ] P0 Detector + baselines + severity + `GET /health/now` (§6.2.1, §6.2.2)
- [ ] P0 Kubernetes watch + journal with inverses, `GET /journal` (§6.2.3, §6.2.4)
- [ ] P0 Culprit from traces, fallback to deepest unhealthy service (§6.3.2)
- [ ] P0 Dependency graph from Jaeger, 60 s cache (§6.3.1)
- [ ] P0 Evidence bundle with IDs on every item (§6.3.4)
- [ ] P0 Rules: general rule only (§6.3.6)
- [ ] P0 Gateway: schema, policy, dry run + snapshot, freshness, executor for `rollback_deploy` (§6.4.2, §6.4.3, §6.4.5, §6.4.7)
- [ ] P0 Verifier: recovery + prediction + auto-undo (§6.4.9)
- [ ] P0 `test_rules.py`, `test_culprit.py` (§8.1)

Exit: `scripts/smoke.sh` (A) passes: bad deploy detected, rolled back on "ask" via curl approve, verified, receipt written.

## Phase 2: the other failures and the checks

- [ ] P0 Flag tracking in the journal (§6.2.5)
- [ ] P0 Executor: `revert_config`, `restart_service`, `scale`, `raise_limit`, `enable_degraded_mode` (§6.4.7)
- [ ] P0 Rules: 3 special cases (resource, protected, unknown) (§6.3.6)
- [ ] P0 Claude call: forced tool, Pydantic check, one retry, 30 s timeout, token log, demo cache (§6.3.7)
- [ ] P0 Harm check (spec/data hashes), early abort with rollout pause (§6.4.9)

Exit: scenarios 1 to 6 in §7 behave as specified.

## Phase 3: trust, humans, proof

- [ ] P1 Trust gate + ledger + tiers (§6.4.6); depends on Q2, Q3
- [ ] P1 Approvals: create, decide endpoint, expiry, re-run steps 2 to 6 (§6.4.8)
- [ ] P1 Hands-off rule (§6.4.2 step 2); depends on Q4
- [ ] P1 Watchdog (§6.4.10)
- [ ] P1 Blast radius + net-benefit check (§6.4.4)

Exit: scenarios 7 to 9 and 11 to 12 pass.

## Phase 4: wide outages and measurement

- [ ] P1 Major-incident mode + shared-cause analysis (§6.3.3), checklist major rules (§6.4.2); `/chaos/shared-outage` endpoint per Q6
- [ ] P1 Property-based tests, report "N cases, 0 violations" (§8.2)

Exit: scenario 10 passes.

## Phase 6: stretch (only if Phase 4 exit is met early)

- [ ] P2 One retry after clean undo (§6.4.11)
- [ ] P2 Calibration chart of Claude's confidence
- [ ] P2 Second LLM through MCP

## Never cut

RBAC + admission policy, the verifier's auto-undo.
