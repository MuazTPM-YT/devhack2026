# Graph Report - devhack2026  (2026-11-13)

## Corpus Check
- 105 files · ~43,872 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 5 file(s) not represented in the graph (top: (none) 3, .example 1, .lock 1)

## Summary
- 893 nodes · 2045 edges · 54 communities (38 shown, 16 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 186 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `816de306`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- NotifierState
- test_audit.py
- 6.4 Gateway (`gateway/`) [M] P0 unless marked
- HttpTrialServices
- test_inference.py
- models.py
- AGENTS.md
- CLAUDE.md
- 10. Build plan
- Anirudh [A]: tasks
- Muaz [M]: tasks
- Twaha [T]: tasks
- Implementation Plan: the on-call agent that has to earn its autonomy
- Card
- Anirudh [A]: architecture of my part
- Anirudh [A]: state
- test_observer.py
- NotificationConsumer
- Observer
- ApprovalButton
- 3. Environment setup
- 8. Testing
- 0. Scope and principles
- 11. Demo
- 1. System overview
- 4. Configuration files
- 5. Data model
- 9. Benchmark (`bench/`) [T] P1
- connect
- oncall-agent
- detector.py
- test_verifier.py
- JournalTest
- find_culprit
- det
- trust_report.py
- security_check.sh
- make_kubeconfigs.sh
- install_shop.sh
- match
- setup_cluster.sh
- test_chaos.py
- Tracker
- test_chaos.py
- test_bench.py
- build_from_env
- charge.js
- httpx
- build_bad_payment.sh
- smoke.sh

## God Nodes (most connected - your core abstractions)
1. `DiagnosisService` - 26 edges
2. `connect()` - 26 edges
3. `NotifierState` - 22 edges
4. `FakeKubectl` - 21 edges
5. `HttpTrialServices` - 21 edges
6. `redact_value()` - 21 edges
7. `ActionRequest` - 19 edges
8. `Card` - 18 edges
9. `ensure_snapshot()` - 17 edges
10. `ApprovalController` - 17 edges

## Surprising Connections (you probably didn't know these)
- `8.2 Property-based tests (`test_invariants.py`, Hypothesis) [M] P1` --references--> `ActionRequest`  [INFERRED]
  IMPLEMENTATION.md → schemas/models.py
- `Notes for my next session` --references--> `ReceiptStore`  [INFERRED]
  team/twaha/STATE.md → gateway/receipts.py
- `5.3 Event types (SSE and audit)` --references--> `harm_check()`  [INFERRED]
  IMPLEMENTATION.md → gateway/verifier.py
- `Done (with proof)` --references--> `InferenceProvider`  [INFERRED]
  team/twaha/STATE.md → brain/providers/base.py
- `Log (append-only, newest at bottom)` --references--> `OpenCodeGoAdapter`  [INFERRED]
  team/SHARED_CONTEXT.md → brain/providers/opencode_go.py

## Import Cycles
- None detected.

## Communities (54 total, 16 thin omitted)

### Community 0 - "NotifierState"
Cohesion: 0.20
Nodes (7): ApprovalController, NotifierState, test_unauthorized_approval_never_calls_gateway(), test_approval_auth_expiry_duplicate_and_gateway_refusal(), test_gateway_refusal_does_not_record_approval(), test_repage_expiry_and_persistent_buttons(), test_success_status_with_refusal_body_is_not_approval()

### Community 1 - "test_audit.py"
Cohesion: 0.05
Nodes (56): quarantine(), redact(), redact_value(), AuditLog, canonical(), EventBus, verify(), active_bus() (+48 more)

### Community 2 - "6.4 Gateway (`gateway/`) [M] P0 unless marked"
Cohesion: 0.05
Nodes (40): 6.1 Chaos panel (`chaos/`) [A] P0, 6.2.1 Baselines (`baselines.py`), 6.2.2 Detector (`detector.py`), 6.2.3 Kubernetes watch (`kube_watch.py`), 6.2.4 Change journal (`journal.py`), 6.2.5 Flags (`flags.py`), 6.2 Observer (`observer/`) [M] P0, 6.3.1 Dependency graph (`graph.py`) (+32 more)

### Community 3 - "HttpTrialServices"
Cohesion: 0.11
Nodes (17): HttpTrialServices, ObservationError, stream(), test_reconnect_resumes_cursor_and_ignores_duplicate_events(), handle(), test_replayed_approval_does_not_repeat_post(), handle(), test_timeout_keeps_detection_and_diagnosis_measurements() (+9 more)

### Community 4 - "test_inference.py"
Cohesion: 0.08
Nodes (30): DiagnosisResult, DiagnosisService, InferenceProvider, InferenceRequest, InferenceResponse, ProviderError, OpenCodeGoAdapter, Diagnosis (+22 more)

### Community 5 - "models.py"
Cohesion: 0.07
Nodes (40): Benchmarks and adversarial checks, Discord notifier, Inference, On-call agent: Twaha components, Project graph, Setup and checks, ActionRequest, ApprovalDecidedPayload (+32 more)

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

### Community 13 - "Card"
Cohesion: 0.21
Nodes (4): Notifier, ApprovalView, DiscordNotifier, Card

### Community 14 - "Anirudh [A]: architecture of my part"
Cohesion: 0.29
Nodes (6): Anirudh [A]: architecture of my part, Flow through my parts, Hard rules my code must keep, What I need from others, What I own, What I provide to others

### Community 15 - "Anirudh [A]: state"
Cohesion: 0.29
Nodes (6): Anirudh [A]: state, Blocked / waiting on, Done (with proof), In progress, Next, Notes for my next session

### Community 16 - "test_observer.py"
Cohesion: 0.18
Nodes (13): require_env(), Backend, make(), prom_result(), test_brain_down_does_not_stop_detection(), handler(), test_endpoints(), test_nan_rows_are_dropped() (+5 more)

### Community 18 - "Observer"
Cohesion: 0.17
Nodes (5): load(), medians(), store(), Detector, Observer

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

### Community 38 - "test_verifier.py"
Cohesion: 0.10
Nodes (17): Manual baseline, spec_hashes(), harm_check(), ledger_effect(), service_score(), Verification, health(), test_verified_outcome_controls_persisted_trust_and_card() (+9 more)

### Community 39 - "JournalTest"
Cohesion: 0.10
Nodes (23): check(), author(), _configmap_changes(), _containers(), current(), _deployment_changes(), entry(), insert() (+15 more)

### Community 40 - "find_culprit"
Cohesion: 0.22
Nodes (7): deepest_unhealthy(), depth(), find_culprit(), from_traces(), is_error(), CulpritTest, trace()

### Community 42 - "trust_report.py"
Cohesion: 0.11
Nodes (15): main(), summarize(), main(), summarize_ledger(), check(), counts(), eligible(), lower_bound() (+7 more)

### Community 46 - "match"
Cohesion: 0.29
Nodes (7): _action(), latest_change_before_onset(), match(), to_bytes(), change(), incident(), RulesTest

### Community 48 - "test_chaos.py"
Cohesion: 0.23
Nodes (10): bad_pods(), pod_bad(), service_of(), _ts(), deployment(), iso(), pod(), test_bad_pod_rules() (+2 more)

### Community 49 - "Tracker"
Cohesion: 0.20
Nodes (7): run_watch(), Tracker, FakeResp, test_run_watch_relists_after_error(), list_fn(), test_tracker_journals_changes_including_after_relist(), test_tracker_pods_feed_bad_pods()

### Community 51 - "test_chaos.py"
Cohesion: 0.08
Nodes (42): bad_deploy(), broken_config(), datastore_down(), kubectl(), KubectlError, memory_leak(), read_flags(), read_live_flags() (+34 more)

### Community 52 - "test_bench.py"
Cohesion: 0.07
Nodes (17): Harness, measure(), TrialResult, TrialServices, compare(), main(), summarize(), FakeServices (+9 more)

### Community 53 - "build_from_env"
Cohesion: 0.18
Nodes (5): build_from_env(), create_app(), get_journal(), lifespan(), load()

### Community 54 - "charge.js"
Cohesion: 0.10
Nodes (13): { ATTR_ERROR_TYPE }, cardValidator, charge(), { context, propagation, trace, metrics, SpanStatusCode }, { FlagdProvider }, flagProvider, LOYALTY_LEVEL, meter (+5 more)

### Community 59 - "httpx"
Cohesion: 0.18
Nodes (7): main(), read_events(), lifespan(), load_approvers(), required(), test_notifier_rejects_rehearsal_identity_in_human_allowlist(), test_notifier_uses_gateway_approver_setting()

## Knowledge Gaps
- **1 isolated node(s):** `oncall-agent`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 295 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **16 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Implementation Plan: the on-call agent that has to earn its autonomy` connect `Implementation Plan: the on-call agent that has to earn its autonomy` to `6.4 Gateway (`gateway/`) [M] P0 unless marked`, `10. Build plan`, `3. Environment setup`, `8. Testing`, `0. Scope and principles`, `11. Demo`, `1. System overview`, `4. Configuration files`, `5. Data model`, `9. Benchmark (`bench/`) [T] P1`?**
  _High betweenness centrality (0.117) - this node is a cross-community bridge._
- **Are the 9 inferred relationships involving `DiagnosisService` (e.g. with `InferenceProvider` and `InferenceRequest`) actually correct?**
  _`DiagnosisService` has 9 INFERRED edges - model-reasoned connections that need verification._
- **What connects `oncall-agent` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `test_audit.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05147563486616335 - nodes in this community are weakly interconnected._
- **Why does `ActionRequest` connect `models.py` to `test_audit.py`, `test_inference.py`, `trust_report.py`, `8. Testing`, `httpx`?**
  _High betweenness centrality (0.113) - this node is a cross-community bridge._
- **Should `6.4 Gateway (`gateway/`) [M] P0 unless marked` be split into smaller, more focused modules?**
  _Cohesion score 0.05 - nodes in this community are weakly interconnected._
- **Why does `8.2 Property-based tests (`test_invariants.py`, Hypothesis) [M] P1` connect `8. Testing` to `models.py`?**
  _High betweenness centrality (0.096) - this node is a cross-community bridge._