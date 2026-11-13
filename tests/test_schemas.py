import pytest
from pydantic import ValidationError

from schemas.models import ActionRequest, Event, Prediction


def test_unknown_tool_and_event_rejected():
    with pytest.raises(ValidationError):
        ActionRequest(incident_id="i", tool="delete", target="payment", pattern="unknown", evidence_ids=[])
    with pytest.raises(ValidationError):
        Event(type="invented")


def test_prediction_deadline_is_bounded():
    with pytest.raises(ValidationError):
        Prediction(metric="err_ratio", target="payment", below=0.05, within_s=0)


def test_payload_contract_rejects_incomplete_approval():
    with pytest.raises(ValidationError):
        Event(type="approval_requested", incident_id="i", payload={"approval_id": "a"})


def test_payload_rejects_cross_incident_card():
    with pytest.raises(ValidationError):
        Event(type="incident_resolved", incident_id="i", payload={"card": {
            "incident_id": "other", "status": "FIXED", "text": "done", "evidence_ids": [],
        }})


def test_evidence_rejects_nonfinite_timestamp():
    from schemas.models import Evidence
    with pytest.raises(ValidationError):
        Evidence(id="query:x", kind="query", summary="metric", ts=float("nan"))


@pytest.mark.parametrize("pattern", ["recent_change", "resource", "protected", "unknown"])
def test_shared_pattern_values(action, pattern):
    value = ActionRequest.model_validate({**action.model_dump(), "pattern": pattern})
    assert value.pattern == pattern


def test_action_rejects_invented_pattern(action):
    with pytest.raises(ValidationError):
        ActionRequest.model_validate({**action.model_dump(), "pattern": "trusted-because-model-said-so"})


def test_tool_read_is_its_own_event_not_a_model_call():
    from schemas.models import Event
    ev = Event(type="tool_called", incident_id="inc-1",
               payload={"tool": "get_pods", "args": {"service": "payment"}, "ms": 12, "evidence_ids": ["event:1"]})
    assert ev.payload["tool"] == "get_pods" and ev.payload["evidence_ids"] == ["event:1"]
    with pytest.raises(ValidationError):
        Event(type="tool_called", incident_id="inc-1", payload={"args": {}})
    with pytest.raises(ValidationError):
        Event(type="tool_called", payload={"tool": "get_pods"})


def test_action_origin_defaults_to_rule_and_rejects_anything_else(action):
    assert action.origin == "rule"
    assert ActionRequest.model_validate({**action.model_dump(), "origin": "model"}).origin == "model"
    with pytest.raises(ValidationError):
        ActionRequest.model_validate({**action.model_dump(), "origin": "trusted"})
