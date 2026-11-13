# Anirudh [A]: state

Update this file at the end of every session. Newest facts on top of each
section. Only my own work here; cross-team facts go in
`team/SHARED_CONTEXT.md`.

**Last updated:** 2026-11-13
**Current phase:** UI redesign + chaos CLI on `anirudh/ui-redesign`
(cut from `anirudh/spec-fixes`; neither pushed). Phases 0-4 merged.

## Done (with proof)

- End-to-end bad-deploy through the CLI, UI and Discord, 2026-11-13:
  run 3 `incident_resolved`, card `FIXED in 2m 42s: payment; payment
  errors 43.0% -> 0.0%`, receipt #13, prediction held, harm clean,
  approved in Discord by Anirudh. Runs 1-2 escalated: notifier was not
  running (run 1), then Anirudh's id was missing from
  `ONCALL_APPROVER_IDS` (run 2; added, gateway + notifier restarted).
  False ground-truth line removed (backup in scratchpad); chaos panel
  restarted with the `verb()` fix (live `-n shop get` not logged). UI
  fix: trust gate asking a human left Check "stopped" on a resolved
  incident; test added.

- UI redesign + judges' chaos CLI, 2026-11-13, branch `anirudh/ui-redesign`
  (4 commits: a6eaeb9, 94647fb, 63a43d2, 2ccd8d7). Decisions by Anirudh:
  hybrid style (same palette, denser), real events only, approvals stay
  read-only, faults from a CLI not the UI, `/chaos` read-only, brand
  "Akira", event-log card removed.
  - `chaos/cli.py`: `uv run python -m chaos.cli list|inject|reset|kubectl|
    status|truth`, wraps the chaos API so ground truth is still logged.
    Live: `list`, `status`, `truth`, `kubectl get` OK against :7004/:7001.
    Inject/reset **not run live** (would page Discord).
  - Fix: `chaos/main.py` judged read-only kubectl by `args[0]`, so
    `-n shop get ...` was logged as ground truth. Now `verb()` skips
    global flags. Test fails before, passes after.
  - UI: left sidebar (nav, incident history, gateway/observer status;
    rail at <=1100 px, drawer at <=720 px); one SSE stream in the layout
    (`ui/lib/live-context.tsx`); live page has a request-flow map
    (`ui/lib/flow.ts` maps each event to a path between services) and a
    per-incident timeline with payloads. `/chaos` shows health, ground
    truth, copyable CLI commands; Next proxies only
    `GET /chaos/ground-truth`.
  - Checks: UI `npm test` 23 pass, `tsc` clean, `next build` OK; pytest
    400 passed; ruff, mypy clean. Screenshots 1440/900/390 px with live
    bus data and the `?demo=1` replay (scratchpad only).

- Spec audit (IMPLEMENTATION.md vs code) and fixes, 2026-11-13, branch
  `anirudh/spec-fixes`: details and open items in `team/SHARED_CONTEXT.md`
  (last [A] entry). Live: smoke `FIXED in 1m 32s` with prediction held,
  broken-config FIXED, flag-flip resolved, hands-off, stale, expiry all
  as plan section 7. Suite 366 passed, ruff/mypy clean, UI 13 pass, build OK.

- Phase 4: `POST /chaos/shared-outage` (kafka -> 0, ground truth
  `shared_dependency`; live inject + reset OK) and its button on `/chaos`.
  UI pages `/trust` (ledger table, bound meter vs bar, gate),
  `/receipts` (list, detail with card, checklist, pods, diff and inverse;
  "Verify audit log" button), `/benchmark` (server page reading
  `bench/out/summary.json`; bars median/worst, agent vs manual, results
  table). Fallbacks: `/trust` uses `GET /ledger` counts until `GET /trust`
  exists; `/receipts` walks ids from 1 until `GET /receipts` exists
  (`shortcut:` comment, cap 40); the audit button says the route is
  missing until `GET /audit/verify` exists. Checks: `npm test` 13 pass,
  `tsc --noEmit` clean, `next build` OK; Python 331 passed, ruff and mypy
  clean. Screenshots at 1440 and 390 px. Incident card text now keeps
  its line breaks (live page too).

- Live run 2026-11-13 (full report in `team/SHARED_CONTEXT.md`, steps 1-6):
  security_check 19 PASS / 0 fails; payment 5.6 spans/s at 250 users;
  flagd reloads ConfigMap in 55-66 s with no restart; flag map added.
  Smoke: `outcome=escalated`, `detect=42.7s diagnose=72.9s recover=-`.
  Rollback executed after approval and severity hit 0, but
  `gateway/verifier.py:45` never sees `frontend-proxy` in `/health/now`, so
  it undid the rollback. LLM call `deadline_exceeded` (30 s). ad and
  jaeger OOM at 250 users fixed in `k8s/values.yaml` (8bc049e).
- Todo: drop the flagd-ui live-file write from `chaos/faults.py` /
  `chaos/reset.py` (flagd reads the ConfigMap now). Remove UI `?demo=1`
  before submission. Start the observer after the gateway.

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
