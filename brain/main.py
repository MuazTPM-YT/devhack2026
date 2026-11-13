# brain process, port 7002 (IMPLEMENTATION.md §6.3.8): incident -> culprit -> bundle -> rules -> LLM -> action.
# Never writes to the cluster. Run: uv run --locked --env-file .env uvicorn brain.main:app --host 127.0.0.1 --port 7002
import asyncio
import json
import logging
import os
import sqlite3
import threading
import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, cast

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from brain import capabilities, rules
from brain.bundle import build_bundle, collect_k8s, why_text
from brain import major, memory, runbooks
from brain.agent import AgentDiagnosisService, model_from_env, was_tried
from brain.budget import BudgetedModel
from brain.coordinator import Coordinator, ModeMismatch
from brain.delegation import Delegation
from brain.evidence import EvidenceCache
from brain.culprit import dependency_change, fetch_error_traces, find_culprit
from brain.gateway_client import call_tool
from brain.graph import DependencyGraph
from brain.llm import DiagnosisService
from brain.redact import redact
from gateway.cards import started_by
from brain.tools import KubeReader, ToolBox
from schemas import auth, config, migrations
from schemas.config import require_env
from schemas.db import DEFAULT_PATH, connect
from schemas.models import ActionRequest, GatewayDecision, Incident, Pattern
from schemas.orchestration import OrchestrationPolicy, SignalBatch, load_policy
from schemas.workspace import Workspace
from schemas import logs

logs.setup()

log = logging.getLogger("brain")


class Brain:
    def __init__(self, http: httpx.AsyncClient, observer_url: str, gateway_url: str, jaeger_url: str,
                 diagnoser: Any, k8s: Callable[[str, float], dict], conn: sqlite3.Connection,
                 services: dict, policy: dict, clock: Callable[[], float] = time.time,
                 submit: Callable[[ActionRequest], Awaitable[GatewayDecision]] | None = None):
        self.http, self.observer_url, self.gateway_url, self.jaeger_url = http, observer_url, gateway_url, jaeger_url
        self.graph = DependencyGraph(http, jaeger_url, clock=clock)
        self.diagnoser, self.k8s, self.conn = diagnoser, k8s, conn
        self.services, self.policy, self.clock = services, policy, clock
        self.results: dict[str, dict] = {}
        self.majors: set[str] = set()  # incidents already analysed as major (at open or on regroup)
        self.flag_map: dict[str, str] = {}  # config/services.yaml `flags:`, set by build_from_env
        self.runbooks: list[dict] = []  # config/runbooks.yaml, set by build_from_env
        self.guides: dict[str, dict] = {}  # incident id -> runbook + seen-before for the escalation payload
        self.tried: dict[str, list[dict]] = {}  # incident id -> fixes that failed and were undone (retry context)
        # BRAIN_MODE=agent, set by build_from_env: tool-using diagnosis and what its tools read
        self.agent: AgentDiagnosisService | None = None
        self.prom_url = ""
        self.queries: dict[str, str] = {}
        self.kube: Any = None  # brain.tools.KubeReader
        self.lock = threading.Lock()
        self.submit = submit or (lambda a: call_tool(self.gateway_url, a))
        # orchestration (config/orchestration.yaml); disabled = observer POSTs /incidents as before
        self.orch = OrchestrationPolicy()
        self.coordinator: Coordinator | None = None
        self.evidence_cache: EvidenceCache | None = None

    async def publish(self, kind: str, incident_id: str | None, payload: dict) -> None:
        if self.coordinator is not None and self.orch.mode == "coordinated":
            await self.coordinator.emit(kind, incident_id, payload)  # durable: outbox, then the bus
            return
        try:
            r = await self.http.post(f"{self.gateway_url}/events/publish", timeout=5, headers=auth.headers(),
                                     json={"type": kind, "incident_id": incident_id, "payload": payload})
            r.raise_for_status()
        except httpx.HTTPError as e:
            log.warning("publish %s failed: %s", kind, type(e).__name__)

    async def _get_json(self, url: str, default: Any, **params: Any) -> Any:
        try:
            r = await self.http.get(url, params=params, timeout=10, headers=auth.headers())  # /journal needs it
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, ValueError) as e:
            log.warning("GET %s failed: %s", url, type(e).__name__)
            return default

    # one incident end to end; every upstream failure degrades evidence, never stops the rules.
    # still_current: coordinated mode's scope check right before hand-over; timeout_s: what is left of a
    # persisted investigation deadline. tried: a retry after the gateway undid earlier fixes; never sent again
    async def handle(self, incident: Incident, still_current: Callable[[], bool] | None = None,
                     timeout_s: float | None = None, run_id: str | None = None,
                     tried: list[dict] | None = None) -> dict:
        now = self.clock()
        tried = tried or []
        self.tried[incident.id] = tried
        window_s = self.policy["change_window_minutes"] * 60
        health = await self._get_json(f"{self.observer_url}/health/now", {"ts": now, "services": {}})
        first_breach = {s: v["first_breach_ts"] for s, v in health["services"].items()
                        if v.get("first_breach_ts") is not None}
        try:
            edges = await self.graph.get()
        except (httpx.HTTPError, KeyError, ValueError) as e:
            log.warning("dependency graph failed: %s", type(e).__name__)
            edges = []
        try:
            traces = await fetch_error_traces(self.http, self.jaeger_url, incident.unhealthy, now)
        except (httpx.HTTPError, KeyError, ValueError) as e:
            log.warning("trace fetch failed: %s", type(e).__name__)
            traces = []
        culprit, victims = find_culprit(traces, incident.unhealthy, edges, first_breach)
        journal_rows = await self._get_json(f"{self.observer_url}/journal", [], since=incident.onset_at - window_s)
        is_major = major.is_major(incident.unhealthy, first_breach, len(self.services), self.policy)
        if is_major:
            self.majors.add(incident.id)
            # many services at once: the ranked shared cause beats the per-trace culprit
            ranked = major.analyse(incident.unhealthy, edges, first_breach, journal_rows, incident.onset_at, window_s,
                                   self.flag_map)
            if ranked:
                culprit = ranked[0]["target"]
                victims = sorted(set(incident.unhealthy) - {culprit})
            await self.publish("major_incident", incident.id, {"ranked": ranked})
        moved_from = None
        if not is_major and culprit:
            dep = dependency_change(journal_rows, culprit, edges, self.services, incident.onset_at, window_s,
                                    self.flag_map, incident.unhealthy)
            if dep:
                moved_from, culprit = culprit, dep[1]
                victims = sorted((set(victims) | {moved_from}) - {culprit})
        incident = incident.model_copy(update={"culprit": culprit, "victims": victims, "major": is_major})
        await self.publish("culprit_found", incident.id, {"culprit": culprit, "victims": victims,
                                                          "from_traces": bool(traces), "moved_from": moved_from})

        k8s: dict = {"events": [], "logs": [], "memory_ratio": None, "memory_limit": None}
        if culprit:
            try:
                k8s = await asyncio.to_thread(self.k8s, culprit, now)
            except Exception as e:  # reader API down or RBAC: keep going on metrics + traces
                log.warning("k8s read failed: %s", type(e).__name__)
        bundle = build_bundle(incident, journal_rows, health, traces, k8s, edges, window_s, now)
        await self.publish("bundle_built", incident.id, {k: len(getattr(bundle, k)) for k in
                                                         ("changes", "metrics", "traces", "events", "logs")})

        pattern, actions = rules.match(incident.model_dump(), journal_rows, [e.model_dump() for e in bundle.events],
                                       self.services, self.policy, k8s["memory_ratio"], k8s["memory_limit"],
                                       self.flag_map)
        if tried and actions and was_tried(actions[0], tried):
            actions = []  # the rule's pick already failed: it has nothing new, nor do its follow-ups
        rule_action = ActionRequest.model_validate(actions[0]) if actions else None
        # everything else the evidence supports; the agent may take one of these instead of the rule's pick
        _, cands = rules.candidates(incident.model_dump(), journal_rows, [e.model_dump() for e in bundle.events],
                                    self.services, self.policy, k8s["memory_ratio"], k8s["memory_limit"],
                                    self.flag_map)
        if tried:  # failed fixes leave the list; ids renumbered so c1 is the first fix left
            left = [c for c in cands if not was_tried(c["action"], tried)]
            cands = [{**c, "id": f"c{i + 1}"} for i, c in enumerate(left)]
        # company runbooks + verified past incidents: the model reads them, they never change the rule's fix
        fix_entry = next((j for j in journal_rows if rule_action and j["id"] == rule_action.journal_entry), None)
        # redacted first: a runbook can match "[REDACTED]" (secret in logs) and never sees the secret itself
        evidence_text = redact(" ".join(e.summary for group in (bundle.changes, bundle.events, bundle.logs,
                                                                bundle.traces) for e in group))
        matched = runbooks.match(self.runbooks, pattern, culprit, rule_action.tool if rule_action else None,
                                 fix_entry["kind"] if fix_entry else None, evidence_text)
        with self.lock:
            past = memory.similar(self.conn, incident.id, culprit, pattern)
        # "Started by" on Discord: the change the rule's fix reverts, else the newest one on the culprit
        first = fix_entry or (rules.latest_change_before_onset(journal_rows, culprit, incident.onset_at, window_s,
                                                                self.flag_map) if culprit else None)
        self.guides[incident.id] = {"runbook": runbooks.brief(matched[0]) if matched else None,
                                    "seen_before": memory.summary(past),
                                    "started": started_by(first, incident.model_dump())}
        await self.publish("rule_matched", incident.id, {"pattern": pattern, "tools": [a["tool"] for a in actions],
                                                         "runbooks": [rb["id"] for rb in matched],
                                                         "similar_before": len(past),
                                                         "candidates": [{"id": c["id"], "basis": c["basis"],
                                                                         "tool": c["action"]["tool"],
                                                                         "target": c["action"]["target"]}
                                                                        for c in cands]})

        guide = {"runbooks": [runbooks.brief(rb) for rb in matched[:3]], "past_incidents": past}
        if self.coordinator is not None and self.orch.mode == "coordinated":
            with self.lock:
                if lessons := memory.experience(self.conn, pattern, culprit):
                    guide["experience"] = lessons
        if self.agent is not None:  # agent mode: the model reads telemetry through tools, not the bundle
            box = ToolBox(incident, now, self.http, self.observer_url, self.prom_url, self.jaeger_url, self.graph,
                          self.kube, self.conn, self.lock, list(self.services), self.queries, self.publish,
                          edges=list(edges), cache=self.evidence_cache,
                          workspace=self.coordinator.ws if self.coordinator else None, run_id=run_id)
            model = None
            if self.coordinator is not None and self.evidence_cache is not None:  # coordinated: durable budget
                model = BudgetedModel(self.agent.model, self.coordinator.ws, incident.id, run_id or incident.id,
                                      "commander", publish=self.publish, clock=self.clock)
                if self.coordinator.delegation is not None:
                    scope = sorted({*incident.unhealthy, *([culprit] if culprit else [])})
                    box.orch = await self.coordinator.delegation.context(incident.id, cands, scope)
            result = await self.agent.diagnose(box, cast(Pattern, pattern), rule_action, guide, cands,
                                               capabilities.available(self.policy, self.services), timeout_s=timeout_s,
                                               model=model, tried=tried)
        else:
            result = await self.diagnoser.diagnose(bundle, pattern, rule_action, guide)
        for ev in result.events:
            await self.publish(ev["type"], ev.get("incident_id"), ev.get("payload", {}))
        action = result.action
        if action is not None and was_tried(action.model_dump(), tried):
            action = None  # belt and braces: the validator refuses it, a fallback must not resend it either
        # the prediction the verifier checks is the model's, whoever picked the fix
        if action and action.prediction is None and result.diagnosis and result.diagnosis.prediction:
            action = action.model_copy(update={"prediction": result.diagnosis.prediction})
        diag = result.diagnosis
        declined = diag.reason or "no reason given" if diag and diag.decision == "decline" else None

        def brief(a: ActionRequest | None) -> dict | None:
            return {"tool": a.tool, "target": a.target} if a else None

        # who chose what, and why: the UI shows the choice next to what the rule would have done
        await self.publish("diagnosis_ready", incident.id, {
            "pattern": pattern, "culprit": culprit, "decision": diag.decision if diag else None,
            "origin": action.origin if action else None, "chosen": brief(action), "rule_choice": brief(rule_action),
            "reason": diag.reason if diag else None, "alternative": diag.alternative if diag else None})

        causes = result.diagnosis.causes if result.diagnosis else []
        llm_why = " ".join(causes[0].explanation.split())[:300] if causes else None
        with self.lock:
            # MAX: a regroup may already have marked it major while we were diagnosing
            self.conn.execute("UPDATE incidents SET culprit=?, victims_json=?, pattern=?, major=MAX(major, ?), "
                              "llm_why=? WHERE id=?",
                              (culprit, json.dumps(victims), pattern, int(is_major), llm_why, incident.id))
            self.conn.commit()
        record: dict[str, Any] = {"incident": incident.model_dump(mode="json"), "pattern": pattern,
                  "attempt": len(tried) + 1,
                  "action": action.model_dump(mode="json") if action else None,
                  "followups": actions[1:],
                  "diagnosis": result.diagnosis.model_dump(mode="json") if result.diagnosis else None,
                  "llm_error": result.error, "cached": result.cached}
        self.results[incident.id] = record
        entry = next((j for j in journal_rows if action and j["id"] == action.journal_entry), None)
        why = why_text(entry, incident.onset_at)
        if still_current is not None and not still_current():  # scope moved while we looked: replan, never send
            record["superseded"] = True
            return record
        record["gateway"] = await self.hand_over(incident, action, result.diagnosis, pattern, why, health,
                                                 declined=declined, rule_action=rule_action)
        # resource case: restart first, then ask for more memory (never automatic; §6.3.6 special case 1).
        # Only behind the rule's own pick: the follow-ups belong to it, not to a fix the model chose instead
        if (action is not None and action.origin == "rule"
                and record["gateway"].get("decision") in ("executed", "awaiting_approval")):
            record["followups_sent"] = []
            for extra in actions[1:]:
                follow = ActionRequest.model_validate({**extra, "prediction": None})
                record["followups_sent"].append(await self.hand_over(incident, follow, result.diagnosis, pattern, why,
                                                                      health))
        return record

    # alert grouping grew an already-diagnosed incident (§6.3.3 "within 2 minutes"): if it is major now,
    # publish the ranked shared cause and mark it major so the gateway's major rules govern any pending
    # approval. Never submits a second action: one may already be in flight.
    async def regroup(self, incident: Incident) -> list[dict] | None:
        if incident.id in self.majors:
            return None
        health = await self._get_json(f"{self.observer_url}/health/now", {"ts": self.clock(), "services": {}})
        first_breach = {s: v["first_breach_ts"] for s, v in health["services"].items()
                        if v.get("first_breach_ts") is not None}
        if not major.is_major(incident.unhealthy, first_breach, len(self.services), self.policy):
            return None
        self.majors.add(incident.id)
        try:
            edges = await self.graph.get()
        except (httpx.HTTPError, KeyError, ValueError):
            edges = []
        window_s = self.policy["change_window_minutes"] * 60
        journal_rows = await self._get_json(f"{self.observer_url}/journal", [], since=incident.onset_at - window_s)
        ranked = major.analyse(incident.unhealthy, edges, first_breach, journal_rows, incident.onset_at, window_s,
                                   self.flag_map)
        with self.lock:
            self.conn.execute("UPDATE incidents SET major=1 WHERE id=?", (incident.id,))
            if ranked:
                self.conn.execute("UPDATE incidents SET culprit=? WHERE id=?", (ranked[0]["target"], incident.id))
            self.conn.commit()
        await self.publish("major_incident", incident.id, {"ranked": ranked, "regrouped": True})
        return ranked

    # a crash must still end the incident: without a terminal event the observer keeps it open and opens
    # no other incident, ever
    async def handle_safely(self, incident: Incident, **kw: Any) -> dict:
        try:
            return await self.handle(incident, **kw)
        except Exception as e:
            log.error("incident %s failed in the brain: %r", incident.id, e)
            decision = GatewayDecision(decision="escalated", failed_step="brain", reason=type(e).__name__)
            record = {"incident": incident.model_dump(mode="json"), "error": repr(e)}
            self.results[incident.id] = record
            try:
                record["gateway"] = await self.escalate(incident, None, decision,
                                                        f"brain failed ({type(e).__name__}); look by hand", None)
            except Exception as again:  # bus down too: logged, the observer's max age is the last net
                log.error("incident %s: escalation failed too: %r", incident.id, again)
            return record

    # the gateway decides from here; with nothing safe to do, wake a human ourselves
    # declined: the agent's own reason for not acting; a human then gets it next to the rule's suggestion
    async def hand_over(self, incident: Incident, action: ActionRequest | None, diagnosis: Any,
                        pattern: str, why: str | None = None, health: dict | None = None,
                        declined: str | None = None, rule_action: ActionRequest | None = None) -> dict:
        if action is None:
            reason, step = f"no safe action ({pattern})", "rules"
            if tried := self.tried.get(incident.id):
                reason = f"no untried safe fix left after {len(tried)} failed fix{'es' if len(tried) > 1 else ''}"
            if declined:
                hint = f" The rule suggested {rule_action.tool} on {rule_action.target}." if rule_action else ""
                reason, step = f"agent declined to act: {declined}{hint}", "agent"
            decision = GatewayDecision(decision="escalated", failed_step=step, reason=reason)
            return await self.escalate(incident, diagnosis, decision, decision.reason or "", why, health)
        try:
            decision = await self.submit(action)
        except Exception as e:  # gateway down: a human must look, the brain never acts itself
            log.error("gateway call failed: %r", e)
            decision = GatewayDecision(decision="escalated", failed_step="gateway", reason=type(e).__name__)
            return await self.escalate(incident, diagnosis, decision, "gateway unreachable", why, health, action)
        if decision.decision == "refused" and decision.failed_step == "schema":
            # refused before the checklist ran (MCP or schema): no one else ends the incident, so wake a human
            log.error("gateway refused %s at schema: %s", action.tool, decision.reason)
            return await self.escalate(incident, diagnosis, decision, f"action refused: {decision.reason}", why,
                                       health, action)
        return decision.model_dump(mode="json")

    async def escalate(self, incident: Incident, diagnosis: Any, decision: GatewayDecision, briefing: str,
                       why: str | None, health: dict | None = None, action: ActionRequest | None = None) -> dict:
        from gateway.cards import build_incident_card, source  # pure card builder, no cluster access

        retry = {"tries": self.tried.get(incident.id, []), "max": 1 + int(self.policy["budgets"]["max_retries"])}
        card = build_incident_card(incident, diagnosis, decision=decision.model_copy(update={"decision": "escalated"}),
                                   why=why, health=health, proposal=action, retry=retry)
        step = {"rules": "diagnosis", "agent": "diagnosis", "brain": "crash guard"}.get(decision.failed_step or "",
                                                                                      "gateway call")
        with self.lock:
            self.conn.execute("UPDATE incidents SET state='escalated' WHERE id=?", (incident.id,))
            self.conn.commit()
        await self.publish("escalated", incident.id, {"card": card.model_dump(mode="json"), "briefing": briefing,
                                                      **self.guides.get(incident.id, {}),
                                                      "source": source("brain", step)})
        return decision.model_dump(mode="json")


class RetryRequest(BaseModel):
    incident: Incident
    attempt: int = Field(ge=2)
    max_attempts: int = Field(ge=2)
    failed: list[dict[str, Any]] = Field(min_length=1, max_length=10)


def build_from_env() -> Brain:
    from kubernetes import client
    from kubernetes import config as kube_config

    from brain.providers.opencode_go import OpenCodeGoAdapter

    # agent: the model reads through tools and chooses among the rule's candidates (the gateway still decides).
    # advise: same tools, the rule's fix wins. bundle: one call over a prebuilt bundle, the rule's fix wins.
    mode = os.environ.get("BRAIN_MODE", "agent")
    if mode not in ("agent", "advise", "bundle"):
        raise RuntimeError(f"BRAIN_MODE must be agent, advise or bundle, got {mode!r}")
    observer, gateway, jaeger, kubeconfig = require_env("OBSERVER_URL", "GATEWAY_URL", "JAEGER_URL",
                                                        "READER_KUBECONFIG")
    prom = require_env("PROMETHEUS_URL")[0] if mode != "bundle" else ""
    http = httpx.AsyncClient()
    api = kube_config.new_client_from_config(config_file=kubeconfig)
    core, custom = client.CoreV1Api(api), client.CustomObjectsApi(api)
    services_cfg = config.load("services")
    services = services_cfg["services"]
    diagnoser = DiagnosisService(OpenCodeGoAdapter.from_env(http), Path("data/llm_cache"))
    brain = Brain(http, observer, gateway, jaeger, diagnoser,
                  lambda svc, now: collect_k8s(core, custom, "shop", svc, now),
                  connect(DEFAULT_PATH, shared=True), services, config.load("policy"))
    brain.flag_map = services_cfg.get("flags") or {}
    brain.runbooks = runbooks.load()
    brain.orch = load_policy()
    coordinated = brain.orch.mode == "coordinated"
    if mode != "bundle":
        brain.agent = AgentDiagnosisService(model_from_env(http, max_retries=0 if coordinated else None),
                                            choose=mode == "agent",
                                            delegation=brain.orch.delegation_enabled and mode == "agent")
        brain.prom_url, brain.queries, brain.kube = prom, config.load("queries"), KubeReader(core, custom, "shop")
    if brain.orch.mode != "disabled":
        wconn = connect(DEFAULT_PATH, shared=True)  # own connection: the workspace runs its own transactions
        migrations.require(wconn)
        workspace = Workspace(wconn, brain.orch)
        brain.coordinator = Coordinator(brain, workspace, brain.orch)
        if coordinated:
            brain.evidence_cache = EvidenceCache(workspace)
            brain.submit = brain.coordinator.submit  # fixes go as durable intents, not legacy MCP calls
            # specialists only for the tool-using agent that chooses the fix (handoff §7.3)
            if brain.orch.delegation_enabled and brain.agent is not None and brain.agent.choose:
                brain.coordinator.delegation = Delegation(workspace, brain.orch, brain.agent.model, brain.publish,
                                                          owner=brain.coordinator.owner)
    return brain


def create_app(brain: Brain | None = None) -> FastAPI:
    tasks: set[asyncio.Task] = set()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        auth.agent_start()  # fail at start, not on the first incident
        app.state.brain = brain or build_from_env()
        coordinator = getattr(app.state.brain, "coordinator", None)
        if coordinator is not None and coordinator.policy.mode == "coordinated":
            await coordinator.start()  # lease + restart recovery before taking new signals
            if brain is None:  # tests drive the loops by hand
                tasks.update({asyncio.create_task(coordinator.run(), name="coordinator"),
                              asyncio.create_task(coordinator.follow_terminal_events(), name="terminal-events")})
        yield
        for t in tasks:
            t.cancel()
        if coordinator is not None:
            coordinator.stop()
        if brain is None:
            await app.state.brain.http.aclose()

    app = FastAPI(title="oncall brain", lifespan=lifespan)
    app.add_middleware(auth.TokenGuard)

    def _finished(task: asyncio.Task) -> None:
        tasks.discard(task)
        if not task.cancelled() and task.exception():
            log.error("incident %s failed: %r", task.get_name(), task.exception())

    # observer re-POSTs on alert grouping; ponytail: first POST wins, regrouped incidents aren't re-diagnosed
    @app.post("/incidents", status_code=202)
    async def incidents(incident: Incident) -> dict:
        b = app.state.brain
        if b.orch.mode == "coordinated":  # two owners for one fault is worse than a loud refusal
            log.error("legacy incident %s refused: brain is in coordinated mode, observer is not", incident.id)
            raise HTTPException(409, "brain is in coordinated mode: observer must send /signals")
        if incident.id in b.results or any(t.get_name() == incident.id for t in tasks):
            # a re-POST is alert grouping: re-check for a major incident, never diagnose twice
            regroup = asyncio.create_task(b.regroup(incident), name=f"{incident.id}:regroup")
            tasks.add(regroup)
            regroup.add_done_callback(_finished)
            return {"incident_id": incident.id, "status": "already_handled"}
        task = asyncio.create_task(b.handle_safely(incident), name=incident.id)
        tasks.add(task)
        task.add_done_callback(_finished)
        return {"incident_id": incident.id, "status": "accepted"}

    # gateway, after it undid a failed fix (§6.4.11): diagnose again with the failed fixes as context.
    # Agent mode only: in advise and bundle mode no model reads the context, and the rule would resend its pick
    @app.post("/incidents/{incident_id}/retry", status_code=202)
    async def retry(incident_id: str, body: RetryRequest) -> dict:
        b = app.state.brain
        if body.incident.id != incident_id:
            raise HTTPException(422, "incident id does not match the path")
        if b.agent is None or not b.agent.choose:
            raise HTTPException(409, "retries need BRAIN_MODE=agent")
        if b.coordinator is not None:  # coordinated runs own their incidents; a side door would bypass them
            raise HTTPException(409, "retries run in the single-agent path; orchestration is on")
        if any(t.get_name() == incident_id and not t.done() for t in tasks):
            raise HTTPException(409, "this incident is still being diagnosed")
        # the brain's own copy keeps the full unhealthy list; the gateway only knows culprit + victims
        known = (b.results.get(incident_id) or {}).get("incident")
        incident = Incident.model_validate(known) if known else body.incident
        task = asyncio.create_task(b.handle_safely(incident, tried=body.failed), name=incident_id)
        tasks.add(task)
        task.add_done_callback(_finished)
        log.info("incident %s: retry %s of %s after %s failed fix(es)", incident_id, body.attempt,
                 body.max_attempts, len(body.failed))
        return {"incident_id": incident_id, "status": "accepted", "attempt": body.attempt}

    # observer episodes (orchestration shadow/coordinated); a redelivery returns the stored acknowledgement
    @app.post("/signals")
    async def signals(batch: SignalBatch) -> dict:
        coordinator = app.state.brain.coordinator
        if coordinator is None:
            log.error("signals %s refused: orchestration is disabled in the brain", batch.delivery_id)
            raise HTTPException(409, "orchestration disabled in the brain: observer must POST /incidents")
        try:
            return (await coordinator.on_signals(batch)).model_dump(mode="json")
        except ModeMismatch as e:
            log.error("signals %s refused: %s", batch.delivery_id, e)
            raise HTTPException(409, str(e)) from None

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    @app.get("/incidents/{incident_id}")
    def get_incident(incident_id: str) -> dict:
        record = app.state.brain.results.get(incident_id)
        if record is None:
            raise HTTPException(404, "unknown or still running")
        return record

    return app


app = create_app()
