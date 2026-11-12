# Twaha [T]: tasks

Read `team/twaha/ARCHITECTURE.md` first. Tick a box only with proof.
Record progress in `team/twaha/STATE.md`. Append cross-team facts to
`team/SHARED_CONTEXT.md`.

Priority: P0 = minimum deliverable, P1 = to win, P2 = stretch.
Implementation is on main through merged PRs #8 and #12. Checked components
have offline test evidence; live acceptance stays open below.

## Phase 0: foundations

- [x] P0 `.gitignore` covers secrets, local data, kubeconfigs, and dependencies (§2)
- [x] P0 `.env.example`: OpenCode Go, Discord, shared `ONCALL_APPROVER_IDS`, rehearsal disabled by default
- [x] P0 Repo guidance and README type-check commands include observer and chaos packages
- [x] P0 Python 3.12 manifest and `uv.lock`, minor version constraints, approved dependencies (Q9, Q10)
- [x] P0 Shared schemas accepted with M Q11; imports and schema tests pass (§5.2, C1)
- [x] P0 Event names from §5.3 and typed payloads used by implemented consumers (`tests/test_schemas.py`)
- [ ] P0 Finish remaining producer payload contracts and obtain all owner agreements (C2)
- [x] P0 OpenCode Go adapter behind `InferenceProvider`; async `DiagnosisService` is the sole inference path (`tests/test_inference.py`)
- [x] P0 Live OpenCode Go call: `deepseek-v4.1-flash`, valid diagnosis, 16.6 s, 2209 tokens (2026-11-13)

## Phase 1: the spine

- [x] P0 Event router, in-process publish, durable audit, SSE replay and disconnect handling (`gateway/events.py`; pytest suite, C3, Q8)
- [x] P0 Mount event and receipt routes in M's gateway runtime; prove cross-process delivery (live 2026-11-13: curl publish -> SSE ids 1-3, Last-Event-ID replay, audit verified)
- [x] P0 Audit hash chain and first-broken-sequence CLI (`tests/test_audit.py`, §6.7.2)
- [x] P0 Redacted receipt display store and five-line incident cards (`gateway/receipts.py`; pytest suite, §6.7.1)

## Phase 2: checks

- [x] P0 Redaction and hash-only injection quarantine; diagnosis returns quarantine events (`tests/test_redact.py`, `tests/test_inference.py`, C8)
- [x] P0 Brain forwards diagnosis result events (`brain/main.py`, `tests/test_brain.py`, merged PR #14)
- [ ] P0 Prove brain-to-gateway event delivery with running services
- [x] P0 Trust, verifier, redaction, audit, and SQLite integration tests pass (§8.1)
- [x] P0 Policy gate unit tests (`tests/test_policy.py`, 19 cases); checklist integration in M's `tests/test_gateway.py`
- [ ] P0 Runtime authorization against live cluster (RBAC/admission; needs cluster)

## Phase 3: humans and proof

- [x] P1 Discord component: FYI/wake/tickets, persistent buttons, approver/expiry checks, re-page, cursor recovery (`tests/test_notifier.py`, §6.6)
- [x] P1 Live Discord via real gateway SSE: FYI, tickets, wake + role mention, approval buttons, expiry closes buttons, re-page, restart cursor recovery (2026-11-13)
- [ ] P1 Human approver clicks Approve/Reject on a real cluster approval
- [x] P1 Benchmark harness: incremental results, failed attempts, resume, SSE reconnect/deduplication, partial timings (`tests/test_bench.py`, §9.1)
- [x] P1 Read-only trust report separates statistical confidence from authorization (`tests/test_trust_report.py`)
- [ ] P1 Start overnight runs: 30 each for `(recent_change, rollback_deploy, payment)` and `(recent_change, revert_config, checkout)` (§9.1)
- [x] P1 Red-team component suite: 12 cases; JSON report generation (`tests/redteam/`, `bench/redteam.py`)
- [ ] P1 Complete live RBAC/admission, freshness, budget, and authorization checks; publish the acceptance table (§8.3)

## Phase 4: measurement

- [ ] P1 Accuracy runs: 10 per scenario 1 to 5 (§9.1)
- [ ] P1 Manual baseline: teammate using only kubectl and UIs, 3 runs per scenario in `bench/manual_baseline.md` (§9.2)
- [x] P1 Report code: timings, accuracy, wakes, verification, tokens, manual comparison (`bench/report.py`, `tests/test_bench.py`)
- [x] P1 Export JSON, CSV, Markdown tables, and SVG timings; validate inputs and expose sample counts (`tests/test_bench_export.py`, §9.3)
- [x] P1 Require current observer metrics for the entire pre-injection healthy window (`tests/test_bench_recovery.py`)
- [ ] P1 Collect live trials and publish their measured tables and charts (§9.3)
- [ ] P1 Card verification study with 5 people

## Phase 5: freeze

- [x] README documents component setup, route mounting, approval and rehearsal contracts
- [ ] Final README: measured results, limits, credits, and complete runnable system (§13)
- [ ] Deck (§11.3) and backup video

## Never cut

The audit log and measured benchmark time-to-recovery numbers.

## Evidence and next gate (2026-11-13)

PR #12 merged as `c6091f7`. Its verified source had 160 passing tests,
Ruff passing, and mypy passing across 37 source files. The older 166-test
count included the retired synchronous provider tests.

Merged main through `1b980a0`, including observer #11, chaos #10, and brain #14.
Shared-note conflict kept both teams' entries. Current branch adds benchmark
readiness checks and report exports (PR #15). Full suite: 215 passed; Ruff passed;
mypy passed across 53 source files. Two upstream deprecation warnings remain.
A reports the cluster and shop running on A's machine. Live integration still
needs service access, M's gateway runtime/action handoff, and approval/rehearsal handlers.

No live provider/Discord checks, incident measurements, overnight trust
credits, manual trials, or card study are claimed complete.
