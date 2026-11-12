# Graph Report - devhack2026  (2026-11-13)

## Corpus Check
- 152 files · ~66,265 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 20 file(s) not represented in the graph (top: .css 15, (none) 3, .example 1)

## Summary
- 1585 nodes · 3603 edges · 106 communities (86 shown, 20 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 243 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `67527a9e`
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
- find_culprit
- test_previous_template_and_diff_helpers
- checklist.py
- Implementation Plan: the on-call agent that has to earn its autonomy
- FakeApps
- ActionRequest
- pytest
- test_observer.py
- NotificationConsumer
- test_verify_loop.py
- test_kube_watch.py
- pytest
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
- connect
- oncall-agent
- build_from_env
- HttpTrialServices
- journal.py
- services
- trust_report.py
- security_check.sh
- make_kubeconfigs.sh
- install_shop.sh
- package.json
- setup_cluster.sh
- create_app
- test_run_watch_relists_after_error
- test_verify_loop.py
- test_chaos.py
- test_phase3.py
- test_tools.py
- charge.js
- det
- .observe
- Muaz [M]: tasks
- Muaz [M]: tasks
- chaos-view.tsx
- test_rehearsal_credits_action_receipt_with_false_diagnosis
- TrialServices
- build_bad_payment.sh
- smoke.sh
- components
- Done (with proof)
- spec
- test_resume_counts_recorded_attempts_and_does_not_repeat_fault
- RoleBinding oncall-agent
- RoleBinding oncall-reader
- live.ts
- live-view.tsx
- redact_value
- harm_check
- bundle.py
- notifier/main.py
- compilerOptions
- ValidatingAdmissionPolicyBinding oncall-agent-fields
- Card
- test_integration.py
- verify
- models.py
- words
- AuditLog
- discord_bot.py
- argparse
- policy.yaml
- tools
- Anirudh [A]: tasks
- stage-strip.tsx
- summarize_ledger
- DependencyGraph
- baselines.py
- demo.ts
- detection
- scale
- test_verifier_safety.py
- approval
- major_incident
- raise_limit
- trust
- net_benefit
- restart_service
- Decide
- manual_baseline.md
- ui/AGENTS.md

## God Nodes (most connected - your core abstractions)
1. `ActionRequest` - 37 edges
2. `Gateway` - 35 edges
3. `connect()` - 34 edges
4. `GatewayDecision` - 34 edges
5. `DiagnosisService` - 33 edges
6. `World` - 31 edges
7. `FakeKubectl` - 27 edges
8. `action()` - 25 edges
9. `ReceiptStore` - 24 edges
10. `HttpTrialServices` - 23 edges

## Surprising Connections (you probably didn't know these)
- `5.3 Event types (SSE and audit)` --references--> `harm_check()`  [INFERRED]
  IMPLEMENTATION.md → gateway/verifier.py
- `8.2 Property-based tests (`test_invariants.py`, Hypothesis) [M] P1` --references--> `ActionRequest`  [INFERRED]
  IMPLEMENTATION.md → schemas/models.py
- `Discord notifier` --references--> `GatewayDecision`  [INFERRED]
  README.md → schemas/models.py
- `Done (with proof)` --references--> `DiagnosisService`  [INFERRED]
  team/muaz/STATE.md → brain/llm.py
- `Phase 2: the other failures and the checks` --references--> `DiagnosisService`  [INFERRED]
  team/muaz/TASK.md → brain/llm.py

## Import Cycles
- None detected.

## Communities (106 total, 20 thin omitted)

### Community 0 - "NotifierState"
Cohesion: 0.19
Nodes (7): ApprovalController, NotifierState, test_unauthorized_approval_never_calls_gateway(), test_approval_auth_expiry_duplicate_and_gateway_refusal(), test_gateway_refusal_does_not_record_approval(), test_repage_expiry_and_persistent_buttons(), test_success_status_with_refusal_body_is_not_approval()

### Community 1 - "test_audit.py"
Cohesion: 0.19
Nodes (15): build_card(), build_incident_card(), create_receipts_router(), get(), ReceiptStore, Gateway mounting, Receipt, Log (append-only, newest at bottom) (+7 more)

### Community 2 - "6.4 Gateway (`gateway/`) [M] P0 unless marked"
Cohesion: 0.05
Nodes (40): 6.1 Chaos panel (`chaos/`) [A] P0, 6.2.1 Baselines (`baselines.py`), 6.2.2 Detector (`detector.py`), 6.2.3 Kubernetes watch (`kube_watch.py`), 6.2.4 Change journal (`journal.py`), 6.2.5 Flags (`flags.py`), 6.2 Observer (`observer/`) [M] P0, 6.3.1 Dependency graph (`graph.py`) (+32 more)

### Community 3 - "test_bench.py"
Cohesion: 0.21
Nodes (9): Harness, measure(), TrialResult, FakeServices, test_disabled_harness_never_resets_or_injects(), test_failed_trial_persisted_and_next_trial_runs(), test_matching_pattern_wrong_culprit_is_not_correct(), observe() (+1 more)

### Community 4 - "DiagnosisService"
Cohesion: 0.07
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

### Community 9 - "find_culprit"
Cohesion: 0.15
Nodes (18): create_app(), _finished(), incidents(), diagnosis_json(), FakeProvider, jaeger_trace(), make(), submit() (+10 more)

### Community 10 - "test_previous_template_and_diff_helpers"
Cohesion: 0.07
Nodes (35): upstream(), _action(), latest_change_before_onset(), match(), to_bytes(), blast_radius(), forecast_added_seconds(), net_benefit() (+27 more)

### Community 11 - "checklist.py"
Cohesion: 0.12
Nodes (11): build_from_env(), lifespan(), require_env(), approvers_from_env(), read_events(), build_from_env(), lifespan(), require_env() (+3 more)

### Community 12 - "Implementation Plan: the on-call agent that has to earn its autonomy"
Cohesion: 0.29
Nodes (6): 12. Risks and fallbacks, 13. Submission checklist, 14. Command cheat sheet, 2. Repository layout, 7. End-to-end flows (acceptance scenarios), Implementation Plan: the on-call agent that has to earn its autonomy

### Community 13 - "FakeApps"
Cohesion: 0.16
Nodes (5): FakeApps, FakeCore, merge(), Observer, Resp

### Community 14 - "ActionRequest"
Cohesion: 0.22
Nodes (7): deepest_unhealthy(), depth(), find_culprit(), from_traces(), is_error(), CulpritTest, trace()

### Community 15 - "pytest"
Cohesion: 0.12
Nodes (18): Cause, Event, Model, Prediction, Contracts (agreed interfaces between owners), Open questions, Rules for agents, Shared context (all agents read and write this) (+10 more)

### Community 16 - "test_observer.py"
Cohesion: 0.18
Nodes (4): Detector, fetch_readings(), prom_query(), Observer

### Community 17 - "NotificationConsumer"
Cohesion: 0.18
Nodes (13): require_env(), Backend, make(), prom_result(), test_brain_down_does_not_stop_detection(), handler(), test_endpoints(), test_nan_rows_are_dropped() (+5 more)

### Community 18 - "test_verify_loop.py"
Cohesion: 0.28
Nodes (12): test_restart_success_card_says_mitigated(), executed(), healthy(), ledger(), Script, sick(), test_early_abort_pauses_undoes_resumes(), test_human_change_during_verify_hands_off_without_undo() (+4 more)

### Community 19 - "test_kube_watch.py"
Cohesion: 0.23
Nodes (14): bad_pods(), pod_bad(), run_watch(), service_of(), Tracker, _ts(), deployment(), iso() (+6 more)

### Community 20 - "pytest"
Cohesion: 0.25
Nodes (4): Brain, Incident, action(), bundle()

### Community 21 - "3. Environment setup"
Cohesion: 0.33
Nodes (6): 3.1 Prerequisites [A] P0, 3.2 Cluster [A] P0, 3.3 The shop [A] P0, 3.4 The buggy payment image [A] P0, 3.5 Kubeconfigs for the three identities [M] P0, 3. Environment setup

### Community 22 - "8. Testing"
Cohesion: 0.40
Nodes (5): 8.1 Unit tests [M][T] P0, 8.2 Property-based tests (`test_invariants.py`, Hypothesis) [M] P1, 8.3 Red-team suite (`tests/redteam/`) [T] P1, 8.4 Smoke test (`scripts/smoke.sh`) [A] P0, 8. Testing

### Community 23 - "test_bench_export.py"
Cohesion: 0.17
Nodes (16): display(), export_report(), markdown(), timing_svg(), compare(), load_rows(), main(), summarize() (+8 more)

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
Cohesion: 0.19
Nodes (10): create(), get(), set_state(), forecast_text(), Gateway, usage(), ActionRequest, GatewayDecision (+2 more)

### Community 32 - "test_gateway.py"
Cohesion: 0.26
Nodes (15): Phase 3: trust, humans, proof, action(), test_approval_rules(), test_bad_deploy_asks_then_rolls_back_on_approval(), test_budget_and_in_flight(), test_conflict_on_execute_hands_off_and_admission_denial_escalates(), test_dry_run_outside_template_escalates(), test_http_app_routes() (+7 more)

### Community 34 - "connect"
Cohesion: 0.21
Nodes (6): Verification, connect(), DbTest, health(), test_resource_rule_actions_keep_different_approval_eligibility(), test_verified_outcome_controls_persisted_trust_and_card()

### Community 37 - "build_from_env"
Cohesion: 0.29
Nodes (3): build_from_env(), create_app(), lifespan()

### Community 38 - "HttpTrialServices"
Cohesion: 0.18
Nodes (5): HttpTrialServices, main(), test_health_wait_requires_current_metrics_and_retries_startup(), test_stale_metrics_restart_the_entire_stability_window(), test_rehearsal_disabled_before_any_network_call()

### Community 39 - "journal.py"
Cohesion: 0.13
Nodes (18): check(), author(), _configmap_changes(), _containers(), current(), _deployment_changes(), entry(), insert() (+10 more)

### Community 41 - "services"
Cohesion: 0.05
Nodes (40): actable, critical, kind, actable, critical, kind, actable, critical (+32 more)

### Community 42 - "trust_report.py"
Cohesion: 0.24
Nodes (6): check(), counts(), eligible(), lower_bound(), record(), TrustTest

### Community 46 - "package.json"
Cohesion: 0.06
Nodes (34): next, react-dom, @types/node, @types/react, @types/react-dom, typescript, metadata, mono (+26 more)

### Community 48 - "create_app"
Cohesion: 0.13
Nodes (5): create_app(), build_mcp(), make(), test_brain_mcp_client_reaches_real_gateway(), test_rehearsal_route_needs_flag()

### Community 49 - "test_run_watch_relists_after_error"
Cohesion: 0.33
Nodes (3): FakeResp, test_run_watch_relists_after_error(), list_fn()

### Community 50 - "test_verify_loop.py"
Cohesion: 0.29
Nodes (6): Benchmarks and adversarial checks, Discord notifier, Inference, On-call agent: Twaha components, Project graph, Setup and checks

### Community 51 - "test_chaos.py"
Cohesion: 0.06
Nodes (59): bad_deploy(), broken_config(), datastore_down(), flag_flip(), kubectl(), KubectlError, memory_leak(), raw_kubectl() (+51 more)

### Community 52 - "test_phase3.py"
Cohesion: 0.31
Nodes (8): executed_and_parked(), FakeGraph, single_replica(), test_costly_action_asks_at_net_benefit_then_runs_after_approval(), test_failed_watchdog_undo_keeps_blocking(), test_unknown_graph_with_capacity_cost_asks(), test_watchdog_leaves_ticking_verifier_alone(), test_watchdog_undoes_silent_verification()

### Community 53 - "test_tools.py"
Cohesion: 0.31
Nodes (9): container(), run_tool(), test_flag_tools_not_built_yet(), test_raise_limit_bounded_and_must_raise(), test_restart_sets_restarted_at_only(), test_revert_env_from_journal_inverse(), test_revert_without_env_entry_is_refused(), test_scale_uses_subresource_and_bounds() (+1 more)

### Community 54 - "charge.js"
Cohesion: 0.10
Nodes (13): { ATTR_ERROR_TYPE }, cardValidator, charge(), { context, propagation, trace, metrics, SpanStatusCode }, { FlagdProvider }, flagProvider, LOYALTY_LEVEL, meter (+5 more)

### Community 57 - "Muaz [M]: tasks"
Cohesion: 0.25
Nodes (7): Muaz [M]: tasks, Never cut, Phase 0: foundations, Phase 1: the spine, one failure end to end, Phase 2: the other failures and the checks, Phase 4: wide outages and measurement, Phase 6: stretch (only if Phase 4 exit is met early)

### Community 58 - "Muaz [M]: tasks"
Cohesion: 0.29
Nodes (6): Anirudh [A]: architecture of my part, Flow through my parts, Hard rules my code must keep, What I need from others, What I own, What I provide to others

### Community 59 - "chaos-view.tsx"
Cohesion: 0.12
Nodes (21): ChaosPage(), metadata, ChaosView(), FaultBoard(), fire(), FAULTS, Gauge(), Health() (+13 more)

### Community 60 - "test_rehearsal_credits_action_receipt_with_false_diagnosis"
Cohesion: 0.25
Nodes (5): test_rehearsal_credits_action_receipt_with_false_diagnosis(), test_rehearsal_hooks_only_when_enabled(), handle(), test_rehearsal_refusal_stops_credit(), test_rehearsal_without_receipt_never_submits_credit()

### Community 64 - "components"
Cohesion: 0.06
Nodes (30): enabled, enabled, replicas, components, agent, chatbot, checkout, mcp (+22 more)

### Community 65 - "Done (with proof)"
Cohesion: 0.12
Nodes (10): fetch_error_traces(), call_tool(), downstream(), spec_hashes(), Blocked / waiting on, Done (with proof), In progress, Muaz [M]: state (+2 more)

### Community 66 - "spec"
Cohesion: 0.08
Nodes (27): ValidatingAdmissionPolicy oncall-agent-fields, ValidatingAdmissionPolicy oncall-agent-scale, expression, name, resourceRules, name, apiGroups, apiVersions (+19 more)

### Community 68 - "RoleBinding oncall-agent"
Cohesion: 0.08
Nodes (27): ServiceAccount oncall-agent, Role oncall-agent, RoleBinding oncall-agent, name, namespace, apiVersion, kind, metadata (+19 more)

### Community 69 - "RoleBinding oncall-reader"
Cohesion: 0.09
Nodes (26): ServiceAccount oncall-reader, Role oncall-reader, RoleBinding oncall-reader, name, namespace, apiVersion, kind, metadata (+18 more)

### Community 70 - "live.ts"
Cohesion: 0.12
Nodes (20): advance(), apply(), blank(), BusRecord, Card, close(), EVENT_TYPES, initialState (+12 more)

### Community 71 - "live-view.tsx"
Cohesion: 0.15
Nodes (15): react, LivePage(), Blast(), Evidence(), LINK_COPY, LiveView(), Outcome(), Yes() (+7 more)

### Community 72 - "redact_value"
Cohesion: 0.15
Nodes (15): quarantine(), redact(), redact_value(), clean(), Flow through my parts, Hard rules my code must keep, Twaha [T]: architecture of my part, What I need from others (+7 more)

### Community 73 - "harm_check"
Cohesion: 0.18
Nodes (8): harm_check(), ledger_effect(), service_score(), HarmCheckTest, health(), svc(), verification(), VerifierTest

### Community 74 - "bundle.py"
Cohesion: 0.24
Nodes (18): build_bundle(), change_evidence(), collect_k8s(), k8s_evidence(), log_evidence(), memory_ratio(), metric_evidence(), _span_error_text() (+10 more)

### Community 75 - "notifier/main.py"
Cohesion: 0.17
Nodes (8): NotificationConsumer, health(), lifespan(), load_approvers(), required(), test_consumer_restart_deduplicates_and_resolves_wake(), test_notifier_rejects_rehearsal_identity_in_human_allowlist(), test_notifier_uses_gateway_approver_setting()

### Community 76 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib (+11 more)

### Community 77 - "ValidatingAdmissionPolicyBinding oncall-agent-fields"
Cohesion: 0.14
Nodes (17): ValidatingAdmissionPolicyBinding oncall-agent-fields, ValidatingAdmissionPolicyBinding oncall-agent-scale, kubernetes.io/metadata.name, namespaceSelector, name, matchLabels, matchResources, policyName (+9 more)

### Community 78 - "Card"
Cohesion: 0.21
Nodes (3): Notifier, DiscordNotifier, Card

### Community 79 - "test_integration.py"
Cohesion: 0.20
Nodes (10): active_bus(), create_events_router(), events(), stream(), publish_event(), selected_bus(), lifespan(), publish() (+2 more)

### Community 80 - "verify"
Cohesion: 0.16
Nodes (10): canonical(), verify(), Flow through my code, Hard rules my code must keep, Muaz [M]: architecture of my part, What I need from others, What I own, What I provide to others (+2 more)

### Community 81 - "models.py"
Cohesion: 0.18
Nodes (8): ApprovalDecidedPayload, ApprovalRequestedPayload, CardPayload, ChecklistPayload, DiagnosisReadyPayload, InferencePayload, Payload, QuarantinePayload

### Community 82 - "words"
Cohesion: 0.23
Nodes (8): Checklist(), Mark(), KINDS, Feed(), LOUD, clock(), since(), words()

### Community 83 - "AuditLog"
Cohesion: 0.28
Nodes (7): AuditLog, EventBus, test_audit_cli_runs_from_repository_root(), test_disconnect_cleans_subscription(), test_events_replay_and_overflow(), test_publish_does_not_emit_if_disk_fails(), test_sse_wire_format_and_disconnect_cleanup()

### Community 85 - "argparse"
Cohesion: 0.29
Nodes (4): main(), summarize(), main(), main()

### Community 86 - "policy.yaml"
Cohesion: 0.20
Nodes (9): budgets, max_actions_per_hour, max_actions_per_incident, max_in_flight, max_retries, change_window_minutes, verify, early_abort (+1 more)

### Community 87 - "tools"
Cohesion: 0.20
Nodes (10): auto_eligible, reversible, auto_eligible, reversible, auto_eligible, reversible, tools, enable_degraded_mode (+2 more)

### Community 88 - "Anirudh [A]: tasks"
Cohesion: 0.22
Nodes (8): Anirudh [A]: tasks, Never cut, Phase 0: foundations, Phase 1: the spine, Phase 2: the other failures, Phase 3: UI, Phase 4: more UI, Phase 5: freeze

### Community 89 - "stage-strip.tsx"
Cohesion: 0.25
Nodes (7): COPY, Dots(), StageStrip(), STATE_LABEL, Stage, STAGES, StageState

### Community 90 - "summarize_ledger"
Cohesion: 0.36
Nodes (4): summarize_ledger(), test_invalid_thresholds_fail_before_database_access(), test_ledger_report_reads_actual_separate_counts_and_failure_reset(), test_missing_database_is_not_created()

### Community 92 - "baselines.py"
Cohesion: 0.53
Nodes (3): load(), medians(), store()

### Community 93 - "demo.ts"
Cohesion: 0.33
Nodes (5): DEMO_RECEIPT, DEMO_SCRIPT, DemoStep, STEPS, TICKS

### Community 94 - "detection"
Cohesion: 0.40
Nodes (5): detection, error_ratio_threshold, latency_multiplier, poll_seconds, sustain_seconds

### Community 95 - "scale"
Cohesion: 0.40
Nodes (5): auto_eligible, max, min, reversible, scale

### Community 96 - "test_verifier_safety.py"
Cohesion: 0.90
Nodes (4): service(), test_human_change_takes_priority_over_early_abort(), test_missing_service_cannot_confirm_recovery_after_prediction(), verification()

### Community 97 - "approval"
Cohesion: 0.50
Nodes (4): approval, approvers_env, expiry_seconds, repage_seconds

### Community 98 - "major_incident"
Cohesion: 0.50
Nodes (4): major_incident, min_fraction, min_services, within_seconds

### Community 99 - "raise_limit"
Cohesion: 0.50
Nodes (4): auto_eligible, max_memory, reversible, raise_limit

### Community 100 - "trust"
Cohesion: 0.50
Nodes (4): trust, bar, confidence, reset_on_failure

### Community 101 - "net_benefit"
Cohesion: 0.67
Nodes (3): net_benefit, max_added_harm_seconds, min_benefit_ratio

### Community 102 - "restart_service"
Cohesion: 0.67
Nodes (3): auto_eligible, reversible, restart_service

## Knowledge Gaps
- **1 isolated node(s):** `oncall-agent`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 543 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **20 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ActionRequest` connect `ActionRequest` to `Done (with proof)`, `connect`, `DiagnosisService`, `test_previous_template_and_diff_helpers`, `checklist.py`, `pytest`, `create_app`, `models.py`, `test_verify_loop.py`, `pytest`, `discord_bot.py`, `8. Testing`?**
  _High betweenness centrality (0.074) - this node is a cross-community bridge._
- **Are the 14 inferred relationships involving `ActionRequest` (e.g. with `call_tool()` and `DiagnosisResult`) actually correct?**
  _`ActionRequest` has 14 INFERRED edges - model-reasoned connections that need verification._
- **What connects `oncall-agent` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `6.4 Gateway (`gateway/`) [M] P0 unless marked` be split into smaller, more focused modules?**
  _Cohesion score 0.05 - nodes in this community are weakly interconnected._
- **Why does `Implementation Plan: the on-call agent that has to earn its autonomy` connect `Implementation Plan: the on-call agent that has to earn its autonomy` to `6.4 Gateway (`gateway/`) [M] P0 unless marked`, `10. Build plan`, `3. Environment setup`, `8. Testing`, `0. Scope and principles`, `11. Demo`, `1. System overview`, `4. Configuration files`, `5. Data model`, `9. Benchmark (`bench/`) [T] P1`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **Are the 8 inferred relationships involving `Gateway` (e.g. with `ReceiptStore` and `Verification`) actually correct?**
  _`Gateway` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Should `DiagnosisService` be split into smaller, more focused modules?**
  _Cohesion score 0.0662004662004662 - nodes in this community are weakly interconnected._