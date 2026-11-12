# Muaz [M]: architecture of my part

Plan: `IMPLEMENTATION.md`. Shared contracts and questions:
`team/SHARED_CONTEXT.md`. My progress: `team/muaz/STATE.md`.

## What I own

The agent's core: it notices, diagnoses, acts safely and checks its work.

| Area | Paths | Plan |
|---|---|---|
| Observer (port 7001, identity `oncall-reader`) | `observer/` (`main.py`, `detector.py`, `baselines.py`, `kube_watch.py`, `journal.py`, `flags.py`) | §6.2 |
| Brain (port 7002, identity `oncall-reader`, holds the Claude key) | `brain/` except `redact.py` (`main.py`, `graph.py`, `culprit.py`, `major.py`, `bundle.py`, `rules.py`, `llm.py`, `prompts/`) | §6.3 |
| Gateway (port 7003, MCP + HTTP, the only write identity `oncall-agent`) | `gateway/` except `audit.py`, `receipts.py` (`main.py`, `mcp_server.py`, `checklist.py`, `policy.py`, `dryrun.py`, `blast.py`, `freshness.py`, `trust.py`, `executor.py`, `verifier.py`, `watchdog.py`, `approvals.py`) | §6.4 |
| Kubernetes security | `k8s/rbac-reader.yaml`, `rbac-agent.yaml`, `admission-policy.yaml`, `admission-binding.yaml`, `scripts/make_kubeconfigs.sh` | §3.5, §6.5 |
| Config | `config/policy.yaml`, `config/queries.yaml` | §4.2, §4.3 |
| Data | SQLite `data/oncall.db` tables (§5.1); `schemas/` together with T | §5 |
| Tests | `test_rules.py`, `test_culprit.py`, `tests/test_invariants.py` (Hypothesis) | §8.1, §8.2 |

## Flow through my code

```
Prometheus + K8s watch
  -> observer: detector (breach, sustain, severity) + journal (diff, author, inverse)
  -> POST incident to brain
brain:
  culprit from Jaeger traces -> [major-incident analysis] -> evidence bundle
  -> redact (T) -> rules.match -> one Claude call (explain, predict)
  -> ActionRequest -> gateway over MCP
gateway checklist (first failure decides):
  1 schema  2 hands-off  3 policy  4 dry run + blast + snapshot
  5 net benefit  6 freshness  7 trust gate  8 execute
  -> verifier (prediction, harm check, early abort, auto-undo)
  -> ledger update, receipt + audit (T), events (T)
```

## Hard rules my code must keep

1. The LLM proposes; deterministic code decides (§0.2).
2. The brain never writes to the cluster. The gateway never calls an LLM.
3. Only six tools exist, and only on `actable` services from
   `config/services.yaml`. Protected services always escalate.
4. Every write: agent kubeconfig, `field_manager="oncall-agent"`,
   `resourceVersion` precondition. 409 -> `handed_off`; 403/422 -> `escalated`.
5. Every executed action has a receipt with a non-empty inverse, and every
   decision has an audit entry.
6. The brain and gateway never read `data/ground_truth.jsonl`.
7. Property invariants in §8.2 always hold.

## What I provide to others

| To | What | Contract |
|---|---|---|
| A (UI, smoke), gateway | `GET :7001/health/now`, `GET :7001/journal` | C4 |
| A (UI), T (notifier, bench) | Gateway HTTP `/health`, `/approvals/{id}/decide`, `/ledger` | C5 |
| A, T | Terminal events per incident | C10 |
| T | Incident, diagnosis and receipt data for the card | C9 |

## What I need from others

| From | What | Contract |
|---|---|---|
| A | `config/services.yaml`, VERIFY values, chaos writes with a known field manager | C7, Q4 |
| T | `schemas/`, `schemas/events.py`, event publish + SSE routes | C1, C2, C3 |
| T | `redact()` and injection quarantine | C8 |
| T | `audit.append()`, receipt and card builders | C9 |
