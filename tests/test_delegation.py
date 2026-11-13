import asyncio
import json

import httpx
import pytest
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from brain.agent import AgentDiagnosisService
from brain.budget import BudgetedModel
from brain.delegation import Delegation, catalog
from schemas import migrations
from schemas.db import connect
from schemas.models import ActionRequest
from schemas.orchestration import FindingResult, OrchestrationPolicy
from schemas.workspace import Workspace
from tests.test_agent import PREDICT, Script, call
from tests.test_agent_tools import NOW, FakeKube, Upstreams, make_box

POLICY = OrchestrationPolicy(mode="coordinated", delegation_enabled=True, max_input_tokens_per_request=60000,
                             max_total_tokens=400000)


class Clock:
    def __init__(self, t: float = NOW):
        self.t = t

    def __call__(self) -> float:
        return self.t


class TwoChanges(Upstreams):
    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/journal":  # decoy env change on payment, then the real image change
            return httpx.Response(200, json=[
                {"id": 41, "object": "deployment/payment", "kind": "env", "ts": 950.0, "field_manager": "chaos-panel",
                 "diff": {"containers[payment].env": {"old": [{"name": "PROMO", "value": "a"}],
                                                      "new": [{"name": "PROMO", "value": "b"}]}}},
                {"id": 42, "object": "deployment/payment", "kind": "image", "ts": 955.0,
                 "field_manager": "chaos-panel", "diff": {"containers[payment].image": {"old": "a", "new": "b"}}}])
        return super().__call__(request)


def cand(cid, entry, tool="rollback_deploy", target="payment"):
    return {"id": cid, "basis": f"undo change {entry}", "action": {
        "incident_id": "inc-1", "tool": tool, "target": target, "params": {}, "pattern": "recent_change",
        "evidence_ids": [f"journal:{entry}"], "prediction": None, "journal_entry": entry}}


CANDS = [cand("c1", 42), cand("c2", 41)]
SCOPE = ["checkout", "payment"]


def finding(info: AgentInfo, cite=("journal:42",), qid=None, hyp="c1", verdict="supported") -> ModelResponse:
    return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {
        "question_id": qid or QID[0], "hypothesis_id": hyp, "verdict": verdict,
        "summary": "the image change matches the error onset; the env change does not",
        "evidence_ids": list(cite)})])


QID: list[str] = []


# one model turn, two reads: the specialist must see the changes itself before it may cite them
def read_both(m, i) -> ModelResponse:
    return ModelResponse(parts=[ToolCallPart("get_recent_changes", {}),
                                ToolCallPart("get_metric_history", {"service": "payment", "metric": "err_ratio"})])


def world(tmp_path, specialist_script=None, policy=POLICY, incidents=("inc-1",)):
    clock = Clock()
    conn = connect(str(tmp_path / "d.db"), shared=True)
    migrations.migrate(conn)
    ws = Workspace(conn, policy, clock=clock)
    for iid in incidents:
        conn.execute("INSERT INTO incidents (id, opened_at, onset_at, state) VALUES (?, 990, 960, 'open')", (iid,))
        conn.execute("INSERT INTO orchestration_workspaces (incident_id, phase, created_at, deadline_at, "
                     "requests_limit, tool_calls_limit, specialists_limit) VALUES (?, 'investigating', 990, 1140, "
                     "?, 24, ?)", (iid, policy.max_model_requests, policy.max_specialists_per_incident))
    conn.commit()
    published: list[tuple[str, dict]] = []

    async def publish(kind, incident_id, payload):
        published.append((kind, payload))

    box = make_box(TwoChanges(), FakeKube())
    box.workspace, box.run_id = ws, "inc-1:cmd:1"
    gate = Delegation(ws, policy, FunctionModel(specialist_script or Script()), publish, clock=clock)
    QID[:] = [q.question_id for q in catalog("inc-1", CANDS, SCOPE, 0)]
    return gate, ws, box, published, clock


def kinds(published):
    return [k for k, _ in published]


def test_catalog_needs_two_changes_in_scope():
    assert catalog("inc-1", [cand("c1", 42)], SCOPE, 0) == []
    assert catalog("inc-1", [cand("c1", 42), cand("c2", 41, target="cart")], SCOPE, 0) == []
    [q] = catalog("inc-1", CANDS, SCOPE, 0)
    assert q.journal_ids == [41, 42] and q.hypotheses == ["c2", "c1"] and q.type == "change_causality"
    # same changes, same services: the same question for any incident
    assert catalog("inc-2", CANDS, SCOPE, 3)[0].fingerprint == q.fingerprint


async def test_no_question_means_commander_alone_with_reason(tmp_path):
    gate, ws, box, published, _ = world(tmp_path)
    ctx = await gate.context("inc-1", [cand("c1", 42)], SCOPE)
    assert ctx.questions == []
    assert published == [("delegation_decided", {"status": "none_needed", "reason": None, "question_id": None,
                                                 "task_id": None,
                                                 "explanation": "No specialist needed: at most one recorded change "
                                                                "fits"})]
    assert ws.snapshot("inc-1").delegation[0].status == "none_needed"


async def test_shared_dependency_explains_zero_specialists(tmp_path):
    gate, ws, _, published, _ = world(tmp_path)
    ws.conn.execute("UPDATE orchestration_workspaces SET cause_key='dependency:valkey-cart'")
    ws.conn.commit()
    await gate.context("inc-1", [], ["cart", "checkout", "valkey-cart"])
    assert "shared cause valkey-cart already supported" in published[0][1]["explanation"]


async def test_must_read_the_changes_before_delegating(tmp_path):
    gate, ws, box, published, _ = world(tmp_path)
    ctx = await gate.context("inc-1", CANDS, SCOPE)
    denied = await ctx.request(box, QID[0], 0, None, None)
    assert (denied.status, denied.reason) == ("denied", "simple_read_sufficient")
    assert ws.task("x") is None and ws.rows("SELECT * FROM investigation_tasks") == []


@pytest.mark.parametrize("question, plan, phase, reason", [
    ("q-invented", 0, "investigating", "no_eligible_question"),
    (None, 3, "investigating", "stale_plan"),
    (None, 0, "terminal", "incident_terminal"),
])
async def test_gate_denials(tmp_path, question, plan, phase, reason):
    gate, ws, box, _, _ = world(tmp_path)
    ws.conn.execute("UPDATE orchestration_workspaces SET phase=?", (phase,))
    ws.conn.commit()
    ctx = await gate.context("inc-1", CANDS, SCOPE)
    await box.call("get_recent_changes", {}, box.changes(10, None))
    result = await ctx.request(box, question or QID[0], plan, None, None)
    assert (result.status, result.reason) == ("denied", reason)


async def test_specialist_finding_becomes_citable_for_commander(tmp_path):
    script = Script(read_both, lambda m, i: finding(i, cite=("journal:42", "query:err_ratio:service=payment:range")))
    gate, ws, box, published, _ = world(tmp_path, script)
    ctx = await gate.context("inc-1", CANDS, SCOPE)
    await box.call("get_recent_changes", {}, box.changes(10, None))
    assert "query:err_ratio:service=payment:range" not in box.ledger
    result = await ctx.request(box, QID[0], 0, None, None)
    assert result.status == "admitted" and result.finding.hypothesis_id == "c1"
    assert "query:err_ratio:service=payment:range" in box.ledger  # imported because the specialist saw it
    assert ws.delivered("inc-1:cmd:1") >= {"query:err_ratio:service=payment:range"}
    task = ws.task(result.task_id)
    assert task["state"] == "succeeded" and json.loads(task["input_json"])["scope"] == SCOPE
    assert ws.workspace("inc-1")["plan_revision"] == 1 and ws.workspace("inc-1")["specialists_started"] == 1
    assert [p["state"] for k, p in published if k == "investigation_task_changed"] == ["running", "succeeded"]
    assert "finding_recorded" in kinds(published)
    roles = [r["role"] for r in ws.rows("SELECT role FROM model_calls")]
    assert roles == ["specialist", "specialist"]


async def test_fresh_finding_is_reused_without_a_model_call(tmp_path):
    gate, ws, box, published, _ = world(tmp_path)
    [q] = catalog("inc-1", CANDS, SCOPE, 0)
    with ws.tx() as c:
        ws.create_task(c, "t-old", "inc-1", q.question_id, q.type, q.fingerprint, 0, 0, {}, [], 2000, 2, 6)
    token = ws.claim_task("t-old", "w", 0)
    ws.complete_task("t-old", token, "succeeded", FindingResult(question_id=q.question_id, hypothesis_id="c1",
                                                                  verdict="supported", summary="image change did it"))
    ctx = await gate.context("inc-1", CANDS, SCOPE)
    assert [f.summary for f in ctx.findings] == ["image change did it"]
    await box.call("get_recent_changes", {}, box.changes(10, None))
    result = await ctx.request(box, q.question_id, 0, None, None)
    assert result.status == "reused" and result.finding.summary == "image change did it"
    assert ws.rows("SELECT * FROM model_calls") == []


async def test_duplicate_request_gets_no_new_quota(tmp_path):
    script = Script(lambda m, i: finding(i, cite=()), lambda m, i: finding(i, cite=()))  # bad twice: fails
    gate, ws, box, _, _ = world(tmp_path, script)
    ctx = await gate.context("inc-1", CANDS, SCOPE)
    await box.call("get_recent_changes", {}, box.changes(10, None))
    first = await ctx.request(box, QID[0], 0, None, None)
    assert first.status == "admitted" and first.finding is None  # bounded failure, nothing respawned
    assert ws.task(first.task_id)["state"] == "failed"
    again = await ctx.request(box, QID[0], 0, None, None)
    assert (again.status, again.reason) == ("denied", "already_answered")
    assert ws.workspace("inc-1")["specialists_started"] == 1


async def test_child_limit_and_request_budget(tmp_path):
    gate, ws, box, _, _ = world(tmp_path)
    ctx = await gate.context("inc-1", CANDS, SCOPE)
    await box.call("get_recent_changes", {}, box.changes(10, None))
    ws.conn.execute("UPDATE orchestration_workspaces SET specialists_started=2")
    ws.conn.commit()
    assert (await ctx.request(box, QID[0], 0, None, None)).reason == "child_limit"
    ws.conn.execute("UPDATE orchestration_workspaces SET specialists_started=0")
    for i in range(7):  # 7 of 9 used: the commander's 2 are all that is left
        ws.conn.execute("INSERT INTO model_calls (call_id, incident_id, run_id, role, state, reserved_at) "
                        "VALUES (?, 'inc-1', 'r', 'commander', 'ok', 1)", (f"c{i}",))
    ws.conn.commit()
    assert (await ctx.request(box, QID[0], 0, None, None)).reason == "request_budget"


async def test_concurrent_last_fleet_slot_admits_exactly_one(tmp_path):
    policy = POLICY.model_copy(update={"max_active_specialists": 1})
    gate, ws, box, _, _ = world(tmp_path, policy=policy, incidents=("inc-1", "inc-2"))
    ctx1 = await gate.context("inc-1", CANDS, SCOPE)
    other = [dict(c, action={**c["action"], "incident_id": "inc-2"}) for c in CANDS]
    ctx2 = await gate.context("inc-2", other, ["payment", "shipping"])
    await box.call("get_recent_changes", {}, box.changes(10, None))
    ledger = set(box.ledger)
    results = await asyncio.gather(gate.admit(ctx1, ctx1.questions[0].question_id, 0, ledger),
                                   gate.admit(ctx2, ctx2.questions[0].question_id, 0, ledger))
    assert sorted((r.status, r.reason) for r in results) == [("admitted", None), ("denied", "fleet_busy")]


async def test_specialist_cannot_read_outside_scope_or_cite_unseen_ids(tmp_path):
    script = Script(lambda m, i: call("get_pods", service="cart"),
                    lambda m, i: finding(i, cite=("journal:99",)),
                    lambda m, i: finding(i, cite=("journal:99",)))
    gate, ws, box, published, _ = world(tmp_path, script)
    ctx = await gate.context("inc-1", CANDS, SCOPE)
    await box.call("get_recent_changes", {}, box.changes(10, None))
    result = await ctx.request(box, QID[0], 0, None, None)
    assert result.finding is None and ws.task(result.task_id)["state"] == "failed"
    reads = [p for k, p in box.published if k == "tool_called"]
    assert reads[-1]["tool"] == "get_pods" and reads[-1]["evidence_ids"] == []  # "unknown service cart"
    assert reads[-1]["task_id"] == result.task_id and "task_id" not in reads[0]  # UI draws it on the specialist
    offered = {t.name for t in script.seen[0][1].function_tools}
    assert "request_investigation" not in offered and "get_service_health" not in offered


async def test_specialist_budget_per_task(tmp_path):
    script = Script(*[lambda m, i: call("get_recent_changes")] * 5)
    gate, ws, box, _, _ = world(tmp_path, script)
    ctx = await gate.context("inc-1", CANDS, SCOPE)
    await box.call("get_recent_changes", {}, box.changes(10, None))
    result = await ctx.request(box, QID[0], 0, None, None)
    assert result.finding is None and "budget" in ws.task(result.task_id)["error"]
    assert len(ws.rows("SELECT * FROM model_calls WHERE task_id=?", (result.task_id,))) == 2


async def test_late_result_after_lease_expiry_is_dropped(tmp_path):
    holder = {}

    def slow(m, i):  # the lease runs out while the specialist thinks
        holder["clock"].t += 100
        holder["ws"].expire_leases()
        return finding(i)

    gate, ws, box, published, clock = world(tmp_path, Script(slow))
    holder.update(clock=clock, ws=ws)
    ctx = await gate.context("inc-1", CANDS, SCOPE)
    await box.call("get_recent_changes", {}, box.changes(10, None))
    clock.t = NOW  # specialist deadline is far enough
    result = await ctx.request(box, QID[0], 0, None, None)
    assert result.finding is None and ws.task(result.task_id)["state"] == "lease_expired"
    assert ws.finding_for(ctx.questions[0].fingerprint) is None and "finding_recorded" not in kinds(published)


async def test_parent_and_child_share_one_durable_request_budget(tmp_path):
    # 6 in all: commander used 2 before asking, the specialist may take 2, the last 2 stay the commander's
    policy = POLICY.model_copy(update={"max_model_requests": 6, "reserved_commander_requests": 2,
                                       "max_requests_per_specialist": 2})
    spec = Script(read_both, lambda m, i: finding(i, cite=("journal:42",)))
    gate, ws, box, published, clock = world(tmp_path, spec, policy=policy)
    box.choose, box.candidates = True, CANDS
    box.tools_ok = {"rollback_deploy"}

    def commander_final(m, i):
        return ModelResponse(parts=[ToolCallPart(i.output_tools[0].name, {
            "causes": [{"cause_class": "recent_change", "culprit": "payment", "evidence_ids": ["journal:42"],
                        "explanation": "the image change on payment broke charges right before onset"}],
            "prediction": PREDICT, "confidence": 0.8, "decision": "accept", "candidate": "c1",
            "reason": "the specialist found the image change matches the errors",
            "alternative": "the env change, but its timing and content do not fit"})])

    commander = Script(lambda m, i: call("get_recent_changes"),
                       lambda m, i: call("request_investigation", question_id=QID[0], expected_plan_revision=0),
                       commander_final, commander_final)
    svc = AgentDiagnosisService(FunctionModel(commander), choose=True, delegation=True)
    box.orch = await gate.context("inc-1", CANDS, SCOPE)
    model = BudgetedModel(svc.model, ws, "inc-1", "inc-1:cmd:1", "commander", publish=gate.publish, clock=clock)
    result = await svc.diagnose(box, "recent_change", ActionRequest.model_validate(CANDS[0]["action"]), {}, CANDS,
                                [{"tool": "rollback_deploy"}], model=model)
    assert result.error is None and result.diagnosis.candidate == "c1"
    calls = ws.rows("SELECT role FROM model_calls")
    assert len(calls) <= policy.max_model_requests
    assert sorted(r["role"] for r in calls) == ["commander", "commander", "commander", "specialist", "specialist"]
    assert result.events[-1]["payload"]["kind"] == "summary"
    per_call = [p for k, p in published if k == "llm_called"]
    assert len(per_call) == 5 and all(p["kind"] == "call" for p in per_call)


async def test_delegation_tool_hidden_without_questions_and_absent_when_off(tmp_path):
    gate, ws, box, _, _ = world(tmp_path)
    box.orch = await gate.context("inc-1", [cand("c1", 42)], SCOPE)
    script = Script(lambda m, i: call("get_recent_changes"),
                    lambda m, i: ModelResponse(parts=[ToolCallPart(i.output_tools[0].name, {
                        "causes": [{"cause_class": "recent_change", "culprit": "payment", "evidence_ids": ["journal:42"],
                                    "explanation": "the image change on payment broke charges"}],
                        "prediction": PREDICT, "confidence": 0.8})]))
    svc = AgentDiagnosisService(FunctionModel(script), delegation=True)
    await svc.diagnose(box, "recent_change", ActionRequest.model_validate(CANDS[0]["action"]))
    assert "request_investigation" not in {t.name for t in script.seen[0][1].function_tools}
    off = AgentDiagnosisService(FunctionModel(Script()))
    assert "request_investigation" not in off.agent._function_toolset.tools  # legacy agent unchanged


async def test_budget_wrapper_refuses_oversized_request(tmp_path):
    policy = POLICY.model_copy(update={"max_input_tokens_per_request": 5})
    gate, ws, box, _, _ = world(tmp_path, policy=policy)
    script = Script(lambda m, i: call("get_recent_changes"))
    svc = AgentDiagnosisService(FunctionModel(script))
    model = BudgetedModel(svc.model, ws, "inc-1", "r", "commander")
    result = await svc.diagnose(box, "recent_change", ActionRequest.model_validate(CANDS[0]["action"]), model=model)
    assert result.error == "round_limit" and ws.rows("SELECT * FROM model_calls") == []
