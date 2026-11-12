# Muaz [M]: state

Update this file at the end of every session. Newest facts on top of each
section. Only my own work here; cross-team facts go in
`team/SHARED_CONTEXT.md`.

**Last updated:** 2026-11-13
**Current phase:** 1 (stdlib-only core done; IO wiring waits on deps + schemas)
**Branches:** PR #16 (`muaz/gateway`) open. Now `muaz/verify-loop` on top of #16 (not pushed)

## Done (with proof)

- Gateway part 2 + brain hand-over on `muaz/verify-loop`:
  `Gateway.verify` (5 s health poll, early abort -> pause/undo/resume,
  human change -> handed_off without undo, harm check, outcome), `undo`,
  `close` (receipt outcome, ledger `real` credit except rehearsal approvals,
  incident state, terminal event with T's card), `rehearsal_credit` +
  `POST /ledger/rehearsal` (404 unless `ONCALL_REHEARSAL=1`, once per
  receipt), `ReceiptStore.update` (T's file, 5 lines),
  `brain/gateway_client.py` (MCP `call_tool`), brain escalates itself when
  there is no action or the gateway is down. Proof: `uv run pytest` ->
  `239 passed`; `ruff check .` -> `All checks passed!`; `mypy schemas
  brain gateway notifier bench observer chaos` -> `no issues found in 60
  source files`; in-process test: brain MCP client -> real gateway app ->
  `awaiting_approval`. Mutation check (rehearsal exclusion, pause, undo on
  failure, credit once) -> all caught. Not run on the real cluster.
- Gateway part 1 on `muaz/gateway`: `gateway/checklist.py` (steps 1 to 8,
  first failure decides, terminal events with T's card), `gateway/policy.py`,
  `gateway/dryrun.py` (previous ReplicaSet template, JSON Patch with
  resourceVersion test, spec diff, template-only check, namespace hashes),
  `gateway/executor.py` (agent identity, `field_manager=oncall-agent`,
  `_content_type` explicit; 409 or failed test -> handed_off; 403/422 ->
  escalated), `gateway/approvals.py`, `gateway/mcp_server.py` (6 MCP tools,
  target enum = actable services), `gateway/main.py` (7003: `/health`,
  `/approvals/{id}/decide`, `/ledger`, T's `/events` + `/receipts`, `/mcp`).
  Dep `mcp~=1.30.0` (Muaz chose A; 2.x needs pydantic 2.12). Proof:
  `uv run pytest` -> `209 passed`; `ruff check .` -> `All checks passed!`;
  `mypy ... observer` -> `no issues found in 53 source files`. Mutation
  check (hands-off filter, protected policy, template-only check, 409
  mapping) -> 4 FAIL, all caught. Every published event validates against
  T's `Event` model in the tests. Not run against the real cluster.
- Brain service on `muaz/brain`: `brain/main.py` (FastAPI `POST /incidents`,
  `GET /incidents/{id}`, pipeline), `brain/graph.py` (Jaeger deps, 60 s
  cache, `downstream`), `brain/culprit.py` `fetch_error_traces`,
  `brain/bundle.py` (evidence with IDs, env names only, k8s events, last
  state, error logs <= 50, memory ratio). Proof: `uv run pytest` -> `186
  passed`; `ruff check .` -> `All checks passed!`; `mypy ... observer` ->
  `no issues found in 47 source files`. Mutation check (env hiding, change
  window, prediction attach, self-edge filter) -> 4 FAIL, all caught. Jaeger
  response shape NOT verified live.
- Observer service (C4) on `muaz/observer`: `observer/main.py` (FastAPI,
  detector loop, `/health/now`, `/journal`, `/baselines/refresh`, incident
  POST to brain + bus, terminal-event close), `observer/kube_watch.py`
  (list + watch, relist on error, bad pods, journal tracker),
  `observer/baselines.py`, Prometheus fetch in `observer/detector.py`,
  `schemas/config.py`. Deps `kubernetes~=36.0.3`, `pyyaml~=6.0.3` (Muaz OK).
  Proof: `uv run pytest` -> `150 passed`; `ruff check .` -> `All checks
  passed!`; `mypy schemas brain gateway notifier bench observer` -> `no
  issues found in 43 source files`. Mutation check (OOM window, traffic
  rule, relist version check, Prometheus-down skip) -> 4 FAIL, all caught.
  NOT run against the real cluster yet (cluster is on Anirudh's machine).
- Merged main after PR #8 (Twaha) into `muaz/drop-llm`; resolved
  `brain/llm.py` modify/delete by keeping `DiagnosisService` and removing
  only my sync interface. Proof: `uv sync --locked` OK; `uv run pytest` ->
  `136 passed`; `uv run ruff check .` -> `All checks passed!`;
  `uv run mypy schemas brain gateway notifier bench` -> `no issues found in
  36 source files`; `graphify update .` run.
- Removed my `brain/llm.py` + `tests/test_llm.py` + env keys; Twaha's
  `DiagnosisService` is the LLM path (Muaz chose A). Proof: stdlib suite
  `OK`; `git merge-tree` vs `origin/codex/twaha-opencode-go` shows no
  conflict.
- `brain/rules.py` + `brain/llm.py` on `muaz/llm-opencode`, stdlib only.
  Proof: `python3 -m unittest discover -s tests` -> `Ran 59 tests ... OK`
  (3.14.9 and 3.12.12). Mutation check (by_agent filter, change window,
  retry count, cache fallback) -> 5 FAIL, all 4 caught. Lint + type check
  NOT RUN (Q9). No real OpenCode Go call made (no key here).
  - rules: general rule (image/resources/other -> `rollback_deploy`, env ->
    `revert_config`, replicas -> `scale`), protected inverse, OOM or
    memory >= 90% -> `restart_service` + `raise_limit` (2x, capped at
    `max_memory`). `tests/test_rules.py`. Commit `cc60751`.
  - llm: OpenCode Go chat completions, model `deepseek-v4.1-flash` (Muaz
    pick), forced `submit_diagnosis` tool, one retry, 30 s timeout, token
    counts, cache in `data/llm_cache/`. `OPENCODE_API_KEY`, `LLM_MODEL`
    in `.env.example`. `tests/test_llm.py`. Commit `97eab10`.
  - ASSUMED: tool per change kind as above; `Authorization: Bearer` for
    the key; DeepSeek accepts forced tool choice with reasoning on. Check
    the last two with one real call.
- LLM provider switched to OpenCode Go in `team/SHARED_CONTEXT.md` (VERIFY
  row, Q10 reply, 3 log entries). Proof, live probes 2026-11-13:
  `GET https://opencode.ai/inference/go/v1/models` -> 200, 30 models with
  `api`, `cost`, `capabilities`; POST chat completions without session
  header -> 400 `MissingSessionID`; with it, no key -> `OpenCode Go requires
  an API key`. Key header format NOT verified (no key here).
- Gateway pure logic on `muaz/phase1-logic`, stdlib only. Proof:
  `python3 -m unittest discover -s tests` -> `Ran 45 tests ... OK` (3.14.9
  and 3.12.12). Mutation check: rule-change, harm unexpected-change,
  right-by-accident mutations -> 3 FAIL. Lint + type check NOT RUN (Q9).
  - `gateway/freshness.py` + `journal.current()` / `still_live()`
    (§6.4.5). `tests/test_freshness.py`. Commit `d69d46c`.
  - `gateway/trust.py`: closed-form bound, eligibility, ledger `record()` /
    `counts()`, `check()` returns receipt numbers (§6.4.6). Gate opens at
    29 clean runs. Fails loud if `reset_on_failure` is false.
    `tests/test_trust.py`. Commit `e07fedb`.
  - `gateway/verifier.py`: `Verification.step()` (early abort, hands-off,
    15 s stable recovery, prediction, collateral seconds), `outcome()`,
    `ledger_effect()`, `harm_check()`; `gateway/dryrun.py`
    `spec_hashes()` (spec/data only) (§6.4.9, §6.4.3). `tests/test_verifier.py`.
    Commit `08b7860`.
- My VERIFY rows filled in `team/SHARED_CONTEXT.md` (commit `e90fd78`).
  Proof is the source each came from:
  - Claude row superseded 2026-11-13: team uses OpenCode Go (see below).
  - kubernetes 37.0.1 wheel, `kubernetes/client/api_client.py:724`
    `select_header_content_type` returns first `json` match, so every patch
    defaults to `application/json-patch+json`; pass `_content_type`.
  - mcp 2.3.0 wheel, `mcp/server/fastmcp.py` raises `ModuleNotFoundError`
    ("FastMCP was renamed to MCPServer"); `MCPServer.streamable_http_app`
    default path `/mcp`.
  - Jaeger docs: `/api/dependencies` (`endTs`, `lookback` in ms) is
    internal; `/api/traces` search params not documented. NOT checked live.
- Phase 1 stdlib-only core on `muaz/phase1-core` (Muaz chose: no new deps
  until T's Q9/Q10). Proof: `python3 -m unittest discover -s tests` ->
  `Ran 24 tests ... OK` on Python 3.14.9 and 3.12.12. Mutation check
  (break sustain `>=`, culprit origin test, author status filter) -> 3 FAIL,
  2 ERROR, so tests catch it. Lint + type check NOT RUN: no ruff/mypy yet (Q9).
  - `schemas/db.py`: §5.1 tables, `connect()` sets WAL. `tests/test_db.py`.
    Commit `3075f3d`.
  - `observer/detector.py`: breach, 30 s sustain, severity, incident open,
    grouping within 120 s, `close_incident()`. `tests/test_detector.py`.
    Commit `fbc24b6`. ASSUMED: "open alerts" in severity = count of
    unhealthy services.
  - `observer/journal.py`: diff on image/env/resources/replicas/template
    annotations/ConfigMap data, author = newest non-status manager, inverse
    ops (`patch`, `scale`, `rollback`), `insert()`, `read()` for
    `GET /journal`. `tests/test_journal.py`. Commit `f7dab99`.
  - `brain/culprit.py`: origin from Jaeger JSON (`error` or
    `otel.status_code=ERROR` tag), fallback deepest unhealthy service, onset
    tie-break. `tests/test_culprit.py`. Commit `6892694`.
- Scale rows fixed: agent Role now has `get` + `patch` on `deployments/scale`
  (Muaz OK'd option A). Re-ran local pre-test on a fresh `oncall-test`
  cluster: `fails: 0`, 19 PASS. Scale to 5: `denied request: replicas must
  stay between 1 and 3` (policy `oncall-agent-scale`); scale to 2:
  `scale.autoscaling/payment patched`. Commit `cfd37e6`. Still local only;
  the real §6.5.5 table stays blocked. The older 15 PASS / 4 FAIL result
  below is replaced by this one.
- Replies to Q1 to Q10 and schema proposal Q11 (for T) in
  `team/SHARED_CONTEXT.md`. Proof: commit `99b0ab5`.
- Local pre-test only (throwaway k3d cluster `oncall-test`, k3s v1.35.5,
  dummy `payment` Deployment on `payment:v1` with 2 replicas, `valkey-cart`,
  `flagd-config`). This is **not** the §6.5.5 table; the real shop was not
  used. Results of `./scripts/security_check.sh`: 15 PASS, 4 FAIL.
  - PASS: can-i delete deployment/payment `no`, get secrets `no`, patch
    deployment/valkey-cart `no`, create pods `no`, patch deployment/payment
    `yes`; reader patch deployment/payment `no`.
  - PASS (dry run and real): approved image patch `patched (no change)`;
    serviceAccountName `denied request: agent may not change the service account`;
    `evil/image:latest` `denied request: image must come from an approved source`;
    restartedAt `patched`; server dry run left resourceVersion `476` unchanged.
  - FAIL (dry run and real): both scale rows. `cannot get resource
    "deployments/scale"`. Cause: `kubectl patch --subresource=scale` does a GET
    first, and the agent Role grants only `patch` on `deployments/scale`.
    The admission rule itself was not reached.
  - Extra dry-run spot checks: env patch `patched`, memory limit patch
    `patched`, add volume `DENIED: agent may not change volumes`,
    hostNetwork `DENIED`, replicas 4 via deployment `DENIED: replicas must
    stay between 1 and 3`, patch flagd-config `patched`.
  - Both policies report empty `status.typeChecking` (no CEL type warnings).
- `scripts/make_kubeconfigs.sh` and `scripts/security_check.sh`. Proof:
  `bash -n` OK; on the test cluster it wrote `agent.kubeconfig` and
  `reader.kubeconfig` with mode `-rw-------`; both are git-ignored
  (`git status` clean after). Commit `e8dd9cf`.
- `k8s/rbac-reader.yaml`, `k8s/rbac-agent.yaml`, `k8s/admission-policy.yaml`
  (2 policies), `k8s/admission-binding.yaml` (2 bindings). Proof: YAML parses;
  `kubectl apply --dry-run=client -f k8s/` OK; applied to the test cluster.
  Commit `3445006`.
- `config/policy.yaml`, `config/queries.yaml`. Proof: YAML parses. Commit
  `43177b1`. Approver ids moved to env `ONCALL_APPROVER_IDS`; `p95_ms_all` added.
- `.gitignore`, `.env.example` (T's files, created with OK). Commit `f0158f4`.

## In progress

- Phase 1 spine complete in code (fakes only). Next: A runs
  `scripts/smoke.sh` on the cluster with observer, brain, gateway up; fix
  what the real API server and Jaeger show. Then Phase 2 tools.

## Blocked / waiting on

- Approval auth: Muaz chose allowlist only, gateway on 127.0.0.1 (no
  shared secret).
- JSON Patch `test` failure status (assumed 422 with "test" in the body ->
  handed_off) not verified on a real API server.
- **§6.5.5 security acceptance table: BLOCKED.** A's cluster is not up. No
  row is passed. Run `kubectl apply -f k8s/`, `./scripts/make_kubeconfigs.sh`,
  `./scripts/security_check.sh` on it.
- Row "real `rollback_deploy` through the executor": needs the gateway
  executor (Phase 1).
- Real-cluster runs (observer smoke, §6.5.5 table, Jaeger curls) happen on Anirudh's machine.
- VERIFY values from A: Deployment names, `flagd-config` name, image prefixes.
- Jaeger paths: need one curl on A's cluster (asked in SHARED_CONTEXT log).
- OpenCode Go: one real call with Muaz's key through Twaha's adapter.
- Schemas (C1): waiting on T's reply to Q11. Blocks `rules.py`, bundle, gateway.
- Deps + commands (Q9/Q10): block every network/cluster part of Phase 1.
- Q replies need the other owners to answer `agreed`.

## Next

1. Pull A's and T's work when pushed; read new SHARED_CONTEXT replies.
2. Run the §6.5.5 table on A's cluster; paste the output here.
3. When deps land: wire detector + journal to Prometheus and kube watch,
   add `/health/now`, `/journal`; then rules, gateway, verifier.
4. When llm.py lands: add `OPENCODE_API_KEY`, `LLM_MODEL` to `.env.example` in the same commit.

## Notes for my next session

- The test cluster `oncall-test` was deleted at session end. Recreate with
  `k3d cluster create oncall-test --servers 1 --k3s-arg "--disable=traefik@server:*" --kubeconfig-update-default=false --kubeconfig-switch-context=false`
  so the default kube context stays `kind-muaz-foss`.
- Admission CEL pattern: `has(new) == has(old) && (!has(new) || new == old)`.
