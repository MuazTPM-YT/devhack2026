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
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from chaos import faults, ground_truth
from chaos.faults import KubectlError, Kubectl
from chaos.reset import ensure_snapshot, reset
from schemas import logs

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

RawKubectl = Callable[[list[str]], tuple[bool, str]]
Severity = Callable[[], float | None]
log = logging.getLogger("chaos")


# observer severity now; None when it can't be read (observer down or not started yet)
def observer_severity(url: str) -> float | None:
    try:
        r = httpx.get(f"{url}/health/now", timeout=5)
        r.raise_for_status()
        return float(r.json()["severity"])
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        return None


# plan §6.1: reset ends when severity is back to 0. True / False (timed out) / None (no observer configured)
def wait_healthy(severity: Severity | None, timeout_s: float, every_s: float = 5,
                 sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic) -> bool | None:
    if severity is None:
        return None
    deadline = clock() + timeout_s
    while True:
        if severity() == 0:
            return True
        if clock() >= deadline:
            return False
        sleep(every_s)


class KubectlBody(BaseModel):
    command: str = Field(min_length=1, max_length=2000)


# chaos panel on :7004, admin kubeconfig; the agent must never get a path to this app
def create_app(data_dir: Path = Path("data"), run: Kubectl = faults.kubectl,
               raw: RawKubectl = faults.raw_kubectl, severity: Severity | None = None,
               reset_timeout_s: float = 300) -> FastAPI:
    if severity is None and (url := os.environ.get("OBSERVER_URL")):
        severity = lambda: observer_severity(url)  # noqa: E731
    truth_path = data_dir / "ground_truth.jsonl"
    snapshot_path = data_dir / "healthy_snapshot.json"
    # one cluster write at a time, so a reset never races an inject
    lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.snapshot = ensure_snapshot(snapshot_path, run)
        yield

    app = FastAPI(lifespan=lifespan)

    # closure per fault; a default-arg lambda would show up as a query parameter
    def endpoint(fault: Callable[[Kubectl], dict[str, str]]) -> Callable[[], dict[str, Any]]:
        def inject() -> dict[str, Any]:
            with lock:
                try:
                    done = fault(run)
                except KubectlError as error:
                    raise HTTPException(502, str(error)) from None
                return ground_truth.record(truth_path, done.pop("type"), done.pop("target"), **done)
        return inject

    for path, fault in FAULTS.items():
        app.post(f"/chaos/{path}")(endpoint(fault))

    @app.post("/chaos/reset")
    def do_reset():
        with lock:
            try:
                restored = reset(app.state.snapshot, run)
            except KubectlError as error:
                raise HTTPException(502, str(error)) from None
            healthy = wait_healthy(severity, reset_timeout_s)
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
            if args[0] not in READ_ONLY:
                recorded = ground_truth.record(truth_path, "judge_kubectl", args=args, ok=ok)
        return {"ok": ok, "output": output, "recorded": recorded is not None}

    # for the bench only; never called by the agent
    @app.get("/chaos/ground-truth")
    def read_truth():
        return ground_truth.read_all(truth_path)

    return app


app = create_app()
