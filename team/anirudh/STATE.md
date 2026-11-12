# Anirudh [A]: state

Update this file at the end of every session. Newest facts on top of each
section. Only my own work here; cross-team facts go in
`team/SHARED_CONTEXT.md`.

**Last updated:** 2026-11-13
**Current phase:** 3 done (branch `anirudh/phase3-ui`, not pushed).
Phases 0-2 merged (PRs #9, #10, #16, #21). Real smoke run still waits on
M's spine.

## Done (with proof)

- Phase 3 UI (`ui/`, Next 16.4.3, React 19.2.9, TypeScript 6.0.3; no other
  deps): `/` live incident page (six stage tiles, blast radius, severity
  chart with predicted vs actual recovery, checklist, evidence, outcome
  card + receipt, event log) and `/chaos` (5 fault buttons, reset, observer
  health gauge, raw kubectl box, ground truth log). Proof: `npm test` 9
  pass (reducer + demo script), `tsc --noEmit` clean, `next build` builds
  `/` and `/chaos`. Screenshots checked at 1440 px and phone width.
  Live mode tested against a stub gateway with the real SSE wire format:
  link `live`, check tile `stopped`, outcome `handed off`.
- `POST /chaos/kubectl` (scenario 6): live `get deploy payment cart` and
  a NotFound error both returned through the Next proxy; tests prove shell
  metacharacters stay plain args. Chaos tests 30 pass; full suite 276
  passed; ruff and mypy clean.
- Muted text colour changed to `#736359`: 4.6-5.2:1 contrast on every
  surface (was 3.2-3.7:1, failing WCAG AA).
- `POST /chaos/flag-flip` (scenario 3): `paymentFailure` set to `50%`;
  flagd OFREP returned `value: 0.5`; payment failed 5.1 of 11.2 charges
  (45%) over 5 min; reset restored `["configmap/flagd-config"]` in 0 s,
  and the next 2 min showed 0 errors. flagd was not restarted. Tests:
  `tests/test_chaos.py` 23 pass, full suite 258 passed, ruff and mypy
  clean. Phase 2 exit: scenarios 1-5 inject and reset; scenario 6 comes
  with the raw `kubectl` box on `/chaos` (Phase 3).
- Phase 2 faults, all live on the cluster, each injected then reset:
  - `broken-config`: checkout `PAYMENT_ADDR=payment:9999`; checkout error
    ratio went from 0 to 1.0; reset restored `["checkout"]` in 15 s and
    the errors were back to 0 within 60 s.
  - `datastore-down`: `valkey-cart` replicas went to 0; cart error ratio
    1.0 (throughput collapsed). Reset restored `["valkey-cart"]` in 2 s;
    cart was back at 3.6 successful req/s with 0 errors.
  - `memory-leak`: flag `recommendationCacheFailure` turned on in the
    ConfigMap and the live flagd file; recommendation hit `OOMKilled` 128 s
    after inject and leaked again after its restart (persists). Reset
    restored `["configmap/flagd-config"]` in 1 s and the leak stopped 21 s
    later. flagd was never restarted.
  - managedFields show `chaos-panel` on `cm/flagd-config`,
    `deploy/checkout` and `deploy/valkey-cart`.
- Bug found and fixed: the first leak design restarted flagd, and
  recommendation then ignored the flag for 9 min (stale flagd client).
  Fixed by writing the live file. New test
  `test_reset_restores_flag_flipped_only_in_flagd_ui` fails without the
  live-file check and passes with it.
- Checks: `tests/test_chaos.py` 21 pass; full suite 195 passed; ruff
  clean; `uv run mypy schemas brain gateway notifier bench observer chaos`
  clean (49 files).
- `scripts/smoke.sh`: against a stub `curl`, it prints
  `incident=inc-7 outcome=incident_resolved` and
  `detect=12.5s diagnose=40.0s recover=90.2s` with rc 0. It ignores
  events from before the inject and other incidents. `escalated` gives
  rc 1, and a missing terminal event prints `outcome=timeout`. **Not run
  for real**: there is no observer or gateway yet.
- Chaos API live on :7004. `POST /chaos/bad-deploy` returned in 113 ms
  and the rollout finished. Payment's server-span error ratio went from
  0 to 0.444 within 75 s. managedFields show the `chaos-panel` Update.
  `POST /chaos/reset` restored `["payment"]` in 2 s, and the ratio was
  back to 0 about 46 s later. A second reset is a no-op (`restored: []`).
  `data/ground_truth.jsonl` holds the 3 lines.
- Checks: `tests/test_chaos.py` 11 pass; full suite 153 passed; `uv run
  ruff check .` clean; `uv run mypy schemas brain gateway notifier bench
  chaos` clean (42 files).
- `payment:v2-bad` built from `chaos/payment-bad/` (base
  `ghcr.io/open-telemetry/demo:3.1.0-payment` + patched `charge.js`).
  `scripts/build_bad_payment.sh` imports it into k3d, and `crictl images`
  shows `docker.io/library/payment:v2-bad`.
- VERIFY rows owned by A filled in `team/SHARED_CONTEXT.md`; replies to
  Q1, Q4 and Q6 added.
- `config/services.yaml`: names match live `kubectl -n shop get deploy`;
  `yq '.services | keys'` parses all 9 services.
- Shop installed: `scripts/install_shop.sh` exit 0, 25/25 Deployments
  ready, 28 pods Running. Through
  `kubectl -n shop port-forward svc/frontend-proxy 8080:8080`, `/`,
  `/jaeger/ui/`, `/feature/` and `/loadgen/` all return 200.
  `kubectl top pods -n shop` works. `payment` and `checkout` run 2/2.
  The payment strategy is `{"maxSurge":1,"maxUnavailable":0}` with
  `IfNotPresent`. The `recommendation` limit is 200Mi (steady use 50Mi).
  Prometheus has `traces_span_metrics_calls_total` with `service_name`.
- `k8s/values.yaml` for chart 0.42.6 (released 2026-10-21): renders with
  `helm template`.
- Cluster `oncall`: `scripts/setup_cluster.sh` reports server
  v1.31.5+k3s1, VAP `admissionregistration.k8s.io/v1`, and ns `shop`
  Active. Re-run is idempotent.
- Prerequisites: kubectl v1.37.2, helm v4.3.0, k3d v5.8.3, Python
  3.12.13 (uv), Node v26.13.0, Docker 29.9.2.

## In progress

- Rebuild-under-10-min goal: **not met cold**. Measured cluster create
  47 s plus first install about 10 min (image pulls, with DNS retries
  `lookup auth.docker.io: Try again`), so about 10m45s in total. A warm
  re-run of install takes 5 s. Fix idea: k3d registry cache or
  pre-pulled images.

## Blocked / waiting on

- Phase 1 exit (smoke passes with M's spine): needs C4 `/health/now`
  and C10 terminal events from M.
- Q1: needs M and T to agree before the plan file refs are edited.
- M to confirm the span-metric and flagd VERIFY rows.

## Next

0. **REMINDER for Anirudh: remove the `?demo=1` replay before submission**
   (`ui/lib/demo.ts`, the demo branch in `ui/lib/use-live.ts` and
   `ui/lib/use-receipt.ts`, the Replay button in
   `ui/components/live/live-view.tsx`, and the demo test in
   `ui/lib/live.test.ts`). Asked for on 2026-11-13.
1. Run `scripts/smoke.sh` for real once M's observer + gateway run.
2. Switch the reset wait to severity 0 once C4 exists (`shortcut:` in
   `chaos/reset.py`).
3. Phase 4: `/trust`, `/receipts` (verify audit log), `/benchmark`;
   `POST /chaos/shared-outage` (Q6 agreed).
4. Get the cold rebuild under 10 min (image cache).

## Notes for my next session

- Snapshot format is now `{deployments, flags}`; the current
  `data/healthy_snapshot.json` was taken on 2026-11-13 from a healthy shop.
- Port 8016 (flagd OFREP) is port-forwarded for flag checks:
  `curl -X POST localhost:8016/ofrep/v1/evaluate/flags/<flag> -d '{"context":{}}'`.
- `kubectl` 1.37 vs server 1.31 prints a skew warning (more than ±1
  minor). It works so far.
- shellcheck is not installed (pacman 404, stale package DB); scripts
  are checked with `bash -n` only.
- flagd-ui edits live in an emptyDir, so restarting the flagd pod resets
  the flags to ConfigMap `flagd-config`. This matters for chaos
  `broken-config` persistence and for reset.
- Start the chaos panel with
  `uv run uvicorn chaos.main:app --host 127.0.0.1 --port 7004`, only
  while the shop is healthy (the first start takes the snapshot).
- The payment error ratio query is in the scratchpad (`payerr.sh`):
  server spans with `status_code="STATUS_CODE_ERROR"` / all server spans.
- Ports 8080 (frontend-proxy) and 9090 (prometheus) are port-forwarded
  in the background while the session runs.
