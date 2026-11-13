import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from brain.coordinator import as_decision
from gateway.intents import Conflict, IntentStore
from gateway.main import create_app
from gateway.verifier import Verification, harm_check
from schemas import auth, migrations
from schemas.models import ActionRequest
from schemas.orchestration import IntentEnvelope, IntentSubmission, intent_fingerprint
from tests.test_gateway import World, action


def orch_world(tmp_path, plan=0):
    w = World(tmp_path)
    migrations.migrate(w.conn)
    w.conn.execute("INSERT INTO orchestration_workspaces (incident_id, phase, plan_revision, created_at, "
                   "requests_limit, tool_calls_limit, specialists_limit) VALUES ('inc-1', 'awaiting_gateway', ?, "
                   "990, 9, 24, 2)", (plan,))
    w.conn.commit()
    w.gw.intents = IntentStore(w.conn, w.gw.lock, w.gw.clock)
    return w


def envelope(plan=0, intent_id=None, **over) -> IntentEnvelope:
    a = ActionRequest.model_validate(action(**over))
    fp = intent_fingerprint("inc-1", plan, a)
    return IntentEnvelope(intent_id=intent_id or f"int-{fp[:24]}", incident_id="inc-1", scope_revision=0,
                          plan_revision=plan, fingerprint=fp, action=a)


def intent_events(w):
    return [e["payload"]["status"] for e in w.events if e["type"] == "action_intent_changed"]


def busy(w):
    w.conn.execute("INSERT INTO receipts (incident_id, ts, tool, target, outcome) "
                   "VALUES ('inc-x', 999, 'scale', 'cart', 'pending')")
    w.conn.commit()


async def test_intent_asks_then_executes_once_on_approval(tmp_path):
    w = orch_world(tmp_path)
    env = envelope()
    sub = await w.gw.submit_intent(env)
    assert sub.status == "awaiting_approval" and sub.approval_id
    assert w.conn.execute("SELECT intent_id FROM approvals").fetchone()[0] == env.intent_id
    d = await w.gw.decide(sub.approval_id, "approved", "u1")
    assert d.decision == "executed"
    row = w.gw.intents.get(env.intent_id)
    assert row["status"] == "verifying" and row["receipt_id"] == d.receipt_id
    assert json.loads(row["precondition_json"])["resource_version"] == "100"
    assert intent_events(w) == ["awaiting_approval", "executing", "verifying"]
    for task in list(w.gw.tasks):
        task.cancel()


async def test_repost_returns_stored_status_without_rerunning(tmp_path):
    w = orch_world(tmp_path)
    env = envelope()
    first = await w.gw.submit_intent(env)
    dry_runs = len(w.apps.patches)
    again = await w.gw.submit_intent(env)
    assert again == first and len(w.apps.patches) == dry_runs
    other_id = envelope(intent_id="int-retry-with-new-id")
    assert (await w.gw.submit_intent(other_id)).intent_id == env.intent_id  # same execution: same intent


async def test_same_id_other_action_conflicts(tmp_path):
    w = orch_world(tmp_path)
    env = envelope()
    await w.gw.submit_intent(env)
    clash = envelope(intent_id=env.intent_id, target="checkout")
    with pytest.raises(Conflict):
        await w.gw.submit_intent(clash)


async def test_busy_slot_queues_instead_of_refusing_then_drains(tmp_path):
    w = orch_world(tmp_path)
    busy(w)
    env = envelope()
    sub = await w.gw.submit_intent(env)
    assert sub.status == "queued" and w.apps.patches == []  # nothing ran, not even a dry run
    assert not any(e["type"] in ("escalated", "handed_off") for e in w.events)
    await w.gw.drain_intents()
    assert w.gw.intents.get(env.intent_id)["status"] == "queued"  # still busy
    w.conn.execute("UPDATE receipts SET outcome='success'")
    w.conn.commit()
    await w.gw.drain_intents()
    assert w.gw.intents.get(env.intent_id)["status"] == "awaiting_approval"


async def test_queued_intent_with_stale_plan_is_superseded_not_run(tmp_path):
    w = orch_world(tmp_path)
    busy(w)
    env = envelope()
    await w.gw.submit_intent(env)
    w.conn.execute("UPDATE orchestration_workspaces SET plan_revision=1")
    w.conn.execute("UPDATE receipts SET outcome='success'")
    w.conn.commit()
    await w.gw.drain_intents()
    assert w.gw.intents.get(env.intent_id)["status"] == "superseded" and w.apps.patches == []


async def test_old_approval_cannot_authorise_a_new_plan(tmp_path):
    w = orch_world(tmp_path)
    sub = await w.gw.submit_intent(envelope())
    w.conn.execute("UPDATE orchestration_workspaces SET plan_revision=1")
    w.conn.commit()
    d = await w.gw.decide(sub.approval_id, "approved", "u1")
    assert (d.decision, d.failed_step) == ("refused", "approval") and d.reason.startswith("stale_plan")
    assert w.conn.execute("SELECT state FROM approvals").fetchone()[0] == "superseded"
    assert all(p["dry_run"] == "All" for p in w.apps.patches)  # never written
    decided = [e for e in w.events if e["type"] == "approval_decided"][-1]["payload"]
    assert decided["decision"] == "superseded"


async def test_busy_approval_semantics_unchanged(tmp_path):
    w = orch_world(tmp_path)
    sub = await w.gw.submit_intent(envelope())
    busy(w)
    d = await w.gw.decide(sub.approval_id, "approved", "u1")
    assert (d.decision, d.failed_step) == ("refused", "policy") and d.approval_id == sub.approval_id
    assert w.conn.execute("SELECT state FROM approvals").fetchone()[0] == "pending"
    assert w.gw.intents.get(sub.intent_id)["status"] == "awaiting_approval"


async def test_transport_failure_during_write_is_unknown_and_holds_slot(tmp_path):
    w = orch_world(tmp_path)
    sub = await w.gw.submit_intent(envelope())
    w.apps.fail_real = ConnectionResetError("peer reset")
    d = await w.gw.decide(sub.approval_id, "approved", "u1")
    assert d.decision == "escalated" and "outcome unknown" in d.reason
    assert w.gw.intents.get(sub.intent_id)["status"] == "execution_unknown"
    assert w.gw.slot_busy()  # nobody acts until a human checks
    writes = [p for p in w.apps.patches if p["dry_run"] is None]
    assert len(writes) == 1  # never retried
    assert (await w.gw.clear_intent(sub.intent_id, "stranger"))["cleared"] is False
    assert (await w.gw.clear_intent(sub.intent_id, "u1"))["cleared"] is True
    assert not w.gw.slot_busy()


async def test_restart_after_write_without_receipt_is_unknown_never_replayed(tmp_path):
    w = orch_world(tmp_path)
    env = envelope()
    await w.gw.submit_intent(env)
    # crash: intent marked executing, write sent, process died before the receipt row
    w.gw.intents.move(env.intent_id, "executing", executing_at=1000.0)
    patches = len(w.apps.patches)
    unknown = await w.gw.reconcile_intents()
    assert unknown == [env.intent_id] and len(w.apps.patches) == patches
    assert w.gw.intents.get(env.intent_id)["status"] == "execution_unknown"
    assert w.types()[-1] == "escalated" and w.gw.slot_busy()


async def test_restart_after_receipt_links_and_leaves_it_to_watchdog(tmp_path):
    w = orch_world(tmp_path)
    env = envelope()
    await w.gw.submit_intent(env)
    w.gw.intents.move(env.intent_id, "executing", executing_at=1000.0)
    w.conn.execute("INSERT INTO receipts (id, incident_id, ts, tool, target, outcome) "
                   "VALUES (7, 'inc-1', 1001, 'rollback_deploy', 'payment', 'pending')")
    w.conn.commit()
    assert await w.gw.reconcile_intents() == []
    row = w.gw.intents.get(env.intent_id)
    assert (row["status"], row["receipt_id"]) == ("verifying", 7)
    w.conn.execute("UPDATE receipts SET outcome='success' WHERE id=7")
    w.conn.commit()
    await w.gw.sync_intents()
    assert w.gw.intents.get(env.intent_id)["status"] == "terminal"


async def test_concurrent_submits_hold_one_slot(tmp_path):
    w = orch_world(tmp_path)
    w.conn.execute("INSERT INTO ledger (pattern, action, target, source, successes) VALUES "
                   "('recent_change', 'rollback_deploy', 'payment', 'real', 100)")
    w.conn.commit()
    a = envelope()
    b = envelope(prediction={"metric": "err_ratio", "target": "payment", "below": 0.04, "within_s": 90})
    results = await asyncio.gather(w.gw.submit_intent(a), w.gw.submit_intent(b))
    assert sorted(r.status for r in results) == ["queued", "verifying"]  # trusted fix runs, the other waits
    assert len([p for p in w.apps.patches if p["dry_run"] is None]) == 1
    for task in list(w.gw.tasks):
        task.cancel()


def test_scoped_severity_ignores_other_incident():
    health = {"severity": 4, "services": {"payment": {"unhealthy": True, "breaching": True, "bad_pods": 0},
                                          "shipping": {"unhealthy": False, "breaching": False, "bad_pods": 0}}}
    v = Verification(1000, health, "payment", [], None, 120, early_abort=True, scope={"payment"})
    worse = {"severity": 30, "prometheus_ok": True, "services": {
        "payment": {"unhealthy": True, "breaching": True, "bad_pods": 0},
        "shipping": {"unhealthy": True, "breaching": True, "bad_pods": 5}}}
    assert v.step(1100, worse, False) is None  # another outage: not this fix's harm
    legacy = Verification(1000, health, "payment", [], None, 120, early_abort=True)
    assert legacy.step(1100, worse, False) == "early_abort"


def test_harm_excuses_only_independently_evidenced_unrelated_services():
    before = {"services": {"shipping": {"unhealthy": False, "breaching": False, "bad_pods": 0},
                           "ad": {"unhealthy": False, "breaching": False, "bad_pods": 0}}}
    after = {"services": {"shipping": {"unhealthy": True, "breaching": True, "bad_pods": 0},
                          "ad": {"unhealthy": True, "breaching": True, "bad_pods": 0}}}
    h = harm_check({"deployment/payment": "a"}, {"deployment/payment": "b"}, "deployment/payment", set(), before,
                   after, {"payment"}, excused=frozenset({"shipping"}))
    assert h["worse_services"] == ["ad"] and h["unrelated_worse"] == ["shipping"] and h["clean"] is False


def test_as_decision_maps_queue_to_waiting():
    assert as_decision(IntentSubmission(intent_id="int-1", status="queued")).decision == "awaiting_approval"
    assert as_decision(IntentSubmission(intent_id="int-1", status="verifying", receipt_id=3)).receipt_id == 3
    assert as_decision(IntentSubmission(intent_id="int-1", status="superseded")).failed_step == "intent"
    assert as_decision(IntentSubmission(intent_id="int-1", status="execution_unknown")).decision == "escalated"


def test_routes_need_token_and_conflict_is_409(tmp_path):
    w = orch_world(tmp_path)
    env = envelope()
    with TestClient(create_app(w.gw)) as client:
        assert client.post("/orchestration/actions", json=env.model_dump(mode="json")).status_code == 401
        ok = client.post("/orchestration/actions", headers=auth.headers(), json=env.model_dump(mode="json"))
        assert ok.status_code == 200 and ok.json()["status"] == "awaiting_approval"
        clash = envelope(intent_id=env.intent_id, target="checkout")
        r = client.post("/orchestration/actions", headers=auth.headers(), json=clash.model_dump(mode="json"))
        assert r.status_code == 409
        got = client.get(f"/orchestration/actions/{env.intent_id}").json()
        assert got["status"] == "awaiting_approval" and got["action"]["target"] == "payment"
        assert "precondition_json" not in got


def test_routes_refused_when_orchestration_off(tmp_path):
    w = World(tmp_path)
    with TestClient(create_app(w.gw)) as client:
        r = client.post("/orchestration/actions", headers=auth.headers(), json=envelope().model_dump(mode="json"))
    assert r.status_code == 409


async def test_brain_submit_uses_stable_intent_id(tmp_path):
    from tests.test_orchestration_recovery import Clock, coordinated
    from tests.test_brain import World as BrainWorld

    sent = []

    class GatewayWorld(BrainWorld):
        def __call__(self, request):
            if request.url.path == "/orchestration/actions":
                body = json.loads(request.content)
                sent.append(body)
                return httpx.Response(200, json={"intent_id": body["intent_id"], "status": "queued"})
            return super().__call__(request)

    brain = coordinated(GatewayWorld(), tmp_path, Clock())
    coord = brain.coordinator
    coord.ws.conn.execute("INSERT INTO incidents (id, state, opened_at, onset_at) VALUES ('inc-9', 'open', 1, 1)")
    coord.ws.conn.execute("INSERT INTO orchestration_workspaces (incident_id, phase, plan_revision, created_at, "
                          "requests_limit, tool_calls_limit, specialists_limit) VALUES ('inc-9', 'investigating', 2, "
                          "1, 9, 24, 2)")
    coord.ws.conn.commit()
    act = ActionRequest.model_validate(action(incident_id="inc-9"))
    d1 = await coord.submit(act)
    d2 = await coord.submit(act)
    follow = await coord.submit(act.model_copy(update={"tool": "raise_limit", "params": {"memory": "512Mi"}}))
    assert d1.decision == d2.decision == follow.decision == "awaiting_approval"
    assert sent[0]["intent_id"] == sent[1]["intent_id"] and sent[0]["plan_revision"] == 2
    assert sent[2]["parent_intent_id"] == sent[0]["intent_id"] and sent[2]["intent_id"] != sent[0]["intent_id"]
