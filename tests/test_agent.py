import asyncio
import json

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
    tools = [p["tool"] for kind, p in box.published if kind == "tool_called"]
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


# glm-5.3-flash, live 2026-11-14: sends prediction as a JSON string on every retry, never as an object
async def test_prediction_sent_as_json_string_still_counts():
    script = Script(lambda m, i: call("get_recent_changes"),
                    *[lambda m, i: final(i, prediction=json.dumps(PREDICT))] * 3)
    result = await service(script).diagnose(make_box(), "recent_change", RULE)
    assert result.error is None and result.diagnosis.prediction.below == 0.05


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


# ---- BRAIN_MODE=agent: the model chooses among candidates, code builds the action -------------------------
OLDER = {"incident_id": "inc-1", "tool": "revert_config", "target": "payment", "params": {}, "pattern": "recent_change",
         "evidence_ids": ["journal:40"], "prediction": None, "journal_entry": 40}
CANDS = [{"id": "c1", "basis": "newest change, image on deployment/payment 50 s before errors began",
          "action": RULE.model_dump(mode="json")},
         {"id": "c2", "basis": "older change, flag on configmap/flagd-config 90 s before errors began", "action": OLDER}]
CAPS = [{"tool": t} for t in ("rollback_deploy", "revert_config", "restart_service", "scale", "raise_limit")]


def chosen(info: AgentInfo, decision, candidate=None, proposed=None, reason="The flag change fits the errors.",
           alternative="The image change came later but its pods are healthy.", prediction=PREDICT) -> ModelResponse:
    return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {
        "causes": [{"cause_class": "recent_change", "culprit": "payment", "evidence_ids": ["journal:41"],
                    "explanation": "payment env changed 10 s before errors began."}],
        "prediction": prediction, "proposed": proposed, "confidence": 0.8, "decision": decision,
        "candidate": candidate, "reason": reason, "alternative": alternative})])


def sent_back(script, text) -> bool:
    return any(text in str(getattr(p, "content", "")) for m, _ in script.seen for msg in m
               for p in getattr(msg, "parts", []))


async def choose(*steps, pattern="recent_change", rule=RULE, cands=CANDS):
    script = Script(lambda m, i: call("get_recent_changes"), *steps)
    result = await service(script, choose=True).diagnose(make_box(), pattern, rule, None, cands, CAPS)
    return script, result


async def test_accepting_the_rules_pick_keeps_the_rule_path():
    script, result = await choose(lambda m, i: chosen(i, "accept", "c1"))
    assert result.action == RULE and result.action.origin == "rule" and result.error is None
    first_prompt = str(script.seen[0][0])
    assert "candidates" in first_prompt and "capabilities" in first_prompt and "rule_action" not in first_prompt


# the decoy case: the newest change is not the cause, the model takes the older one
async def test_accepting_another_candidate_is_the_models_choice():
    _, result = await choose(lambda m, i: chosen(i, "accept", "c2"))
    assert (result.action.tool, result.action.journal_entry, result.action.origin) == ("revert_config", 40, "model")
    assert result.diagnosis.reason and result.diagnosis.alternative


async def test_proposing_another_built_tool_is_the_models_choice():
    proposal = {"incident_id": "inc-1", "tool": "scale", "target": "payment", "pattern": "unknown",
                "params": {"replicas": 3}, "evidence_ids": ["journal:41"], "origin": "rule"}
    _, result = await choose(lambda m, i: chosen(i, "other", proposed=proposal))
    # pattern and origin are set by code, whatever the model wrote
    assert (result.action.tool, result.action.pattern, result.action.origin) == ("scale", "recent_change", "model")


async def test_candidate_written_out_by_hand_becomes_the_code_built_one():
    by_hand = {**RULE.model_dump(mode="json"), "evidence_ids": ["journal:41"], "prediction": PREDICT}
    _, result = await choose(lambda m, i: chosen(i, "other", proposed=by_hand))
    assert result.action.origin == "rule" and result.action.journal_entry == 41


async def test_decline_sends_no_action_and_keeps_the_reason():
    _, result = await choose(lambda m, i: chosen(i, "decline", reason="Evidence is too thin; check the payment "
                                                                       "provider status page.", prediction=None))
    assert result.action is None and result.error is None
    assert result.diagnosis.decision == "decline" and "too thin" in result.diagnosis.reason


async def test_unusable_choices_go_back_to_the_model():
    degraded = {"incident_id": "inc-1", "tool": "enable_degraded_mode", "target": "payment",
                "pattern": "recent_change", "evidence_ids": ["journal:41"]}
    script, result = await choose(
        lambda m, i: final(i),                                       # no decision at all
        lambda m, i: chosen(i, "accept", "c9"),                      # not on the list
        lambda m, i: chosen(i, "other", proposed=degraded),          # a tool that is not built
    )
    assert sent_back(script, "set decision to accept, other or decline")
    assert sent_back(script, "candidate must be one of ['c1', 'c2']")
    # three strikes: the answer is dropped and the rule's pick goes on, as when the model is down
    assert result.diagnosis is None and result.error == "invalid_diagnosis"
    assert result.action == RULE and result.action.origin == "rule"


async def test_tool_that_is_not_built_is_named_in_the_rejection():
    degraded = {"incident_id": "inc-1", "tool": "enable_degraded_mode", "target": "payment",
                "pattern": "recent_change", "evidence_ids": ["journal:41"]}
    script, result = await choose(lambda m, i: chosen(i, "other", proposed=degraded),
                                  lambda m, i: chosen(i, "accept", "c1"))
    assert sent_back(script, "enable_degraded_mode is not an available capability") and result.action == RULE


async def test_accept_needs_a_prediction_and_a_reason():
    script, result = await choose(lambda m, i: chosen(i, "accept", "c1", prediction=None),
                                  lambda m, i: chosen(i, "accept", "c1", reason=" "),
                                  lambda m, i: chosen(i, "accept", "c1"))
    assert retried(script) and sent_back(script, "reason must say") and result.action == RULE


async def test_no_candidates_means_other_or_decline():
    script, result = await choose(lambda m, i: chosen(i, "accept", "c1"),
                                  lambda m, i: chosen(i, "decline", prediction=None),
                                  pattern="unknown", rule=None, cands=[])
    assert sent_back(script, "there are no candidates") and result.action is None


# a proposal smuggled next to "accept" or "decline" never becomes the action
async def test_proposal_counts_only_with_decision_other():
    extra = {"incident_id": "inc-1", "tool": "scale", "target": "payment", "pattern": "recent_change",
             "params": {"replicas": 3}, "evidence_ids": ["journal:41"]}
    _, result = await choose(lambda m, i: chosen(i, "decline", proposed=extra, prediction=None))
    assert result.action is None and result.diagnosis.proposed is None


async def test_no_rule_proposal_in_advise_mode_is_marked_as_the_models():
    proposal = {"incident_id": "inc-1", "tool": "restart_service", "target": "payment", "pattern": "unknown",
                "evidence_ids": ["event:payment-1:payment:last"], "prediction": PREDICT}
    script = Script(lambda m, i: call("get_pods", service="payment"),
                    lambda m, i: final(i, cite=("event:payment-1:payment:last",), proposed=proposal))
    result = await service(script).diagnose(make_box(), "unknown", None)
    assert result.action.origin == "model"


# live, inc-1794577880789: after two rejected answers the model sent decision=decline, reason="test",
# cause "placeholder", no evidence. It was accepted and a human was paged with "agent declined to act: test"
async def test_placeholder_decline_is_rejected_and_the_rule_pick_goes_on():
    def junk(m, i):
        return ModelResponse(parts=[ToolCallPart(i.output_tools[0].name, {
            "causes": [{"cause_class": "unknown", "culprit": "payment", "evidence_ids": [], "explanation": "placeholder"}],
            "prediction": None, "proposed": None, "confidence": 0.0, "decision": "decline", "candidate": None,
            "reason": "test", "alternative": "test"})])

    script, result = await choose(junk, junk, junk)
    assert sent_back(script, "reason must say")
    assert result.diagnosis is None and result.error == "invalid_diagnosis"
    assert result.action == RULE and result.action.origin == "rule"


async def test_decline_must_show_what_was_looked_at():
    def no_evidence(m, i):
        return ModelResponse(parts=[ToolCallPart(i.output_tools[0].name, {
            "causes": [{"cause_class": "unknown", "culprit": "payment", "evidence_ids": [],
                        "explanation": "Nothing in the changes explains the errors on payment."}],
            "prediction": None, "proposed": None, "confidence": 0.3, "decision": "decline", "candidate": None,
            "reason": "The recorded change does not match the symptoms; check the payment provider first.",
            "alternative": "A bad image, but the pods run the old one."})])

    script, result = await choose(no_evidence,
                                  lambda m, i: chosen(i, "decline", prediction=None,
                                                      reason="The env change does not explain errors on checkout; "
                                                             "check the payment provider status page first."))
    assert sent_back(script, "decline must cite") and result.action is None and result.error is None


def user_brief(script) -> dict:
    import json
    return json.loads(next(p.content for msg in script.seen[0][0] for p in msg.parts
                           if getattr(p, "part_kind", "") == "user-prompt"))


# ---- retry after a failed fix (§6.4.11): failed fixes are context for the model, never a choice again ----
TRIED = [{"attempt": 1, **RULE.model_dump(mode="json"), "why_undone": "did not recover", "severity_before": 4,
          "severity_after": 4, "recovered": False, "receipt_id": 3}]


async def test_retry_brief_shows_failed_fixes_and_a_repeat_is_refused():
    repeat = {**RULE.model_dump(mode="json"), "prediction": PREDICT}
    left = [{**CANDS[1], "id": "c1"}]  # brain/main.py drops the failed rule pick and renumbers
    script = Script(lambda m, i: call("get_recent_changes"),
                    lambda m, i: chosen(i, "other", proposed=repeat),
                    lambda m, i: chosen(i, "accept", "c1"))
    result = await service(script, choose=True).diagnose(make_box(), "recent_change", None, None, left, CAPS,
                                                         tried=TRIED)
    brief = user_brief(script)
    assert brief["failed_attempts"][0]["why_undone"] == "did not recover"
    assert sent_back(script, "that fix already failed in this incident")
    assert (result.action.tool, result.action.journal_entry, result.action.origin) == ("revert_config", 40, "model")


async def test_first_try_brief_has_no_failed_attempts():
    script, _ = await choose(lambda m, i: chosen(i, "accept", "c1"))
    assert "failed_attempts" not in user_brief(script)
