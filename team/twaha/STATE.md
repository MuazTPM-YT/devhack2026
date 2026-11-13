# Twaha [T]: state

**Last updated:** 2026-11-13
**Current phase:** Live end-to-end smoke passes on local k3d; next is LLM latency, then trust runs
**Branch:** `twaha/live-fixes-2` (from `origin/main` `89ca81e`), not pushed
**Implementation:** PRs #8, #12, #15 merged

## Done (with proof)

- Local k3d cluster `oncall` (context `k3d-oncall`) on Twaha's host, built from
  A's scripts; shop re-installed with A's new `k8s/values.yaml` (28 pods Running).
  `security_check.sh`: 19 PASS, 0 FAIL. Host DNS changed to 1.1.1.1/8.8.8.8 on
  "Wired connection 2" (iPhone tether DNS could not resolve ghcr.io); undo:
  `sudo nmcli connection modify "Wired connection 2" ipv4.dns "" ipv4.ignore-auto-dns no`.
- Smoke #3 on main `89ca81e` + branch fixes: PASS, `inc-1794542033381`,
  detect 49.9 s, diagnose 95.1 s, recover 188.1 s; Twaha clicked Approve in
  Discord; harm clean; audit verified 129 records. Smoke #1 and #2 (earlier,
  old main) escalated: the frontend-proxy verifier bug, fixed by M in `4c9cf29`.
  My own copy of that fix is in `git stash` ("superseded by 4c9cf29"), unused.
- `97d1a56` early abort needs the severity rise to hold `sustain_seconds`
  (30 s); 2 new tests failed first. `bf9f082` LLM deadline 45 s; adapter httpx
  timeout follows `DEADLINE_S`; test failed first. Checks: 332 passed, Ruff and
  mypy clean.

- Live checks 2026-11-13, isolated scratch dir (own `data/`, not repo `data/`),
  gateway started with an unreachable dummy kubeconfig (no cluster on this host):
  - OpenCode Go: one real `DiagnosisService` call, model `deepseek-v4.1-flash`,
    16.6 s, 2209 tokens (829 reasoning), valid diagnosis (rollback payment,
    confidence 0.82, cites journal + metric IDs). JSON-only prompt was enough.
  - Cross-process events: curl publish -> SSE ids 1-3 live; `Last-Event-ID: 1`
    replays 2-3; typed payload rejects bad `checklist_step`; audit verified 13.
  - Discord through real gateway SSE: FYI silent, ticket silent, wake with role
    mention, approval with 2 buttons, expiry edits message and removes buttons,
    re-page every 30 s, restart resumes at cursor 7 -> 9 with no duplicates.
    All smoke messages say `[SMOKE TEST, ignore]`. No human button click yet.
- Live smoke found 2 notifier bugs; fixed in `30af608` with tests that failed first:
  approved approvals kept re-paging "Approval pending"; silently expired approvals
  kept saying "pending". Gateway emits nothing on silent expiry.
- `tests/test_policy.py` (19 cases, `c46c301`): tool/target gates, protected beats
  actable flag, budget boundaries, every actable pair passes, policy tools equal
  schema tools, config invariants, auto-eligibility, `usage()` counts.
- Checks after: 260 passed; Ruff passed; mypy passed across 60 files.

- PR #13 merged into main as `7457a56`. Its shared-note conflict preserved both
  teams' entries. PR #15 includes that merge without further conflicts. Final
  pre-merge checks: 215 tests passed; Ruff passed; mypy passed across 53 files.

- PR #15: https://github.com/MuazTPM-YT/devhack2026/pull/15. Merged the later
  main `1b980a0`, including M's brain runtime. Preserved both shared handoffs and
  rebuilt conflicting generated graph files. Combined suite: 215 passed; Ruff
  passed; mypy passed across 53 files. Two upstream warnings remain. Graph:
  889 nodes, 2013 edges, 60 communities.
- Brain now constructs the existing Go adapter and forwards DiagnosisService
  result events through its publisher (`brain/main.py`, `tests/test_brain.py`).
  Gateway action handoff and live event delivery still need integration.

- Pulled main through `816de30`. Shared-note merge conflict kept both teams'
  entries; merge commit `f442ab9` retains the task/state update from PR #13's branch.
- Fixed benchmark startup handling: observer 503 retries within the deadline;
  stale/missing Prometheus status and boolean severity cannot pass readiness.
  Stale data resets the entire stability window. Two new regression tests first
  failed against the original implementation, then passed with the fix.
- Phase 4 report export: `--output-dir` writes JSON, CSV, Markdown tables, and
  SVG median/worst timings. Missing values retain sample count zero; measured
  zero remains zero. Manual-only scenarios remain visible. Source/outcome counts
  identify rehearsal records. Subscription token usage is not a cash charge.
- Report validation rejects invalid durations, counts, booleans, and usage before
  export. Tests cover invalid manual input, no partial export on validation failure,
  missing/zero measurements, empty reports, escaped SVG labels, and CSV formulas.
- Validation: full suite 203 passed; Ruff passed; mypy passed across 50 source
  files including observer and chaos. Two upstream deprecation warnings remain.
  Synthetic SVG preview inspected in a browser; labels fit the viewport. No
  synthetic trial was published as live evidence. Graph rebuilt: 828 nodes,
  1788 edges, 55 communities.

- Historical observer baseline `23eda91`: `uv run --locked pytest -q` -> 174 passed;
  `uv run --locked ruff check .` -> passed;
  `uv run --locked mypy schemas brain gateway notifier bench observer` ->
  passed across 44 source files. Two upstream deprecation warnings remain
  (discord.py audioop and Starlette anyio BlockingPortal alias).
- Updated TASK.md to separate tested components from live acceptance tasks.
  Removed obsolete blockers and historical claims that work was not pushed.
- PR #12 merged verifier safety fixes, resumable benchmark observation, and
  read-only trust reporting. Source validation before that merge: 160 tests
  passed; Ruff passed; mypy passed across 37 source files. Shell syntax and
  whitespace checks passed. The former 166 count included retired sync tests.
- OpenCode Go inference uses `InferenceProvider` and `OpenCodeGoAdapter`.
  `DiagnosisService` is the sole inference path. Main intentionally removed
  the synchronous facade, its tests, and its legacy env aliases.
- Provider tests cover evidence validation, deadlines, bounded attempts,
  redaction, hash-only quarantine, caching, and deterministic fallback.
- Shared schemas follow M Q11. Event consumers have typed payloads; other
  producer payload contracts still need agreement.
- Event router and async publish share one lifespan-owned audit writer.
  Tests cover hash chain, restart, SSE replay, and disconnect cleanup.
- Receipt display records coexist with M's tables in SQLite. Cards have
  five lines maximum and require prediction/harm evidence for FIXED claims.
- Notifier components cover persistent approval buttons, approver/expiry
  checks, gateway refusal, re-page, and cursor recovery. No live delivery proof.
- Benchmark writes attempts incrementally. Resume counts failures toward
  each scenario's target. Corrupt records fail before reset or injection.
  SSE reconnect deduplicates replay and preserves partial timings on failure.
  Uncertain approval/ledger POSTs are never retried automatically.
- Verifier regression tests cover missing service readings and simultaneous
  human edits/severity spikes. Human handoff takes precedence over early abort.
- SQLite integration tests cover verifier, receipt, and trust outcomes.
  Read-only trust reporting separates rehearsal and real counts. A statistical
  threshold never claims gateway authorization or writes ledger credit.
- Red-team component suite has 12 cases. Report code supports timing,
  accuracy, verification, token use, manual comparison, and red-team JSON.
- Python 3.12 manifest and lockfile exist. M approved and merged Kubernetes
  and PyYAML dependencies with observer PR #11; those are no longer blockers.

## In progress

- Services 7001-7005 and port-forwards 9090/8080 run detached from the repo root
  (scratchpad `start_services.sh`); they stop on reboot.

## Blocked / waiting on

- Smoke #8 FIXED end to end (first proven fix). Fixed today, all with tests
  that failed first: culprit tie (frontend-proxy), latency noise floor,
  LLM max_tokens/truncation, prediction required, LLM "why" on cards
  (labelled, new `incidents.why`), plain-word cards, absolute receipt links.
- Local only: `config/policy.yaml` `max_actions_per_hour: 30` (do not commit;
  `test_policy` budget boundary fails while it is set).
- M: `/approvals/{id}/decide` trusts `decided_by` from the body (auth gap).
- Push/PR of `twaha/live-fixes-2` waits on Twaha's OK.
- `agent.kubeconfig`/`reader.kubeconfig` tokens last 72 h; rerun
  `make_kubeconfigs.sh` after that.
- Human-only: approver button click on a real approval, manual baseline (3 runs
  per scenario), five-person card study, deck, video.
- `brain/major.py` not built yet, so major-incident policy tests are not written.

## Next

1. Repeat smoke a few times for stability, then overnight trust runs.
2. Escalated incidents never close when the service recovers by itself
   (re-page forever); needs an ack button or auto-close.
3. Overnight trust runs, accuracy runs, separate result files; then reports.
4. Try A's `/chaos/flag-flip` -> `revert_config` path live.
5. Manual baseline, card study, final README, deck, video.

## Notes for next session

- Use `INFERENCE_PROVIDER=opencode_go`, `INFERENCE_MODEL`, and
  `OPENCODE_GO_API_KEY`. Select the model explicitly. No Claude API dependency.
- Rehearsal requires `ONCALL_REHEARSAL=1`; default is disabled. Notifier and
  gateway share `ONCALL_APPROVER_IDS`. Retired env aliases remain removed.
- Rehearsal clients use `/approvals/{id}/decide` with the reserved rehearsal
  identity and `/ledger/rehearsal` with receipt ID and diagnosis match. Gateway
  must enforce rehearsal mode and independent prediction/harm evidence.
- `receipt_views` stores redacted display data. Executor must keep executable
  undo snapshots separately. Display records cannot undo changes.
- At confidence 0.95 and success bar 0.90, the trust core opens after 29 clean
  successes; the overnight collection target remains 30 attempts per key.
- ASGI thread tests hang in this sandbox; full pytest runs outside it.
- Export recorded trials with `python -m bench.report <results.jsonl> --manual
  <manual.jsonl> --output-dir data/report`. Omit `--manual` for agent-only reports.
- Environment overrides: `UV_CACHE_DIR=/tmp/devhack-uv-cache` and
  `UV_PYTHON_INSTALL_DIR=/tmp/devhack-python`.
