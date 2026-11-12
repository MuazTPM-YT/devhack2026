# Graph Report - devhack2026  (2026-11-13)

## Corpus Check
- 65 files · ~30,852 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 526 nodes · 980 edges · 44 communities (40 shown, 4 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 65 edges (avg confidence: 0.53)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `4c78e795`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- NotifierState
- test_audit.py
- 6.4 Gateway (`gateway/`) [M] P0 unless marked
- consumer.py
- DiagnosisService
- models.py
- AGENTS.md
- CLAUDE.md
- 10. Build plan
- Anirudh [A]: tasks
- Muaz [M]: tasks
- Twaha [T]: tasks
- Implementation Plan: the on-call agent that has to earn its autonomy
- On-call agent: Twaha components
- Anirudh [A]: architecture of my part
- Anirudh [A]: state
- Muaz [M]: architecture of my part
- Muaz [M]: state
- Shared context (all agents read and write this)
- Twaha [T]: architecture of my part
- Twaha [T]: state
- 3. Environment setup
- 8. Testing
- summarize
- 0. Scope and principles
- 11. Demo
- 1. System overview
- 4. Configuration files
- 5. Data model
- 9. Benchmark (`bench/`) [T] P1
- manual_baseline.md
- oncall-agent
- JournalTest
- find_culprit
- det
- journal.py
- security_check.sh
- make_kubeconfigs.sh

## God Nodes (most connected - your core abstractions)
1. `DiagnosisService` - 25 edges
2. `NotifierState` - 25 edges
3. `Card` - 22 edges
4. `ApprovalController` - 18 edges
5. `FakeProvider` - 18 edges
6. `DiscordNotifier` - 17 edges
7. `GatewayDecision` - 17 edges
8. `redact_value()` - 16 edges
9. `AuditLog` - 16 edges
10. `EventBus` - 16 edges

## Surprising Connections (you probably didn't know these)
- `TrialResult` --uses--> `GatewayDecision`  [INFERRED]
  bench/harness.py → schemas/models.py
- `TrialServices` --uses--> `GatewayDecision`  [INFERRED]
  bench/harness.py → schemas/models.py
- `Harness` --uses--> `GatewayDecision`  [INFERRED]
  bench/harness.py → schemas/models.py
- `HttpTrialServices` --uses--> `GatewayDecision`  [INFERRED]
  bench/harness.py → schemas/models.py
- `test_adversarial_proposal()` --calls--> `DiagnosisService`  [EXTRACTED]
  tests/redteam/test_attacks.py → brain/llm.py

## Import Cycles
- None detected.

## Communities (44 total, 4 thin omitted)

### Community 0 - "NotifierState"
Cohesion: 0.06
Nodes (39): Any, quarantine(), redact(), redact_value(), Any, AsyncClient, read_events(), Interaction (+31 more)

### Community 1 - "test_audit.py"
Cohesion: 0.11
Nodes (36): AuditLog, canonical(), EventBus, Any, Path, verify(), active_bus(), create_events_router() (+28 more)

### Community 2 - "6.4 Gateway (`gateway/`) [M] P0 unless marked"
Cohesion: 0.05
Nodes (40): 6.1 Chaos panel (`chaos/`) [A] P0, 6.2.1 Baselines (`baselines.py`), 6.2.2 Detector (`detector.py`), 6.2.3 Kubernetes watch (`kube_watch.py`), 6.2.4 Change journal (`journal.py`), 6.2.5 Flags (`flags.py`), 6.2 Observer (`observer/`) [M] P0, 6.3.1 Dependency graph (`graph.py`) (+32 more)

### Community 3 - "consumer.py"
Cohesion: 0.09
Nodes (25): Harness, HttpTrialServices, main(), Any, AsyncClient, Path, Protocol, TrialResult (+17 more)

### Community 4 - "DiagnosisService"
Cohesion: 0.13
Nodes (32): DiagnosisResult, DiagnosisService, Path, InferenceProvider, InferenceRequest, InferenceResponse, ProviderError, Protocol (+24 more)

### Community 5 - "models.py"
Cohesion: 0.11
Nodes (19): BaseModel, ApprovalDecidedPayload, ApprovalRequestedPayload, CardPayload, Cause, ChecklistPayload, DiagnosisReadyPayload, Event (+11 more)

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

### Community 13 - "On-call agent: Twaha components"
Cohesion: 0.25
Nodes (7): Benchmarks and adversarial checks, Discord notifier, Gateway mounting, Inference, On-call agent: Twaha components, Project graph, Setup and checks

### Community 14 - "Anirudh [A]: architecture of my part"
Cohesion: 0.29
Nodes (6): Anirudh [A]: architecture of my part, Flow through my parts, Hard rules my code must keep, What I need from others, What I own, What I provide to others

### Community 15 - "Anirudh [A]: state"
Cohesion: 0.29
Nodes (6): Anirudh [A]: state, Blocked / waiting on, Done (with proof), In progress, Next, Notes for my next session

### Community 16 - "Muaz [M]: architecture of my part"
Cohesion: 0.29
Nodes (6): Flow through my code, Hard rules my code must keep, Muaz [M]: architecture of my part, What I need from others, What I own, What I provide to others

### Community 17 - "Muaz [M]: state"
Cohesion: 0.29
Nodes (6): Blocked / waiting on, Done (with proof), In progress, Muaz [M]: state, Next, Notes for my next session

### Community 18 - "Shared context (all agents read and write this)"
Cohesion: 0.29
Nodes (6): Contracts (agreed interfaces between owners), Log (append-only, newest at bottom), Open questions, Rules for agents, Shared context (all agents read and write this), VERIFY results (§3.3, Phase 0)

### Community 19 - "Twaha [T]: architecture of my part"
Cohesion: 0.29
Nodes (6): Flow through my parts, Hard rules my code must keep, Twaha [T]: architecture of my part, What I need from others, What I own, What I provide to others

### Community 20 - "Twaha [T]: state"
Cohesion: 0.29
Nodes (6): Blocked / waiting on, Done (with proof), In progress, Next, Notes for my next session, Twaha [T]: state

### Community 21 - "3. Environment setup"
Cohesion: 0.33
Nodes (6): 3.1 Prerequisites [A] P0, 3.2 Cluster [A] P0, 3.3 The shop [A] P0, 3.4 The buggy payment image [A] P0, 3.5 Kubeconfigs for the three identities [M] P0, 3. Environment setup

### Community 22 - "8. Testing"
Cohesion: 0.40
Nodes (5): 8.1 Unit tests [M][T] P0, 8.2 Property-based tests (`test_invariants.py`, Hypothesis) [M] P1, 8.3 Red-team suite (`tests/redteam/`) [T] P1, 8.4 Smoke test (`scripts/smoke.sh`) [A] P0, 8. Testing

### Community 23 - "summarize"
Cohesion: 0.67
Nodes (3): main(), Path, summarize()

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

### Community 39 - "JournalTest"
Cohesion: 0.19
Nodes (5): connect(), Connection, DbTest, deploy(), JournalTest

### Community 40 - "find_culprit"
Cohesion: 0.27
Nodes (6): deepest_unhealthy(), find_culprit(), from_traces(), is_error(), CulpritTest, trace()

### Community 41 - "det"
Cohesion: 0.23
Nodes (3): Detector, det(), DetectorTest

### Community 42 - "journal.py"
Cohesion: 0.32
Nodes (11): author(), _configmap_changes(), _containers(), _deployment_changes(), entry(), insert(), Connection, read() (+3 more)

## Knowledge Gaps
- **160 isolated node(s):** `oncall-agent`, `make_kubeconfigs.sh script`, `Communication`, `Code comments`, `Workflow` (+155 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `GatewayDecision` connect `test_audit.py` to `NotifierState`, `consumer.py`, `models.py`?**
  _High betweenness centrality (0.050) - this node is a cross-community bridge._
- **Why does `connect()` connect `JournalTest` to `test_audit.py`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._
- **Why does `Card` connect `NotifierState` to `test_audit.py`, `models.py`?**
  _High betweenness centrality (0.025) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `DiagnosisService` (e.g. with `InferenceProvider` and `InferenceRequest`) actually correct?**
  _`DiagnosisService` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `NotifierState` (e.g. with `NotificationConsumer` and `ApprovalButton`) actually correct?**
  _`NotifierState` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `Card` (e.g. with `ReceiptStore` and `Notifier`) actually correct?**
  _`Card` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `ApprovalController` (e.g. with `NotifierState` and `Card`) actually correct?**
  _`ApprovalController` has 3 INFERRED edges - model-reasoned connections that need verification._