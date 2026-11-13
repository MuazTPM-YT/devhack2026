# Anirudh [A]: tasks

Read `team/anirudh/ARCHITECTURE.md` first. Tick a box only with proof
(command output, screenshot). Record progress in `team/anirudh/STATE.md`.
Anything another teammate needs goes in `team/SHARED_CONTEXT.md`.

Priority: P0 = minimum deliverable, P1 = to win, P2 = stretch.

## Phase 0: foundations

- [ ] P0 Prerequisites: Docker (10 GB+ memory), `k3d`, `kubectl`, `helm`, Python 3.12, Node 20+ (§3.1)
- [ ] P0 Cluster `oncall`, server >= 1.30, ValidatingAdmissionPolicy present, namespace `shop` (§3.2)
- [ ] P0 `k8s/values.yaml` (disable OpenSearch and key-needing services, replicas, rolling strategy, low memory on `recommendation`, 5 s scrape) (§3.3)
- [ ] P0 Shop installed with load; store, Jaeger, flagd UI, load generator reachable; `kubectl top pods -n shop` works (§3.3)
- [ ] P0 VERIFY list with M; write every result to the VERIFY table in `team/SHARED_CONTEXT.md` (§3.3)
- [ ] P0 `config/services.yaml` with the real names (§4.1, C7)
- [ ] P0 `scripts/setup_cluster.sh`, `scripts/install_shop.sh` rebuild everything in under 10 minutes (§12)

## Phase 1: the spine

- [ ] P0 `payment:v2-bad` image (about 40% charge errors), imported into k3d (§3.4)
- [ ] P0 `POST /chaos/bad-deploy`, `POST /chaos/reset`, ground truth file (§6.1)
- [ ] P0 `scripts/smoke.sh`: reset, wait healthy, inject bad deploy, wait for terminal event or 5 min, print times (§8.4); needs C10

Exit: smoke test passes with M's spine.

## Phase 2: the other failures

- [ ] P0 `POST /chaos/broken-config` (wrong env on checkout, or flag flip) (§6.1)
- [ ] P0 `POST /chaos/memory-leak` (leak flag on `recommendation`)
- [ ] P0 `POST /chaos/datastore-down` (scale `valkey-cart` to 0)
- [ ] P0 Every fault persists until reversed; reset restores all of them

Exit: scenarios 1 to 6 in §7 can be injected and reset.

## Phase 3: UI

- [ ] P1 `/` live incident page: six stage tiles, grouping counter, culprit and victims, evidence list, checklist steps, trust numbers, predicted vs actual chart, card, receipt (§6.8)
- [ ] P1 `/chaos` page: one button per fault, raw `kubectl` box, reset, current health

## Phase 4: more UI

- [x] P1 `POST /chaos/shared-outage` (scale `kafka` to 0), if Q6 is agreed. Proof: `tests/test_chaos.py` 32 pass; live inject -> kafka replicas 0, checkout err 0.068 after 90 s, reset restored `["kafka"]`.
- [x] P1 `/trust`, `/receipts` (with "verify audit log" button), `/benchmark` pages (§6.8). Proof: `npm test` 13 pass, `tsc` clean, `next build` OK; screenshots at 1440 px and 390 px with live gateway data. Waiting on `GET /trust` (M), `GET /receipts` + `GET /audit/verify` (T); pages fall back until then.

## Phase 5: freeze

- [ ] Architecture diagram export from Miro into the repo
- [ ] Demo browser tabs and pre-demo checklist (§11.1)

## Never cut

The live incident page and the chaos page are the last UI pages to cut.
