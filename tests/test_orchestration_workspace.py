import sqlite3

import pytest

from schemas import migrations
from schemas.db import connect
from schemas.orchestration import (DelegationRecord, FindingResult, IncidentLink, Membership, OrchestrationPolicy,
                                   SignalAck, SignalEpisode)
from schemas.workspace import Conflict, Workspace


class Clock:
    def __init__(self, t: float = 1000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def ws(tmp_path):
    conn = connect(str(tmp_path / "o.db"), shared=True)
    migrations.migrate(conn)
    return Workspace(conn, OrchestrationPolicy(), clock=Clock())


def episode(eid="ep-000001", service="cart", rev=1, **kw):
    base = {"episode_id": eid, "service": service, "symptom": "errors", "first_breach_at": 990.0,
            "sustained_at": 1000.0, "last_observed_at": 1000.0, "source_revision": rev}
    return SignalEpisode.model_validate({**base, **kw})


def open_one(ws, inc="inc-a", services=("cart",)):
    eps = [episode(f"ep-{inc}-{s}", s) for s in services]
    for e in eps:
        ws.upsert_episode(e)
    with ws.tx() as c:
        ws.open_incident(c, {"id": inc, "opened_at": 1000.0, "onset_at": 990.0, "severity": 4.0},
                         [Membership(incident_id=inc, episode_id=e.episode_id, service=e.service,
                                     reason="independent", added_revision=0) for e in eps])
        ws.enqueue(c, f"evt-{inc}", "gateway", "incident_opened", inc, {"type": "incident_opened"})
    return eps


def test_episode_rejects_old_or_repeated_revision(ws):
    assert ws.upsert_episode(episode(rev=2))
    assert not ws.upsert_episode(episode(rev=2))
    assert not ws.upsert_episode(episode(rev=1, recovered_at=1010.0))
    assert ws.episode("ep-000001").recovered_at is None
    assert ws.upsert_episode(episode(rev=3, recovered_at=1010.0, last_observed_at=1010.0))
    assert ws.open_episodes() == [] and ws.max_source_revision() == 3


def test_open_incident_is_all_or_nothing(ws):
    ws.upsert_episode(episode())
    with pytest.raises(sqlite3.IntegrityError):
        with ws.tx() as c:
            ws.open_incident(c, {"id": "inc-a", "opened_at": 1, "onset_at": 1, "severity": 1},
                             [Membership(incident_id="inc-a", episode_id="ep-unknown", service="cart",
                                         reason="independent", added_revision=0)])
    assert ws.workspace("inc-a") is None
    assert ws.row("SELECT 1 FROM incidents WHERE id='inc-a'") is None


def test_open_incident_writes_gateway_row_workspace_and_outbox(ws):
    open_one(ws)
    assert ws.row("SELECT state FROM incidents WHERE id='inc-a'")[0] == "open"
    w = ws.workspace("inc-a")
    assert w["phase"] == "queued" and w["requests_limit"] == 9
    assert [r["event_id"] for r in ws.due("gateway")] == ["evt-inc-a"]
    assert ws.owner_of("ep-inc-a-cart") == "inc-a"


def test_one_owner_per_open_episode(ws):
    open_one(ws)
    with pytest.raises(sqlite3.IntegrityError):
        with ws.tx() as c:
            ws.open_incident(c, {"id": "inc-b", "opened_at": 1, "onset_at": 1, "severity": 1},
                             [Membership(incident_id="inc-b", episode_id="ep-inc-a-cart", service="cart",
                                         reason="independent", added_revision=0)])


def test_close_frees_episode_and_suppresses_until_recovered(ws):
    open_one(ws)
    with ws.tx() as c:
        assert ws.close_memberships(c, "inc-a") == ["ep-inc-a-cart"]
    assert ws.owner_of("ep-inc-a-cart") is None
    assert ws.row("SELECT suppressed FROM signal_episodes WHERE episode_id='ep-inc-a-cart'")[0] == 1


def test_cas_moves_once(ws):
    open_one(ws)
    assert ws.update("inc-a", 0, phase="investigating")
    assert not ws.update("inc-a", 0, phase="needs_human")
    assert ws.workspace("inc-a")["phase"] == "investigating"
    with pytest.raises(ValueError):
        ws.update("inc-a", 1, plan_revision=5)


def test_bump_scope_and_plan(ws):
    open_one(ws)
    with ws.tx() as c:
        assert ws.bump(c, "inc-a", "scope") == 1
        assert ws.bump(c, "inc-a", "plan") == 1
    assert ws.workspace("inc-a")["revision"] == 2


def test_links_are_canonical_and_upsert(ws):
    open_one(ws, "inc-a")
    open_one(ws, "inc-b", ("payment",))
    link = IncidentLink(incident_a="inc-a", incident_b="inc-b", relation="related", reason="unknown_topology")
    with ws.tx() as c:
        ws.link(c, link)
        ws.link(c, link)
    assert [lk.revision for lk in ws.links("inc-b")] == [1]


def test_snapshot_is_immutable(ws):
    ws.put_snapshot("snap:1", "k", "health", 1000, 1005, {"a": 1})
    ws.put_snapshot("snap:1", "k", "health", 1000, 1005, {"a": 1})  # same content: fine
    with pytest.raises(Conflict):
        ws.put_snapshot("snap:1", "k", "health", 1000, 1005, {"a": 2})
    assert ws.snapshot_payload("snap:1") == {"a": 1}


def test_delivered_ledger_is_per_run(ws):
    open_one(ws)
    ws.deliver("run-1", "inc-a", [("journal:41", None), ("query:x@ab", "snap:1")])
    ws.deliver("run-1", "inc-a", [("journal:41", None)])
    assert ws.delivered("run-1") == {"journal:41", "query:x@ab"}
    assert ws.delivered("run-2") == set()


def make_task(ws, task_id="t1", deadline=1100.0):
    with ws.tx() as c:
        ws.create_task(c, task_id, "inc-a", "q1", "change_causality", "fp1", 0, 0, {"scope": ["cart"]},
                       ["get_recent_changes"], deadline, 2, 6)


def test_task_lease_is_fenced(ws):
    open_one(ws)
    make_task(ws)
    token = ws.claim_task("t1", "w1", 0)
    assert token == 1
    assert ws.claim_task("t1", "w2", 0) is None  # already running
    assert ws.heartbeat("t1", token)
    ws.clock.t += 31
    assert ws.expire_leases() == ["t1"]
    finding = FindingResult(question_id="q1", hypothesis_id="c2", verdict="supported", summary="flag broke cart")
    assert ws.complete_task("t1", token, "succeeded", finding) == "stale"  # late result never lands
    assert ws.finding_for("fp1") is None
    assert not ws.heartbeat("t1", token)


def test_task_completion_records_finding(ws):
    open_one(ws)
    make_task(ws)
    token = ws.claim_task("t1", "w1", 0)
    finding = FindingResult(question_id="q1", hypothesis_id="c2", verdict="refuted", summary="decoy only")
    assert ws.complete_task("t1", token, "succeeded", finding) == "accepted"
    assert ws.complete_task("t1", token, "succeeded", finding) == "stale"
    assert ws.finding_for("fp1").verdict == "refuted"
    snap = ws.snapshot("inc-a")
    assert snap.tasks[0].state == "succeeded" and snap.findings[0].summary == "decoy only"


def test_task_past_deadline_cannot_be_claimed(ws):
    open_one(ws)
    make_task(ws, deadline=1000.0)
    assert ws.claim_task("t1", "w1", 0) is None


def test_cancel_tasks(ws):
    open_one(ws)
    make_task(ws)
    with ws.tx() as c:
        assert ws.cancel_tasks(c, "inc-a", "incident_terminal") == ["t1"]
    assert ws.task("t1")["state"] == "cancelled"


def test_call_budget_keeps_commander_reserve(ws):
    open_one(ws)
    for i in range(7):  # 9 total, 2 kept for the commander
        assert ws.reserve_call(f"c{i}", "inc-a", "run-1", "specialist", "t1") is None
    assert ws.reserve_call("c7", "inc-a", "run-1", "specialist", "t1") == "request_budget"
    assert ws.reserve_call("c7", "inc-a", "run-c", "commander") is None
    assert ws.reserve_call("c8", "inc-a", "run-c", "commander") is None
    assert ws.reserve_call("c9", "inc-a", "run-c", "commander") == "request_budget"


def test_call_budget_per_task(ws):
    open_one(ws)
    assert ws.reserve_call("c1", "inc-a", "r", "specialist", "t1", task_limit=1) is None
    assert ws.reserve_call("c2", "inc-a", "r", "specialist", "t1", task_limit=1) == "request_budget"


def test_failed_and_unknown_calls_still_count(ws):
    open_one(ws)
    ws.reserve_call("c1", "inc-a", "r", "commander")
    assert ws.settle_call("c1", "error", error="http_500")
    assert not ws.settle_call("c1", "ok", 10, 10)  # exactly once
    ws.reserve_call("c2", "inc-a", "r", "commander")
    assert ws.orphan_calls_unknown() == 1
    b = ws.budget("inc-a")
    assert b.requests_used == 2 and b.unknown_calls == 1


def test_token_budget(tmp_path):
    conn = connect(str(tmp_path / "t.db"), shared=True)
    migrations.migrate(conn)
    ws = Workspace(conn, OrchestrationPolicy(max_total_tokens=1000), clock=Clock())
    open_one(ws)
    assert ws.reserve_call("c1", "inc-a", "r", "commander", reserved_tokens=600) is None
    assert ws.reserve_call("c2", "inc-a", "r", "commander", reserved_tokens=600) == "token_budget"
    ws.settle_call("c1", "ok", 100, 50)  # still charged the larger reservation
    assert ws.reserve_call("c2", "inc-a", "r", "commander", reserved_tokens=500) == "token_budget"


def test_outbox_backoff_and_delivery(ws):
    open_one(ws)
    ws.mark_failed("evt-inc-a", "ConnectError")
    assert ws.due("gateway") == []
    ws.clock.t += 1
    assert [r["attempts"] for r in ws.due("gateway")] == [1]
    ws.mark_delivered("evt-inc-a")
    assert ws.due("gateway") == [] and ws.pending_count("gateway") == 0


def test_coordinator_lease_single_owner(ws):
    assert ws.acquire_coordinator("brain-1", 30) == 1
    assert ws.acquire_coordinator("brain-2", 30) is None
    assert ws.renew_coordinator("brain-1", 1, 30)
    ws.clock.t += 31
    assert ws.acquire_coordinator("brain-2", 30) == 2
    assert not ws.renew_coordinator("brain-1", 1, 30)


def test_signal_delivery_ack_is_stored(ws):
    with ws.tx() as c:
        ws.record_delivery(c, SignalAck(delivery_id="deliv-01", accepted=2))
    assert ws.delivery("deliv-01").accepted == 2
    assert ws.delivery("deliv-02") is None


def test_snapshot_projection(ws):
    open_one(ws, "inc-a", ("cart", "checkout"))
    with ws.tx() as c:
        ws.record_delegation(c, "inc-a", DelegationRecord(status="none_needed", ts=1000.0,
                                                          explanation="shared dependency already supported"))
    snap = ws.snapshot("inc-a")
    assert snap.phase == "queued" and [m.service for m in snap.memberships] == ["cart", "checkout"]
    assert snap.delegation[0].status == "none_needed" and snap.budget.requests_limit == 9
    assert ws.snapshot("inc-none") is None
