# Muaz [M]: tasks

Read `team/muaz/ARCHITECTURE.md` first. Tick a box only with proof (test
output, command result). Record progress in `team/muaz/STATE.md`. Anything
another teammate needs goes in `team/SHARED_CONTEXT.md`.

Priority: P0 = minimum deliverable, P1 = to win, P2 = stretch.

## Phase 0: foundations

- [x] P0 Agree shared schemas with T; `schemas/` imports cleanly (§5.2, C1) — proof: T replied `agreed` to Q11 in SHARED_CONTEXT; `uv run pytest` imports `schemas.models` (197 passed). C1 row in the contract table still says `proposed`.
- [ ] P0 VERIFY list with A: metric names, flag storage, Jaeger API paths; write results to `team/SHARED_CONTEXT.md` and `config/` (§3.3) — partial: metric names and flag storage checked live by A; Jaeger paths from docs only, live curl pending (A).
- [x] P0 `config/policy.yaml`, `config/queries.yaml` (§4.2, §4.3) — proof: files on main; loaded by `tests/test_observer.py` and `tests/test_brain.py` (pass).
- [ ] P0 `k8s/rbac-reader.yaml`, `k8s/rbac-agent.yaml`, `k8s/admission-policy.yaml`, `k8s/admission-binding.yaml` applied (§6.5) — partial: written and applied on a throwaway k3d cluster only; not applied on A's cluster yet.
- [x] P0 `scripts/make_kubeconfigs.sh` writes `agent.kubeconfig`, `reader.kubeconfig` (git-ignored) (§3.5) — proof: on the test cluster it wrote both with mode `-rw-------`; `git status` stayed clean (`*.kubeconfig` in `.gitignore`).
- [ ] P0 Security acceptance table passes, every row (§6.5.5) — BLOCKED: needs `./scripts/security_check.sh` on A's cluster. Local pre-test only: `fails: 0`, 19 PASS. Executor row needs the gateway.

## Phase 1: the spine, one failure end to end

- [x] P0 SQLite schema, WAL mode (§5.1) — proof: `schemas/db.py`; `tests/test_db.py` asserts `journal_mode` = `wal` (pass).
- [x] P0 Detector + baselines + severity + `GET /health/now` (§6.2.1, §6.2.2) — proof: `tests/test_detector.py`, `tests/test_observer.py` (pass, PR #11 merged). Fake Prometheus only; not run on the cluster yet.
- [x] P0 Kubernetes watch + journal with inverses, `GET /journal` (§6.2.3, §6.2.4) — proof: `tests/test_kube_watch.py`, `tests/test_journal.py`, `tests/test_observer.py` (pass, PR #11). Fake API objects only.
- [x] P0 Culprit from traces, fallback to deepest unhealthy service (§6.3.2) — proof: `tests/test_culprit.py`, `tests/test_brain.py` (pass). Jaeger response shape not verified live.
- [x] P0 Dependency graph from Jaeger, 60 s cache (§6.3.1) — proof: `tests/test_brain.py::test_graph_cache_and_downstream` (pass, branch `muaz/brain`). Jaeger response shape not verified live.
- [x] P0 Evidence bundle with IDs on every item (§6.3.4) — proof: `tests/test_bundle.py` (pass, branch `muaz/brain`).
- [x] P0 Rules: general rule only (§6.3.6) — proof: `tests/test_rules.py` (pass).
- [x] P0 Gateway: schema, policy, dry run + snapshot, freshness, executor for `rollback_deploy` (§6.4.2, §6.4.3, §6.4.5, §6.4.7) — proof: `tests/test_gateway.py` (12 pass) + `tests/test_freshness.py`, branch `muaz/gateway`. Fake API server only; not run on the cluster.
- [x] P0 Verifier: recovery + prediction + auto-undo (§6.4.9) — proof: `tests/test_verify_loop.py` (success, no-recovery undo, early abort pause/undo/resume, hands-off) + `tests/test_verifier.py`, branch `muaz/verify-loop`. Fake API server only.
- [x] P0 `test_rules.py`, `test_culprit.py` (§8.1) — proof: both in `tests/`, pass.

Exit: `scripts/smoke.sh` (A) passes: bad deploy detected, rolled back on "ask" via curl approve, verified, receipt written.

## Phase 2: the other failures and the checks

- [ ] P0 Flag tracking in the journal (§6.2.5)
- [ ] P0 Executor: `revert_config`, `restart_service`, `scale`, `raise_limit`, `enable_degraded_mode` (§6.4.7) — partial: `revert_config` (env), `restart_service`, `scale`, `raise_limit` done (`tests/test_tools.py`, branch `muaz/phase2-tools`); flag revert and `enable_degraded_mode` wait on the flag plan.
- [x] P0 Rules: 3 special cases (resource, protected, unknown) (§6.3.6) — proof: `tests/test_rules.py` resource, protected and unknown cases (pass).
- [ ] P0 Claude call: forced tool, Pydantic check, one retry, 30 s timeout, token log, demo cache (§6.3.7) — now OpenCode Go via T's `DiagnosisService`: Pydantic check, retry, 30 s, token log, cache done (T's tests). Forced tool not done; no real call made yet.
- [x] P0 Harm check (spec/data hashes), early abort with rollout pause (§6.4.9) — proof: `tests/test_verify_loop.py::test_early_abort_pauses_undoes_resumes`, `harm_check` in the success path (pass). Fake API server only.

Exit: scenarios 1 to 6 in §7 behave as specified.

## Phase 3: trust, humans, proof

- [x] P1 Trust gate + ledger + tiers (§6.4.6); depends on Q2, Q3 — proof: `tests/test_trust.py`; gate in checklist step 7 (auto when open, else ask); real credit + `POST /ledger/rehearsal` in `tests/test_verify_loop.py` (pass). Rehearsal runs not performed yet.
- [ ] P1 Approvals: create, decide endpoint, expiry, re-run steps 2 to 6 (§6.4.8) — partial: create, decide endpoint, expiry check, rerun steps 2 to 6 done (`tests/test_gateway.py::test_approval_rules`); expiry sweeper and re-page not built.
- [x] P1 Hands-off rule (§6.4.2 step 2); depends on Q4 — proof: `tests/test_gateway.py::test_human_change_after_open_hands_off` (pass); Q4 agreed by A.
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
