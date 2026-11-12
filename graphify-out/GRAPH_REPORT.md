# Graph Report - devhack2026  (2026-11-13)

## Corpus Check
- 105 files · ~43,091 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 5 file(s) not represented in the graph (top: (none) 3, .example 1, .lock 1)

## Summary
- 873 nodes · 1969 edges · 64 communities (50 shown, 14 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 175 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `60b4eee0`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- NotifierState
- test_audit.py
- 6.4 Gateway (`gateway/`) [M] P0 unless marked
- HttpTrialServices
- httpx
- models.py
- AGENTS.md
- CLAUDE.md
- 10. Build plan
- Anirudh [A]: tasks
- Muaz [M]: tasks
- Twaha [T]: tasks
- Implementation Plan: the on-call agent that has to earn its autonomy
- On-call agent: Twaha components
- Anirudh [A]: architecture of my part
- Anirudh [A]: state
- test_observer.py
- Muaz [M]: state
- Observer
- test_bench_recovery.py
- Twaha [T]: state
- 3. Environment setup
- 8. Testing
- json
- 0. Scope and principles
- 11. Demo
- 1. System overview
- 4. Configuration files
- 5. Data model
- 9. Benchmark (`bench/`) [T] P1
- Done (with proof)
- test_trust_integration.py
- connect
- oncall-agent
- observer/main.py
- test_verifier.py
- JournalTest
- find_culprit
- det
- trust.py
- security_check.sh
- make_kubeconfigs.sh
- install_shop.sh
- match
- setup_cluster.sh
- test_chaos.py
- test_run_watch_relists_after_error
- build_bad_payment.sh
- test_chaos.py
- test_bench.py
- build_from_env
- charge.js
- redact_value
- TrialServices
- gateway/events.py
- test_integration.py
- llm.py
- Muaz [M]: architecture of my part
- measure
- build_bad_payment.sh
- smoke.sh

## God Nodes (most connected - your core abstractions)
1. `DiagnosisService` - 26 edges
2. `connect()` - 26 edges
3. `NotifierState` - 22 edges
4. `HttpTrialServices` - 21 edges
5. `redact_value()` - 21 edges
6. `ActionRequest` - 19 edges
7. `Card` - 18 edges
8. `ApprovalController` - 17 edges
9. `NotificationConsumer` - 16 edges
10. `AuditLog` - 16 edges

## Surprising Connections (you probably didn't know these)
- `Notes for my next session` --references--> `ReceiptStore`  [INFERRED]
  team/twaha/STATE.md → gateway/receipts.py
- `Done (with proof)` --references--> `InferenceProvider`  [INFERRED]
  team/twaha/STATE.md → brain/providers/base.py
- `8.2 Property-based tests (`test_invariants.py`, Hypothesis) [M] P1` --references--> `ActionRequest`  [INFERRED]
  IMPLEMENTATION.md → schemas/models.py
- `Discord notifier` --references--> `GatewayDecision`  [INFERRED]
  README.md → schemas/models.py
- `5.3 Event types (SSE and audit)` --references--> `harm_check()`  [INFERRED]
  IMPLEMENTATION.md → gateway/verifier.py

## Import Cycles
- None detected.

## Communities (64 total, 14 thin omitted)

### Community 0 - "NotifierState"
Cohesion: 0.07
Nodes (19): Notifier, NotificationConsumer, ApprovalButton, ApprovalController, ApprovalView, DiscordNotifier, lifespan(), load_approvers() (+11 more)

### Community 1 - "test_audit.py"
Cohesion: 0.15
Nodes (15): AuditLog, canonical(), EventBus, verify(), build_incident_card(), clean(), test_audit_cli_runs_from_repository_root(), test_chain_tamper_and_concurrent_append() (+7 more)

### Community 2 - "6.4 Gateway (`gateway/`) [M] P0 unless marked"
Cohesion: 0.05
Nodes (40): 6.1 Chaos panel (`chaos/`) [A] P0, 6.2.1 Baselines (`baselines.py`), 6.2.2 Detector (`detector.py`), 6.2.3 Kubernetes watch (`kube_watch.py`), 6.2.4 Change journal (`journal.py`), 6.2.5 Flags (`flags.py`), 6.2 Observer (`observer/`) [M] P0, 6.3.1 Dependency graph (`graph.py`) (+32 more)

### Community 3 - "HttpTrialServices"
Cohesion: 0.12
Nodes (14): HttpTrialServices, main(), ObservationError, test_reconnect_resumes_cursor_and_ignores_duplicate_events(), handle(), test_replayed_approval_does_not_repeat_post(), handle(), test_uncertain_approval_post_is_not_retried() (+6 more)

### Community 4 - "httpx"
Cohesion: 0.14
Nodes (10): InferenceProvider, InferenceRequest, InferenceResponse, ProviderError, OpenCodeGoAdapter, test_adversarial_proposal(), generate(), test_adapter_headers_and_wire_shape() (+2 more)

### Community 5 - "models.py"
Cohesion: 0.07
Nodes (47): DiagnosisResult, DiagnosisService, ActionRequest, ApprovalDecidedPayload, ApprovalRequestedPayload, CardPayload, Cause, ChecklistPayload (+39 more)

### Community 6 - "AGENTS.md"
Cohesion: 0.18
Nodes (10): Code comments, Commands, Commits, Communication, Dependencies, Git safety, graphify, Secrets (+2 more)

### Community 7 - "CLAUDE.md"
Cohesion: 0.18
Nodes (10): Code comments, Commands, Commits, Communication, Dependencies, Git safety, graphify, Secrets (+2 more)

### Community 8 - "10. Build plan"
Cohesion: 0.22
Nodes (9): 10. Build plan, Cut order if time runs short, Phase 0: foundations (about 2 h, everyone), Phase 1: the spine, one failure end to end (about 5 h) P0, Phase 2: the other failures and the checks (about 5 h) P0, Phase 3: trust, humans, proof (about 5 h) P1, Phase 4: wide outages and measurement (about 4 h) P1, Phase 5: freeze and polish (about 4 h) (+1 more)

### Community 9 - "Anirudh [A]: tasks"
Cohesion: 0.22
Nodes (8): Anirudh [A]: tasks, Never cut, Phase 0: foundations, Phase 1: the spine, Phase 2: the other failures, Phase 3: UI, Phase 4: more UI, Phase 5: freeze

### Community 10 - "Muaz [M]: tasks"
Cohesion: 0.22
Nodes (8): Muaz [M]: tasks, Never cut, Phase 0: foundations, Phase 1: the spine, one failure end to end, Phase 2: the other failures and the checks, Phase 3: trust, humans, proof, Phase 4: wide outages and measurement, Phase 6: stretch (only if Phase 4 exit is met early)

### Community 11 - "Twaha [T]: tasks"
Cohesion: 0.18
Nodes (10): Integration proof (2026-11-13), Never cut, Phase 0: foundations, Phase 1: the spine, Phase 2: checks, Phase 3: humans and proof, Phase 4: measurement, Phase 5: freeze (+2 more)

### Community 12 - "Implementation Plan: the on-call agent that has to earn its autonomy"
Cohesion: 0.29
Nodes (6): 12. Risks and fallbacks, 13. Submission checklist, 14. Command cheat sheet, 2. Repository layout, 7. End-to-end flows (acceptance scenarios), Implementation Plan: the on-call agent that has to earn its autonomy

### Community 13 - "On-call agent: Twaha components"
Cohesion: 0.29
Nodes (6): Benchmarks and adversarial checks, Discord notifier, Inference, On-call agent: Twaha components, Project graph, Setup and checks

### Community 14 - "Anirudh [A]: architecture of my part"
Cohesion: 0.29
Nodes (6): Anirudh [A]: architecture of my part, Flow through my parts, Hard rules my code must keep, What I need from others, What I own, What I provide to others

### Community 15 - "Anirudh [A]: state"
Cohesion: 0.29
Nodes (6): Anirudh [A]: state, Blocked / waiting on, Done (with proof), In progress, Next, Notes for my next session

### Community 16 - "test_observer.py"
Cohesion: 0.20
Nodes (13): require_env(), Backend, make(), prom_result(), test_brain_down_does_not_stop_detection(), handler(), test_endpoints(), test_nan_rows_are_dropped() (+5 more)

### Community 17 - "Muaz [M]: state"
Cohesion: 0.33
Nodes (5): Blocked / waiting on, In progress, Muaz [M]: state, Next, Notes for my next session

### Community 18 - "Observer"
Cohesion: 0.17
Nodes (5): load(), medians(), store(), Detector, Observer

### Community 19 - "test_bench_recovery.py"
Cohesion: 0.13
Nodes (8): Harness, stream(), test_failed_attempts_count_toward_resume_target(), test_resume_corrupt_file_fails_before_reset(), test_resume_counts_recorded_attempts_and_does_not_repeat_fault(), test_timeout_keeps_detection_and_diagnosis_measurements(), handle(), handle()

### Community 20 - "Twaha [T]: state"
Cohesion: 0.29
Nodes (6): Blocked / waiting on, Done (with proof), In progress, Next, Notes for my next session, Twaha [T]: state

### Community 21 - "3. Environment setup"
Cohesion: 0.33
Nodes (6): 3.1 Prerequisites [A] P0, 3.2 Cluster [A] P0, 3.3 The shop [A] P0, 3.4 The buggy payment image [A] P0, 3.5 Kubeconfigs for the three identities [M] P0, 3. Environment setup

### Community 22 - "8. Testing"
Cohesion: 0.40
Nodes (5): 8.1 Unit tests [M][T] P0, 8.2 Property-based tests (`test_invariants.py`, Hypothesis) [M] P1, 8.3 Red-team suite (`tests/redteam/`) [T] P1, 8.4 Smoke test (`scripts/smoke.sh`) [A] P0, 8. Testing

### Community 23 - "json"
Cohesion: 0.22
Nodes (4): main(), summarize(), read_events(), main()

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

### Community 30 - "Done (with proof)"
Cohesion: 0.27
Nodes (7): Manual baseline, Verification, Done (with proof), service(), test_human_change_takes_priority_over_early_abort(), test_missing_service_cannot_confirm_recovery_after_prediction(), verification()

### Community 32 - "test_trust_integration.py"
Cohesion: 0.22
Nodes (7): build_card(), get(), health(), Gateway mounting, test_card_stays_five_lines_with_multiline_fields(), health(), test_verified_outcome_controls_persisted_trust_and_card()

### Community 37 - "observer/main.py"
Cohesion: 0.22
Nodes (3): fetch_readings(), prom_query(), create_app()

### Community 38 - "test_verifier.py"
Cohesion: 0.15
Nodes (9): spec_hashes(), harm_check(), ledger_effect(), service_score(), HarmCheckTest, health(), svc(), verification() (+1 more)

### Community 39 - "JournalTest"
Cohesion: 0.13
Nodes (18): check(), author(), _configmap_changes(), _containers(), current(), _deployment_changes(), entry(), insert() (+10 more)

### Community 40 - "find_culprit"
Cohesion: 0.22
Nodes (7): deepest_unhealthy(), depth(), find_culprit(), from_traces(), is_error(), CulpritTest, trace()

### Community 42 - "trust.py"
Cohesion: 0.27
Nodes (7): check(), counts(), eligible(), lower_bound(), record(), test_resource_rule_actions_keep_different_approval_eligibility(), TrustTest

### Community 46 - "match"
Cohesion: 0.29
Nodes (7): _action(), latest_change_before_onset(), match(), to_bytes(), change(), incident(), RulesTest

### Community 48 - "test_chaos.py"
Cohesion: 0.20
Nodes (14): bad_pods(), pod_bad(), run_watch(), service_of(), Tracker, _ts(), deployment(), iso() (+6 more)

### Community 49 - "test_run_watch_relists_after_error"
Cohesion: 0.33
Nodes (3): FakeResp, test_run_watch_relists_after_error(), list_fn()

### Community 50 - "build_bad_payment.sh"
Cohesion: 0.31
Nodes (5): main(), summarize_ledger(), test_invalid_thresholds_fail_before_database_access(), test_ledger_report_reads_actual_separate_counts_and_failure_reset(), test_missing_database_is_not_created()

### Community 51 - "test_chaos.py"
Cohesion: 0.09
Nodes (28): bad_deploy(), kubectl(), KubectlError, read_all(), record(), create_app(), bad_deploy(), do_reset() (+20 more)

### Community 52 - "test_bench.py"
Cohesion: 0.19
Nodes (9): compare(), main(), summarize(), FakeServices, test_disabled_harness_never_resets_or_injects(), test_failed_trial_persisted_and_next_trial_runs(), test_manual_comparison_preserves_missing_measurements(), test_matching_pattern_wrong_culprit_is_not_correct() (+1 more)

### Community 53 - "build_from_env"
Cohesion: 0.33
Nodes (3): build_from_env(), lifespan(), load()

### Community 54 - "charge.js"
Cohesion: 0.10
Nodes (13): { ATTR_ERROR_TYPE }, cardValidator, charge(), { context, propagation, trace, metrics, SpanStatusCode }, { FlagdProvider }, flagProvider, LOYALTY_LEVEL, meter (+5 more)

### Community 55 - "redact_value"
Cohesion: 0.15
Nodes (14): redact(), redact_value(), What I need from others, Flow through my parts, Hard rules my code must keep, Twaha [T]: architecture of my part, What I need from others, What I own (+6 more)

### Community 57 - "gateway/events.py"
Cohesion: 0.17
Nodes (10): active_bus(), create_events_router(), events(), stream(), publish_event(), selected_bus(), lifespan(), publish() (+2 more)

### Community 58 - "test_integration.py"
Cohesion: 0.34
Nodes (6): create_receipts_router(), ReceiptStore, Receipt, test_routes_and_receipt_card(), test_diagnosis_audit_and_receipt_round_trip(), test_event_router_validates_before_persisting_and_shares_database()

### Community 60 - "Muaz [M]: architecture of my part"
Cohesion: 0.33
Nodes (5): Flow through my code, Hard rules my code must keep, Muaz [M]: architecture of my part, What I own, What I provide to others

### Community 61 - "measure"
Cohesion: 0.70
Nodes (3): measure(), TrialResult, test_sync_provider_usage_normalizes_without_double_counting()

## Knowledge Gaps
- **1 isolated node(s):** `oncall-agent`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 292 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Implementation Plan: the on-call agent that has to earn its autonomy` connect `Implementation Plan: the on-call agent that has to earn its autonomy` to `6.4 Gateway (`gateway/`) [M] P0 unless marked`, `10. Build plan`, `3. Environment setup`, `8. Testing`, `0. Scope and principles`, `11. Demo`, `1. System overview`, `4. Configuration files`, `5. Data model`, `9. Benchmark (`bench/`) [T] P1`?**
  _High betweenness centrality (0.119) - this node is a cross-community bridge._
- **Are the 9 inferred relationships involving `DiagnosisService` (e.g. with `InferenceProvider` and `InferenceRequest`) actually correct?**
  _`DiagnosisService` has 9 INFERRED edges - model-reasoned connections that need verification._
- **What connects `oncall-agent` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `NotifierState` be split into smaller, more focused modules?**
  _Cohesion score 0.06778846153846153 - nodes in this community are weakly interconnected._
- **Why does `ActionRequest` connect `models.py` to `test_trust_integration.py`, `trust.py`, `llm.py`, `8. Testing`?**
  _High betweenness centrality (0.115) - this node is a cross-community bridge._
- **Should `test_audit.py` be split into smaller, more focused modules?**
  _Cohesion score 0.14814814814814814 - nodes in this community are weakly interconnected._
- **Why does `8.2 Property-based tests (`test_invariants.py`, Hypothesis) [M] P1` connect `8. Testing` to `models.py`?**
  _High betweenness centrality (0.098) - this node is a cross-community bridge._