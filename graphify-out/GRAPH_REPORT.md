# Graph Report - devhack2026  (2026-11-13)

## Corpus Check
- 114 files · ~57,161 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 5 file(s) not represented in the graph (top: (none) 3, .example 1, .lock 1)

## Summary
- 1139 nodes · 2918 edges · 64 communities (45 shown, 19 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 256 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `ce576ef8`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- NotifierState
- test_audit.py
- 6.4 Gateway (`gateway/`) [M] P0 unless marked
- test_bench.py
- DiagnosisService
- httpx
- AGENTS.md
- CLAUDE.md
- 10. Build plan
- Card
- dryrun.py
- NotificationConsumer
- Implementation Plan: the on-call agent that has to earn its autonomy
- brain/main.py
- test_bench_recovery.py
- models.py
- Observer
- test_observer.py
- HttpTrialServices
- checklist.py
- pathlib
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
- Verification
- oncall-agent
- observer/main.py
- harm_check
- journal.py
- det
- connect
- security_check.sh
- make_kubeconfigs.sh
- install_shop.sh
- match
- setup_cluster.sh
- gateway/main.py
- test_kube_watch.py
- .observe
- json
- test_rehearsal_credits_action_receipt_with_false_diagnosis
- TrialServices
- charge.js
- Muaz [M]: architecture of my part
- test_run_watch_relists_after_error
- ApprovalButton
- detector.py
- test_attacks.py
- test_resume_counts_recorded_attempts_and_does_not_repeat_fault
- build_bad_payment.sh
- smoke.sh
- Done (with proof)

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
- `6.1 Chaos panel (`chaos/`) [A] P0` --references--> `kubectl()`  [INFERRED]
  IMPLEMENTATION.md → chaos/faults.py
- `6.8 UI (`ui/`, Next.js) [A] P1` --references--> `kubectl()`  [INFERRED]
  IMPLEMENTATION.md → chaos/faults.py
- `9.2 Manual baseline (`manual_baseline.md`)` --references--> `kubectl()`  [INFERRED]
  IMPLEMENTATION.md → chaos/faults.py
- `5.3 Event types (SSE and audit)` --references--> `harm_check()`  [INFERRED]
  IMPLEMENTATION.md → gateway/verifier.py

## Import Cycles
- None detected.

## Communities (64 total, 19 thin omitted)

### Community 0 - "NotifierState"
Cohesion: 0.24
Nodes (6): ApprovalController, NotifierState, test_unauthorized_approval_never_calls_gateway(), test_approval_auth_expiry_duplicate_and_gateway_refusal(), test_gateway_refusal_does_not_record_approval(), test_success_status_with_refusal_body_is_not_approval()

### Community 1 - "test_audit.py"
Cohesion: 0.06
Nodes (54): DiagnosisResult, quarantine(), redact(), redact_value(), AuditLog, canonical(), EventBus, verify() (+46 more)

### Community 2 - "6.4 Gateway (`gateway/`) [M] P0 unless marked"
Cohesion: 0.05
Nodes (43): create(), get(), set_state(), 6.1 Chaos panel (`chaos/`) [A] P0, 6.2.1 Baselines (`baselines.py`), 6.2.2 Detector (`detector.py`), 6.2.3 Kubernetes watch (`kube_watch.py`), 6.2.4 Change journal (`journal.py`) (+35 more)

### Community 3 - "test_bench.py"
Cohesion: 0.20
Nodes (10): Harness, measure(), TrialResult, FakeServices, test_disabled_harness_never_resets_or_injects(), test_failed_trial_persisted_and_next_trial_runs(), test_manual_comparison_preserves_missing_measurements(), test_matching_pattern_wrong_culprit_is_not_correct() (+2 more)

### Community 4 - "DiagnosisService"
Cohesion: 0.07
Nodes (38): DiagnosisService, InferenceProvider, InferenceRequest, InferenceResponse, ProviderError, OpenCodeGoAdapter, Blocked / waiting on, Done (with proof) (+30 more)

### Community 6 - "AGENTS.md"
Cohesion: 0.18
Nodes (10): Code comments, Commands, Commits, Communication, Dependencies, Git safety, graphify, Secrets (+2 more)

### Community 7 - "CLAUDE.md"
Cohesion: 0.18
Nodes (10): Code comments, Commands, Commits, Communication, Dependencies, Git safety, graphify, Secrets (+2 more)

### Community 8 - "10. Build plan"
Cohesion: 0.22
Nodes (9): 10. Build plan, Cut order if time runs short, Phase 0: foundations (about 2 h, everyone), Phase 1: the spine, one failure end to end (about 5 h) P0, Phase 2: the other failures and the checks (about 5 h) P0, Phase 3: trust, humans, proof (about 5 h) P1, Phase 4: wide outages and measurement (about 4 h) P1, Phase 5: freeze and polish (about 4 h) (+1 more)

### Community 9 - "Card"
Cohesion: 0.21
Nodes (4): Notifier, ApprovalView, DiscordNotifier, Card

### Community 10 - "dryrun.py"
Cohesion: 0.17
Nodes (14): build_patch(), _flatten(), _h(), namespace_hash(), outside_allowed(), previous_template(), rollback_patch(), _single_container() (+6 more)

### Community 11 - "NotificationConsumer"
Cohesion: 0.18
Nodes (3): NotificationConsumer, test_consumer_restart_deduplicates_and_resolves_wake(), test_repage_expiry_and_persistent_buttons()

### Community 12 - "Implementation Plan: the on-call agent that has to earn its autonomy"
Cohesion: 0.29
Nodes (6): 12. Risks and fallbacks, 13. Submission checklist, 14. Command cheat sheet, 2. Repository layout, 7. End-to-end flows (acceptance scenarios), Implementation Plan: the on-call agent that has to earn its autonomy

### Community 13 - "brain/main.py"
Cohesion: 0.06
Nodes (51): build_bundle(), change_evidence(), collect_k8s(), k8s_evidence(), log_evidence(), memory_ratio(), metric_evidence(), _span_error_text() (+43 more)

### Community 14 - "test_bench_recovery.py"
Cohesion: 0.15
Nodes (10): stream(), test_failed_attempts_count_toward_resume_target(), test_reconnect_resumes_cursor_and_ignores_duplicate_events(), handle(), test_replayed_approval_does_not_repeat_post(), handle(), test_resume_corrupt_file_fails_before_reset(), test_timeout_keeps_detection_and_diagnosis_measurements() (+2 more)

### Community 15 - "models.py"
Cohesion: 0.09
Nodes (24): ApprovalDecidedPayload, ApprovalRequestedPayload, CardPayload, Cause, ChecklistPayload, DiagnosisReadyPayload, Event, InferencePayload (+16 more)

### Community 16 - "Observer"
Cohesion: 0.17
Nodes (5): load(), medians(), store(), Detector, Observer

### Community 17 - "test_observer.py"
Cohesion: 0.23
Nodes (11): Backend, make(), prom_result(), test_brain_down_does_not_stop_detection(), handler(), test_endpoints(), test_nan_rows_are_dropped(), test_prometheus_down_keeps_last_health_and_skips_detector() (+3 more)

### Community 18 - "HttpTrialServices"
Cohesion: 0.18
Nodes (5): HttpTrialServices, main(), test_health_wait_requires_current_metrics_and_retries_startup(), test_stale_metrics_restart_the_entire_stability_window(), test_rehearsal_disabled_before_any_network_call()

### Community 19 - "checklist.py"
Cohesion: 0.38
Nodes (7): rv(), _call(), classify(), list_json(), patch_deployment(), patch_scale(), read_deployment()

### Community 20 - "pathlib"
Cohesion: 0.29
Nodes (6): health(), lifespan(), load_approvers(), required(), test_notifier_rejects_rehearsal_identity_in_human_allowlist(), test_notifier_uses_gateway_approver_setting()

### Community 21 - "3. Environment setup"
Cohesion: 0.33
Nodes (6): 3.1 Prerequisites [A] P0, 3.2 Cluster [A] P0, 3.3 The shop [A] P0, 3.4 The buggy payment image [A] P0, 3.5 Kubeconfigs for the three identities [M] P0, 3. Environment setup

### Community 22 - "8. Testing"
Cohesion: 0.40
Nodes (5): 8.1 Unit tests [M][T] P0, 8.2 Property-based tests (`test_invariants.py`, Hypothesis) [M] P1, 8.3 Red-team suite (`tests/redteam/`) [T] P1, 8.4 Smoke test (`scripts/smoke.sh`) [A] P0, 8. Testing

### Community 23 - "test_bench_export.py"
Cohesion: 0.12
Nodes (18): display(), export_report(), markdown(), timing_svg(), main(), summarize(), compare(), load_rows() (+10 more)

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
Cohesion: 0.32
Nodes (6): Gateway, ActionRequest, GatewayDecision, submit(), test_mcp_exposes_six_tools_with_actable_targets_only(), submit()

### Community 32 - "test_gateway.py"
Cohesion: 0.05
Nodes (48): create_app(), Muaz [M]: tasks, Never cut, Phase 0: foundations, Phase 1: the spine, one failure end to end, Phase 2: the other failures and the checks, Phase 3: trust, humans, proof, Phase 4: wide outages and measurement (+40 more)

### Community 34 - "Verification"
Cohesion: 0.29
Nodes (6): Manual baseline, Verification, service(), test_human_change_takes_priority_over_early_abort(), test_missing_service_cannot_confirm_recovery_after_prediction(), verification()

### Community 37 - "observer/main.py"
Cohesion: 0.15
Nodes (7): build_from_env(), create_app(), get_journal(), lifespan(), require_env(), load(), test_require_env_names_missing()

### Community 38 - "harm_check"
Cohesion: 0.19
Nodes (8): harm_check(), ledger_effect(), service_score(), HarmCheckTest, health(), svc(), verification(), VerifierTest

### Community 39 - "journal.py"
Cohesion: 0.13
Nodes (16): check(), author(), _configmap_changes(), _containers(), current(), _deployment_changes(), entry(), insert() (+8 more)

### Community 42 - "connect"
Cohesion: 0.11
Nodes (16): main(), summarize_ledger(), check(), counts(), eligible(), lower_bound(), record(), connect() (+8 more)

### Community 46 - "match"
Cohesion: 0.14
Nodes (16): _action(), latest_change_before_onset(), match(), to_bytes(), bounds(), check(), usage(), Benchmarks and adversarial checks (+8 more)

### Community 48 - "gateway/main.py"
Cohesion: 0.16
Nodes (8): approvers_from_env(), build_from_env(), lifespan(), Decide, RehearsalCredit, require_env(), build_mcp(), make()

### Community 49 - "test_kube_watch.py"
Cohesion: 0.20
Nodes (14): bad_pods(), pod_bad(), run_watch(), service_of(), Tracker, _ts(), deployment(), iso() (+6 more)

### Community 51 - "json"
Cohesion: 0.05
Nodes (62): bad_deploy(), broken_config(), datastore_down(), kubectl(), KubectlError, memory_leak(), read_flags(), read_live_flags() (+54 more)

### Community 52 - "test_rehearsal_credits_action_receipt_with_false_diagnosis"
Cohesion: 0.25
Nodes (5): test_rehearsal_credits_action_receipt_with_false_diagnosis(), test_rehearsal_hooks_only_when_enabled(), handle(), test_rehearsal_refusal_stops_credit(), test_rehearsal_without_receipt_never_submits_credit()

### Community 54 - "charge.js"
Cohesion: 0.10
Nodes (14): { ATTR_ERROR_TYPE }, cardValidator, charge(), { context, propagation, trace, metrics, SpanStatusCode }, { FlagdProvider }, flagProvider, logger, LOYALTY_LEVEL (+6 more)

### Community 55 - "Muaz [M]: architecture of my part"
Cohesion: 0.33
Nodes (5): Flow through my code, Hard rules my code must keep, Muaz [M]: architecture of my part, What I own, What I provide to others

### Community 56 - "test_run_watch_relists_after_error"
Cohesion: 0.33
Nodes (3): FakeResp, test_run_watch_relists_after_error(), list_fn()

### Community 68 - "Done (with proof)"
Cohesion: 0.12
Nodes (8): call_tool(), read(), Blocked / waiting on, Done (with proof), In progress, Muaz [M]: state, Next, Notes for my next session

## Knowledge Gaps
- **1 isolated node(s):** `oncall-agent`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 323 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **19 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `kubectl()` connect `json` to `6.4 Gateway (`gateway/`) [M] P0 unless marked`, `9. Benchmark (`bench/`) [T] P1`, `3. Environment setup`, `models.py`?**
  _High betweenness centrality (0.096) - this node is a cross-community bridge._
- **Are the 14 inferred relationships involving `ActionRequest` (e.g. with `call_tool()` and `DiagnosisResult`) actually correct?**
  _`ActionRequest` has 14 INFERRED edges - model-reasoned connections that need verification._
- **What connects `oncall-agent` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `test_audit.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05513612445664608 - nodes in this community are weakly interconnected._
- **Why does `ActionRequest` connect `ActionRequest` to `test_gateway.py`, `test_audit.py`, `Done (with proof)`, `DiagnosisService`, `dryrun.py`, `connect`, `brain/main.py`, `models.py`, `checklist.py`, `8. Testing`, `test_attacks.py`?**
  _High betweenness centrality (0.061) - this node is a cross-community bridge._
- **Are the 10 inferred relationships involving `GatewayDecision` (e.g. with `HttpTrialServices` and `Brain`) actually correct?**
  _`GatewayDecision` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Should `6.4 Gateway (`gateway/`) [M] P0 unless marked` be split into smaller, more focused modules?**
  _Cohesion score 0.0463768115942029 - nodes in this community are weakly interconnected._