import json

from kubernetes.client.rest import ApiException

from brain.major import analyse, is_major, shared_change
from schemas import config
from test_gateway import World, action

POLICY = config.load("policy")
EDGES = [("frontend", "checkout", 1.0), ("checkout", "kafka", 1.0), ("checkout", "cart", 1.0),
         ("accounting", "kafka", 1.0), ("fraud-detection", "kafka", 1.0), ("cart", "valkey-cart", 1.0)]


def test_is_major_by_count_and_spread():
    fb = {"checkout": 100, "accounting": 110, "fraud-detection": 120, "frontend": 130}
    assert is_major(list(fb), fb, 20, POLICY)
    assert not is_major(["checkout", "accounting"], fb, 20, POLICY)
    spread = {**fb, "frontend": 400}  # outside 120 s of the first
    assert not is_major(list(spread), spread, 20, POLICY)
    assert is_major(["a", "b", "c"], {"a": 1, "b": 2, "c": 3}, 9, POLICY)  # 3/9 >= 30%


def test_shared_change_ranked_before_shared_dependency():
    journal = [{"id": 5, "object": "deployment/kafka", "kind": "replicas", "ts": 90.0, "by_agent": False},
               {"id": 4, "object": "deployment/ad", "kind": "image", "ts": 10.0, "by_agent": False},
               {"id": 6, "object": "deployment/kafka", "kind": "replicas", "ts": 95.0, "by_agent": True}]
    unhealthy = ["checkout", "accounting", "fraud-detection"]
    ranked = analyse(unhealthy, EDGES, {"checkout": 100, "accounting": 101, "fraud-detection": 102}, journal, 100, 60)
    assert [(c["kind"], c["target"]) for c in ranked] == [("shared_change", "kafka")]
    assert ranked[0]["journal_entry"] == 5 and ranked[0]["failure_order"] == unhealthy
    assert shared_change(journal, 100, 600)["id"] == 5
    no_change = analyse(unhealthy, EDGES, {}, [], 100, 60)
    assert [(c["kind"], c["target"]) for c in no_change] == [("shared_dependency", "kafka")]


def major_world(tmp_path):
    w = World(tmp_path)
    w.conn.execute("UPDATE incidents SET major=1, culprit='payment'")
    w.gw.verify_every = 3600
    return w


async def test_major_only_root_cause_and_always_asks(tmp_path):
    w = major_world(tmp_path)
    d = await w.gw.submit(action(target="checkout", tool="restart_service", pattern="resource", journal_entry=None))
    assert (d.decision, d.failed_step) == ("refused", "policy") and "root cause" in d.reason
    w.conn.execute("INSERT INTO ledger (pattern, action, target, source, successes) "
                   "VALUES ('resource', 'restart_service', 'payment', 'rehearsal', 60)")
    d = await w.gw.submit(action(tool="restart_service", pattern="resource", journal_entry=None))
    assert d.decision == "awaiting_approval" and "major incident" in d.reason  # trust open, still asks


async def test_major_revert_of_shared_change_may_run_auto(tmp_path):
    w = major_world(tmp_path)
    w.conn.execute("INSERT INTO ledger (pattern, action, target, source, successes) "
                   "VALUES ('recent_change', 'rollback_deploy', 'payment', 'rehearsal', 60)")
    d = await w.gw.submit(action())  # journal 41 is the change closest before onset
    assert d.decision == "executed"
    for t in w.gw.tasks:
        t.cancel()


async def test_major_one_restart_and_no_scale_up(tmp_path):
    w = major_world(tmp_path)
    w.conn.execute("INSERT INTO receipts (id, incident_id, ts, tool, target, outcome) "
                   "VALUES (99, 'inc-1', 0, 'restart_service', 'payment', 'success')")
    d = await w.gw.submit(action(tool="restart_service", pattern="resource", journal_entry=None))
    assert d.failed_step == "policy" and "one restart" in d.reason
    d = await w.gw.submit(action(tool="scale", pattern="resource", journal_entry=None, params={"replicas": 3}))
    assert (d.decision, d.failed_step, d.reason) == ("refused", "dry_run", "major incident: no scale up")


async def test_admission_denial_publishes_blocked(tmp_path):
    w = World(tmp_path)
    w.apps.fail_dry = ApiException(status=422, reason="denied request: agent may not change volumes")
    d = await w.gw.submit(action())
    blocked = next(e for e in w.events if e["type"] == "blocked")["payload"]
    assert blocked["step"] == "dry_run" and "may not change volumes" in blocked["reason"]
    assert d.decision == "escalated" and w.types()[-1] == "escalated"


async def test_brain_kafka_outage_is_major_and_protected(tmp_path):
    import httpx

    from test_brain import World as BrainWorld, diagnosis_json, make
    from schemas.models import Incident

    class KafkaWorld(BrainWorld):
        def __call__(self, request):
            if request.url.path == "/health/now":
                return httpx.Response(200, json={"ts": 1000.0, "services": {
                    s: {"err_ratio": 0.5, "first_breach_ts": 960.0 + i, "unhealthy": True}
                    for i, s in enumerate(["checkout", "accounting", "fraud-detection", "frontend"])}})
            if request.url.path == "/journal":
                return httpx.Response(200, json=[{"id": 9, "object": "deployment/kafka", "kind": "replicas",
                                                  "ts": 950.0, "field_manager": "chaos-panel", "by_agent": False,
                                                  "diff": {"replicas": {"old": 1, "new": 0}}}])
            if request.url.path.endswith("/api/dependencies"):
                return httpx.Response(200, json={"data": [{"parent": p, "child": c, "callCount": 1}
                                                          for p, c, _ in EDGES]})
            return super().__call__(request)

    world = KafkaWorld()
    brain = make(world, [diagnosis_json(causes=[], prediction=None)], tmp_path)
    inc = Incident(id="inc-1", opened_at=990, onset_at=960,
                   unhealthy=["checkout", "accounting", "fraud-detection", "frontend"], severity=12)
    record = await brain.handle(inc)
    assert record["incident"]["major"] and record["incident"]["culprit"] == "kafka"
    assert record["pattern"] == "protected"
    assert [(a.tool, a.target, a.params) for a in brain.submitted] == [("scale", "kafka", {"replicas": 1})]
    major_ev = next(e for e in world.published if e["type"] == "major_incident")
    assert major_ev["payload"]["ranked"][0]["kind"] == "shared_change"
    assert brain.conn.execute("SELECT major FROM incidents").fetchone()[0] == 1
    assert json.loads(brain.conn.execute("SELECT victims_json FROM incidents").fetchone()[0])[0] == "accounting"
