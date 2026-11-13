import asyncio

from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from brain.agent import AgentDiagnosisService
from schemas.models import ActionRequest
from test_agent_tools import make_box

RULE = ActionRequest(incident_id="inc-1", tool="rollback_deploy", target="payment", pattern="recent_change",
                     evidence_ids=["journal:41"], journal_entry=41)
PREDICT = {"metric": "err_ratio", "target": "payment", "below": 0.05, "within_s": 90}


def final(info: AgentInfo, cite=("journal:41",), prediction=PREDICT, proposed=None) -> ModelResponse:
    return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {
        "causes": [{"cause_class": "recent_change", "culprit": "payment", "evidence_ids": list(cite),
                    "explanation": "payment env changed 10 s before errors began."}],
        "prediction": prediction, "proposed": proposed, "confidence": 0.8})])


def call(name, **args) -> ModelResponse:
    return ModelResponse(parts=[ToolCallPart(name, args)])


# replays steps; each step gets (messages, info) so it can look at what the model was offered
class Script:
    def __init__(self, *steps):
        self.steps, self.seen = list(steps), []

    def __call__(self, messages, info):
        self.seen.append((messages, info))
        return self.steps.pop(0)(messages, info)


def service(script, **kw):
    return AgentDiagnosisService(FunctionModel(script), **kw)


# the validator's rejection reaches the model as a part carrying its message
def retried(script) -> bool:
    return any("cite only evidence ids" in str(getattr(p, "content", ""))
               for m, _ in script.seen for msg in m for p in getattr(msg, "parts", []))


async def test_agent_reads_then_explains_rule_fix():
    script = Script(lambda m, i: call("get_service_health"),
                    lambda m, i: call("get_recent_changes", minutes_before_onset=10),
                    lambda m, i: final(i, cite=("journal:41", "query:err_ratio:service=payment")))
    box = make_box()
    result = await service(script).diagnose(box, "recent_change", RULE)
    assert result.error is None and result.action == RULE
    assert result.diagnosis.prediction.below == 0.05
    tools = [p["tool"] for kind, p in box.published if kind == "llm_called"]
    assert tools == ["get_service_health", "get_recent_changes"]
    usage = result.events[-1]["payload"]
    assert usage["usage"]["tool_calls"] == 2 and usage["attempt"] == 3


async def test_brief_is_thin_no_telemetry_up_front():
    script = Script(lambda m, i: call("get_recent_changes"), lambda m, i: final(i))
    await service(script).diagnose(make_box(), "recent_change", RULE)
    first_prompt = str(script.seen[0][0])
    assert "rollback_deploy" in first_prompt and "known_services" in first_prompt
    assert "err_ratio\\\": 0.4" not in first_prompt and "journal:41\\\", \\\"kind" not in first_prompt


async def test_citing_an_id_never_fetched_is_sent_back():
    script = Script(lambda m, i: final(i),  # journal:41 exists upstream but the model never looked
                    lambda m, i: call("get_recent_changes"),
                    lambda m, i: final(i))
    result = await service(script).diagnose(make_box(), "recent_change", RULE)
    assert retried(script) and result.diagnosis is not None and result.error is None


async def test_made_up_ids_forever_keep_rule_action_without_diagnosis():
    script = Script(*[lambda m, i: final(i, cite=("journal:99",))] * 5)
    result = await service(script).diagnose(make_box(), "recent_change", RULE)
    assert result.diagnosis is None and result.action == RULE and result.error == "invalid_diagnosis"


async def test_rule_action_needs_a_prediction():
    script = Script(lambda m, i: call("get_recent_changes"), lambda m, i: final(i, prediction=None),
                    lambda m, i: final(i))
    result = await service(script).diagnose(make_box(), "recent_change", RULE)
    assert retried(script) and result.diagnosis.prediction is not None


async def test_tools_vanish_after_round_cap():
    def look_while_allowed(m, i):
        return call("get_service_health") if i.function_tools else final(i, cite=("query:err_ratio:service=payment",))

    script = Script(*[look_while_allowed] * 10)
    box = make_box()
    result = await service(script, max_rounds=2).diagnose(box, "recent_change", RULE)
    offered = [len(info.function_tools) for _, info in script.seen]
    assert offered == [9, 9, 0] and result.diagnosis is not None and box.calls == 2


async def test_unknown_tool_and_bad_args_go_back_to_model():
    script = Script(lambda m, i: call("kubectl_delete", target="payment"),
                    lambda m, i: call("get_metric_history", service="payment", metric="err_ratio", minutes=999),
                    lambda m, i: call("get_recent_changes"),
                    lambda m, i: final(i))
    box = make_box()
    result = await service(script).diagnose(box, "recent_change", RULE)
    assert result.diagnosis is not None and box.calls == 1


async def test_deadline_keeps_rule_action():
    async def slow(m, i):
        await asyncio.sleep(1)
        return final(i)

    result = await AgentDiagnosisService(FunctionModel(slow), timeout_s=0.05).diagnose(make_box(), "recent_change",
                                                                                       RULE)
    assert result.diagnosis is None and result.action == RULE and result.error == "deadline_exceeded"
    assert result.events[-1]["payload"] == {"error": "deadline_exceeded"}


async def test_unknown_pattern_uses_agent_proposal():
    proposal = {"incident_id": "inc-1", "tool": "restart_service", "target": "payment", "pattern": "unknown",
                "evidence_ids": ["event:payment-1:payment:last"], "prediction": PREDICT}
    script = Script(lambda m, i: call("get_pods", service="payment"),
                    lambda m, i: final(i, cite=("event:payment-1:payment:last",), proposed=proposal))
    result = await service(script).diagnose(make_box(), "unknown", None)
    assert result.action is not None and result.action.tool == "restart_service"
    assert result.action.pattern == "unknown"


async def test_known_pattern_ignores_agent_proposal():
    proposal = {"incident_id": "inc-1", "tool": "scale", "target": "payment", "pattern": "recent_change",
                "params": {"replicas": 3}, "evidence_ids": ["journal:41"], "prediction": PREDICT}
    script = Script(lambda m, i: call("get_recent_changes"), lambda m, i: final(i, proposed=proposal))
    result = await service(script).diagnose(make_box(), "recent_change", RULE)
    assert result.action == RULE
