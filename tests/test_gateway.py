import copy
import json

import httpx
import pytest
from kubernetes.client.rest import ApiException

from gateway.checklist import Gateway
from gateway.dryrun import outside_allowed, previous_template, spec_diff
from gateway.mcp_server import TOOLS, build_mcp
from gateway.receipts import ReceiptStore
from schemas import auth
from schemas import config
from schemas.db import connect
from schemas.models import Event

SERVICES = config.load("services")["services"]
POLICY = config.load("policy")
GOOD = "ghcr.io/open-telemetry/demo:3.1.0-payment"
BAD = "payment:v2-bad"
# the Status body a real API server (k3s v1.31) returns when one JSON Patch op, our `test`, fails
PATCH_FAILED = json.dumps({"kind": "Status", "apiVersion": "v1", "metadata": {}, "status": "Failure",
                           "message": "the server rejected our request due to an error in our request",
                           "reason": "Invalid", "details": {}, "code": 422})


def patch_failed() -> ApiException:
    e = ApiException(status=422, reason="Unprocessable Entity")
    e.body = PATCH_FAILED
    return e


class Resp:
    def __init__(self, obj):
        self.data = json.dumps(obj).encode()


def template(image):
    return {"metadata": {"labels": {"app": "payment"}}, "spec": {"containers": [{"name": "payment", "image": image}]}}


def rs(rev, image):
    t = template(image)
    t["metadata"]["labels"]["pod-template-hash"] = f"h{rev}"
    return {"metadata": {"name": f"payment-h{rev}", "annotations": {"deployment.kubernetes.io/revision": str(rev)},
                         "ownerReferences": [{"kind": "Deployment", "name": "payment"}]}, "spec": {"template": t}}


def merge(dst, src):
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            merge(dst[k], v)
        elif k in ("containers", "env") and isinstance(v, list):
            items = {i["name"]: i for i in dst.get(k, [])}
            for item in v:
                if item.get("$patch") == "delete":
                    items.pop(item["name"], None)
                elif item["name"] in items:
                    merge(items[item["name"]], item)
                else:
                    items[item["name"]] = item
            dst[k] = list(items.values())
        else:
            dst[k] = v


class FakeApps:
    def __init__(self):
        self.dep = {"metadata": {"name": "payment", "resourceVersion": "100", "generation": 7,
                                 "annotations": {"deployment.kubernetes.io/revision": "2"}},
                    "spec": {"replicas": 2, "template": template(BAD),  # strategy as scripts/install_shop.sh sets it
                             "strategy": {"type": "RollingUpdate",
                                          "rollingUpdate": {"maxUnavailable": 0, "maxSurge": 1}}}}
        self.rss = [rs(1, GOOD), rs(2, BAD)]
        self.patches, self.fail_real, self.fail_dry, self.dry_extra = [], None, None, False
        self.status_churn, self.fail_template = False, None

    def read_namespaced_deployment(self, name, ns, **kw):
        return Resp(self.dep)

    def patch_namespaced_deployment_scale(self, name, ns, body, dry_run=None, field_manager=None,
                                          _content_type=None, _preload_content=True):
        self.patches.append({"dry_run": dry_run, "field_manager": field_manager, "content_type": _content_type,
                             "patch": body, "scale": True})
        assert body["metadata"]["resourceVersion"] == self.dep["metadata"]["resourceVersion"]
        if not dry_run:
            self.dep["spec"]["replicas"] = body["spec"]["replicas"]
            self.dep["metadata"]["resourceVersion"] = str(int(self.dep["metadata"]["resourceVersion"]) + 1)
        return Resp({"metadata": {"name": name}, "spec": {"replicas": body["spec"]["replicas"]}})

    def list_namespaced_replica_set(self, ns, **kw):
        return Resp({"items": self.rss})

    def list_namespaced_deployment(self, ns, **kw):
        return Resp({"items": [self.dep]})

    def patch_namespaced_deployment(self, name, ns, patch, dry_run=None, field_manager=None, _content_type=None,
                                    _preload_content=True):
        self.patches.append({"dry_run": dry_run, "field_manager": field_manager, "content_type": _content_type,
                             "patch": patch})
        fail = self.fail_dry if dry_run else self.fail_real
        if fail:
            raise fail
        if self.status_churn:  # rollout controller wrote status between our read and this patch, as live
            self.dep["metadata"]["resourceVersion"] = str(int(self.dep["metadata"]["resourceVersion"]) + 1)
        new = copy.deepcopy(self.dep)
        if isinstance(patch, dict):  # strategic merge: maps merge, containers merge by name
            assert patch["metadata"]["resourceVersion"] == self.dep["metadata"]["resourceVersion"]
            merge(new, {k: v for k, v in patch.items() if k != "metadata"})
        else:
            key = patch[0]["path"].rsplit("/", 1)[1]
            if patch[0]["op"] == "test" and self.dep["metadata"].get(key) != patch[0]["value"]:
                raise patch_failed()
            if self.fail_template and not dry_run and any(op["path"] == "/spec/template" for op in patch):
                raise self.fail_template
            for op in patch[1:]:
                new["spec"][op["path"].rsplit("/", 1)[1]] = op["value"]
            if not dry_run:
                new["metadata"]["generation"] += 1
        if self.dry_extra:
            new["spec"]["replicas"] = 9
        if not dry_run:
            new["metadata"]["resourceVersion"] = str(int(new["metadata"]["resourceVersion"]) + 1)
            self.dep = new
        return Resp(new)


class FakeCore:
    def list_namespaced_config_map(self, ns, **kw):
        return Resp({"items": [{"metadata": {"name": "flagd-config"}, "data": {"a": "1"}}]})

    def list_namespaced_pod(self, ns, **kw):
        return Resp({"items": [{"metadata": {"name": "payment-h2-x",
                                             "ownerReferences": [{"kind": "ReplicaSet", "name": "payment-h2"}]}}]})


class Observer:
    def __init__(self):
        self.journal = [{"id": 41, "object": "deployment/payment", "kind": "image", "ts": 950.0,
                         "field_manager": "chaos-panel", "by_agent": False,
                         "diff": {"containers[payment].image": {"old": GOOD, "new": BAD}}}]
        self.unhealthy = True

    def __call__(self, request):
        if request.url.path == "/journal":
            return httpx.Response(200, json=[r for r in self.journal if r["ts"] >= float(request.url.params["since"])])
        return httpx.Response(200, json={"ts": 1000.0, "severity": 4, "services": {
            "payment": {"unhealthy": self.unhealthy, "err_ratio": 0.4}}})


class World:
    def __init__(self, tmp_path, now=1000.0):
        self.apps, self.core, self.obs, self.events, self.now = FakeApps(), FakeCore(), Observer(), [], [now]
        self.conn = connect(":memory:", shared=True)
        self.conn.execute("INSERT INTO incidents (id, opened_at, onset_at, culprit, victims_json, state, "
                          "severity_at_open) VALUES ('inc-1', 990, 960, 'payment', '[\"checkout\"]', 'open', 4)")

        async def publish(event):
            Event.model_validate(event)  # T's contract: every event we emit must validate
            self.events.append(event)

        self.gw = Gateway(self.conn, self.apps, self.core, httpx.AsyncClient(transport=httpx.MockTransport(self.obs)),
                          "http://obs", SERVICES, POLICY, publish, ReceiptStore(tmp_path / "r.db"), {"u1"},
                          clock=lambda: self.now[0])

    def types(self):
        return [e["type"] for e in self.events]


def action(**over):
    a = {"incident_id": "inc-1", "tool": "rollback_deploy", "target": "payment", "pattern": "recent_change",
         "evidence_ids": ["journal:41"], "journal_entry": 41,
         "prediction": {"metric": "err_ratio", "target": "payment", "below": 0.05, "within_s": 90}}
    a.update(over)
    return a


async def test_bad_deploy_asks_then_rolls_back_on_approval(tmp_path):
    w = World(tmp_path)
    d = await w.gw.submit(action())
    assert d.decision == "awaiting_approval" and d.approval_id
    assert "approval_requested" in w.types() and w.apps.patches[0]["dry_run"] == "All"
    req = next(e for e in w.events if e["type"] == "approval_requested")["payload"]
    assert "revision 1" in req["diff"] and req["card"]["incident_id"] == "inc-1"

    d = await w.gw.decide(d.approval_id, "approved", "u1")
    assert d.decision == "executed" and d.receipt_id
    real = w.apps.patches[-1]
    assert real["dry_run"] is None and real["field_manager"] == "oncall-agent"
    assert real["content_type"] == "application/json-patch+json"
    assert real["patch"][0] == {"op": "test", "path": "/metadata/generation", "value": 7}
    assert real["patch"][1]["value"]["spec"]["containers"][0]["image"] == GOOD
    assert "pod-template-hash" not in real["patch"][1]["value"]["metadata"]["labels"]
    row = w.conn.execute("SELECT outcome, inverse_json, pods_touched_json FROM receipts WHERE id=?",
                         (d.receipt_id,)).fetchone()
    assert row["outcome"] == "pending" and json.loads(row["pods_touched_json"]) == ["payment-h2-x"]
    assert json.loads(row["inverse_json"])["template"]["spec"]["containers"][0]["image"] == BAD
    assert w.gw.receipts.get(d.receipt_id).target == "payment"
    assert w.conn.execute("SELECT state FROM incidents").fetchone()[0] == "verifying"
    assert w.types()[-1] == "action_executed"


async def test_schema_refuses_unknown_tool(tmp_path):
    w = World(tmp_path)
    d = await w.gw.submit(action(tool="delete_everything"))
    assert (d.decision, d.failed_step) == ("refused", "schema") and w.apps.patches == []


async def test_protected_target_escalates_with_card(tmp_path):
    w = World(tmp_path)
    d = await w.gw.submit(action(target="valkey-cart"))
    assert (d.decision, d.failed_step) == ("escalated", "policy")
    assert w.types()[-1] == "escalated" and w.apps.patches == []


async def test_human_change_after_open_hands_off(tmp_path):
    w = World(tmp_path)
    w.obs.journal.append({"id": 42, "object": "deployment/payment", "kind": "replicas", "ts": 995.0,
                          "field_manager": "kubectl", "by_agent": False, "diff": {}})
    d = await w.gw.submit(action())
    assert (d.decision, d.failed_step) == ("handed_off", "hands_off") and w.types()[-1] == "handed_off"


# plan §6.4.2 step 2: the chaos panel's injection is not a human taking over
async def test_chaos_panel_change_after_open_is_not_hands_off(tmp_path):
    w = World(tmp_path)
    w.obs.journal.append({"id": 43, "object": "configmap/flagd-config", "kind": "flag", "ts": 995.0,
                          "field_manager": "chaos-panel", "by_agent": False, "diff": {}})
    d = await w.gw.submit(action())
    assert d.failed_step != "hands_off"
    step = next(e for e in w.events if e["type"] == "checklist_step" and e["payload"]["name"] == "hands_off")
    assert step["payload"]["passed"] is True


async def test_approval_rules(tmp_path):
    w = World(tmp_path)
    d = await w.gw.submit(action())
    assert (await w.gw.decide(d.approval_id, "approved", "stranger")).reason == "not an approver"
    w.now[0] = 1000 + POLICY["approval"]["expiry_seconds"] + 1
    late = await w.gw.decide(d.approval_id, "approved", "u1")
    assert late.decision == "escalated" and w.apps.patches[-1]["dry_run"] == "All"
    assert (await w.gw.decide(d.approval_id, "approved", "u1")).reason == "approval is expired"


async def test_conflict_on_execute_hands_off_and_admission_denial_escalates(tmp_path):
    w = World(tmp_path)
    d = await w.gw.submit(action())
    w.apps.fail_real = ApiException(status=409, reason="Conflict")
    assert (await w.gw.decide(d.approval_id, "approved", "u1")).decision == "handed_off"

    w2 = World(tmp_path)
    w2.apps.fail_dry = ApiException(status=422, reason="denied request: image must come from an approved source")
    d2 = await w2.gw.submit(action())
    assert (d2.decision, d2.failed_step) == ("escalated", "dry_run") and "approved source" in d2.reason


# scenario 5: valkey-cart scaled to 0. The agent may scale a data store back, never alone (Muaz chose)
async def test_protected_data_store_scale_needs_a_human_then_runs(tmp_path):
    w = World(tmp_path)
    w.conn.execute("UPDATE incidents SET culprit='valkey-cart', victims_json='[\"cart\"]'")
    w.apps.dep["spec"]["replicas"] = 0
    w.obs.journal = [{"id": 50, "object": "deployment/valkey-cart", "kind": "replicas", "ts": 950.0,
                      "field_manager": "chaos-panel", "by_agent": False, "diff": {"replicas": {"old": 1, "new": 0}}}]

    def health(request):
        if request.url.path == "/journal":
            return w.obs(request)
        # a data store emits no spans: no readings, looks "fine"; its caller cart is the sick one
        return httpx.Response(200, json={"ts": 1000.0, "severity": 4, "services": {
            "valkey-cart": {"unhealthy": False, "err_ratio": None, "p95_ms": None, "bad_pods": 0},
            "cart": {"unhealthy": True, "err_ratio": 1.0, "p95_ms": 5.0, "bad_pods": 0}}})

    w.gw.http = httpx.AsyncClient(transport=httpx.MockTransport(health))
    # 30 clean rehearsals still never open the gate for a data store
    w.conn.execute("INSERT INTO ledger VALUES ('protected', 'scale', 'valkey-cart', 'rehearsal', 60, 0, NULL)")
    a = action(tool="scale", target="valkey-cart", pattern="protected", journal_entry=50,
               evidence_ids=["journal:50"], params={"replicas": 1}, prediction=None)
    d = await w.gw.submit(a)
    assert (d.decision, d.failed_step) == ("awaiting_approval", "trust_gate") and "protected" in d.reason
    assert not [p for p in w.apps.patches if not p["dry_run"]]
    req = next(e for e in w.events if e["type"] == "approval_requested")["payload"]
    assert "valkey-cart" in req["card"]["text"] and "replicas" in req["card"]["text"]

    d = await w.gw.decide(d.approval_id, "approved", "u1")
    assert d.decision == "executed"
    real = w.apps.patches[-1]
    assert real.get("scale") and real["dry_run"] is None and real["patch"]["spec"]["replicas"] == 1
    for t in list(w.gw.tasks):
        t.cancel()

    other = World(tmp_path)  # anything but a scale on a data store is still a straight escalation
    d = await other.gw.submit(action(tool="restart_service", target="valkey-cart", pattern="protected"))
    assert (d.decision, d.failed_step) == ("escalated", "policy")


# generation moved between our read and the write: someone else changed it, not an RBAC/admission block
async def test_failed_generation_test_hands_off_and_is_not_blocked(tmp_path):
    w = World(tmp_path)
    d = await w.gw.submit(action())
    w.apps.fail_real = patch_failed()
    d = await w.gw.decide(d.approval_id, "approved", "u1")
    assert (d.decision, d.failed_step) == ("handed_off", "execute")
    assert "blocked" not in w.types() and w.types()[-1] == "handed_off"


async def test_problem_gone_resolves_without_acting(tmp_path):
    w = World(tmp_path)
    w.obs.unhealthy = False
    d = await w.gw.submit(action())
    assert (d.decision, d.failed_step) == ("refused", "freshness") and w.types()[-1] == "incident_resolved"


async def test_dry_run_outside_template_escalates(tmp_path):
    w = World(tmp_path)
    w.apps.dry_extra = True
    d = await w.gw.submit(action())
    assert (d.decision, d.failed_step) == ("escalated", "dry_run") and "replicas" in d.reason


async def test_budget_and_in_flight(tmp_path):
    w = World(tmp_path)
    d = await w.gw.submit(action())
    await w.gw.decide(d.approval_id, "approved", "u1")
    again = await w.gw.submit(action())
    assert (again.decision, again.failed_step) == ("refused", "policy") and "still being verified" in again.reason


# overnight trust runs need ~15 actions an hour; only ONCALL_REHEARSAL=1 lifts the 3/hour cap
async def test_hour_budget_lifted_only_in_rehearsal_mode(tmp_path):
    for rehearsal, decision in ((False, "escalated"), (True, "awaiting_approval")):
        w = World(tmp_path)
        w.gw.rehearsal = rehearsal
        for i in range(POLICY["budgets"]["max_actions_per_hour"]):
            w.conn.execute("INSERT INTO receipts (id, incident_id, ts, tool, target, outcome) VALUES "
                           "(?, 'old', 900, 'rollback_deploy', 'payment', 'success')", (500 + i,))
        d = await w.gw.submit(action())
        assert d.decision == decision, (rehearsal, d)
        if not rehearsal:
            assert d.reason == "action budget used up"


def test_previous_template_and_diff_helpers():
    dep = FakeApps().dep
    t, rev = previous_template(dep, [rs(1, GOOD), rs(2, BAD), rs(3, "x")])
    assert rev == "1" and "pod-template-hash" not in t["metadata"]["labels"]
    assert previous_template({**dep, "metadata": {**dep["metadata"], "annotations": {}}}, [rs(1, GOOD)]) is None
    diff = spec_diff({"replicas": 2, "template": template(BAD)}, {"replicas": 3, "template": template(GOOD)})
    assert sorted(diff) == ["replicas", "template.spec.containers"] and outside_allowed(diff) == ["replicas"]


async def test_mcp_exposes_six_tools_with_actable_targets_only():
    calls = []

    async def submit(raw):
        calls.append(raw)
        from schemas.models import GatewayDecision
        return GatewayDecision(decision="refused", failed_step="schema")

    mcp = build_mcp(submit, ["payment", "cart"])
    tools = {t.name: t for t in await mcp.list_tools()}
    assert sorted(tools) == sorted(TOOLS)
    assert tools["scale"].inputSchema["properties"]["target"]["enum"] == ["payment", "cart"]
    await mcp.call_tool("rollback_deploy", {"incident_id": "i", "target": "payment", "pattern": "recent_change",
                                            "evidence_ids": ["journal:1"]})
    assert calls[0]["tool"] == "rollback_deploy" and calls[0]["params"] == {}
    with pytest.raises(Exception):
        await mcp.call_tool("rollback_deploy", {"incident_id": "i", "target": "valkey-cart", "pattern": "x",
                                                "evidence_ids": []})
    assert len(calls) == 1


def test_http_app_routes(tmp_path):
    from fastapi.testclient import TestClient

    from gateway.main import create_app

    w = World(tmp_path)
    with TestClient(create_app(w.gw), base_url="http://127.0.0.1:7003", headers=auth.headers()) as client:  # MCP rejects other Hosts
        assert client.get("/health").json() == {"ok": True}
        assert client.get("/ledger").json() == []
        r = client.post("/approvals/nope/decide", json={"decision": "approved", "decided_by": "u1"})
        assert r.json()["reason"] == "unknown approval"
        assert client.post("/approvals/x/decide", json={"decision": "maybe", "decided_by": "u1"}).status_code == 422
        init = client.post("/mcp", headers={"accept": "application/json, text/event-stream"},
                           json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
        assert init.status_code == 200 and len(init.json()["result"]["tools"]) == 6


# UI pages (plan §6.8): /trust table, receipt list, "verify audit log" button
def test_trust_receipts_and_audit_routes(tmp_path):
    from fastapi.testclient import TestClient

    from gateway.main import create_app
    from schemas.models import Receipt

    w = World(tmp_path)
    w.conn.execute("INSERT INTO ledger VALUES ('recent_change', 'rollback_deploy', 'payment', 'rehearsal', 30, 0, NULL)")
    w.conn.execute("INSERT INTO ledger VALUES ('recent_change', 'rollback_deploy', 'payment', 'real', 1, 0, NULL)")
    w.conn.execute("INSERT INTO ledger VALUES ('resource', 'raise_limit', 'recommendation', 'real', 40, 0, NULL)")
    w.gw.receipts.save(Receipt(incident_id="inc-1", tool="scale", target="payment", diff={}, inverse={"op": "scale"},
                               evidence_ids=[]))
    app = create_app(w.gw)
    app.state.audit_path = str(tmp_path / "audit.jsonl")
    with TestClient(app, base_url="http://127.0.0.1:7003", headers=auth.headers()) as client:
        rows = {(r["pattern"], r["action"]): r for r in client.get("/trust").json()}
        assert rows[("recent_change", "rollback_deploy")]["bar"] == 0.9
        assert rows[("recent_change", "rollback_deploy")]["open"] is True
        assert rows[("recent_change", "rollback_deploy")]["rehearsal"] == [30, 0]
        assert rows[("resource", "raise_limit")]["open"] is False  # never auto-eligible
        listed = client.get("/receipts?limit=50").json()
        assert [r["id"] for r in listed] == [1] and listed[0]["receipt"]["tool"] == "scale"
        assert client.get("/audit/verify").json() == {"ok": True, "records": 0}
        client.post("/events/publish", json={"type": "blocked", "payload": {"step": "x"}})
        path = tmp_path / "audit.jsonl"
        path.write_text(path.read_text().replace('"x"', '"y"'))  # someone edits the log while we run
        assert client.get("/audit/verify").json() == {"ok": False, "error": "Audit chain broken at seq 1"}
