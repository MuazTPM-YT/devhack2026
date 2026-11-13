import pytest
from pydantic import ValidationError

from schemas.models import ActionRequest, Event
from schemas.orchestration import (AdmissionResult, FindingResult, IncidentLink, IntentEnvelope,
                                   OrchestrationPolicy, SignalBatch, fingerprint, intent_fingerprint,
                                   load_policy)


def test_no_config_file_means_disabled(tmp_path):
    policy = load_policy(str(tmp_path))
    assert policy.mode == "disabled" and policy.delegation_enabled is False


def test_repo_config_loads_and_is_disabled():
    policy = load_policy()
    assert policy.mode == "disabled" and policy.delegation_enabled is False
    # shipped off; token limits measured from recorded runs so delegation can be switched on deliberately
    assert policy.max_input_tokens_per_request == 24000 and policy.max_total_tokens == 120000
    assert policy.model_copy(update={"max_input_tokens_per_request": None, "max_total_tokens": None}) == \
        OrchestrationPolicy()


def test_config_typo_fails_loud(tmp_path):
    (tmp_path / "orchestration.yaml").write_text("mode: disabled\nmax_modle_requests: 3\n")
    with pytest.raises(ValidationError, match="max_modle_requests"):
        load_policy(str(tmp_path))


@pytest.mark.parametrize("bad, words", [
    ({"max_delegation_depth": 2}, "max_delegation_depth"),
    ({"reserved_commander_requests": 9}, "reserved_commander_requests"),
    ({"max_requests_per_specialist": 8}, "commander reserve"),
    ({"max_specialist_tool_calls": 30}, "max_specialist_tool_calls"),
    ({"specialist_deadline_seconds": 200}, "specialist_deadline_seconds"),
    ({"task_heartbeat_seconds": 30}, "task_heartbeat_seconds"),
    ({"max_model_requests": 0}, "greater than 0"),
    ({"mode": "parallel"}, "mode"),
    ({"delegation_enabled": True, "mode": "shadow", "max_input_tokens_per_request": 1,
      "max_total_tokens": 1}, "needs mode coordinated"),
    ({"delegation_enabled": True, "mode": "coordinated"}, "token"),
])
def test_impossible_policy_rejected(bad, words):
    with pytest.raises(ValidationError, match=words):
        OrchestrationPolicy.model_validate(bad)


def test_delegation_allowed_with_coordinated_and_token_limits():
    p = OrchestrationPolicy(mode="coordinated", delegation_enabled=True, max_input_tokens_per_request=20000,
                            max_total_tokens=80000)
    assert p.delegation_enabled


def test_fingerprint_ignores_key_order():
    assert fingerprint({"a": 1, "b": [1, 2]}) == fingerprint({"b": [1, 2], "a": 1})
    assert fingerprint({"a": 1}) != fingerprint({"a": 2})


def envelope(action: ActionRequest, plan: int = 1, **kw) -> IntentEnvelope:
    return IntentEnvelope(intent_id="intent-0001", incident_id=action.incident_id, scope_revision=0,
                          plan_revision=plan, fingerprint=intent_fingerprint(action.incident_id, plan, action),
                          action=action, **kw)


def test_intent_wraps_unchanged_action(action):
    env = envelope(action)
    assert env.action == action
    # the legacy ActionRequest still forbids extra fields: orchestration identity never leaks into it
    with pytest.raises(ValidationError):
        ActionRequest.model_validate({**action.model_dump(), "intent_id": "x"})


def test_intent_fingerprint_must_match_plan_and_action(action):
    with pytest.raises(ValidationError, match="fingerprint"):
        IntentEnvelope(intent_id="intent-0001", incident_id=action.incident_id, scope_revision=0, plan_revision=2,
                       fingerprint=intent_fingerprint(action.incident_id, 1, action), action=action)
    other = action.model_copy(update={"target": "cart"})
    assert intent_fingerprint("i", 1, action) != intent_fingerprint("i", 1, other)
    assert intent_fingerprint("i", 1, action) != intent_fingerprint("i", 2, action)


def test_intent_rejects_foreign_incident(action):
    with pytest.raises(ValidationError, match="another incident"):
        IntentEnvelope(intent_id="intent-0001", incident_id="other", scope_revision=0, plan_revision=1,
                       fingerprint=intent_fingerprint("other", 1, action), action=action)


def test_admission_reason_only_on_denial():
    assert AdmissionResult(status="denied", reason="child_limit").reason == "child_limit"
    with pytest.raises(ValidationError):
        AdmissionResult(status="denied")
    with pytest.raises(ValidationError):
        AdmissionResult(status="admitted", reason="deadline")
    with pytest.raises(ValidationError):
        AdmissionResult(status="denied", reason="model_asked_nicely")


def test_finding_has_no_action_or_instructions():
    f = FindingResult(question_id="q", hypothesis_id="c2", verdict="supported", summary="flag change broke it")
    assert "proposed" not in FindingResult.model_fields and "action" not in FindingResult.model_fields
    with pytest.raises(ValidationError):
        FindingResult.model_validate({**f.model_dump(), "action": {"tool": "scale"}})


def test_link_pair_is_canonical():
    IncidentLink(incident_a="inc-a", incident_b="inc-b", relation="related", reason="unknown_topology")
    with pytest.raises(ValidationError):
        IncidentLink(incident_a="inc-b", incident_b="inc-a", relation="related", reason="unknown_topology")


def test_signal_batch_is_bounded():
    ep = {"episode_id": "ep-00000001", "service": "cart", "symptom": "errors", "sustained_at": 1.0,
          "last_observed_at": 1.0, "source_revision": 1}
    SignalBatch(delivery_id="deliv-001", source_revision=1, observed_at=1.0, episodes=[ep])
    with pytest.raises(ValidationError):
        SignalBatch(delivery_id="deliv-001", source_revision=1, observed_at=1.0, episodes=[ep] * 201)


def test_old_event_shape_unchanged_without_event_id():
    ev = Event(type="incident_opened", incident_id="inc-1", payload={"x": 1})
    assert "event_id" not in ev.model_dump(mode="json")
    tagged = Event(type="incident_opened", incident_id="inc-1", event_id="e-1")
    assert tagged.model_dump(mode="json")["event_id"] == "e-1"


@pytest.mark.parametrize("kind, payload", [
    ("incident_scope_changed", {"scope_revision": 1, "services": ["cart"], "reasons": ["shared_dependency"]}),
    ("delegation_decided", {"status": "none_needed", "explanation": "shared dependency already supported"}),
    ("investigation_task_changed", {"task_id": "t1", "question_id": "q1", "state": "running", "attempt": 1}),
    ("finding_recorded", {"task_id": "t1", "finding_id": "f1", "question_id": "q1", "verdict": "refuted",
                          "summary": "decoy env change did not reach traffic"}),
    ("evidence_reused", {"query_key": "k", "source": "cache", "age_s": 2.0}),
    ("orchestration_budget_changed", {"requests_used": 3, "requests_limit": 9}),
    ("action_intent_changed", {"intent_id": "intent-0001", "status": "queued", "plan_revision": 1}),
])
def test_orchestration_events_validate(kind, payload):
    assert Event(type=kind, incident_id="inc-1", payload=payload).type == kind
    with pytest.raises(ValidationError):
        Event(type=kind, payload=payload)  # lifecycle events need an incident
    with pytest.raises(ValidationError):
        Event(type=kind, incident_id="inc-1", payload={})


def test_intent_event_rejects_unknown_status():
    with pytest.raises(ValidationError):
        Event(type="action_intent_changed", incident_id="inc-1",
              payload={"intent_id": "intent-0001", "status": "retrying", "plan_revision": 1})
