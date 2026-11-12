# Graph Report - devhack2026  (2026-11-13)

## Corpus Check
- 97 files · ~43,147 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 811 nodes · 1733 edges · 54 communities (45 shown, 9 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 94 edges (avg confidence: 0.58)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `f442ab94`
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
- On-call agent: Twaha components
- Anirudh [A]: architecture of my part
- Anirudh [A]: state
- Shared context (all agents read and write this)
- Muaz [M]: state
- Twaha [T]: state
- 3. Environment setup
- 8. Testing
- 0. Scope and principles
- 11. Demo
- 1. System overview
- 4. Configuration files
- 5. Data model
- 9. Benchmark (`bench/`) [T] P1
- manual_baseline.md
- ref_logger
- oncall-agent
- test_trust_integration.py
- JournalTest
- find_culprit
- connect
- security_check.sh
- make_kubeconfigs.sh
- install_shop.sh
- match
- setup_cluster.sh
- main.py
- test_chaos.py
- charge.js
- Twaha [T]: architecture of my part
- Muaz [M]: architecture of my part
- build_bad_payment.sh
- smoke.sh

## God Nodes (most connected - your core abstractions)
1. `DiagnosisService` - 25 edges
2. `NotifierState` - 25 edges
3. `connect()` - 25 edges
4. `HttpTrialServices` - 24 edges
5. `Card` - 24 edges
6. `GatewayDecision` - 20 edges
7. `ApprovalController` - 18 edges
8. `FakeProvider` - 18 edges
9. `redact_value()` - 17 edges
10. `DiscordNotifier` - 17 edges

## Surprising Connections (you probably didn't know these)
- `TrialResult` --uses--> `GatewayDecision`  [INFERRED]
  bench/harness.py → schemas/models.py
- `ObservationError` --uses--> `GatewayDecision`  [INFERRED]
  bench/harness.py → schemas/models.py
- `TrialServices` --uses--> `GatewayDecision`  [INFERRED]
  bench/harness.py → schemas/models.py
- `Harness` --uses--> `GatewayDecision`  [INFERRED]
  bench/harness.py → schemas/models.py
- `HttpTrialServices` --uses--> `GatewayDecision`  [INFERRED]
  bench/harness.py → schemas/models.py

## Import Cycles
- None detected.

## Communities (54 total, 9 thin omitted)

### Community 0 - "NotifierState"
Cohesion: 0.05
Nodes (58): asyncio, Any, quarantine(), redact(), redact_value(), Any, Path, read_all() (+50 more)

### Community 1 - "test_audit.py"
Cohesion: 0.09
Nodes (40): concurrent_futures, fastapi_responses, AuditLog, canonical(), EventBus, Any, Path, verify() (+32 more)

### Community 2 - "6.4 Gateway (`gateway/`) [M] P0 unless marked"
Cohesion: 0.05
Nodes (40): 6.1 Chaos panel (`chaos/`) [A] P0, 6.2.1 Baselines (`baselines.py`), 6.2.2 Detector (`detector.py`), 6.2.3 Kubernetes watch (`kube_watch.py`), 6.2.4 Change journal (`journal.py`), 6.2.5 Flags (`flags.py`), 6.2 Observer (`observer/`) [M] P0, 6.3.1 Dependency graph (`graph.py`) (+32 more)

### Community 3 - "HttpTrialServices"
Cohesion: 0.07
Nodes (38): Harness, HttpTrialServices, main(), measure(), ObservationError, Any, AsyncClient, Path (+30 more)

### Community 4 - "test_inference.py"
Cohesion: 0.14
Nodes (29): DiagnosisResult, DiagnosisService, Path, InferenceProvider, InferenceRequest, InferenceResponse, ProviderError, Protocol (+21 more)

### Community 5 - "models.py"
Cohesion: 0.10
Nodes (29): BaseModel, ActionRequest, ApprovalDecidedPayload, ApprovalRequestedPayload, CardPayload, Cause, ChecklistPayload, DiagnosisReadyPayload (+21 more)

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
Nodes (9): Evidence and next gate (2026-11-13), Never cut, Phase 0: foundations, Phase 1: the spine, Phase 2: checks, Phase 3: humans and proof, Phase 4: measurement, Phase 5: freeze (+1 more)

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

### Community 16 - "Shared context (all agents read and write this)"
Cohesion: 0.29
Nodes (6): Contracts (agreed interfaces between owners), Log (append-only, newest at bottom), Open questions, Rules for agents, Shared context (all agents read and write this), VERIFY results (§3.3, Phase 0)

### Community 17 - "Muaz [M]: state"
Cohesion: 0.29
Nodes (6): Blocked / waiting on, Done (with proof), In progress, Muaz [M]: state, Next, Notes for my next session

### Community 20 - "Twaha [T]: state"
Cohesion: 0.29
Nodes (6): Blocked / waiting on, Done (with proof), In progress, Next, Notes for next session, Twaha [T]: state

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

### Community 38 - "test_trust_integration.py"
Cohesion: 0.11
Nodes (17): spec_hashes(), harm_check(), ledger_effect(), service_score(), Verification, hashlib, health(), test_verified_outcome_controls_persisted_trust_and_card() (+9 more)

### Community 39 - "JournalTest"
Cohesion: 0.11
Nodes (18): check(), author(), _configmap_changes(), _containers(), current(), _deployment_changes(), entry(), insert() (+10 more)

### Community 40 - "find_culprit"
Cohesion: 0.24
Nodes (7): deepest_unhealthy(), find_culprit(), from_traces(), is_error(), collections, CulpritTest, trace()

### Community 42 - "connect"
Cohesion: 0.09
Nodes (25): argparse, main(), Path, summarize(), main(), Any, Path, summarize_ledger() (+17 more)

### Community 46 - "match"
Cohesion: 0.29
Nodes (7): _action(), latest_change_before_onset(), match(), to_bytes(), change(), incident(), RulesTest

### Community 48 - "main.py"
Cohesion: 0.05
Nodes (51): logging, math, load(), Connection, store(), Detector, fetch_readings(), prom_query() (+43 more)

### Community 51 - "test_chaos.py"
Cohesion: 0.11
Nodes (32): bad_deploy(), kubectl(), KubectlError, create_app(), FastAPI, Kubectl, Path, diff_ops() (+24 more)

### Community 54 - "charge.js"
Cohesion: 0.11
Nodes (20): { ATTR_ERROR_TYPE }, cardValidator, charge(), { context, propagation, trace, metrics, SpanStatusCode }, { FlagdProvider }, flagProvider, logger, LOYALTY_LEVEL (+12 more)

### Community 55 - "Twaha [T]: architecture of my part"
Cohesion: 0.29
Nodes (6): Flow through my parts, Hard rules my code must keep, Twaha [T]: architecture of my part, What I need from others, What I own, What I provide to others

### Community 60 - "Muaz [M]: architecture of my part"
Cohesion: 0.29
Nodes (6): Flow through my code, Hard rules my code must keep, Muaz [M]: architecture of my part, What I need from others, What I own, What I provide to others

## Knowledge Gaps
- **174 isolated node(s):** `{ context, propagation, trace, metrics, SpanStatusCode }`, `{ ATTR_ERROR_TYPE }`, `{ v4: uuidv4 }`, `{ FlagdProvider }`, `flagProvider` (+169 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `connect()` connect `connect` to `test_audit.py`, `models.py`, `test_trust_integration.py`, `JournalTest`, `main.py`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **Why does `GatewayDecision` connect `test_audit.py` to `NotifierState`, `HttpTrialServices`, `models.py`?**
  _High betweenness centrality (0.025) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `DiagnosisService` (e.g. with `InferenceProvider` and `InferenceRequest`) actually correct?**
  _`DiagnosisService` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `NotifierState` (e.g. with `NotificationConsumer` and `ApprovalButton`) actually correct?**
  _`NotifierState` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `HttpTrialServices` (e.g. with `GatewayDecision` and `FakeServices`) actually correct?**
  _`HttpTrialServices` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `Card` (e.g. with `ReceiptStore` and `Notifier`) actually correct?**
  _`Card` has 7 INFERRED edges - model-reasoned connections that need verification._
- **What connects `{ context, propagation, trace, metrics, SpanStatusCode }`, `{ ATTR_ERROR_TYPE }`, `{ v4: uuidv4 }` to the rest of the system?**
  _175 weakly-connected nodes found - possible documentation gaps or missing edges._