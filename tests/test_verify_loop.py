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
    assert "image change" in card["text"].splitlines()[1]  # gateway has no diagnosis; the journal explains
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
                              ActionRequest.model_validate(action(target="frontend-proxy")), http=http)
        assert bad.decision == "refused"  # not in the MCP target enum: rejected before the checklist
        # data stores are in the enum now, but only a human-approved scale may touch them (Muaz chose)
        store = await call_tool("http://127.0.0.1:7003",
                                ActionRequest.model_validate(action(target="valkey-cart")), http=http)
        assert (store.decision, store.failed_step) == ("escalated", "policy")


# plan §6.7.1 card + §9.1 bench fields on the terminal event
async def test_success_card_and_terminal_payload(tmp_path):
    w, d, outcome = await executed(tmp_path, [healthy()])
    payload = w.events[-1]["payload"]
    lines = payload["card"]["text"].splitlines()
    assert len(lines) == 5 and lines[0].startswith("FIXED in ") and "payment errors 40.0% → 1.0%" in lines[0]
    assert "payment:v2-bad" in lines[1] and "journal:41" in payload["card"]["evidence_ids"]
    assert "back to revision 1" in lines[2] and "approved by u1" in lines[2]
    assert "recovery matched the agent's prediction; nothing else got worse; extra disruption 0 s" in lines[3]
    assert lines[4] == "Undo: kubectl rollout undo deploy/payment -n shop"
    assert (payload["tier"], payload["prediction_held"], payload["harm_clean"]) == ("ask", True, True)
    assert payload["receipt_id"] == d.receipt_id and payload["actual_added_s"] == 0
    assert next(e for e in w.events if e["type"] == "action_executed")["payload"]["tier"] == "ask"


# real success needs a human's yes (§6.4.6): an automatic fix that works earns no real credit
async def test_automatic_success_earns_no_real_credit_but_failure_counts(tmp_path):
    for healths, want in (([healthy()], []), ([sick()], [("real", 0, 1)])):
        w = World(tmp_path)
        w.conn.execute("INSERT INTO ledger VALUES ('recent_change', 'rollback_deploy', 'payment', 'rehearsal', "
                       "30, 0, NULL)")
        script = Script(w, healths)
        w.gw.http = httpx.AsyncClient(transport=httpx.MockTransport(script))
        w.gw.verify_every = 0
        d = await w.gw.submit(action())
        assert d.decision == "executed"
        script.active = True
        await asyncio.wait_for(next(iter(w.gw.tasks)), 5)
        assert [r for r in ledger(w) if r[0] == "real"] == want
        assert w.conn.execute("SELECT tier FROM incidents").fetchone()[0] == "auto"
        if not want:
            assert "automatic; trust 30 rehearsals, 0 real; proven at least 90%" in \
                w.events[-1]["payload"]["card"]["text"]


async def test_no_prediction_is_none_not_missed(tmp_path):
    w = World(tmp_path)
    script = Script(w, [healthy()])
    w.gw.http = httpx.AsyncClient(transport=httpx.MockTransport(script))
    w.gw.verify_every = 0
    d = await w.gw.submit(action(prediction=None))
    d = await w.gw.decide(d.approval_id, "approved", "u1")
    script.active = True
    assert await asyncio.wait_for(next(iter(w.gw.tasks)), 5) == "right_by_accident"
    assert w.gw.receipts.get(d.receipt_id).prediction_held is None
    assert "no prediction to check" in w.events[-1]["payload"]["card"]["text"]
    assert w.events[-1]["payload"]["card"]["status"] == "RECOVERED, FIX NOT PROVEN"


# harm check spares the blast radius (§6.4.9): an upstream caller that dips is expected, not harm
async def test_upstream_caller_inside_blast_radius_is_not_harm(tmp_path):
    from test_phase3 import FakeGraph

    def frontend(h, sick_frontend):
        h["services"]["frontend"] = {"unhealthy": False, "breaching": sick_frontend, "bad_pods": 0,
                                     "err_ratio": 0.2 if sick_frontend else 0.0}
        return h

    for edges, want in (([("frontend", "checkout", 5.0), ("checkout", "payment", 5.0)], "success"),
                        ([], "undone")):  # not upstream of payment: a frontend that got worse is harm
        w = World(tmp_path)
        w.gw.graph = FakeGraph(edges)
        script = Script(w, [frontend(healthy(), True)])
        before = frontend(sick(), False)

        def handler(request, script=script, before=before):
            if request.url.path == "/health/now" and not script.active:
                return httpx.Response(200, json=before)
            return script(request)

        w.gw.http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        w.gw.verify_every = 0
        d = await w.gw.submit(action())
        d = await w.gw.decide(d.approval_id, "approved", "u1")
        script.active = True
        assert await asyncio.wait_for(next(iter(w.gw.tasks)), 5) == want


def store(cart_sick: bool, severity: int, spread: bool = False) -> dict:
    sick_svc = {"unhealthy": True, "breaching": True, "bad_pods": 0, "err_ratio": 1.0, "p95_ms": 5.0}
    fine = {"unhealthy": False, "breaching": False, "bad_pods": 0, "err_ratio": 0.0, "p95_ms": 5.0}
    services = {"valkey-cart": {"unhealthy": False, "breaching": False, "bad_pods": 0, "err_ratio": None,
                                "p95_ms": None},
                "cart": sick_svc if cart_sick else fine, "checkout": sick_svc if spread else fine}
    return {"ts": 0, "severity": severity, "services": services}


# valkey-cart scaled to 0, a human approves the scale back to 1; health then follows `healths`
async def store_scaled_back(tmp_path, healths):
    w = World(tmp_path)
    w.conn.execute("UPDATE incidents SET culprit='valkey-cart', victims_json='[\"cart\"]'")
    w.apps.dep["spec"]["replicas"] = 0
    w.apps.dep["metadata"]["name"] = "valkey-cart"  # harm check hashes deployments by name
    journal = [{"id": 50, "object": "deployment/valkey-cart", "kind": "replicas", "ts": 950.0,
                "field_manager": "chaos-panel", "by_agent": False, "diff": {"replicas": {"old": 1, "new": 0}}}]

    def before(request):
        if request.url.path == "/journal":
            return httpx.Response(200, json=[r for r in journal if r["ts"] >= float(request.url.params["since"])])
        return httpx.Response(200, json=store(True, 7))

    w.obs = before
    script = Script(w, healths)
    w.gw.http = httpx.AsyncClient(transport=httpx.MockTransport(script))
    w.gw.verify_every = 0
    a = action(tool="scale", target="valkey-cart", pattern="protected", journal_entry=50,
               evidence_ids=["journal:50"], params={"replicas": 1}, prediction=None)
    d = await w.gw.submit(a)
    d = await w.gw.decide(d.approval_id, "approved", "u1")
    assert d.decision == "executed"
    script.active = True
    return w, d, await asyncio.wait_for(next(iter(w.gw.tasks)), 5)


# live inc-1794564403607: callers kept failing while valkey-cart came back (sev 7 -> 17), early abort fired,
# and the undo "scale to 0" was refused by the replicas 1-3 admission policy: page said "half changed"
async def test_fix_with_no_safe_undo_is_not_aborted_while_the_fault_still_spreads(tmp_path):
    w, d, outcome = await store_scaled_back(tmp_path, [store(True, 17, spread=True)] * 14 + [store(False, 0)])
    assert "early_abort" not in w.types() and outcome == "right_by_accident"
    assert w.apps.dep["spec"]["replicas"] == 1
    assert json.loads(w.conn.execute("SELECT inverse_json FROM receipts").fetchone()[0])["op"] == "none"


async def test_fix_with_no_safe_undo_that_never_recovers_is_kept_and_pages(tmp_path):
    w, d, outcome = await store_scaled_back(tmp_path, [store(True, 17, spread=True)])
    assert outcome == "handed_off" and w.apps.dep["spec"]["replicas"] == 1
    assert [p for p in w.apps.patches if not p["dry_run"]][-1]["patch"]["spec"]["replicas"] == 1  # no scale to 0
    last = w.events[-1]
    assert last["type"] == "escalated" and "no safe undo" in last["payload"]["briefing"]
    assert "UNDO FAILED" not in json.dumps(last) and "configmap/None" not in json.dumps(last)
    assert "Undo: none is safe" in last["payload"]["card"]["text"]
    assert w.gw.receipts.get(d.receipt_id).outcome == "handed_off"
    assert ledger(w) == [("real", 0, 1)]  # an unproven fix counts against trust, kept or not


# the watchdog undoes a silent verifier's fix; a receipt with no safe undo must not crash it (KeyError)
async def test_watchdog_on_a_fix_with_no_safe_undo_fails_closed(tmp_path):
    from test_phase3 import executed_and_parked
    w, d = await executed_and_parked(tmp_path)
    w.conn.execute("UPDATE receipts SET inverse_json=?", (json.dumps({"op": "none", "why": "would scale to 0"}),))
    w.now[0] += 200
    assert await w.gw.watchdog() == 1
    assert w.conn.execute("SELECT outcome FROM receipts").fetchone()[0] == "watchdog_failed"
    assert w.apps.dep["spec"]["template"]["spec"]["containers"][0]["image"] == GOOD  # fix left in place
