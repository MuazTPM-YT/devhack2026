"""Property tests (IMPLEMENTATION.md §8.2): random and hostile requests + cluster states against the checklist.

ponytail: stdlib `random` with fixed seeds instead of Hypothesis (no new dependency); no shrinking, so a failure
prints the seed and case to replay.
"""
import json
import random

import httpx

from kubernetes.client.rest import ApiException

from gateway import trust
from gateway.mcp_server import TOOLS
from schemas import config
from test_gateway import World

SERVICES = config.load("services")["services"]
POLICY = config.load("policy")
CASES = 2000
FORBIDDEN_VERBS = ("delete", "create", "replace", "update", "connect")


class SickObserver:
    """Fake observer whose health marks a random set of services unhealthy (protected ones included)."""

    def __init__(self, inner, sick):
        self.inner, self.sick = inner, sick

    def __call__(self, request):
        if request.url.path == "/health/now":
            return httpx.Response(200, json={"ts": 1000.0, "severity": 4, "services": {
                svc: {"unhealthy": svc in self.sick, "err_ratio": 0.4 if svc in self.sick else 0.0}
                for svc in SERVICES}})
        return self.inner(request)


class Recorder:
    """Wraps the fake API client and records every method the gateway touches."""

    def __init__(self, inner):
        self.inner, self.calls = inner, []

    def __getattr__(self, name):
        self.calls.append(name)
        return getattr(self.inner, name)


def random_action(rng: random.Random) -> dict:
    tool = rng.choice(TOOLS + ["delete_deployment", "exec_pod", ""])
    a = {"incident_id": rng.choice(["inc-1", "inc-1", "inc-missing"]), "tool": tool,
         "target": rng.choice(list(SERVICES) + ["unknown-svc", "kube-apiserver", ""]),
         "pattern": rng.choice(["recent_change", "resource", "protected", "unknown", "bogus"]),
         "evidence_ids": rng.choice([["journal:41"], [], ["event:x", "trace:y"]]),
         "journal_entry": rng.choice([None, 41, 999]),
         "params": rng.choice([{}, {"replicas": rng.randint(-1, 6)}, {"memory": rng.choice(["64Mi", "512Mi",
                                                                                          "2Gi", "abc"])},
                               {"replicas": "3"}, {"memory": "300Mi", "container": "nope"}])}
    if rng.random() < 0.5:  # half the cases look almost valid, so they reach the deep steps
        a.update({"incident_id": "inc-1", "target": rng.choice(["payment", "payment", "cart", "valkey-cart"]),
                  "tool": rng.choice(["rollback_deploy", "rollback_deploy", "restart_service", "scale"]),
                  "evidence_ids": ["journal:41"]})
        if a["tool"] == "rollback_deploy":
            a.update({"pattern": "recent_change", "journal_entry": 41})
    if rng.random() < 0.05:
        a["extra_field"] = "smuggled"
    if rng.random() < 0.05:
        del a["evidence_ids"]
    return a


async def run_case(tmp_path, rng: random.Random) -> list[str]:
    w = World(tmp_path)
    w.gw.verify_every = 10**9
    rec = Recorder(w.apps)
    w.gw.apps = rec
    core = Recorder(w.core)
    w.gw.core = core
    now = w.now[0]

    # random cluster / history state
    major = rng.random() < 0.2
    w.conn.execute("UPDATE incidents SET major=?, culprit=?", (int(major), rng.choice(["payment", "cart", None])))
    prior = rng.randint(0, 4)
    for i in range(prior):
        w.conn.execute("INSERT INTO receipts (id, incident_id, ts, tool, target, outcome) VALUES (?, 'inc-1', ?, "
                       "'rollback_deploy', 'payment', ?)", (10_000 + i, now - rng.choice([10, 7200]),
                                                            rng.choice(["success", "undone", "pending"])))
    successes, failures = rng.choice([0, 28, 60]), rng.choice([0, 0, 1])
    for key in [("recent_change", "rollback_deploy", "payment"), ("resource", "restart_service", "payment")]:
        w.conn.execute("INSERT INTO ledger (pattern, action, target, source, successes, failures) VALUES "
                       "(?, ?, ?, 'rehearsal', ?, ?)", (*key, successes, failures))
    w.conn.commit()
    w.obs.unhealthy = rng.random() < 0.8
    sick = {svc for svc in SERVICES if rng.random() < 0.5} | ({"payment"} if w.obs.unhealthy else set())
    sick -= set() if w.obs.unhealthy else {"payment"}
    w.gw.http = httpx.AsyncClient(transport=httpx.MockTransport(SickObserver(w.obs, sick)))
    if rng.random() < 0.15:
        w.obs.journal.append({"id": 77, "object": "deployment/payment", "kind": "replicas", "ts": 995.0,
                              "field_manager": "kubectl", "by_agent": False, "diff": {}})
    if rng.random() < 0.1:
        w.apps.fail_dry = ApiException(status=rng.choice([403, 409, 422, 500]), reason="no")
    if rng.random() < 0.1:
        w.apps.fail_real = ApiException(status=rng.choice([403, 409, 422]), reason="no")

    def counts():
        r = w.conn.execute("SELECT COUNT(*) FROM receipts WHERE incident_id='inc-1'").fetchone()[0]
        h = w.conn.execute("SELECT COUNT(*) FROM receipts WHERE ts >= ?", (w.now[0] - 3600,)).fetchone()[0]
        f = w.conn.execute("SELECT COUNT(*) FROM receipts WHERE outcome IN ('pending','watchdog_failed')").fetchone()[0]
        return r, h, f

    before = counts()
    violations: list[str] = []
    raw = random_action(rng)
    n_events = len(w.events)
    d = await w.gw.submit(raw)
    calls = [(d, False)]
    if n_events == len(w.events):
        violations.append("8: submit produced no audit event")
    if d.decision == "awaiting_approval" and rng.random() < 0.7:
        w.now[0] += rng.choice([0, 0, 400])  # sometimes too late
        n_events = len(w.events)
        d2 = await w.gw.decide(d.approval_id, rng.choice(["approved", "approved", "rejected"]),
                               rng.choice(["u1", "u1", "stranger"]))
        calls.append((d2, True))
        if n_events == len(w.events) and d2.failed_step != "approval":
            violations.append("8: decide produced no audit event")
    for t in list(w.gw.tasks):
        t.cancel()

    executed = [(dec, via_approval) for dec, via_approval in calls if dec.decision == "executed"]
    names = rec.calls + core.calls
    if bad := [n for n in names if n.startswith(FORBIDDEN_VERBS)]:
        violations.append(f"1: forbidden API calls {bad}")
    for dec, via_approval in executed:
        row = w.conn.execute("SELECT * FROM receipts WHERE id=?", (dec.receipt_id,)).fetchone()
        svc = SERVICES.get(row["target"], {})
        if not svc.get("actable") or svc.get("protected"):
            violations.append(f"2: executed on {row['target']}")
        view = w.gw.receipts.get(dec.receipt_id)
        if view is None or not view.inverse or not json.loads(row["inverse_json"]):
            violations.append("7: executed without a receipt inverse")
        if not via_approval:
            tool_cfg = POLICY["tools"][row["tool"]]
            gate = trust.lower_bound(successes, failures) >= POLICY["trust"]["bar"]
            if not gate or raw["pattern"] == "unknown" or not trust.eligible(tool_cfg, svc.get("kind", "stateless")):
                violations.append("5: automatic execution with the gate closed / unknown / not eligible")
        if row["target"] not in sick:
            violations.append("6: executed although the problem was gone")
    if executed:
        r0, h0, f0 = before
        if f0 >= POLICY["budgets"]["max_in_flight"]:
            violations.append("3: executed while another action was in flight")
        if r0 >= POLICY["budgets"]["max_actions_per_incident"] or h0 >= POLICY["budgets"]["max_actions_per_hour"]:
            violations.append("4: executed past a budget")
    if counts()[2] > max(before[2], POLICY["budgets"]["max_in_flight"]):
        violations.append("3: more than one action in flight")
    return violations


async def test_invariants_hold_for_random_cases(tmp_path, capsys):
    rng = random.Random(20261113)
    failures = []
    for i in range(CASES):
        seed = rng.randrange(2**32)
        found = await run_case(tmp_path, random.Random(seed))
        if found:
            failures.append((i, seed, found))
    with capsys.disabled():
        print(f"\n{CASES} generated cases, {len(failures)} violations")
    assert not failures, failures[:5]


async def test_generator_reaches_execution(tmp_path):
    # guard against a vacuous suite: some random cases must actually execute
    rng = random.Random(7)
    hits = 0
    for _ in range(300):
        w = World(tmp_path)
        w.gw.verify_every = 10**9
        w.conn.execute("INSERT INTO ledger (pattern, action, target, source, successes) "
                       "VALUES ('recent_change', 'rollback_deploy', 'payment', 'rehearsal', 60)")
        a = random_action(rng)
        a.update({"incident_id": "inc-1", "target": "payment", "tool": "rollback_deploy",
                  "pattern": "recent_change", "evidence_ids": ["journal:41"], "journal_entry": 41})
        a.pop("extra_field", None)
        d = await w.gw.submit(a)
        hits += d.decision == "executed"
        for t in list(w.gw.tasks):
            t.cancel()
    assert hits > 100
