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
