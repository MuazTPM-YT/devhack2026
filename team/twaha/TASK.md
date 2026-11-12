# Twaha [T]: tasks

Read `team/twaha/ARCHITECTURE.md` first. Tick a box only with proof (test
output, command result). Record progress in `team/twaha/STATE.md`.
Anything another teammate needs goes in `team/SHARED_CONTEXT.md`.

Priority: P0 = minimum deliverable, P1 = to win, P2 = stretch.

## Phase 0: foundations

- [x] P0 `.gitignore` (`.env`, `data/`, `*.kubeconfig`, `node_modules/`) in the first code commit (§2)
- [x] P0 `.env.example`: OpenCode Go model/key, Discord settings, shared `ONCALL_APPROVER_IDS`, rehearsal disabled by default
- [x] P0 `AGENTS.md` with the same content as `CLAUDE.md`
- [ ] P0 Dependency manifest + lockfile, pinned `~=`, after the team agrees the list (Q9, Q10)
- [x] P0 Shared schemas: T accepted M Q11; `schemas/` imports cleanly (§5.2, C1)
- [ ] P0 `schemas/events.py`: the event types in §5.3 with payload fields (C2)

## Phase 1: the spine

- [ ] P0 Event publish + SSE endpoint in the gateway process (§1.3, C3, Q8)
- [x] P0 Audit log hash chain + `scripts/verify_audit.py` (§6.7.2)
- [x] P0 Receipt + incident card, text only (§6.7.1)

## Phase 2: checks

- [ ] P0 Redaction + injection quarantine, publishes `injection_quarantined` (§6.3.5, C8)
- [ ] P0 Unit tests: `test_trust.py` (10 -> 0.741, 30 -> 0.905, 59 -> 0.950, reset on failure), `test_policy.py`, `test_redact.py`, `test_audit.py` (§8.1)

## Phase 3: humans and proof

- [ ] P1 Discord bot: `#oncall-fyi`, `#oncall-wake` (re-page every `repage_seconds`), `#oncall-tickets`; approvals with buttons, expiry, approver check (§6.6)
- [x] P1 Benchmark harness; survives failed runs; writes `bench/results.jsonl` incrementally (§9.1); depends on Q2, Q3
- [ ] P1 **Start overnight trust runs**: 30 each for `(recent_change, rollback_deploy, payment)` and `(recent_change, revert_config, checkout)` (§9.1)
- [ ] P1 Red-team suite, output a table (§8.3)

## Phase 4: measurement

- [ ] P1 Accuracy runs: 10 per scenario 1 to 5 (§9.1)
- [ ] P1 Manual baseline: teammate with only `kubectl` and UIs, 3 times per scenario, in `bench/manual_baseline.md` (§9.2)
- [ ] P1 `bench/report.py` tables and charts (§9.3)
- [ ] P1 Card verification test with 5 people

## Phase 5: freeze

- [ ] README: what it is, architecture, how to run, safety model, results, limits, credits (§13)
- [ ] Deck (§11.3) and backup video

## Never cut

The audit log, the benchmark's time-to-recovery numbers.

## Integration proof (2026-11-13)

- Event router and in-process publish implemented per M Q8. Runtime mounting in
  Muaz's gateway entrypoint remains pending; no actual gateway main exists here.
- Shared Pattern type and schema defaults match M Q11. Cause classes unchanged.
- Rehearsal clients match M Q2/Q3. Server handlers and trust/policy tests still
  require Muaz's implementations. No rehearsal trust credits generated.
- Notifier component tests pass; real Discord delivery remains untested.
- Red-team component suite passes; live RBAC/admission rows remain pending.
- Full implementation/check evidence is recorded in STATE.md.

## Unattended-run proof (2026-11-13)

- Full suite: 166 passed; Ruff and mypy passed. No tests skipped or weakened.
- Harness now resumes completed attempt counts, reconnects SSE with deduplication,
  and saves partial measurements on timeout. Failed attempts remain in the data.
- Real SQLite integration covers verifier outcomes, trust counts, and card claims.
  Policy/checklist tests are still pending the policy/checklist implementation.
- Trust report reads real ledger rows without writes and distinguishes statistical
  confidence from gateway authorization. No live trust evidence was generated.
- Two verifier regressions were fixed with tests: missing readings and simultaneous
  human edits/severity spikes. Shared context records the exact change for M.
