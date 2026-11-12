# Graph Report - devhack2026  (2026-11-13)

## Corpus Check
- 95 files · ~37,969 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 5 file(s) not represented in the graph (top: (none) 3, .example 1, .lock 1)

## Summary
- 782 nodes · 1414 edges · 53 communities (38 shown, 15 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 82 edges (avg confidence: 0.58)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `43b3c1ff`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- NotifierState
- test_audit.py
- 6.4 Gateway (`gateway/`) [M] P0 unless marked
- consumer.py
- DiagnosisService
- test_chaos.py
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
- test_verifier.py
- JournalTest
- find_culprit
- det
- services
- security_check.sh
- make_kubeconfigs.sh
- LlmTest
- match
- components
- charge.js
- build_bad_payment.sh
- install_shop.sh
- setup_cluster.sh
- smoke.sh

## God Nodes (most connected - your core abstractions)
1. `DiagnosisService` - 25 edges
2. `NotifierState` - 25 edges
3. `Card` - 22 edges
4. `FakeProvider` - 19 edges
5. `ApprovalController` - 18 edges
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
- `FakeProvider` --uses--> `OpenCodeGoSyncAdapter`  [INFERRED]
  tests/test_inference.py → brain/providers/opencode_go_sync.py

## Import Cycles
- None detected.

## Communities (53 total, 15 thin omitted)

### Community 0 - "NotifierState"
Cohesion: 0.07
Nodes (27): quarantine(), redact(), redact_value(), Notifier, NotificationConsumer, ApprovalButton, ApprovalController, ApprovalView (+19 more)

### Community 1 - "test_audit.py"
Cohesion: 0.11
Nodes (30): AuditLog, canonical(), EventBus, verify(), active_bus(), create_events_router(), lifespan(), publish() (+22 more)

### Community 2 - "6.4 Gateway (`gateway/`) [M] P0 unless marked"
Cohesion: 0.05
Nodes (40): 6.1 Chaos panel (`chaos/`) [A] P0, 6.2.1 Baselines (`baselines.py`), 6.2.2 Detector (`detector.py`), 6.2.3 Kubernetes watch (`kube_watch.py`), 6.2.4 Change journal (`journal.py`), 6.2.5 Flags (`flags.py`), 6.2 Observer (`observer/`) [M] P0, 6.3.1 Dependency graph (`graph.py`) (+32 more)

### Community 3 - "consumer.py"
Cohesion: 0.08
Nodes (19): Harness, HttpTrialServices, main(), TrialResult, TrialServices, compare(), main(), summarize() (+11 more)

### Community 4 - "DiagnosisService"
Cohesion: 0.07
Nodes (45): DiagnosisResult, DiagnosisService, InferenceProvider, InferenceRequest, InferenceResponse, ProviderError, OpenCodeGoAdapter, ActionRequest (+37 more)

### Community 5 - "test_chaos.py"
Cohesion: 0.08
Nodes (28): bad_deploy(), kubectl(), KubectlError, read_all(), record(), create_app(), bad_deploy(), do_reset() (+20 more)

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
Cohesion: 0.22
Nodes (8): Benchmarks and adversarial checks, Discord notifier, Gateway mounting, Inference, Main-branch diagnosis compatibility, On-call agent: Twaha components, Project graph, Setup and checks

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
Cohesion: 0.14
Nodes (10): spec_hashes(), harm_check(), ledger_effect(), service_score(), Verification, HarmCheckTest, health(), svc() (+2 more)

### Community 39 - "JournalTest"
Cohesion: 0.07
Nodes (25): check(), check(), counts(), eligible(), lower_bound(), record(), author(), _configmap_changes() (+17 more)

### Community 40 - "find_culprit"
Cohesion: 0.27
Nodes (6): deepest_unhealthy(), find_culprit(), from_traces(), is_error(), CulpritTest, trace()

### Community 41 - "det"
Cohesion: 0.23
Nodes (3): Detector, det(), DetectorTest

### Community 42 - "services"
Cohesion: 0.05
Nodes (40): actable, critical, kind, actable, critical, kind, actable, critical (+32 more)

### Community 45 - "LlmTest"
Cohesion: 0.15
Nodes (9): config_from_env(), _diagnose(), OpenCodeGoSyncAdapter, request_body(), test_main_branch_sync_facade_uses_provider_adapter(), FakePost, LlmTest, reply() (+1 more)

### Community 46 - "match"
Cohesion: 0.29
Nodes (7): _action(), latest_change_before_onset(), match(), to_bytes(), change(), incident(), RulesTest

### Community 47 - "components"
Cohesion: 0.06
Nodes (30): enabled, enabled, replicas, components, agent, chatbot, checkout, mcp (+22 more)

### Community 48 - "charge.js"
Cohesion: 0.10
Nodes (13): { ATTR_ERROR_TYPE }, cardValidator, charge(), { context, propagation, trace, metrics, SpanStatusCode }, { FlagdProvider }, flagProvider, LOYALTY_LEVEL, meter (+5 more)

## Knowledge Gaps
- **1 isolated node(s):** `oncall-agent`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 308 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **15 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `connect()` connect `JournalTest` to `test_audit.py`?**
  _High betweenness centrality (0.051) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `DiagnosisService` (e.g. with `InferenceProvider` and `InferenceRequest`) actually correct?**
  _`DiagnosisService` has 7 INFERRED edges - model-reasoned connections that need verification._
- **What connects `oncall-agent` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `NotifierState` be split into smaller, more focused modules?**
  _Cohesion score 0.06964006259780908 - nodes in this community are weakly interconnected._
- **Why does `GatewayDecision` connect `test_audit.py` to `NotifierState`, `consumer.py`, `DiagnosisService`?**
  _High betweenness centrality (0.027) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `NotifierState` (e.g. with `NotificationConsumer` and `ApprovalButton`) actually correct?**
  _`NotifierState` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_audit.py` be split into smaller, more focused modules?**
  _Cohesion score 0.10522496371552975 - nodes in this community are weakly interconnected._