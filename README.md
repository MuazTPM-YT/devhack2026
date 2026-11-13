# On-call agent: Twaha components

DevHack 2026 incident response agent. The model proposes a diagnosis and action.
Deterministic rules and the safety gateway decide whether an action can run.
The executor verifies recovery and retains responsibility for undo.

The repository includes Twaha's components, the OpenCode Go adapter, the observer,
the brain service, and initial cluster/chaos tooling. The gateway runtime,
remediation executor, policy checklist, and UI still need integration.
`IMPLEMENTATION.md` is the current plan; `docs/PLAN.md` contains conflicting older
contracts. Team contracts remain proposed until affected owners agree.

## Setup and checks

Use Python 3.12 and uv. Versions are constrained to minor releases; `uv.lock`
records exact packages. The resolver excludes releases after 2026-10-29.

```sh
uv sync --locked
uv run --locked pytest
uv run --locked ruff check .
uv run --locked mypy schemas brain gateway notifier bench observer chaos
```

Copy `.env.example` to `.env`, then fill only the settings for the service being
started. Credentials stay local. No credential is required for offline tests.

## Inference

Set `INFERENCE_PROVIDER=opencode_go`, `INFERENCE_MODEL` to an explicitly selected
Go model, and `OPENCODE_GO_API_KEY` to your subscription key. There is no Claude
API dependency, CLI subprocess, automatic model switch, or metered-provider fallback.

The provider protocol is in `brain/providers/base.py`; the concrete adapter is
`brain/providers/opencode_go.py`. It calls the documented Go Chat Completions
endpoint with its own user agent and a stable incident session header.
[OpenCode Go documentation](https://opencode.ai/docs/console/go/) describes model
availability, compatible clients, and allowance limits. Confirm that the selected
model and workload are supported by your subscription before live use.

### Agent mode (default)

`BRAIN_MODE=agent` (the default) runs diagnosis as a tool-using agent
(`brain/agent.py`, built on `pydantic-ai-slim`). The model gets a thin brief:
the incident, the rule pattern and action, the culprit guess, runbooks and past
incidents. It then reads telemetry through nine read-only tools in
`brain/tools.py`: service health, metric history (allow-listed PromQL only),
recent changes, dependencies, error traces, pods, Kubernetes events, pod error
logs, and earlier runs of a fix. Agent mode needs `PROMETHEUS_URL`.

The code keeps control. After 6 model rounds the tools are removed, and the
whole run has 150 s. Each tool result is redacted, its injection lines are
quarantined, and it is capped at 2000 chars. The model may cite only evidence IDs
that a tool returned, and a made-up ID goes back to the model. For known
patterns the rule's fix is still the action. When the agent fails, the rule
action goes to the gateway without a diagnosis. Every tool call is published as
`llm_called` with `tool`, `args`, `ms` and `evidence_ids`.

`BRAIN_MODE=bundle` keeps the single-call path below, for comparison.

### Bundle mode

Muaz's orchestration constructs `OpenCodeGoAdapter.from_env(http_client)`, then
`DiagnosisService(provider, Path("data/inference-cache"))`. Call
`await service.diagnose(bundle, pattern, rule_action)`. The result contains a
validated diagnosis, selected action, cache marker, error code, and events.
Publish every returned event through the gateway. The service itself cannot
write to Kubernetes or grant approval.

Requests have a 30-second overall deadline and at most two attempts. Unknown
proposals retain `pattern="unknown"`. Evidence IDs and bounded scale proposals
are checked locally. Model confidence never grants permission. Missing inference
preserves a supplied deterministic action; unknown incidents return no action.
Cache fallback requires the exact redacted input, model, and prompt version.

## Gateway mounting

Muaz mounts the event router in the gateway process. Its lifespan creates the
single audit writer, and `events.publish(event)` uses that same bus in process.
Use one worker; do not run multiple audit writers against the same file.

```python
from pathlib import Path
from gateway import events
from gateway.receipts import ReceiptStore, create_receipts_router

# Set app.state.audit_path before startup to override data/audit.jsonl.
store = ReceiptStore(Path("data/oncall.db"))
app.include_router(events.router)
app.include_router(create_receipts_router(store))

# Inside the running gateway:
# await events.publish({"type": "blocked", "payload": {"reason": "policy"}})
```

Router import creates no audit files. In-process publishing requires an active
gateway lifespan; a second active application is rejected. Tests and explicitly
injected applications can still use `create_events_router(bus)`. That factory
uses the supplied bus directly and does not activate module-level publishing.

Routes: `POST /events/publish`, `GET /events`, `GET /receipts` (newest first), `GET /receipts/{receipt_id}`.
The gateway also serves `GET /trust` (per-key counts, proven bound, gate state) and
`GET /audit/verify` (walks the hash chain; names the first broken seq) for the UI.
SSE event IDs are audit sequence numbers. `Last-Event-ID` resumes after that
sequence; slow clients disconnect and replay. Audit append succeeds before fanout.
Consumers receive `{seq, ts, event, prev_hash, hash}`; `event` contains
`{type, incident_id, payload}`. UI reads the inner payload.

`schemas/models.py` defines the shared types and typed payloads consumed here.
`Pattern` accepts only `recent_change`, `resource`, `protected`, and `unknown`.
It is shared by action requests, diagnosis events, and diagnosis service inputs.
`Cause.cause_class` keeps the separate cause vocabulary from the plan.
Notable payload requirements:

- `diagnosis_ready`: `pattern`, `culprit`.
- `approval_requested`: `approval_id`, `card`, `diff`, `forecast`, `expires_at`.
- `approval_decided`: `approval_id`, `decision`; optional `acknowledged`.
- `incident_resolved`, `escalated`, `handed_off`: `card`; optional `receipt_url`, `briefing`.
- `injection_quarantined`: `line_hash`, never the quarantined text.

Each lifecycle payload requires a matching `incident_id`. Other event types from
§5.3 retain extensible payloads until their producers agree on fields.
`checklist_step` uses `name`, `passed`, and optional `reason`.

Use `build_incident_card` for incident/diagnosis/decision cards and `build_card`
for receipt views. Both cap output at five lines. `FIXED` requires a success
outcome, prediction confirmation, and a clean harm check.

`ReceiptStore` writes redacted display records to a separate `receipt_views`
table. It does not create or replace the executor's receipts table. The executor
must retain its usable inverse and verification state separately. Display
receipts cannot serve as undo snapshots. No write or undo route is added here.

```sh
uv run --locked python scripts/verify_audit.py data/audit.jsonl
```

The verifier reports the first broken sequence. The hash chain detects changes
relative to its recorded hashes; it does not authenticate hostile storage or
protect against an attacker rewriting the entire chain. Redaction is a heuristic,
not proof that arbitrary text contains no secret.

## Discord notifier

Fill the Discord settings and `GATEWAY_URL` in `.env`. Channel and role IDs must
refer to the intended server. Set comma-separated `ONCALL_APPROVER_IDS` for
both gateway and notifier. The old `DISCORD_APPROVER_IDS` setting is ignored.
Never put the reserved `rehearsal-harness` identity in the human allowlist;
notifier startup rejects it.

```sh
uv run --locked --env-file .env uvicorn notifier.main:app --host 127.0.0.1 --port 7005
```

The notifier consumes gateway SSE, stores its cursor and message mappings in
`data/notifier.db`, and restores pending buttons after restart. FYI messages are
silent. Wake messages mention only the configured role. Pending approvals and
unresolved wakes re-page; the Acknowledge button on a wake page (approvers only)
or resolution stops paging. Expired
buttons close. Discord delivery is at least once across process crashes; a crash
between send and state persistence can produce a duplicate message.

Approval requests go to `POST /approvals/{id}/decide` with `decision` and
`decided_by`; replies must use `GatewayDecision`. Approvals require an `executed`
reply before the notifier confirms success. The gateway must independently check
identity, pending state, expiry, current safety checks, and concurrency. These
routers assume trusted local callers; caller authentication belongs to the
integrating gateway. Do not expose them on an untrusted network as-is.

Every write route on the gateway, brain and observer (any method but GET/HEAD/OPTIONS,
MCP tool calls included) needs header `X-Oncall-Token` equal to `ONCALL_API_TOKEN`.
Set the same value (16+ characters) in every process's `.env`; a missing token fails
at start. Read routes stay open for the UI. A manual approval is now:
`curl -X POST -H "X-Oncall-Token: $ONCALL_API_TOKEN" -H 'content-type: application/json'
-d '{"decision":"approved","decided_by":"<id>"}' $GATEWAY_URL/approvals/<id>/decide`.

The notifier and Go adapter are not exercised live by the offline suite.

## Breaking the shop (chaos CLI)

Faults are injected from the terminal, not from the UI. The CLI talks to the
chaos panel on `:7004` (`CHAOS_URL`), so every change is logged in
`data/ground_truth.jsonl`. The agent never reads that file. Every fault
stays until `reset`.

Interactive shell: run `uv run -m chaos.cli` with no command. Type `/` for
a dropdown of commands (arrow keys to pick, Tab or Enter to fill in);
`/inject <Tab>` lists the faults; `/watch` streams the agent's steps live;
the bottom bar shows gateway and observer state and the current severity.

One-shot commands (scripts, CI):

```bash
uv run python -m chaos.cli list                       # faults you can inject
uv run python -m chaos.cli inject bad-deploy          # break payment; watch http://localhost:3000/live
uv run python -m chaos.cli status                     # severity and per-service health (observer :7001)
uv run python -m chaos.cli kubectl -n shop scale deploy/cart --replicas=0   # break it your own way (admin)
uv run python -m chaos.cli truth                      # what was really broken and when
uv run python -m chaos.cli reset                      # undo everything, wait until healthy
```

`kubectl` runs as cluster admin without a shell: pipes and `$()` are passed
to kubectl as plain words. Read-only verbs (`get`, `describe`, `logs`, ...)
are not logged. Every other verb is logged as ground truth.

## Benchmarks and adversarial checks

The harness resets before every trial, waits for 60 seconds of zero severity,
and times out after 300 seconds. Chaos injection responses must contain `ts`,
`type`, and `target`; optional `should_wake` sets the trial's expected paging.
The observer must return numeric `severity` and `prometheus_ok` from `/health/now`.
Startup 503 responses are retried within the existing deadline. The full stability
window requires zero severity and `prometheus_ok=true`; stale metrics reset it.

```sh
uv run --locked --env-file .env python -m bench.harness --scenario bad-deploy --runs 10
uv run --locked python -m bench.report bench/results.jsonl
# Resume toward 30 attempts per scenario, without repeating recorded attempts:
uv run --locked --env-file .env python -m bench.harness --scenario bad-deploy --runs 30 --resume
# Read existing trust evidence without modifying the gateway database:
uv run --locked python -m bench.trust_report data/oncall.db
# After manual trials exist:
uv run --locked python -m bench.report bench/results.jsonl --manual data/manual-results.jsonl
# Export tables and chart files from recorded trials:
uv run --locked python -m bench.report bench/results.jsonl --manual data/manual-results.jsonl --output-dir bench/out  # the UI /benchmark page reads bench/out
uv run --locked pytest tests/redteam --junitxml=data/redteam.xml
uv run --locked python -m bench.redteam data/redteam.xml
```

Results append durably, including failed trials. Diagnosis accuracy requires both
matching pattern and culprit. Missing measurements remain null. Terminal payloads
may supply `tier`, `failed_customer_requests`, `harm_clean`, `prediction_held`,
`forecast_s`, and `actual_added_s`. Reports provide timing series for charts,
accuracy, wakes, verification samples, forecast error, and token usage. Token
usage is not reported as cash spent under a subscription. Manual timing records
are described in `bench/manual_baseline.md`; no manual measurements exist yet.

`--output-dir` writes `summary.json`, `timings.csv`, `report.md`, and `timings.svg`.
JSON output on stdout remains available. The SVG uses a common seconds scale:
filled bars show medians and outlines show worst timings. Zero is measured;
missing values have no bar. Tables include attempt/failure counts and measurement
sample counts. Manual-only scenarios remain visible. Source and outcome counts
identify rehearsal data; these reports do not claim production evidence or grant
authorization. Timing comparisons use only recorded samples, so inspect failures
and missing recovery counts before interpreting speedup. Invalid durations,
counts, booleans, or usage values fail with the input line number before export.
No recorded trials means an explicit empty report. Exports add no dependencies.

`--resume` treats `--runs` as the total attempt count per scenario in that output
file. Failed attempts count, so recovery never silently replaces failed evidence
with successes. Completed attempts are not injected again. Corrupt or truncated
result files fail before any reset. An interrupted attempt without a completed
row starts fresh through reset. Use one writer per output file and a separate
output file for each configuration or experiment.

SSE observation reconnects after disconnects or temporary stream errors, passing
the last audit sequence and ignoring replayed events. The overall observation
deadline (`--timeout`, default 600 s; flag-flip needs about 350 s) remains in force.
In rehearsal the harness approves only the first approval of a trial (the
scenario's fix); follow-ups such as `raise_limit` are left for a human. Timeout and failed approval/ledger requests
preserve already collected measurements in the failed trial record. Approval
and ledger POSTs are not automatically retried after uncertain network outcomes.
Normalized usage accepts either provider `usage` fields or sync metadata
`tokens_in` / `tokens_out`; an explicit usage map takes precedence.

The trust report opens an existing database read-only and keeps rehearsal and
real counts separate. `statistical_threshold_met` describes sample evidence
only; `authorization_evaluated` is false. Tools, protected targets, freshness,
budgets, and approvals still need gateway checks. Set `--confidence` and `--bar`
to match the gateway policy when it differs from 0.95 and 0.90. No report creates
trust credit or supplies missing measurements.

Rehearsal clients now follow Muaz's Q2/Q3 contract. Gateway routes are still
owned by Muaz and are not implemented on this branch. Use both `--rehearsal`
and `ONCALL_REHEARSAL=1`; disabled mode fails before reset or injection. The old
`REHEARSAL_ENABLED` setting is ignored.

- `POST /approvals/{id}/decide` receives
  `{decision: "approved", decided_by: "rehearsal-harness"}`.
- `POST /ledger/rehearsal` receives `{receipt_id, diagnosis_matched}`.

The client submits a match only for a positive receipt ID found in
`action_executed` or the terminal event. It compares both culprit and pattern;
a missing receipt produces no credit submission. A refused approval stops the
run. The gateway must return 404 for rehearsal credit when `ONCALL_REHEARSAL`
is not `1`, restrict the reserved identity to rehearsal mode, and independently
require prediction success and clean harm checks before trust credit. Use a
dedicated rehearsal gateway. The harness never sends raw ground truth to the
brain or gateway. No real rehearsal runs or trust credits have been generated.

The red-team report labels checks as component tests. It does not claim proof of
Kubernetes RBAC, admission policy, protected-target checks, budgets, freshness,
or auto-undo. Those require Muaz's gateway and Anirudh's cluster.

## Project graph

`graphify update .` refreshes the code graph without an LLM call. Generated
`graphify-out/graph.json`, `graph.html`, and `GRAPH_REPORT.md` describe the current
component relationships. Local graph caches and dated backups stay untracked.
