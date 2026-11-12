# Graph Report - devhack2026  (2026-11-13)

## Corpus Check
- 114 files · ~55,933 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 5 file(s) not represented in the graph (top: (none) 3, .example 1, .lock 1)

## Summary
- 1120 nodes · 2845 edges · 57 communities (44 shown, 13 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 248 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `bfbc838d`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- NotifierState
- test_audit.py
- 6.4 Gateway (`gateway/`) [M] P0 unless marked
- test_bench.py
- find_culprit
- test_bench_recovery.py
- AGENTS.md
- CLAUDE.md
- 10. Build plan
- DiagnosisService
- dryrun.py
- create_app
- Implementation Plan: the on-call agent that has to earn its autonomy
- test_brain.py
- kubectl
- models.py
- test_observer.py
- 6. Component specifications
- .observe
- HttpTrialServices
- FakeApps
- 3. Environment setup
- 8. Testing
- 6.3 Brain (`brain/`) [M] P0 unless marked
- 0. Scope and principles
- 11. Demo
- test_tools.py
- Anirudh [A]: architecture of my part
- 5. Data model
- 9. Benchmark (`bench/`) [T] P1
- Anirudh [A]: state
- test_gateway.py
- 6.2 Observer (`observer/`) [M] P0
- oncall-agent
- ActionRequest
- test_kube_watch.py
- test_rehearsal_credits_action_receipt_with_false_diagnosis
- checklist.py
- security_check.sh
- make_kubeconfigs.sh
- install_shop.sh
- match
- setup_cluster.sh
- test_verify_loop.py
- json
- TrialServices
- charge.js
- test_resume_counts_recorded_attempts_and_does_not_repeat_fault
- Twaha [T]: tasks
- Muaz [M]: tasks
- build_mcp
- build_bad_payment.sh
- smoke.sh
- Muaz [M]: architecture of my part

## God Nodes (most connected - your core abstractions)
1. `ActionRequest` - 37 edges
2. `connect()` - 34 edges
3. `GatewayDecision` - 34 edges
4. `DiagnosisService` - 33 edges
5. `Gateway` - 32 edges
6. `ReceiptStore` - 24 edges
7. `Incident` - 24 edges
8. `World` - 24 edges
9. `HttpTrialServices` - 23 edges
10. `Receipt` - 23 edges

## Surprising Connections (you probably didn't know these)
- `3.1 Prerequisites [A] P0` --references--> `kubectl()`  [INFERRED]
  IMPLEMENTATION.md → chaos/faults.py
- `6.8 UI (`ui/`, Next.js) [A] P1` --references--> `kubectl()`  [INFERRED]
  IMPLEMENTATION.md → chaos/faults.py
- `9.2 Manual baseline (`manual_baseline.md`)` --references--> `kubectl()`  [INFERRED]
  IMPLEMENTATION.md → chaos/faults.py
- `Hard rules my code must keep` --references--> `kubectl()`  [INFERRED]
  team/anirudh/ARCHITECTURE.md → chaos/faults.py
- `Notes for my next session` --references--> `kubectl()`  [INFERRED]
  team/anirudh/STATE.md → chaos/faults.py

## Import Cycles
- None detected.

## Communities (57 total, 13 thin omitted)

### Community 0 - "NotifierState"
Cohesion: 0.07
Nodes (19): Notifier, NotificationConsumer, ApprovalButton, ApprovalController, ApprovalView, DiscordNotifier, lifespan(), load_approvers() (+11 more)

### Community 1 - "test_audit.py"
Cohesion: 0.08
Nodes (37): AuditLog, canonical(), EventBus, verify(), active_bus(), create_events_router(), events(), stream() (+29 more)

### Community 2 - "6.4 Gateway (`gateway/`) [M] P0 unless marked"
Cohesion: 0.17
Nodes (12): 6.4.10 Watchdog (`watchdog.py`) P1, 6.4.11 One retry (P2), 6.4.1 MCP server (`mcp_server.py`), 6.4.2 The checklist (`checklist.py`), 6.4.3 Dry run and snapshot (`dryrun.py`), 6.4.4 Blast radius and net benefit (`blast.py`) P1, 6.4.5 Freshness (`freshness.py`), 6.4.6 Trust gate (`trust.py`) P1 (+4 more)

### Community 3 - "test_bench.py"
Cohesion: 0.20
Nodes (10): Harness, measure(), TrialResult, FakeServices, test_disabled_harness_never_resets_or_injects(), test_failed_trial_persisted_and_next_trial_runs(), test_manual_comparison_preserves_missing_measurements(), test_matching_pattern_wrong_culprit_is_not_correct() (+2 more)

### Community 4 - "find_culprit"
Cohesion: 0.19
Nodes (8): deepest_unhealthy(), depth(), fetch_error_traces(), find_culprit(), from_traces(), is_error(), CulpritTest, trace()

### Community 5 - "test_bench_recovery.py"
Cohesion: 0.15
Nodes (10): stream(), test_failed_attempts_count_toward_resume_target(), test_reconnect_resumes_cursor_and_ignores_duplicate_events(), handle(), test_replayed_approval_does_not_repeat_post(), handle(), test_resume_corrupt_file_fails_before_reset(), test_timeout_keeps_detection_and_diagnosis_measurements() (+2 more)

### Community 6 - "AGENTS.md"
Cohesion: 0.18
Nodes (10): Code comments, Commands, Commits, Communication, Dependencies, Git safety, graphify, Secrets (+2 more)

### Community 7 - "CLAUDE.md"
Cohesion: 0.18
Nodes (10): Code comments, Commands, Commits, Communication, Dependencies, Git safety, graphify, Secrets (+2 more)

### Community 8 - "10. Build plan"
Cohesion: 0.22
Nodes (9): 10. Build plan, Cut order if time runs short, Phase 0: foundations (about 2 h, everyone), Phase 1: the spine, one failure end to end (about 5 h) P0, Phase 2: the other failures and the checks (about 5 h) P0, Phase 3: trust, humans, proof (about 5 h) P1, Phase 4: wide outages and measurement (about 4 h) P1, Phase 5: freeze and polish (about 4 h) (+1 more)

### Community 9 - "DiagnosisService"
Cohesion: 0.06
Nodes (48): DiagnosisResult, DiagnosisService, InferenceProvider, InferenceRequest, InferenceResponse, ProviderError, OpenCodeGoAdapter, quarantine() (+40 more)

### Community 10 - "dryrun.py"
Cohesion: 0.14
Nodes (19): rv(), build_patch(), _flatten(), _h(), outside_allowed(), previous_template(), rollback_patch(), _single_container() (+11 more)

### Community 11 - "create_app"
Cohesion: 0.18
Nodes (4): create_app(), lifespan(), test_brain_mcp_client_reaches_real_gateway(), test_rehearsal_route_needs_flag()

### Community 12 - "Implementation Plan: the on-call agent that has to earn its autonomy"
Cohesion: 0.13
Nodes (14): 12. Risks and fallbacks, 13. Submission checklist, 14. Command cheat sheet, 1.1 Processes, 1.2 Data flow, 1.3 Internal event bus, 1. System overview, 2. Repository layout (+6 more)

### Community 13 - "test_brain.py"
Cohesion: 0.09
Nodes (20): DependencyGraph, Brain, create_app(), _finished(), incidents(), diagnosis_json(), FakeProvider, jaeger_trace() (+12 more)

### Community 14 - "kubectl"
Cohesion: 0.18
Nodes (10): kubectl(), 6.1 Chaos panel (`chaos/`) [A] P0, Anirudh [A]: tasks, Never cut, Phase 0: foundations, Phase 1: the spine, Phase 2: the other failures, Phase 3: UI (+2 more)

### Community 15 - "models.py"
Cohesion: 0.07
Nodes (45): build_bundle(), change_evidence(), collect_k8s(), k8s_evidence(), log_evidence(), memory_ratio(), metric_evidence(), _span_error_text() (+37 more)

### Community 16 - "test_observer.py"
Cohesion: 0.06
Nodes (24): load(), medians(), store(), Detector, fetch_readings(), prom_query(), create_app(), lifespan() (+16 more)

### Community 17 - "6. Component specifications"
Cohesion: 0.18
Nodes (11): 6.5.1 `rbac-reader.yaml`, 6.5.3 `admission-policy.yaml`, 6.5.4 `admission-binding.yaml`, 6.5.5 Acceptance tests for the security layer (do these on day one), 6.5 Kubernetes security manifests (`k8s/`) [M] P0, 6.6 Notifier (`notifier/`) [T] P1, 6.7.1 Incident card, 6.7.2 Audit log (`data/audit.jsonl`) (+3 more)

### Community 19 - "HttpTrialServices"
Cohesion: 0.18
Nodes (5): HttpTrialServices, main(), test_health_wait_requires_current_metrics_and_retries_startup(), test_stale_metrics_restart_the_entire_stability_window(), test_rehearsal_disabled_before_any_network_call()

### Community 20 - "FakeApps"
Cohesion: 0.16
Nodes (5): FakeApps, FakeCore, merge(), Observer, Resp

### Community 21 - "3. Environment setup"
Cohesion: 0.33
Nodes (6): 3.1 Prerequisites [A] P0, 3.2 Cluster [A] P0, 3.3 The shop [A] P0, 3.4 The buggy payment image [A] P0, 3.5 Kubeconfigs for the three identities [M] P0, 3. Environment setup

### Community 22 - "8. Testing"
Cohesion: 0.40
Nodes (5): 8.1 Unit tests [M][T] P0, 8.2 Property-based tests (`test_invariants.py`, Hypothesis) [M] P1, 8.3 Red-team suite (`tests/redteam/`) [T] P1, 8.4 Smoke test (`scripts/smoke.sh`) [A] P0, 8. Testing

### Community 23 - "6.3 Brain (`brain/`) [M] P0 unless marked"
Cohesion: 0.22
Nodes (9): 6.3.1 Dependency graph (`graph.py`), 6.3.2 Culprit (`culprit.py`), 6.3.3 Major-incident analysis (`major.py`) P1, 6.3.4 Evidence bundle (`bundle.py`), 6.3.5 Redaction and quarantine (`redact.py`), 6.3.6 Rules (`rules.py`), 6.3.7 Claude call (`llm.py`), 6.3.8 Orchestration (`main.py`) (+1 more)

### Community 24 - "0. Scope and principles"
Cohesion: 0.50
Nodes (4): 0.1 What we are building, 0.2 Three rules everything follows, 0.3 Scope by priority, 0. Scope and principles

### Community 25 - "11. Demo"
Cohesion: 0.50
Nodes (4): 11.1 Pre-demo checklist, 11.2 Script, 11.3 Deck outline (8 to 10 slides), 11. Demo

### Community 26 - "test_tools.py"
Cohesion: 0.43
Nodes (6): run_tool(), test_flag_tools_not_built_yet(), test_restart_sets_restarted_at_only(), test_revert_without_env_entry_is_refused(), test_scale_uses_subresource_and_bounds(), test_undo_of_scale_scales_back()

### Community 27 - "Anirudh [A]: architecture of my part"
Cohesion: 0.29
Nodes (6): Anirudh [A]: architecture of my part, Flow through my parts, Hard rules my code must keep, What I need from others, What I own, What I provide to others

### Community 28 - "5. Data model"
Cohesion: 0.50
Nodes (4): 5.1 SQLite (`data/oncall.db`, WAL mode) [M] P0, 5.2 Shared schemas (`schemas/`, Pydantic) [T] P0, agreed in hour 1, 5.3 Event types (SSE and audit), 5. Data model

### Community 29 - "9. Benchmark (`bench/`) [T] P1"
Cohesion: 0.50
Nodes (4): 9.1 Harness (`harness.py`), 9.2 Manual baseline (`manual_baseline.md`), 9.3 Report (`report.py`), 9. Benchmark (`bench/`) [T] P1

### Community 30 - "Anirudh [A]: state"
Cohesion: 0.29
Nodes (6): Anirudh [A]: state, Blocked / waiting on, Done (with proof), In progress, Next, Notes for my next session

### Community 32 - "test_gateway.py"
Cohesion: 0.24
Nodes (16): Phase 3: trust, humans, proof, action(), test_approval_rules(), test_bad_deploy_asks_then_rolls_back_on_approval(), test_budget_and_in_flight(), test_conflict_on_execute_hands_off_and_admission_denial_escalates(), test_dry_run_outside_template_escalates(), test_http_app_routes() (+8 more)

### Community 34 - "6.2 Observer (`observer/`) [M] P0"
Cohesion: 0.33
Nodes (6): 6.2.1 Baselines (`baselines.py`), 6.2.2 Detector (`detector.py`), 6.2.3 Kubernetes watch (`kube_watch.py`), 6.2.4 Change journal (`journal.py`), 6.2.5 Flags (`flags.py`), 6.2 Observer (`observer/`) [M] P0

### Community 38 - "ActionRequest"
Cohesion: 0.06
Nodes (33): Manual baseline, call_tool(), create(), get(), set_state(), Gateway, namespace_hash(), spec_hashes() (+25 more)

### Community 39 - "test_kube_watch.py"
Cohesion: 0.07
Nodes (35): check(), author(), _configmap_changes(), _containers(), current(), _deployment_changes(), entry(), insert() (+27 more)

### Community 40 - "test_rehearsal_credits_action_receipt_with_false_diagnosis"
Cohesion: 0.25
Nodes (5): test_rehearsal_credits_action_receipt_with_false_diagnosis(), test_rehearsal_hooks_only_when_enabled(), handle(), test_rehearsal_refusal_stops_credit(), test_rehearsal_without_receipt_never_submits_credit()

### Community 42 - "checklist.py"
Cohesion: 0.07
Nodes (25): summarize_ledger(), build_from_env(), lifespan(), require_env(), approvers_from_env(), read_events(), build_from_env(), Decide (+17 more)

### Community 46 - "match"
Cohesion: 0.14
Nodes (16): _action(), latest_change_before_onset(), match(), to_bytes(), bounds(), check(), usage(), Benchmarks and adversarial checks (+8 more)

### Community 50 - "test_verify_loop.py"
Cohesion: 0.30
Nodes (11): executed(), healthy(), ledger(), Script, sick(), test_early_abort_pauses_undoes_resumes(), test_human_change_during_verify_hands_off_without_undo(), test_no_recovery_undoes_and_escalates() (+3 more)

### Community 51 - "json"
Cohesion: 0.06
Nodes (45): display(), export_report(), markdown(), timing_svg(), main(), summarize(), compare(), load_rows() (+37 more)

### Community 54 - "charge.js"
Cohesion: 0.10
Nodes (14): { ATTR_ERROR_TYPE }, cardValidator, charge(), { context, propagation, trace, metrics, SpanStatusCode }, { FlagdProvider }, flagProvider, logger, LOYALTY_LEVEL (+6 more)

### Community 58 - "Twaha [T]: tasks"
Cohesion: 0.22
Nodes (8): Evidence and next gate (2026-11-13), Never cut, Phase 1: the spine, Phase 2: checks, Phase 3: humans and proof, Phase 4: measurement, Phase 5: freeze, Twaha [T]: tasks

### Community 59 - "Muaz [M]: tasks"
Cohesion: 0.25
Nodes (7): Muaz [M]: tasks, Never cut, Phase 0: foundations, Phase 1: the spine, one failure end to end, Phase 2: the other failures and the checks, Phase 4: wide outages and measurement, Phase 6: stretch (only if Phase 4 exit is met early)

### Community 61 - "build_mcp"
Cohesion: 0.29
Nodes (4): build_mcp(), make(), test_mcp_exposes_six_tools_with_actable_targets_only(), submit()

### Community 64 - "Muaz [M]: architecture of my part"
Cohesion: 0.29
Nodes (6): Flow through my code, Hard rules my code must keep, Muaz [M]: architecture of my part, What I need from others, What I own, What I provide to others

## Knowledge Gaps
- **1 isolated node(s):** `oncall-agent`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 322 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **13 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `kubectl()` connect `kubectl` to `ActionRequest`, `6. Component specifications`, `json`, `3. Environment setup`, `Anirudh [A]: architecture of my part`, `9. Benchmark (`bench/`) [T] P1`, `Anirudh [A]: state`?**
  _High betweenness centrality (0.088) - this node is a cross-community bridge._
- **Are the 14 inferred relationships involving `ActionRequest` (e.g. with `call_tool()` and `DiagnosisResult`) actually correct?**
  _`ActionRequest` has 14 INFERRED edges - model-reasoned connections that need verification._
- **What connects `oncall-agent` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `NotifierState` be split into smaller, more focused modules?**
  _Cohesion score 0.06597222222222222 - nodes in this community are weakly interconnected._
- **Why does `ActionRequest` connect `ActionRequest` to `DiagnosisService`, `checklist.py`, `dryrun.py`, `create_app`, `test_brain.py`, `models.py`, `test_verify_loop.py`, `8. Testing`?**
  _High betweenness centrality (0.061) - this node is a cross-community bridge._
- **Are the 10 inferred relationships involving `GatewayDecision` (e.g. with `HttpTrialServices` and `Brain`) actually correct?**
  _`GatewayDecision` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_audit.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0764423076923077 - nodes in this community are weakly interconnected._