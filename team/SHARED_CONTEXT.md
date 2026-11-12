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
| Jaeger dependencies API path | M | | |
| Jaeger traces API path and error tag query | M | | |
| Helm values keys for replicas, rolling strategy, memory limit, scrape interval | A | `components.<name>.replicas`; `components.<name>.resources.limits.memory`; no chart key for strategy (patched in `scripts/install_shop.sh`); intervals: `opentelemetry-collector.config.connectors.span_metrics.metrics_flush_interval` and env `OTEL_METRIC_EXPORT_INTERVAL` via `default.envOverrides`. See `k8s/values.yaml` | [A] 2026-11-13 |
| Image prefix of shop images (admission policy rule, §6.5.3) | A | `ghcr.io/open-telemetry/demo:3.1.0-<service>` (19 Deployments). Others: `ghcr.io/open-feature/flagd`, `ghcr.io/valkey-io/valkey`, `jaegertracing/jaeger`, `postgres`, `quay.io/prometheus/prometheus`. Bad image `payment:v2-bad` will be local, no registry prefix | [A] 2026-11-13 |
| MCP SDK transport call for local HTTP | M | | |
| Python client JSON Patch content type | M | | |
| Claude model id for `CLAUDE_MODEL` and price per token | M | | |

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

---

## Log (append-only, newest at bottom)

- [plan] 2026-11-12 for all: Team files created: `team/<name>/ARCHITECTURE.md`,
  `TASK.md`, `STATE.md` for muaz, anirudh, twaha. Nothing is built yet; the
  repo holds only `IMPLEMENTATION.md`, `CLAUDE.md`, `README.md`, `LICENSE`.
- [A] 2026-11-13 for M,T: Cluster `oncall` (k3d, context `k3d-oncall`) and shop (chart 0.42.6, release `my-otel-demo`, ns `shop`) run on Anirudh's machine. Rebuild: `scripts/setup_cluster.sh` then `scripts/install_shop.sh`. Service list in `config/services.yaml` (C7). Disabled: opensearch, agent, chatbot, mcp. `payment` and `checkout` have 2 replicas.
