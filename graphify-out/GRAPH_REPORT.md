# Graph Report - devhack2026  (2026-11-13)

## Corpus Check
- 109 files · ~50,484 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 5 file(s) not represented in the graph (top: (none) 3, .example 1, .lock 1)

## Summary
- 1041 nodes · 2556 edges · 60 communities (48 shown, 12 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 221 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `3438f3f7`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- NotifierState
- ReceiptStore
- 6.4 Gateway (`gateway/`) [M] P0 unless marked
- HttpTrialServices
- InferenceResponse
- DiagnosisService
- AGENTS.md
- CLAUDE.md
- 10. Build plan
- kubectl
- test_gateway.py
- Twaha [T]: tasks
- Implementation Plan: the on-call agent that has to earn its autonomy
- json
- Anirudh [A]: architecture of my part
- Anirudh [A]: state
- test_observer.py
- pytest
- test_audit.py
- harness.py
- InferenceProvider
- 3. Environment setup
- 8. Testing
- audit.py
- 0. Scope and principles
- 11. Demo
- 1. System overview
- 4. Configuration files
- 5. Data model
- 9. Benchmark (`bench/`) [T] P1
- models.py
- test_integration.py
- ActionRequest
- oncall-agent
- test_timeout_keeps_detection_and_diagnosis_measurements
- 6.3 Brain (`brain/`) [M] P0 unless marked
- journal.py
- find_culprit
- Detector
- connect
- security_check.sh
- make_kubeconfigs.sh
- install_shop.sh
- match
- setup_cluster.sh
- 6. Component specifications
- 6.2 Observer (`observer/`) [M] P0
- test_bench.py
- test_chaos.py
- 6.5 Kubernetes security manifests (`k8s/`) [M] P0
- checklist.py
- charge.js
- redact_value
- TrialServices
- test_resume_counts_recorded_attempts_and_does_not_repeat_fault
- build_bad_payment.sh
- smoke.sh

## God Nodes (most connected - your core abstractions)
1. `connect()` - 34 edges
2. `DiagnosisService` - 31 edges
3. `ActionRequest` - 27 edges
4. `Gateway` - 26 edges
5. `GatewayDecision` - 25 edges
6. `ReceiptStore` - 24 edges
7. `Incident` - 23 edges
8. `NotifierState` - 22 edges
9. `HttpTrialServices` - 21 edges
10. `redact_value()` - 21 edges

## Surprising Connections (you probably didn't know these)
- `Phase 2: the other failures and the checks` --references--> `DiagnosisService`  [INFERRED]
  team/muaz/TASK.md → brain/llm.py
- `3.1 Prerequisites [A] P0` --references--> `kubectl()`  [INFERRED]
  IMPLEMENTATION.md → chaos/faults.py
- `6.1 Chaos panel (`chaos/`) [A] P0` --references--> `kubectl()`  [INFERRED]
  IMPLEMENTATION.md → chaos/faults.py
- `6.8 UI (`ui/`, Next.js) [A] P1` --references--> `kubectl()`  [INFERRED]
  IMPLEMENTATION.md → chaos/faults.py
- `9.2 Manual baseline (`manual_baseline.md`)` --references--> `kubectl()`  [INFERRED]
  IMPLEMENTATION.md → chaos/faults.py

## Import Cycles
- None detected.

## Communities (60 total, 12 thin omitted)

### Community 0 - "NotifierState"
Cohesion: 0.06
Nodes (22): Notifier, NotificationConsumer, ApprovalButton, ApprovalController, ApprovalView, DiscordNotifier, health(), lifespan() (+14 more)

### Community 1 - "ReceiptStore"
Cohesion: 0.23
Nodes (13): build_card(), build_incident_card(), create_receipts_router(), get(), ReceiptStore, Gateway mounting, Receipt, Log (append-only, newest at bottom) (+5 more)

### Community 2 - "6.4 Gateway (`gateway/`) [M] P0 unless marked"
Cohesion: 0.17
Nodes (12): 6.4.10 Watchdog (`watchdog.py`) P1, 6.4.11 One retry (P2), 6.4.1 MCP server (`mcp_server.py`), 6.4.2 The checklist (`checklist.py`), 6.4.3 Dry run and snapshot (`dryrun.py`), 6.4.4 Blast radius and net benefit (`blast.py`) P1, 6.4.5 Freshness (`freshness.py`), 6.4.6 Trust gate (`trust.py`) P1 (+4 more)

### Community 3 - "HttpTrialServices"
Cohesion: 0.15
Nodes (9): HttpTrialServices, ObservationError, test_uncertain_approval_post_is_not_retried(), test_rehearsal_credits_action_receipt_with_false_diagnosis(), test_rehearsal_disabled_before_any_network_call(), test_rehearsal_hooks_only_when_enabled(), handle(), test_rehearsal_refusal_stops_credit() (+1 more)

### Community 4 - "InferenceResponse"
Cohesion: 0.16
Nodes (9): InferenceRequest, InferenceResponse, ProviderError, OpenCodeGoAdapter, test_adversarial_proposal(), generate(), test_adapter_headers_and_wire_shape(), test_provider_errors_are_sanitized() (+1 more)

### Community 5 - "DiagnosisService"
Cohesion: 0.36
Nodes (12): DiagnosisService, diagnosis(), FakeProvider, test_cache_disk_failure_does_not_discard_diagnosis(), test_cache_is_exact_and_marked(), test_deadline_falls_back_to_rule(), test_fabricated_evidence_rejected(), test_invalid_json_retries_and_preserves_rule() (+4 more)

### Community 6 - "AGENTS.md"
Cohesion: 0.18
Nodes (10): Code comments, Commands, Commits, Communication, Dependencies, Git safety, graphify, Secrets (+2 more)

### Community 7 - "CLAUDE.md"
Cohesion: 0.18
Nodes (10): Code comments, Commands, Commits, Communication, Dependencies, Git safety, graphify, Secrets (+2 more)

### Community 8 - "10. Build plan"
Cohesion: 0.22
Nodes (9): 10. Build plan, Cut order if time runs short, Phase 0: foundations (about 2 h, everyone), Phase 1: the spine, one failure end to end (about 5 h) P0, Phase 2: the other failures and the checks (about 5 h) P0, Phase 3: trust, humans, proof (about 5 h) P1, Phase 4: wide outages and measurement (about 4 h) P1, Phase 5: freeze and polish (about 4 h) (+1 more)

### Community 9 - "kubectl"
Cohesion: 0.18
Nodes (10): kubectl(), Anirudh [A]: tasks, Never cut, Phase 0: foundations, Phase 1: the spine, Phase 2: the other failures, Phase 3: UI, Phase 4: more UI (+2 more)

### Community 10 - "test_gateway.py"
Cohesion: 0.06
Nodes (40): _flatten(), _h(), namespace_hash(), outside_allowed(), previous_template(), rollback_patch(), spec_diff(), classify() (+32 more)

### Community 11 - "Twaha [T]: tasks"
Cohesion: 0.20
Nodes (9): Integration proof (2026-11-13), Never cut, Phase 0: foundations, Phase 1: the spine, Phase 2: checks, Phase 3: humans and proof, Phase 5: freeze, Twaha [T]: tasks (+1 more)

### Community 12 - "Implementation Plan: the on-call agent that has to earn its autonomy"
Cohesion: 0.29
Nodes (6): 12. Risks and fallbacks, 13. Submission checklist, 14. Command cheat sheet, 2. Repository layout, 7. End-to-end flows (acceptance scenarios), Implementation Plan: the on-call agent that has to earn its autonomy

### Community 13 - "json"
Cohesion: 0.06
Nodes (45): build_bundle(), change_evidence(), collect_k8s(), k8s_evidence(), log_evidence(), memory_ratio(), metric_evidence(), _span_error_text() (+37 more)

### Community 14 - "Anirudh [A]: architecture of my part"
Cohesion: 0.29
Nodes (6): Anirudh [A]: architecture of my part, Flow through my parts, Hard rules my code must keep, What I need from others, What I own, What I provide to others

### Community 15 - "Anirudh [A]: state"
Cohesion: 0.29
Nodes (6): Anirudh [A]: state, Blocked / waiting on, Done (with proof), In progress, Next, Notes for my next session

### Community 16 - "test_observer.py"
Cohesion: 0.06
Nodes (38): load(), medians(), store(), bad_pods(), pod_bad(), run_watch(), service_of(), Tracker (+30 more)

### Community 17 - "pytest"
Cohesion: 0.25
Nodes (9): Event, Prediction, test_action_rejects_invented_pattern(), test_evidence_rejects_nonfinite_timestamp(), test_payload_contract_rejects_incomplete_approval(), test_payload_rejects_cross_incident_card(), test_prediction_deadline_is_bounded(), test_shared_pattern_values() (+1 more)

### Community 18 - "test_audit.py"
Cohesion: 0.22
Nodes (9): AuditLog, EventBus, test_audit_cli_runs_from_repository_root(), test_corrupt_record_reports_sequence(), test_disconnect_cleans_subscription(), test_events_replay_and_overflow(), test_incident_card_variants(), test_publish_does_not_emit_if_disk_fails() (+1 more)

### Community 19 - "harness.py"
Cohesion: 0.28
Nodes (7): Harness, main(), measure(), TrialResult, test_failed_attempts_count_toward_resume_target(), test_resume_corrupt_file_fails_before_reset(), test_sync_provider_usage_normalizes_without_double_counting()

### Community 20 - "InferenceProvider"
Cohesion: 0.17
Nodes (7): InferenceProvider, Blocked / waiting on, Done (with proof), In progress, Next, Notes for my next session, Twaha [T]: state

### Community 21 - "3. Environment setup"
Cohesion: 0.33
Nodes (6): 3.1 Prerequisites [A] P0, 3.2 Cluster [A] P0, 3.3 The shop [A] P0, 3.4 The buggy payment image [A] P0, 3.5 Kubeconfigs for the three identities [M] P0, 3. Environment setup

### Community 22 - "8. Testing"
Cohesion: 0.40
Nodes (5): 8.1 Unit tests [M][T] P0, 8.2 Property-based tests (`test_invariants.py`, Hypothesis) [M] P1, 8.3 Red-team suite (`tests/redteam/`) [T] P1, 8.4 Smoke test (`scripts/smoke.sh`) [A] P0, 8. Testing

### Community 23 - "audit.py"
Cohesion: 0.20
Nodes (6): main(), summarize(), canonical(), verify(), main(), test_chain_tamper_and_concurrent_append()

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

### Community 30 - "models.py"
Cohesion: 0.13
Nodes (14): DiagnosisResult, ApprovalDecidedPayload, ApprovalRequestedPayload, CardPayload, Cause, ChecklistPayload, Diagnosis, DiagnosisReadyPayload (+6 more)

### Community 32 - "test_integration.py"
Cohesion: 0.18
Nodes (10): active_bus(), create_events_router(), events(), stream(), publish_event(), selected_bus(), lifespan(), publish() (+2 more)

### Community 34 - "ActionRequest"
Cohesion: 0.09
Nodes (21): create(), get(), set_state(), Gateway, check(), usage(), 6.5.2 `rbac-agent.yaml`, Benchmarks and adversarial checks (+13 more)

### Community 37 - "test_timeout_keeps_detection_and_diagnosis_measurements"
Cohesion: 0.20
Nodes (8): stream(), test_reconnect_resumes_cursor_and_ignores_duplicate_events(), handle(), test_replayed_approval_does_not_repeat_post(), handle(), test_timeout_keeps_detection_and_diagnosis_measurements(), handle(), handle()

### Community 38 - "6.3 Brain (`brain/`) [M] P0 unless marked"
Cohesion: 0.22
Nodes (9): 6.3.1 Dependency graph (`graph.py`), 6.3.2 Culprit (`culprit.py`), 6.3.3 Major-incident analysis (`major.py`) P1, 6.3.4 Evidence bundle (`bundle.py`), 6.3.5 Redaction and quarantine (`redact.py`), 6.3.6 Rules (`rules.py`), 6.3.7 Claude call (`llm.py`), 6.3.8 Orchestration (`main.py`) (+1 more)

### Community 39 - "journal.py"
Cohesion: 0.13
Nodes (17): check(), author(), _configmap_changes(), _containers(), current(), _deployment_changes(), entry(), insert() (+9 more)

### Community 40 - "find_culprit"
Cohesion: 0.28
Nodes (5): deepest_unhealthy(), depth(), find_culprit(), CulpritTest, trace()

### Community 41 - "Detector"
Cohesion: 0.16
Nodes (5): Detector, fetch_readings(), prom_query(), det(), DetectorTest

### Community 42 - "connect"
Cohesion: 0.05
Nodes (37): Manual baseline, main(), summarize_ledger(), spec_hashes(), check(), counts(), eligible(), lower_bound() (+29 more)

### Community 46 - "match"
Cohesion: 0.29
Nodes (7): _action(), latest_change_before_onset(), match(), to_bytes(), change(), incident(), RulesTest

### Community 48 - "6. Component specifications"
Cohesion: 0.29
Nodes (7): 6.1 Chaos panel (`chaos/`) [A] P0, 6.6 Notifier (`notifier/`) [T] P1, 6.7.1 Incident card, 6.7.2 Audit log (`data/audit.jsonl`), 6.7 Report (`gateway/receipts.py`, `gateway/audit.py`) [T] P0, 6.8 UI (`ui/`, Next.js) [A] P1, 6. Component specifications

### Community 49 - "6.2 Observer (`observer/`) [M] P0"
Cohesion: 0.33
Nodes (6): 6.2.1 Baselines (`baselines.py`), 6.2.2 Detector (`detector.py`), 6.2.3 Kubernetes watch (`kube_watch.py`), 6.2.4 Change journal (`journal.py`), 6.2.5 Flags (`flags.py`), 6.2 Observer (`observer/`) [M] P0

### Community 50 - "test_bench.py"
Cohesion: 0.19
Nodes (9): compare(), main(), summarize(), FakeServices, test_disabled_harness_never_resets_or_injects(), test_failed_trial_persisted_and_next_trial_runs(), test_manual_comparison_preserves_missing_measurements(), test_matching_pattern_wrong_culprit_is_not_correct() (+1 more)

### Community 51 - "test_chaos.py"
Cohesion: 0.10
Nodes (26): bad_deploy(), KubectlError, read_all(), record(), create_app(), bad_deploy(), do_reset(), lifespan() (+18 more)

### Community 52 - "6.5 Kubernetes security manifests (`k8s/`) [M] P0"
Cohesion: 0.40
Nodes (5): 6.5.1 `rbac-reader.yaml`, 6.5.3 `admission-policy.yaml`, 6.5.4 `admission-binding.yaml`, 6.5.5 Acceptance tests for the security layer (do these on day one), 6.5 Kubernetes security manifests (`k8s/`) [M] P0

### Community 53 - "checklist.py"
Cohesion: 0.11
Nodes (9): approvers_from_env(), build_from_env(), create_app(), lifespan(), Decide, require_env(), build_mcp(), make() (+1 more)

### Community 54 - "charge.js"
Cohesion: 0.10
Nodes (14): { ATTR_ERROR_TYPE }, cardValidator, charge(), { context, propagation, trace, metrics, SpanStatusCode }, { FlagdProvider }, flagProvider, logger, LOYALTY_LEVEL (+6 more)

### Community 55 - "redact_value"
Cohesion: 0.10
Nodes (21): quarantine(), redact(), redact_value(), clean(), Flow through my code, Hard rules my code must keep, Muaz [M]: architecture of my part, What I need from others (+13 more)

## Knowledge Gaps
- **1 isolated node(s):** `oncall-agent`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 310 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **12 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `kubectl()` connect `kubectl` to `ActionRequest`, `Anirudh [A]: architecture of my part`, `Anirudh [A]: state`, `6. Component specifications`, `test_chaos.py`, `3. Environment setup`, `9. Benchmark (`bench/`) [T] P1`?**
  _High betweenness centrality (0.108) - this node is a cross-community bridge._
- **Are the 10 inferred relationships involving `DiagnosisService` (e.g. with `InferenceProvider` and `InferenceRequest`) actually correct?**
  _`DiagnosisService` has 10 INFERRED edges - model-reasoned connections that need verification._
- **What connects `oncall-agent` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `NotifierState` be split into smaller, more focused modules?**
  _Cohesion score 0.06151742993848257 - nodes in this community are weakly interconnected._
- **Why does `ActionRequest` connect `ActionRequest` to `NotifierState`, `DiagnosisService`, `connect`, `json`, `pytest`, `checklist.py`, `8. Testing`, `models.py`?**
  _High betweenness centrality (0.086) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `ActionRequest` (e.g. with `DiagnosisResult` and `DiagnosisService`) actually correct?**
  _`ActionRequest` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_gateway.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05952380952380952 - nodes in this community are weakly interconnected._