# Graph Report - devhack2026  (2026-11-13)

## Corpus Check
- 113 files · ~54,634 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 5 file(s) not represented in the graph (top: (none) 3, .example 1, .lock 1)

## Summary
- 1101 nodes · 2786 edges · 71 communities (53 shown, 18 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 249 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c2c2be33`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- typing
- test_audit.py
- 6.4 Gateway (`gateway/`) [M] P0 unless marked
- test_bench.py
- DiagnosisService
- test_timeout_keeps_detection_and_diagnosis_measurements
- AGENTS.md
- CLAUDE.md
- 10. Build plan
- llm.py
- json
- gateway/main.py
- Implementation Plan: the on-call agent that has to earn its autonomy
- brain/main.py
- InferenceResponse
- models.py
- test_observer.py
- On-call agent: Twaha components
- Observer
- HttpTrialServices
- FakeApps
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
- create_app
- harm_check
- journal.py
- .observe
- det
- test_trust_integration.py
- security_check.sh
- make_kubeconfigs.sh
- install_shop.sh
- match
- setup_cluster.sh
- observer/main.py
- Tracker
- test_verify_loop.py
- test_chaos.py
- TrialServices
- pytest
- charge.js
- InferenceProvider
- test_resume_counts_recorded_attempts_and_does_not_repeat_fault
- connect
- Twaha [T]: tasks
- Muaz [M]: tasks
- httpx
- build_mcp
- build_bad_payment.sh
- smoke.sh
- Muaz [M]: architecture of my part
- Twaha [T]: architecture of my part
- approvals.py
- baselines.py
- Muaz [M]: state
- test_verifier_safety.py
- Shared context (all agents read and write this)

## God Nodes (most connected - your core abstractions)
1. `ActionRequest` - 36 edges
2. `connect()` - 34 edges
3. `GatewayDecision` - 34 edges
4. `DiagnosisService` - 33 edges
5. `Gateway` - 32 edges
6. `ReceiptStore` - 24 edges
7. `Incident` - 24 edges
8. `HttpTrialServices` - 23 edges
9. `Receipt` - 23 edges
10. `redact_value()` - 22 edges

## Surprising Connections (you probably didn't know these)
- `Hard rules my code must keep` --references--> `redact()`  [INFERRED]
  team/twaha/ARCHITECTURE.md → brain/redact.py
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

## Communities (71 total, 18 thin omitted)

### Community 0 - "typing"
Cohesion: 0.06
Nodes (20): Notifier, NotificationConsumer, ApprovalButton, ApprovalController, ApprovalView, DiscordNotifier, health(), lifespan() (+12 more)

### Community 1 - "test_audit.py"
Cohesion: 0.08
Nodes (36): AuditLog, canonical(), EventBus, verify(), active_bus(), create_events_router(), events(), stream() (+28 more)

### Community 2 - "6.4 Gateway (`gateway/`) [M] P0 unless marked"
Cohesion: 0.05
Nodes (40): 6.1 Chaos panel (`chaos/`) [A] P0, 6.2.1 Baselines (`baselines.py`), 6.2.2 Detector (`detector.py`), 6.2.3 Kubernetes watch (`kube_watch.py`), 6.2.4 Change journal (`journal.py`), 6.2.5 Flags (`flags.py`), 6.2 Observer (`observer/`) [M] P0, 6.3.1 Dependency graph (`graph.py`) (+32 more)

### Community 3 - "test_bench.py"
Cohesion: 0.16
Nodes (11): Harness, measure(), TrialResult, FakeServices, test_failed_attempts_count_toward_resume_target(), test_resume_corrupt_file_fails_before_reset(), test_disabled_harness_never_resets_or_injects(), test_failed_trial_persisted_and_next_trial_runs() (+3 more)

### Community 4 - "DiagnosisService"
Cohesion: 0.26
Nodes (14): DiagnosisResult, DiagnosisService, Diagnosis, diagnosis(), FakeProvider, test_cache_disk_failure_does_not_discard_diagnosis(), test_cache_is_exact_and_marked(), test_deadline_falls_back_to_rule() (+6 more)

### Community 6 - "AGENTS.md"
Cohesion: 0.18
Nodes (10): Code comments, Commands, Commits, Communication, Dependencies, Git safety, graphify, Secrets (+2 more)

### Community 7 - "CLAUDE.md"
Cohesion: 0.18
Nodes (10): Code comments, Commands, Commits, Communication, Dependencies, Git safety, graphify, Secrets (+2 more)

### Community 8 - "10. Build plan"
Cohesion: 0.22
Nodes (9): 10. Build plan, Cut order if time runs short, Phase 0: foundations (about 2 h, everyone), Phase 1: the spine, one failure end to end (about 5 h) P0, Phase 2: the other failures and the checks (about 5 h) P0, Phase 3: trust, humans, proof (about 5 h) P1, Phase 4: wide outages and measurement (about 4 h) P1, Phase 5: freeze and polish (about 4 h) (+1 more)

### Community 9 - "llm.py"
Cohesion: 0.17
Nodes (12): quarantine(), redact(), redact_value(), clean(), test_adversarial_proposal(), test_forbidden_tools(), test_poisoned_log(), test_hash_and_token_counts_survive_nested_redaction() (+4 more)

### Community 10 - "json"
Cohesion: 0.20
Nodes (15): rv(), _flatten(), _h(), namespace_hash(), outside_allowed(), previous_template(), rollback_patch(), spec_diff() (+7 more)

### Community 11 - "gateway/main.py"
Cohesion: 0.13
Nodes (9): approvers_from_env(), build_from_env(), create_app(), lifespan(), Decide, RehearsalCredit, require_env(), load() (+1 more)

### Community 12 - "Implementation Plan: the on-call agent that has to earn its autonomy"
Cohesion: 0.29
Nodes (6): 12. Risks and fallbacks, 13. Submission checklist, 14. Command cheat sheet, 2. Repository layout, 7. End-to-end flows (acceptance scenarios), Implementation Plan: the on-call agent that has to earn its autonomy

### Community 13 - "brain/main.py"
Cohesion: 0.05
Nodes (53): build_bundle(), change_evidence(), collect_k8s(), k8s_evidence(), log_evidence(), memory_ratio(), metric_evidence(), _span_error_text() (+45 more)

### Community 14 - "InferenceResponse"
Cohesion: 0.18
Nodes (7): InferenceRequest, InferenceResponse, ProviderError, OpenCodeGoAdapter, generate(), test_adapter_headers_and_wire_shape(), test_provider_errors_are_sanitized()

### Community 15 - "models.py"
Cohesion: 0.16
Nodes (12): ApprovalDecidedPayload, ApprovalRequestedPayload, CardPayload, Cause, ChecklistPayload, DiagnosisReadyPayload, EvidenceBundle, InferencePayload (+4 more)

### Community 16 - "test_observer.py"
Cohesion: 0.20
Nodes (13): require_env(), Backend, make(), prom_result(), test_brain_down_does_not_stop_detection(), handler(), test_endpoints(), test_nan_rows_are_dropped() (+5 more)

### Community 17 - "On-call agent: Twaha components"
Cohesion: 0.18
Nodes (8): check(), usage(), Benchmarks and adversarial checks, Discord notifier, Inference, On-call agent: Twaha components, Project graph, Setup and checks

### Community 18 - "Observer"
Cohesion: 0.18
Nodes (4): Detector, fetch_readings(), prom_query(), Observer

### Community 19 - "HttpTrialServices"
Cohesion: 0.20
Nodes (10): HttpTrialServices, stream(), test_health_wait_requires_current_metrics_and_retries_startup(), test_reconnect_resumes_cursor_and_ignores_duplicate_events(), handle(), test_replayed_approval_does_not_repeat_post(), handle(), test_stale_metrics_restart_the_entire_stability_window() (+2 more)

### Community 20 - "FakeApps"
Cohesion: 0.15
Nodes (6): FakeApps, FakeCore, Observer, Resp, rs(), template()

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
Cohesion: 0.20
Nodes (6): Gateway, ActionRequest, GatewayDecision, Open questions, test_mcp_exposes_six_tools_with_actable_targets_only(), submit()

### Community 32 - "test_gateway.py"
Cohesion: 0.27
Nodes (14): Phase 3: trust, humans, proof, action(), test_approval_rules(), test_bad_deploy_asks_then_rolls_back_on_approval(), test_budget_and_in_flight(), test_conflict_on_execute_hands_off_and_admission_denial_escalates(), test_dry_run_outside_template_escalates(), test_http_app_routes() (+6 more)

### Community 34 - "Done (with proof)"
Cohesion: 0.18
Nodes (5): Manual baseline, call_tool(), Verification, read(), Done (with proof)

### Community 38 - "harm_check"
Cohesion: 0.18
Nodes (8): harm_check(), ledger_effect(), service_score(), HarmCheckTest, health(), svc(), verification(), VerifierTest

### Community 39 - "journal.py"
Cohesion: 0.13
Nodes (16): check(), author(), _configmap_changes(), _containers(), current(), _deployment_changes(), entry(), insert() (+8 more)

### Community 40 - ".observe"
Cohesion: 0.16
Nodes (7): ObservationError, test_rehearsal_credits_action_receipt_with_false_diagnosis(), test_rehearsal_disabled_before_any_network_call(), test_rehearsal_hooks_only_when_enabled(), handle(), test_rehearsal_refusal_stops_credit(), test_rehearsal_without_receipt_never_submits_credit()

### Community 42 - "test_trust_integration.py"
Cohesion: 0.13
Nodes (14): main(), summarize_ledger(), check(), counts(), eligible(), lower_bound(), record(), health() (+6 more)

### Community 46 - "match"
Cohesion: 0.29
Nodes (7): _action(), latest_change_before_onset(), match(), to_bytes(), change(), incident(), RulesTest

### Community 48 - "observer/main.py"
Cohesion: 0.27
Nodes (10): bad_pods(), pod_bad(), service_of(), _ts(), deployment(), iso(), pod(), test_bad_pod_rules() (+2 more)

### Community 49 - "Tracker"
Cohesion: 0.16
Nodes (9): run_watch(), Tracker, build_from_env(), lifespan(), FakeResp, test_run_watch_relists_after_error(), list_fn(), test_tracker_journals_changes_including_after_relist() (+1 more)

### Community 50 - "test_verify_loop.py"
Cohesion: 0.30
Nodes (11): executed(), healthy(), ledger(), Script, sick(), test_early_abort_pauses_undoes_resumes(), test_human_change_during_verify_hands_off_without_undo(), test_no_recovery_undoes_and_escalates() (+3 more)

### Community 51 - "test_chaos.py"
Cohesion: 0.05
Nodes (48): bad_deploy(), kubectl(), KubectlError, read_all(), record(), create_app(), bad_deploy(), do_reset() (+40 more)

### Community 53 - "pytest"
Cohesion: 0.25
Nodes (9): Event, Prediction, test_action_rejects_invented_pattern(), test_evidence_rejects_nonfinite_timestamp(), test_payload_contract_rejects_incomplete_approval(), test_payload_rejects_cross_incident_card(), test_prediction_deadline_is_bounded(), test_shared_pattern_values() (+1 more)

### Community 54 - "charge.js"
Cohesion: 0.10
Nodes (14): { ATTR_ERROR_TYPE }, cardValidator, charge(), { context, propagation, trace, metrics, SpanStatusCode }, { FlagdProvider }, flagProvider, logger, LOYALTY_LEVEL (+6 more)

### Community 55 - "InferenceProvider"
Cohesion: 0.17
Nodes (8): InferenceProvider, Blocked / waiting on, Done (with proof), In progress, Next, Notes for next session, Twaha [T]: state, Phase 0: foundations

### Community 58 - "Twaha [T]: tasks"
Cohesion: 0.22
Nodes (8): Evidence and next gate (2026-11-13), Never cut, Phase 1: the spine, Phase 2: checks, Phase 3: humans and proof, Phase 4: measurement, Phase 5: freeze, Twaha [T]: tasks

### Community 59 - "Muaz [M]: tasks"
Cohesion: 0.25
Nodes (7): Muaz [M]: tasks, Never cut, Phase 0: foundations, Phase 1: the spine, one failure end to end, Phase 2: the other failures and the checks, Phase 4: wide outages and measurement, Phase 6: stretch (only if Phase 4 exit is met early)

### Community 64 - "Muaz [M]: architecture of my part"
Cohesion: 0.29
Nodes (6): Flow through my code, Hard rules my code must keep, Muaz [M]: architecture of my part, What I need from others, What I own, What I provide to others

### Community 65 - "Twaha [T]: architecture of my part"
Cohesion: 0.29
Nodes (6): Flow through my parts, Hard rules my code must keep, Twaha [T]: architecture of my part, What I need from others, What I own, What I provide to others

### Community 66 - "approvals.py"
Cohesion: 0.53
Nodes (3): create(), get(), set_state()

### Community 67 - "baselines.py"
Cohesion: 0.53
Nodes (3): load(), medians(), store()

### Community 68 - "Muaz [M]: state"
Cohesion: 0.33
Nodes (5): Blocked / waiting on, In progress, Muaz [M]: state, Next, Notes for my next session

### Community 69 - "test_verifier_safety.py"
Cohesion: 0.90
Nodes (4): service(), test_human_change_takes_priority_over_early_abort(), test_missing_service_cannot_confirm_recovery_after_prediction(), verification()

### Community 70 - "Shared context (all agents read and write this)"
Cohesion: 0.50
Nodes (3): Rules for agents, Shared context (all agents read and write this), VERIFY results (§3.3, Phase 0)

## Knowledge Gaps
- **1 isolated node(s):** `oncall-agent`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 321 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **18 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ActionRequest` connect `ActionRequest` to `test_gateway.py`, `Done (with proof)`, `DiagnosisService`, `llm.py`, `json`, `test_trust_integration.py`, `brain/main.py`, `models.py`, `test_verify_loop.py`, `pytest`, `8. Testing`?**
  _High betweenness centrality (0.072) - this node is a cross-community bridge._
- **Are the 14 inferred relationships involving `ActionRequest` (e.g. with `call_tool()` and `DiagnosisResult`) actually correct?**
  _`ActionRequest` has 14 INFERRED edges - model-reasoned connections that need verification._
- **What connects `oncall-agent` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `typing` be split into smaller, more focused modules?**
  _Cohesion score 0.06350877192982456 - nodes in this community are weakly interconnected._
- **Why does `kubectl()` connect `test_chaos.py` to `6.4 Gateway (`gateway/`) [M] P0 unless marked`, `9. Benchmark (`bench/`) [T] P1`, `3. Environment setup`, `ActionRequest`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Are the 10 inferred relationships involving `GatewayDecision` (e.g. with `HttpTrialServices` and `Brain`) actually correct?**
  _`GatewayDecision` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_audit.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0818452380952381 - nodes in this community are weakly interconnected._