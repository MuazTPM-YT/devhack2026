# Graph Report - devhack2026  (2026-11-13)

## Corpus Check
- 119 files · ~61,642 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 5 file(s) not represented in the graph (top: (none) 3, .example 1, .lock 1)

## Summary
- 1199 nodes · 3121 edges · 65 communities (52 shown, 13 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 265 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `2b4bd810`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- httpx
- test_audit.py
- 6.4 Gateway (`gateway/`) [M] P0 unless marked
- harness.py
- DiagnosisService
- llm.py
- AGENTS.md
- CLAUDE.md
- 10. Build plan
- test_brain.py
- checklist.py
- json
- Implementation Plan: the on-call agent that has to earn its autonomy
- bundle.py
- find_culprit
- models.py
- Observer
- test_observer.py
- InferenceResponse
- fetch_error_traces
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
- create_app
- oncall-agent
- build_from_env
- test_verify_loop.py
- journal.py
- create_app
- pytest
- connect
- security_check.sh
- make_kubeconfigs.sh
- install_shop.sh
- match
- setup_cluster.sh
- brain/main.py
- Tracker
- test_major.py
- test_chaos.py
- test_phase3.py
- Twaha [T]: tasks
- charge.js
- test_tools.py
- InferenceProvider
- det
- Anirudh [A]: architecture of my part
- test_kube_watch.py
- Anirudh [A]: tasks
- Anirudh [A]: state
- build_bad_payment.sh
- smoke.sh
- detector.py

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

## Communities (65 total, 13 thin omitted)

### Community 0 - "httpx"
Cohesion: 0.06
Nodes (23): read_events(), Notifier, NotificationConsumer, ApprovalButton, ApprovalController, ApprovalView, DiscordNotifier, health() (+15 more)

### Community 1 - "test_audit.py"
Cohesion: 0.05
Nodes (56): quarantine(), redact(), redact_value(), AuditLog, canonical(), EventBus, verify(), active_bus() (+48 more)

### Community 2 - "6.4 Gateway (`gateway/`) [M] P0 unless marked"
Cohesion: 0.06
Nodes (34): 6.1 Chaos panel (`chaos/`) [A] P0, 6.2.1 Baselines (`baselines.py`), 6.2.2 Detector (`detector.py`), 6.2.3 Kubernetes watch (`kube_watch.py`), 6.2.4 Change journal (`journal.py`), 6.2.5 Flags (`flags.py`), 6.2 Observer (`observer/`) [M] P0, 6.3.1 Dependency graph (`graph.py`) (+26 more)

### Community 3 - "harness.py"
Cohesion: 0.05
Nodes (33): Harness, HttpTrialServices, main(), measure(), ObservationError, TrialResult, TrialServices, FakeServices (+25 more)

### Community 4 - "DiagnosisService"
Cohesion: 0.36
Nodes (12): DiagnosisService, diagnosis(), FakeProvider, test_cache_disk_failure_does_not_discard_diagnosis(), test_cache_is_exact_and_marked(), test_deadline_falls_back_to_rule(), test_fabricated_evidence_rejected(), test_invalid_json_retries_and_preserves_rule() (+4 more)

### Community 5 - "llm.py"
Cohesion: 0.26
Nodes (7): DiagnosisResult, Cause, Diagnosis, EvidenceBundle, Model, Prediction, Contracts (agreed interfaces between owners)

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
Cohesion: 0.06
Nodes (40): DependencyGraph, downstream(), upstream(), create_app(), _finished(), incidents(), lifespan(), blast_radius() (+32 more)

### Community 10 - "checklist.py"
Cohesion: 0.08
Nodes (30): forecast_text(), rv(), build_patch(), _flatten(), _h(), namespace_hash(), outside_allowed(), previous_template() (+22 more)

### Community 11 - "json"
Cohesion: 0.23
Nodes (15): bad_deploy(), broken_config(), datastore_down(), kubectl(), memory_leak(), read_flags(), read_live_flags(), write_flags() (+7 more)

### Community 12 - "Implementation Plan: the on-call agent that has to earn its autonomy"
Cohesion: 0.29
Nodes (6): 12. Risks and fallbacks, 13. Submission checklist, 14. Command cheat sheet, 2. Repository layout, 7. End-to-end flows (acceptance scenarios), Implementation Plan: the on-call agent that has to earn its autonomy

### Community 13 - "bundle.py"
Cohesion: 0.19
Nodes (21): build_bundle(), change_evidence(), collect_k8s(), k8s_evidence(), log_evidence(), memory_ratio(), metric_evidence(), _span_error_text() (+13 more)

### Community 14 - "find_culprit"
Cohesion: 0.22
Nodes (7): deepest_unhealthy(), depth(), find_culprit(), from_traces(), is_error(), CulpritTest, trace()

### Community 15 - "models.py"
Cohesion: 0.20
Nodes (8): ApprovalDecidedPayload, ApprovalRequestedPayload, CardPayload, ChecklistPayload, DiagnosisReadyPayload, InferencePayload, Payload, QuarantinePayload

### Community 16 - "Observer"
Cohesion: 0.17
Nodes (5): load(), medians(), store(), Detector, Observer

### Community 17 - "test_observer.py"
Cohesion: 0.18
Nodes (13): require_env(), Backend, make(), prom_result(), test_brain_down_does_not_stop_detection(), handler(), test_endpoints(), test_nan_rows_are_dropped() (+5 more)

### Community 18 - "InferenceResponse"
Cohesion: 0.16
Nodes (10): build_from_env(), require_env(), InferenceRequest, InferenceResponse, ProviderError, OpenCodeGoAdapter, test_adversarial_proposal(), generate() (+2 more)

### Community 20 - "FakeApps"
Cohesion: 0.16
Nodes (5): FakeApps, FakeCore, merge(), Observer, Resp

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
Cohesion: 0.06
Nodes (34): call_tool(), Brain, create(), get(), set_state(), Gateway, usage(), 6.5.1 `rbac-reader.yaml` (+26 more)

### Community 32 - "test_gateway.py"
Cohesion: 0.27
Nodes (16): Phase 3: trust, humans, proof, action(), test_approval_rules(), test_bad_deploy_asks_then_rolls_back_on_approval(), test_budget_and_in_flight(), test_conflict_on_execute_hands_off_and_admission_denial_escalates(), test_dry_run_outside_template_escalates(), test_http_app_routes() (+8 more)

### Community 34 - "create_app"
Cohesion: 0.16
Nodes (11): read_all(), record(), create_app(), do_reset(), endpoint(), inject(), lifespan(), read_truth() (+3 more)

### Community 37 - "build_from_env"
Cohesion: 0.25
Nodes (4): build_from_env(), create_app(), get_journal(), lifespan()

### Community 38 - "test_verify_loop.py"
Cohesion: 0.28
Nodes (12): test_restart_success_card_says_mitigated(), executed(), healthy(), ledger(), Script, sick(), test_early_abort_pauses_undoes_resumes(), test_human_change_during_verify_hands_off_without_undo() (+4 more)

### Community 39 - "journal.py"
Cohesion: 0.13
Nodes (16): check(), author(), _configmap_changes(), _containers(), current(), _deployment_changes(), entry(), insert() (+8 more)

### Community 40 - "create_app"
Cohesion: 0.13
Nodes (5): create_app(), build_mcp(), make(), test_brain_mcp_client_reaches_real_gateway(), test_rehearsal_route_needs_flag()

### Community 41 - "pytest"
Cohesion: 0.27
Nodes (8): Event, test_action_rejects_invented_pattern(), test_evidence_rejects_nonfinite_timestamp(), test_payload_contract_rejects_incomplete_approval(), test_payload_rejects_cross_incident_card(), test_prediction_deadline_is_bounded(), test_shared_pattern_values(), test_unknown_tool_and_event_rejected()

### Community 42 - "connect"
Cohesion: 0.05
Nodes (31): Manual baseline, main(), summarize(), main(), summarize_ledger(), check(), counts(), eligible() (+23 more)

### Community 46 - "match"
Cohesion: 0.22
Nodes (10): _action(), latest_change_before_onset(), match(), to_bytes(), bounds(), check(), major_check(), change() (+2 more)

### Community 48 - "brain/main.py"
Cohesion: 0.12
Nodes (8): approvers_from_env(), lifespan(), build_from_env(), lifespan(), Decide, RehearsalCredit, require_env(), load()

### Community 49 - "Tracker"
Cohesion: 0.20
Nodes (7): run_watch(), Tracker, FakeResp, test_run_watch_relists_after_error(), list_fn(), test_tracker_journals_changes_including_after_relist(), test_tracker_pods_feed_bad_pods()

### Community 50 - "test_major.py"
Cohesion: 0.32
Nodes (9): analyse(), is_major(), shared_change(), major_world(), test_is_major_by_count_and_spread(), test_major_one_restart_and_no_scale_up(), test_major_only_root_cause_and_always_asks(), test_major_revert_of_shared_change_may_run_auto() (+1 more)

### Community 51 - "test_chaos.py"
Cohesion: 0.15
Nodes (15): KubectlError, diff_ops(), deployment(), FakeKubectl, test_bad_deploy_patches_payment_image_as_chaos_panel(), test_broken_config_sets_wrong_payment_addr_keeps_other_env(), test_datastore_down_scales_valkey_cart_to_zero(), test_diff_ops_empty_when_healthy() (+7 more)

### Community 52 - "test_phase3.py"
Cohesion: 0.31
Nodes (8): executed_and_parked(), FakeGraph, single_replica(), test_costly_action_asks_at_net_benefit_then_runs_after_approval(), test_failed_watchdog_undo_keeps_blocking(), test_unknown_graph_with_capacity_cost_asks(), test_watchdog_leaves_ticking_verifier_alone(), test_watchdog_undoes_silent_verification()

### Community 53 - "Twaha [T]: tasks"
Cohesion: 0.22
Nodes (8): Evidence and next gate (2026-11-13), Never cut, Phase 1: the spine, Phase 2: checks, Phase 3: humans and proof, Phase 4: measurement, Phase 5: freeze, Twaha [T]: tasks

### Community 54 - "charge.js"
Cohesion: 0.10
Nodes (14): { ATTR_ERROR_TYPE }, cardValidator, charge(), { context, propagation, trace, metrics, SpanStatusCode }, { FlagdProvider }, flagProvider, logger, LOYALTY_LEVEL (+6 more)

### Community 55 - "test_tools.py"
Cohesion: 0.31
Nodes (9): container(), run_tool(), test_flag_tools_not_built_yet(), test_raise_limit_bounded_and_must_raise(), test_restart_sets_restarted_at_only(), test_revert_env_from_journal_inverse(), test_revert_without_env_entry_is_refused(), test_scale_uses_subresource_and_bounds() (+1 more)

### Community 56 - "InferenceProvider"
Cohesion: 0.15
Nodes (8): InferenceProvider, Blocked / waiting on, Done (with proof), In progress, Next, Notes for next session, Twaha [T]: state, Phase 0: foundations

### Community 58 - "Anirudh [A]: architecture of my part"
Cohesion: 0.29
Nodes (6): Anirudh [A]: architecture of my part, Flow through my parts, Hard rules my code must keep, What I need from others, What I own, What I provide to others

### Community 59 - "test_kube_watch.py"
Cohesion: 0.33
Nodes (10): bad_pods(), pod_bad(), service_of(), _ts(), deployment(), iso(), pod(), test_bad_pod_rules() (+2 more)

### Community 60 - "Anirudh [A]: tasks"
Cohesion: 0.22
Nodes (8): Anirudh [A]: tasks, Never cut, Phase 0: foundations, Phase 1: the spine, Phase 2: the other failures, Phase 3: UI, Phase 4: more UI, Phase 5: freeze

### Community 61 - "Anirudh [A]: state"
Cohesion: 0.25
Nodes (7): Anirudh [A]: state, Blocked / waiting on, Done (with proof), In progress, Next, Notes for my next session, test_reset_restores_flag_flipped_only_in_flagd_ui()

## Knowledge Gaps
- **1 isolated node(s):** `oncall-agent`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 331 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **13 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `kubectl()` connect `json` to `6.4 Gateway (`gateway/`) [M] P0 unless marked`, `test_chaos.py`, `Anirudh [A]: state`, `3. Environment setup`, `Anirudh [A]: architecture of my part`, `Anirudh [A]: tasks`, `9. Benchmark (`bench/`) [T] P1`, `ActionRequest`?**
  _High betweenness centrality (0.083) - this node is a cross-community bridge._
- **Are the 14 inferred relationships involving `ActionRequest` (e.g. with `call_tool()` and `DiagnosisResult`) actually correct?**
  _`ActionRequest` has 14 INFERRED edges - model-reasoned connections that need verification._
- **What connects `oncall-agent` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `httpx` be split into smaller, more focused modules?**
  _Cohesion score 0.05925925925925926 - nodes in this community are weakly interconnected._
- **Why does `Done (with proof)` connect `ActionRequest` to `test_audit.py`, `DiagnosisService`, `journal.py`, `test_brain.py`, `checklist.py`, `connect`, `pytest`, `Observer`, `fetch_error_traces`, `charge.js`?**
  _High betweenness centrality (0.060) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `World` (e.g. with `Gateway` and `ReceiptStore`) actually correct?**
  _`World` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_audit.py` be split into smaller, more focused modules?**
  _Cohesion score 0.052604698672114404 - nodes in this community are weakly interconnected._