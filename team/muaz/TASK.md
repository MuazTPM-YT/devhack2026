# Muaz [M]: tasks

Read `team/muaz/ARCHITECTURE.md` first. Tick a box only with proof (test
output, command result). Record progress in `team/muaz/STATE.md`. Anything
another teammate needs goes in `team/SHARED_CONTEXT.md`.

Priority: P0 = minimum deliverable, P1 = to win, P2 = stretch.

## Phase 0: foundations

- [x] P0 Agree shared schemas with T; `schemas/` imports cleanly (§5.2, C1) — proof: T replied `agreed` to Q11 in SHARED_CONTEXT; `uv run pytest` imports `schemas.models` (197 passed). C1 row in the contract table still says `proposed`.
- [x] P0 VERIFY list with A: metric names, flag storage, Jaeger API paths; write results to `team/SHARED_CONTEXT.md` and `config/` (§3.3) — proof (A, live 2026-11-13): span metrics confirmed; flags now read from ConfigMap `flagd-config` (~60 s reload, no restart); Jaeger `/api/dependencies` HTTP 200 `{"data":[{"parent":..,"child":..,"callCount":..}]}` (shape my graph code expects), `/api/traces` with the error tag HTTP 200.
- [x] P0 `config/policy.yaml`, `config/queries.yaml` (§4.2, §4.3) — proof: files on main; loaded by `tests/test_observer.py` and `tests/test_brain.py` (pass).
- [x] P0 `k8s/rbac-reader.yaml`, `k8s/rbac-agent.yaml`, `k8s/admission-policy.yaml`, `k8s/admission-binding.yaml` applied (§6.5) — proof (A, live): `kubectl apply` created all 10 RBAC/VAP objects on cluster `oncall`.
- [x] P0 `scripts/make_kubeconfigs.sh` writes `agent.kubeconfig`, `reader.kubeconfig` (git-ignored) (§3.5) — proof: on the test cluster it wrote both with mode `-rw-------`; `git status` stayed clean (`*.kubeconfig` in `.gitignore`).
- [x] P0 Security acceptance table passes, every row (§6.5.5) — proof (A, live): `./scripts/security_check.sh` -> 19 PASS, `fails: 0`; denies came from `oncall-agent-fields` / `oncall-agent-scale` with our messages; executor row: smoke receipt #1 `rollback_deploy` executed with the agent identity.

## Phase 1: the spine, one failure end to end

- [x] P0 SQLite schema, WAL mode (§5.1) — proof: `schemas/db.py`; `tests/test_db.py` asserts `journal_mode` = `wal` (pass).
- [x] P0 Detector + baselines + severity + `GET /health/now` (§6.2.1, §6.2.2) — proof: `tests/test_detector.py`, `tests/test_observer.py` (pass, PR #11 merged). Fake Prometheus only; not run on the cluster yet.
- [x] P0 Kubernetes watch + journal with inverses, `GET /journal` (§6.2.3, §6.2.4) — proof: `tests/test_kube_watch.py`, `tests/test_journal.py`, `tests/test_observer.py` (pass, PR #11). Fake API objects only.
- [x] P0 Culprit from traces, fallback to deepest unhealthy service (§6.3.2) — proof: `tests/test_culprit.py`, `tests/test_brain.py` (pass). Jaeger response shape not verified live.
- [x] P0 Dependency graph from Jaeger, 60 s cache (§6.3.1) — proof: `tests/test_brain.py::test_graph_cache_and_downstream` (pass, merged in PR #14). Jaeger response shape not verified live.
- [x] P0 Evidence bundle with IDs on every item (§6.3.4) — proof: `tests/test_bundle.py` (pass, merged in PR #14).
- [x] P0 Rules: general rule only (§6.3.6) — proof: `tests/test_rules.py` (pass).
- [x] P0 Gateway: schema, policy, dry run + snapshot, freshness, executor for `rollback_deploy` (§6.4.2, §6.4.3, §6.4.5, §6.4.7) — proof: `tests/test_gateway.py` (12 pass) + `tests/test_freshness.py`, merged in PR #16. Fake API server only; not run on the cluster.
- [x] P0 Verifier: recovery + prediction + auto-undo (§6.4.9) — proof: `tests/test_verify_loop.py` (success, no-recovery undo, early abort pause/undo/resume, hands-off) + `tests/test_verifier.py`, merged in PR #17. Fake API server only.
- [x] P0 `test_rules.py`, `test_culprit.py` (§8.1) — proof: both in `tests/`, pass.

Exit: `scripts/smoke.sh` (A) passes: bad deploy detected, rolled back on "ask" via curl approve, verified, receipt written.

Plan audit 2026-11-13: failed generation test now hands off (checked on a real API server). Exit status: NOT MET yet. Live run 2 (A, 2026-11-13): rollback executed, then early abort undid it 5 s later (checkout lagged), and the undo got 422 and left payment paused. Fixed on branch `muaz/verify-fixes` (grace period, generation test, `finally` unpause, `undo_failed`; 3 tests in `tests/test_verify_loop.py`). Needs a smoke rerun. The run needs one manual `curl` approval.

## Phase 2: the other failures and the checks

- [x] P0 Flag tracking in the journal (§6.2.5) — proof: flagd reads ConfigMap `flagd-config` (A, live ~60 s reload); journal names the flipped flag (`flags[paymentFailure].defaultVariant: off -> 50%`) with a per-flag inverse; rules link it to the service via `flags:` in `config/services.yaml`. `tests/test_flags.py` (9 pass), branch `muaz/flag-revert`.
- [ ] P0 Executor: `revert_config`, `restart_service`, `scale`, `raise_limit`, `enable_degraded_mode` (§6.4.7) — partial: all but `enable_degraded_mode` done (`tests/test_tools.py`, `tests/test_flags.py`; flag revert on branch `muaz/flag-revert`). `enable_degraded_mode` stays refused: the shop has no feature-off flags (Muaz chose A).
- [x] P0 Rules: 3 special cases (resource, protected, unknown) (§6.3.6) — proof: `tests/test_rules.py` resource, protected and unknown cases (pass).
- [ ] P0 Claude call: forced tool, Pydantic check, one retry, 30 s timeout, token log, demo cache (§6.3.7) — now OpenCode Go via T's `DiagnosisService`: Pydantic check, retry, 30 s, token log, cache done (T's tests). Live run: both calls hit `deadline_exceeded` at 30 s (deepseek-v4.1-flash); rules still gave the right action. Timeout/model is T's call. Forced tool not done.
- [x] P0 Harm check (spec/data hashes), early abort with rollout pause (§6.4.9) — proof: `tests/test_verify_loop.py::test_early_abort_pauses_undoes_resumes`, `harm_check` in the success path (pass). Fake API server only.

Exit: scenarios 1 to 6 in §7 behave as specified.

Scenario 5 now pages with Approve; approved scale-back works on a real API server (test cluster, `muaz/plan-audit`). Exit status: NOT MET. Needs live runs. Scenario 3 (flag flipped) now built: `tests/test_flags.py::test_brain_flag_flip_proposes_flag_revert` + gateway flag revert tests. Scenario 5 (datastore down -> protected) fixed in code: `tests/test_brain.py::test_datastore_scaled_to_zero_moves_culprit_to_protected_dependency`. Live flag flip 2026-11-13 (A): culprit payment, `revert_config` executed, then early abort undid it; grace fix on `muaz/verify-fixes`, needs rerun.

## Phase 3: trust, humans, proof

- [x] P1 Trust gate + ledger + tiers (§6.4.6); depends on Q2, Q3 — proof: `tests/test_trust.py`; gate in checklist step 7 (auto when open, else ask); real credit + `POST /ledger/rehearsal` in `tests/test_verify_loop.py` (pass). Rehearsal runs not performed yet.
- [x] P1 Approvals: create, decide endpoint, expiry, re-run steps 2 to 6 (§6.4.8) — proof: `tests/test_gateway.py::test_approval_rules`, `tests/test_phase3.py::test_expired_approvals_are_swept` (pass). Re-page lives in T's notifier.
- [x] P1 Hands-off rule (§6.4.2 step 2); depends on Q4 — proof: `tests/test_gateway.py::test_human_change_after_open_hands_off` (pass); Q4 agreed by A.
- [x] P1 Watchdog (§6.4.10) — proof: `tests/test_phase3.py` watchdog tests (undo, leaves ticking verifier, failed undo keeps blocking) pass, merged in PR #20.
- [x] P1 Blast radius + net-benefit check (§6.4.4) — proof: `tests/test_phase3.py` blast/forecast/net-benefit tests pass, merged in PR #20. Graph from Jaeger not verified live.

Exit: scenarios 7 to 9 and 11 to 12 pass.

Exit status: code paths covered by tests (fakes); NOT MET live.

## Phase 4: wide outages and measurement

- [x] P1 Major-incident mode + shared-cause analysis (§6.3.3), checklist major rules (§6.4.2); `/chaos/shared-outage` endpoint per Q6 — proof: `tests/test_major.py` 7 pass (incl. kafka outage -> major, culprit kafka, protected), merged in PR #22. `/chaos/shared-outage` is A's (Q6). Shared node skipped (one-node k3d).
- [x] P1 Property-based tests, report "N cases, 0 violations" (§8.2) — proof: `tests/test_invariants.py` prints `2000 generated cases, 0 violations`; mutated checks produce violations. Stdlib random, not Hypothesis.

Exit: scenario 10 passes.

Exit status: covered by `tests/test_major.py` (fakes); NOT MET live, needs A's `/chaos/shared-outage`.

## Phase 6: stretch (only if Phase 4 exit is met early)

- [ ] P2 One retry after clean undo (§6.4.11)
- [ ] P2 Calibration chart of Claude's confidence
- [ ] P2 Second LLM through MCP

## Never cut

RBAC + admission policy, the verifier's auto-undo.
