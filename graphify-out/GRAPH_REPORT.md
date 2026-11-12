# Graph Report - devhack2026  (2026-11-13)

## Corpus Check
- 74 files · ~34,173 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 4 file(s) not represented in the graph (top: (none) 2, .example 1, .lock 1)

## Summary
- 664 nodes · 1399 edges · 40 communities (31 shown, 9 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 138 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `f19d8a41`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- NotifierState
- test_audit.py
- 6.4 Gateway (`gateway/`) [M] P0 unless marked
- test_bench.py
- test_inference.py
- models.py
- AGENTS.md
- CLAUDE.md
- 10. Build plan
- Anirudh [A]: tasks
- Muaz [M]: tasks
- Twaha [T]: tasks
- Implementation Plan: the on-call agent that has to earn its autonomy
- TrialServices
- Anirudh [A]: architecture of my part
- Anirudh [A]: state
- json
- Twaha [T]: state
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
- test_verifier.py
- journal.py
- find_culprit
- det
- security_check.sh
- make_kubeconfigs.sh
- match

## God Nodes (most connected - your core abstractions)
1. `DiagnosisService` - 26 edges
2. `NotifierState` - 22 edges
3. `redact_value()` - 20 edges
4. `Card` - 18 edges
5. `ApprovalController` - 17 edges
6. `ActionRequest` - 17 edges
7. `verify()` - 16 edges
8. `AuditLog` - 16 edges
9. `EventBus` - 16 edges
10. `NotificationConsumer` - 16 edges

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

## Communities (40 total, 9 thin omitted)

### Community 0 - "NotifierState"
Cohesion: 0.06
Nodes (20): read_events(), Notifier, NotificationConsumer, ApprovalButton, ApprovalController, ApprovalView, DiscordNotifier, lifespan() (+12 more)

### Community 1 - "test_audit.py"
Cohesion: 0.07
Nodes (40): AuditLog, EventBus, active_bus(), create_events_router(), events(), stream(), publish_event(), selected_bus() (+32 more)

### Community 2 - "6.4 Gateway (`gateway/`) [M] P0 unless marked"
Cohesion: 0.05
Nodes (40): 6.1 Chaos panel (`chaos/`) [A] P0, 6.2.1 Baselines (`baselines.py`), 6.2.2 Detector (`detector.py`), 6.2.3 Kubernetes watch (`kube_watch.py`), 6.2.4 Change journal (`journal.py`), 6.2.5 Flags (`flags.py`), 6.2 Observer (`observer/`) [M] P0, 6.3.1 Dependency graph (`graph.py`) (+32 more)

### Community 3 - "test_bench.py"
Cohesion: 0.09
Nodes (19): Harness, HttpTrialServices, main(), TrialResult, compare(), main(), summarize(), FakeServices (+11 more)

### Community 4 - "test_inference.py"
Cohesion: 0.09
Nodes (25): DiagnosisResult, DiagnosisService, InferenceProvider, InferenceRequest, InferenceResponse, ProviderError, OpenCodeGoAdapter, Diagnosis (+17 more)

### Community 5 - "models.py"
Cohesion: 0.09
Nodes (32): ActionRequest, ApprovalDecidedPayload, ApprovalRequestedPayload, CardPayload, Cause, ChecklistPayload, DiagnosisReadyPayload, Event (+24 more)

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
Nodes (9): Integration proof (2026-11-13), Never cut, Phase 0: foundations, Phase 1: the spine, Phase 2: checks, Phase 3: humans and proof, Phase 4: measurement, Phase 5: freeze (+1 more)

### Community 12 - "Implementation Plan: the on-call agent that has to earn its autonomy"
Cohesion: 0.29
Nodes (6): 12. Risks and fallbacks, 13. Submission checklist, 14. Command cheat sheet, 2. Repository layout, 7. End-to-end flows (acceptance scenarios), Implementation Plan: the on-call agent that has to earn its autonomy

### Community 14 - "Anirudh [A]: architecture of my part"
Cohesion: 0.29
Nodes (6): Anirudh [A]: architecture of my part, Flow through my parts, Hard rules my code must keep, What I need from others, What I own, What I provide to others

### Community 15 - "Anirudh [A]: state"
Cohesion: 0.29
Nodes (6): Anirudh [A]: state, Blocked / waiting on, Done (with proof), In progress, Next, Notes for my next session

### Community 16 - "json"
Cohesion: 0.07
Nodes (26): main(), summarize(), quarantine(), redact(), redact_value(), canonical(), verify(), main() (+18 more)

### Community 20 - "Twaha [T]: state"
Cohesion: 0.33
Nodes (5): Blocked / waiting on, In progress, Next, Notes for my next session, Twaha [T]: state

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

### Community 34 - "connect"
Cohesion: 0.14
Nodes (8): check(), counts(), eligible(), lower_bound(), record(), connect(), DbTest, TrustTest

### Community 38 - "test_verifier.py"
Cohesion: 0.12
Nodes (11): Manual baseline, spec_hashes(), harm_check(), ledger_effect(), service_score(), Verification, HarmCheckTest, health() (+3 more)

### Community 39 - "journal.py"
Cohesion: 0.10
Nodes (23): check(), author(), _configmap_changes(), _containers(), current(), _deployment_changes(), entry(), insert() (+15 more)

### Community 40 - "find_culprit"
Cohesion: 0.22
Nodes (7): deepest_unhealthy(), depth(), find_culprit(), from_traces(), is_error(), CulpritTest, trace()

### Community 41 - "det"
Cohesion: 0.22
Nodes (3): Detector, det(), DetectorTest

### Community 46 - "match"
Cohesion: 0.29
Nodes (7): _action(), latest_change_before_onset(), match(), to_bytes(), change(), incident(), RulesTest

## Knowledge Gaps
- **1 isolated node(s):** `oncall-agent`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 240 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Implementation Plan: the on-call agent that has to earn its autonomy` connect `Implementation Plan: the on-call agent that has to earn its autonomy` to `6.4 Gateway (`gateway/`) [M] P0 unless marked`, `10. Build plan`, `3. Environment setup`, `8. Testing`, `0. Scope and principles`, `11. Demo`, `1. System overview`, `4. Configuration files`, `5. Data model`, `9. Benchmark (`bench/`) [T] P1`?**
  _High betweenness centrality (0.157) - this node is a cross-community bridge._
- **Are the 9 inferred relationships involving `DiagnosisService` (e.g. with `InferenceProvider` and `InferenceRequest`) actually correct?**
  _`DiagnosisService` has 9 INFERRED edges - model-reasoned connections that need verification._
- **What connects `oncall-agent` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `NotifierState` be split into smaller, more focused modules?**
  _Cohesion score 0.06172839506172839 - nodes in this community are weakly interconnected._
- **Why does `ActionRequest` connect `models.py` to `json`, `NotifierState`, `test_inference.py`, `8. Testing`?**
  _High betweenness centrality (0.119) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `NotifierState` (e.g. with `NotificationConsumer` and `ApprovalController`) actually correct?**
  _`NotifierState` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_audit.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07307692307692308 - nodes in this community are weakly interconnected._