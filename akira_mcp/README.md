# Akira MCP

A local MCP server (stdio) that lets Claude (Claude Desktop, Claude Code) work
with **Akira's own records and controls**: incidents, the event bus, receipts,
trust, approvals, Discord pages and the Chaos Lab. It is a thin, typed client
over the HTTP APIs the Akira services already run. It holds no state and has
no database of its own.

- Package: `akira_mcp/` (`settings.py`, `api.py`, `server.py`, `report.py`, `watch.py`, `__main__.py`)
- Tests: `tests/test_akira_mcp.py` (35 tests), plus route tests in `tests/test_gateway.py`,
  `tests/test_notifier.py`, `tests/test_experiments.py`, `tests/test_auth.py`
- SDK: `mcp~=1.30.0` (`mcp.server.fastmcp.FastMCP`), `httpx`. No new dependency.

## Contents

1. [What it is for, and what it is not for](#scope)
2. [How it fits in](#architecture)
3. [Setup](#setup)
4. [Configuration](#configuration)
5. [Tool reference](#tools)
6. [Safety model](#safety)
7. [Live feed CLI](#watch)
8. [Server-side routes added for it](#routes)
9. [Live test results](#tests)
10. [Known limits and open items](#limits)

<a id="scope"></a>
## 1. What it is for, and what it is not for

**For.** Ask Claude about Akira's work in plain language:

- What happened in past incidents, how long each stage took, what was fixed and whether it was proven.
- Whether Akira and its services are healthy right now.
- What is happening live (a cursor-based event feed).
- What Discord is waiting on, and approve, reject or acknowledge without opening Discord.
- Break the shop on purpose from the reviewed chaos config and watch Akira respond.

**Not for.** Raw data from the demo shop (the OpenTelemetry demo app) is not
exposed: no PromQL, no Jaeger traces, no pod logs, no admin `kubectl`.

- The observer's derived view (`/health/now`: error ratio, p95, bad pods,
  severity per service) and the evidence inside incidents already carry the
  numbers Claude needs.
- Pod logs and traces contain text written by the system under test, which is a
  prompt-injection path. Akira quarantines such lines before its own model sees
  them; a raw-log tool would skip that filter.
- Raw metrics plus chaos control would let Claude solve incidents itself, so a
  demo would no longer show that Akira fixed it.
- If raw shop data is ever wanted, add a separate read-only connector (for
  example Grafana's official `mcp-grafana` with `--disable-write`).

<a id="architecture"></a>
## 2. How it fits in

```
Claude Desktop / Claude Code
        | stdio (JSON-RPC)
        v
  python -m akira_mcp  ── HTTP ──> gateway  :7003  incidents, approvals, receipts, trust, audit, event log
   (akira_mcp/server.py)  ── HTTP ──> observer :7001  /health/now, /journal
                          ── HTTP ──> brain    :7002  /health
                          ── HTTP ──> notifier :7005  /health, /pages, /pages/{id}/ack   (Discord)
                          ── HTTP ──> chaos    :7004  /chaos/registry, /chaos/experiments..., /chaos/reset
```

- **HTTP only.** It never opens `data/*.db` or `data/*.jsonl`. It works the
  same if the services run on another machine (set the `*_URL` variables).
- **Two secrets, two planes**, as in the rest of Akira:
  - `ONCALL_API_TOKEN` (header `X-Oncall-Token`): the agent plane. Needed for
    approvals, acks, clearing receipts and the observer journal.
  - `CHAOS_JUDGE_TOKEN` (header `X-Chaos-Token`): the judge plane. Needed for
    every chaos route, reads included.
- **Process model.** The client (Claude Desktop) starts one process per
  session and talks over stdin/stdout. Logs go to stderr only; stdout is the
  protocol channel.

Code map:

| File | Job |
|---|---|
| `settings.py` | Reads env once at start; tool groups; fails loud with the variable's name; drops the judge token when chaos is off |
| `api.py` | One `httpx.AsyncClient`; turns HTTP errors into one readable line (`AkiraError`); token headers |
| `server.py` | `build_server()`: registers tools per group, with annotations, confirmation, redaction and a size cap |
| `report.py` | Pure function `incident_report()`: stage timings and outcome from one incident's detail |
| `watch.py` | `python -m akira_mcp watch`: tails the bus, one line per event, reconnects |
| `__main__.py` | Entry point: `serve` (default) or `watch` |

<a id="setup"></a>
## 3. Setup

### Claude Desktop

Add to `~/.config/Claude/claude_desktop_config.json` (Linux; macOS uses
`~/Library/Application Support/Claude/`). Use absolute paths: Claude Desktop
does not start the server in the repo.

```json
{
  "mcpServers": {
    "akira": {
      "command": "/usr/bin/uv",
      "args": ["run", "--directory", "/home/anirudh/Desktop/DevHack/devhack2026", "--locked",
               "--env-file", "/home/anirudh/Desktop/DevHack/devhack2026/.env", "python", "-m", "akira_mcp"]
    }
  }
}
```

Fully quit and reopen Claude Desktop (`pkill -f claude-desktop`). The `akira`
connector then appears in the chat's tools menu.

### Claude Code

The repo's `.mcp.json` registers it:

```json
{"mcpServers": {"akira": {"command": "uv", "args": ["run", "--locked", "--env-file", ".env", "python", "-m", "akira_mcp"]}}}
```

Run `claude` from the repo root and approve the `akira` server once. `/mcp`
shows its state; `claude mcp list` shows "Pending approval" until then.

### Check the config without a client

```sh
uv run --locked --env-file .env python -c "from akira_mcp.settings import load; s=load(); print('ok', sorted(s.toolsets))"
```

It prints `ok [...]` or the exact problem, for example
`AKIRA_OPERATOR_ID must be a Discord user id (digits only)`.

### Services that must run

| Service | Port | Start (from `CLAUDE.md`) | Needed for |
|---|---|---|---|
| gateway | 7003 | `uv run --locked --env-file .env uvicorn gateway.main:app --host 127.0.0.1 --port 7003` | most read tools, approvals |
| observer | 7001 | `... uvicorn observer.main:app --host 127.0.0.1 --port 7001` | health, journal |
| brain | 7002 | `... uvicorn brain.main:app --host 127.0.0.1 --port 7002` | status only |
| notifier | 7005 | `... uvicorn notifier.main:app --host 127.0.0.1 --port 7005` | pages, ack |
| chaos | 7004 | `... uvicorn chaos.main:app --host 127.0.0.1 --port 7004` | chaos tools |

Services started before branch `anirudh/akira-mcp` lack the new routes and
answer 404 (gateway, brain, notifier) or 422 `body.origin: Extra inputs are
not permitted` (chaos). Restart them.

<a id="configuration"></a>
## 4. Configuration (`.env`)

| Variable | Default | Used for |
|---|---|---|
| `AKIRA_MCP_TOOLSETS` | `read` | Comma-separated groups: `read`, `chaos`, `approvals`. `read` is always on. Unknown name = startup error |
| `AKIRA_OPERATOR_ID` | none | The Discord user id Claude approves and acks as. Digits only, must be in `ONCALL_APPROVER_IDS`. Required with `approvals` |
| `ONCALL_API_TOKEN` | none | Required with `approvals`; also turns on `get_recent_changes` |
| `ONCALL_APPROVER_IDS` | none | The allowlist `AKIRA_OPERATOR_ID` is checked against (same list the gateway uses) |
| `CHAOS_JUDGE_TOKEN` | none | Required with `chaos`. Removed from the process when chaos is off |
| `GATEWAY_URL` | `http://127.0.0.1:7003` | gateway |
| `OBSERVER_URL` | `http://127.0.0.1:7001` | observer |
| `BRAIN_URL` | `http://127.0.0.1:7002` | brain |
| `NOTIFIER_URL` | `http://127.0.0.1:7005` | notifier |
| `CHAOS_URL` | `http://127.0.0.1:7004` | chaos panel |

Which groups to turn on:

| `AKIRA_MCP_TOOLSETS` | Claude can |
|---|---|
| `read` | look only |
| `read,approvals` | look, approve or reject, acknowledge pages, clear receipts |
| `read,chaos` | look, break and reset the shop |
| `read,chaos,approvals` | everything (one session can break the shop and approve its own fix; see [Safety](#safety)) |

Startup errors name the variable, for example:
`missing required env var(s): CHAOS_JUDGE_TOKEN (at least 16 characters) (needed by AKIRA_MCP_TOOLSETS=chaos,read)`.

<a id="tools"></a>
## 5. Tool reference

Every tool returns a JSON object. Every result passes through
`brain.redact.redact_value` (secrets, tokens, emails scrubbed) and is cut at
60,000 characters (`{"truncated": true, "note": ..., "preview": ...}`). A
failed call returns an MCP error with one line naming the HTTP status, method,
URL and the service's reason, for example
`404 from GET http://127.0.0.1:7003/incidents/inc-x: unknown incident`, or
`cannot reach http://127.0.0.1:7003/approvals (ConnectError); is that service running?`.

Annotations (hints for the client):

| Kind | readOnly | destructive | idempotent | Confirmation |
|---|---|---|---|---|
| read | yes | no | yes | none |
| write | no | yes | no | dialog, or client permission prompt |
| restore (`stop_chaos`) | no | no | yes | client permission prompt |

### 5.1 Read group (always on)

| Tool | Parameters | Service and route | Returns |
|---|---|---|---|
| `get_akira_status` | none | gateway `GET /health`, brain `GET /health`, observer `GET /health/now`, notifier `GET /health`, chaos `GET /chaos/experiments` (only with chaos on) | per service `up` or `error`; observer `prometheus_ok`, `severity`, `reading_age_s`; notifier `discord_ready`; the groups on; the operator id |
| `get_service_health` | `only_unhealthy` (bool) | observer `GET /health/now` | `severity`, `prometheus_ok`, `last_ok_ts`, `reading_age_s`, per service `err_ratio`, `p95_ms`, `baseline_p95_ms`, `breaching`, `first_breach_ts`, `bad_pods`, `unhealthy` |
| `list_incidents` | `state` (exact: `resolved`, `escalated`, `handed_off`, `awaiting_approval`, `verifying`, `open`), `unfinished` (bool), `limit` 1-200 (20) | gateway `GET /incidents` | incidents newest first: id, times, culprit, victims, pattern, major, tier, state, severity at open, the model's one-line why (dropped if it looks like an instruction) |
| `get_incident` | `incident_id`, `events_limit` 1-1000 (150), `raw_events` (false) | gateway `GET /incidents/{id}` | the incident, its approvals (with the exact action and `past_expiry`), receipts with their cards, similar past incidents, `events_total`, and `timeline`: one line per bus event (`seq`, `ts`, `type`, `tone`, `text`). `raw_events=true` adds full payloads |
| `get_incident_report` | `incident_id` | gateway `GET /incidents/{id}` + `report.py` | `outcome`, culprit, victims, pattern, `seconds_from_onset` (`detect`, `diagnose`, `act`, `finish`), diagnosis (pattern, culprit, decision, origin, reason), `model_said`, actions (tool, target, outcome, `prediction_held`, `harm_clean`, card), approvals (who decided), final card, similar incidents, notes (for example "resolved with no action") |
| `list_receipts` | `limit` 1-100 (10) | gateway `GET /receipts` | id, incident, tool, target, outcome, card text |
| `get_receipt` | `receipt_id` | gateway `GET /receipts/{id}` | full receipt: diff, inverse (undo), blast radius, forecast, checklist, trust, verification, hashes, and the card |
| `get_trust_table` | none | gateway `GET /trust` | per (pattern, action, target): successes, failures, rehearsal/real counts, lower bound, bar, `open` (may act without a human) |
| `verify_audit_log` | none | gateway `GET /audit/verify` | `{"ok": true, "records": N}` or the first broken seq |
| `list_pending_approvals` | none | gateway `GET /approvals?state=pending` | approval id, incident, created/expires, `past_expiry`, the exact action (tool, target, params, evidence) |
| `list_pages` | none | notifier `GET /pages` | wake pages still re-paging (incident, briefing, page count, last page, headline, acknowledged by whom) and approval messages not yet decided |
| `watch_events` | `after_seq` (omit = from now), `wait_s` 0-60 (30), `incident_id`, `types` (list), `max_events` 1-500 (100) | gateway `GET /events/log` (polled every 1 s) | `events` (one line each), `next_seq` (pass back as `after_seq`), `last_seq`, `timed_out` |
| `get_runbooks` | `runbook_id` (optional, e.g. `RB-01`) | local `config/runbooks.yaml` via `brain.runbooks.load` | id, title, owner, severity, steps, `require_approval`, `forbid_tools`, match rules |
| `get_recent_changes` | `since_minutes` 1-1440 (30), `object` (e.g. `deployment/payment`) | observer `GET /journal` with `X-Oncall-Token` | the cluster change journal: kind, object, field manager, diff and inverse (redacted). Only listed when `ONCALL_API_TOKEN` is set |

How the live feed works: call `watch_events` with no `after_seq` to start
from now. It returns as soon as at least one matching event exists, or after
`wait_s`. Call again with the returned `next_seq`. The cursor always advances
past events that `types` filtered out, so none is read twice.

### 5.2 Approvals group (`approvals`)

All three act as `AKIRA_OPERATOR_ID`. Claude cannot pass a different identity:
no tool has a `decided_by` or `by` parameter.

| Tool | Parameters | What it does | Service and route |
|---|---|---|---|
| `decide_approval` | `approval_id`, `decision` (`approved` or `rejected`) | 1. Reads pending approvals; refuses if this one is not pending. 2. Confirms with the user, showing tool, target, incident and operator. 3. Decides. Approving makes the gateway re-run checklist steps 2-6 and execute the change | gateway `GET /approvals?state=pending`, then `POST /approvals/{id}/decide` `{decision, decided_by, via: "akira-mcp"}` with `X-Oncall-Token` |
| `acknowledge_page` | `incident_id` | Confirms, then acknowledges: re-paging stops and the Discord wake message loses its button and shows "acknowledged by @you via Akira MCP" | notifier `POST /pages/{incident_id}/ack` `{by, via}` with `X-Oncall-Token`. 404 no open page, 403 not an approver, 409 already acknowledged |
| `clear_receipt` | `receipt_id` | After a failed watchdog undo: confirms, then tells the gateway a human checked the cluster, so Akira may act again. A no-op unless the receipt's outcome is `watchdog_failed` | gateway `POST /receipts/{id}/clear` `{decided_by}` with `X-Oncall-Token` |

The gateway still checks everything it always checks: approver allowlist,
pending state, expiry, in-flight budget and checklist steps 2-6. The MCP adds
the confirmation in front; it removes no check.

After a decision from Claude, the gateway's `approval_decided` event carries
`decided_by` and `via: "akira-mcp"`. The notifier closes the Discord approval
message within about 5 s, showing "approved by @you via Akira MCP". A late
click in Discord then answers "already decided".

### 5.3 Chaos group (`chaos`)

Everything goes through the chaos panel, so every fault is logged in
`data/ground_truth.jsonl` and bounded by `config/chaos.yaml` (one lab
experiment at a time, delay up to 120 s, duration 60-900 s, auto cleanup after
1800 s). Every run Claude starts is stored with `origin: "akira-mcp"`, visible
even for blind runs, and on the ground-truth line.

| Tool | Parameters | What it does | Route (`X-Chaos-Token`) |
|---|---|---|---|
| `list_chaos_options` | none | The reviewed config joined with the live cluster: targets, capabilities (`flag:<name>`, `image`, `env:<KEY>`, `scale_zero`), choices, availability and reason, family, tested, limits, current baseline, open runs, flags pending review | `GET /chaos/registry` |
| `preview_chaos` | `target`, `capability`, `choice`, `delay_s` 0-120, `duration_s` 60-900, `decoy` | Dry run: the exact field that would change (`place`, `before`, `after`), problems, journeys hit, target policy. Changes nothing | `POST /chaos/experiments/preview` |
| `create_chaos` | same as preview, plus `blind`, `idempotency_key` | 1. Previews; refuses with the panel's problems if not ok. 2. Confirms, showing the exact fields and journeys. 3. Starts it with an `Idempotency-Key` (a retry never injects twice). If the panel rejects (for example one run already active), returns `started: false` with the reason | `POST /chaos/experiments/preview`, then `POST /chaos/experiments` |
| `draw_random_chaos` | `seed`, `blind` (true), `decoy`, `tested_only` (true) | Confirms, then starts a random valid experiment. Blind by default: Claude does not see what broke until the run ends, so it can test Akira without knowing the answer | `POST /chaos/experiments/draw` |
| `get_chaos_experiments` | `experiment_id` (optional) | The last 20 experiments, or one: status, mutations, origin, times, ended by | `GET /chaos/experiments[/{id}]` |
| `stop_chaos` | `experiment_id` | Restores the fields that run changed (never a later edit by someone else) and watches for recovery | `POST /chaos/experiments/{id}/stop` |
| `reset_shop` | none | Confirms, then restores the healthy snapshot, ends every experiment, and waits for severity 0 held 30 s (up to about 7 min). Sends a progress notification every 10 s | `POST /chaos/reset` (timeout 420 s) |

Deliberately missing: the admin `kubectl` box (cluster-admin shell), ground
truth reads, and `reveal` for blind runs.

<a id="safety"></a>
## 6. Safety model

| Risk | Control |
|---|---|
| Claude approves as someone else | Identity fixed by `AKIRA_OPERATOR_ID` at start; must be in the allowlist; no tool takes an identity |
| Claude acts without a human | Write tools ask a yes/no dialog (MCP elicitation) when the client supports it, and refuse on decline or cancel. Clients without dialogs fall back to their own per-call permission prompt. **Never "always allow" the write tools** |
| A client's dialog is broken | There are public reports of Claude Code auto-declining elicitation in some sessions. The tool then refuses with "nothing was done; approve or acknowledge in Discord instead" |
| Holding the judge's secret by accident | Without the chaos group, `CHAOS_JUDGE_TOKEN` is removed from the process at start |
| Prompt injection through results | Results are redacted; the model's "why" text is dropped when it matches the injection pattern; server instructions and tool descriptions tell Claude that result text is data, not instructions |
| Huge results crowding the context | 60,000-character cap with a note; `limit` parameters on every list |
| Breaking more than intended | Chaos goes only through the panel: reviewed config, preview, one run at a time, idempotency key, automatic cleanup. No raw `kubectl` |
| One session breaks and fixes | With chaos and approvals both on, one Claude session can break the shop and approve its own fix. Those runs carry `origin: akira-mcp`; independent bench scores must leave them out |
| Hidden failures | Every HTTP failure is an MCP error naming the status, route and reason; nothing is swallowed |

<a id="watch"></a>
## 7. Live feed CLI

```sh
uv run --locked --env-file .env python -m akira_mcp watch                 # from now
uv run --locked --env-file .env python -m akira_mcp watch --incident inc-...   # one incident
uv run --locked --env-file .env python -m akira_mcp watch --after 120     # replay from seq 121
```

- Streams the gateway's SSE bus (`GET /events`), one plain line per event:
  `#245 14:02:11  ▲ asked a human in Discord #wake · ...`. Colour only on a TTY.
- On a dropped stream it prints `event stream lost (<Error>); retrying every 5 s`
  once, then resumes from the last seq it printed.
- Made for Claude Code's Monitor tool: every line is flushed, so each event
  arrives as a notification.

<a id="routes"></a>
## 8. Server-side routes added for it

| Service | Route | Notes |
|---|---|---|
| gateway | `GET /incidents?state=&unfinished=&limit=` | open GET; redacted |
| gateway | `GET /incidents/{id}?events_limit=` | incident, approvals, receipts + cards, its bus events, `brain.memory.similar` |
| gateway | `GET /approvals?state=&limit=` | action parsed; `past_expiry` by the gateway clock |
| gateway | `GET /events/log?after=&limit=&incident_id=` | JSON pages of the bus with `next_after` (the SSE stream replays everything and never ends) |
| gateway | `POST /approvals/{id}/decide` | body takes optional `via` (`discord` default, `akira-mcp`) |
| brain | `GET /health` | `{"ok": true}` |
| notifier | `GET /pages` | wake pages + undecided approvals |
| notifier | `POST /pages/{incident_id}/ack` | `X-Oncall-Token`; notifier now has `TokenGuard` on writes |
| chaos | `Spec.origin`, `DrawBody.origin` | `judge` default, `akira-mcp`; stored on the experiment and ground truth |
| schema | `approval_decided` payload | adds optional `decided_by`, `via` |

<a id="tests"></a>
## 9. Live test results

Run on 2026-11-13 against the live stack, through a real stdio session
started from the Claude Desktop config (cwd `/`, the same command Claude
Desktop runs), with `AKIRA_MCP_TOOLSETS=read,chaos,approvals`. The test
client answered every confirm dialog with yes. **All 24 tools passed.**

Offline: `uv run pytest` 677 passed (35 in `tests/test_akira_mcp.py`), ruff
clean, mypy clean on 82 files.

### Read phase (26 calls)

| Tool | Call | Time | Result |
|---|---|---|---|
| `get_akira_status` | - | 25 ms | 5 services up, Prometheus OK, severity 0, Discord ready |
| `get_service_health` | all / `only_unhealthy` | 5 ms | all services; empty unhealthy set |
| `list_incidents` | `limit 5` / `state resolved` / `unfinished` | 5-6 ms | newest first; filters correct; no unfinished |
| `get_incident` | a resolved incident, `events_limit 40` | 18 ms | record, approvals, receipts, one-line timeline |
| `get_incident` | `inc-does-not-exist` | 3 ms | error: `404 ... unknown incident` (expected) |
| `get_incident_report` | `inc-1794580207241` | 8 ms | detect 30.6 s, diagnose 64.3 s, act 101.3 s, finish 201.5 s; revert_config on checkout, prediction held, harm clean |
| `list_receipts` / `get_receipt` | `limit 5` / `#3` | 6-7 ms | cards; full diff and undo |
| `get_trust_table` | - | 4 ms | ledger rows with bound vs bar |
| `verify_audit_log` | - | 12 ms | `ok: true`, 240 records |
| `list_pending_approvals` | - | 5 ms | none pending |
| `list_pages` | - | 4 ms | one escalated incident still re-paging |
| `watch_events` | from now, `wait_s 3` / from seq 0, 3 events | 3017 ms / 5 ms | timed out empty / first 3 events with next cursor |
| `get_runbooks` | `RB-01` / `RB-nope` | 11 / 8 ms | the runbook / error `no runbook RB-nope` (expected) |
| `get_recent_changes` | 120 min | 8 ms | journal rows, values redacted |
| `list_chaos_options` | - | 418 ms | registry, limits, baseline |
| `get_chaos_experiments` | - | 6 ms | last 20 runs |
| `preview_chaos` | payment `flag:paymentFailure` 50% / payment `scale_zero` | 333 / 220 ms | exact field `configmap/flagd-config flags[paymentFailure].defaultVariant` / refused: `payment does not support scale_zero` |

### Live drill (a real incident, start to finish)

| Step | Tool | Result |
|---|---|---|
| 1 | `create_chaos` payment `flag:paymentFailure` 50%, 900 s | Dialog: "Break the shop: configmap/flagd-config flags[paymentFailure].defaultVariant -> 50%. Journeys hit: checkout. Go?" Started `exp-c8c1060f96`, `origin: akira-mcp` (974 ms) |
| 2 | `draw_random_chaos` | Rejected by the panel (one lab run at a time); returned `started: false`, nothing extra broken |
| 3 | `watch_events` (34 calls) | Followed Akira live: incident opened (payment, severity 7), culprit from error traces, rule `recent_change -> revert_config`, model diagnosis, checklist gates passed until the trust gate (`trust bound 0.0 < 0.9`), approval requested |
| 4 | `list_pending_approvals`, `list_pages` | Approval `814e78a364ee`: revert_config on payment, expires in 300 s |
| 5 | `decide_approval` approved | Dialog: "APPROVED Akira's revert_config on payment for incident inc-1794583929102 as operator ...?" Gateway: `executed`, receipt #4 (95 ms). Notifier stored `decided_by` = operator, `via: akira-mcp`, closed the Discord card |
| 6 | `watch_events` | Gates re-run, executed, severity 10 -> 12 -> 8 -> 4 -> 0, harm check clean, `incident resolved · FIXED in 1m 59s: payment errors 53.5% → 0.0%` |
| 7 | `acknowledge_page` | On the older escalated incident still re-paging: `acknowledged ...; paging stopped`, `message_updated: true` (1168 ms) |
| 8 | `get_incident_report` | outcome resolved, detect 30.6 s, diagnose 48.4 s, act 48.9 s, finish 149.1 s from onset; prediction held, harm clean |
| 9 | `clear_receipt` #4 | `cleared: false, receipt is success, nothing to clear` (correct no-op) |
| 10 | `get_chaos_experiments` by id, `stop_chaos` | Run was already `verifying` (Akira's fix detected); stop returned it |
| 11 | `reset_shop` | `restored: ["configmap/flagd-config"], healthy: true` in 30.4 s |
| 12 | `get_service_health` | severity 0 |

Found during the live run: a chaos panel started before this branch refused
the new `origin` field (`422 body.origin: Extra inputs are not permitted`).
Restarting the panel fixed it; the same applies to gateway, brain and notifier.

<a id="limits"></a>
## 10. Known limits and open items

- `reset_shop` can take up to about 7 minutes; some clients may time out the
  call even with progress notifications. The reset still completes on the panel.
- Claude Desktop's support for MCP elicitation (the confirm dialog) is not
  confirmed; there it falls back to the per-call permission prompt.
- Bench scoring does not yet leave out `origin: akira-mcp` runs.
- `get_akira_status` reports a service as down when it answers 404 on
  `/health`: true for a brain started before this branch, which is running but old.
- Pre-existing, not changed: a Discord button click and the notifier's 5 s close
  loop can both edit the same approval card, adding a second "Outcome" line.
- `.env.example` lists `PROMETHEUS_URL` twice (the second is blank).
