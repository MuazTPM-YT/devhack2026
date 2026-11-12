# Twaha [T]: state

**Last updated:** 2026-11-13
**Current phase:** integration contracts aligned; gateway runtime/live checks pending
**Branch:** `codex/twaha-opencode-go`

## Done (with proof)

- Pulled origin/main through `bacb45a` (rules, freshness, trust, verifier,
  synchronous OpenCode diagnosis). Resolved brain/llm.py add/add conflict by
  retaining DiagnosisService and exporting main's sync facade through a provider
  adapter. Imported journal changes need type annotations only; runtime intact.
- Final merge validation: 142 passed, 1 upstream audioop warning. Adapter
  boundary test passes. Ruff/mypy passed (37 files).

- Integration slice: `uv run --locked pytest -q` -> 106 passed, 1 upstream
  discord.py audioop warning. Ruff and mypy passed (31 source files).
- T accepted M Q11: shared Pattern literal, existing schema ordering/defaults,
  and extra-field refusal. Inference keeps the OpenCode Go adapter.
- `gateway.events.router` plus async `publish(event)` match M Q8. Router
  lifespan owns one active bus; tests verify HTTP/in-process shared audit chain,
  restart, second-app refusal, SSE frame format, and disconnect cleanup.
- Harness follows M Q2/Q3: `ONCALL_REHEARSAL=1`, normal approval endpoint with
  reserved rehearsal identity, and `/ledger/rehearsal` using a receipt ID.
  Disabled mode makes no reset/injection calls; refused approvals stop credit.
- Notifier now reads `ONCALL_APPROVER_IDS`. Legacy DISCORD_APPROVER_IDS and
  REHEARSAL_ENABLED are ignored. Human allowlist cannot include rehearsal-harness.
- Shared SQLite test proves display receipt storage coexists with Muaz's
  operational tables. No migration, new dependency, or gateway main added.

- Merged Muaz's `origin/main` at `1741b6a`. Resolved env/ignore/shared-context
  conflicts without dropping either side. Combined suite: 90 passed. Added
  culprit counter/set type annotations for the existing mypy check.

- User confirmed Twaha role and approved Twaha components plus inference adapter.
- Read `CLAUDE.md`, `IMPLEMENTATION.md`, `docs/PLAN.md`, own architecture/tasks,
  and shared context. `IMPLEMENTATION.md` remains the current plan.
- Python 3.12.12, uv project, minor constraints, package age cutoff, `uv.lock`,
  secret/data ignore rules, blank `.env.example`, matching `AGENTS.md` rules.
- Shared schemas and consumed event payloads implemented as proposed contracts.
- OpenCode Go adapter behind `InferenceProvider`; injected HTTP client,
  explicit model setting, evidence validation, deadline, bounded attempts,
  redaction, hash-only quarantine, exact-input cache, deterministic fallback.
- Audit hash chain, first-broken-sequence CLI, durable publish, SSE replay,
  receipt display store, five-line incident/card variants.
- Discord notifier protocol and adapter, persistent approval buttons,
  approver/expiry checks, gateway refusal handling, cursor recovery, re-paging.
- Benchmark runner, incremental trial records, opt-in rehearsal client hooks,
  timing/accuracy/verification reports, manual comparison, red-team JSON report.
- Final offline suite: `uv run --locked pytest -q` -> 66 passed, 1 upstream
  discord.py deprecation warning. Focused benchmark suite: 4 passed.
- Ruff and mypy passed (29 source files). `uv sync --locked` and `uv lock --check`
  passed. Benchmark CLI help and Uvicorn version commands ran.
- Direct audit CLI regression test passed. Red-team suite: 12 passed.
- `graphify update .` passed: 439 nodes, 818 edges, 39 communities.
- Frequent logical commits recorded on feature branch. Nothing pushed.

## In progress

- Integration slice complete. Live wiring still needs Muaz's gateway entrypoint,
  approval/rehearsal handlers, and Anirudh's running shop.

## Blocked / waiting on

- Contract table still awaits all listed owners. T has explicitly accepted M's
  Q2/Q3/Q7/Q8/Q11 proposals; no agreement from A inferred.
- Muaz must mount `events.router` and receipt routes, then connect diagnosis
  results to orchestration. Module-level publish requires router lifespan.
- Muaz must implement authoritative approvals, policy/trust/freshness/budget tests,
  usable undo snapshots, and rehearsal-only endpoints before live integration.
- Anirudh must provide cluster, telemetry, and agreed chaos responses.
- No OpenCode Go key/model or Discord configuration supplied. Live checks not run.
- Accuracy runs, overnight trust runs, manual trials, card study, and live cluster
  red-team/security checks not run. No benchmark numbers or trust credits invented.

## Next

1. Muaz mounts components and implements the agreed approval/rehearsal handlers.
2. Configure `.env` locally with Go model/key and Discord settings.
3. Run live provider/notifier checks, then cluster smoke and benchmark trials.
4. Add gateway trust/policy tests when Muaz's implementations exist.

## Notes for my next session

- Rehearsal is opt-in with ONCALL_REHEARSAL=1. Normal notifier and gateway
  share ONCALL_APPROVER_IDS; use the updated .env.example.
- No Claude API dependency. Use `INFERENCE_PROVIDER=opencode_go`, `INFERENCE_MODEL`,
  `OPENCODE_GO_API_KEY`; exact model must be selected explicitly.
- `ReceiptStore` persists redacted display data in `receipt_views`; executor must
  keep executable inverses separately. Display records cannot undo changes.
- Gateway owns caller authentication and authoritative safety checks. Current
  HTTP contracts assume trusted local callers; notifier checks alone do not prove identity.
- ASGI thread tests hang inside this sandbox but pass outside it. Full suite was
  run outside sandbox. One upstream discord.py audioop deprecation warning remains.
- This environment uses `UV_CACHE_DIR=/tmp/devhack-uv-cache` and
  `UV_PYTHON_INSTALL_DIR=/tmp/devhack-python` because default locations are read-only.
- README contains exact mounting, event, approval, rehearsal, and run contracts.
