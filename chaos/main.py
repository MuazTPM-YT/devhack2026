import shlex
import threading
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from chaos import faults, ground_truth
from chaos.faults import KubectlError, Kubectl
from chaos.reset import ensure_snapshot, reset

# URL path -> fault; every bench/harness.py SCENARIOS name has a route here
FAULTS: dict[str, Callable[[Kubectl], dict[str, str]]] = {
    "bad-deploy": faults.bad_deploy,
    "broken-config": faults.broken_config,
    "memory-leak": faults.memory_leak,
    "datastore-down": faults.datastore_down,
    "flag-flip": faults.flag_flip,
}

# judge commands that change nothing; everything else is logged as ground truth for the bench
READ_ONLY = {"get", "describe", "logs", "top", "explain", "api-resources", "api-versions", "version",
             "events", "auth", "cluster-info", "diff"}

RawKubectl = Callable[[list[str]], tuple[bool, str]]


class KubectlBody(BaseModel):
    command: str = Field(min_length=1, max_length=2000)


# chaos panel on :7004, admin kubeconfig; the agent must never get a path to this app
def create_app(data_dir: Path = Path("data"), run: Kubectl = faults.kubectl,
               raw: RawKubectl = faults.raw_kubectl) -> FastAPI:
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
            return ground_truth.record(truth_path, "reset", restored=restored)

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
