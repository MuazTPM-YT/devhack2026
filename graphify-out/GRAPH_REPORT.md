# Graph Report - devhack2026  (2026-11-13)

## Corpus Check
- 104 files · ~48,408 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 889 nodes · 2013 edges · 60 communities (51 shown, 9 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 114 edges (avg confidence: 0.58)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `87b51e79`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- NotifierState
- test_audit.py
- 6.4 Gateway (`gateway/`) [M] P0 unless marked
- HttpTrialServices
- DiagnosisService
- connect
- AGENTS.md
- CLAUDE.md
- 10. Build plan
- Anirudh [A]: tasks
- Muaz [M]: tasks
- Twaha [T]: tasks
- Implementation Plan: the on-call agent that has to earn its autonomy
- main.py
- Anirudh [A]: architecture of my part
- Anirudh [A]: state
- test_observer.py
- On-call agent: Twaha components
- main.py
- Muaz [M]: state
- Twaha [T]: state
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
- Twaha [T]: architecture of my part
- Shared context (all agents read and write this)
- oncall-agent
- manual_baseline.md
- test_trust_integration.py
- journal.py
- Detector
- trust_report.py
- security_check.sh
- make_kubeconfigs.sh
- install_shop.sh
- match
- setup_cluster.sh
- test_kube_watch.py
- Tracker
- test_chaos.py
- charge.js
- Muaz [M]: architecture of my part
- ref_logger
- build_bad_payment.sh
- smoke.sh

## God Nodes (most connected - your core abstractions)
1. `DiagnosisService` - 32 edges
2. `connect()` - 29 edges
3. `NotifierState` - 25 edges
4. `HttpTrialServices` - 24 edges
5. `Card` - 24 edges
6. `Incident` - 20 edges
7. `GatewayDecision` - 20 edges
8. `ActionRequest` - 19 edges
9. `ApprovalController` - 18 edges
10. `FakeProvider` - 18 edges

## Surprising Connections (you probably didn't know these)
- `test_manual_comparison_preserves_missing_measurements()` --calls--> `compare()`  [EXTRACTED]
  tests/test_bench.py → bench/report.py
- `DiagnosisResult` --uses--> `ActionRequest`  [INFERRED]
  brain/llm.py → schemas/models.py
- `DiagnosisResult` --uses--> `EvidenceBundle`  [INFERRED]
  brain/llm.py → schemas/models.py
- `DiagnosisService` --uses--> `ActionRequest`  [INFERRED]
  brain/llm.py → schemas/models.py
- `DiagnosisService` --uses--> `EvidenceBundle`  [INFERRED]
  brain/llm.py → schemas/models.py

## Import Cycles
- None detected.

## Communities (60 total, 9 thin omitted)

### Community 0 - "NotifierState"
Cohesion: 0.07
Nodes (36): asyncio, discord, Any, AsyncClient, read_events(), httpx, Interaction, Notifier (+28 more)

### Community 1 - "test_audit.py"
Cohesion: 0.09
Nodes (40): argparse, concurrent_futures, fastapi, fastapi_responses, AuditLog, canonical(), EventBus, Any (+32 more)

### Community 2 - "6.4 Gateway (`gateway/`) [M] P0 unless marked"
Cohesion: 0.05
Nodes (40): 6.1 Chaos panel (`chaos/`) [A] P0, 6.2.1 Baselines (`baselines.py`), 6.2.2 Detector (`detector.py`), 6.2.3 Kubernetes watch (`kube_watch.py`), 6.2.4 Change journal (`journal.py`), 6.2.5 Flags (`flags.py`), 6.2 Observer (`observer/`) [M] P0, 6.3.1 Dependency graph (`graph.py`) (+32 more)

### Community 3 - "HttpTrialServices"
Cohesion: 0.08
Nodes (35): Harness, HttpTrialServices, main(), measure(), ObservationError, Any, AsyncClient, Path (+27 more)

### Community 4 - "DiagnosisService"
Cohesion: 0.09
Nodes (41): DiagnosisResult, DiagnosisService, Path, InferenceProvider, InferenceRequest, InferenceResponse, ProviderError, Protocol (+33 more)

### Community 5 - "connect"
Cohesion: 0.20
Nodes (6): connect(), Connection, tempfile, DbTest, TrustTest, unittest

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

### Community 13 - "main.py"
Cohesion: 0.06
Nodes (58): build_bundle(), change_evidence(), collect_k8s(), k8s_evidence(), log_evidence(), memory_ratio(), metric_evidence(), Any (+50 more)

### Community 14 - "Anirudh [A]: architecture of my part"
Cohesion: 0.29
Nodes (6): Anirudh [A]: architecture of my part, Flow through my parts, Hard rules my code must keep, What I need from others, What I own, What I provide to others

### Community 15 - "Anirudh [A]: state"
Cohesion: 0.29
Nodes (6): Anirudh [A]: state, Blocked / waiting on, Done (with proof), In progress, Next, Notes for my next session

### Community 16 - "test_observer.py"
Cohesion: 0.21
Nodes (15): require_env(), Backend, make(), prom_result(), Request, Response, Fake Prometheus + gateway + brain behind one httpx MockTransport., test_brain_down_does_not_stop_detection() (+7 more)

### Community 17 - "On-call agent: Twaha components"
Cohesion: 0.25
Nodes (7): Benchmarks and adversarial checks, Discord notifier, Gateway mounting, Inference, On-call agent: Twaha components, Project graph, Setup and checks

### Community 18 - "main.py"
Cohesion: 0.23
Nodes (8): contextlib, math, fetch_readings(), prom_query(), AsyncClient, create_app(), Observer, FastAPI

### Community 19 - "Muaz [M]: state"
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

### Community 23 - "test_bench_export.py"
Cohesion: 0.15
Nodes (25): display(), export_report(), markdown(), Any, Path, timing_svg(), main(), Path (+17 more)

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
Cohesion: 0.10
Nodes (27): BaseModel, pytest, ActionRequest, ApprovalDecidedPayload, ApprovalRequestedPayload, CardPayload, Cause, ChecklistPayload (+19 more)

### Community 32 - "Twaha [T]: architecture of my part"
Cohesion: 0.29
Nodes (6): Flow through my parts, Hard rules my code must keep, Twaha [T]: architecture of my part, What I need from others, What I own, What I provide to others

### Community 34 - "Shared context (all agents read and write this)"
Cohesion: 0.29
Nodes (6): Contracts (agreed interfaces between owners), Log (append-only, newest at bottom), Open questions, Rules for agents, Shared context (all agents read and write this), VERIFY results (§3.3, Phase 0)

### Community 38 - "test_trust_integration.py"
Cohesion: 0.11
Nodes (18): spec_hashes(), harm_check(), ledger_effect(), service_score(), Verification, hashlib, health(), test_resource_rule_actions_keep_different_approval_eligibility() (+10 more)

### Community 39 - "journal.py"
Cohesion: 0.11
Nodes (19): copy, check(), author(), _configmap_changes(), _containers(), current(), _deployment_changes(), entry() (+11 more)

### Community 41 - "Detector"
Cohesion: 0.24
Nodes (3): Detector, det(), DetectorTest

### Community 42 - "trust_report.py"
Cohesion: 0.15
Nodes (18): main(), Any, Path, summarize_ledger(), check(), counts(), eligible(), lower_bound() (+10 more)

### Community 46 - "match"
Cohesion: 0.29
Nodes (7): _action(), latest_change_before_onset(), match(), to_bytes(), change(), incident(), RulesTest

### Community 48 - "test_kube_watch.py"
Cohesion: 0.26
Nodes (13): logging, bad_pods(), pod_bad(), service_of(), _ts(), deployment(), iso(), pod() (+5 more)

### Community 49 - "Tracker"
Cohesion: 0.21
Nodes (9): Connection, run_watch(), Tracker, build_from_env(), AsyncClient, Connection, FakeResp, test_run_watch_relists_after_error() (+1 more)

### Community 51 - "test_chaos.py"
Cohesion: 0.10
Nodes (35): bad_deploy(), kubectl(), KubectlError, Any, Path, read_all(), record(), create_app() (+27 more)

### Community 54 - "charge.js"
Cohesion: 0.11
Nodes (20): { ATTR_ERROR_TYPE }, cardValidator, charge(), { context, propagation, trace, metrics, SpanStatusCode }, { FlagdProvider }, flagProvider, logger, LOYALTY_LEVEL (+12 more)

### Community 55 - "Muaz [M]: architecture of my part"
Cohesion: 0.29
Nodes (6): Flow through my code, Hard rules my code must keep, Muaz [M]: architecture of my part, What I need from others, What I own, What I provide to others

## Knowledge Gaps
- **174 isolated node(s):** `{ context, propagation, trace, metrics, SpanStatusCode }`, `{ ATTR_ERROR_TYPE }`, `{ v4: uuidv4 }`, `{ FlagdProvider }`, `flagProvider` (+169 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `connect()` connect `connect` to `test_audit.py`, `test_trust_integration.py`, `journal.py`, `trust_report.py`, `main.py`, `test_kube_watch.py`, `Tracker`, `main.py`, `test_observer.py`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **Why does `GatewayDecision` connect `HttpTrialServices` to `NotifierState`, `test_audit.py`, `models.py`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **Why does `Card` connect `NotifierState` to `test_audit.py`, `models.py`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **Are the 10 inferred relationships involving `DiagnosisService` (e.g. with `InferenceProvider` and `InferenceRequest`) actually correct?**
  _`DiagnosisService` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `NotifierState` (e.g. with `NotificationConsumer` and `ApprovalButton`) actually correct?**
  _`NotifierState` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `HttpTrialServices` (e.g. with `GatewayDecision` and `FakeServices`) actually correct?**
  _`HttpTrialServices` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `{ context, propagation, trace, metrics, SpanStatusCode }`, `{ ATTR_ERROR_TYPE }`, `{ v4: uuidv4 }` to the rest of the system?**
  _176 weakly-connected nodes found - possible documentation gaps or missing edges._