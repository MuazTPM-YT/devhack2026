# Graph Report - devhack2026  (2026-11-13)

## Corpus Check
- 111 files · ~52,611 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 5 file(s) not represented in the graph (top: (none) 3, .example 1, .lock 1)

## Summary
- 1064 nodes · 2619 edges · 59 communities (44 shown, 15 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 228 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `eba3061b`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- httpx
- test_audit.py
- 6.4 Gateway (`gateway/`) [M] P0 unless marked
- test_bench.py
- DiagnosisService
- test_bench_recovery.py
- AGENTS.md
- CLAUDE.md
- 10. Build plan
- Anirudh [A]: tasks
- json
- kubectl
- Implementation Plan: the on-call agent that has to earn its autonomy
- brain/main.py
- Anirudh [A]: architecture of my part
- Anirudh [A]: state
- test_observer.py
- On-call agent: Twaha components
- Observer
- HttpTrialServices
- .observe
- 3. Environment setup
- 8. Testing
- test_bench_export.py
- 0. Scope and principles
- 11. Demo
- 1. System overview
- 4. Configuration files
- 5. Data model
- 9. Benchmark (`bench/`) [T] P1
- models.py
- record
- 6.3 Brain (`brain/`) [M] P0 unless marked
- oncall-agent
- build_from_env
- test_verifier.py
- journal.py
- test_rehearsal_credits_action_receipt_with_false_diagnosis
- det
- connect
- security_check.sh
- make_kubeconfigs.sh
- install_shop.sh
- match
- setup_cluster.sh
- test_kube_watch.py
- Tracker
- create_app
- test_chaos.py
- TrialServices
- 6.2 Observer (`observer/`) [M] P0
- charge.js
- detector.py
- test_resume_counts_recorded_attempts_and_does_not_repeat_fault
- build_bad_payment.sh
- smoke.sh

## God Nodes (most connected - your core abstractions)
1. `connect()` - 34 edges
2. `DiagnosisService` - 33 edges
3. `ActionRequest` - 27 edges
4. `Gateway` - 26 edges
5. `GatewayDecision` - 25 edges
6. `HttpTrialServices` - 23 edges
7. `ReceiptStore` - 23 edges
8. `Incident` - 23 edges
9. `NotifierState` - 22 edges
10. `redact_value()` - 21 edges

## Surprising Connections (you probably didn't know these)
- `Phase 2: the other failures and the checks` --references--> `DiagnosisService`  [INFERRED]
  team/muaz/TASK.md → brain/llm.py
- `3.1 Prerequisites [A] P0` --references--> `kubectl()`  [INFERRED]
  IMPLEMENTATION.md → chaos/faults.py
- `9.2 Manual baseline (`manual_baseline.md`)` --references--> `kubectl()`  [INFERRED]
  IMPLEMENTATION.md → chaos/faults.py
- `Hard rules my code must keep` --references--> `kubectl()`  [INFERRED]
  team/anirudh/ARCHITECTURE.md → chaos/faults.py
- `Notes for my next session` --references--> `kubectl()`  [INFERRED]
  team/anirudh/STATE.md → chaos/faults.py

## Import Cycles
- None detected.

## Communities (59 total, 15 thin omitted)

### Community 0 - "httpx"
Cohesion: 0.06
Nodes (23): read_events(), Notifier, NotificationConsumer, ApprovalButton, ApprovalController, ApprovalView, DiscordNotifier, health() (+15 more)

### Community 1 - "test_audit.py"
Cohesion: 0.05
Nodes (57): quarantine(), redact(), redact_value(), AuditLog, canonical(), EventBus, verify(), active_bus() (+49 more)

### Community 2 - "6.4 Gateway (`gateway/`) [M] P0 unless marked"
Cohesion: 0.17
Nodes (12): 6.4.10 Watchdog (`watchdog.py`) P1, 6.4.11 One retry (P2), 6.4.1 MCP server (`mcp_server.py`), 6.4.2 The checklist (`checklist.py`), 6.4.3 Dry run and snapshot (`dryrun.py`), 6.4.4 Blast radius and net benefit (`blast.py`) P1, 6.4.5 Freshness (`freshness.py`), 6.4.6 Trust gate (`trust.py`) P1 (+4 more)

### Community 3 - "test_bench.py"
Cohesion: 0.20
Nodes (10): Harness, measure(), TrialResult, FakeServices, test_disabled_harness_never_resets_or_injects(), test_failed_trial_persisted_and_next_trial_runs(), test_manual_comparison_preserves_missing_measurements(), test_matching_pattern_wrong_culprit_is_not_correct() (+2 more)

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

### Community 9 - "Anirudh [A]: tasks"
Cohesion: 0.29
Nodes (6): Anirudh [A]: tasks, Never cut, Phase 1: the spine, Phase 2: the other failures, Phase 4: more UI, Phase 5: freeze

### Community 10 - "json"
Cohesion: 0.08
Nodes (33): _flatten(), _h(), namespace_hash(), outside_allowed(), previous_template(), rollback_patch(), spec_diff(), spec_hashes() (+25 more)

### Community 11 - "kubectl"
Cohesion: 0.16
Nodes (11): kubectl(), KubectlError, 6.1 Chaos panel (`chaos/`) [A] P0, 6.6 Notifier (`notifier/`) [T] P1, 6.7.1 Incident card, 6.7.2 Audit log (`data/audit.jsonl`), 6.7 Report (`gateway/receipts.py`, `gateway/audit.py`) [T] P0, 6.8 UI (`ui/`, Next.js) [A] P1 (+3 more)

### Community 12 - "Implementation Plan: the on-call agent that has to earn its autonomy"
Cohesion: 0.29
Nodes (6): 12. Risks and fallbacks, 13. Submission checklist, 14. Command cheat sheet, 2. Repository layout, 7. End-to-end flows (acceptance scenarios), Implementation Plan: the on-call agent that has to earn its autonomy

### Community 13 - "brain/main.py"
Cohesion: 0.05
Nodes (35): deepest_unhealthy(), depth(), fetch_error_traces(), find_culprit(), from_traces(), is_error(), DependencyGraph, downstream() (+27 more)

### Community 14 - "Anirudh [A]: architecture of my part"
Cohesion: 0.29
Nodes (6): Anirudh [A]: architecture of my part, Flow through my parts, Hard rules my code must keep, What I need from others, What I own, What I provide to others

### Community 15 - "Anirudh [A]: state"
Cohesion: 0.29
Nodes (6): Anirudh [A]: state, Blocked / waiting on, Done (with proof), In progress, Next, Notes for my next session

### Community 16 - "test_observer.py"
Cohesion: 0.20
Nodes (13): require_env(), Backend, make(), prom_result(), test_brain_down_does_not_stop_detection(), handler(), test_endpoints(), test_nan_rows_are_dropped() (+5 more)

### Community 17 - "On-call agent: Twaha components"
Cohesion: 0.18
Nodes (8): check(), usage(), Benchmarks and adversarial checks, Discord notifier, Inference, On-call agent: Twaha components, Project graph, Setup and checks

### Community 18 - "Observer"
Cohesion: 0.17
Nodes (5): load(), medians(), store(), Detector, Observer

### Community 19 - "HttpTrialServices"
Cohesion: 0.18
Nodes (5): HttpTrialServices, main(), test_health_wait_requires_current_metrics_and_retries_startup(), test_stale_metrics_restart_the_entire_stability_window(), test_rehearsal_disabled_before_any_network_call()

### Community 21 - "3. Environment setup"
Cohesion: 0.33
Nodes (6): 3.1 Prerequisites [A] P0, 3.2 Cluster [A] P0, 3.3 The shop [A] P0, 3.4 The buggy payment image [A] P0, 3.5 Kubeconfigs for the three identities [M] P0, 3. Environment setup

### Community 22 - "8. Testing"
Cohesion: 0.40
Nodes (5): 8.1 Unit tests [M][T] P0, 8.2 Property-based tests (`test_invariants.py`, Hypothesis) [M] P1, 8.3 Red-team suite (`tests/redteam/`) [T] P1, 8.4 Smoke test (`scripts/smoke.sh`) [A] P0, 8. Testing

### Community 23 - "test_bench_export.py"
Cohesion: 0.14
Nodes (17): display(), export_report(), markdown(), timing_svg(), main(), summarize(), compare(), load_rows() (+9 more)

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
Cohesion: 0.06
Nodes (51): build_bundle(), change_evidence(), collect_k8s(), k8s_evidence(), log_evidence(), memory_ratio(), metric_evidence(), _span_error_text() (+43 more)

### Community 32 - "record"
Cohesion: 0.28
Nodes (7): read_all(), record(), bad_deploy(), do_reset(), read_truth(), test_read_all_missing_file_is_empty(), test_record_appends_lines_with_ts_type_target()

### Community 34 - "6.3 Brain (`brain/`) [M] P0 unless marked"
Cohesion: 0.22
Nodes (9): 6.3.1 Dependency graph (`graph.py`), 6.3.2 Culprit (`culprit.py`), 6.3.3 Major-incident analysis (`major.py`) P1, 6.3.4 Evidence bundle (`bundle.py`), 6.3.5 Redaction and quarantine (`redact.py`), 6.3.6 Rules (`rules.py`), 6.3.7 Claude call (`llm.py`), 6.3.8 Orchestration (`main.py`) (+1 more)

### Community 37 - "build_from_env"
Cohesion: 0.25
Nodes (4): build_from_env(), create_app(), get_journal(), lifespan()

### Community 38 - "test_verifier.py"
Cohesion: 0.12
Nodes (14): Manual baseline, harm_check(), ledger_effect(), service_score(), Verification, HarmCheckTest, health(), service() (+6 more)

### Community 39 - "journal.py"
Cohesion: 0.10
Nodes (23): check(), author(), _configmap_changes(), _containers(), current(), _deployment_changes(), entry(), insert() (+15 more)

### Community 40 - "test_rehearsal_credits_action_receipt_with_false_diagnosis"
Cohesion: 0.25
Nodes (5): test_rehearsal_credits_action_receipt_with_false_diagnosis(), test_rehearsal_hooks_only_when_enabled(), handle(), test_rehearsal_refusal_stops_credit(), test_rehearsal_without_receipt_never_submits_credit()

### Community 42 - "connect"
Cohesion: 0.05
Nodes (34): main(), summarize_ledger(), approvers_from_env(), create(), get(), set_state(), build_from_env(), create_app() (+26 more)

### Community 46 - "match"
Cohesion: 0.29
Nodes (7): _action(), latest_change_before_onset(), match(), to_bytes(), change(), incident(), RulesTest

### Community 48 - "test_kube_watch.py"
Cohesion: 0.30
Nodes (10): bad_pods(), pod_bad(), service_of(), _ts(), deployment(), iso(), pod(), test_bad_pod_rules() (+2 more)

### Community 49 - "Tracker"
Cohesion: 0.20
Nodes (7): run_watch(), Tracker, FakeResp, test_run_watch_relists_after_error(), list_fn(), test_tracker_journals_changes_including_after_relist(), test_tracker_pods_feed_bad_pods()

### Community 50 - "create_app"
Cohesion: 0.23
Nodes (7): create_app(), lifespan(), ensure_snapshot(), read_cluster(), reset(), _state(), test_http_kubectl_failure_is_502_and_not_recorded()

### Community 51 - "test_chaos.py"
Cohesion: 0.22
Nodes (12): bad_deploy(), diff_ops(), deployment(), FakeKubectl, test_bad_deploy_patches_payment_image_as_chaos_panel(), test_diff_ops_empty_when_healthy(), test_diff_ops_refuses_when_container_is_gone(), test_diff_ops_restores_replicas_image_and_drops_added_env() (+4 more)

### Community 53 - "6.2 Observer (`observer/`) [M] P0"
Cohesion: 0.33
Nodes (6): 6.2.1 Baselines (`baselines.py`), 6.2.2 Detector (`detector.py`), 6.2.3 Kubernetes watch (`kube_watch.py`), 6.2.4 Change journal (`journal.py`), 6.2.5 Flags (`flags.py`), 6.2 Observer (`observer/`) [M] P0

### Community 54 - "charge.js"
Cohesion: 0.10
Nodes (14): { ATTR_ERROR_TYPE }, cardValidator, charge(), { context, propagation, trace, metrics, SpanStatusCode }, { FlagdProvider }, flagProvider, logger, LOYALTY_LEVEL (+6 more)

## Knowledge Gaps
- **1 isolated node(s):** `oncall-agent`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 314 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **15 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `kubectl()` connect `kubectl` to `Anirudh [A]: architecture of my part`, `Anirudh [A]: state`, `create_app`, `test_chaos.py`, `3. Environment setup`, `9. Benchmark (`bench/`) [T] P1`, `models.py`?**
  _High betweenness centrality (0.088) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `DiagnosisService` (e.g. with `InferenceProvider` and `InferenceRequest`) actually correct?**
  _`DiagnosisService` has 12 INFERRED edges - model-reasoned connections that need verification._
- **What connects `oncall-agent` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `httpx` be split into smaller, more focused modules?**
  _Cohesion score 0.05693664795509222 - nodes in this community are weakly interconnected._
- **Why does `ActionRequest` connect `models.py` to `httpx`, `DiagnosisService`, `json`, `connect`, `brain/main.py`, `8. Testing`?**
  _High betweenness centrality (0.075) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `ActionRequest` (e.g. with `DiagnosisResult` and `DiagnosisService`) actually correct?**
  _`ActionRequest` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_audit.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05106382978723404 - nodes in this community are weakly interconnected._