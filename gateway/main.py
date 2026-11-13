# gateway process, port 7003 (IMPLEMENTATION.md §6.4): MCP tools + HTTP. The only write identity.
# Run: uv run --locked --env-file .env uvicorn gateway.main:app --host 127.0.0.1 --port 7003
import asyncio
import contextlib
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from brain import memory
from brain.redact import INJECTION, redact_value
from gateway import events, trust
from gateway.audit import verify
from gateway.approvals import approvers_from_env
from gateway.checklist import Gateway
from gateway.intents import Conflict, IntentStore
from gateway.mcp_server import build_mcp
from gateway.receipts import ReceiptStore, build_card, create_receipts_router
from schemas import auth, config, migrations
from schemas.db import DEFAULT_PATH, connect
from schemas.orchestration import IntentEnvelope, OrchestrationPolicy, load_policy
from schemas.workspace import Workspace
from schemas import logs

logs.setup()


class Decide(BaseModel):
    decision: Literal["approved", "rejected"]
    decided_by: str
    via: Literal["discord", "akira-mcp"] = "discord"


class Clear(BaseModel):
    decided_by: str


class RehearsalCredit(BaseModel):
    receipt_id: int
    diagnosis_matched: bool


ApprovalState = Literal["pending", "approved", "rejected", "expired", "superseded"]


# the model's "why" was written after reading untrusted evidence: drop it when it looks like an instruction
def incident_view(row: dict) -> dict:
    out = {k: v for k, v in row.items() if k != "victims_json"}
    out["victims"] = json.loads(row.get("victims_json") or "[]")
    out["major"] = bool(row.get("major"))
    if out.get("llm_why") and INJECTION.search(out["llm_why"]):
        out["llm_why"] = None
    return redact_value(out)


def approval_view(row: dict, now: float) -> dict:
    out = {k: v for k, v in row.items() if k != "action_json"}
    out["action"] = json.loads(row["action_json"])
    out["past_expiry"] = row["expires_at"] <= now
    return redact_value(out)


def require_env(*names: str) -> list[str]:
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        raise RuntimeError(f"missing required env var(s): {', '.join(missing)}")
    return [os.environ[n] for n in names]


def build_from_env() -> Gateway:
    from kubernetes import client
    from kubernetes import config as kube_config

    from brain import runbooks
    from brain.graph import DependencyGraph

    kubeconfig, observer, jaeger = require_env("AGENT_KUBECONFIG", "OBSERVER_URL", "JAEGER_URL")
    api = kube_config.new_client_from_config(config_file=kubeconfig)
    http = httpx.AsyncClient()
    gw = Gateway(connect(DEFAULT_PATH, shared=True), client.AppsV1Api(api), client.CoreV1Api(api),
                 http, observer, config.load("services")["services"], config.load("policy"),
                 events.publish, ReceiptStore(Path(DEFAULT_PATH)), approvers_from_env(),
                 graph=DependencyGraph(http, jaeger), flag_map=config.load("services").get("flags") or {},
                 rehearsal=os.environ.get("ONCALL_REHEARSAL") == "1", books=runbooks.load())
    orch = gw.orchestration = load_policy()
    if orch.mode != "disabled":  # orchestration: durable intents + read views (migration v2 required)
        migrations.require(gw.conn)
        gw.intents = IntentStore(gw.conn, gw.lock, gw.clock)
        gw.workspace = Workspace(gw.conn, orch, gw.clock, lock=gw.lock)
    return gw


def create_app(gateway: Gateway | None = None) -> FastAPI:
    services = config.load("services")["services"]
    # protected data stores are valid targets too, for a human-approved scale only (policy step 3)
    actable = [s for s, v in services.items() if v.get("actable") or v.get("protected")]
    holder: dict[str, Gateway] = {}

    async def submit(raw: dict):
        return await holder["gw"].submit(raw)

    mcp = build_mcp(submit, actable)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        auth.agent_start()  # fail at start, not on the first approval
        holder["gw"] = gateway or build_from_env()
        app.state.gateway = holder["gw"]
        async with contextlib.AsyncExitStack() as stack:
            await stack.enter_async_context(mcp.session_manager.run())
            await holder["gw"].reconcile_intents()  # unknown writes from before a restart, before anything new
            upkeep = asyncio.create_task(holder["gw"].upkeep()) if gateway is None else None
            yield
            if upkeep:
                upkeep.cancel()
            for task in list(holder["gw"].tasks):
                task.cancel()
            if gateway is None:
                await holder["gw"].http.aclose()

    app = FastAPI(title="oncall gateway", lifespan=lifespan)
    app.add_middleware(auth.TokenGuard)  # decide, clear, publish, MCP tools: our processes only
    app.include_router(events.router)
    app.include_router(create_receipts_router(ReceiptStore(Path(DEFAULT_PATH))) if gateway is None
                       else create_receipts_router(gateway.receipts))

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    # what the UI shows as the run mode: orchestration on or off, specialists on or off, what is in flight
    @app.get("/orchestration/status")
    def orchestration_status() -> dict:
        gw = holder["gw"]
        p = gw.orchestration or OrchestrationPolicy()
        out: dict = {"mode": p.mode, "delegation_enabled": p.delegation_enabled,
                     "max_active_commanders": p.max_active_commanders, "max_model_requests": p.max_model_requests,
                     "phases": {}, "specialists_running": 0, "unknown_writes": 0}
        if gw.workspace is not None:
            out["phases"] = {r[0]: r[1] for r in gw.workspace.rows(
                "SELECT phase, COUNT(*) FROM orchestration_workspaces WHERE phase != 'terminal' GROUP BY phase")}
            out["specialists_running"] = gw.workspace.rows(
                "SELECT COUNT(*) FROM investigation_tasks WHERE state IN ('pending', 'running')")[0][0]
            out["unknown_writes"] = gw.workspace.rows(
                "SELECT COUNT(*) FROM action_intents WHERE status='execution_unknown'")[0][0]
        return out

    # caller must hold ONCALL_API_TOKEN (TokenGuard); decided_by is then checked against the allowlist
    @app.post("/approvals/{approval_id}/decide")
    async def decide(approval_id: str, body: Decide) -> dict:
        d = await holder["gw"].decide(approval_id, body.decision, body.decided_by, body.via)
        return d.model_dump(mode="json")

    # orchestration: the brain's fix with its identity; same id + same action answers with the stored status
    @app.post("/orchestration/actions")
    async def submit_intent(env: IntentEnvelope) -> dict:
        gw = holder["gw"]
        if gw.intents is None:
            raise HTTPException(409, "orchestration is disabled in the gateway")
        try:
            return (await gw.submit_intent(env)).model_dump(mode="json")
        except Conflict as e:
            raise HTTPException(409, str(e)) from None

    @app.get("/orchestration/actions/{intent_id}")
    def get_intent(intent_id: str) -> dict:
        gw = holder["gw"]
        row = gw.intents.get(intent_id) if gw.intents is not None else None
        if row is None:
            raise HTTPException(404, "unknown intent")
        view = {k: v for k, v in row.items() if k not in ("precondition_json", "action_json")}
        return redact_value({**view, "action": json.loads(row["action_json"])})

    # an approver checked the cluster after a write with an unknown outcome: the slot frees, audited
    @app.post("/orchestration/actions/{intent_id}/clear")
    async def clear_intent(intent_id: str, body: Clear) -> dict:
        return await holder["gw"].clear_intent(intent_id, body.decided_by)

    # after a failed watchdog undo: an approver confirms the cluster was checked, actions may run again
    @app.post("/receipts/{receipt_id}/clear")
    async def clear_receipt(receipt_id: int, body: Clear) -> dict:
        return await holder["gw"].clear_receipt(receipt_id, body.decided_by)

    # Q2: bench-only; 404 unless the gateway started with ONCALL_REHEARSAL=1
    @app.post("/ledger/rehearsal")
    def ledger_rehearsal(body: RehearsalCredit) -> dict:
        if os.environ.get("ONCALL_REHEARSAL") != "1":
            raise HTTPException(404, "rehearsal mode is off")
        return holder["gw"].rehearsal_credit(body.receipt_id, body.diagnosis_matched)

    # /trust page (plan §6.8, A's shape): one row per key = trust.check(...) + the key
    @app.get("/trust")
    def trust_table() -> list[dict]:
        gw = holder["gw"]
        with gw.lock:
            keys = gw.conn.execute("SELECT DISTINCT pattern, action, target FROM ledger "
                                   "ORDER BY pattern, action, target").fetchall()
            rows = [{**dict(k), **trust.check(gw.conn, gw.policy["trust"], gw.policy["tools"].get(k["action"], {}),
                                              k["pattern"], k["action"], k["target"],
                                              gw.services.get(k["target"], {}).get("kind", "stateless"))}
                    for k in keys]
        return rows

    # the "verify audit log" button: walk the hash chain, name the first broken seq
    @app.get("/audit/verify")
    def audit_verify() -> dict:
        try:
            return {"ok": True, "records": len(verify(events.active_bus().audit.path))}
        except ValueError as e:
            return {"ok": False, "error": str(e)}

    @app.get("/ledger")
    def ledger() -> list[dict]:
        gw = holder["gw"]
        with gw.lock:
            return [dict(r) for r in gw.conn.execute("SELECT * FROM ledger ORDER BY pattern, action, target")]

    # ---- read views for the Akira MCP (open GETs like /receipts; text redacted) --------------------
    # unfinished: anything not yet resolved, escalated or handed off (open, verifying, awaiting_approval, ...)
    @app.get("/incidents")
    def list_incidents(state: str | None = Query(None, max_length=40), unfinished: bool = False,
                       limit: int = Query(50, ge=1, le=200)) -> list[dict]:
        gw = holder["gw"]
        where = ""
        args: tuple[str, ...] = ()
        if unfinished:
            where = " WHERE state IS NULL OR state NOT IN ('resolved', 'escalated', 'handed_off')"
        elif state:
            where, args = " WHERE state = ?", (state,)
        with gw.lock:
            rows = gw.conn.execute(f"SELECT * FROM incidents{where} ORDER BY opened_at DESC LIMIT ?",
                                   (*args, limit)).fetchall()
        views = [incident_view(dict(r)) for r in rows]
        if gw.workspace is not None:  # additive: orchestration phase and task count, null for old incidents
            for view in views:
                view["orchestration"] = gw.workspace.summary(view["id"])
        return views

    # one incident with everything around it: approvals, receipts + cards, its bus events, similar past ones
    @app.get("/incidents/{incident_id}")
    def get_incident(incident_id: str, events_limit: int = Query(300, ge=1, le=1000),
                     tasks_limit: int = Query(20, ge=1, le=200)) -> dict:
        gw = holder["gw"]
        with gw.lock:
            row = gw.conn.execute("SELECT * FROM incidents WHERE id=?", (incident_id,)).fetchone()
            if row is None:
                raise HTTPException(404, "unknown incident")
            asks = gw.conn.execute("SELECT * FROM approvals WHERE incident_id=? ORDER BY created_at",
                                   (incident_id,)).fetchall()
            ids = [r[0] for r in gw.conn.execute("SELECT id FROM receipts WHERE incident_id=? ORDER BY id",
                                                 (incident_id,))]
            past = memory.similar(gw.conn, incident_id, row["culprit"], row["pattern"])
        receipts = [{"id": i, "receipt": r, "card": build_card(r, i)} for i in ids if (r := gw.receipts.get(i))]
        mine = [rec for rec in events.active_bus().audit.records if rec["event"].get("incident_id") == incident_id]
        now = gw.clock()
        snapshot = gw.workspace.snapshot(incident_id, tasks_limit) if gw.workspace is not None else None
        return {"incident": incident_view(dict(row)), "approvals": [approval_view(dict(a), now) for a in asks],
                "receipts": receipts, "events": mine[-events_limit:], "events_total": len(mine), "similar": past,
                "orchestration": redact_value(snapshot.model_dump(mode="json")) if snapshot else None}

    @app.get("/approvals")
    def list_approvals(state: ApprovalState | None = None, limit: int = Query(50, ge=1, le=200)) -> list[dict]:
        gw = holder["gw"]
        where, args = (" WHERE state = ?", (state,)) if state else ("", ())
        with gw.lock:
            rows = gw.conn.execute(f"SELECT * FROM approvals{where} ORDER BY created_at DESC LIMIT ?",
                                   (*args, limit)).fetchall()
        now = gw.clock()
        return [approval_view(dict(r), now) for r in rows]

    # bus records after a seq, as JSON (the SSE stream replays everything and never ends; pollers need a page)
    @app.get("/events/log")
    def events_log(after: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=1000),
                   incident_id: str | None = None) -> dict:
        records = events.active_bus().audit.records
        page = [r for r in records[after:] if incident_id is None or r["event"].get("incident_id") == incident_id]
        # next_after: where the next poll starts; short of the end when the page was cut at limit
        cut = len(page) > limit
        return {"records": page[:limit], "last_seq": len(records),
                "next_after": page[limit - 1]["seq"] if cut else len(records)}

    app.mount("/", mcp.streamable_http_app())  # serves /mcp; mounted last so the routes above win
    return app


app = create_app()
