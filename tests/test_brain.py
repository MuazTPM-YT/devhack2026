import json
import time

import httpx
from fastapi.testclient import TestClient

from brain.graph import DependencyGraph, downstream
from brain.llm import DiagnosisService
from brain.main import Brain, create_app
from brain.providers.base import InferenceResponse
from schemas import config
from schemas.db import connect
from schemas.models import GatewayDecision, Incident

SERVICES = config.load("services")["services"]
POLICY = config.load("policy")
NOW = 1000.0


class FakeProvider:
    name, model = "fake", "test-model"

    def __init__(self, responses):
        self.responses = list(responses)

    async def generate(self, request):
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return InferenceResponse(value, self.name, self.model, {"prompt_tokens": 10})


def jaeger_trace():
    return {"traceID": "t1", "processes": {"p1": {"serviceName": "checkout"}, "p2": {"serviceName": "payment"}},
            "spans": [{"spanID": "a", "processID": "p1", "operationName": "PlaceOrder",
                       "tags": [{"key": "error", "value": True}]},
                      {"spanID": "b", "processID": "p2", "operationName": "Charge",
                       "references": [{"refType": "CHILD_OF", "spanID": "a"}],
                       "tags": [{"key": "error", "value": True}]}]}


class World:
    """Fake observer + Jaeger + gateway behind one MockTransport."""

    def __init__(self, jaeger_up=True):
        self.jaeger_up, self.published, self.requests, self.gateway_down = jaeger_up, [], [], False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path == "/health/now":
            return httpx.Response(200, json={"ts": NOW, "services": {
                "payment": {"err_ratio": 0.4, "p95_ms": 200.0, "first_breach_ts": 960.0, "unhealthy": True},
                "checkout": {"err_ratio": 0.2, "p95_ms": 300.0, "first_breach_ts": 965.0, "unhealthy": True}}})
        if path == "/journal":
            return httpx.Response(200, json=[{"id": 41, "object": "deployment/payment", "kind": "image", "ts": 950.0,
                                              "field_manager": "chaos-panel", "by_agent": False,
                                              "diff": {"containers[payment].image": {"old": "a", "new": "b"}}}])
        if path.startswith("/jaeger"):
            if not self.jaeger_up:
                return httpx.Response(502)
            if path.endswith("/api/dependencies"):
                return httpx.Response(200, json={"data": [{"parent": "checkout", "child": "payment", "callCount": 9}]})
            return httpx.Response(200, json={"data": [jaeger_trace()]})
        if path == "/events/publish":
            self.published.append(json.loads(request.content))
            return httpx.Response(200, json={})
        return httpx.Response(404)


def diagnosis_json(**over):
    d = {"causes": [{"cause_class": "recent_change", "culprit": "payment", "evidence_ids": ["journal:41"],
                     "explanation": "Bad image."}],
         "prediction": {"metric": "err_ratio", "target": "payment", "below": 0.05, "within_s": 90},
         "proposed": None, "confidence": 0.9}
    d.update(over)
    return json.dumps(d)


def make(world, responses, tmp_path):
    conn = connect(":memory:", shared=True)
    conn.execute("INSERT INTO incidents (id, state) VALUES ('inc-1', 'open')")
    http = httpx.AsyncClient(transport=httpx.MockTransport(world))
    k8s = getattr(world, "k8s", None) or {"events": [], "logs": [], "memory_ratio": None, "memory_limit": None}
    submitted = []

    async def submit(action):
        submitted.append(action)
        if world.gateway_down:
            raise httpx.ConnectError("down")
        return GatewayDecision(decision="awaiting_approval", approval_id="a1")

    brain = Brain(http, "http://obs", "http://gw", "http://p/jaeger/ui",
                  DiagnosisService(FakeProvider(responses), tmp_path), lambda svc, now: k8s,
                  conn, SERVICES, POLICY, clock=lambda: NOW, submit=submit)
    brain.submitted = submitted  # type: ignore[attr-defined]
    return brain


INC = Incident(id="inc-1", opened_at=990, onset_at=960, unhealthy=["checkout", "payment"], severity=6)


def brain_why(world):
    return world.brain.conn.execute("SELECT llm_why FROM incidents WHERE id='inc-1'").fetchone()[0]


async def test_bad_deploy_end_to_end(tmp_path):
    world = World()
    world.brain = make(world, [diagnosis_json()], tmp_path)
    record = await world.brain.handle(INC)
    assert record["incident"]["culprit"] == "payment" and record["incident"]["victims"] == ["checkout"]
    assert record["pattern"] == "recent_change"
    action = record["action"]
    assert (action["tool"], action["target"], action["journal_entry"]) == ("rollback_deploy", "payment", 41)
    assert action["prediction"] == {"metric": "err_ratio", "target": "payment", "below": 0.05, "within_s": 90}
    types = [e["type"] for e in world.published]
    assert types[:3] == ["culprit_found", "bundle_built", "rule_matched"] and types[-1] == "diagnosis_ready"
    assert "llm_called" in types
    # the model's own words reach the card the gateway builds later
    assert brain_why(world) == "Bad image."


async def test_llm_failure_keeps_rule_action(tmp_path):
    world = World()
    record = await make(world, ["not json", "still not json"], tmp_path).handle(INC)
    assert record["action"]["tool"] == "rollback_deploy" and record["action"]["prediction"] is None
    assert record["llm_error"] == "invalid_diagnosis"


async def test_jaeger_down_falls_back_to_deepest_unhealthy(tmp_path):
    world = World(jaeger_up=False)
    brain = make(world, [diagnosis_json()], tmp_path)
    record = await brain.handle(INC)
    # no graph either: tie on depth, earliest onset (payment 960) wins
    assert record["incident"]["culprit"] == "payment"
    assert world.published[0]["payload"]["from_traces"] is False
    row = brain.conn.execute("SELECT culprit, victims_json, pattern FROM incidents WHERE id='inc-1'").fetchone()
    assert tuple(row) == ("payment", '["checkout"]', "recent_change")


async def test_trace_query_uses_error_tag_and_window(tmp_path):
    world = World()
    await make(world, [diagnosis_json()], tmp_path).handle(INC)
    q = next(r for r in world.requests if r.url.path.endswith("/api/traces")).url.params
    assert json.loads(q["tags"]) == {"error": "true"} and q["limit"] == "20"
    assert int(q["end"]) - int(q["start"]) == 300 * 10**6


async def test_graph_cache_and_downstream():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"data": [{"parent": "a", "child": "b", "callCount": 1},
                                                  {"parent": "b", "child": "c", "callCount": 2},
                                                  {"parent": "c", "child": "c", "callCount": 1}]})

    clock = [0.0]
    g = DependencyGraph(httpx.AsyncClient(transport=httpx.MockTransport(handler)), "http://j", clock=lambda: clock[0])
    edges = await g.get()
    await g.get()
    clock[0] = 61
    await g.get()
    assert len(calls) == 2 and ("c", "c", 1.0) not in edges
    assert downstream(edges, "a") == {"b", "c"} and downstream(edges, "c") == set()


def test_post_incident_accepts_once(tmp_path):
    brain = make(World(), [diagnosis_json()], tmp_path)
    with TestClient(create_app(brain)) as client:
        body = INC.model_dump(mode="json")
        assert client.post("/incidents", json=body).json()["status"] == "accepted"
        assert client.post("/incidents", json=body).json()["status"] == "already_handled"
        for _ in range(100):  # handled in a background task
            r = client.get("/incidents/inc-1")
            if r.status_code == 200:
                break
            time.sleep(0.01)
        assert r.json()["pattern"] == "recent_change"
        assert client.get("/incidents/nope").status_code == 404


async def test_action_goes_to_gateway(tmp_path):
    brain = make(World(), [diagnosis_json()], tmp_path)
    record = await brain.handle(INC)
    assert [a.tool for a in brain.submitted] == ["rollback_deploy"]
    assert record["gateway"]["decision"] == "awaiting_approval"


async def test_no_action_escalates_without_gateway(tmp_path):
    world = World(jaeger_up=False)  # fallback culprit = ad, no change on ad -> unknown, no rule action
    brain = make(world, [diagnosis_json(causes=[], prediction=None)], tmp_path)
    inc = INC.model_copy(update={"unhealthy": ["ad"]})
    record = await brain.handle(inc)
    assert record["pattern"] == "unknown" and brain.submitted == []
    assert record["gateway"]["decision"] == "escalated" and world.published[-1]["type"] == "escalated"


async def test_gateway_down_escalates(tmp_path):
    world = World()
    world.gateway_down = True
    record = await make(world, [diagnosis_json()], tmp_path).handle(INC)
    assert record["gateway"]["failed_step"] == "gateway" and world.published[-1]["type"] == "escalated"


async def test_resource_case_sends_restart_then_raise_limit(tmp_path):
    from schemas.models import Evidence
    world = World(jaeger_up=False)
    world.k8s = {"events": [Evidence(id="event:rec:app:last", kind="event", ts=NOW,
                                     summary="container app last ended OOMKilled, exit 137")],
                 "logs": [], "memory_ratio": 0.5, "memory_limit": "256Mi"}
    inc = INC.model_copy(update={"unhealthy": ["recommendation"]})
    brain = make(world, [diagnosis_json(causes=[], prediction={"metric": "err_ratio", "target": "recommendation",
                                                               "below": 0.05, "within_s": 120})], tmp_path)
    record = await brain.handle(inc)
    assert record["pattern"] == "resource"
    assert [(a.tool, a.params) for a in brain.submitted] == [("restart_service", {}),
                                                             ("raise_limit", {"memory": "512Mi"})]


async def test_datastore_scaled_to_zero_moves_culprit_to_protected_dependency(tmp_path):
    from brain.culprit import dependency_change

    class StoreWorld(World):
        def __call__(self, request):
            if request.url.path == "/journal":
                return httpx.Response(200, json=[{"id": 12, "object": "deployment/valkey-cart", "kind": "replicas",
                                                  "ts": 950.0, "field_manager": "chaos-panel", "by_agent": False,
                                                  "diff": {"replicas": {"old": 1, "new": 0}}}])
            return super().__call__(request)

    world = StoreWorld(jaeger_up=False)  # no traces, no graph edge to the datastore
    inc = INC.model_copy(update={"unhealthy": ["cart"]})
    brain = make(world, [diagnosis_json(causes=[], prediction={"metric": "err_ratio", "target": "cart", "below": 0.05, "within_s": 120})], tmp_path)
    record = await brain.handle(inc)
    assert record["incident"]["culprit"] == "valkey-cart" and record["incident"]["victims"] == ["cart"]
    assert record["pattern"] == "protected"
    assert [(a.tool, a.target, a.params) for a in brain.submitted] == [("scale", "valkey-cart", {"replicas": 1})]
    assert world.published[0]["payload"]["moved_from"] == "cart"
    own = [{"id": 1, "object": "deployment/cart", "kind": "image", "ts": 940.0, "by_agent": False}]
    assert dependency_change(own + [{"id": 12, "object": "deployment/valkey-cart", "kind": "replicas", "ts": 950.0,
                                     "by_agent": False}], "cart", [], SERVICES, 960, 600) is None  # own change wins


# MCP/schema refused it before the checklist ran: no one else would end the incident (it stayed open forever)
async def test_schema_refusal_escalates_with_why(tmp_path):
    world = World()
    brain = make(world, [diagnosis_json()], tmp_path)

    async def refuse(action):
        return GatewayDecision(decision="refused", failed_step="schema", reason="target not allowed")

    brain.submit = refuse
    record = await brain.handle(INC)
    assert record["gateway"]["decision"] == "refused" and world.published[-1]["type"] == "escalated"
    text = world.published[-1]["payload"]["card"]["text"]
    assert text.startswith("WOKE YOU BECAUSE") and "deployment/payment image change" in text
    assert brain.conn.execute("SELECT state FROM incidents").fetchone()[0] == "escalated"
