import logging
import os
import shlex
import threading
import time
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from chaos import faults, ground_truth, registry
from chaos.experiments import Engine, Health, Spec
from chaos.faults import KubectlError, Kubectl
from chaos.registry import Refused
from chaos.reset import ensure_snapshot, reset
from schemas import auth, logs

logs.setup()

# URL path -> fault; every bench/harness.py SCENARIOS name has a route here
FAULTS: dict[str, Callable[[Kubectl], dict[str, str]]] = {
    "bad-deploy": faults.bad_deploy,
    "broken-config": faults.broken_config,
    "memory-leak": faults.memory_leak,
    "datastore-down": faults.datastore_down,
    "flag-flip": faults.flag_flip,
    "shared-outage": faults.shared_outage,
}

# judge commands that change nothing; everything else is logged as ground truth for the bench
READ_ONLY = {"get", "describe", "logs", "top", "explain", "api-resources", "api-versions", "version",
             "events", "auth", "cluster-info", "diff"}

# kubectl global flags that take the next word as their value (when written without "=")
VALUE_FLAGS = {"-n", "--namespace", "--context", "--cluster", "--user", "--kubeconfig", "-s", "--server",
               "--as", "--as-group", "--request-timeout", "-v", "--v"}


# the subcommand, skipping global flags before it: `-n shop get pods` -> "get"
def verb(args: list[str]) -> str | None:
    skip = False
    for word in args:
        if skip:
            skip = False
        elif word.startswith("-"):
            skip = "=" not in word and word in VALUE_FLAGS
        else:
            return word
    return None


RawKubectl = Callable[[list[str]], tuple[bool, str]]
Severity = Callable[[], float | None]
log = logging.getLogger("chaos")


# the six fixed scenarios as experiments: same faults, now tracked. -> (spec, ground-truth line)
LEGACY: dict[str, tuple[Spec, dict[str, str]]] = {
    "bad-deploy": (Spec(target="payment", capability="image", choice=faults.BAD_PAYMENT_IMAGE),
                   {"type": "bad_deploy"}),
    "broken-config": (Spec(target="checkout", capability="env:PAYMENT_ADDR", choice="wrong_port"),
                      {"type": "broken_config", "key": "PAYMENT_ADDR"}),
    "memory-leak": (Spec(target="recommendation", capability=f"flag:{faults.LEAK_FLAG}", choice="on"),
                    {"type": "resource_exhaustion"}),
    "datastore-down": (Spec(target="valkey-cart", capability="scale_zero", choice="0"),
                       {"type": "failing_dependency"}),
    "flag-flip": (Spec(target="payment", capability=f"flag:{faults.FLIP_FLAG}", choice=faults.FLIP_VARIANT),
                  {"type": "broken_config", "key": faults.FLIP_FLAG}),
    "shared-outage": (Spec(target="kafka", capability="scale_zero", choice="0"), {"type": "shared_dependency"}),
}


# the observer's reading now; None when it can't be read (observer down or not started yet)
def observer_health(url: str) -> dict[str, Any] | None:
    try:
        r = httpx.get(f"{url}/health/now", timeout=5)
        r.raise_for_status()
        body = r.json()
        float(body["severity"])
        return body
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        return None


# severity now; None when unreadable or when the numbers are stale (prometheus_ok false): stale zero
# is not healthy
def observer_severity(url: str) -> float | None:
    health = observer_health(url)
    if health is None or health.get("prometheus_ok") is not True:
        return None
    return float(health["severity"])


# plan §6.1: reset ends when severity is back to 0 and stays there for stable_s (one zero reading isn't
# enough: live, cart flapped after valkey-cart came back and the next scenario opened on it).
# True / False (timed out) / None (no observer configured)
def wait_healthy(severity: Severity | None, timeout_s: float, every_s: float = 5, stable_s: float = 30,
                 sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic) -> bool | None:
    if severity is None:
        return None
    deadline = clock() + timeout_s
    calm_since: float | None = None
    while True:
        now = clock()
        if severity() == 0:
            calm_since = now if calm_since is None else calm_since
            if now - calm_since >= stable_s:
                return True
        else:
            calm_since = None
        if now >= deadline:
            return False
        sleep(every_s)


class KubectlBody(BaseModel):
    command: str = Field(min_length=1, max_length=2000)


class DrawBody(BaseModel):
    seed: int | None = Field(default=None, ge=0, lt=2**31)
    blind: bool = True
    decoy: bool = False
    tested_only: bool = True


# chaos panel on :7004, admin kubeconfig; the agent must never get a path to this app.
# Every route, reads too, needs the judge token: ground truth and experiment specs are the answers
def create_app(data_dir: Path = Path("data"), run: Kubectl = faults.kubectl,
               raw: RawKubectl = faults.raw_kubectl, severity: Severity | None = None,
               reset_timeout_s: float = 300, reset_stable_s: float = 30, health: Health | None = None,
               tick_s: float | None = 5) -> FastAPI:
    if (url := os.environ.get("OBSERVER_URL")):
        if severity is None:
            severity = lambda: observer_severity(url)  # noqa: E731
        if health is None:
            health = lambda: observer_health(url)  # noqa: E731
    truth_path = data_dir / "ground_truth.jsonl"
    snapshot_path = data_dir / "healthy_snapshot.json"
    # one cluster write at a time, so a reset never races an inject or the watchdog
    lock = threading.RLock()
    engine = Engine(data_dir, run, health, lock)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        auth.token(auth.JUDGE_ENV)  # fail at start, not on the first inject
        app.state.snapshot = ensure_snapshot(snapshot_path, run)
        engine.open()
        stop = threading.Event()

        # expiry, cleanup and recovery checks keep running when no browser is open
        def watchdog() -> None:
            while not stop.wait(tick_s):
                try:
                    engine.tick()
                except Exception:
                    log.exception("watchdog tick failed")

        if tick_s is not None:
            threading.Thread(target=watchdog, name="chaos-watchdog", daemon=True).start()
        yield
        stop.set()

    app = FastAPI(lifespan=lifespan)
    app.state.engine = engine
    app.add_middleware(auth.TokenGuard, env=auth.JUDGE_ENV, header=auth.JUDGE_HEADER, guard_reads=True)

    # closure per fault; a default-arg lambda would show up as a query parameter
    def endpoint(spec: Spec, truth: dict[str, str]) -> Callable[[], dict[str, Any]]:
        def inject() -> dict[str, Any]:
            try:
                exp = engine.start(spec, truth=truth)
            except KubectlError as error:
                raise HTTPException(502, str(error)) from None
            if exp["status"] == "rejected":
                raise HTTPException(409, exp["error"])
            return exp["truth_entry"]
        return inject

    for path in FAULTS:
        app.post(f"/chaos/{path}")(endpoint(*LEGACY[path]))

    @app.post("/chaos/reset")
    def do_reset():
        with lock:
            try:
                restored = reset(app.state.snapshot, run)
            except KubectlError as error:
                raise HTTPException(502, str(error)) from None
            engine.close_all("reset")
        # outside the lock: a slow recovery must not block stop or the next inject
        healthy = wait_healthy(severity, reset_timeout_s, stable_s=reset_stable_s)
        if healthy is False:
            log.warning("reset done but severity not 0 after %.0f s", reset_timeout_s)
        return ground_truth.record(truth_path, "reset", restored=restored, healthy=healthy)

    # scenario 6: judges break things their own way; shlex split, never a shell
    @app.post("/chaos/kubectl")
    def judge_kubectl(body: KubectlBody):
        try:
            args = shlex.split(body.command)
        except ValueError as error:
            raise HTTPException(400, f"cannot parse command: {error}") from None
        if args[:1] == ["kubectl"]:
            args = args[1:]
        if not args:
            raise HTTPException(400, "empty command")
        with lock:
            ok, output = raw(args)
            recorded = None
            if verb(args) not in READ_ONLY:
                recorded = ground_truth.record(truth_path, "judge_kubectl", args=args, ok=ok)
        return {"ok": ok, "output": output, "recorded": recorded is not None}

    # for the bench and the judge; never called by the agent
    @app.get("/chaos/ground-truth")
    def read_truth():
        return ground_truth.read_all(truth_path)

    # ---- chaos lab: bounded experiments over the reviewed registry ------------------------------
    @app.get("/chaos/registry")
    def read_registry():
        try:
            with lock:
                return {**registry.build(run), "baseline": engine.baseline(),
                        "open": [engine.view(e) for e in engine.open_runs()]}
        except KubectlError as error:
            raise HTTPException(502, str(error)) from None

    @app.post("/chaos/experiments/preview")
    def preview(spec: Spec):
        try:
            return engine.preview(spec)
        except KubectlError as error:
            raise HTTPException(502, str(error)) from None

    def started(exp: dict[str, Any]) -> JSONResponse:
        return JSONResponse(engine.view(exp), status_code=409 if exp["status"] == "rejected" else 200)

    @app.post("/chaos/experiments")
    def start(spec: Spec, idempotency_key: str | None = Header(default=None, max_length=80)):
        try:
            return started(engine.start(spec, idempotency_key))
        except KubectlError as error:
            raise HTTPException(502, str(error)) from None

    @app.post("/chaos/experiments/draw")
    def draw(body: DrawBody):
        try:
            return started(engine.draw(body.seed, body.blind, body.decoy, body.tested_only))
        except Refused as error:
            raise HTTPException(409, str(error)) from None
        except KubectlError as error:
            raise HTTPException(502, str(error)) from None

    @app.get("/chaos/experiments")
    def recent():
        return engine.recent()

    def found(exp: dict[str, Any] | None) -> dict[str, Any]:
        if exp is None:
            raise HTTPException(404, "unknown experiment")
        return exp

    @app.get("/chaos/experiments/{exp_id}")
    def one(exp_id: str):
        return found(engine.get(exp_id))

    @app.post("/chaos/experiments/{exp_id}/stop")
    def stop(exp_id: str):
        return found(engine.stop(exp_id))

    @app.post("/chaos/experiments/{exp_id}/reveal")
    def reveal(exp_id: str):
        return found(engine.reveal(exp_id))

    return app


app = create_app()
