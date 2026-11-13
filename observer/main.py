# observer process, port 7001 (IMPLEMENTATION.md §6.2): detector loop, kube watch, /health/now, /journal.
# Run: uv run --env-file .env uvicorn observer.main:app --host 127.0.0.1 --port 7001
import asyncio
import json
import logging
import os
import sqlite3
import threading
import time
from collections.abc import Callable
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException

from gateway.client import read_events
from observer import baselines, journal
from observer.detector import Detector, fetch_readings
from observer.kube_watch import Tracker, run_watch
from schemas import auth, config
from schemas.db import DEFAULT_PATH, connect
from gateway.receipts import build_incident_card, source, started_by
from schemas.models import GatewayDecision, Incident
from schemas import logs

logs.setup()

log = logging.getLogger("observer")
TERMINAL = {"incident_resolved", "escalated", "handed_off"}


def require_env(*names: str) -> list[str]:
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        raise RuntimeError(f"missing required env var(s): {', '.join(missing)}")
    return [os.environ[n] for n in names]


class Observer:
    def __init__(self, conn: sqlite3.Connection, tracker: Tracker, http: httpx.AsyncClient, prom_url: str,
                 brain_url: str, gateway_url: str, policy: dict, queries: dict, services: list[str],
                 clock: Callable[[], float] = time.time):
        d = policy["detection"]
        self.detector = Detector(d["error_ratio_threshold"], d["latency_multiplier"], d["sustain_seconds"],
                                 policy["major_incident"]["within_seconds"], d["latency_floor_ms"])
        self.poll_s = d["poll_seconds"]
        self.max_age_s = d["incident_max_age_seconds"]
        self.handover_s = d["handover_seconds"]
        self.conn, self.tracker, self.http, self.clock = conn, tracker, http, clock
        self.prom_url, self.brain_url, self.gateway_url = prom_url, brain_url, gateway_url
        self.queries, self.services = queries, services
        with tracker.lock:
            self.baselines = baselines.load(conn)
        self.health: dict | None = None
        self.undelivered: set[str] = set()
        self.detector.incident = self.open_incident(clock())

    # a restart forgot the open incident and opened a second one for the same fault (e2e: two approval pages).
    # Take back the newest unfinished one younger than the max age; the event replay from seq 0 still closes it.
    # ponytail: unhealthy = culprit + victims we watch (the DB keeps no list); empty before the brain answered
    def open_incident(self, now: float) -> dict | None:
        with self.tracker.lock:
            r = self.conn.execute("SELECT * FROM incidents WHERE state NOT IN ('resolved', 'escalated', 'handed_off')"
                                  " AND opened_at >= ? ORDER BY opened_at DESC LIMIT 1",
                                  (now - self.max_age_s,)).fetchone()
        if r is None:
            return None
        named = [r["culprit"], *json.loads(r["victims_json"] or "[]")]
        log.info("taking back open incident %s after a restart", r["id"])
        return {"id": r["id"], "opened_at": r["opened_at"], "onset_at": r["onset_at"],
                "unhealthy": sorted({s for s in named if s in self.services}), "culprit": None, "victims": [],
                "major": bool(r["major"]), "severity": float(r["severity_at_open"] or 0)}

    async def readings(self) -> dict:
        return await fetch_readings(self.http, self.prom_url, self.queries, self.services)

    # one poll; Prometheus down -> keep last health, flagged, and don't feed the detector blanks
    async def step(self) -> tuple | None:
        now = self.clock()
        try:
            readings = await self.readings()
        except (httpx.HTTPError, KeyError, ValueError) as e:
            log.warning("prometheus query failed: %s", type(e).__name__)
            self.health = {**(self.health or {"severity": 0, "services": {}}), "ts": now, "prometheus_ok": False}
            return None
        # answered but no span metrics for anyone: the pipeline is down, not every service healthy
        if readings and all(r["err_ratio"] is None and r["p95_ms"] is None for r in readings.values()):
            log.warning("prometheus has no span metrics for any service; keeping last health")
            self.health = {**(self.health or {"severity": 0, "services": {}}), "ts": now, "prometheus_ok": False}
            return None
        await self.expire_stuck_incident(now)
        health, event = self.detector.tick(now, readings, self.baselines, self.tracker.bad_pods(now))
        self.health = {**health, "prometheus_ok": True, "last_ok_ts": now}
        if event:
            await self.announce(*event)
        elif self.undelivered and self.detector.incident:
            await self.announce("incident_opened", self.detector.incident, retry=True)
        return event

    # record + tell the bus and the brain; neither being down stops detection, and an incident the brain
    # never got is re-sent every poll (else it stays open and blocks every later incident)
    async def announce(self, kind: str, incident: dict, retry: bool = False) -> None:
        body = Incident.model_validate(incident).model_dump(mode="json")
        if kind == "incident_opened" and not retry:
            with self.tracker.lock:
                self.conn.execute("INSERT OR IGNORE INTO incidents (id, opened_at, onset_at, state, severity_at_open)"
                                  " VALUES (?, ?, ?, 'open', ?)",
                                  (body["id"], body["opened_at"], body["onset_at"], body["severity"]))
                self.conn.commit()
        targets = self.undelivered if retry else {"bus", "brain"}
        urls = {"bus": (f"{self.gateway_url}/events/publish", {"type": kind, "incident_id": body["id"], "payload": body}),
                "brain": (f"{self.brain_url}/incidents", body)}
        failed = set()
        for name in [n for n in ("bus", "brain") if n in targets]:  # bus first, as before
            url, payload = urls[name]
            try:
                (await self.http.post(url, json=payload, timeout=5, headers=auth.headers())).raise_for_status()
            except httpx.HTTPError as e:
                failed.add(name)
                if not retry:
                    log.warning("POST %s failed: %s; will retry each poll", url, type(e).__name__)
        self.undelivered = failed

    # last safety net: an incident with no terminal event blocks every later incident, so after
    # incident_max_age_seconds close it here and wake a human. One the brain never handed over (DB state
    # still 'open': brain crashed mid-diagnosis) gets handover_seconds, not the whole max age
    async def expire_stuck_incident(self, now: float) -> None:
        inc = self.detector.incident
        if inc is None or now - inc["opened_at"] < min(self.max_age_s, self.handover_s):
            return
        with self.tracker.lock:
            r = self.conn.execute("SELECT state FROM incidents WHERE id=?", (inc["id"],)).fetchone()
        never_handed = r is not None and r["state"] == "open"
        age = now - inc["opened_at"]
        if age < self.max_age_s and not never_handed:
            return
        reason = (f"the brain never handed this incident to the gateway within {age:.0f} s; it may have crashed, "
                  "look by hand") if age < self.max_age_s else \
            f"no outcome {age:.0f} s after opening; the agent lost track, look by hand"
        log.error("incident %s: %s", inc["id"], reason)
        self.detector.close_incident()
        self.undelivered = set()
        with self.tracker.lock:
            self.conn.execute("UPDATE incidents SET state='escalated' WHERE id=? AND state NOT IN "
                              "('resolved', 'escalated', 'handed_off')", (inc["id"],))
            self.conn.commit()
        card = build_incident_card(Incident.model_validate(inc), health=self.health,
                                   decision=GatewayDecision(decision="escalated", failed_step="observer", reason=reason))
        try:
            (await self.http.post(f"{self.gateway_url}/events/publish", timeout=5, headers=auth.headers(), json={
                "type": "escalated", "incident_id": inc["id"],
                "payload": {"card": card.model_dump(mode="json"), "briefing": reason,
                            "source": source("observer", "stuck-incident check"),
                            "started": started_by(None, inc)}})).raise_for_status()
        except httpx.HTTPError as e:
            log.error("incident %s: escalation publish failed: %s", inc["id"], type(e).__name__)

    # one bad poll (locked DB, odd API object) must not end detection for good
    async def run(self) -> None:
        while True:
            try:
                await self.step()
            except Exception as e:
                log.error("detector poll failed: %r; next poll in %s s", e, self.poll_s)
            await asyncio.sleep(self.poll_s)

    # close our open incident when the gateway reports it finished
    async def follow_terminal_events(self) -> None:
        after = 0
        down_since: float | None = None
        while True:
            try:
                async for envelope in read_events(self.http, self.gateway_url, after):
                    after = envelope["seq"]
                    event = envelope["event"]
                    inc = self.detector.incident
                    if event["type"] in TERMINAL and inc and event.get("incident_id") == inc["id"]:
                        self.detector.close_incident()
                down_since = None
            except Exception as e:  # any error, else incidents stop closing for good
                if down_since is None:  # once per outage, not every 2 s
                    log.warning("event stream failed: %s; retrying every 2 s", type(e).__name__)
                    down_since = self.clock()
            await asyncio.sleep(2)

    async def refresh_baselines(self, seconds: float = 600, every: float = 5) -> None:
        samples = []
        for _ in range(int(seconds / every)):
            try:
                samples.append(await self.readings())
            except (httpx.HTTPError, KeyError, ValueError):
                pass
            await asyncio.sleep(every)
        values = baselines.medians(samples)
        with self.tracker.lock:
            baselines.store(self.conn, values, self.clock())
            self.baselines = baselines.load(self.conn)


def build_from_env() -> tuple[Observer, list[threading.Thread], threading.Event]:
    from kubernetes import client
    from kubernetes import config as kube_config

    prom, kubeconfig, brain, gateway = require_env("PROMETHEUS_URL", "READER_KUBECONFIG", "BRAIN_URL", "GATEWAY_URL")
    auth.agent_start()  # brain and gateway refuse our POSTs without it; fail at start
    policy, queries, services = config.load("policy"), config.load("queries"), config.load("services")
    conn = connect(DEFAULT_PATH, shared=True)
    tracker = Tracker(conn, services["flag_config"]["configmap"])
    api = kube_config.new_client_from_config(config_file=kubeconfig)
    apps, core = client.AppsV1Api(api), client.CoreV1Api(api)
    stop = threading.Event()
    threads = [threading.Thread(target=run_watch, args=(fn, kind, tracker, "shop", stop), daemon=True)
               for fn, kind in ((apps.list_namespaced_deployment, "deployment"),
                                (core.list_namespaced_config_map, "configmap"),
                                (core.list_namespaced_pod, "pod"))]
    observer = Observer(conn, tracker, httpx.AsyncClient(), prom, brain, gateway, policy, queries,
                        list(services["services"]))
    return observer, threads, stop


def create_app(observer: Observer | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if observer is not None:  # tests drive it by hand
            app.state.observer = observer
            yield
            return
        obs, threads, stop = build_from_env()
        app.state.observer = obs
        for t in threads:
            t.start()
        tasks = [asyncio.create_task(obs.run()), asyncio.create_task(obs.follow_terminal_events())]
        if not obs.baselines:
            tasks.append(asyncio.create_task(obs.refresh_baselines()))
        yield
        stop.set()
        for task in tasks:
            task.cancel()
        await obs.http.aclose()

    app = FastAPI(title="oncall observer", lifespan=lifespan)
    # writes: a baselines refresh mid-incident would skew latency checks; /journal shows env values
    app.add_middleware(auth.TokenGuard, private_reads=frozenset({"/journal"}))

    @app.get("/health/now")
    def health_now() -> dict:
        health = app.state.observer.health
        if health is None:
            raise HTTPException(503, "no reading yet")
        return health

    @app.get("/journal")
    def get_journal(since: float = 0, object: str | None = None) -> list[dict]:
        obs = app.state.observer
        with obs.tracker.lock:
            return journal.read(obs.conn, since, object)

    background: set[asyncio.Task] = set()

    @app.post("/baselines/refresh", status_code=202)
    async def refresh() -> dict:
        task = asyncio.create_task(app.state.observer.refresh_baselines())
        background.add(task)  # keep a ref or the loop may drop it mid-run
        task.add_done_callback(background.discard)
        return {"started": True}

    return app


app = create_app()
