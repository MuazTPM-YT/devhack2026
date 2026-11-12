# Graph Report - devhack2026  (2026-11-13)

## Corpus Check
- 114 files · ~55,190 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1036 nodes · 2537 edges · 58 communities (49 shown, 9 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 162 edges (avg confidence: 0.57)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `98b8ade8`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- NotifierState
- ReceiptStore
- 6.4 Gateway (`gateway/`) [M] P0 unless marked
- HttpTrialServices
- find_culprit
- Anirudh [A]: tasks
- AGENTS.md
- CLAUDE.md
- 10. Build plan
- main.py
- checklist.py
- Implementation Plan: the on-call agent that has to earn its autonomy
- test_brain.py
- Anirudh [A]: architecture of my part
- models.py
- connect
- On-call agent: Twaha components
- Anirudh [A]: state
- 3. Environment setup
- 8. Testing
- test_bench_export.py
- 0. Scope and principles
- 11. Demo
- 1. System overview
- 4. Configuration files
- 5. Data model
- 9. Benchmark (`bench/`) [T] P1
- GatewayDecision
- manual_baseline.md
- oncall-agent
- ref_logger
- journal.py
- Detector
- trust.py
- security_check.sh
- make_kubeconfigs.sh
- install_shop.sh
- setup_cluster.sh
- test_verify_loop.py
- test_chaos.py
- charge.js
- Twaha [T]: state
- Twaha [T]: tasks
- Muaz [M]: tasks
- build_bad_payment.sh
- smoke.sh
- Muaz [M]: architecture of my part
- Twaha [T]: architecture of my part
- Muaz [M]: state
- Shared context (all agents read and write this)

## God Nodes (most connected - your core abstractions)
1. `GatewayDecision` - 45 edges
2. `Gateway` - 42 edges
3. `ActionRequest` - 37 edges
4. `connect()` - 35 edges
5. `DiagnosisService` - 32 edges
6. `ReceiptStore` - 32 edges
7. `NotifierState` - 28 edges
8. `HttpTrialServices` - 24 edges
9. `Incident` - 24 edges
10. `Card` - 24 edges

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
- 1-file cycle: `gateway/checklist.py -> gateway/checklist.py`

## Communities (58 total, 9 thin omitted)

### Community 0 - "NotifierState"
Cohesion: 0.07
Nodes (31): Interaction, Notifier, Protocol, NotificationConsumer, Any, AsyncClient, ApprovalButton, ApprovalController (+23 more)

### Community 1 - "ReceiptStore"
Cohesion: 0.10
Nodes (38): concurrent_futures, fastapi, fastapi_responses, AuditLog, canonical(), EventBus, Any, Path (+30 more)

### Community 2 - "6.4 Gateway (`gateway/`) [M] P0 unless marked"
Cohesion: 0.05
Nodes (40): 6.1 Chaos panel (`chaos/`) [A] P0, 6.2.1 Baselines (`baselines.py`), 6.2.2 Detector (`detector.py`), 6.2.3 Kubernetes watch (`kube_watch.py`), 6.2.4 Change journal (`journal.py`), 6.2.5 Flags (`flags.py`), 6.2 Observer (`observer/`) [M] P0, 6.3.1 Dependency graph (`graph.py`) (+32 more)

### Community 3 - "HttpTrialServices"
Cohesion: 0.08
Nodes (33): Harness, HttpTrialServices, main(), measure(), ObservationError, Any, AsyncClient, Path (+25 more)

### Community 4 - "find_culprit"
Cohesion: 0.20
Nodes (9): deepest_unhealthy(), fetch_error_traces(), find_culprit(), from_traces(), is_error(), AsyncClient, collections, CulpritTest (+1 more)

### Community 5 - "Anirudh [A]: tasks"
Cohesion: 0.22
Nodes (8): Anirudh [A]: tasks, Never cut, Phase 0: foundations, Phase 1: the spine, Phase 2: the other failures, Phase 3: UI, Phase 4: more UI, Phase 5: freeze

### Community 6 - "AGENTS.md"
Cohesion: 0.18
Nodes (10): Code comments, Commands, Commits, Communication, Dependencies, Git safety, graphify, Secrets (+2 more)

### Community 7 - "CLAUDE.md"
Cohesion: 0.18
Nodes (10): Code comments, Commands, Commits, Communication, Dependencies, Git safety, graphify, Secrets (+2 more)

### Community 8 - "10. Build plan"
Cohesion: 0.22
Nodes (9): 10. Build plan, Cut order if time runs short, Phase 0: foundations (about 2 h, everyone), Phase 1: the spine, one failure end to end (about 5 h) P0, Phase 2: the other failures and the checks (about 5 h) P0, Phase 3: trust, humans, proof (about 5 h) P1, Phase 4: wide outages and measurement (about 4 h) P1, Phase 5: freeze and polish (about 4 h) (+1 more)

### Community 9 - "main.py"
Cohesion: 0.05
Nodes (58): asyncio, Any, quarantine(), redact(), redact_value(), Any, Path, read_all() (+50 more)

### Community 10 - "checklist.py"
Cohesion: 0.08
Nodes (30): _flatten(), _h(), namespace_hash(), outside_allowed(), previous_template(), Any, rollback_patch(), spec_diff() (+22 more)

### Community 12 - "Implementation Plan: the on-call agent that has to earn its autonomy"
Cohesion: 0.29
Nodes (6): 12. Risks and fallbacks, 13. Submission checklist, 14. Command cheat sheet, 2. Repository layout, 7. End-to-end flows (acceptance scenarios), Implementation Plan: the on-call agent that has to earn its autonomy

### Community 13 - "test_brain.py"
Cohesion: 0.08
Nodes (49): DependencyGraph, AsyncClient, DiagnosisResult, DiagnosisService, Path, create_app(), FastAPI, InferenceProvider (+41 more)

### Community 14 - "Anirudh [A]: architecture of my part"
Cohesion: 0.29
Nodes (6): Anirudh [A]: architecture of my part, Flow through my parts, Hard rules my code must keep, What I need from others, What I own, What I provide to others

### Community 15 - "models.py"
Cohesion: 0.07
Nodes (46): build_bundle(), change_evidence(), collect_k8s(), k8s_evidence(), log_evidence(), memory_ratio(), metric_evidence(), Any (+38 more)

### Community 16 - "connect"
Cohesion: 0.05
Nodes (48): datetime, logging, load(), Connection, store(), bad_pods(), pod_bad(), Connection (+40 more)

### Community 17 - "On-call agent: Twaha components"
Cohesion: 0.25
Nodes (7): Benchmarks and adversarial checks, Discord notifier, Gateway mounting, Inference, On-call agent: Twaha components, Project graph, Setup and checks

### Community 18 - "Anirudh [A]: state"
Cohesion: 0.29
Nodes (6): Anirudh [A]: state, Blocked / waiting on, Done (with proof), In progress, Next, Notes for my next session

### Community 21 - "3. Environment setup"
Cohesion: 0.33
Nodes (6): 3.1 Prerequisites [A] P0, 3.2 Cluster [A] P0, 3.3 The shop [A] P0, 3.4 The buggy payment image [A] P0, 3.5 Kubeconfigs for the three identities [M] P0, 3. Environment setup

### Community 22 - "8. Testing"
Cohesion: 0.40
Nodes (5): 8.1 Unit tests [M][T] P0, 8.2 Property-based tests (`test_invariants.py`, Hypothesis) [M] P1, 8.3 Red-team suite (`tests/redteam/`) [T] P1, 8.4 Smoke test (`scripts/smoke.sh`) [A] P0, 8. Testing

### Community 23 - "test_bench_export.py"
Cohesion: 0.12
Nodes (29): argparse, display(), export_report(), markdown(), Any, Path, timing_svg(), main() (+21 more)

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

### Community 30 - "GatewayDecision"
Cohesion: 0.07
Nodes (46): call_tool(), AsyncClient, Brain, build_from_env(), Any, AsyncClient, Connection, require_env() (+38 more)

### Community 39 - "journal.py"
Cohesion: 0.08
Nodes (27): _action(), latest_change_before_onset(), match(), to_bytes(), copy, check(), author(), _configmap_changes() (+19 more)

### Community 41 - "Detector"
Cohesion: 0.18
Nodes (7): math, Detector, fetch_readings(), prom_query(), AsyncClient, det(), DetectorTest

### Community 42 - "trust.py"
Cohesion: 0.25
Nodes (13): main(), Any, Path, summarize_ledger(), check(), counts(), eligible(), lower_bound() (+5 more)

### Community 50 - "test_verify_loop.py"
Cohesion: 0.30
Nodes (12): executed(), healthy(), ledger(), Observer whose /health/now follows a script; each read moves the clock 5 s., Script, sick(), test_early_abort_pauses_undoes_resumes(), test_human_change_during_verify_hands_off_without_undo() (+4 more)

### Community 51 - "test_chaos.py"
Cohesion: 0.13
Nodes (29): bad_deploy(), kubectl(), KubectlError, create_app(), FastAPI, Kubectl, Path, diff_ops() (+21 more)

### Community 54 - "charge.js"
Cohesion: 0.11
Nodes (20): { ATTR_ERROR_TYPE }, cardValidator, charge(), { context, propagation, trace, metrics, SpanStatusCode }, { FlagdProvider }, flagProvider, logger, LOYALTY_LEVEL (+12 more)

### Community 55 - "Twaha [T]: state"
Cohesion: 0.29
Nodes (6): Blocked / waiting on, Done (with proof), In progress, Next, Notes for next session, Twaha [T]: state

### Community 58 - "Twaha [T]: tasks"
Cohesion: 0.20
Nodes (9): Evidence and next gate (2026-11-13), Never cut, Phase 0: foundations, Phase 1: the spine, Phase 2: checks, Phase 3: humans and proof, Phase 4: measurement, Phase 5: freeze (+1 more)

### Community 59 - "Muaz [M]: tasks"
Cohesion: 0.22
Nodes (8): Muaz [M]: tasks, Never cut, Phase 0: foundations, Phase 1: the spine, one failure end to end, Phase 2: the other failures and the checks, Phase 3: trust, humans, proof, Phase 4: wide outages and measurement, Phase 6: stretch (only if Phase 4 exit is met early)

### Community 64 - "Muaz [M]: architecture of my part"
Cohesion: 0.29
Nodes (6): Flow through my code, Hard rules my code must keep, Muaz [M]: architecture of my part, What I need from others, What I own, What I provide to others

### Community 65 - "Twaha [T]: architecture of my part"
Cohesion: 0.29
Nodes (6): Flow through my parts, Hard rules my code must keep, Twaha [T]: architecture of my part, What I need from others, What I own, What I provide to others

### Community 68 - "Muaz [M]: state"
Cohesion: 0.29
Nodes (6): Blocked / waiting on, Done (with proof), In progress, Muaz [M]: state, Next, Notes for my next session

### Community 70 - "Shared context (all agents read and write this)"
Cohesion: 0.29
Nodes (6): Contracts (agreed interfaces between owners), Log (append-only, newest at bottom), Open questions, Rules for agents, Shared context (all agents read and write this), VERIFY results (§3.3, Phase 0)

## Knowledge Gaps
- **174 isolated node(s):** `{ context, propagation, trace, metrics, SpanStatusCode }`, `{ ATTR_ERROR_TYPE }`, `{ v4: uuidv4 }`, `{ FlagdProvider }`, `flagProvider` (+169 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `GatewayDecision` connect `GatewayDecision` to `NotifierState`, `ReceiptStore`, `HttpTrialServices`, `main.py`, `checklist.py`, `test_brain.py`, `models.py`?**
  _High betweenness centrality (0.065) - this node is a cross-community bridge._
- **Why does `connect()` connect `connect` to `ReceiptStore`, `journal.py`, `main.py`, `trust.py`, `test_brain.py`, `GatewayDecision`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **Why does `Gateway` connect `GatewayDecision` to `ReceiptStore`, `main.py`, `checklist.py`, `trust.py`, `models.py`, `connect`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._
- **Are the 19 inferred relationships involving `GatewayDecision` (e.g. with `Harness` and `HttpTrialServices`) actually correct?**
  _`GatewayDecision` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `Gateway` (e.g. with `WriteRefused` and `ReceiptStore`) actually correct?**
  _`Gateway` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `ActionRequest` (e.g. with `DiagnosisResult` and `DiagnosisService`) actually correct?**
  _`ActionRequest` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `{ context, propagation, trace, metrics, SpanStatusCode }`, `{ ATTR_ERROR_TYPE }`, `{ v4: uuidv4 }` to the rest of the system?**
  _177 weakly-connected nodes found - possible documentation gaps or missing edges._