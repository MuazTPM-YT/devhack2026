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
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException

from brain import rules
from brain.bundle import build_bundle, collect_k8s
from brain.culprit import fetch_error_traces, find_culprit
from brain.gateway_client import call_tool
from brain.graph import DependencyGraph
from brain.llm import DiagnosisService
from schemas import config
from schemas.db import DEFAULT_PATH, connect
from schemas.models import ActionRequest, GatewayDecision, Incident

log = logging.getLogger("brain")


def require_env(*names: str) -> list[str]:
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        raise RuntimeError(f"missing required env var(s): {', '.join(missing)}")
    return [os.environ[n] for n in names]


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
        self.lock = threading.Lock()
        self.submit = submit or (lambda a: call_tool(self.gateway_url, a))

    async def publish(self, kind: str, incident_id: str | None, payload: dict) -> None:
        try:
            r = await self.http.post(f"{self.gateway_url}/events/publish", timeout=5,
                                     json={"type": kind, "incident_id": incident_id, "payload": payload})
            r.raise_for_status()
        except httpx.HTTPError as e:
            log.warning("publish %s failed: %s", kind, type(e).__name__)

    async def _get_json(self, url: str, default: Any, **params: Any) -> Any:
        try:
            r = await self.http.get(url, params=params, timeout=10)
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, ValueError) as e:
            log.warning("GET %s failed: %s", url, type(e).__name__)
            return default

    # one incident end to end; every upstream failure degrades evidence, never stops the rules
    async def handle(self, incident: Incident) -> dict:
        now = self.clock()
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
        incident = incident.model_copy(update={"culprit": culprit, "victims": victims})
        await self.publish("culprit_found", incident.id, {"culprit": culprit, "victims": victims,
                                                          "from_traces": bool(traces)})

        journal_rows = await self._get_json(f"{self.observer_url}/journal", [], since=incident.onset_at - window_s)
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
                                       self.services, self.policy, k8s["memory_ratio"], k8s["memory_limit"])
        await self.publish("rule_matched", incident.id, {"pattern": pattern, "tools": [a["tool"] for a in actions]})
        rule_action = ActionRequest.model_validate(actions[0]) if actions else None

        result = await self.diagnoser.diagnose(bundle, pattern, rule_action)
        for ev in result.events:
            await self.publish(ev["type"], ev.get("incident_id"), ev.get("payload", {}))
        action = result.action
        # the rule picks the fix; the model only adds the prediction the verifier checks
        if action and action.prediction is None and result.diagnosis and result.diagnosis.prediction:
            action = action.model_copy(update={"prediction": result.diagnosis.prediction})
        await self.publish("diagnosis_ready", incident.id, {"pattern": pattern, "culprit": culprit})

        with self.lock:
            self.conn.execute("UPDATE incidents SET culprit=?, victims_json=?, pattern=? WHERE id=?",
                              (culprit, json.dumps(victims), pattern, incident.id))
            self.conn.commit()
        record = {"incident": incident.model_dump(mode="json"), "pattern": pattern,
                  "action": action.model_dump(mode="json") if action else None,
                  "followups": actions[1:],
                  "diagnosis": result.diagnosis.model_dump(mode="json") if result.diagnosis else None,
                  "llm_error": result.error, "cached": result.cached}
        self.results[incident.id] = record
        record["gateway"] = await self.hand_over(incident, action, result.diagnosis, pattern)
        return record

    # the gateway decides from here; with nothing safe to do, wake a human ourselves
    async def hand_over(self, incident: Incident, action: ActionRequest | None, diagnosis: Any,
                        pattern: str) -> dict:
        from gateway.receipts import build_incident_card  # pure card builder, no cluster access

        if action is None:
            decision = GatewayDecision(decision="escalated", failed_step="rules", reason=f"no safe action ({pattern})")
            card = build_incident_card(incident, diagnosis, decision=decision)
            with self.lock:
                self.conn.execute("UPDATE incidents SET state='escalated' WHERE id=?", (incident.id,))
                self.conn.commit()
            await self.publish("escalated", incident.id, {"card": card.model_dump(mode="json"),
                                                          "briefing": decision.reason})
            return decision.model_dump(mode="json")
        try:
            return (await self.submit(action)).model_dump(mode="json")
        except Exception as e:  # gateway down: a human must look, the brain never acts itself
            log.error("gateway call failed: %r", e)
            decision = GatewayDecision(decision="escalated", failed_step="gateway", reason=type(e).__name__)
            card = build_incident_card(incident, diagnosis, decision=decision)
            await self.publish("escalated", incident.id, {"card": card.model_dump(mode="json"),
                                                          "briefing": "gateway unreachable"})
            return decision.model_dump(mode="json")


def build_from_env() -> Brain:
    from kubernetes import client
    from kubernetes import config as kube_config

    from brain.providers.opencode_go import OpenCodeGoAdapter

    observer, gateway, jaeger, kubeconfig = require_env("OBSERVER_URL", "GATEWAY_URL", "JAEGER_URL",
                                                        "READER_KUBECONFIG")
    http = httpx.AsyncClient()
    api = kube_config.new_client_from_config(config_file=kubeconfig)
    core, custom = client.CoreV1Api(api), client.CustomObjectsApi(api)
    services = config.load("services")["services"]
    diagnoser = DiagnosisService(OpenCodeGoAdapter.from_env(http), Path("data/llm_cache"))
    return Brain(http, observer, gateway, jaeger, diagnoser,
                 lambda svc, now: collect_k8s(core, custom, "shop", svc, now),
                 connect(DEFAULT_PATH, shared=True), services, config.load("policy"))


def create_app(brain: Brain | None = None) -> FastAPI:
    tasks: set[asyncio.Task] = set()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.brain = brain or build_from_env()
        yield
        for t in tasks:
            t.cancel()
        if brain is None:
            await app.state.brain.http.aclose()

    app = FastAPI(title="oncall brain", lifespan=lifespan)

    def _finished(task: asyncio.Task) -> None:
        tasks.discard(task)
        if not task.cancelled() and task.exception():
            log.error("incident %s failed: %r", task.get_name(), task.exception())

    # observer re-POSTs on alert grouping; ponytail: first POST wins, regrouped incidents aren't re-diagnosed
    @app.post("/incidents", status_code=202)
    async def incidents(incident: Incident) -> dict:
        b = app.state.brain
        if incident.id in b.results or any(t.get_name() == incident.id for t in tasks):
            return {"incident_id": incident.id, "status": "already_handled"}
        task = asyncio.create_task(b.handle(incident), name=incident.id)
        tasks.add(task)
        task.add_done_callback(_finished)
        return {"incident_id": incident.id, "status": "accepted"}

    @app.get("/incidents/{incident_id}")
    def get_incident(incident_id: str) -> dict:
        record = app.state.brain.results.get(incident_id)
        if record is None:
            raise HTTPException(404, "unknown or still running")
        return record

    return app


app = create_app()
