# Anirudh [A]: architecture of my part

Plan: `IMPLEMENTATION.md`. Shared contracts and questions:
`team/SHARED_CONTEXT.md`. My progress: `team/anirudh/STATE.md`.

## What I own

The world the agent lives in (cluster, shop, faults) and the screens people
watch.

| Area | Paths | Plan |
|---|---|---|
| Cluster | k3d cluster `oncall`, namespace `shop`, `scripts/setup_cluster.sh` | §3.1, §3.2 |
| The shop | OpenTelemetry demo via Helm, `k8s/values.yaml`, `scripts/install_shop.sh` | §3.3 |
| Buggy payment image | `chaos/payment-bad/` (Dockerfile + patched source), image `payment:v2-bad` | §3.4 |
| Service list | `config/services.yaml` | §4.1 |
| Chaos panel (port 7004, admin kubeconfig) | `chaos/` (`main.py`, `faults.py`, `ground_truth.py`, `reset.py`) | §6.1 |
| UI (port 3000, Next.js) | `ui/` | §6.8 |
| Smoke test | `scripts/smoke.sh` | §8.4 |

## Flow through my parts

```
load generator -> shop services -> OTel Collector -> Prometheus + Jaeger
                                                      (read by M's observer/brain)
chaos panel:  POST /chaos/<fault> -> patch cluster as admin
              -> append ground truth to data/ground_truth.jsonl
              POST /chaos/reset -> restore healthy snapshot, wait severity 0
UI:           EventSource(":7003/events") -> one reducer -> pages
              /  /chaos  /trust  /receipts  /benchmark
```

## Hard rules my code must keep

1. Every fault **persists** until its cause is reversed (§6.1).
2. Ground truth lives only in `data/ground_truth.jsonl`. The brain and the
   gateway have no path to it. `GET /chaos/ground-truth` is for the bench
   only.
3. Chaos writes use a known field manager so the agent's hands-off check
   can tell them apart (proposal Q4: `chaos-panel`).
4. Payment Deployment uses `imagePullPolicy: IfNotPresent`; `payment` has
   2 replicas; rolling strategy `maxUnavailable: 0`, `maxSurge: 1` on
   actable services (§3.3).
5. The raw `kubectl` box on `/chaos` is for judges and runs as admin. It
   must never be reachable from agent code.

## What I provide to others

| To | What | Contract |
|---|---|---|
| M | Running cluster, VERIFY values, `config/services.yaml` | C7 |
| T (bench), me (smoke) | Chaos API; inject returns ground-truth timestamp; reset | C6 |
| T (bench) | Load generator failure counts for "failed customer requests" (§9.1) | add to C6 |
| everyone | UI pages | §6.8 |

## What I need from others

| From | What | Contract |
|---|---|---|
| T | SSE stream `:7003/events`, event types and payloads | C2, C3 |
| M | `GET :7001/health/now` for `/chaos` health and reset wait | C4 |
| M, T | `/ledger`, `/receipts/{id}` for `/trust` and `/receipts` | C5 |
| M | Terminal events for the smoke test | C10 |
| T | Benchmark results format for `/benchmark` | ask T |
