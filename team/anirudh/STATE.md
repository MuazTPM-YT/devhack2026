# Anirudh [A]: state

Update this file at the end of every session. Newest facts on top of each
section. Only my own work here; cross-team facts go in
`team/SHARED_CONTEXT.md`.

**Last updated:** 2026-11-13
**Current phase:** 0 (nearly done; branch `anirudh/phase0-cluster`, not pushed)

## Done (with proof)

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

- Q1: needs M and T to agree before the plan file refs are edited.
- M to confirm the span-metric and flagd VERIFY rows.

## Next

1. Get the cold rebuild under 10 min (image cache).
2. Phase 1: `payment:v2-bad` image, chaos `bad-deploy` and `reset`.

## Notes for my next session

- `kubectl` 1.37 vs server 1.31 prints a skew warning (more than ±1
  minor). It works so far.
- shellcheck is not installed (pacman 404, stale package DB); scripts
  are checked with `bash -n` only.
- flagd-ui edits live in an emptyDir, so restarting the flagd pod resets
  the flags to ConfigMap `flagd-config`. This matters for chaos
  `broken-config` persistence and for reset.
- Ports 8080 (frontend-proxy) and 9090 (prometheus) are port-forwarded
  in the background while the session runs.
