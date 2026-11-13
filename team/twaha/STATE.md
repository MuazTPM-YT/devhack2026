# Twaha [T]: state

**Last updated:** 2026-11-13
**Current phase:** Chaos Lab + agent chooses the fix, offline checks done, live check NOT run
**Branch:** `twaha/chaos-lab` off `origin/main` `88d0ef7` (PR #43 merged), 19 commits, not pushed
**Implementation:** PRs #8, #12, #15, #43 merged

## Done (with proof)

- Chaos Lab + agent upgrade (`twaha/chaos-lab`), from `reports/akira-ui-chaos-panel-review.md`.
  Plan: `~/.claude/plans/i-want-you-to-floating-wand.md`. Twaha OK'd edits in A's and M's files.
  - Chaos: faults are tracked experiments (`chaos/experiments.py`, `data/chaos.db`): preflight,
    idempotency key, watchdog (expiry, cleanup, repaired-fault detection), restore only when the
    field still holds the injected value. Reviewed list `config/chaos.yaml` + live facts in
    `chaos/registry.py`. The six old routes run as presets through the engine, same response
    plus `experiment_id`. Every chaos route needs `CHAOS_JUDGE_TOKEN` (`X-Chaos-Token`), reads too.
  - UI: `/chaos` is the lab (composer, preview, active run, stop, reveal, blind draw by seed).
    Token added by `ui/app/api/chaos/[...path]/route.ts`; loopback same-origin only, else a
    passcode unlock. `/chaos/kubectl` is not proxied.
  - Brain: `BRAIN_MODE=agent` now lets the model accept a rule candidate, propose another built
    tool, or decline (`brain/rules.py candidates()`, `brain/capabilities.py`, `brain/agent.py
    select()`). `BRAIN_MODE=advise` = old rule-wins behaviour. Tool reads are `tool_called`.
    The model sees "the agent" / "another writer", never the field manager name.
  - Gateway: `ActionRequest.origin == "model"` always asks a human, skips the rule-equality
    freshness compare, writes no ledger credit. Verifier ignores readings with
    `prometheus_ok: false`. `still_live` compares env var by var.
  - Proof: `uv run pytest` 616 passed, 1 failed = local budget 30 (`test_policy`); Ruff clean;
    mypy clean, 75 files. UI: `tsc --noEmit` clean; 60 `node:test` pass, run through a
    compile step because this host's Node 22.22.1 cannot run `.ts` (`npm test` fails here for
    that reason, not for a test). Registry build and 3 previews run against live k3d with
    server-side dry runs only: 11 targets, `cartFailure 50%` + decoy and
    `checkout PAYMENT_ADDR wrong_host` preview OK, `shipping` flag refused "not watched".
  - NOT done: live run of an experiment or of agent mode with the new prompt (needs
    `CHAOS_JUDGE_TOKEN` in `.env` and a stack restart). No browser look at the populated lab:
    the running dev server has no token, pages only checked for HTTP 200 and SSR text.
    `.env.example` still lacks `CHAOS_JUDGE_TOKEN=` (deny rule blocks my edit).

- Agent tools (`twaha/agent-tools`): brain diagnoses as a pydantic-ai agent
  (`brain/agent.py`) with 9 read tools (`brain/tools.py`). Thin brief, max 6
  rounds, 150 s, cited ids must come from tool output, rule fix still wins.
  `BRAIN_MODE=agent|bundle`. Deps: pydantic 2.11 -> 2.14.1, pydantic-ai-slim
  2.63.0 (+14 transitive incl. openai 3.41, httpx2). Suite 508 passed (1 fail =
  local budget 30), Ruff + mypy clean.
  Probe: OpenCode Go passes native `tools`/`tool_calls` for deepseek-v4.1-flash
  (1.4 s + 1.2 s two turns); `x-opencode-session` header required (400 without).
  Live model on fake upstreams: 64.1 s, 6 requests, 19 tool calls, 26.3k prompt
  + 4.1k completion tokens, right cause (journal:41), prediction err_ratio
  < 0.05 within 120 s.
  Live smoke, agent mode, k3d bad deploy: PASS `inc-1794570030014`, detect
  51.0 s, diagnose 67.1 s, act 110.5 s (Twaha approved in Discord), recover
  180.7 s. Agent: 4 requests, 6 tool calls (health, changes, fix history,
  metric history, pods, logs), 14.5k + 0.9k tokens, ~16 s. Cause cites
  journal:53 + range metric, confidence 0.93; prediction held, harm clean;
  audit verified 841. Bundle-mode smokes #3/#11 diagnosed at 95.1/96.6 s.
  Before the run: collector OTLP push got HTTP 400 from Prometheus again
  (`rollout restart ds/otel-collector-agent` fixed it); `.env` lacked
  `ONCALL_API_TOKEN`, generated a local one (two-machine demo needs the
  same value on both).
  Open: `.env.example` needs `BRAIN_MODE=` and `PROMETHEUS_URL=` (deny rule
  blocks my edit); main.py wiring commit waits for it. pydantic-ai warns
  `httpx.AsyncClient` support goes in its v3 (we pin 2.63).

- 2026-11-13 live runs, all 4 PS failure types, 1 run each: bad deploy FIXED
  191 s, broken config FIXED 204 s (prediction held, harm clean), memory leak
  FIXED 343 s, datastore down escalated "UNDO FAILED" (bug, fixed below).
  Every fix asked approval: trust ledger empty. Results in
  `data/demo/scenarios.jsonl` and `data/demo/smoke-run.txt`.
- Fixes, each with a test that failed first: freshness no readings -> ask
  (`694e8c2`), smoke false PASS (`62df3f6`), no-safe-undo keeps the fix
  (`684af4d`, `eada3c1`), observer no span metrics = blind (`d8fe5a3`),
  blind-observer preflight in smoke/demo (`f3a70e5`), max_tokens 8192
  (`2d7557b`), frontend 400Mi / astronomy-db 200Mi (`9a0d3ec`, installed
  with helm 3, see SHARED_CONTEXT). Suite 444 passed, 1 fail = local budget.
- `scripts/demo.sh` (`b3b47f4`, `b538f53`): one command for the whole stack;
  `shop`/`backend` modes over Cloudflare quick tunnels, tested on one host.
- Cluster: RBAC re-applied (agent scales valkey-cart/kafka), otel collector
  restarted (OTLP pushes were rejected "too old"; root cause unknown).

- Card embeds (`twaha/card-embeds`): plain-word reasons, symptom line with units
  and normal value, suggested fix with command, AI sentence in its own field,
  evidence IDs moved to footer, colour by level. 407 passed on committed
  config; Ruff and mypy clean. New tests in `tests/test_card.py` (scenario per
  card, every known reason, embed limits, old-card fallback) and the gateway
  budget page in `tests/test_gateway.py`. PR #36 and #37 merged.
- Live check of the embeds, smoke #11: FIXED, `inc-1794551830062`, detect
  48.9 s, diagnose 96.6 s, recover 206.4 s; approval and fixed cards read in
  Discord; audit verified 394 records. Smokes #9 and #10 found 2 bugs, both
  fixed with tests that failed first: the audit redactor blanked
  `{name, value}` card fields (keys now `label`/`body`), and one unreadable
  saved wake crashed the notifier's whole TaskGroup (now re-pages as text).
  Smoke #10's LLM hit the 90 s deadline (no prediction, no AI field).

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

- Trust runs since 16:05: `bench.harness --rehearsal`, 30 x bad-deploy then
  30 x broken-config, output `data/demo/trust-runs.jsonl`, log
  `data/demo/trust-runs.log`. Stack started with `ONCALL_REHEARSAL=1
  scripts/demo.sh up`; notifier stopped so Discord is not flooded. One
  non-clean run puts that pair's trust back to 0.
- Before the demo: `scripts/demo.sh down && scripts/demo.sh up` (rehearsal
  off, notifier back), and set `max_actions_per_hour` back to 3.

## Blocked / waiting on

- Smoke #8 FIXED end to end (first proven fix). Fixed today, all with tests
  that failed first: culprit tie (frontend-proxy), latency noise floor,
  LLM max_tokens/truncation, prediction required, LLM "why" on cards
  (labelled, new `incidents.why`), plain-word cards, absolute receipt links.
- Local only: `config/policy.yaml` `max_actions_per_hour: 30` (do not commit;
  `test_policy` budget boundary fails while it is set).
- M: `/approvals/{id}/decide` trusts `decided_by` from the body (auth gap).
- Push/PR of `twaha/card-embeds` waits on Twaha's OK.
- `agent.kubeconfig`/`reader.kubeconfig` tokens last 72 h; rerun
  `make_kubeconfigs.sh` after that.
- Human-only: approver button click on a real approval, manual baseline (3 runs
  per scenario), five-person card study, deck, video.
- `brain/major.py` not built yet, so major-incident policy tests are not written.

## Next

0. Chaos Lab live check: add `CHAOS_JUDGE_TOKEN` to `.env`, `scripts/demo.sh down && up`, one guided
   run (`cartFailure 50%`), one decoy run, stop, reveal; then screenshots at 1440 and 390 px.
   Trust runs collected before this branch describe `advise` behaviour, not `agent`.
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
