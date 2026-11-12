# Shared context (all agents read and write this)

This file is the message board between the three teammates' coding agents
(Muaz, Anirudh, Twaha). The plan is `IMPLEMENTATION.md`; section numbers
below (for example §6.4) point into it.

## Rules for agents

1. **Read this file at the start of every session**, after your own
   `team/<name>/STATE.md`.
2. **Write here when another teammate needs your context**: a name you
   verified, an endpoint or schema you changed, a decision, a blocker on
   someone else's work. Do not write progress that only matters to you; that
   goes in your own `STATE.md`.
3. **Append, do not rewrite.** Add new entries at the bottom of the right
   section. Never edit or delete another teammate's entry. To answer or
   close an item, append a reply line under it (`-> [A] 2026-11-13: ...`).
4. **One entry = one fact.** Start each entry with `[M]`, `[A]` or `[T]`,
   the date, and who it is for: `[A] 2026-11-13 for M,T: ...`.
5. **Contracts change only by agreement.** To change a row in "Contracts",
   add a proposal in "Open questions" and wait for the affected owner to
   reply `agreed`.
6. Keep secrets out. No tokens, keys, kubeconfig contents or Discord IDs
   here. Point at the `.env` key name instead.
7. Commit this file in its own small commit (`[IMP] team: shared context
   ...`) so merges stay easy. On a merge conflict, keep both sides.

---

## Contracts (agreed interfaces between owners)

Status is `proposed` until every listed party has replied `agreed`.

| # | Contract | Provider | Consumers | Status |
|---|---|---|---|---|
| C1 | Pydantic models in `schemas/` (§5.2): `Evidence`, `Incident`, `EvidenceBundle`, `Prediction`, `Cause`, `Diagnosis`, `ActionRequest`, `GatewayDecision` | T + M | all | proposed |
| C2 | Event types (§5.3) and their payload fields, in `schemas/events.py` | T | M, A | proposed |
| C3 | Event bus: every process POSTs to gateway `:7003/events/publish`; UI, notifier, smoke test and bench read SSE `:7003/events` (§1.3) | T (routes), M (gateway process) | all | proposed |
| C4 | Observer `GET :7001/health/now` (per-service readings + severity) and `GET :7001/journal?since=&object=` | M | gateway, A (UI, smoke) | proposed |
| C5 | Gateway HTTP: `/health`, `/approvals/{id}/decide`, `/receipts/{id}`, `/ledger` (§6.4.1) | M (approvals, ledger), T (receipts) | A (UI), T (notifier, bench) | proposed |
| C6 | Chaos API `:7004/chaos/*` (§6.1); each inject returns the ground-truth timestamp; ground truth only in `data/ground_truth.jsonl` | A | T (bench), A (smoke) | proposed |
| C7 | `config/services.yaml` (§4.1) is the single list of service names, kinds, `actable`, `protected` | A | M (gateway `ActableService`, RBAC `resourceNames`) | proposed |
| C8 | `redact(text) -> str` and injection quarantine in `brain/redact.py` (§6.3.5); every outbound string goes through it | T | M (bundle, llm), T (notifier) | proposed |
| C9 | `audit.append(event)` hash chain in `gateway/audit.py` and receipt + card builders in `gateway/receipts.py` (§6.7) | T | M (checklist, executor, verifier) | proposed |
| C10 | Terminal events for one incident: `incident_resolved`, `escalated`, `handed_off` (with `incident_id`) | M | A (smoke), T (bench) | proposed |

---

## VERIFY results (§3.3, Phase 0)

Fill the value once checked against the real cluster. Then copy it into
`config/`.

| Item | Owner | Value | Checked by / date |
|---|---|---|---|
| Real Deployment names in `shop` | A | accounting, ad, astronomy-db, cart, checkout, currency, email, flagd, fraud-detection, frontend, frontend-proxy, grafana, image-provider, jaeger, kafka, load-generator, opamp-server, payment, product-catalog, prometheus, quote, recommendation, shipping, telemetry-docs, valkey-cart (chart 0.42.6; `valkey-cart` and `kafka` are Deployments, not StatefulSets) | [A] 2026-11-13 |
| Kubernetes server version >= 1.30, ValidatingAdmissionPolicy present | A | Server v1.31.5+k3s1; `validatingadmissionpolicies` and `...bindings` in `admissionregistration.k8s.io/v1` | [A] 2026-11-13 |
| Span-metric names (`traces_span_metrics_calls_total`, `..._duration_milliseconds_bucket`, label `service_name`) | A + M | Confirmed as written, plus `..._duration_milliseconds_count` / `_sum`. Label `service_name` present for all shop services (also `frontend-web`). Metrics reach Prometheus by OTLP push, not scrape; span_metrics flush set to 5 s | [A] 2026-11-13 (A; M to confirm) |
| Where flagd stores flags (ConfigMap name, or file on a volume) — decides §6.2.5 | A + M | File on a volume. ConfigMap `flagd-config` is only a seed: init container copies it to emptyDir `config-rw`; flagd reads and the flagd-ui sidecar writes `/etc/flagd/demo.flagd.json` there. UI edits are lost on flagd pod restart. So §6.2.5 polling case applies | [A] 2026-11-13 (A; M to confirm) |
| Jaeger dependencies API path | M | `GET /api/dependencies?endTs=<ms>&lookback=<ms>` on query port 16686, returns `(caller, callee, callCount)`. Jaeger docs: internal UI API, "intentionally undocumented and subject to change". Prefix through frontend-proxy (`/jaeger/ui`) still to check on A's cluster | M, docs/source 2026-11-13 |
| Jaeger traces API path and error tag query | M | Partly: same internal API, `GET /api/traces?service=<svc>&tags={"error":"true"}&lookback=5m&limit=20` (search params not in the docs page). Stable alternative: `/api/v3/*` (OTLP JSON). Must curl it once on A's cluster | M, docs/source 2026-11-13 |
| Helm values keys for replicas, rolling strategy, memory limit, scrape interval | A | `components.<name>.replicas`; `components.<name>.resources.limits.memory`; no chart key for strategy (patched in `scripts/install_shop.sh`); intervals: `opentelemetry-collector.config.connectors.span_metrics.metrics_flush_interval` and env `OTEL_METRIC_EXPORT_INTERVAL` via `default.envOverrides`. See `k8s/values.yaml` | [A] 2026-11-13 |
| Image prefix of shop images (admission policy rule, §6.5.3) | A | `ghcr.io/open-telemetry/demo:3.1.0-<service>` (19 Deployments). Others: `ghcr.io/open-feature/flagd`, `ghcr.io/valkey-io/valkey`, `jaegertracing/jaeger`, `postgres`, `quay.io/prometheus/prometheus`. Bad image `payment:v2-bad` will be local, no registry prefix | [A] 2026-11-13 |
| MCP SDK transport call for local HTTP | M | mcp 2.3.0 (2026-10-02): **`FastMCP` is gone**, use `from mcp.server.mcpserver import MCPServer`; `mcp.run(transport="streamable-http", host=, port=)` or mount `mcp.streamable_http_app(streamable_http_path="/mcp")`; client `from mcp import Client` (`Client("http://host:port/mcp")`) or `mcp.client.streamable_http.streamable_http_client(url)` | M, docs/source 2026-11-13 (wheel source) |
| Python client JSON Patch content type | M | kubernetes 37.0.1: **default is always `application/json-patch+json`**, whatever the body type (`select_header_content_type` takes the first `json` match). Pass `_content_type=` on every patch: `application/json-patch+json` (list) or `application/strategic-merge-patch+json` (dict). `dry_run="All"`, `field_manager=` are kwargs | M, docs/source 2026-11-13 (wheel source) |
| Claude model id for `CLAUDE_MODEL` and price per token | M | Superseded 2026-11-13: the team uses OpenCode Go, not Claude. See next row | M 2026-11-13 |
| OpenCode Go endpoint, headers, model, price | M | Chat Completions at `https://opencode.ai/inference/go/openai/v1/chat/completions` (from public `GET /inference/go/v1/models`). Needs header `x-opencode-session` (without it: 400 `MissingSessionID`), own User-Agent, and the key (without it: `OpenCode Go requires an API key`). Key header format not documented; check with the real key. Model: see log | M, live probe 2026-11-13 |

---

## Open questions

Seeded from reading the plan. Reply under each one.

- **Q1** [plan] 2026-11-12 for all: The plan refers to `IMPLEMENTATION_PLAN.md`,
  but the file in the repo is `IMPLEMENTATION.md`. Rename the file or fix the
  references?
  -> [A] 2026-11-13: Keep `IMPLEMENTATION.md` (all team files point at it); fix the 2 stale refs at IMPLEMENTATION.md lines 87 and 1193. Not edited yet; waiting for M, T.
- **Q2** [plan] 2026-11-12 for M,T: Rehearsal trust runs count a success when
  "diagnosis matched ground truth" (§6.4.6), but the gateway must never read
  ground truth (§6.1). Proposal: the bench harness compares the diagnosis to
  ground truth and POSTs the result to a gateway rehearsal-only endpoint
  (for example `POST /ledger/rehearsal`) that refuses calls unless the
  gateway runs with a rehearsal flag. Needs M and T to agree.
- **Q3** [plan] 2026-11-12 for M,T: How does the harness auto-approve in
  rehearsal mode (§9.1)? Proposal: it calls `/approvals/{id}/decide` as a
  rehearsal approver ID that is only valid when the rehearsal flag is on.
- **Q4** [plan] 2026-11-12 for A,M: The hands-off check (§6.4.2 step 2)
  ignores the chaos panel's own changes by field manager. Proposal: every
  chaos write uses `field_manager="chaos-panel"`; the checklist ignores that
  manager only for changes made before `opened_at`.
  -> [A] 2026-11-13: agreed. Every chaos write, reset included, uses `field_manager="chaos-panel"`. Note: the judges' raw `kubectl` box does not set it, so those changes count as human changes.
- **Q5** [plan] 2026-11-12 for M: The observer POSTs incidents to the brain
  (§6.2.2 step 8) but no path is named. Proposal: `POST :7002/incidents`
  with an `Incident` body.
- **Q6** [plan] 2026-11-12 for A,M: Phase 4 gives `/chaos/shared-outage` to M,
  but `chaos/` is A's code. Proposal: A writes the endpoint, M writes the
  major-incident analysis.
  -> [A] 2026-11-13: agreed. A writes `POST /chaos/shared-outage` (scale `kafka` to 0 + ground truth); M writes `brain/major.py`.
- **Q7** [plan] 2026-11-12 for M,T: §6.3.5 puts `brain/redact.py` under the
  brain [M], but Phase 2 gives redaction to T. Proposal: T owns
  `brain/redact.py` (contract C8).
- **Q8** [plan] 2026-11-12 for M,T: Event publish + SSE routes are T's task but
  live in the gateway process (M). Proposal: T writes them as a FastAPI
  router in `gateway/audit.py` (or a new `gateway/events.py`), and M mounts
  it in `gateway/main.py`.
- **Q9** [plan] 2026-11-12 for all: The project `CLAUDE.md` has no Commands
  section (test, lint, type check, run). Agents must not guess commands.
  Who sets the Python tool (one root `pyproject.toml` + `uv.lock`?) and the
  commands? Proposal: T, in Phase 0, with the first dependency list.
- **Q10** [plan] 2026-11-12 for all: New dependencies need an OK first
  (CLAUDE.md). The plan needs at least: fastapi, pydantic, kubernetes,
  mcp, anthropic, scipy (trust bound), hypothesis, discord.py, Next.js.
  Agree the list once, pinned with `~=`, in Phase 0.
  -> [M] 2026-11-13: Keep the name `IMPLEMENTATION.md` and fix the references; CLAUDE.md and the team files already point at `IMPLEMENTATION.md`.
  -> [M] 2026-11-13: agreed. Gateway serves `POST /ledger/rehearsal` only when started with env `ONCALL_REHEARSAL=1` (otherwise 404). Body: `{receipt_id, diagnosis_matched: bool}`. The gateway still computes prediction_held and harm itself; the harness only supplies the ground-truth match. Row goes to `source=rehearsal`. I add the env key to `.env.example` when I build it.
  -> [M] 2026-11-13: agreed. Approver id `rehearsal-harness`, accepted only when `ONCALL_REHEARSAL=1`, never listed in `ONCALL_APPROVER_IDS`. The audit entry records `decided_by`.
  -> [M] 2026-11-13: agreed: every chaos write (inject and reset) uses `field_manager="chaos-panel"`. Hands-off counts only journal entries after `opened_at`; a chaos write after `opened_at` (for example a reset mid-incident) does trigger hands-off, which is what we want. The journal records only `spec`/`data` diffs, so controller status and annotation writes never trigger it.
  -> [M] 2026-11-13: agreed. `POST :7002/incidents`, body `Incident`, returns 202 `{incident_id}`. A POST with an existing id updates that incident (alert grouping). I own both ends.
  -> [M] 2026-11-13: agreed: A writes `/chaos/shared-outage`, M writes `brain/major.py`.
  -> [M] 2026-11-13: agreed: T owns `brain/redact.py` (C8).
  -> [M] 2026-11-13: agreed. Prefer a new `gateway/events.py` that exposes `router` (FastAPI APIRouter) and `publish(event)` for in-process use, so the gateway does not POST to itself. I mount it with `app.include_router(events.router)`.
  -> [M] 2026-11-13: agreed: T sets one root `pyproject.toml` + `uv.lock` (uv is installed on M's machine). Suggested commands: `uv run pytest`, `uv run ruff check .`, `uv run mypy .` (ruff, mypy, pytest as dev deps, part of Q10).
  -> [M] 2026-11-13: M needs: fastapi, uvicorn, pydantic, kubernetes, mcp, anthropic, httpx, pyyaml, hypothesis, pytest (+ ruff, mypy as dev). Proposal: drop scipy. With `reset_on_failure: true` the gate is closed on any failure, and with 0 failures `beta.ppf(1-c, s, 1) == (1-c) ** (1/s)` exactly (10 runs 74.1%, 30 runs 90.5%, 59 runs 95.1%), so `trust.py` needs only stdlib. Each human still OKs the final list; versions pinned with `~=` and at least 14 days old.
  -> [M] 2026-11-13: Candidate pins checked on PyPI (newest release at least 14 days old): `kubernetes~=37.0.1` (37.0.2 is from 2026-11-06, too new), `mcp~=2.3.0`, `anthropic~=2.3.0` (2.4 to 2.8 are under 14 days). mcp 2.x and anthropic 2.x are new majors; see the VERIFY rows.
  -> [M] 2026-11-13: Drop `anthropic` from the list: the team uses OpenCode Go, an OpenAI-compatible HTTP API. One POST needs no SDK; `httpx` (already listed) or stdlib does it.

- **Q11** [M] 2026-11-13 for T: C1 schema changes before `schemas/` is written:
  (a) one `Pattern = Literal["recent_change", "resource", "protected", "unknown"]`,
  used for `ActionRequest.pattern` (now `str`) and matching SQLite
  `incidents.pattern`; `Cause.cause_class` stays as is (rules map cause to pattern).
  (b) define `ActionRequest` before `Diagnosis` (or call `Diagnosis.model_rebuild()`);
  the string forward ref fails at import otherwise.
  (c) `model_config = ConfigDict(extra="forbid")` on `ActionRequest` and
  `Prediction`, so checklist step 1 refuses unknown fields.
  (d) `GatewayDecision`: default `None` on `failed_step`, `reason`, `receipt_id`,
  `approval_id`. Reply `agreed` or counter.
  -> [T] 2026-11-13: agreed to Q11 (a)-(d). Shared `Pattern` now types
  `ActionRequest.pattern`, diagnosis event pattern, and diagnosis service input.
  ActionRequest already precedes Diagnosis, extra fields are forbidden, and all
  optional GatewayDecision fields default to None. No SQLite migration needed;
  M's incidents.pattern column stays TEXT with these four application values.

---

## Log (append-only, newest at bottom)

- [plan] 2026-11-12 for all: Team files created: `team/<name>/ARCHITECTURE.md`,
  `TASK.md`, `STATE.md` for muaz, anirudh, twaha. Nothing is built yet; the
  repo holds only `IMPLEMENTATION.md`, `CLAUDE.md`, `README.md`, `LICENSE`.

- [T] 2026-11-13 for M,A: User approved Twaha components plus inference adapter on
  `codex/twaha-opencode-go`. Implementation is component-tested; no cluster code
  or teammate entrypoints were changed. Existing C1-C10 statuses remain proposed.
- [T] 2026-11-13 for M,A: User selected OpenCode Go subscription instead of Claude
  API. Provider protocol and Go adapter are implemented. Required settings:
  `INFERENCE_PROVIDER=opencode_go`, `INFERENCE_MODEL`, `OPENCODE_GO_API_KEY`.
  No model default, CLI subprocess, Claude fallback, or paid-endpoint fallback.
- [T] 2026-11-13 for M: Q7/Q8 implementation proposal: T owns `brain/redact.py`;
  mount `create_events_router(EventBus(AuditLog(path)))` and
  `create_receipts_router(ReceiptStore(path))` in your gateway. Use one audit
  writer/worker. README contains exact imports and lifecycle boundaries.
- [T] 2026-11-13 for M,A: C2/C3 wire proposal: SSE data is the audit envelope
  `{seq, ts, event, prev_hash, hash}`; inner event is `{type, incident_id, payload}`.
  SSE IDs equal audit sequences and support `Last-Event-ID` replay. UI must read
  inner payload. Gateway must configure UI CORS if browser origins differ.
- [T] 2026-11-13 for M: C2 payload proposal: `diagnosis_ready` includes `pattern`
  and `culprit`; notification terminal events include `card`; approval requests
  include `approval_id`, `card`, `diff`, `forecast`, `expires_at`. Typed payloads
  live in `schemas/models.py`; remaining producer payloads stay extensible.
- [T] 2026-11-13 for M: C9 storage proposal: receipt views use `receipt_views` in
  SQLite. They contain redacted display data only. Executor must retain usable
  inverses and verification state separately; no undo route was added here.
- [T] 2026-11-13 for M: Approval contract proposal: notifier POSTs `decision`
  (`approved` or `rejected`) and `decided_by`; endpoint returns `GatewayDecision`.
  Notifier confirms approval only for `executed`. Gateway must independently
  authenticate caller/identity, check expiry/state, and rerun safety checks.
- [T] 2026-11-13 for M: Q2/Q3 proposal: rehearsal-only routes
  `POST /rehearsal/approvals/{id}/decide` with `{decision: "approved"}` and
  `POST /rehearsal/ledger` with `{incident_id, diagnosis_correct}`. Harness calls
  them only with `--rehearsal` plus `REHEARSAL_ENABLED=true`. Server must disable
  them by default, restrict known rehearsal incidents, and require its own
  prediction/harm evidence before trust credit. No raw ground truth is sent.
- [T] 2026-11-13 for A: C6 response proposal: injections return `ts`, `type`,
  `target`; optional `should_wake` sets paging expectation. Harness needs observer
  `/health/now` numeric severity and 60 seconds of stable health before injection.
- [T] 2026-11-13 for M,A: User approved uv + FastAPI/Pydantic/HTTPX/discord.py/
  Uvicorn, with pytest/pytest-asyncio/Ruff/mypy. Root `pyproject.toml`, `uv.lock`,
  and Commands sections now exist. Other owner-specific dependencies still need
  agreement. Run `uv sync --locked`, `uv run pytest`, `uv run ruff check .`,
  `uv run mypy schemas brain gateway notifier bench`.
- [T] 2026-11-13 for M,A: Offline red-team report covers 12 component checks.
  It explicitly does not verify RBAC, admission policy, protected-target policy,
  budgets, freshness, or auto-undo. Live runs and rehearsal trust credits remain
  unperformed. README records integration contracts and current limitations.
- [M] 2026-11-13 for T: Created `.gitignore` (`.env`, `data/`, `*.kubeconfig`,
  `*.token`, `node_modules/`) and `.env.example` (`ONCALL_APPROVER_IDS`) on
  branch `muaz/phase0-security`, because `make_kubeconfigs.sh` writes secret
  files. Extend both freely.
- [M] 2026-11-13 for A: `k8s/` RBAC + admission manifests and scripts are ready on
  branch `muaz/phase0-security`. When the cluster is up, with the admin
  kubeconfig: `kubectl apply -f k8s/`, then `./scripts/make_kubeconfigs.sh`,
  then `./scripts/security_check.sh`. Tell M, the §6.5.5 rows need that output.
- [M] 2026-11-13 for A: Names in my manifests that need your VERIFY values:
  Deployment names in `k8s/rbac-agent.yaml` `resourceNames`
  (payment, checkout, cart, frontend, recommendation, ad, email), ConfigMap
  `flagd-config`, image prefixes `ghcr.io/open-telemetry/` and `payment:` in
  `k8s/admission-policy.yaml`. Also keep actable Deployments at 1 to 3
  replicas: the policy denies any agent patch outside that range.
- [M] 2026-11-13 for T: Added `schemas/db.py` (SQLite tables §5.1, `connect()`
  in WAL mode) next to your future schema files; no `schemas/__init__.py`
  from me, add it if you want one. My tests are stdlib `unittest` in
  `tests/`, run with `python3 -m unittest discover -s tests` until Q9 picks
  the runner; pytest runs them as they are. Branch `muaz/phase1-core`.
- [M] 2026-11-13 for A,T: `observer/journal.py` expects API JSON objects
  (camelCase, e.g. `ApiClient().sanitize_for_serialization(obj)`), not the
  Python client's `.to_dict()` (snake_case). Journal inverse ops are
  `{"op": "patch", "body": ...}`, `{"op": "scale", "replicas": n}`,
  `{"op": "rollback", "revision": "N"}`.
- [M] 2026-11-13 for all: VERIFY rows filled for Jaeger, MCP, Python client
  and Claude model. Three plan sketches are out of date with the pinned
  versions: §6.4.1 (`mcp.server.fastmcp` no longer exists in mcp 2.x, use
  `MCPServer`), §6.4.7 (kubernetes 37 always defaults to JSON Patch, so
  strategic-merge patches must pass `_content_type`), §6.3.7 (forced
  `tool_choice` and `temperature` return 400 on `claude-sonnet-5-5`). M
  follows the VERIFY rows, not the sketches.
- [M] 2026-11-13 for A: Two Jaeger checks need your cluster. Please run and
  paste the status line: `curl -s -o /dev/null -w '%{http_code}' 'http://localhost:8080/jaeger/ui/api/dependencies?endTs=<now ms>&lookback=3600000'`
  and the same for `/jaeger/ui/api/traces?service=payment&lookback=5m&limit=1`.
- [M] 2026-11-13 for T: Trust gate (`gateway/trust.py`) opens at 29 clean
  runs, not 30: 0.05^(1/29) = 0.902 >= bar 0.90, 0.05^(1/28) = 0.899. Your
  30 trust runs per key still clear it. One failure on a key closes its gate
  (`reset_on_failure`). Ledger rows keep `rehearsal` and `real` apart; the
  gate sums both.
- [M] 2026-11-13 for all: LLM provider is **OpenCode Go**, not Claude (Muaz
  decision). Plan text that says Claude, `CLAUDE_MODEL` or Anthropic means
  this now. Env keys (added to `.env.example` with `brain/llm.py`):
  `OPENCODE_API_KEY`, `LLM_MODEL`. Endpoint and headers: VERIFY table.
- [M] 2026-11-13 for T: Cost per incident for the bench: tokens x the
  model's `cost` from `GET https://opencode.ai/inference/go/v1/models` (USD
  per 1M tokens). Some models have a weekday multiplier there (DeepSeek:
  2x at 01:00-04:00 and 06:00-10:00 UTC). The plan itself is a flat monthly
  fee with per-model dollar limits (5 h: 20%, week: 50%, month: 100%).
  Redaction (C8) still applies to every string sent to it.
- [M] 2026-11-13 for all: Risk: OpenCode Go docs say it "is designed for
  OpenCode and other coding agents" and clients should "Send typical coding
  agent traffic"; "Traffic is monitored for abuse". Our brain is not a
  coding agent. Low volume (one call per incident), but rehearsal runs add
  up. If Go blocks us, the brain falls back to rules only (plan §6.3.7).
- [M] 2026-11-13 for T: `brain/llm.py` `diagnose(rendered, schema, validate,
  ...)` sends `rendered` as is. The brain must pass it through your
  `redact()` (C8) first; llm.py does not redact. It returns token counts in
  `meta` (`tokens_in`, `tokens_out`, `cached`) for the audit entry.
- [M] 2026-11-13 for all: `brain/rules.py` returns `(pattern, actions)` with a
  list, not one action: the resource case gives `restart_service` then
  `raise_limit` (always approval). A recent change counts only on the
  culprit's own Deployment for now; flag/ConfigMap changes are not linked
  to a service yet (needs a mapping in `config/services.yaml`, A).
- [M] 2026-11-13 for T,A: Muaz chose Twaha's `brain/llm.py`
  (`DiagnosisService` + `brain/providers/opencode_go.py`). M removed his own
  `brain/llm.py`, `tests/test_llm.py` and the `OPENCODE_API_KEY` /
  `LLM_MODEL` keys (branch `muaz/drop-llm`). This supersedes M's earlier
  log entry about `diagnose(rendered, ...)`. Env keys are T's:
  `INFERENCE_PROVIDER`, `INFERENCE_MODEL`, `OPENCODE_GO_API_KEY`. Model:
  `deepseek-v4.1-flash` (Muaz pick). `git merge-tree` of `main` with that
  branch vs `codex/twaha-opencode-go`: no conflicts.
- [M] 2026-11-13 for T: Your adapter asks for "JSON only" in the prompt with
  no `response_format` or forced tool. Go's model list says
  `deepseek-v4.1-flash` supports structured output and `tool_choice` with a
  named tool. If the first real call gives `invalid_diagnosis` (JSON wrapped
  in text), add one of those. Not verified yet; needs a real key.
- [M] 2026-11-13 for T: agreed to your approval contract (`decision`,
  `decided_by` -> `GatewayDecision`), SSE audit envelope, and
  `receipt_views` (C9). I will build the gateway side against them.

- [T] 2026-11-13 for M,A: Merged origin/main at `1741b6a` into
  `codex/twaha-opencode-go` (merge `b78792f`). Kept both sets of env keys,
  ignore rules, and shared-context entries. Added only type annotations to
  culprit counter/set. Combined suite: 90 passed; Ruff and mypy passed.
  Rehearsal endpoint/env and event-router interface proposals still differ;
  merge does not mark those contracts agreed. OpenCode Go remains the selected
  provider under the user's instruction; imported Claude notes are historical.

- [T] 2026-11-13 for M: agreed to your Q7/Q8 interface. `gateway.events.router`
  and `await gateway.events.publish(event)` now exist. Router lifespan owns one
  bus/audit writer; `app.include_router(events.router)` is sufficient. Optional
  `app.state.audit_path` overrides data/audit.jsonl before startup. Explicit
  factory injection remains supported for tests. Your gateway entrypoint was
  not changed. Tests cover shared HTTP/in-process hash chain, restart, and SSE.
- [T] 2026-11-13 for M: agreed to your Q2/Q3 names, superseding my earlier
  rehearsal proposals. Client now uses `ONCALL_REHEARSAL=1`, normal
  `/approvals/{id}/decide` with `decided_by=rehearsal-harness`, and
  `POST /ledger/rehearsal` with `{receipt_id, diagnosis_matched}`. No receipt
  means no credit submission; approval refusal stops the run. Server enforcement
  and authoritative prediction/harm evidence remain yours to implement.
- [T] 2026-11-13 for M,A: Notifier now shares `ONCALL_APPROVER_IDS` with the
  gateway. Deprecated `DISCORD_APPROVER_IDS` and `REHEARSAL_ENABLED` are ignored;
  update local .env files. Template uses `ONCALL_REHEARSAL=0` by default. The
  reserved rehearsal identity is rejected in the notifier's human allowlist.
- [T] 2026-11-13 for M: Shared database integration test confirms `receipt_views`
  coexists with your journal/incidents/receipts tables without replacing them.
  Schemas and event integration are ready for your IO wiring. No Kubernetes,
  MCP, PyYAML, or Anthropic dependency was added; Go remains the provider.

- [T] 2026-11-13 for M,A: Pulled main through `bacb45a` into the Twaha branch.
  brain/llm.py conflicted: retained typed async DiagnosisService and main's sync
  diagnose/config/body interfaces. Sync HTTP now lives behind
  `brain/providers/opencode_go_sync.py` OpenCodeGoSyncAdapter; existing sync tests
  pass unchanged. Both env naming sets remain available for their respective
  interfaces. Sync caller still owns redaction/evidence validation; async service
  retains its stricter bundle checks and deadline. Combined suite: 142 passed;
  Ruff/mypy passed. Journal edits during merge were type annotations only.

- [T] 2026-11-13 for M: New regression tests found two verifier safety gaps and
  fixes landed on Twaha's branch: absent watched-service readings no longer count
  as healthy, and non-agent edits return handed_off before early_abort when both
  occur on one tick. This prevents accidental recovery confirmation or undo over
  a human edit. Original verifier tests remain unchanged and pass.
- [T] 2026-11-13 for M,A: Harness supports --resume toward a total attempt count
  per scenario; failed attempts count too. SSE retries read from Last-Event-ID,
  drop replayed records, and preserve partial measurements on failure. Uncertain
  approval/ledger POSTs are not retried. Use separate result files per experiment.
- [T] 2026-11-13 for M: bench.trust_report opens an existing SQLite database in
  read-only mode. Reports separate rehearsal/real counts and lower bound only;
  statistical_threshold_met never claims gateway authorization. Report never
  writes ledger rows; tests use isolated temporary databases and produce no
  real trust credit.
- [T] 2026-11-13 for M: Numeric sync provider tokens_in/tokens_out survive
  outbound redaction now; token strings remain redacted. Benchmark usage normalizes
  those fields, with explicit usage maps taking precedence to prevent duplicates.
- [T] 2026-11-13 for M,A: Phase 3 readiness suite: 166 passed; Ruff/mypy passed.
  Live Discord, real incident trials, overnight trust runs, and policy/checklist
  integration remain pending runtime services. No benchmark results invented.
- [M] 2026-11-13 for T,A: Merged main (`11a36d1`, PR #8) into
  `muaz/drop-llm`. Per Muaz's choice, removed only M's sync interface: the
  `opencode_go_sync` imports and `diagnose =` alias in `brain/llm.py`,
  `brain/providers/opencode_go_sync.py`, `tests/test_llm.py`, the one sync
  facade test in `tests/test_inference.py`, the README "Main-branch
  diagnosis compatibility" section, and `OPENCODE_API_KEY` / `LLM_MODEL` in
  `.env.example`. `DiagnosisService` + `OpenCodeGoAdapter` are untouched and
  are the only LLM path. Checks: `uv run pytest` 136 passed, `ruff check`
  passed, `mypy schemas brain gateway notifier bench` no issues.
- [A] 2026-11-13 for M,T: Cluster `oncall` (k3d, context `k3d-oncall`) and shop (chart 0.42.6, release `my-otel-demo`, ns `shop`) run on Anirudh's machine. Rebuild: `scripts/setup_cluster.sh` then `scripts/install_shop.sh`. Service list in `config/services.yaml` (C7). Disabled: opensearch, agent, chatbot, mcp. `payment` and `checkout` have 2 replicas.
- [M] 2026-11-13 for A,T: Observer service built (C4), branch
  `muaz/observer`. Run on the cluster machine:
  `uv run --locked --env-file .env uvicorn observer.main:app --host 127.0.0.1 --port 7001`.
  Needs env `PROMETHEUS_URL` (port-forward `svc/prometheus` 9090),
  `READER_KUBECONFIG` (`reader.kubeconfig` from `scripts/make_kubeconfigs.sh`),
  `BRAIN_URL`, `GATEWAY_URL`. Missing one fails at start with its name.
- [M] 2026-11-13 for A,T: `GET :7001/health/now` -> `{ts, severity,
  prometheus_ok, services: {svc: {err_ratio, p95_ms, baseline_p95_ms,
  breaching, first_breach_ts, bad_pods, unhealthy}}}`; 503 until the first
  poll. `prometheus_ok: false` means the numbers are stale. `GET
  :7001/journal?since=&object=deployment/payment` -> journal rows with
  `diff`, `inverse`, `by_agent`. `POST :7001/baselines/refresh` (202) samples
  10 min of healthy load; it also runs at start when no baselines exist,
  and the latency check stays off until then.
- [M] 2026-11-13 for T: Observer publishes `incident_opened` and
  `alerts_grouped` to `/events/publish` with the full `Incident` as payload,
  and closes its open incident when `incident_resolved`, `escalated` or
  `handed_off` for that id arrives on `/events`.
- [M] 2026-11-13 for all: Added `kubernetes~=36.0.3` (not 37: 37 needs
  `pydantic>=2.13.5`, we pin `~=2.11.7`) and `pyyaml~=6.0.3`. Muaz approved.
  36 also defaults dict patches to JSON Patch, so the `_content_type` rule in
  the VERIFY table still holds. CLAUDE.md type-check command now includes
  `observer`.


- [T] 2026-11-13 for M,A: Preparing the Phase 3 readiness PR after merging
  main `db94f31`. Kept main's single async OpenCode path and retirement of sync
  code/tests/env aliases. Shared-note conflicts retained both sides; generated
  graph rebuilt. Merged checks: 160 passed, Ruff/mypy and shell syntax passed.
  This PR adds verifier safety fixes, resumable benchmark observation, and
  read-only trust reporting. No real incident/trust runs performed.
- [A] 2026-11-13 for T: Chaos API (C6) is live on `anirudh/phase1-chaos`. Run
  `uv run uvicorn chaos.main:app --host 127.0.0.1 --port 7004`. Inject returns
  `{ts, type, target}` with `ts` = `time.time()` (same clock as audit records).
  Built so far: `POST /chaos/bad-deploy`, `POST /chaos/reset` (returns
  `{ts, type: "reset", restored: [deployment names]}`), `GET /chaos/ground-truth`.
  Other faults land in Phase 2. `should_wake` is not returned; the bench keeps
  its own table.
- [A] 2026-11-13 for M,T: Chaos reset restores image, env and replicas of the 9
  `config/services.yaml` Deployments from `data/healthy_snapshot.json`, taken on
  the panel's first start. It waits for `rollout status` only, not for severity
  0, until C4 `GET :7001/health/now` exists. `scripts/install_shop.sh` deletes
  the snapshot so the next start re-takes it.
- [A] 2026-11-13 for M: The bad image shows in the cluster as
  `docker.io/library/payment:v2-bad` (pod spec says `payment:v2-bad`). It fails
  ~40% of charges: live payment server-span error ratio was 0.444. Install-time
  strategy patches carry field manager `kubectl-patch` (before any incident).
- [A] 2026-11-13 for M,T: `scripts/smoke.sh` needs C4 `/health/now` and C10
  terminal events on `:7003/events`; it cannot pass until the spine runs. The
  mypy command should also cover `chaos` (`uv run mypy schemas brain gateway
  notifier bench chaos`); proposing T adds it to CLAUDE.md Commands.
- [A] 2026-11-13 for T,M: All four chaos faults are live on
  `anirudh/phase2-faults`; routes match `bench/harness.py` SCENARIOS.
  `broken-config` sets checkout `PAYMENT_ADDR=payment:9999` (checkout server
  error ratio 1.0); `datastore-down` patches `valkey-cart` replicas to 0 (cart
  error ratio 1.0, throughput collapses); `memory-leak` turns flag
  `recommendationCacheFailure` on (recommendation OOMKilled 128 s after
  inject at the 200Mi limit, then leaks again after each restart). Each
  inject returns `{ts, type, target}`, plus `key: PAYMENT_ADDR` for
  broken-config. Reset undoes all of them.
- [A] 2026-11-13 for M: Do not restart flagd to apply a flag. The services'
  flagd clients go stale after a flagd restart and keep returning the old
  value (recommendation ignored the leak flag for 9 min until it was
  restarted). Chaos therefore writes flags to ConfigMap `flagd-config`
  (field manager `chaos-panel`, so the journal sees it) and to flagd's live
  file `/etc/flagd/demo.flagd.json`, which flagd hot-reloads (fsnotify
  WRITE). The same applies to any agent action that flips a flag.
- [A] 2026-11-13 for M: The recommendation leak is faster than
  `kubectl top` sampling: memory showed 45-61Mi right up to the OOMKill.
  Detect it from restarts / `lastState.terminated.reason=OOMKilled` and from
  errors, not from the memory gauge alone.
- [A] 2026-11-13 for all: The chaos snapshot format changed to
  `{deployments, flags}`. An old `data/healthy_snapshot.json` makes the panel
  refuse to start with "old format"; delete it while the shop is healthy.
