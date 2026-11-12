# Graph Report - devhack2026  (2026-11-13)

## Corpus Check
- 93 files · ~43,512 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 4 file(s) not represented in the graph (top: (none) 2, .example 1, .lock 1)

## Summary
- 866 nodes · 2037 edges · 44 communities (34 shown, 10 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 182 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `3647832a`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- NotifierState
- test_audit.py
- 6.4 Gateway (`gateway/`) [M] P0 unless marked
- HttpTrialServices
- DiagnosisService
- models.py
- AGENTS.md
- CLAUDE.md
- 10. Build plan
- Anirudh [A]: tasks
- Muaz [M]: tasks
- Twaha [T]: tasks
- Implementation Plan: the on-call agent that has to earn its autonomy
- json
- Anirudh [A]: architecture of my part
- Anirudh [A]: state
- brain/main.py
- test_resume_counts_recorded_attempts_and_does_not_repeat_fault
- Observer
- harness.py
- 3. Environment setup
- 8. Testing
- 0. Scope and principles
- 11. Demo
- 1. System overview
- 4. Configuration files
- 5. Data model
- 9. Benchmark (`bench/`) [T] P1
- oncall-agent
- Done (with proof)
- journal.py
- find_culprit
- trust_report.py
- security_check.sh
- make_kubeconfigs.sh
- install_shop.sh
- test_brain.py
- setup_cluster.sh
- test_timeout_keeps_detection_and_diagnosis_measurements
- test_bench.py
- TrialServices

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
- `Notes for my next session` --references--> `ReceiptStore`  [INFERRED]
  team/twaha/STATE.md → gateway/receipts.py
- `5.3 Event types (SSE and audit)` --references--> `harm_check()`  [INFERRED]
  IMPLEMENTATION.md → gateway/verifier.py
- `8.2 Property-based tests (`test_invariants.py`, Hypothesis) [M] P1` --references--> `ActionRequest`  [INFERRED]
  IMPLEMENTATION.md → schemas/models.py
- `Done (with proof)` --references--> `DiagnosisService`  [INFERRED]
  team/muaz/STATE.md → brain/llm.py
- `Log (append-only, newest at bottom)` --references--> `DiagnosisService`  [INFERRED]
  team/SHARED_CONTEXT.md → brain/llm.py

## Import Cycles
- None detected.

## Communities (44 total, 10 thin omitted)

### Community 0 - "NotifierState"
Cohesion: 0.06
Nodes (22): Notifier, NotificationConsumer, ApprovalButton, ApprovalController, ApprovalView, DiscordNotifier, health(), lifespan() (+14 more)

### Community 1 - "test_audit.py"
Cohesion: 0.07
Nodes (43): AuditLog, canonical(), EventBus, verify(), active_bus(), create_events_router(), events(), stream() (+35 more)

### Community 2 - "6.4 Gateway (`gateway/`) [M] P0 unless marked"
Cohesion: 0.05
Nodes (40): 6.1 Chaos panel (`chaos/`) [A] P0, 6.2.1 Baselines (`baselines.py`), 6.2.2 Detector (`detector.py`), 6.2.3 Kubernetes watch (`kube_watch.py`), 6.2.4 Change journal (`journal.py`), 6.2.5 Flags (`flags.py`), 6.2 Observer (`observer/`) [M] P0, 6.3.1 Dependency graph (`graph.py`) (+32 more)

### Community 3 - "HttpTrialServices"
Cohesion: 0.15
Nodes (9): HttpTrialServices, ObservationError, test_uncertain_approval_post_is_not_retried(), test_rehearsal_credits_action_receipt_with_false_diagnosis(), test_rehearsal_disabled_before_any_network_call(), test_rehearsal_hooks_only_when_enabled(), handle(), test_rehearsal_refusal_stops_credit() (+1 more)

### Community 4 - "DiagnosisService"
Cohesion: 0.09
Nodes (28): DiagnosisService, InferenceProvider, InferenceRequest, InferenceResponse, ProviderError, OpenCodeGoAdapter, Blocked / waiting on, Done (with proof) (+20 more)

### Community 5 - "models.py"
Cohesion: 0.06
Nodes (51): build_bundle(), change_evidence(), collect_k8s(), k8s_evidence(), log_evidence(), memory_ratio(), metric_evidence(), _span_error_text() (+43 more)

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

### Community 13 - "json"
Cohesion: 0.10
Nodes (21): quarantine(), redact(), redact_value(), clean(), Flow through my code, Hard rules my code must keep, Muaz [M]: architecture of my part, What I need from others (+13 more)

### Community 14 - "Anirudh [A]: architecture of my part"
Cohesion: 0.29
Nodes (6): Anirudh [A]: architecture of my part, Flow through my parts, Hard rules my code must keep, What I need from others, What I own, What I provide to others

### Community 15 - "Anirudh [A]: state"
Cohesion: 0.29
Nodes (6): Anirudh [A]: state, Blocked / waiting on, Done (with proof), In progress, Next, Notes for my next session

### Community 16 - "brain/main.py"
Cohesion: 0.05
Nodes (40): build_from_env(), require_env(), read_events(), medians(), bad_pods(), pod_bad(), run_watch(), service_of() (+32 more)

### Community 18 - "Observer"
Cohesion: 0.11
Nodes (8): load(), store(), Detector, fetch_readings(), prom_query(), Observer, det(), DetectorTest

### Community 19 - "harness.py"
Cohesion: 0.28
Nodes (7): Harness, main(), measure(), TrialResult, test_failed_attempts_count_toward_resume_target(), test_resume_corrupt_file_fails_before_reset(), test_sync_provider_usage_normalizes_without_double_counting()

### Community 21 - "3. Environment setup"
Cohesion: 0.33
Nodes (6): 3.1 Prerequisites [A] P0, 3.2 Cluster [A] P0, 3.3 The shop [A] P0, 3.4 The buggy payment image [A] P0, 3.5 Kubeconfigs for the three identities [M] P0, 3. Environment setup

### Community 22 - "8. Testing"
Cohesion: 0.40
Nodes (5): 8.1 Unit tests [M][T] P0, 8.2 Property-based tests (`test_invariants.py`, Hypothesis) [M] P1, 8.3 Red-team suite (`tests/redteam/`) [T] P1, 8.4 Smoke test (`scripts/smoke.sh`) [A] P0, 8. Testing

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

### Community 38 - "Done (with proof)"
Cohesion: 0.08
Nodes (21): Manual baseline, spec_hashes(), harm_check(), ledger_effect(), service_score(), Verification, Blocked / waiting on, Done (with proof) (+13 more)

### Community 39 - "journal.py"
Cohesion: 0.13
Nodes (18): check(), author(), _configmap_changes(), _containers(), current(), _deployment_changes(), entry(), insert() (+10 more)

### Community 40 - "find_culprit"
Cohesion: 0.19
Nodes (8): deepest_unhealthy(), depth(), fetch_error_traces(), find_culprit(), from_traces(), is_error(), CulpritTest, trace()

### Community 42 - "trust_report.py"
Cohesion: 0.11
Nodes (15): main(), summarize(), main(), summarize_ledger(), check(), counts(), eligible(), lower_bound() (+7 more)

### Community 46 - "test_brain.py"
Cohesion: 0.07
Nodes (24): DependencyGraph, Brain, create_app(), _finished(), incidents(), lifespan(), _action(), latest_change_before_onset() (+16 more)

### Community 51 - "test_timeout_keeps_detection_and_diagnosis_measurements"
Cohesion: 0.20
Nodes (8): stream(), test_reconnect_resumes_cursor_and_ignores_duplicate_events(), handle(), test_replayed_approval_does_not_repeat_post(), handle(), test_timeout_keeps_detection_and_diagnosis_measurements(), handle(), handle()

### Community 52 - "test_bench.py"
Cohesion: 0.19
Nodes (9): compare(), main(), summarize(), FakeServices, test_disabled_harness_never_resets_or_injects(), test_failed_trial_persisted_and_next_trial_runs(), test_manual_comparison_preserves_missing_measurements(), test_matching_pattern_wrong_culprit_is_not_correct() (+1 more)

## Knowledge Gaps
- **1 isolated node(s):** `oncall-agent`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 279 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Implementation Plan: the on-call agent that has to earn its autonomy` connect `Implementation Plan: the on-call agent that has to earn its autonomy` to `6.4 Gateway (`gateway/`) [M] P0 unless marked`, `10. Build plan`, `3. Environment setup`, `8. Testing`, `0. Scope and principles`, `11. Demo`, `1. System overview`, `4. Configuration files`, `5. Data model`, `9. Benchmark (`bench/`) [T] P1`?**
  _High betweenness centrality (0.127) - this node is a cross-community bridge._
- **Are the 9 inferred relationships involving `DiagnosisService` (e.g. with `InferenceProvider` and `InferenceRequest`) actually correct?**
  _`DiagnosisService` has 9 INFERRED edges - model-reasoned connections that need verification._
- **What connects `oncall-agent` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `NotifierState` be split into smaller, more focused modules?**
  _Cohesion score 0.06220095693779904 - nodes in this community are weakly interconnected._
- **Why does `ActionRequest` connect `models.py` to `NotifierState`, `test_audit.py`, `DiagnosisService`, `trust_report.py`, `test_brain.py`, `brain/main.py`, `8. Testing`?**
  _High betweenness centrality (0.127) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `NotifierState` (e.g. with `NotificationConsumer` and `ApprovalController`) actually correct?**
  _`NotifierState` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_audit.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06886338393187708 - nodes in this community are weakly interconnected._