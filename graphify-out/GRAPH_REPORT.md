# Graph Report - devhack2026  (2026-11-13)

## Corpus Check
- 119 files · ~61,904 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 5 file(s) not represented in the graph (top: (none) 3, .example 1, .lock 1)

## Summary
- 1201 nodes · 3132 edges · 68 communities (52 shown, 16 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 266 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `58a47886`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- NotifierState
- test_audit.py
- 6.4 Gateway (`gateway/`) [M] P0 unless marked
- test_bench.py
- DiagnosisService
- test_bench_recovery.py
- AGENTS.md
- CLAUDE.md
- 10. Build plan
- test_brain.py
- checklist.py
- brain/main.py
- Implementation Plan: the on-call agent that has to earn its autonomy
- FakeApps
- find_culprit
- models.py
- Observer
- test_observer.py
- test_verify_loop.py
- harm_check
- test_invariants.py
- 3. Environment setup
- 8. Testing
- test_bench_export.py
- 0. Scope and principles
- 11. Demo
- 1. System overview
- 4. Configuration files
- 5. Data model
- 9. Benchmark (`bench/`) [T] P1
- ActionRequest
- test_gateway.py
- Done (with proof)
- oncall-agent
- build_from_env
- HttpTrialServices
- journal.py
- test_verifier_safety.py
- connect
- security_check.sh
- make_kubeconfigs.sh
- install_shop.sh
- match
- setup_cluster.sh
- create_app
- test_kube_watch.py
- On-call agent: Twaha components
- json
- test_phase3.py
- test_tools.py
- charge.js
- Detector
- .observe
- Muaz [M]: tasks
- Anirudh [A]: architecture of my part
- blast.py
- test_rehearsal_credits_action_receipt_with_false_diagnosis
- TrialServices
- build_bad_payment.sh
- smoke.sh
- Shared context (all agents read and write this)
- Muaz [M]: state
- detector.py
- test_resume_counts_recorded_attempts_and_does_not_repeat_fault

## God Nodes (most connected - your core abstractions)
1. `ActionRequest` - 37 edges
2. `World` - 37 edges
3. `Gateway` - 35 edges
4. `connect()` - 34 edges
5. `GatewayDecision` - 34 edges
6. `DiagnosisService` - 33 edges
7. `action()` - 30 edges
8. `Incident` - 26 edges
9. `Done (with proof)` - 25 edges
10. `ReceiptStore` - 24 edges

## Surprising Connections (you probably didn't know these)
- `3.1 Prerequisites [A] P0` --references--> `kubectl()`  [INFERRED]
  IMPLEMENTATION.md → chaos/faults.py
- `6.1 Chaos panel (`chaos/`) [A] P0` --references--> `kubectl()`  [INFERRED]
  IMPLEMENTATION.md → chaos/faults.py
- `6.8 UI (`ui/`, Next.js) [A] P1` --references--> `kubectl()`  [INFERRED]
  IMPLEMENTATION.md → chaos/faults.py
- `9.2 Manual baseline (`manual_baseline.md`)` --references--> `kubectl()`  [INFERRED]
  IMPLEMENTATION.md → chaos/faults.py
- `Hard rules my code must keep` --references--> `kubectl()`  [INFERRED]
  team/anirudh/ARCHITECTURE.md → chaos/faults.py

## Import Cycles
- None detected.

## Communities (68 total, 16 thin omitted)

### Community 0 - "NotifierState"
Cohesion: 0.06
Nodes (20): Notifier, NotificationConsumer, ApprovalButton, ApprovalController, ApprovalView, DiscordNotifier, health(), lifespan() (+12 more)

### Community 1 - "test_audit.py"
Cohesion: 0.07
Nodes (38): AuditLog, canonical(), EventBus, verify(), active_bus(), create_events_router(), events(), stream() (+30 more)

### Community 2 - "6.4 Gateway (`gateway/`) [M] P0 unless marked"
Cohesion: 0.05
Nodes (43): create(), get(), set_state(), 6.1 Chaos panel (`chaos/`) [A] P0, 6.2.1 Baselines (`baselines.py`), 6.2.2 Detector (`detector.py`), 6.2.3 Kubernetes watch (`kube_watch.py`), 6.2.4 Change journal (`journal.py`) (+35 more)

### Community 3 - "test_bench.py"
Cohesion: 0.21
Nodes (9): Harness, measure(), TrialResult, FakeServices, test_disabled_harness_never_resets_or_injects(), test_failed_trial_persisted_and_next_trial_runs(), test_matching_pattern_wrong_culprit_is_not_correct(), observe() (+1 more)

### Community 4 - "DiagnosisService"
Cohesion: 0.06
Nodes (39): DiagnosisResult, DiagnosisService, InferenceProvider, InferenceRequest, InferenceResponse, ProviderError, OpenCodeGoAdapter, Diagnosis (+31 more)

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

### Community 9 - "test_brain.py"
Cohesion: 0.08
Nodes (33): downstream(), Brain, create_app(), _finished(), incidents(), analyse(), is_major(), shared_change() (+25 more)

### Community 10 - "checklist.py"
Cohesion: 0.14
Nodes (22): startup_seconds(), surge_ok(), forecast_text(), rv(), build_patch(), _flatten(), _h(), namespace_hash() (+14 more)

### Community 11 - "brain/main.py"
Cohesion: 0.06
Nodes (31): DependencyGraph, build_from_env(), lifespan(), require_env(), quarantine(), redact(), redact_value(), approvers_from_env() (+23 more)

### Community 12 - "Implementation Plan: the on-call agent that has to earn its autonomy"
Cohesion: 0.29
Nodes (6): 12. Risks and fallbacks, 13. Submission checklist, 14. Command cheat sheet, 2. Repository layout, 7. End-to-end flows (acceptance scenarios), Implementation Plan: the on-call agent that has to earn its autonomy

### Community 13 - "FakeApps"
Cohesion: 0.14
Nodes (7): FakeApps, FakeCore, merge(), Observer, Resp, rs(), template()

### Community 14 - "find_culprit"
Cohesion: 0.19
Nodes (8): deepest_unhealthy(), depth(), fetch_error_traces(), find_culprit(), from_traces(), is_error(), CulpritTest, trace()

### Community 15 - "models.py"
Cohesion: 0.08
Nodes (42): build_bundle(), change_evidence(), collect_k8s(), k8s_evidence(), log_evidence(), memory_ratio(), metric_evidence(), _span_error_text() (+34 more)

### Community 16 - "Observer"
Cohesion: 0.18
Nodes (4): load(), medians(), store(), Observer

### Community 17 - "test_observer.py"
Cohesion: 0.18
Nodes (13): require_env(), Backend, make(), prom_result(), test_brain_down_does_not_stop_detection(), handler(), test_endpoints(), test_nan_rows_are_dropped() (+5 more)

### Community 18 - "test_verify_loop.py"
Cohesion: 0.49
Nodes (10): executed(), healthy(), ledger(), sick(), test_early_abort_pauses_undoes_resumes(), test_human_change_during_verify_hands_off_without_undo(), test_no_recovery_undoes_and_escalates(), test_recovered_but_prediction_missed_is_right_by_accident() (+2 more)

### Community 19 - "harm_check"
Cohesion: 0.18
Nodes (8): harm_check(), ledger_effect(), service_score(), HarmCheckTest, health(), svc(), verification(), VerifierTest

### Community 20 - "test_invariants.py"
Cohesion: 0.17
Nodes (6): random_action(), Recorder, run_case(), SickObserver, test_generator_reaches_execution(), test_invariants_hold_for_random_cases()

### Community 21 - "3. Environment setup"
Cohesion: 0.33
Nodes (6): 3.1 Prerequisites [A] P0, 3.2 Cluster [A] P0, 3.3 The shop [A] P0, 3.4 The buggy payment image [A] P0, 3.5 Kubeconfigs for the three identities [M] P0, 3. Environment setup

### Community 22 - "8. Testing"
Cohesion: 0.40
Nodes (5): 8.1 Unit tests [M][T] P0, 8.2 Property-based tests (`test_invariants.py`, Hypothesis) [M] P1, 8.3 Red-team suite (`tests/redteam/`) [T] P1, 8.4 Smoke test (`scripts/smoke.sh`) [A] P0, 8. Testing

### Community 23 - "test_bench_export.py"
Cohesion: 0.12
Nodes (19): display(), export_report(), markdown(), timing_svg(), main(), summarize(), compare(), load_rows() (+11 more)

### Community 24 - "0. Scope and principles"
Cohesion: 0.50
Nodes (4): 0.1 What we are building, 0.2 Three rules everything follows, 0.3 Scope by priority, 0. Scope and principles

### Community 25 - "11. Demo"
Cohesion: 0.50
Nodes (4): 11.1 Pre-demo checklist, 11.2 Script, 11.3 Deck outline (8 to 10 slides), 11. Demo

### Community 26 - "1. System overview"
Cohesion: 0.50
Nodes (4): 1.1 Processes, 1.2 Data flow, 1.3 Internal event bus, 1. System overview

### Community 27 - "4. Configuration files"
Cohesion: 0.50
Nodes (4): 4.1 `config/services.yaml` [A] P0, 4.2 `config/policy.yaml` [M] P0, 4.3 `config/queries.yaml` [M] P0, 4. Configuration files

### Community 28 - "5. Data model"
Cohesion: 0.50
Nodes (4): 5.1 SQLite (`data/oncall.db`, WAL mode) [M] P0, 5.2 Shared schemas (`schemas/`, Pydantic) [T] P0, agreed in hour 1, 5.3 Event types (SSE and audit), 5. Data model

### Community 29 - "9. Benchmark (`bench/`) [T] P1"
Cohesion: 0.50
Nodes (4): 9.1 Harness (`harness.py`), 9.2 Manual baseline (`manual_baseline.md`), 9.3 Report (`report.py`), 9. Benchmark (`bench/`) [T] P1

### Community 30 - "ActionRequest"
Cohesion: 0.24
Nodes (10): Gateway, usage(), build_incident_card(), ActionRequest, GatewayDecision, Log (append-only, newest at bottom), Open questions, test_incident_card_variants() (+2 more)

### Community 32 - "test_gateway.py"
Cohesion: 0.25
Nodes (17): Phase 3: trust, humans, proof, action(), test_approval_rules(), test_bad_deploy_asks_then_rolls_back_on_approval(), test_budget_and_in_flight(), test_conflict_on_execute_hands_off_and_admission_denial_escalates(), test_dry_run_outside_template_escalates(), test_http_app_routes() (+9 more)

### Community 34 - "Done (with proof)"
Cohesion: 0.19
Nodes (6): Manual baseline, call_tool(), spec_hashes(), Verification, read(), Done (with proof)

### Community 37 - "build_from_env"
Cohesion: 0.25
Nodes (4): build_from_env(), create_app(), get_journal(), lifespan()

### Community 38 - "HttpTrialServices"
Cohesion: 0.18
Nodes (5): HttpTrialServices, main(), test_health_wait_requires_current_metrics_and_retries_startup(), test_stale_metrics_restart_the_entire_stability_window(), test_rehearsal_disabled_before_any_network_call()

### Community 39 - "journal.py"
Cohesion: 0.13
Nodes (16): check(), author(), _configmap_changes(), _containers(), current(), _deployment_changes(), entry(), insert() (+8 more)

### Community 41 - "test_verifier_safety.py"
Cohesion: 0.90
Nodes (4): service(), test_human_change_takes_priority_over_early_abort(), test_missing_service_cannot_confirm_recovery_after_prediction(), verification()

### Community 42 - "connect"
Cohesion: 0.11
Nodes (16): main(), summarize_ledger(), check(), counts(), eligible(), lower_bound(), record(), connect() (+8 more)

### Community 46 - "match"
Cohesion: 0.22
Nodes (10): _action(), latest_change_before_onset(), match(), to_bytes(), bounds(), check(), major_check(), change() (+2 more)

### Community 49 - "test_kube_watch.py"
Cohesion: 0.16
Nodes (17): bad_pods(), pod_bad(), run_watch(), service_of(), Tracker, _ts(), deployment(), FakeResp (+9 more)

### Community 50 - "On-call agent: Twaha components"
Cohesion: 0.25
Nodes (7): ts(), Benchmarks and adversarial checks, Discord notifier, Inference, On-call agent: Twaha components, Project graph, Setup and checks

### Community 51 - "json"
Cohesion: 0.06
Nodes (58): bad_deploy(), broken_config(), datastore_down(), flag_flip(), kubectl(), KubectlError, memory_leak(), read_flags() (+50 more)

### Community 52 - "test_phase3.py"
Cohesion: 0.19
Nodes (10): executed_and_parked(), FakeGraph, single_replica(), test_costly_action_asks_at_net_benefit_then_runs_after_approval(), test_failed_watchdog_undo_keeps_blocking(), test_restart_success_card_says_mitigated(), test_unknown_graph_with_capacity_cost_asks(), test_watchdog_leaves_ticking_verifier_alone() (+2 more)

### Community 53 - "test_tools.py"
Cohesion: 0.31
Nodes (9): container(), run_tool(), test_flag_tools_not_built_yet(), test_raise_limit_bounded_and_must_raise(), test_restart_sets_restarted_at_only(), test_revert_env_from_journal_inverse(), test_revert_without_env_entry_is_refused(), test_scale_uses_subresource_and_bounds() (+1 more)

### Community 54 - "charge.js"
Cohesion: 0.10
Nodes (14): { ATTR_ERROR_TYPE }, cardValidator, charge(), { context, propagation, trace, metrics, SpanStatusCode }, { FlagdProvider }, flagProvider, logger, LOYALTY_LEVEL (+6 more)

### Community 55 - "Detector"
Cohesion: 0.29
Nodes (3): Detector, det(), DetectorTest

### Community 57 - "Muaz [M]: tasks"
Cohesion: 0.29
Nodes (6): Muaz [M]: tasks, Never cut, Phase 0: foundations, Phase 2: the other failures and the checks, Phase 4: wide outages and measurement, Phase 6: stretch (only if Phase 4 exit is met early)

### Community 58 - "Anirudh [A]: architecture of my part"
Cohesion: 0.29
Nodes (6): Anirudh [A]: architecture of my part, Flow through my parts, Hard rules my code must keep, What I need from others, What I own, What I provide to others

### Community 59 - "blast.py"
Cohesion: 0.53
Nodes (5): upstream(), blast_radius(), forecast_added_seconds(), net_benefit(), test_blast_radius_forecast_and_net_benefit()

### Community 60 - "test_rehearsal_credits_action_receipt_with_false_diagnosis"
Cohesion: 0.25
Nodes (5): test_rehearsal_credits_action_receipt_with_false_diagnosis(), test_rehearsal_hooks_only_when_enabled(), handle(), test_rehearsal_refusal_stops_credit(), test_rehearsal_without_receipt_never_submits_credit()

### Community 64 - "Shared context (all agents read and write this)"
Cohesion: 0.50
Nodes (3): Rules for agents, Shared context (all agents read and write this), VERIFY results (§3.3, Phase 0)

### Community 65 - "Muaz [M]: state"
Cohesion: 0.33
Nodes (5): Blocked / waiting on, In progress, Muaz [M]: state, Next, Notes for my next session

## Knowledge Gaps
- **1 isolated node(s):** `oncall-agent`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 331 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **16 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `kubectl()` connect `json` to `6.4 Gateway (`gateway/`) [M] P0 unless marked`, `3. Environment setup`, `Anirudh [A]: architecture of my part`, `9. Benchmark (`bench/`) [T] P1`, `ActionRequest`?**
  _High betweenness centrality (0.083) - this node is a cross-community bridge._
- **Are the 14 inferred relationships involving `ActionRequest` (e.g. with `call_tool()` and `DiagnosisResult`) actually correct?**
  _`ActionRequest` has 14 INFERRED edges - model-reasoned connections that need verification._
- **What connects `oncall-agent` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `NotifierState` be split into smaller, more focused modules?**
  _Cohesion score 0.06467661691542288 - nodes in this community are weakly interconnected._
- **Why does `Done (with proof)` connect `Done (with proof)` to `test_audit.py`, `Muaz [M]: state`, `DiagnosisService`, `journal.py`, `test_brain.py`, `connect`, `checklist.py`, `find_culprit`, `models.py`, `Observer`, `harm_check`, `charge.js`, `ActionRequest`?**
  _High betweenness centrality (0.068) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `World` (e.g. with `Gateway` and `ReceiptStore`) actually correct?**
  _`World` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_audit.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07191316146540028 - nodes in this community are weakly interconnected._