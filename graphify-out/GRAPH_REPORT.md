# Graph Report - devhack2026  (2026-11-13)

## Corpus Check
- 121 files · ~55,862 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 5 file(s) not represented in the graph (top: (none) 3, .example 1, .lock 1)

## Summary
- 1121 nodes · 2860 edges · 63 communities (49 shown, 14 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 258 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `39f0f7fc`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- NotifierState
- test_audit.py
- 6.4 Gateway (`gateway/`) [M] P0 unless marked
- harness.py
- DiagnosisService
- test_brain.py
- AGENTS.md
- CLAUDE.md
- 10. Build plan
- Incident
- test_previous_template_and_diff_helpers
- create_app
- Implementation Plan: the on-call agent that has to earn its autonomy
- bundle.py
- ActionRequest
- models.py
- test_observer.py
- NotificationConsumer
- Anirudh [A]: architecture of my part
- Anirudh [A]: state
- Any
- 3. Environment setup
- 8. Testing
- test_bench_export.py
- 0. Scope and principles
- 11. Demo
- 1. System overview
- 4. Configuration files
- 5. Data model
- 9. Benchmark (`bench/`) [T] P1
- GatewayDecision
- test_gateway.py
- connect
- oncall-agent
- build_from_env
- dryrun.py
- journal.py
- usage
- trust_report.py
- security_check.sh
- make_kubeconfigs.sh
- install_shop.sh
- match
- setup_cluster.sh
- checklist.py
- Tracker
- test_verify_loop.py
- test_chaos.py
- build_from_env
- charge.js
- connect
- Twaha [T]: tasks
- httpx
- build_bad_payment.sh
- smoke.sh
- Muaz [M]: state
- Contracts (agreed interfaces between owners)

## God Nodes (most connected - your core abstractions)
1. `ActionRequest` - 36 edges
2. `GatewayDecision` - 34 edges
3. `connect()` - 34 edges
4. `DiagnosisService` - 33 edges
5. `Gateway` - 32 edges
6. `ReceiptStore` - 24 edges
7. `Incident` - 24 edges
8. `Receipt` - 23 edges
9. `HttpTrialServices` - 23 edges
10. `NotifierState` - 22 edges

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

## Communities (63 total, 14 thin omitted)

### Community 0 - "NotifierState"
Cohesion: 0.06
Nodes (23): read_events(), Notifier, NotificationConsumer, ApprovalButton, ApprovalController, ApprovalView, DiscordNotifier, health() (+15 more)

### Community 1 - "test_audit.py"
Cohesion: 0.05
Nodes (56): quarantine(), redact(), redact_value(), AuditLog, canonical(), EventBus, verify(), active_bus() (+48 more)

### Community 2 - "6.4 Gateway (`gateway/`) [M] P0 unless marked"
Cohesion: 0.05
Nodes (41): create(), 6.1 Chaos panel (`chaos/`) [A] P0, 6.2.1 Baselines (`baselines.py`), 6.2.2 Detector (`detector.py`), 6.2.3 Kubernetes watch (`kube_watch.py`), 6.2.4 Change journal (`journal.py`), 6.2.5 Flags (`flags.py`), 6.2 Observer (`observer/`) [M] P0 (+33 more)

### Community 3 - "harness.py"
Cohesion: 0.05
Nodes (33): Harness, HttpTrialServices, main(), measure(), ObservationError, TrialResult, TrialServices, FakeServices (+25 more)

### Community 4 - "DiagnosisService"
Cohesion: 0.08
Nodes (32): DiagnosisResult, DiagnosisService, InferenceProvider, InferenceRequest, InferenceResponse, ProviderError, OpenCodeGoAdapter, Diagnosis (+24 more)

### Community 5 - "test_brain.py"
Cohesion: 0.12
Nodes (19): DependencyGraph, create_app(), _finished(), incidents(), diagnosis_json(), FakeProvider, jaeger_trace(), make() (+11 more)

### Community 6 - "AGENTS.md"
Cohesion: 0.18
Nodes (10): Code comments, Commands, Commits, Communication, Dependencies, Git safety, graphify, Secrets (+2 more)

### Community 7 - "CLAUDE.md"
Cohesion: 0.18
Nodes (10): Code comments, Commands, Commits, Communication, Dependencies, Git safety, graphify, Secrets (+2 more)

### Community 8 - "10. Build plan"
Cohesion: 0.22
Nodes (9): 10. Build plan, Cut order if time runs short, Phase 0: foundations (about 2 h, everyone), Phase 1: the spine, one failure end to end (about 5 h) P0, Phase 2: the other failures and the checks (about 5 h) P0, Phase 3: trust, humans, proof (about 5 h) P1, Phase 4: wide outages and measurement (about 4 h) P1, Phase 5: freeze and polish (about 4 h) (+1 more)

### Community 9 - "Incident"
Cohesion: 0.29
Nodes (3): fetch_error_traces(), Brain, Incident

### Community 10 - "test_previous_template_and_diff_helpers"
Cohesion: 0.47
Nodes (5): outside_allowed(), previous_template(), rs(), template(), test_previous_template_and_diff_helpers()

### Community 11 - "create_app"
Cohesion: 0.13
Nodes (5): create_app(), lifespan(), build_mcp(), make(), test_rehearsal_route_needs_flag()

### Community 12 - "Implementation Plan: the on-call agent that has to earn its autonomy"
Cohesion: 0.29
Nodes (6): 12. Risks and fallbacks, 13. Submission checklist, 14. Command cheat sheet, 2. Repository layout, 7. End-to-end flows (acceptance scenarios), Implementation Plan: the on-call agent that has to earn its autonomy

### Community 13 - "bundle.py"
Cohesion: 0.11
Nodes (26): build_bundle(), change_evidence(), collect_k8s(), k8s_evidence(), log_evidence(), memory_ratio(), metric_evidence(), _span_error_text() (+18 more)

### Community 14 - "ActionRequest"
Cohesion: 0.27
Nodes (4): call_tool(), ActionRequest, action(), bundle()

### Community 15 - "models.py"
Cohesion: 0.18
Nodes (8): ApprovalDecidedPayload, ApprovalRequestedPayload, CardPayload, ChecklistPayload, DiagnosisReadyPayload, InferencePayload, Payload, QuarantinePayload

### Community 16 - "test_observer.py"
Cohesion: 0.06
Nodes (25): load(), medians(), store(), Detector, fetch_readings(), prom_query(), create_app(), get_journal() (+17 more)

### Community 17 - "NotificationConsumer"
Cohesion: 0.33
Nodes (5): Discord notifier, Inference, On-call agent: Twaha components, Project graph, Setup and checks

### Community 18 - "Anirudh [A]: architecture of my part"
Cohesion: 0.29
Nodes (6): Anirudh [A]: architecture of my part, Flow through my parts, Hard rules my code must keep, What I need from others, What I own, What I provide to others

### Community 19 - "Anirudh [A]: state"
Cohesion: 0.29
Nodes (6): Anirudh [A]: state, Blocked / waiting on, Done (with proof), In progress, Next, Notes for my next session

### Community 20 - "Any"
Cohesion: 0.18
Nodes (4): FakeApps, FakeCore, Observer, Resp

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

### Community 30 - "GatewayDecision"
Cohesion: 0.26
Nodes (7): get(), set_state(), Gateway, check(), GatewayDecision, test_mcp_exposes_six_tools_with_actable_targets_only(), submit()

### Community 32 - "test_gateway.py"
Cohesion: 0.27
Nodes (14): Phase 3: trust, humans, proof, action(), test_approval_rules(), test_bad_deploy_asks_then_rolls_back_on_approval(), test_budget_and_in_flight(), test_conflict_on_execute_hands_off_and_admission_denial_escalates(), test_dry_run_outside_template_escalates(), test_http_app_routes() (+6 more)

### Community 34 - "connect"
Cohesion: 0.24
Nodes (5): Manual baseline, Verification, insert(), read(), Done (with proof)

### Community 37 - "build_from_env"
Cohesion: 0.33
Nodes (4): build_from_env(), lifespan(), require_env(), load()

### Community 38 - "dryrun.py"
Cohesion: 0.08
Nodes (24): rv(), _flatten(), _h(), namespace_hash(), rollback_patch(), spec_diff(), spec_hashes(), classify() (+16 more)

### Community 39 - "journal.py"
Cohesion: 0.15
Nodes (15): check(), author(), _configmap_changes(), _containers(), current(), _deployment_changes(), entry(), still_live() (+7 more)

### Community 42 - "trust_report.py"
Cohesion: 0.17
Nodes (12): main(), summarize_ledger(), check(), counts(), eligible(), lower_bound(), record(), test_resource_rule_actions_keep_different_approval_eligibility() (+4 more)

### Community 46 - "match"
Cohesion: 0.29
Nodes (7): _action(), latest_change_before_onset(), match(), to_bytes(), change(), incident(), RulesTest

### Community 48 - "checklist.py"
Cohesion: 0.16
Nodes (5): approvers_from_env(), build_from_env(), Decide, RehearsalCredit, require_env()

### Community 49 - "Tracker"
Cohesion: 0.15
Nodes (18): bad_pods(), pod_bad(), run_watch(), service_of(), Tracker, _ts(), build_from_env(), deployment() (+10 more)

### Community 50 - "test_verify_loop.py"
Cohesion: 0.28
Nodes (11): executed(), healthy(), ledger(), Script, sick(), test_early_abort_pauses_undoes_resumes(), test_human_change_during_verify_hands_off_without_undo(), test_no_recovery_undoes_and_escalates() (+3 more)

### Community 51 - "test_chaos.py"
Cohesion: 0.07
Nodes (50): bad_deploy(), broken_config(), datastore_down(), kubectl(), KubectlError, memory_leak(), read_flags(), read_live_flags() (+42 more)

### Community 53 - "build_from_env"
Cohesion: 0.24
Nodes (10): Event, Model, Prediction, test_action_rejects_invented_pattern(), test_evidence_rejects_nonfinite_timestamp(), test_payload_contract_rejects_incomplete_approval(), test_payload_rejects_cross_incident_card(), test_prediction_deadline_is_bounded() (+2 more)

### Community 54 - "charge.js"
Cohesion: 0.10
Nodes (14): { ATTR_ERROR_TYPE }, cardValidator, charge(), { context, propagation, trace, metrics, SpanStatusCode }, { FlagdProvider }, flagProvider, logger, LOYALTY_LEVEL (+6 more)

### Community 57 - "connect"
Cohesion: 0.23
Nodes (4): connect(), DbTest, health(), test_verified_outcome_controls_persisted_trust_and_card()

### Community 58 - "Twaha [T]: tasks"
Cohesion: 0.22
Nodes (8): Evidence and next gate (2026-11-13), Never cut, Phase 1: the spine, Phase 2: checks, Phase 3: humans and proof, Phase 4: measurement, Phase 5: freeze, Twaha [T]: tasks

### Community 59 - "httpx"
Cohesion: 0.25
Nodes (7): Muaz [M]: tasks, Never cut, Phase 0: foundations, Phase 1: the spine, one failure end to end, Phase 2: the other failures and the checks, Phase 4: wide outages and measurement, Phase 6: stretch (only if Phase 4 exit is met early)

### Community 68 - "Muaz [M]: state"
Cohesion: 0.33
Nodes (5): Blocked / waiting on, In progress, Muaz [M]: state, Next, Notes for my next session

### Community 70 - "Contracts (agreed interfaces between owners)"
Cohesion: 0.29
Nodes (6): Cause, Contracts (agreed interfaces between owners), Open questions, Rules for agents, Shared context (all agents read and write this), VERIFY results (§3.3, Phase 0)

## Knowledge Gaps
- **1 isolated node(s):** `oncall-agent`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 325 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `kubectl()` connect `test_chaos.py` to `Anirudh [A]: architecture of my part`, `6.4 Gateway (`gateway/`) [M] P0 unless marked`, `9. Benchmark (`bench/`) [T] P1`, `3. Environment setup`?**
  _High betweenness centrality (0.100) - this node is a cross-community bridge._
- **Are the 14 inferred relationships involving `ActionRequest` (e.g. with `call_tool()` and `DiagnosisResult`) actually correct?**
  _`ActionRequest` has 14 INFERRED edges - model-reasoned connections that need verification._
- **What connects `oncall-agent` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `NotifierState` be split into smaller, more focused modules?**
  _Cohesion score 0.05925925925925926 - nodes in this community are weakly interconnected._
- **Why does `GatewayDecision` connect `GatewayDecision` to `NotifierState`, `test_audit.py`, `test_gateway.py`, `harness.py`, `test_brain.py`, `Contracts (agreed interfaces between owners)`, `Incident`, `ActionRequest`, `models.py`, `checklist.py`, `NotificationConsumer`, `build_from_env`?**
  _High betweenness centrality (0.072) - this node is a cross-community bridge._
- **Are the 10 inferred relationships involving `GatewayDecision` (e.g. with `HttpTrialServices` and `Brain`) actually correct?**
  _`GatewayDecision` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_audit.py` be split into smaller, more focused modules?**
  _Cohesion score 0.052349336057201226 - nodes in this community are weakly interconnected._