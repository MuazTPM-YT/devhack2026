# Twaha [T]: architecture of my part

Plan: `IMPLEMENTATION.md`. Shared contracts and questions:
`team/SHARED_CONTEXT.md`. My progress: `team/twaha/STATE.md`.

## What I own

The shared language, the record of what happened, the people channel, and
the proof that it works.

| Area | Paths | Plan |
|---|---|---|
| Repo hygiene | `.gitignore` (`.env`, `data/`, `*.kubeconfig`, `node_modules/`), `.env.example`, `AGENTS.md`, dependency manifest + lockfile | §2, Phase 0 |
| Shared schemas (with M) | `schemas/` (`incident.py`, `evidence.py`, `diagnosis.py`, `action.py`, `receipt.py`, `events.py`) | §5.2, §5.3 |
| Event bus | publish + SSE routes in the gateway process (`/events/publish`, `/events`) | §1.3; see Q8 |
| Audit log | `gateway/audit.py`, `data/audit.jsonl`, `scripts/verify_audit.py` | §6.7.2 |
| Receipts + incident card | `gateway/receipts.py` | §6.7.1 |
| Redaction + injection quarantine | `brain/redact.py` | §6.3.5; see Q7 |
| Notifier (port 7005, holds the Discord token) | `notifier/` (`main.py`, `base.py`, `discord_bot.py`) | §6.6 |
| Benchmark | `bench/` (`harness.py`, `manual_baseline.md`, `report.py`), `bench/results.jsonl` | §9 |
| Tests | `test_trust.py`, `test_policy.py`, `test_redact.py`, `test_audit.py`, `tests/redteam/` | §8.1, §8.3 |

## Flow through my parts

```
any process -> POST :7003/events/publish -> audit.append (hash chain) -> SSE :7003/events
                                                                          |-> UI (A)
                                                                          |-> notifier
                                                                          |-> bench, smoke
notifier: approval_requested -> Discord embed + Approve/Reject
          click -> approver check, expiry check -> POST /approvals/{id}/decide (M)
          #oncall-fyi (silent) | #oncall-wake (mention, re-page) | #oncall-tickets
bench:    reset -> wait healthy -> inject (A) -> wait terminal event -> record -> results.jsonl
```

## Hard rules my code must keep

1. Audit hash: SHA-256 over canonical JSON (`sort_keys=True`,
   `separators=(",", ":")`) including `prev_hash`; `verify_audit.py` prints
   the first broken `seq` (§6.7.2).
2. Every string that leaves a process passes `redact()` first, including
   Discord text. Quarantined lines are logged by hash, never by text.
3. The card is built by code, max 5 lines, every claim cites an evidence ID
   (§6.7.1).
4. Notifier checks approver ID and expiry before calling the gateway; the
   gateway checks again. Non-approvers get an ephemeral "not authorised".
5. The bench may read ground truth; nothing it writes may reach the brain
   or gateway, except through an agreed rehearsal path (Q2, Q3).
6. No secrets in code, tests or fixtures. Discord token and approver IDs
   come from `.env`.

## What I provide to others

| To | What | Contract |
|---|---|---|
| all | `schemas/`, event types | C1, C2 |
| all | Event publish + SSE | C3 |
| M | `redact()`, quarantine | C8 |
| M | `audit.append()`, receipt + card builders, `/receipts/{id}` | C9, C5 |
| A | Benchmark results format for `/benchmark` | tell A |

## What I need from others

| From | What | Contract |
|---|---|---|
| M | Gateway process to mount my routes; `/approvals/{id}/decide`; terminal events | C3, C5, C10 |
| M | Incident, diagnosis and receipt data for the card | C9 |
| A | Chaos API with ground-truth timestamp; load generator failure counts | C6 |
