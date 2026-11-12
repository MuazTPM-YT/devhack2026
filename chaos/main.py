import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException

from chaos import faults, ground_truth
from chaos.faults import KubectlError, Kubectl
from chaos.reset import ensure_snapshot, reset


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

    @app.post("/chaos/bad-deploy")
    def bad_deploy():
        with lock:
            try:
                fault = faults.bad_deploy(run)
            except KubectlError as error:
                raise HTTPException(502, str(error)) from None
            return ground_truth.record(truth_path, fault["type"], fault["target"])

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
