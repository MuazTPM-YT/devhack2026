import threading
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException

from chaos import faults, ground_truth
from chaos.faults import KubectlError, Kubectl
from chaos.reset import ensure_snapshot, reset

# URL path -> fault; names match bench/harness.py SCENARIOS
FAULTS: dict[str, Callable[[Kubectl], dict[str, str]]] = {
    "bad-deploy": faults.bad_deploy,
    "broken-config": faults.broken_config,
    "memory-leak": faults.memory_leak,
    "datastore-down": faults.datastore_down,
}


# chaos panel on :7004, admin kubeconfig; the agent must never get a path to this app
def create_app(data_dir: Path = Path("data"), run: Kubectl = faults.kubectl) -> FastAPI:
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

    # for the bench only; never called by the agent
    @app.get("/chaos/ground-truth")
    def read_truth():
        return ground_truth.read_all(truth_path)

    return app


app = create_app()
