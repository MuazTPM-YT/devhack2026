# observer process, port 7001 (IMPLEMENTATION.md §6.2): detector loop, kube watch, /health/now, /journal.
# Run: uv run --env-file .env uvicorn observer.main:app --host 127.0.0.1 --port 7001
import asyncio
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
from schemas import config
from schemas.db import DEFAULT_PATH, connect
from schemas.models import Incident

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
                                 policy["major_incident"]["within_seconds"])
        self.poll_s = d["poll_seconds"]
        self.conn, self.tracker, self.http, self.clock = conn, tracker, http, clock
        self.prom_url, self.brain_url, self.gateway_url = prom_url, brain_url, gateway_url
        self.queries, self.services = queries, services
        with tracker.lock:
            self.baselines = baselines.load(conn)
        self.health: dict | None = None
        self.undelivered: set[str] = set()

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
        health, event = self.detector.tick(now, readings, self.baselines, self.tracker.bad_pods(now))
        self.health = {**health, "prometheus_ok": True}
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
                (await self.http.post(url, json=payload, timeout=5)).raise_for_status()
            except httpx.HTTPError as e:
                failed.add(name)
                if not retry:
                    log.warning("POST %s failed: %s; will retry each poll", url, type(e).__name__)
        self.undelivered = failed

    async def run(self) -> None:
        while True:
            await self.step()
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
            except (httpx.HTTPError, KeyError, ValueError) as e:
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
