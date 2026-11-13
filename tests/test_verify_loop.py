import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from gateway.approvals import REHEARSAL_APPROVER
from test_gateway import BAD, GOOD, World, action


def healthy(err=0.01, severity=0):
    return {"ts": 0, "severity": severity, "services": {
        "payment": {"unhealthy": False, "breaching": False, "bad_pods": 0, "err_ratio": err},
        "checkout": {"unhealthy": False, "breaching": False, "bad_pods": 0, "err_ratio": 0.0}}}


def sick(severity=4):
    return {"ts": 0, "severity": severity, "services": {
        "payment": {"unhealthy": True, "breaching": True, "bad_pods": 0, "err_ratio": 0.4},
        "checkout": {"unhealthy": True, "breaching": True, "bad_pods": 0, "err_ratio": 0.2}}}


class Script:
    """Observer whose /health/now follows a script; each read moves the clock 5 s."""

    def __init__(self, world, healths, journal_during=None):
        self.world, self.healths, self.journal_during, self.active = world, list(healths), journal_during, False
        self.inner = world.obs

    def __call__(self, request):
        if request.url.path == "/health/now" and self.active:
            self.world.now[0] += 5
            h = self.healths.pop(0) if len(self.healths) > 1 else self.healths[0]
            return httpx.Response(200, json=h)
        if request.url.path == "/journal" and self.journal_during and self.active:
            return httpx.Response(200, json=self.journal_during)
        return self.inner(request)


async def executed(tmp_path, healths, decided_by="u1", journal_during=None, setup=None):
    w = World(tmp_path)
    script = Script(w, healths, journal_during)
    w.gw.http = httpx.AsyncClient(transport=httpx.MockTransport(script))
    d = await w.gw.submit(action())
    w.gw.verify_every = 0
    if decided_by == REHEARSAL_APPROVER:
        w.gw.approvers.add(REHEARSAL_APPROVER)
    d = await w.gw.decide(d.approval_id, "approved", decided_by)
    assert d.decision == "executed"
    if setup:
        setup(w)
    script.active = True  # verify task has not run a tick yet; from here health follows the script
    task = next(iter(w.gw.tasks))
    return w, d, await asyncio.wait_for(task, 5)


def ledger(w):
    return [tuple(r) for r in w.conn.execute("SELECT source, successes, failures FROM ledger")]


async def test_recovery_with_prediction_is_success_and_real_credit(tmp_path):
    w, d, outcome = await executed(tmp_path, [healthy()])
    assert outcome == "success"
    assert w.types()[-1] == "incident_resolved" and "harm_check" in w.types()
    card = w.events[-1]["payload"]["card"]
    assert card["status"] == "FIXED"
    assert ledger(w) == [("real", 1, 0)]
    r = w.gw.receipts.get(d.receipt_id)
    assert (r.outcome, r.prediction_held, r.harm_clean) == ("success", True, True)
    assert w.conn.execute("SELECT state FROM incidents").fetchone()[0] == "resolved"


async def test_no_recovery_undoes_and_escalates(tmp_path):
    w, d, outcome = await executed(tmp_path, [sick()])
    assert outcome == "undone"
    assert w.apps.dep["spec"]["template"]["spec"]["containers"][0]["image"] == BAD
    assert "action_undone" in w.types() and w.types()[-1] == "escalated"
    assert ledger(w) == [("real", 0, 1)]


async def test_recovered_but_prediction_missed_is_right_by_accident(tmp_path):
    w, d, outcome = await executed(tmp_path, [healthy(err=0.06)] * 30 + [healthy()])
    assert outcome == "right_by_accident" and ledger(w) == []


async def test_early_abort_pauses_undoes_resumes(tmp_path):
    w, d, outcome = await executed(tmp_path, [sick(severity=9)])
    assert outcome == "undone" and "early_abort" in w.types()
    ops = [p["patch"][1] for p in w.apps.patches[-3:]]
    assert ops[0] == {"op": "add", "path": "/spec/paused", "value": True}
    assert ops[1]["path"] == "/spec/template" and ops[2]["value"] is False
    assert w.apps.dep["spec"]["paused"] is False


# live run 2026-11-13: checkout turned sick 5 s after the right rollback, severity 7 -> 8, early abort undid it
async def test_lagging_victim_inside_grace_does_not_abort(tmp_path):
    w, d, outcome = await executed(tmp_path, [sick(severity=9)] * 6 + [healthy()])
    assert outcome == "success" and "early_abort" not in w.types()


# live run 2026-11-13: rollout status bumped resourceVersion between read and patch -> 422 on undo
async def test_undo_survives_status_churn(tmp_path):
    w, d, outcome = await executed(tmp_path, [sick(severity=9)], setup=lambda w: setattr(w.apps, "status_churn", True))
    assert outcome == "undone" and w.apps.dep["spec"]["paused"] is False


# live run 2026-11-13: failed undo left payment paused and its receipt pending, blocking every later action
async def test_failed_undo_unpauses_and_frees_the_slot(tmp_path, caplog):
    from kubernetes.client.rest import ApiException

    def broken(w):
        w.apps.fail_template = ApiException(status=422, reason="Invalid")

    w, d, outcome = await executed(tmp_path, [sick(severity=9)], setup=broken)
    assert outcome == "undo_failed" and w.apps.dep["spec"]["paused"] is False
    assert w.conn.execute("SELECT outcome FROM receipts WHERE id=?", (d.receipt_id,)).fetchone()[0] == "undo_failed"
    assert w.gw.receipts.get(d.receipt_id).outcome == "undo_failed"
    assert d.receipt_id not in w.gw.verifying and "UNDO FAILED" in caplog.text


async def test_human_change_during_verify_hands_off_without_undo(tmp_path):
    human = [{"id": 50, "object": "deployment/payment", "kind": "replicas", "ts": 1001.0,
              "field_manager": "kubectl", "by_agent": False, "diff": {}}]
    w, d, outcome = await executed(tmp_path, [sick()], journal_during=human)
    assert outcome == "handed_off" and w.types()[-1] == "handed_off"
    assert w.apps.dep["spec"]["template"]["spec"]["containers"][0]["image"] == GOOD
    assert ledger(w) == []


async def test_rehearsal_credit_once_and_only_for_rehearsal(tmp_path):
    w, d, outcome = await executed(tmp_path, [healthy()], decided_by=REHEARSAL_APPROVER)
    assert outcome == "success" and ledger(w) == []
    assert w.gw.rehearsal_credit(d.receipt_id, True) == {"credited": True, "success": True}
    assert w.gw.rehearsal_credit(d.receipt_id, True)["reason"] == "already credited"
    assert ledger(w) == [("rehearsal", 1, 0)]
    w2, d2, _ = await executed(tmp_path / "b", [healthy()])
    assert w2.gw.rehearsal_credit(d2.receipt_id, True)["reason"] == "not a rehearsal receipt"


@pytest.mark.parametrize("flag,code", [("0", 404), ("1", 200)])
def test_rehearsal_route_needs_flag(tmp_path, monkeypatch, flag, code):
    from gateway.main import create_app
    monkeypatch.setenv("ONCALL_REHEARSAL", flag)
    w = World(tmp_path)
    with TestClient(create_app(w.gw), base_url="http://127.0.0.1:7003") as client:
        r = client.post("/ledger/rehearsal", json={"receipt_id": 1, "diagnosis_matched": True})
        assert r.status_code == code
        if code == 200:
            assert json.loads(r.content)["reason"] == "unknown receipt"


async def test_brain_mcp_client_reaches_real_gateway(tmp_path):
    from brain.gateway_client import call_tool
    from gateway.main import create_app
    from schemas.models import ActionRequest

    w = World(tmp_path)
    app = create_app(w.gw)
    async with app.router.lifespan_context(app):
        http = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:7003")
        d = await call_tool("http://127.0.0.1:7003", ActionRequest.model_validate(action()), http=http)
        assert d.decision == "awaiting_approval" and d.approval_id
        bad = await call_tool("http://127.0.0.1:7003",
                              ActionRequest.model_validate(action(target="valkey-cart")), http=http)
        assert bad.decision == "refused"  # not in the MCP target enum: rejected before the checklist
