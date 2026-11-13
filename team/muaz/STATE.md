# Muaz [M]: state

Update this file at the end of every session. Newest facts on top of each
section. Only my own work here; cross-team facts go in
`team/SHARED_CONTEXT.md`.

**Last updated:** 2026-11-14
**Current phase:** safe journal autonomy + Chaos Lab restore parameters; full live drill pending
**Branches:** `codex/safe-journal-autonomy` (local, not pushed)

## Done (with proof)

- Fixed single-replica surge forecast blocking safe memory restores (2026-11-14).
  Live incident `inc-5198ce6253f6` selected recommendation 32Mi -> 200Mi, but net-benefit asked with a
  10535 s forecast. `gateway/blast.py` now treats 1+ replicas with RollingUpdate, maxUnavailable=0 and
  positive maxSurge as no planned capacity loss. Invalid/zero surge stays unsafe; Recreate still asks.
  Regression failed before fix for both rule/model memory restores with one replica and healthy frontend
  caller; after fix both verify recovery and notifier FYI without approval. 12 new forecast/surge cases.
  Proof: 61 targeted pass; full isolated suite with tracked defaults 949 pass (20.38 s), Ruff clean,
  mypy clean (99 files), graph updated. Existing local config overrides untouched. Gateway restarted
  alone, /health ok; MCP reports all services up, Prometheus/Discord ready, severity 0. Actual live
  recommendation strategy now forecasts 0 s instead of 10535 s. No new live fault/model/Discord drill.

- Chaos Lab now has actual memory/capacity fault parameters feeding new repair proposals (2026-11-14).
  `memory_limit` offers reviewed caps below live limit and at least live request on recommendation/ad/email;
  `replica_reduction` leaves 1+ replicas, on those services plus payment/checkout. Missing baseline capacity
  stays unavailable with a reason. `brain.rules.memory_restore` turns a memory-only limit reduction into
  `raise_limit` with exact old memory/container/journal evidence instead of rolling back the whole template.
  `autonomy.memory_restores` permits those exact inverses on the same three non-critical services; generic
  increases, critical services, mixed resource changes and all existing safety failures still ask/refuse.
  Existing runbook guidance extended (18 entries retained); model capabilities expose the exception; prompt
  `agent-5`. UI types/choice labels added; engine injection/cleanup handles memory as one field.
  Proof: isolated suite with tracked defaults 937 pass (19.21 s), 15 new cases; compiled UI tests 84 pass;
  Ruff/mypy clean (99 files), UI typecheck clean, graph updated. Node 22 lacks TypeScript support: `npm test`
  cannot run TS directly here; compiled with existing tsc into /tmp, then ran node:test.
  Live API dry runs: recommendation 200Mi -> 32Mi -> 200Mi, ad 450Mi -> 128Mi -> 450Mi, checkout replicas
  2 -> 1 -> 2; judge injection and oncall-agent repair accepted, deployment specs unchanged. Current
  non-critical services have 1 replica, so nonzero reduction is unavailable until baseline has 2 or 3.
  No actual live injection/model/Discord drill. Restart chaos + brain + gateway to load new handlers/policy;
  production UI needs rebuild for new choice labels. Existing local overrides remain outside commit.

- Safe autonomous journal reverts, `codex/safe-journal-autonomy` (2026-11-14). User approved a quick subset:
  `config/policy.yaml` `autonomy.journal_reverts: [ad, email, recommendation]` allows exact flag/env inverses
  and restoring a reduced replica count without incident-time approval or 29 trust runs. Gateway checks
  explicit non-critical stateless scope, latest journal entry, fresh Prometheus health (3 polls), prediction,
  exact inverse and no ledger failures; runbook, major, protected, budget and in-flight gates remain.
  Model choices can qualify. Receipt/card names the policy; normal notifier FYI reports verified success.
  Failed autonomous model fixes now debit trust too, so undo + escalation suspends the next auto attempt.
  Prompt version `agent-4`. No new dependency. Proof: 23 new checks; full isolated suite with tracked config
  defaults `922 passed` (19.84 s), Ruff clean, mypy clean (99 files), graphify updated. Workspace suite:
  920 passed, 2 failures from existing local overrides (orchestration coordinated, hourly budget 30).
  Local overrides preserved, excluded from commit. Sandbox async thread wakeups stall; tests pass outside.
  Real cluster, model and Discord NOT run. Restart gateway + brain to load the new policy/prompt.

- Live runs 2026-11-13/14 on k3d `oncall` (same branch). Found and fixed, each with a test that failed first:
  notifier bot died on a Discord 503 at connect and stayed up silent (`fdf7e7a`: reconnect 5 times, then stop
  loud); journal blamed a removed field on the newest manager left (`cc73c96`: blame the manager that vanished);
  verifier handed off a right fix when chaos removed its decoy (`76af19a`: chaos writes are no hand-off, as step
  2); two gateways after a restart broke the audit chain (`dc3fcc8`: audit writer lock, demo.sh
  `--timeout-graceful-shutdown 5`; live: 2nd gateway refused, stop took 6 s). The 3 stray audit lines are kept in
  `data/audit.zombie-2026-11-14.jsonl`; `/audit/verify` -> ok, 124 records. Merged main (`978f0b5`), 714 passed.
  Live: agent picked the right fix past a decoy twice; one fix executed (flag revert).
  Retry live 2026-11-14 00:24-00:37 (flag 50% + payment:v2-bad, both needed): fix 1 rollback approved, did not
  recover, undone -> `retry_started` -> agent read the failed fix, chose flag revert -> approved, did not recover,
  undone -> page "tried 2 fixes; each failed", `no retry: action budget used up` (1 fix earlier that hour).
  Fixed after: retry push line (`d57c0cd`); test gateway apps wrote live data/audit.jsonl (`4aff979`).
  715 passed. First model call hit the 150 s deadline (rule pick used): T's open item.

- Retries + Discord origin (branch `muaz/agent-polish`, not pushed). Muaz chose: 3 fixes per incident, retries
  run alone (trust gate kept), only fixes run and cleanly undone retry, agent mode only, all three origin parts.
  - Before: no retry at all; `budgets.max_retries: 1` was never read. Now `max_retries: 2` (3 fixes).
  - Gateway decides (`Gateway.close`): undo for "did not recover", "severity rose", "harm check failed", tries
    and budget left, no other approval waiting -> state `replanning`, event `retry_started` (FYI), POST
    `BRAIN_URL/incidents/{id}/retry` with every failed fix (tool, change, why undone, severity before/after,
    readings, prediction, worse services). Else page as before, briefing `...; no retry: <why>`.
  - Granted retry (gateway memory, brain cannot claim one) skips only the "model picked it" ask; trust gate,
    protected, runbook, major, net benefit, freshness still ask. No grant answered in 300 s -> page; gateway
    restart adopts `replanning` incidents (next fix asks).
  - Brain: failed fixes leave the candidates (renumbered), model sees `failed_attempts`, a repeat is refused.
  - Observer: max age 1200 -> 2400 s; incident still `open` (brain never handed over) pages after 600 s.
  - Discord: Your move line, Impact (all sick services), Fixes tried, Origin (started by / sent by + machine /
    LIVE or REHEARSAL, stamped by the gateway bus), Timeline (Discord time tags), footer Event #, embed time.
  Proof: `uv run pytest` -> `666 passed`; `ruff check .` -> `All checks passed!`; `mypy ... chaos` -> `no issues
  found in 75 source files`; UI `npm test` 62 pass, typecheck OK, build OK. Two tests changed (setup/additive,
  intent kept): `test_observer.py` stuck-incident test marks the incident handed over; `test_embeds.py` consumer
  test also sees the new `event` detail; UI `overview.test.ts` mirrors max age 2400. Fakes only: real shop, real
  LLM and Discord NOT run.

- Full audit + local end-to-end run (branch `muaz/agent-polish`, 15 commits from `20ea15c` to `48c2194`):
  - Harness (not in git, job scratch dir): k3d `oncall-test` (k3s v1.31.5) with tiny Deployments named like the
    shop + real RBAC/VAP; real observer, brain, gateway, chaos processes; a fake Prometheus + Jaeger whose numbers
    follow the live cluster state (agent writes change them); only the LLM network call faked. 25 scenarios: plan
    §7 rows 1-10 and 12, approval expiry, stale metrics, gateway/brain/observer restarts, back-to-back faults,
    bad model output, `scripts/smoke.sh`, one `bench.harness` rehearsal trial.
  - Bugs fixed (Muaz chose each behaviour; each has a test that failed first): k8s read errors on an approved
    re-run gave HTTP 500 and no page; a lost connection on a real write paged nobody (now "check by hand", no
    receipt); two checklists could both execute (global run lock); relist kept deleted pods as bad; one DB error
    killed the detector loop; major flag incident blamed `flagd-config`; expired follow-up flipped resolved ->
    escalated (now a ticket); major "no scale up" blocked restoring kafka (now approved restore of the journaled
    count); gateway acted on and judged fixes with stale health (now asks; blind verify keeps the fix); watchdog
    on a no-undo fix blocked all actions; observer restart opened a duplicate incident.
  - Security fixed: `GET /journal` needs the token (env values); chaos POSTs need the token (UI server adds it,
    route `ui/app/api/chaos`); UI binds 127.0.0.1; admission denies exec probes/hooks, envFrom/secretKeyRef,
    memory > 1Gi, label/scheduling/strategy/history changes, other ghcr.io/open-telemetry images, new keys in
    flagd-config (new policy `oncall-agent-flags`).
  Proof: `uv run pytest` -> `492 passed`; `ruff check .` -> `All checks passed!`; `mypy ... chaos` -> `no issues
  found in 67 source files`; UI 19 pass, typecheck OK, build OK; `security_check.sh` on `oncall-test` -> 35 PASS,
  `fails: 0`; e2e: all 25 scenarios pass (23/25 on the second run; P4, P5 fixed then rerun 5/5 with R3, R4, S1). Real shop, real LLM and Discord NOT run.

- Agent polish (branch `muaz/agent-polish`), Muaz chose 1a 2a 3 samples 4a 5a 6a:
  - Shared token `ONCALL_API_TOKEN` (`schemas/auth.py`, header `X-Oncall-Token`): gateway,
    brain and observer refuse every non-GET without it (decide, clear, publish, MCP).
    Closes T's auth gap. Reads stay open for the UI.
  - Company runbooks `config/runbooks.yaml` (samples RB-01..07, RB-99), `brain/runbooks.py`:
    code matches; the LLM reads them (prompt v6); the gateway enforces `require_approval`
    (step 7, even with an open trust gate) and `forbid_tools` (step 3).
  - Experience memory `brain/memory.py`: similar finished incidents + verified outcome go
    into the prompt and Discord ("seen before"). No training; RL/GRPO rejected (rented
    model, 4 GB GPU, tens of runs). Injected model text is dropped.
  - Discord embeds (`notifier/embeds.py`): audience line, color per status, runbook, seen
    before, approvers, expiry, page count; decisions/acks edit the embed (who, when).
  - Detector: a new fault after the open incident went quiet opens its own incident
    (A's open item 2).
  Proof: `uv run pytest` -> `414 passed`; `ruff check .` -> `All checks passed!`; `mypy ...
  chaos` -> `no issues found in 67 source files`; new hard-rule and detector tests fail on
  old code; live Discord: 5 test embeds accepted in the FYI channel. Cluster not run.

- Plan audit (branch `muaz/plan-audit`), Muaz chose: edit teammates' files,
  human-approved data-store scale, rehearsal lifts hour budget, build UI pages.
  - Fixed: failed generation test -> `handed_off` (was escalated + false `blocked`);
    freshness "entry not found" now really asks (returned awaiting_approval with no
    approval); freshness asks named `freshness`; harm check spares the blast radius
    (upstream callers), not only victims; verify fallback uses the flag window; tier
    `ask` when a human approved; real success only with a human approval; brain
    escalates MCP/schema refusals (incident stayed open forever, e.g. scenario 5);
    freshness judges an unmeasured culprit (data store) by its victims.
  - Added: protected scale via approval, rehearsal hour budget, `/trust`,
    `/audit/verify`, `GET /receipts`, terminal-event bench fields, §6.7.1 card.
  Proof: `uv run pytest` -> `349 passed`; `ruff check .` -> `All checks passed!`;
  `mypy ... chaos` -> `no issues found in 62 source files`; UI `npm test` 12 pass,
  typecheck OK, `npm run build` OK. New tests fail on old code (5 checked). Test k3d
  cluster `oncall-test` (deleted after): security table 24 PASS, `fails: 0`; real
  Gateway with agent identity: valkey-cart 0 -> ask -> approve -> 1 -> resolved;
  payment rollback -> early abort -> pause/undo/unpause, 0 blocked events. Shop not run.
- Fixes from live runs 2 (branch `muaz/verify-fixes`, 3 commits):
  - Early abort has a grace period: `verify.early_abort_grace_seconds: 60`
    (+ `flag_extra_seconds` for a flag). A victim that turns sick seconds
    after a right fix no longer undoes it.
  - Undo tests `/metadata/generation`, not `resourceVersion` (rollout
    status writes bump resourceVersion; that gave the live 422). The
    forward rollback patch uses the same test. Unpause runs in `finally`.
  - A failed undo ends as `undo_failed` (no longer `pending`, so it does
    not block later actions) and logs `UNDO FAILED` at ERROR.
  Proof: 3 new tests in `tests/test_verify_loop.py` fail on old code (churn
  test -> `'undo_failed' == 'undone'`, as live) and pass after; `uv run
  pytest` -> `332 passed`; `ruff check .` -> `All checks passed!`; `mypy ...
  chaos` -> `no issues found in 62 source files`. Fakes only; the 422 cause
  is not proven live yet.
  Not changed: `watchdog_failed` still blocks new actions (by design); the
  scale undo still pins `resourceVersion` in a merge patch.
- Flag revert, scenario 3 (branch `muaz/flag-revert`): journal names the
  flipped flag in the flagd JSON (`flags[<name>].defaultVariant`, per-flag
  inverse; non-flagd text falls back to the whole key); rules treat a flag
  change as a recent change on the service `flags:` maps it to; gateway
  `revert_config` on a flag entry patches only `flagd-config` (merge patch
  + resourceVersion), dry run must move exactly the recorded flags, "flag
  already back" is refused before any write, undo restores the old file,
  harm check declares `configmap/flagd-config`, verify window +90 s
  (`verify.flag_extra_seconds` in `config/policy.yaml`). Proof: `uv run
  pytest` -> `329 passed`; `ruff check .` -> `All checks passed!`; `mypy ...
  chaos` -> `no issues found in 62 source files`; mutation check (flag link,
  exact-flags check, extra window, configmap undo) -> all caught. Fakes only.
  `enable_degraded_mode` stays refused (Muaz chose A).
- Live run by A (2026-11-13, report in SHARED_CONTEXT): security table 19
  PASS, `fails: 0` on the real cluster; RBAC/VAP applied; Jaeger API shape
  matches my graph code; flagd reads the ConfigMap (~60 s); load raised to
  payment ~3 req/s; flag map agreed. Smoke: detect 42.7 s, diagnose 72.9 s,
  approve -> rollback executed (receipt #1), then wrongly undone.
- Fixes from the live run (merged in PR #29):
  - Verifier watched trace victim `frontend-proxy`, which `/health/now`
    never lists, so recovery could not pass and the good rollback was
    undone. Now it watches only services the observer measures (culprit
    always); a measured service that vanishes still blocks recovery.
  - Observer: an incident opened while brain/gateway were down stayed open
    forever and blocked all later incidents. Now it is re-sent every poll
    until the brain and bus take it. Event-stream errors log once per
    outage instead of every 2 s (A saw 6138 lines).
  Proof: both regression tests failed before the fix (`AssertionError:
  None != 'recovered'`; resend count) and pass after; `uv run pytest` ->
  `320 passed`; `ruff check .` -> `All checks passed!`; `mypy ... chaos` ->
  `no issues found in 62 source files`.
- Two fixes found by re-reading §7 against the code (merged in PR #25):
  - Incident flood: after an incident closes, its services cannot open a
    new incident until they recover once (`Detector.suppressed`). Before,
    an escalated, still-broken service re-paged every 5 s. The old test
    `test_close_lets_next_incident_open` asserted that flood; replaced by
    `test_close_suppresses_until_recovery` (Muaz approved the change).
  - Scenario 5: when the trace culprit has no own change, a non-agent
    change on a dependency (graph downstream or any stateful service)
    becomes the culprit (`brain/culprit.py::dependency_change`). valkey-cart
    scaled to 0 -> culprit valkey-cart, pattern protected, scale proposal.
    `culprit_found` carries `moved_from`.
  Proof: `uv run pytest` -> `310 passed`; `ruff check .` -> `All checks
  passed!`; `mypy ... chaos` -> `no issues found in 62 source files`;
  mutation check (no suppression, no recovery release, own change ignored,
  no stateful fallback) -> 4 FAIL, all caught. Fakes only.
- Phase 4 on `muaz/phase4`: `brain/major.py` (major = >= 4 or >= 30% of
  services within 120 s; ranked shared change, then shared dependency;
  top candidate becomes the culprit; `major_incident` event; incidents
  `major=1`), gateway major rules (root cause only, one restart, no scale
  up, approval unless reverting the shared change), `blocked` event on
  403/422 (scenario 12), `tests/test_invariants.py`. Proof: `uv run
  pytest` -> `276 passed`; property test prints `2000 generated cases, 0
  violations`; mutating the target checks / freshness / trust gate /
  in-flight / budgets gives 1 / 3 / 40 / 13 / 7 violations, so the test
  bites. `ruff check .` -> `All checks passed!`; `mypy ... chaos` -> `no
  issues found in 62 source files`. Fakes only.
  - ASSUMED: stdlib `random` (fixed seeds) instead of Hypothesis, no new
    dependency; no shrinking. Invariant 8 counts gateway events (the bus
    appends each to the audit log).
  - Not built: "shared node" (k3d has one node), degraded mode on approval
    in scenario 10 (waits on flags).
- Phase 3 on `muaz/phase3`: `gateway/blast.py` (upstream blast radius,
  forecast from replicas + maxUnavailable + measured pod startup, net
  benefit per policy), checklist step 5 real (asks a human when too costly
  or the graph is unknown and the action costs capacity; an approver can
  accept it), `Gateway.watchdog` (pending > 180 s with no heartbeat for
  30 s -> undo, `action_undone` reason watchdog, escalate; failed undo ->
  `watchdog_failed`, keeps blocking), `Gateway.expire_approvals`, `upkeep`
  loop every 5 s in the gateway lifespan, gateway reads Jaeger via
  `JAEGER_URL` (now required), brain sends `raise_limit` follow-up after a
  restart, approval kept when used while another action verifies, restart
  success card "MITIGATED, NOT FIXED". Re-page is the notifier's (T) and
  already exists. Proof: `uv run pytest` -> `267 passed`; `ruff check .`
  -> `All checks passed!`; `mypy ... chaos` -> `no issues found in 61
  source files`; mutation check (heartbeat skip, unknown-graph ask,
  asking bypass, surge rule) -> 5 FAIL, all caught. Fakes only.
- Phase 2 tools on `muaz/phase2-tools`: `revert_config` (env, from the
  journal entry's inverse, strategic merge), `restart_service`
  (restartedAt), `scale` (scale subresource, merge patch), `raise_limit`
  (one container, must raise, <= `max_memory`). Every body pins the live
  resourceVersion; params bounded in the policy step; undo restores the
  pre-action template or scales back. Proof: `uv run pytest` -> `246
  passed`; `ruff check .` -> `All checks passed!`; `mypy ... chaos` -> `no
  issues found in 60 source files`; `tests/test_tools.py` 7 pass. Mutation
  check (must-raise, bounds, scale undo, env-only revert) -> 4 FAIL, all
  caught. Fake API server only.
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

- Nothing running. All code for Phases 0 to 4 is written and tested with
  fakes. The next work depends on live results from A.

## Blocked / waiting on

- **Live cluster (A):** re-apply `k8s/admission-policy.yaml` and `k8s/admission-binding.yaml` (new
  policy `oncall-agent-flags`), then `./scripts/security_check.sh` (35 rows). Every `.env` needs
  `ONCALL_API_TOKEN` (chaos now refuses POSTs without it).
- **Live rerun (A):** after `muaz/verify-fixes` merges: `./scripts/smoke.sh`
  and `/chaos/flag-flip`. Expect `incident_resolved` for both.
- **LLM timeout (T):** both live calls ended `deadline_exceeded` at 30 s
  (deepseek-v4.1-flash). Rules still decide, so not blocking; T to pick a
  longer timeout, lower reasoning effort or another model.
- **Scenario 10 (A):** `/chaos/shared-outage` (Q6).
- Note: `kubectl apply -f k8s/` also tries `k8s/values.yaml` (Helm values)
  and prints a harmless error; apply the four RBAC/VAP files by name.
- Note: `scripts/smoke.sh` needs one manual `curl` approval (empty trust
  ledger -> the gateway asks).

## Decisions made (Muaz)

- `enable_degraded_mode`: stays refused (no feature-off flags in the shop).
- Data stores: human-approved `scale` only (RBAC `deployments/scale`).
- `ONCALL_REHEARSAL=1` lifts the per-hour action budget.
- LLM: OpenCode Go, model `deepseek-v4.1-flash`, through T's
  `DiagnosisService`; my own `brain/llm.py` removed.
- Approvals: allowlist only, gateway bound to 127.0.0.1, no shared secret.
- MCP: `mcp~=1.30.0` (2.x needs pydantic 2.12).
- `kubernetes~=36.0.3` (37 needs pydantic 2.13).
- Property tests: stdlib `random`, not Hypothesis.

## Next

1. Push + merge `muaz/plan-audit`; A re-applies `k8s/rbac-agent.yaml`.
2. A reruns `./scripts/smoke.sh` (bad deploy) and `/chaos/flag-flip`
   (scenario 3); expect `incident_resolved` for both.
3. Tick the Phase 1 and 2 exits only with passing live output.
4. Stretch (Phase 6) only after the Phase 4 exit works live.

## Notes for my next session

- The test cluster `oncall-test` was deleted at session end. Recreate with
  `k3d cluster create oncall-test --servers 1 --k3s-arg "--disable=traefik@server:*" --kubeconfig-update-default=false --kubeconfig-switch-context=false`
  so the default kube context stays `kind-muaz-foss`.
- Admission CEL pattern: `has(new) == has(old) && (!has(new) || new == old)`.
