# Graph Report - devhack2026  (2026-11-13)

## Corpus Check
- 102 files · ~46,188 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 5 file(s) not represented in the graph (top: (none) 3, .example 1, .lock 1)

## Summary
- 940 nodes · 2216 edges · 62 communities (48 shown, 14 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 199 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `27d39a70`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- httpx
- test_audit.py
- 6.4 Gateway (`gateway/`) [M] P0 unless marked
- HttpTrialServices
- llm.py
- DiagnosisService
- AGENTS.md
- CLAUDE.md
- 10. Build plan
- Anirudh [A]: tasks
- Muaz [M]: tasks
- Twaha [T]: tasks
- Implementation Plan: the on-call agent that has to earn its autonomy
- test_brain.py
- kubectl
- Anirudh [A]: state
- test_observer.py
- pytest
- Observer
- Harness
- Twaha [T]: state
- 3. Environment setup
- 8. Testing
- argparse
- 0. Scope and principles
- 11. Demo
- 1. System overview
- 4. Configuration files
- 5. Data model
- 9. Benchmark (`bench/`) [T] P1
- models.py
- test_chaos.py
- Incident
- oncall-agent
- detector.py
- test_verifier.py
- journal.py
- find_culprit
- det
- brain/main.py
- security_check.sh
- make_kubeconfigs.sh
- install_shop.sh
- match
- setup_cluster.sh
- observer/main.py
- Tracker
- FakeServices
- create_app
- json
- build_from_env
- charge.js
- redact_value
- TrialServices
- record
- test_resume_counts_recorded_attempts_and_does_not_repeat_fault
- bundle.py
- build_bad_payment.sh
- smoke.sh

## God Nodes (most connected - your core abstractions)
1. `DiagnosisService` - 30 edges
2. `connect()` - 30 edges
3. `NotifierState` - 22 edges
4. `HttpTrialServices` - 21 edges
5. `redact_value()` - 21 edges
6. `ActionRequest` - 21 edges
7. `Incident` - 20 edges
8. `Card` - 18 edges
9. `InferenceResponse` - 17 edges
10. `ApprovalController` - 17 edges

## Surprising Connections (you probably didn't know these)
- `Done (with proof)` --references--> `InferenceProvider`  [INFERRED]
  team/twaha/STATE.md → brain/providers/base.py
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

## Communities (62 total, 14 thin omitted)

### Community 0 - "httpx"
Cohesion: 0.06
Nodes (20): read_events(), Notifier, NotificationConsumer, ApprovalButton, ApprovalController, ApprovalView, DiscordNotifier, lifespan() (+12 more)

### Community 1 - "test_audit.py"
Cohesion: 0.07
Nodes (42): AuditLog, canonical(), EventBus, verify(), active_bus(), create_events_router(), events(), stream() (+34 more)

### Community 2 - "6.4 Gateway (`gateway/`) [M] P0 unless marked"
Cohesion: 0.05
Nodes (40): 6.1 Chaos panel (`chaos/`) [A] P0, 6.2.1 Baselines (`baselines.py`), 6.2.2 Detector (`detector.py`), 6.2.3 Kubernetes watch (`kube_watch.py`), 6.2.4 Change journal (`journal.py`), 6.2.5 Flags (`flags.py`), 6.2 Observer (`observer/`) [M] P0, 6.3.1 Dependency graph (`graph.py`) (+32 more)

### Community 3 - "HttpTrialServices"
Cohesion: 0.13
Nodes (13): HttpTrialServices, ObservationError, stream(), test_reconnect_resumes_cursor_and_ignores_duplicate_events(), handle(), test_replayed_approval_does_not_repeat_post(), handle(), test_timeout_keeps_detection_and_diagnosis_measurements() (+5 more)

### Community 4 - "llm.py"
Cohesion: 0.12
Nodes (10): InferenceProvider, InferenceRequest, InferenceResponse, ProviderError, OpenCodeGoAdapter, test_adversarial_proposal(), generate(), test_adapter_headers_and_wire_shape() (+2 more)

### Community 5 - "DiagnosisService"
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

### Community 9 - "Anirudh [A]: tasks"
Cohesion: 0.22
Nodes (8): Anirudh [A]: tasks, Never cut, Phase 0: foundations, Phase 1: the spine, Phase 2: the other failures, Phase 3: UI, Phase 4: more UI, Phase 5: freeze

### Community 10 - "Muaz [M]: tasks"
Cohesion: 0.22
Nodes (8): Muaz [M]: tasks, Never cut, Phase 0: foundations, Phase 1: the spine, one failure end to end, Phase 2: the other failures and the checks, Phase 3: trust, humans, proof, Phase 4: wide outages and measurement, Phase 6: stretch (only if Phase 4 exit is met early)

### Community 11 - "Twaha [T]: tasks"
Cohesion: 0.20
Nodes (9): Integration proof (2026-11-13), Never cut, Phase 0: foundations, Phase 1: the spine, Phase 2: checks, Phase 3: humans and proof, Phase 5: freeze, Twaha [T]: tasks (+1 more)

### Community 12 - "Implementation Plan: the on-call agent that has to earn its autonomy"
Cohesion: 0.29
Nodes (6): 12. Risks and fallbacks, 13. Submission checklist, 14. Command cheat sheet, 2. Repository layout, 7. End-to-end flows (acceptance scenarios), Implementation Plan: the on-call agent that has to earn its autonomy

### Community 13 - "test_brain.py"
Cohesion: 0.09
Nodes (18): DependencyGraph, downstream(), Brain, create_app(), _finished(), incidents(), lifespan(), diagnosis_json() (+10 more)

### Community 14 - "kubectl"
Cohesion: 0.16
Nodes (9): kubectl(), KubectlError, Anirudh [A]: architecture of my part, Flow through my parts, Hard rules my code must keep, What I need from others, What I own, What I provide to others (+1 more)

### Community 15 - "Anirudh [A]: state"
Cohesion: 0.29
Nodes (6): Anirudh [A]: state, Blocked / waiting on, Done (with proof), In progress, Next, Notes for my next session

### Community 16 - "test_observer.py"
Cohesion: 0.18
Nodes (13): require_env(), Backend, make(), prom_result(), test_brain_down_does_not_stop_detection(), handler(), test_endpoints(), test_nan_rows_are_dropped() (+5 more)

### Community 17 - "pytest"
Cohesion: 0.19
Nodes (13): ActionRequest, Event, Prediction, Open questions, test_forbidden_tools(), test_poisoned_log(), test_action_rejects_invented_pattern(), test_evidence_rejects_nonfinite_timestamp() (+5 more)

### Community 18 - "Observer"
Cohesion: 0.17
Nodes (5): load(), medians(), store(), Detector, Observer

### Community 19 - "Harness"
Cohesion: 0.25
Nodes (7): Harness, main(), measure(), TrialResult, test_failed_attempts_count_toward_resume_target(), test_resume_corrupt_file_fails_before_reset(), test_sync_provider_usage_normalizes_without_double_counting()

### Community 20 - "Twaha [T]: state"
Cohesion: 0.29
Nodes (6): Blocked / waiting on, Done (with proof), In progress, Next, Notes for my next session, Twaha [T]: state

### Community 21 - "3. Environment setup"
Cohesion: 0.33
Nodes (6): 3.1 Prerequisites [A] P0, 3.2 Cluster [A] P0, 3.3 The shop [A] P0, 3.4 The buggy payment image [A] P0, 3.5 Kubeconfigs for the three identities [M] P0, 3. Environment setup

### Community 22 - "8. Testing"
Cohesion: 0.40
Nodes (5): 8.1 Unit tests [M][T] P0, 8.2 Property-based tests (`test_invariants.py`, Hypothesis) [M] P1, 8.3 Red-team suite (`tests/redteam/`) [T] P1, 8.4 Smoke test (`scripts/smoke.sh`) [A] P0, 8. Testing

### Community 23 - "argparse"
Cohesion: 0.33
Nodes (3): main(), summarize(), main()

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
Cohesion: 0.18
Nodes (8): ApprovalDecidedPayload, ApprovalRequestedPayload, CardPayload, ChecklistPayload, DiagnosisReadyPayload, InferencePayload, Payload, QuarantinePayload

### Community 32 - "test_chaos.py"
Cohesion: 0.25
Nodes (12): bad_deploy(), bad_deploy(), diff_ops(), deployment(), FakeKubectl, test_bad_deploy_patches_payment_image_as_chaos_panel(), test_diff_ops_empty_when_healthy(), test_diff_ops_refuses_when_container_is_gone() (+4 more)

### Community 34 - "Incident"
Cohesion: 0.22
Nodes (11): Cause, EvidenceBundle, Incident, Model, Contracts (agreed interfaces between owners), Log (append-only, newest at bottom), Rules for agents, Shared context (all agents read and write this) (+3 more)

### Community 38 - "test_verifier.py"
Cohesion: 0.10
Nodes (15): Manual baseline, spec_hashes(), harm_check(), ledger_effect(), service_score(), Verification, HarmCheckTest, health() (+7 more)

### Community 39 - "journal.py"
Cohesion: 0.10
Nodes (23): check(), author(), _configmap_changes(), _containers(), current(), _deployment_changes(), entry(), insert() (+15 more)

### Community 40 - "find_culprit"
Cohesion: 0.19
Nodes (8): deepest_unhealthy(), depth(), fetch_error_traces(), find_culprit(), from_traces(), is_error(), CulpritTest, trace()

### Community 42 - "brain/main.py"
Cohesion: 0.11
Nodes (18): main(), summarize_ledger(), build_from_env(), require_env(), check(), counts(), eligible(), lower_bound() (+10 more)

### Community 46 - "match"
Cohesion: 0.29
Nodes (7): _action(), latest_change_before_onset(), match(), to_bytes(), change(), incident(), RulesTest

### Community 48 - "observer/main.py"
Cohesion: 0.23
Nodes (10): bad_pods(), pod_bad(), service_of(), _ts(), deployment(), iso(), pod(), test_bad_pod_rules() (+2 more)

### Community 49 - "Tracker"
Cohesion: 0.20
Nodes (7): run_watch(), Tracker, FakeResp, test_run_watch_relists_after_error(), list_fn(), test_tracker_journals_changes_including_after_relist(), test_tracker_pods_feed_bad_pods()

### Community 50 - "FakeServices"
Cohesion: 0.22
Nodes (4): FakeServices, test_disabled_harness_never_resets_or_injects(), test_matching_pattern_wrong_culprit_is_not_correct(), observe()

### Community 51 - "create_app"
Cohesion: 0.20
Nodes (8): create_app(), lifespan(), ensure_snapshot(), read_cluster(), reset(), _state(), test_http_kubectl_failure_is_502_and_not_recorded(), test_snapshot_refuses_when_target_missing()

### Community 52 - "json"
Cohesion: 0.26
Nodes (9): compare(), main(), summarize(), test_failed_trial_persisted_and_next_trial_runs(), test_manual_comparison_preserves_missing_measurements(), test_rehearsal_credits_action_receipt_with_false_diagnosis(), test_rehearsal_hooks_only_when_enabled(), handle() (+1 more)

### Community 53 - "build_from_env"
Cohesion: 0.18
Nodes (5): build_from_env(), create_app(), get_journal(), lifespan(), load()

### Community 54 - "charge.js"
Cohesion: 0.10
Nodes (14): { ATTR_ERROR_TYPE }, cardValidator, charge(), { context, propagation, trace, metrics, SpanStatusCode }, { FlagdProvider }, flagProvider, logger, LOYALTY_LEVEL (+6 more)

### Community 55 - "redact_value"
Cohesion: 0.10
Nodes (21): quarantine(), redact(), redact_value(), clean(), Flow through my code, Hard rules my code must keep, Muaz [M]: architecture of my part, What I need from others (+13 more)

### Community 57 - "record"
Cohesion: 0.32
Nodes (6): read_all(), record(), do_reset(), read_truth(), test_read_all_missing_file_is_empty(), test_record_appends_lines_with_ts_type_target()

### Community 59 - "bundle.py"
Cohesion: 0.23
Nodes (18): build_bundle(), change_evidence(), collect_k8s(), k8s_evidence(), log_evidence(), memory_ratio(), metric_evidence(), _span_error_text() (+10 more)

## Knowledge Gaps
- **1 isolated node(s):** `oncall-agent`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 295 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `kubectl()` connect `kubectl` to `test_chaos.py`, `6.4 Gateway (`gateway/`) [M] P0 unless marked`, `Anirudh [A]: tasks`, `Anirudh [A]: state`, `pytest`, `create_app`, `3. Environment setup`, `9. Benchmark (`bench/`) [T] P1`?**
  _High betweenness centrality (0.139) - this node is a cross-community bridge._
- **Are the 9 inferred relationships involving `DiagnosisService` (e.g. with `InferenceProvider` and `InferenceRequest`) actually correct?**
  _`DiagnosisService` has 9 INFERRED edges - model-reasoned connections that need verification._
- **What connects `oncall-agent` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `httpx` be split into smaller, more focused modules?**
  _Cohesion score 0.06190476190476191 - nodes in this community are weakly interconnected._
- **Why does `ActionRequest` connect `pytest` to `httpx`, `Incident`, `llm.py`, `DiagnosisService`, `brain/main.py`, `test_brain.py`, `8. Testing`, `models.py`?**
  _High betweenness centrality (0.070) - this node is a cross-community bridge._
- **Should `test_audit.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06921529175050302 - nodes in this community are weakly interconnected._
- **Why does `Implementation Plan: the on-call agent that has to earn its autonomy` connect `Implementation Plan: the on-call agent that has to earn its autonomy` to `6.4 Gateway (`gateway/`) [M] P0 unless marked`, `10. Build plan`, `3. Environment setup`, `8. Testing`, `0. Scope and principles`, `11. Demo`, `1. System overview`, `4. Configuration files`, `5. Data model`, `9. Benchmark (`bench/`) [T] P1`?**
  _High betweenness centrality (0.069) - this node is a cross-community bridge._