import json

import pytest

from brain import memory
from brain.agent import AgentDiagnosisService
from pydantic_ai.models.function import FunctionModel
from schemas import migrations
from schemas.db import connect
from schemas.orchestration import OrchestrationPolicy
from schemas.workspace import Workspace
from tests.test_agent import RULE, Script, call, final
from tests.test_agent_tools import make_box


@pytest.fixture
def ws(tmp_path):
    conn = connect(str(tmp_path / "x.db"), shared=True)
    migrations.migrate(conn)
    return Workspace(conn, OrchestrationPolicy(), clock=lambda: 1000.0)


def incident(ws, iid, outcome, tool="rollback_deploy", target="payment", pattern="recent_change", rid=None):
    ws.conn.execute("INSERT INTO incidents (id, opened_at, onset_at, pattern, state) VALUES (?, 1, 1, ?, 'resolved')",
                    (iid, pattern))
    ws.conn.execute("INSERT INTO receipts (id, incident_id, ts, tool, target, diff_json, outcome) VALUES "
                    "(?, ?, 1, ?, ?, ?, ?)", (rid, iid, tool, target, json.dumps({"spec.image": 1}), outcome))
    ws.conn.commit()


def test_records_fix_outcome_once(ws):
    incident(ws, "inc-1", "success", rid=1)
    first = ws.record_experience("inc-1")
    assert first == ws.record_experience("inc-1") == "exp-inc-1-1"
    row = ws.row("SELECT * FROM experience_records")
    assert (row["tool"], row["service"], row["outcome"], row["status"]) == ("rollback_deploy", "payment", "success",
                                                                            "active")
    assert json.loads(row["applicability_json"]) == {"service": "payment", "diff_paths": ["spec.image"]}


def test_unfinished_verification_is_not_experience(ws):
    incident(ws, "inc-1", "pending", rid=1)
    assert ws.record_experience("inc-1") is None
    ws.conn.execute("INSERT INTO incidents (id, state) VALUES ('inc-2', 'escalated')")
    ws.conn.commit()
    assert ws.record_experience("inc-2") is None  # no fix, no lesson about a fix


def test_contradicting_outcome_retires_the_old_lesson(ws):
    incident(ws, "inc-1", "success", rid=1)
    ws.record_experience("inc-1")
    incident(ws, "inc-2", "undone", rid=2)
    ws.record_experience("inc-2")
    rows = {r["source_incident_id"]: r["status"] for r in ws.rows("SELECT * FROM experience_records")}
    assert rows == {"inc-1": "superseded", "inc-2": "active"}
    incident(ws, "inc-3", "undone", rid=3)  # agreeing outcome: both stay
    ws.record_experience("inc-3")
    assert ws.row("SELECT status FROM experience_records WHERE source_incident_id='inc-2'")[0] == "active"


def test_lessons_from_other_services_need_fresh_confirmation(ws):
    incident(ws, "inc-1", "success", target="cart", rid=1)
    incident(ws, "inc-2", "success", target="payment", rid=2)
    ws.record_experience("inc-1")
    ws.record_experience("inc-2")
    lessons = memory.experience(ws.conn, "recent_change", "payment")
    assert [(e["fix"], e["requires_fresh_confirmation"]) for e in lessons] == [
        ("rollback_deploy payment", False), ("rollback_deploy cart", True)]
    assert memory.experience(ws.conn, None, "payment") == []


def test_no_experience_table_means_no_lessons():
    assert memory.experience(connect(":memory:"), "recent_change", "payment") == []


async def test_brief_carries_experience_only_when_given():
    lessons = [{"fix": "rollback_deploy cart", "outcome": "undone", "incident_id": "inc-9",
                "requires_fresh_confirmation": True}]
    with_it = Script(lambda m, i: call("get_recent_changes"), lambda m, i: final(i))
    await AgentDiagnosisService(FunctionModel(with_it)).diagnose(make_box(), "recent_change", RULE,
                                                                 {"experience": lessons})
    assert "requires_fresh_confirmation" in str(with_it.seen[0][0])
    without = Script(lambda m, i: call("get_recent_changes"), lambda m, i: final(i))
    await AgentDiagnosisService(FunctionModel(without)).diagnose(make_box(), "recent_change", RULE, {})
    assert "experience" not in str(without.seen[0][0])


async def test_terminal_close_records_experience(tmp_path):
    from tests.test_brain import World
    from tests.test_orchestration_recovery import Clock, batch, coordinated, ep, settle

    brain = coordinated(World(), tmp_path, Clock())
    coord = brain.coordinator
    await coord.start()
    await coord.on_signals(batch(ep("payment")))
    [iid] = coord.ws.unfinished()
    await settle(coord)
    coord.ws.conn.execute("UPDATE incidents SET pattern='recent_change' WHERE id=?", (iid,))
    coord.ws.conn.execute("INSERT INTO receipts (id, incident_id, ts, tool, target, outcome) "
                          "VALUES (5, ?, 1, 'rollback_deploy', 'payment', 'success')", (iid,))
    coord.ws.conn.commit()
    coord.on_terminal(iid)
    assert coord.ws.row("SELECT outcome FROM experience_records WHERE source_incident_id=?", (iid,))[0] == "success"
