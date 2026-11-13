import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from gateway.approvals import REHEARSAL_APPROVER
from schemas import auth
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
    with TestClient(create_app(w.gw), base_url="http://127.0.0.1:7003", headers=auth.headers()) as client:
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
        http = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:7003",
                                 headers=auth.headers())
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


# the watchdog undoes a silent verifier's fix; a receipt with no safe undo must not crash it (KeyError).
# It used to end watchdog_failed and block every later action; now it keeps the fix and frees the slot (Muaz chose)
async def test_watchdog_on_a_fix_with_no_safe_undo_fails_closed(tmp_path):
    from gateway import policy
    from test_phase3 import executed_and_parked
    w, d = await executed_and_parked(tmp_path)
    w.conn.execute("UPDATE receipts SET inverse_json=?", (json.dumps({"op": "none", "why": "would scale to 0"}),))
    w.now[0] += 200
    assert await w.gw.watchdog() == 1
    assert w.conn.execute("SELECT outcome FROM receipts").fetchone()[0] == "handed_off"
    assert policy.usage(w.conn, "inc-1", w.now[0])["in_flight"] == 0
    assert w.apps.dep["spec"]["template"]["spec"]["containers"][0]["image"] == GOOD  # fix left in place


# ---- a fix the model chose itself (ActionRequest.origin == "model") ----------------------------------------
def open_gate(w):
    w.conn.execute("INSERT INTO ledger VALUES ('recent_change', 'rollback_deploy', 'payment', 'rehearsal', "
                   "30, 0, NULL)")


async def test_model_chosen_fix_asks_a_human_even_when_the_gate_is_open(tmp_path):
    w = World(tmp_path)
    open_gate(w)
    d = await w.gw.submit(action(origin="model"))
    assert (d.decision, d.failed_step) == ("awaiting_approval", "trust_gate")
    assert "the agent chose this fix itself" in d.reason
    assert all(p["dry_run"] == "All" for p in w.apps.patches)  # nothing was written
    # the same action as the rule's own pick runs on the earned trust
    w2 = World(tmp_path / "b")
    open_gate(w2)
    assert (await w2.gw.submit(action())).decision == "executed"


@pytest.mark.parametrize("healths", [[healthy()], [sick()]])
async def test_model_chosen_fix_neither_earns_nor_costs_rule_trust(tmp_path, healths):
    w = World(tmp_path)
    script = Script(w, healths)
    w.gw.http = httpx.AsyncClient(transport=httpx.MockTransport(script))
    w.gw.verify_every = 0
    d = await w.gw.submit(action(origin="model"))
    d = await w.gw.decide(d.approval_id, "approved", "u1")
    assert d.decision == "executed"
    script.active = True
    await asyncio.wait_for(next(iter(w.gw.tasks)), 5)
    assert ledger(w) == []
    assert json.loads(w.conn.execute("SELECT trust_json FROM receipts").fetchone()[0])["origin"] == "model"


async def test_model_chosen_fix_earns_no_rehearsal_credit(tmp_path):
    w = World(tmp_path)
    script = Script(w, [healthy()])
    w.gw.http = httpx.AsyncClient(transport=httpx.MockTransport(script))
    w.gw.verify_every = 0
    w.gw.approvers.add(REHEARSAL_APPROVER)
    d = await w.gw.submit(action(origin="model"))
    d = await w.gw.decide(d.approval_id, "approved", REHEARSAL_APPROVER)
    script.active = True
    await asyncio.wait_for(next(iter(w.gw.tasks)), 5)
    assert w.gw.rehearsal_credit(d.receipt_id, True)["credited"] is False and ledger(w) == []


# chaos lab decoy: a newer, harmless change sits on top of the real one. The rule's pick would be the newer
# entry; the model may point at the older one, and a human's yes must then run it, not bounce at freshness
async def test_model_may_pick_an_older_change_than_the_rule_would(tmp_path):
    def newer(w):
        w.obs.journal.append({"id": 44, "object": "deployment/payment", "kind": "env", "ts": 955.0,
                              "field_manager": "chaos-panel", "by_agent": False,
                              "diff": {"containers[payment].env": {"old": [], "new": []}}, "inverse": []})

    w = World(tmp_path)
    newer(w)
    d = await w.gw.submit(action(origin="model"))
    assert (d.decision, d.failed_step) == ("awaiting_approval", "trust_gate")
    assert (await w.gw.decide(d.approval_id, "approved", "u1")).decision == "executed"
    # claimed as the rule's pick, the same stale entry is caught: the gateway derives the rule itself
    w2 = World(tmp_path / "b")
    newer(w2)
    d2 = await w2.gw.submit(action())
    assert (d2.decision, d2.failed_step) == ("awaiting_approval", "freshness") and "rule result changed" in d2.reason
    assert (await w2.gw.decide(d2.approval_id, "approved", "u1")).decision == "escalated"


async def test_origin_survives_the_mcp_call(tmp_path):
    from brain.gateway_client import call_tool
    from gateway.main import create_app
    from schemas.models import ActionRequest

    w = World(tmp_path)
    open_gate(w)
    app = create_app(w.gw)
    async with app.router.lifespan_context(app):
        http = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:7003",
                                 headers=auth.headers())
        d = await call_tool("http://127.0.0.1:7003", ActionRequest.model_validate(action(origin="model")), http=http)
        assert (d.decision, d.failed_step) == ("awaiting_approval", "trust_gate")
        stored = json.loads(w.conn.execute("SELECT action_json FROM approvals").fetchone()[0])
        assert stored["origin"] == "model"


def blind(h):
    return {**h, "prometheus_ok": False}


# metrics stopped (observer keeps the last reading, prometheus_ok false): the gateway acted on that stale
# picture, live in e2e. Now: never act on stale health; ask, and an approved run while still stale stops
async def test_stale_health_never_executes(tmp_path):
    w = World(tmp_path)
    w.gw.http = httpx.AsyncClient(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json=blind(sick())) if r.url.path == "/health/now" else w.obs(r)))
    d = await w.gw.submit(action())
    assert d.decision == "awaiting_approval" and "stale" in d.reason
    d = await w.gw.decide(d.approval_id, "approved", "u1")
    assert d.decision == "escalated" and "stale" in d.reason
    assert not [p for p in w.apps.patches if p["dry_run"] is None]


# metrics stop while checking a fix: stale ticks are no data; still stale at the window end -> keep the fix,
# page a human, no undo and no trust failure (Muaz chose: never undo on blindness)
async def test_stale_health_to_window_end_keeps_fix_and_pages(tmp_path):
    w, d, outcome = await executed(tmp_path, [blind(sick())])
    assert outcome == "handed_off"
    assert "action_undone" not in w.types() and w.types()[-1] == "escalated"
    assert w.apps.dep["spec"]["template"]["spec"]["containers"][0]["image"] == GOOD
    assert "could not check" in w.events[-1]["payload"]["briefing"]
    assert ledger(w) == []


# a stale tick in the middle is skipped, not read as "still sick"; fresh data then proves the fix
async def test_stale_ticks_then_fresh_recovery_is_success(tmp_path):
    w, d, outcome = await executed(tmp_path, [blind(sick())] * 3 + [healthy()])
    assert outcome == "success"


# ---- retry after a clean undo (§6.4.11, Muaz: 3 fixes, retries run alone, trust gate kept) ----------------
class Brain:
    def __init__(self, answer=(True, "")):
        self.bodies, self.answer = [], answer

    async def __call__(self, body):
        self.bodies.append(body)
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def with_brain(brain):
    return lambda w: setattr(w.gw, "request_retry", brain)


def state(w):
    return w.conn.execute("SELECT state FROM incidents WHERE id='inc-1'").fetchone()[0]


async def test_failed_fix_goes_back_to_the_brain_with_the_error_context(tmp_path):
    brain = Brain()
    w, d, outcome = await executed(tmp_path, [sick()], setup=with_brain(brain))
    assert outcome == "undone" and "escalated" not in w.types() and w.types()[-1] == "retry_started"
    assert state(w) == "replanning" and w.gw.retry_grants["inc-1"][1] == 2
    body = brain.bodies[0]
    assert (body["incident"]["id"], body["attempt"], body["max_attempts"]) == ("inc-1", 2, 3)
    failed = body["failed"][0]
    assert (failed["tool"], failed["journal_entry"], failed["why_undone"]) == ("rollback_deploy", 41, "did not recover")
    assert failed["recovered"] is False and (failed["severity_before"], failed["severity_after"]) == (4, 4)
    assert failed["readings_after"]["payment"]["err_ratio"] == 0.4 and failed["receipt_id"] == d.receipt_id
    payload = w.events[-1]["payload"]
    assert payload["card"]["status"] == "TRYING ANOTHER FIX" and payload["attempt"] == 2
    assert payload["source"]["part"] == "verifier" and payload["started"]["change"] == "image change on deployment/payment"
    tries = next(f["body"] for f in payload["card"]["fields"] if f["label"] == "Fixes tried")
    assert "did not bring the service back in time" in tries and tries.endswith("Now trying fix 2 of 3.")
    assert ledger(w) == [("real", 0, 1)]  # the failed fix still costs the rule's trust


async def test_early_abort_also_retries(tmp_path):
    w, _, outcome = await executed(tmp_path, [sick(severity=9)], setup=with_brain(Brain()))
    assert outcome == "undone" and w.types()[-1] == "retry_started"
    assert w.gw.tries["inc-1"][0]["why_undone"] == "severity rose after the action"


async def test_no_retry_when_the_undo_failed(tmp_path):
    from kubernetes.client.rest import ApiException

    brain = Brain()

    def broken(w):
        with_brain(brain)(w)
        w.apps.fail_template = ApiException(status=422, reason="Invalid")

    w, _, outcome = await executed(tmp_path, [sick(severity=9)], setup=broken)
    assert outcome == "undo_failed" and brain.bodies == [] and w.types()[-1] == "escalated"


async def test_three_fixes_used_pages_with_every_try(tmp_path):
    def two_earlier(w):
        with_brain(brain)(w)
        for i in (1, 2):
            w.conn.execute("INSERT INTO receipts (incident_id, ts, tool, target, outcome) "
                           "VALUES ('inc-1', 999, 'scale', 'payment', 'undone')")
            w.gw.tries.setdefault("inc-1", []).append({"attempt": i, "tool": "scale", "target": "payment",
                                                        "why_undone": "harm check failed", "receipt_id": i})

    brain = Brain()
    w, _, outcome = await executed(tmp_path, [sick()], setup=two_earlier)
    assert outcome == "undone" and brain.bodies == [] and w.types()[-1] == "escalated" and state(w) == "escalated"
    payload = w.events[-1]["payload"]
    assert payload["briefing"] == "did not recover; no retry: all 3 fixes tried"
    assert payload["card"]["headline"].endswith("The agent tried 3 fixes; each failed and was undone.")
    tries = next(f["body"] for f in payload["card"]["fields"] if f["label"] == "Fixes tried").splitlines()
    assert len(tries) == 4 and tries[2].startswith("3. Rolled payment back") and tries[3] == "No more tries: all 3 fixes tried."


async def test_brain_that_refuses_or_is_down_means_a_page(tmp_path):
    w, _, _ = await executed(tmp_path, [sick()], setup=with_brain(Brain((False, "brain refused the retry: no"))))
    assert w.types()[-1] == "escalated" and state(w) == "escalated" and w.gw.retry_grants == {}
    assert w.events[-1]["payload"]["briefing"].endswith("no retry: brain refused the retry: no")
    w2, _, _ = await executed(tmp_path / "b", [sick()], setup=with_brain(Brain(httpx.ConnectError("down"))))
    assert w2.types()[-1] == "escalated" and "brain unreachable (ConnectError)" in w2.events[-1]["payload"]["briefing"]


async def test_waiting_follow_up_approval_blocks_the_retry(tmp_path):
    from gateway import approvals

    def waiting(w):
        with_brain(brain)(w)
        approvals.create(w.conn, "inc-1", {"tool": "raise_limit"}, 1000, 300)

    brain = Brain()
    w, _, _ = await executed(tmp_path, [sick()], setup=waiting)
    assert brain.bodies == [] and "no retry: another approval" in w.events[-1]["payload"]["briefing"]


class Graph:
    async def get(self):
        return [("checkout", "payment", 9.0)]


def trusted(w, tool, pattern="recent_change", target="payment"):
    from gateway import trust
    for _ in range(30):
        trust.record(w.conn, pattern, tool, target, "rehearsal", True, 0)


# the retry the gateway granted runs alone when the fix has earned trust; the same model pick without a grant
# asks a human, and a granted retry with no earned trust still asks (trust gate kept)
async def test_granted_retry_skips_only_the_model_pick_ask(tmp_path):
    w, _, _ = await executed(tmp_path, [sick()], setup=with_brain(Brain()))
    w.gw.graph = Graph()
    restart = action(tool="restart_service", journal_entry=None, evidence_ids=["query:err_ratio:service=payment"],
                     origin="model")
    trusted(w, "restart_service")
    d = await w.gw.submit(restart)
    assert d.decision == "executed", d
    assert "inc-1" not in w.gw.retry_grants  # one grant, one action
    gate = json.loads(w.conn.execute("SELECT trust_json FROM receipts WHERE id=?", (d.receipt_id,)).fetchone()[0])
    assert gate["attempt"] == 2 and gate["origin"] == "model"


async def test_model_pick_without_a_grant_still_asks(tmp_path):
    w = World(tmp_path)
    w.gw.graph = Graph()
    trusted(w, "restart_service")
    d = await w.gw.submit(action(tool="restart_service", journal_entry=None,
                                 evidence_ids=["query:err_ratio:service=payment"], origin="model"))
    assert d.decision == "awaiting_approval" and "chose this fix itself" in d.reason


async def test_granted_retry_without_trust_still_asks(tmp_path):
    w, _, _ = await executed(tmp_path, [sick()], setup=with_brain(Brain()))
    w.gw.graph = Graph()
    d = await w.gw.submit(action(tool="restart_service", journal_entry=None,
                                 evidence_ids=["query:err_ratio:service=payment"], origin="model"))
    assert d.decision == "awaiting_approval" and d.reason.startswith("trust bound")


async def test_retry_the_brain_never_answers_pages_after_the_deadline(tmp_path):
    from gateway.checklist import RETRY_DEADLINE_S

    w, _, _ = await executed(tmp_path, [sick()], setup=with_brain(Brain()))
    assert await w.gw.retry_timeouts() == 0
    w.now[0] += RETRY_DEADLINE_S + 1
    assert await w.gw.retry_timeouts() == 1
    assert w.types()[-1] == "escalated" and state(w) == "escalated" and w.gw.retry_grants == {}
    payload = w.events[-1]["payload"]
    assert "sent no new fix" in payload["briefing"] and payload["source"]["step"] == "retry deadline"


# gateway restart while the brain replans: the grant is gone, so the next fix asks, and silence still pages
async def test_restart_while_replanning_asks_and_still_has_a_deadline(tmp_path):
    from gateway.checklist import RETRY_DEADLINE_S

    w = World(tmp_path)
    w.conn.execute("UPDATE incidents SET state='replanning' WHERE id='inc-1'")
    assert await w.gw.retry_timeouts() == 0 and w.gw.retry_grants["inc-1"][1] is None
    w.now[0] += RETRY_DEADLINE_S + 1
    assert await w.gw.retry_timeouts() == 1 and state(w) == "escalated"
