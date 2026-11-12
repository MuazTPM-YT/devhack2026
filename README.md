# On-call agent: Twaha components

DevHack 2026 incident response agent. The model proposes a diagnosis and action.
Deterministic rules and the safety gateway decide whether an action can run.
The executor verifies recovery and retains responsibility for undo.

This branch builds Twaha's components and the OpenCode Go adapter. It does not
contain the cluster, detector, remediation executor, gateway policy engine, or UI.
`IMPLEMENTATION.md` is the current plan; `docs/PLAN.md` contains conflicting older
contracts. Team contracts remain proposed until affected owners agree.

## Setup and checks

Use Python 3.12 and uv. Versions are constrained to minor releases; `uv.lock`
records exact packages. The resolver excludes releases after 2026-10-29.

```sh
uv sync --locked
uv run --locked pytest
uv run --locked ruff check .
uv run --locked mypy schemas brain gateway notifier bench
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

Routes: `POST /events/publish`, `GET /events`, `GET /receipts/{receipt_id}`.
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
unresolved wakes re-page; acknowledgement or resolution stops paging. Expired
buttons close. Discord delivery is at least once across process crashes; a crash
between send and state persistence can produce a duplicate message.

Approval requests go to `POST /approvals/{id}/decide` with `decision` and
`decided_by`; replies must use `GatewayDecision`. Approvals require an `executed`
reply before the notifier confirms success. The gateway must independently check
identity, pending state, expiry, current safety checks, and concurrency. These
routers assume trusted local callers; caller authentication belongs to the
integrating gateway. Do not expose them on an untrusted network as-is.

The notifier and Go adapter are not exercised live by the offline suite.

## Benchmarks and adversarial checks

The harness resets before every trial, waits for 60 seconds of zero severity,
and times out after 300 seconds. Chaos injection responses must contain `ts`,
`type`, and `target`; optional `should_wake` sets the trial's expected paging.
The observer must return numeric `severity` from `/health/now`.

```sh
uv run --locked --env-file .env python -m bench.harness --scenario bad-deploy --runs 10
uv run --locked python -m bench.report bench/results.jsonl
# Resume toward 30 attempts per scenario, without repeating recorded attempts:
uv run --locked --env-file .env python -m bench.harness --scenario bad-deploy --runs 30 --resume
# Read existing trust evidence without modifying the gateway database:
uv run --locked python -m bench.trust_report data/oncall.db
# After manual trials exist:
uv run --locked python -m bench.report bench/results.jsonl --manual data/manual-results.jsonl
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

`--resume` treats `--runs` as the total attempt count per scenario in that output
file. Failed attempts count, so recovery never silently replaces failed evidence
with successes. Completed attempts are not injected again. Corrupt or truncated
result files fail before any reset. An interrupted attempt without a completed
row starts fresh through reset. Use one writer per output file and a separate
output file for each configuration or experiment.

SSE observation reconnects after disconnects or temporary stream errors, passing
the last audit sequence and ignoring replayed events. The 300-second overall
observation deadline remains in force. Timeout and failed approval/ledger requests
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

## Main-branch diagnosis compatibility

The merged synchronous `brain.llm.diagnose(rendered, schema, validate, ...)`
interface remains available. It delegates to `OpenCodeGoSyncAdapter` in
`brain/providers/opencode_go_sync.py`; its HTTP and forced-tool-call behavior
remain compatible with main. `config_from_env()` for that interface reads
`OPENCODE_API_KEY` and `LLM_MODEL`. Its caller must redact rendered evidence and
supply the evidence/schema validator. Its timeout applies per HTTP attempt.

The async `DiagnosisService` and `OpenCodeGoAdapter` remain the preferred typed
integration, with the existing `OPENCODE_GO_API_KEY` / `INFERENCE_MODEL` settings,
evidence validation, quarantine, and overall deadline. No call interface or
provider credential setting from either branch was removed by the merge.
