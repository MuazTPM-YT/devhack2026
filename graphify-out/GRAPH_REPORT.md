# Graph Report - devhack2026  (2026-11-13)

## Corpus Check
- 116 files · ~59,329 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 5 file(s) not represented in the graph (top: (none) 3, .example 1, .lock 1)

## Summary
- 1168 nodes · 3026 edges · 65 communities (54 shown, 11 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 264 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `86a1e511`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- NotifierState
- test_audit.py
- 6.4 Gateway (`gateway/`) [M] P0 unless marked
- harness.py
- DiagnosisService
- typing
- AGENTS.md
- CLAUDE.md
- 10. Build plan
- test_brain.py
- checklist.py
- redact_value
- Implementation Plan: the on-call agent that has to earn its autonomy
- bundle.py
- find_culprit
- models.py
- Observer
- test_observer.py
- OpenCodeGoAdapter
- brain/main.py
- Incident
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
- test_trust_integration.py
- oncall-agent
- httpx
- harm_check
- journal.py
- pytest
- connect
- security_check.sh
- make_kubeconfigs.sh
- install_shop.sh
- match
- setup_cluster.sh
- gateway/main.py
- test_kube_watch.py
- On-call agent: Twaha components
- json
- graph.py
- Twaha [T]: tasks
- charge.js
- Muaz [M]: architecture of my part
- InferenceProvider
- baselines.py
- Anirudh [A]: architecture of my part
- blast.py
- Twaha [T]: state
- Open questions
- build_bad_payment.sh
- smoke.sh
- Done (with proof)

## God Nodes (most connected - your core abstractions)
1. `ActionRequest` - 37 edges
2. `Gateway` - 35 edges
3. `connect()` - 34 edges
4. `GatewayDecision` - 34 edges
5. `DiagnosisService` - 33 edges
6. `World` - 31 edges
7. `action()` - 25 edges
8. `Done (with proof)` - 25 edges
9. `ReceiptStore` - 24 edges
10. `Incident` - 24 edges

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

## Communities (65 total, 11 thin omitted)

### Community 0 - "NotifierState"
Cohesion: 0.06
Nodes (20): Notifier, NotificationConsumer, ApprovalButton, ApprovalController, ApprovalView, DiscordNotifier, health(), lifespan() (+12 more)

### Community 1 - "test_audit.py"
Cohesion: 0.08
Nodes (35): AuditLog, canonical(), EventBus, verify(), active_bus(), create_events_router(), events(), stream() (+27 more)

### Community 2 - "6.4 Gateway (`gateway/`) [M] P0 unless marked"
Cohesion: 0.06
Nodes (34): 6.1 Chaos panel (`chaos/`) [A] P0, 6.2.1 Baselines (`baselines.py`), 6.2.2 Detector (`detector.py`), 6.2.3 Kubernetes watch (`kube_watch.py`), 6.2.4 Change journal (`journal.py`), 6.2.5 Flags (`flags.py`), 6.2 Observer (`observer/`) [M] P0, 6.3.1 Dependency graph (`graph.py`) (+26 more)

### Community 3 - "harness.py"
Cohesion: 0.05
Nodes (33): Harness, HttpTrialServices, main(), measure(), ObservationError, TrialResult, TrialServices, FakeServices (+25 more)

### Community 4 - "DiagnosisService"
Cohesion: 0.26
Nodes (14): DiagnosisResult, DiagnosisService, Diagnosis, diagnosis(), FakeProvider, test_cache_disk_failure_does_not_discard_diagnosis(), test_cache_is_exact_and_marked(), test_deadline_falls_back_to_rule() (+6 more)

### Community 5 - "typing"
Cohesion: 0.21
Nodes (6): InferenceResponse, test_adversarial_proposal(), generate(), test_forbidden_tools(), test_poisoned_log(), generate()

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
Cohesion: 0.20
Nodes (14): diagnosis_json(), FakeProvider, jaeger_trace(), make(), test_action_goes_to_gateway(), test_bad_deploy_end_to_end(), test_gateway_down_escalates(), test_jaeger_down_falls_back_to_deepest_unhealthy() (+6 more)

### Community 10 - "checklist.py"
Cohesion: 0.13
Nodes (24): startup_seconds(), surge_ok(), forecast_text(), rv(), build_patch(), _flatten(), _h(), namespace_hash() (+16 more)

### Community 11 - "redact_value"
Cohesion: 0.15
Nodes (15): quarantine(), redact(), redact_value(), clean(), Flow through my parts, Hard rules my code must keep, Twaha [T]: architecture of my part, What I need from others (+7 more)

### Community 12 - "Implementation Plan: the on-call agent that has to earn its autonomy"
Cohesion: 0.29
Nodes (6): 12. Risks and fallbacks, 13. Submission checklist, 14. Command cheat sheet, 2. Repository layout, 7. End-to-end flows (acceptance scenarios), Implementation Plan: the on-call agent that has to earn its autonomy

### Community 13 - "bundle.py"
Cohesion: 0.26
Nodes (17): build_bundle(), change_evidence(), k8s_evidence(), log_evidence(), memory_ratio(), metric_evidence(), _span_error_text(), trace_evidence() (+9 more)

### Community 14 - "find_culprit"
Cohesion: 0.22
Nodes (7): deepest_unhealthy(), depth(), find_culprit(), from_traces(), is_error(), CulpritTest, trace()

### Community 15 - "models.py"
Cohesion: 0.16
Nodes (12): ApprovalDecidedPayload, ApprovalRequestedPayload, CardPayload, Cause, ChecklistPayload, DiagnosisReadyPayload, EvidenceBundle, InferencePayload (+4 more)

### Community 16 - "Observer"
Cohesion: 0.14
Nodes (4): Detector, Observer, det(), DetectorTest

### Community 17 - "test_observer.py"
Cohesion: 0.20
Nodes (13): require_env(), Backend, make(), prom_result(), test_brain_down_does_not_stop_detection(), handler(), test_endpoints(), test_nan_rows_are_dropped() (+5 more)

### Community 18 - "OpenCodeGoAdapter"
Cohesion: 0.22
Nodes (5): InferenceRequest, ProviderError, OpenCodeGoAdapter, test_adapter_headers_and_wire_shape(), test_provider_errors_are_sanitized()

### Community 19 - "brain/main.py"
Cohesion: 0.20
Nodes (8): collect_k8s(), fetch_error_traces(), build_from_env(), create_app(), _finished(), incidents(), lifespan(), require_env()

### Community 20 - "Incident"
Cohesion: 0.25
Nodes (4): Brain, Incident, action(), bundle()

### Community 21 - "3. Environment setup"
Cohesion: 0.33
Nodes (6): 3.1 Prerequisites [A] P0, 3.2 Cluster [A] P0, 3.3 The shop [A] P0, 3.4 The buggy payment image [A] P0, 3.5 Kubeconfigs for the three identities [M] P0, 3. Environment setup

### Community 22 - "8. Testing"
Cohesion: 0.40
Nodes (5): 8.1 Unit tests [M][T] P0, 8.2 Property-based tests (`test_invariants.py`, Hypothesis) [M] P1, 8.3 Red-team suite (`tests/redteam/`) [T] P1, 8.4 Smoke test (`scripts/smoke.sh`) [A] P0, 8. Testing

### Community 23 - "test_bench_export.py"
Cohesion: 0.12
Nodes (20): display(), export_report(), markdown(), timing_svg(), main(), summarize(), compare(), load_rows() (+12 more)

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
Cohesion: 0.23
Nodes (8): Gateway, record(), ActionRequest, GatewayDecision, submit(), test_mcp_exposes_six_tools_with_actable_targets_only(), submit(), test_resource_rule_actions_keep_different_approval_eligibility()

### Community 32 - "test_gateway.py"
Cohesion: 0.05
Nodes (58): Muaz [M]: tasks, Never cut, Phase 0: foundations, Phase 1: the spine, one failure end to end, Phase 2: the other failures and the checks, Phase 3: trust, humans, proof, Phase 4: wide outages and measurement, Phase 6: stretch (only if Phase 4 exit is met early) (+50 more)

### Community 34 - "test_trust_integration.py"
Cohesion: 0.22
Nodes (9): Manual baseline, ledger_effect(), Verification, health(), test_verified_outcome_controls_persisted_trust_and_card(), service(), test_human_change_takes_priority_over_early_abort(), test_missing_service_cannot_confirm_recovery_after_prediction() (+1 more)

### Community 37 - "httpx"
Cohesion: 0.15
Nodes (7): read_events(), fetch_readings(), prom_query(), build_from_env(), create_app(), get_journal(), lifespan()

### Community 38 - "harm_check"
Cohesion: 0.17
Nodes (8): spec_hashes(), harm_check(), service_score(), HarmCheckTest, health(), svc(), verification(), VerifierTest

### Community 39 - "journal.py"
Cohesion: 0.13
Nodes (16): check(), author(), _configmap_changes(), _containers(), current(), _deployment_changes(), entry(), insert() (+8 more)

### Community 41 - "pytest"
Cohesion: 0.25
Nodes (9): Event, Prediction, test_action_rejects_invented_pattern(), test_evidence_rejects_nonfinite_timestamp(), test_payload_contract_rejects_incomplete_approval(), test_payload_rejects_cross_incident_card(), test_prediction_deadline_is_bounded(), test_shared_pattern_values() (+1 more)

### Community 42 - "connect"
Cohesion: 0.13
Nodes (11): summarize_ledger(), check(), counts(), eligible(), lower_bound(), connect(), DbTest, test_invalid_thresholds_fail_before_database_access() (+3 more)

### Community 46 - "match"
Cohesion: 0.24
Nodes (9): _action(), latest_change_before_onset(), match(), to_bytes(), bounds(), check(), change(), incident() (+1 more)

### Community 48 - "gateway/main.py"
Cohesion: 0.07
Nodes (19): approvers_from_env(), create(), get(), set_state(), build_from_env(), create_app(), lifespan(), Decide (+11 more)

### Community 49 - "test_kube_watch.py"
Cohesion: 0.16
Nodes (17): bad_pods(), pod_bad(), run_watch(), service_of(), Tracker, _ts(), deployment(), FakeResp (+9 more)

### Community 50 - "On-call agent: Twaha components"
Cohesion: 0.20
Nodes (8): ts(), usage(), Benchmarks and adversarial checks, Discord notifier, Inference, On-call agent: Twaha components, Project graph, Setup and checks

### Community 51 - "json"
Cohesion: 0.06
Nodes (56): bad_deploy(), broken_config(), datastore_down(), kubectl(), KubectlError, memory_leak(), read_flags(), read_live_flags() (+48 more)

### Community 52 - "graph.py"
Cohesion: 0.31
Nodes (4): DependencyGraph, downstream(), upstream(), test_graph_cache_and_downstream()

### Community 53 - "Twaha [T]: tasks"
Cohesion: 0.22
Nodes (8): Evidence and next gate (2026-11-13), Never cut, Phase 1: the spine, Phase 2: checks, Phase 3: humans and proof, Phase 4: measurement, Phase 5: freeze, Twaha [T]: tasks

### Community 54 - "charge.js"
Cohesion: 0.10
Nodes (14): { ATTR_ERROR_TYPE }, cardValidator, charge(), { context, propagation, trace, metrics, SpanStatusCode }, { FlagdProvider }, flagProvider, logger, LOYALTY_LEVEL (+6 more)

### Community 55 - "Muaz [M]: architecture of my part"
Cohesion: 0.29
Nodes (6): Flow through my code, Hard rules my code must keep, Muaz [M]: architecture of my part, What I need from others, What I own, What I provide to others

### Community 56 - "InferenceProvider"
Cohesion: 0.29
Nodes (3): InferenceProvider, Done (with proof), Phase 0: foundations

### Community 57 - "baselines.py"
Cohesion: 0.43
Nodes (3): load(), medians(), store()

### Community 58 - "Anirudh [A]: architecture of my part"
Cohesion: 0.29
Nodes (6): Anirudh [A]: architecture of my part, Flow through my parts, Hard rules my code must keep, What I need from others, What I own, What I provide to others

### Community 59 - "blast.py"
Cohesion: 0.47
Nodes (4): blast_radius(), forecast_added_seconds(), net_benefit(), test_blast_radius_forecast_and_net_benefit()

### Community 60 - "Twaha [T]: state"
Cohesion: 0.33
Nodes (5): Blocked / waiting on, In progress, Next, Notes for next session, Twaha [T]: state

### Community 61 - "Open questions"
Cohesion: 0.40
Nodes (4): Open questions, Rules for agents, Shared context (all agents read and write this), VERIFY results (§3.3, Phase 0)

### Community 68 - "Done (with proof)"
Cohesion: 0.17
Nodes (8): call_tool(), read(), Blocked / waiting on, Done (with proof), In progress, Muaz [M]: state, Next, Notes for my next session

## Knowledge Gaps
- **1 isolated node(s):** `oncall-agent`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 324 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **11 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ActionRequest` connect `ActionRequest` to `test_gateway.py`, `test_trust_integration.py`, `DiagnosisService`, `Done (with proof)`, `typing`, `pytest`, `checklist.py`, `models.py`, `brain/main.py`, `Incident`, `8. Testing`, `Open questions`?**
  _High betweenness centrality (0.076) - this node is a cross-community bridge._
- **Are the 14 inferred relationships involving `ActionRequest` (e.g. with `call_tool()` and `DiagnosisResult`) actually correct?**
  _`ActionRequest` has 14 INFERRED edges - model-reasoned connections that need verification._
- **What connects `oncall-agent` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `NotifierState` be split into smaller, more focused modules?**
  _Cohesion score 0.06467661691542288 - nodes in this community are weakly interconnected._
- **Why does `GatewayDecision` connect `ActionRequest` to `NotifierState`, `test_audit.py`, `test_gateway.py`, `harness.py`, `Done (with proof)`, `typing`, `test_brain.py`, `checklist.py`, `models.py`, `On-call agent: Twaha components`, `brain/main.py`, `Incident`, `Open questions`?**
  _High betweenness centrality (0.055) - this node is a cross-community bridge._
- **Are the 8 inferred relationships involving `Gateway` (e.g. with `ReceiptStore` and `Verification`) actually correct?**
  _`Gateway` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_audit.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08269230769230769 - nodes in this community are weakly interconnected._