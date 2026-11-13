# gateway process, port 7003 (IMPLEMENTATION.md §6.4): MCP tools + HTTP. The only write identity.
# Run: uv run --locked --env-file .env uvicorn gateway.main:app --host 127.0.0.1 --port 7003
import asyncio
import contextlib
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from gateway import events
from gateway.approvals import approvers_from_env
from gateway.checklist import Gateway
from gateway.mcp_server import build_mcp
from gateway.receipts import ReceiptStore, create_receipts_router
from schemas import config
from schemas.db import DEFAULT_PATH, connect


class Decide(BaseModel):
    decision: Literal["approved", "rejected"]
    decided_by: str


class RehearsalCredit(BaseModel):
    receipt_id: int
    diagnosis_matched: bool


def require_env(*names: str) -> list[str]:
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        raise RuntimeError(f"missing required env var(s): {', '.join(missing)}")
    return [os.environ[n] for n in names]


def build_from_env() -> Gateway:
    from kubernetes import client
    from kubernetes import config as kube_config

    from brain.graph import DependencyGraph

    kubeconfig, observer, jaeger = require_env("AGENT_KUBECONFIG", "OBSERVER_URL", "JAEGER_URL")
    api = kube_config.new_client_from_config(config_file=kubeconfig)
    http = httpx.AsyncClient()
    return Gateway(connect(DEFAULT_PATH, shared=True), client.AppsV1Api(api), client.CoreV1Api(api),
                   http, observer, config.load("services")["services"], config.load("policy"),
                   events.publish, ReceiptStore(Path(DEFAULT_PATH)), approvers_from_env(),
                   graph=DependencyGraph(http, jaeger), flag_map=config.load("services").get("flags") or {})


def create_app(gateway: Gateway | None = None) -> FastAPI:
    services = config.load("services")["services"]
    actable = [s for s, v in services.items() if v.get("actable") and not v.get("protected")]
    holder: dict[str, Gateway] = {}

    async def submit(raw: dict):
        return await holder["gw"].submit(raw)

    mcp = build_mcp(submit, actable)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        holder["gw"] = gateway or build_from_env()
        app.state.gateway = holder["gw"]
        async with contextlib.AsyncExitStack() as stack:
            await stack.enter_async_context(mcp.session_manager.run())
            upkeep = asyncio.create_task(holder["gw"].upkeep()) if gateway is None else None
            yield
            if upkeep:
                upkeep.cancel()
            for task in list(holder["gw"].tasks):
                task.cancel()
            if gateway is None:
                await holder["gw"].http.aclose()

    app = FastAPI(title="oncall gateway", lifespan=lifespan)
    app.include_router(events.router)
    app.include_router(create_receipts_router(ReceiptStore(Path(DEFAULT_PATH))) if gateway is None
                       else create_receipts_router(gateway.receipts))

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    # ponytail: no caller auth beyond the approver allowlist; bind to 127.0.0.1 only
    @app.post("/approvals/{approval_id}/decide")
    async def decide(approval_id: str, body: Decide) -> dict:
        d = await holder["gw"].decide(approval_id, body.decision, body.decided_by)
        return d.model_dump(mode="json")

    # Q2: bench-only; 404 unless the gateway started with ONCALL_REHEARSAL=1
    @app.post("/ledger/rehearsal")
    def ledger_rehearsal(body: RehearsalCredit) -> dict:
        if os.environ.get("ONCALL_REHEARSAL") != "1":
            raise HTTPException(404, "rehearsal mode is off")
        return holder["gw"].rehearsal_credit(body.receipt_id, body.diagnosis_matched)

    @app.get("/ledger")
    def ledger() -> list[dict]:
        gw = holder["gw"]
        with gw.lock:
            return [dict(r) for r in gw.conn.execute("SELECT * FROM ledger ORDER BY pattern, action, target")]

    app.mount("/", mcp.streamable_http_app())  # serves /mcp; mounted last so the routes above win
    return app


app = create_app()
