from fastapi.testclient import TestClient

from akira_mcp.report import incident_report, orchestration_summary
from chaos.shell import describe
from gateway.main import create_app
from schemas.orchestration import OrchestrationPolicy
from schemas.workspace import Workspace
from tests.test_action_intents import envelope, orch_world
from tests.test_gateway import World


def test_old_incident_detail_has_null_orchestration_and_list_is_unchanged(tmp_path):
    w = World(tmp_path)
    with TestClient(create_app(w.gw)) as client:
        detail = client.get("/incidents/inc-1").json()
        listed = client.get("/incidents").json()
    assert detail["orchestration"] is None
    assert {"incident", "approvals", "receipts", "events", "similar"} <= set(detail)
    assert "orchestration" not in listed[0]


async def test_detail_carries_workspace_snapshot_with_intents(tmp_path):
    w = orch_world(tmp_path)
    w.gw.workspace = Workspace(w.conn, OrchestrationPolicy(mode="coordinated"), w.gw.clock, lock=w.gw.lock)
    sub = await w.gw.submit_intent(envelope())
    with TestClient(create_app(w.gw)) as client:
        detail = client.get("/incidents/inc-1").json()
        listed = client.get("/incidents").json()
    o = detail["orchestration"]
    assert o["phase"] == "awaiting_gateway" and o["budget"]["requests_limit"] == 9
    assert [(i["intent_id"], i["status"], i["tool"]) for i in o["intents"]] == [
        (sub.intent_id, "awaiting_approval", "rollback_deploy")]
    assert listed[0]["orchestration"] == {"phase": "awaiting_gateway", "task_count": 0}


def test_report_summarises_orchestration_only_when_present():
    base = {"incident": {"id": "inc-1"}, "events": [], "receipts": [], "approvals": []}
    assert incident_report(base)["orchestration"] is None
    o = {"phase": "terminal", "memberships": [{"service": "cart"}, {"service": "checkout"}],
         "delegation": [{"explanation": "No specialist needed: shared cause valkey-cart already supported"}],
         "tasks": [], "findings": [], "budget": {"requests_used": 4}, "intents": []}
    s = orchestration_summary(o)
    assert s["services"] == ["cart", "checkout"] and s["model_requests"] == 4
    assert s["delegation"] == ["No specialist needed: shared cause valkey-cart already supported"]


def test_shell_describes_orchestration_events():
    assert describe("delegation_decided", {"status": "none_needed", "explanation": "No specialist needed"}) == (
        "info", "No specialist needed")
    tone, text = describe("action_intent_changed", {"intent_id": "int-1", "status": "execution_unknown",
                                                    "reason": "check the cluster"})
    assert tone == "bad" and "execution_unknown" in text and "check the cluster" in text
    assert describe("investigation_task_changed", {"task_id": "t1", "state": "failed"})[0] == "bad"
    assert "cart" in describe("incident_scope_changed", {"scope_revision": 1, "services": ["cart"]})[1]


def test_status_says_disabled_on_a_legacy_gateway(tmp_path):
    with TestClient(create_app(World(tmp_path).gw)) as client:
        s = client.get("/orchestration/status").json()
    assert (s["mode"], s["delegation_enabled"], s["phases"]) == ("disabled", False, {})


async def test_status_counts_open_phases_and_unknown_writes(tmp_path):
    w = orch_world(tmp_path)
    policy = OrchestrationPolicy(mode="coordinated")
    w.gw.orchestration, w.gw.workspace = policy, Workspace(w.conn, policy, w.gw.clock, lock=w.gw.lock)
    sub = await w.gw.submit_intent(envelope())
    w.gw.intents.move(sub.intent_id, "executing")
    w.gw.intents.move(sub.intent_id, "execution_unknown")
    with TestClient(create_app(w.gw)) as client:
        s = client.get("/orchestration/status").json()
    assert s["mode"] == "coordinated" and s["phases"] == {"awaiting_gateway": 1} and s["unknown_writes"] == 1
