import asyncio
import json

from gateway import blast
from test_gateway import World, action
from test_verify_loop import Script, healthy

SERVICES = {"frontend": {"critical": True}, "checkout": {"critical": True}, "ad": {"critical": False}}
POLICY = {"net_benefit": {"max_added_harm_seconds": 30, "min_benefit_ratio": 2.0}}
EDGES = [("frontend", "checkout", 1.0), ("checkout", "payment", 1.0), ("ad", "payment", 1.0)]


def test_blast_radius_forecast_and_net_benefit():
    health = {"services": {"checkout": {"unhealthy": True}, "frontend": {"unhealthy": False}}}
    r = blast.blast_radius("payment", EDGES, health)
    assert r == {"upstream": ["ad", "checkout", "frontend"], "healthy_affected": ["ad", "frontend"]}
    assert blast.forecast_added_seconds("rollback_deploy", 2, True, 40) == 0
    assert blast.forecast_added_seconds("rollback_deploy", 1, True, 40) == 40
    assert blast.forecast_added_seconds("scale", 1, False, 40) == 0
    ok, nb = blast.net_benefit(10, r, 20, SERVICES, POLICY)  # 20 s x 1 critical healthy caller = 20 added
    assert not ok and nb["added"] == 20
    assert blast.net_benefit(40, r, 20, SERVICES, POLICY)[0]
    assert not blast.net_benefit(1000, r, 31, SERVICES, POLICY)[0]  # over the per-service harm cap


def test_startup_and_surge():
    pod = {"metadata": {"creationTimestamp": "2026-11-13T00:00:00Z"},
           "status": {"conditions": [{"type": "Ready", "status": "True", "lastTransitionTime": "2026-11-13T00:00:12Z"}]}}
    assert blast.startup_seconds([pod]) == 12 and blast.startup_seconds([]) == blast.DEFAULT_STARTUP_S
    assert blast.surge_ok({"spec": {"strategy": {"type": "RollingUpdate", "rollingUpdate": {"maxUnavailable": 0}}}})
    assert not blast.surge_ok({"spec": {}})


class FakeGraph:
    def __init__(self, edges=None, fail=False):
        self.edges, self.fail = edges or [], fail

    async def get(self):
        if self.fail:
            import httpx
            raise httpx.ConnectError("down")
        return self.edges


def single_replica(w):
    w.apps.dep["spec"]["replicas"] = 1
    w.apps.dep["spec"]["strategy"] = {"type": "Recreate"}


async def test_costly_action_asks_at_net_benefit_then_runs_after_approval(tmp_path):
    w = World(tmp_path)
    single_replica(w)
    w.gw.graph = FakeGraph([("frontend", "payment", 1.0)])
    w.obs.unhealthy = True
    d = await w.gw.submit(action())
    assert (d.decision, d.failed_step) == ("awaiting_approval", "net_benefit")
    req = next(e for e in w.events if e["type"] == "approval_requested")["payload"]
    assert "frontend" in req["forecast"] and "30 s" in req["forecast"]
    w.gw.verify_every = 3600
    d = await w.gw.decide(d.approval_id, "approved", "u1")
    assert d.decision == "executed"
    step = next(e for e in reversed(w.events) if e["type"] == "checklist_step"
                and e["payload"]["name"] == "net_benefit")["payload"]
    assert step["passed"] and "accepted by approver" in step["reason"]
    blast_json = w.conn.execute("SELECT blast_json FROM receipts").fetchone()[0]
    assert json.loads(blast_json)["healthy_affected"] == ["frontend"]
    for t in w.gw.tasks:
        t.cancel()


async def test_unknown_graph_with_capacity_cost_asks(tmp_path):
    w = World(tmp_path)
    single_replica(w)
    w.gw.graph = FakeGraph(fail=True)
    d = await w.gw.submit(action())
    assert d.failed_step == "net_benefit" and "unknown" in d.reason


async def executed_and_parked(tmp_path):
    w = World(tmp_path)
    d = await w.gw.submit(action())
    w.gw.verify_every = 3600  # verifier parked: no heartbeats after the first
    d = await w.gw.decide(d.approval_id, "approved", "u1")
    await asyncio.sleep(0)
    return w, d


async def test_watchdog_undoes_silent_verification(tmp_path):
    w, d = await executed_and_parked(tmp_path)
    w.now[0] += 100
    assert await w.gw.watchdog() == 0  # too young
    w.now[0] += 100
    assert await w.gw.watchdog() == 1
    assert w.apps.dep["spec"]["template"]["spec"]["containers"][0]["image"] == "payment:v2-bad"
    undone = next(e for e in w.events if e["type"] == "action_undone")["payload"]
    assert undone == {"receipt_id": d.receipt_id, "reason": "watchdog"}
    assert w.types()[-1] == "escalated"
    assert w.conn.execute("SELECT outcome FROM receipts").fetchone()[0] == "undone"
    assert [tuple(r) for r in w.conn.execute("SELECT source, failures FROM ledger")] == [("real", 1)]
    assert await w.gw.watchdog() == 0  # only once
    assert not w.gw.tasks or all(t.cancelled() or t.done() for t in w.gw.tasks)


async def test_watchdog_leaves_ticking_verifier_alone(tmp_path):
    w, d = await executed_and_parked(tmp_path)
    w.now[0] += 200
    w.gw.heartbeats[d.receipt_id] = w.now[0] - 5
    assert await w.gw.watchdog() == 0
    for t in w.gw.tasks:
        t.cancel()


async def test_failed_watchdog_undo_keeps_blocking(tmp_path):
    from kubernetes.client.rest import ApiException
    w, d = await executed_and_parked(tmp_path)
    w.apps.fail_real = ApiException(status=403, reason="forbidden")
    w.now[0] += 200
    assert await w.gw.watchdog() == 1
    assert w.conn.execute("SELECT outcome FROM receipts").fetchone()[0] == "watchdog_failed"
    assert w.gw.receipts.get(d.receipt_id).outcome == "undo_failed"  # /receipts page; was stuck "pending" (A)
    assert "UNDO FAILED" in w.events[-1]["payload"]["briefing"]
    w.apps.fail_real = None
    again = await w.gw.submit(action())
    assert (again.decision, again.failed_step) == ("refused", "policy")


# the block had no way out but editing the database by hand (live, twice); an approver can now clear it
async def test_approver_clears_failed_watchdog_receipt(tmp_path):
    from kubernetes.client.rest import ApiException
    w, d = await executed_and_parked(tmp_path)
    w.apps.fail_real = ApiException(status=403, reason="forbidden")
    w.now[0] += 200
    assert await w.gw.watchdog() == 1
    w.apps.fail_real = None
    assert await w.gw.clear_receipt(d.receipt_id, "stranger") == {"cleared": False, "reason": "not an approver"}
    assert await w.gw.clear_receipt(999, "u1") == {"cleared": False, "reason": "unknown receipt"}
    assert await w.gw.clear_receipt(d.receipt_id, "u1") == {"cleared": True}
    assert w.events[-1]["payload"]["name"] == "human_clear"
    assert w.conn.execute("SELECT outcome FROM receipts").fetchone()[0] == "undo_failed"
    assert (await w.gw.clear_receipt(d.receipt_id, "u1"))["cleared"] is False  # only once
    again = await w.gw.submit(action())
    assert again.failed_step != "policy"
    for t in w.gw.tasks:
        t.cancel()


async def test_expired_approvals_are_swept(tmp_path):
    w = World(tmp_path)
    d = await w.gw.submit(action())
    assert await w.gw.expire_approvals() == 0
    w.now[0] += 301
    assert await w.gw.expire_approvals() == 1
    assert w.conn.execute("SELECT state FROM approvals").fetchone()[0] == "expired"
    assert w.types()[-2:] == ["checklist_step", "escalated"]
    assert (await w.gw.decide(d.approval_id, "approved", "u1")).reason == "approval is expired"


async def test_raise_limit_can_queue_approval_while_restart_verifies(tmp_path):
    w = World(tmp_path)
    w.apps.dep["spec"]["template"]["spec"]["containers"][0]["resources"] = {"limits": {"memory": "256Mi"}}
    w.gw.verify_every = 3600
    d = await w.gw.submit(action(tool="restart_service", pattern="resource", journal_entry=None))
    await w.gw.decide(d.approval_id, "approved", "u1")
    follow = await w.gw.submit(action(tool="raise_limit", pattern="resource", journal_entry=None,
                                      params={"memory": "512Mi"}))
    assert follow.decision == "awaiting_approval"
    blocked = await w.gw.decide(follow.approval_id, "approved", "u1")
    assert (blocked.decision, blocked.failed_step) == ("refused", "policy") and "approval kept" in blocked.reason
    assert w.conn.execute("SELECT state FROM approvals WHERE id=?", (follow.approval_id,)).fetchone()[0] == "pending"
    assert "escalated" not in w.types()
    for t in w.gw.tasks:
        t.cancel()


async def test_restart_success_card_says_mitigated(tmp_path):
    import httpx
    w = World(tmp_path)
    script = Script(w, [healthy()])
    w.gw.http = httpx.AsyncClient(transport=httpx.MockTransport(script))
    d = await w.gw.submit(action(tool="restart_service", pattern="resource", journal_entry=None, prediction=None))
    w.gw.verify_every = 0
    d = await w.gw.decide(d.approval_id, "approved", "u1")
    script.active = True
    await asyncio.wait_for(next(iter(w.gw.tasks)), 5)
    assert w.events[-1]["type"] == "incident_resolved"
    assert w.events[-1]["payload"]["card"]["status"] == "MITIGATED, NOT FIXED"


# e2e: gateway restart while verifying valkey-cart 0 -> 1 (inverse "none"). The watchdog tried an undo that
# cannot exist, marked watchdog_failed and blocked every later action. Now: keep the fix, page, don't block
async def test_watchdog_keeps_fix_with_no_safe_undo_and_does_not_block(tmp_path):
    w, d = await executed_and_parked(tmp_path)
    w.conn.execute("UPDATE receipts SET inverse_json=? WHERE id=?",
                   (json.dumps({"op": "none", "target": "payment", "why": "undo would scale to 0"}), d.receipt_id))
    writes = len(w.apps.patches)
    w.now[0] += 200
    assert await w.gw.watchdog() == 1
    assert len(w.apps.patches) == writes  # no undo attempted
    assert w.conn.execute("SELECT outcome FROM receipts").fetchone()[0] == "handed_off"
    assert w.types()[-1] == "escalated" and "fix kept" in w.events[-1]["payload"]["briefing"]
    assert "action_undone" not in w.types()
    assert [tuple(r) for r in w.conn.execute("SELECT source, failures FROM ledger")] == []
    from gateway import policy
    assert policy.usage(w.conn, "inc-1", w.now[0])["in_flight"] == 0  # nothing left blocking
