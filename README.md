# Akira: on-call agent

DevHack 2026 incident response agent. The model proposes a diagnosis and an
action. Deterministic rules and the safety gateway decide whether that action
may run. The executor checks that the service recovered and stays responsible
for undo.

This repository holds the OpenCode Go adapter, the observer, the brain service,
the gateway, the notifier and the chaos tooling. `IMPLEMENTATION.md` is the current plan. `docs/PLAN.md` has older contracts that
conflict with it. Team contracts stay proposed until the owners they affect agree.

## Setup and checks

Use Python 3.12 and uv. Dependencies are pinned to minor versions, and `uv.lock`
records the exact packages. The resolver ignores releases after 2026-10-29.

```sh
uv sync --locked
uv run --locked pytest
uv run --locked ruff check .
uv run --locked mypy schemas brain gateway notifier bench observer chaos
```

Copy `.env.example` to `.env` and fill in only the settings for the service you
are starting. Credentials stay on your machine. The offline tests need none.

## Inference

Set three variables:

- `INFERENCE_PROVIDER=opencode_go`
- `INFERENCE_MODEL` to the Go model you chose
- `OPENCODE_GO_API_KEY` to your subscription key

Nothing depends on the Claude API. There is no CLI subprocess, no automatic
model switch and no fallback to a metered provider.

The provider protocol lives in `brain/providers/base.py` and the adapter in
`brain/providers/opencode_go.py`. The adapter calls the documented Go Chat
Completions endpoint with its own user agent and a stable incident session
header. The [OpenCode Go documentation](https://opencode.ai/docs/console/go/)
covers which models are available, compatible clients and allowance limits.
Before live use, check that your subscription supports the model and workload
you picked.

### Agent mode (default)

`BRAIN_MODE=agent` is the default. Diagnosis runs as a tool-using agent
(`brain/agent.py`, built on `pydantic-ai-slim`). The model starts from a short
brief: the incident, the rule pattern, the culprit guess, runbooks and past
incidents. Agent mode needs `PROMETHEUS_URL`.

The model then reads telemetry through nine read-only tools in `brain/tools.py`:

- service health
- metric history (allow-listed PromQL only)
- recent changes
- dependencies
- error traces
- pods
- Kubernetes events
- pod error logs
- earlier runs of a fix

The model also picks the fix. The brief gives it two lists:

- `candidates`: every fix the evidence supports (`brain/rules.py candidates()`).
  The rule's own pick comes first as `c1`, the undo of the newest change. Older
  changes and resource fixes follow.
- `capabilities`: only the tools the gateway can actually build.

The model answers with one of:

- `accept`, with a candidate id
- `other`, with one listed tool and the evidence it cites
- `decline`, with what a human should check

It also names the strongest other explanation and says why that one lost.

Code stays in control:

- After 6 model rounds the tools are removed. The whole run gets 150 s.
- Every tool result is redacted, its injection lines are quarantined, and it is
  capped at 2000 chars.
- The model may cite only evidence IDs that a tool returned. A made-up ID or an
  unusable choice goes back to the model.
- Code builds the action from the choice and sets `origin`: `rule` when it is
  the rule's first pick, `model` for anything else.
- The gateway asks a human for every `model` action and writes nothing to the
  trust ledger for it.
- A decline wakes a human with the model's reason and the rule's suggestion.
- If the agent fails, the rule action goes to the gateway without a diagnosis.
- Every tool call is published as `tool_called` with `tool`, `args`, `ms` and
  `evidence_ids`.
- The model never sees which field manager wrote a change. It sees only "the
  agent" or "another writer".

Two other modes are kept for comparison runs. `BRAIN_MODE=advise` uses the same
tools, but the rule's fix always wins. That is how the brain behaved before the
agent could choose. `BRAIN_MODE=bundle` keeps the single-call path below.

### Bundle mode

Muaz's orchestration builds the service with
`OpenCodeGoAdapter.from_env(http_client)`, then
`DiagnosisService(provider, Path("data/inference-cache"))`. It then calls
`await service.diagnose(bundle, pattern, rule_action)`. The result holds a
validated diagnosis, the selected action, a cache marker, an error code and
events. Publish every returned event through the gateway. The service itself
cannot write to Kubernetes or grant approval.

Limits and fallbacks:

- Each request has a 30-second overall deadline and at most two attempts.
- Unknown proposals keep `pattern="unknown"`.
- Evidence IDs and bounded scale proposals are checked locally.
- Model confidence never grants permission.
- If inference is missing, a supplied deterministic action is kept. Unknown
  incidents return no action.
- The cache is a fallback only when the redacted input, model and prompt version
  all match exactly.

## Gateway mounting

Muaz mounts the event router in the gateway process. Its lifespan creates the
single audit writer, and `events.publish(event)` uses that same in-process bus.
Run one worker. Two audit writers must never share a file.

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

Importing the router creates no audit files. In-process publishing needs an
active gateway lifespan, and a second active application is rejected. Tests and
explicitly injected applications can still use `create_events_router(bus)`. That
factory uses the bus you pass in and does not turn on module-level publishing.

Routes:

- `POST /events/publish`
- `GET /events`
- `GET /receipts` (newest first)
- `GET /receipts/{receipt_id}`
- `GET /trust` for the UI: per-key counts, proven bound and gate state
- `GET /audit/verify` for the UI: walks the hash chain and names the first
  broken seq

SSE event IDs are audit sequence numbers, and `Last-Event-ID` resumes after
that sequence. Slow clients are disconnected and replay. An event is written to
the audit log before it fans out. Consumers receive
`{seq, ts, event, prev_hash, hash}`, where `event` is
`{type, incident_id, payload}`. The UI reads the inner payload.

### Shared types and cards

`schemas/models.py` defines the shared types and the typed payloads used here.
`Pattern` accepts only `recent_change`, `resource`, `protected` and `unknown`.
Action requests, diagnosis events and diagnosis service inputs all share it.
`Cause.cause_class` keeps the plan's separate cause vocabulary.

Required payload fields:

- `diagnosis_ready`: `pattern`, `culprit`.
- `approval_requested`: `approval_id`, `card`, `diff`, `forecast`, `expires_at`.
- `approval_decided`: `approval_id`, `decision`; optional `acknowledged`.
- `incident_resolved`, `escalated`, `handed_off`: `card`; optional `receipt_url`, `briefing`.
- `injection_quarantined`: `line_hash`, never the quarantined text.

Every lifecycle payload needs a matching `incident_id`. Other event types from
§5.3 keep open payloads until their producers agree on fields. `checklist_step`
uses `name`, `passed` and an optional `reason`.

`build_incident_card` makes incident, diagnosis and decision cards.
`build_card` makes receipt views. Both cap output at five lines. A card says
`FIXED` only with a success outcome, a confirmed prediction and a clean harm
check.

`ReceiptStore` writes redacted display records to its own `receipt_views`
table. It does not create or replace the executor's receipts table. The executor
must keep its usable inverse and verification state separately, because display
receipts cannot serve as undo snapshots. This code adds no write or undo route.

### Audit check

```sh
uv run --locked python scripts/verify_audit.py data/audit.jsonl
```

The verifier reports the first broken sequence. The hash chain catches changes
against its recorded hashes. It does not authenticate hostile storage, and it
cannot stop an attacker who rewrites the whole chain. Redaction is a heuristic.
It does not prove that arbitrary text holds no secret.

## Discord notifier

Fill in the Discord settings and `GATEWAY_URL` in `.env`. Channel and role IDs
must point at the intended server. Set `ONCALL_APPROVER_IDS` (comma-separated)
for both the gateway and the notifier. `DISCORD_APPROVER_IDS` is ignored. Never
put the reserved `rehearsal-harness` identity in the human allowlist; the
notifier refuses to start if you do.

```sh
uv run --locked --env-file .env uvicorn notifier.main:app --host 127.0.0.1 --port 7005
```

How the notifier behaves:

- It reads the gateway SSE stream and keeps its cursor and message mappings in
  `data/notifier.db`. After a restart it restores pending buttons.
- FYI messages are silent. Wake messages mention only the configured role.
- Pending approvals and unresolved wakes page again. Paging stops when an
  approver presses Acknowledge on the wake page, or when the incident resolves.
- Expired buttons close.
- Discord delivery is at least once across process crashes. A crash between
  sending and saving state can produce a duplicate message.

Approval requests go to `POST /approvals/{id}/decide` with `decision` and
`decided_by`, and replies must use `GatewayDecision`. The notifier confirms
success only after an `executed` reply. The gateway must check identity,
pending state, expiry, current safety checks and concurrency on its own. These
routers assume trusted local callers; caller authentication belongs to the
gateway that integrates them. Do not expose them on an untrusted network as
they are.

### API token

Every write route on the gateway, brain and observer needs the header
`X-Oncall-Token` set to `ONCALL_API_TOKEN`. A write route is any method except
GET, HEAD and OPTIONS, MCP tool calls included. Put the same value (16+
characters) in every process's `.env`. A process with no token fails at start.
Read routes stay open for the UI. A manual approval looks like this:

```sh
curl -X POST -H "X-Oncall-Token: $ONCALL_API_TOKEN" -H 'content-type: application/json' \
  -d '{"decision":"approved","decided_by":"<id>"}' $GATEWAY_URL/approvals/<id>/decide
```

The offline suite does not exercise the notifier or the Go adapter live.

## Breaking the shop (Chaos Lab)

Open `http://localhost:3000/chaos` and pick a target, what breaks, how hard and
when.

- `Preview` shows the exact field that will change and every reason the run
  might not start.
- `Start experiment` applies it. The page then shows the run next to Akira's
  response, a `Stop and restore` button, and a reveal that puts the injected
  cause next to what Akira concluded.
- `Blind challenge` draws a valid fault by seed and hides the answer until you
  reveal it.
- A decoy adds a harmless change after the fault, so the newest change is not
  the cause.

`config/chaos.yaml` holds the reviewed list of what may be broken.
`chaos/registry.py` joins it with live facts (flag variants, env keys,
replicas). Anything else shows as unavailable, with its reason. Experiments live
in `data/chaos.db` (`chaos/experiments.py`). That module handles preflight,
idempotent start, a watchdog that expires and cleans up runs, and a restore that
writes only if the field still holds the injected value. Akira never gets credit
for a fault that ends by timer, stop or reset.

The chaos panel on `:7004` answers only to `CHAOS_JUDGE_TOKEN` in the
`X-Chaos-Token` header. That includes reads, because ground truth and experiment
specs are the answers. The UI server adds the token (`ui/app/api/chaos`), so it
never reaches the browser. From another machine, the page asks for the token
once as a passcode. Agent processes drop the token when they start. The browser
cannot reach the admin `kubectl` route.

### From a terminal

The CLI talks to the same panel (`CHAOS_URL`), so every change is logged in
`data/ground_truth.jsonl`. The agent never reads that file. The six fixed faults
stay in place until their cause is reversed or you run `reset`.

For the interactive shell, run `uv run --env-file .env -m chaos.cli` with no
command. Type `/` for a dropdown of commands (arrow keys to pick, Tab or Enter to
fill in). `/inject <Tab>` lists the faults and `/watch` streams the agent's steps
live. The bottom bar shows gateway and observer state and the current severity.

One-shot commands, for scripts and CI:

```bash
uv run --env-file .env python -m chaos.cli list                       # faults you can inject
uv run --env-file .env python -m chaos.cli inject bad-deploy          # break payment; watch http://localhost:3000/live
uv run --env-file .env python -m chaos.cli status                     # severity and per-service health (observer :7001)
uv run --env-file .env python -m chaos.cli kubectl -n shop scale deploy/cart --replicas=0   # break it your own way (admin)
uv run --env-file .env python -m chaos.cli truth                      # what was really broken and when
uv run --env-file .env python -m chaos.cli reset                      # undo everything, wait until healthy
```

`kubectl` runs as cluster admin but without a shell, so pipes and `$()` reach
kubectl as plain words. Read-only verbs (`get`, `describe`, `logs`, ...) are not
logged. Every other verb is logged as ground truth.

## Akira MCP (Claude Code and Claude Desktop)

`akira_mcp/` is a local MCP server over stdio. It gives Claude Akira's own
records, not the shop's raw metrics. It has no PromQL, traces or pod logs for
two reasons: log text is an injection path, and raw data plus chaos control
would let Claude solve incidents itself. Use a separate read-only connector for
raw shop data.

| Group | On when | Tools |
|---|---|---|
| `read` | always | `get_akira_status`, `get_service_health`, `list_incidents`, `get_incident`, `get_incident_report`, `list_receipts`, `get_receipt`, `get_trust_table`, `verify_audit_log`, `list_pending_approvals`, `list_pages`, `watch_events`, `get_runbooks`, `get_recent_changes` (needs `ONCALL_API_TOKEN`) |
| `chaos` | `AKIRA_MCP_TOOLSETS` has `chaos`; needs `CHAOS_JUDGE_TOKEN` | `list_chaos_options`, `preview_chaos`, `create_chaos`, `draw_random_chaos`, `get_chaos_experiments`, `stop_chaos`, `reset_shop` |
| `approvals` | `AKIRA_MCP_TOOLSETS` has `approvals`; needs `ONCALL_API_TOKEN` and `AKIRA_OPERATOR_ID` | `decide_approval`, `acknowledge_page`, `clear_receipt` |

- If a group's secret is missing, the server stops at start and names the
  variable. Without `chaos`, the process drops `CHAOS_JUDGE_TOKEN`.
- Approvals and acks act as `AKIRA_OPERATOR_ID`, a Discord id that must be in
  `ONCALL_APPROVER_IDS`. Claude cannot choose the identity. Before every write,
  the server shows a confirm dialog if the client supports MCP elicitation, and
  refuses if you decline. Clients without elicitation fall back to their own
  per-call permission prompt, so **never allowlist the write tools**. Discord
  shows "by <user> via Akira MCP" on the closed card.
- Chaos runs go through the panel, so ground truth is logged. They are marked
  `origin: akira-mcp`. The admin `kubectl` box, ground truth and the reveal are
  not exposed.
- With `chaos` and `approvals` both on, one Claude session can break the shop
  and approve its own fix. Bench runs that need to be independent must leave
  those runs out (use `origin` to find them).

In Claude Code, the repo's `.mcp.json` starts the server. Run `claude` from the
repo root and approve the `akira` server once; `/mcp` shows its state. In Claude
Desktop, add this to `claude_desktop_config.json` with absolute paths:

```json
{"mcpServers": {"akira": {"command": "/absolute/path/to/uv",
  "args": ["run", "--directory", "/absolute/path/to/devhack2026", "--locked",
           "--env-file", "/absolute/path/to/devhack2026/.env", "python", "-m", "akira_mcp"]}}}
```

For a live feed without an MCP client, run the command below. It prints one line
per event, reconnects on its own, and works with Claude Code's Monitor tool.

```sh
uv run --locked --env-file .env python -m akira_mcp watch [--incident inc-...] [--after SEQ]
```

The server talks to the other services only over HTTP:

- gateway: `GET /incidents`, `/incidents/{id}`, `/approvals`, `/events/log`
- observer: `/health/now`, `/journal`
- notifier: `GET /pages`, `POST /pages/{id}/ack`
- chaos panel routes
- brain: `GET /health`

## Benchmarks and adversarial checks

The harness resets before every trial, waits for 60 seconds of zero severity,
and times out after 300 seconds. It expects:

- Chaos injection responses with `ts`, `type` and `target`. An optional
  `should_wake` sets whether the trial expects a page.
- An observer `/health/now` that returns a numeric `severity` and
  `prometheus_ok`.

Startup 503 responses are retried within the same deadline. The stability
window needs zero severity and `prometheus_ok=true` for its full length, and
stale metrics restart it.

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
uv run --locked python -m bench.report bench/results.jsonl --manual data/manual-results.jsonl --output-dir bench/out
uv run --locked pytest tests/redteam --junitxml=data/redteam.xml
uv run --locked python -m bench.redteam data/redteam.xml
```

### Reports

Results are appended durably, failed trials included. A diagnosis counts as
accurate only when both pattern and culprit match. Missing measurements stay
null. Terminal payloads may supply `tier`, `failed_customer_requests`,
`harm_clean`, `prediction_held`, `forecast_s` and `actual_added_s`.

Reports give timing series for charts, accuracy, wakes, verification samples,
forecast error and token usage. Token usage is not reported as cash spent,
because inference runs under a subscription. `bench/manual_baseline.md`
describes the manual timing records. No manual measurements exist yet.

`--output-dir` writes `summary.json`, `timings.csv`, `report.md` and
`timings.svg`. JSON on stdout still works.

- The SVG uses one shared seconds scale. Filled bars show medians and outlines
  show worst timings. A zero is a measured zero; missing values get no bar.
- Tables include attempt and failure counts and measurement sample counts.
  Manual-only scenarios stay visible.
- Source and outcome counts mark rehearsal data. These reports do not claim
  production evidence or grant authorization.
- Timing comparisons use only recorded samples, so check failures and missing
  recovery counts before reading anything into a speedup.
- Invalid durations, counts, booleans or usage values fail with the input line
  number before export.
- With no recorded trials you get an explicit empty report.
- Exports add no dependencies.

### Resuming a run

`--resume` treats `--runs` as the total number of attempts per scenario in that
output file. Failed attempts count, so resuming never quietly swaps failed
evidence for successes. Completed attempts are not injected again. Corrupt or
truncated result files fail before any reset. An interrupted attempt with no
completed row starts fresh through reset. Use one writer per output file, and a
separate output file for each configuration or experiment.

### Event stream and approvals

SSE observation reconnects after disconnects or temporary stream errors. It
passes the last audit sequence and ignores replayed events. The overall deadline
(`--timeout`, default 600 s; flag-flip needs about 350 s) still applies.

In rehearsal the harness approves only the first approval of a trial, which is
the scenario's fix. Follow-ups such as `raise_limit` are left for a human. A
timeout or a failed approval or ledger request keeps the measurements already
collected in the failed trial record. Approval and ledger POSTs are not retried
automatically after uncertain network outcomes.

Normalized usage accepts either provider `usage` fields or sync metadata
`tokens_in` / `tokens_out`. An explicit usage map wins.

### Trust report

The trust report opens an existing database read-only and keeps rehearsal and
real counts apart. `statistical_threshold_met` describes sample evidence only,
and `authorization_evaluated` is false. Tools, protected targets, freshness,
budgets and approvals still need gateway checks. Set `--confidence` and `--bar`
to match the gateway policy if it differs from 0.95 and 0.90. No report creates
trust credit or fills in missing measurements.

### Rehearsal

Rehearsal clients follow Muaz's Q2/Q3 contract. The gateway routes belong to
Muaz and are not implemented on this branch. Pass `--rehearsal` and set
`ONCALL_REHEARSAL=1`. With rehearsal disabled, the run fails before reset or
injection. `REHEARSAL_ENABLED` is ignored.

- `POST /approvals/{id}/decide` receives
  `{decision: "approved", decided_by: "rehearsal-harness"}`.
- `POST /ledger/rehearsal` receives `{receipt_id, diagnosis_matched}`.

The client submits a match only for a positive receipt ID found in
`action_executed` or the terminal event. It compares both culprit and pattern.
A missing receipt means no credit is submitted. A refused approval stops the
run.

The gateway must:

- return 404 for rehearsal credit when `ONCALL_REHEARSAL` is not `1`
- allow the reserved identity only in rehearsal mode
- require prediction success and clean harm checks on its own before it gives
  trust credit

Use a dedicated rehearsal gateway. The harness never sends raw ground truth to
the brain or gateway. No real rehearsal runs or trust credits have been
generated.

### Red team

The red-team report labels its checks as component tests. It does not claim to
prove Kubernetes RBAC, admission policy, protected-target checks, budgets,
freshness or auto-undo. Those need Muaz's gateway and Anirudh's cluster.

## Project graph

`graphify update .` refreshes the code graph without an LLM call. The generated
`graphify-out/graph.json`, `graph.html` and `GRAPH_REPORT.md` describe how the
components relate today. Local graph caches and dated backups stay untracked.
