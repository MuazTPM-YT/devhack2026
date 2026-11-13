import json

import pytest

from bench.harness import TrialResult, measure
from bench.report import load_rows, summarize, summarize_by_mode


def rec(ts, etype, incident="inc-a", **payload):
    return {"seq": int(ts), "ts": ts, "event": {"type": etype, "incident_id": incident, "payload": payload}}


def test_measure_follows_first_incident_and_counts_orchestration():
    result = TrialResult("bad-deploy", 100.0, "failed")
    measure(result, {"target": "payment"}, [
        rec(110, "incident_opened"),
        rec(111, "incident_opened", incident="inc-b"),  # a second incident in the window
        rec(112, "delegation_decided", status="none_needed", explanation="x"),
        rec(113, "delegation_decided", status="denied", reason="simple_read_sufficient", explanation="x"),
        rec(114, "delegation_decided", status="admitted", explanation="x"),
        rec(115, "evidence_reused", query_key="k", source="cache", age_s=1),
        rec(116, "llm_called", kind="call", usage={"prompt_tokens": 100, "completion_tokens": 10}),
        rec(117, "llm_called", kind="call", usage={"prompt_tokens": 50, "completion_tokens": 5}),
        rec(118, "llm_called", kind="summary", usage={"prompt_tokens": 150, "completion_tokens": 15, "requests": 2}),
        rec(120, "action_intent_changed", intent_id="i", status="queued", plan_revision=0),
        rec(130, "action_intent_changed", intent_id="i", status="awaiting_approval", plan_revision=0),
        rec(131, "approval_requested", approval_id="a"),
        rec(171, "approval_decided", approval_id="a", decision="approved"),
        rec(172, "llm_called", incident="inc-b", kind="call", usage={"prompt_tokens": 999}),
        rec(200, "incident_resolved"),
    ])
    assert result.incident_id == "inc-a" and result.incidents_opened == 2
    assert result.specialist_starts == 1 and result.delegation_denied == {"simple_read_sufficient": 1}
    assert result.evidence_reused == 1 and result.model_calls == 2
    assert result.usage == {"prompt_tokens": 150, "completion_tokens": 15}  # summary not added again
    assert (result.queue_wait_s, result.approval_wait_s) == (10, 40)
    assert result.outcome == "incident_resolved" and result.recover_s == 100


def test_old_rows_still_load(tmp_path):
    old = {"scenario": "bad-deploy", "started_at": 1.0, "outcome": "incident_resolved", "recover_s": 90.0}
    assert TrialResult(**old).incidents_opened == 0
    path = tmp_path / "r.jsonl"
    path.write_text(json.dumps(old) + "\n")
    summary = summarize(load_rows(path))
    o = summary["bad-deploy"]["orchestration"]
    assert o["grouping_samples"] == 0 and o["grouping_exact"] is None and o["modes"] == {"unlabelled": 1}


@pytest.mark.parametrize("field, value", [("incidents_opened", -1), ("delegation_denied", {"x": "1"}),
                                          ("queue_wait_s", float("inf")), ("mode", 3)])
def test_invalid_orchestration_fields_rejected(tmp_path, field, value):
    path = tmp_path / "r.jsonl"
    path.write_text(json.dumps({"scenario": "bad-deploy", field: value}, allow_nan=True) + "\n")
    with pytest.raises(ValueError):
        load_rows(path)


def rows():
    base = {"scenario": "bad-deploy", "outcome": "incident_resolved"}
    return [{**base, "mode": "disabled", "model_calls": None},
            {**base, "mode": "coordinated", "incidents_opened": 1, "model_calls": 4, "specialist_starts": 0},
            {**base, "mode": "coordinated", "incidents_opened": 2, "model_calls": 6, "specialist_starts": 0},
            {**base, "mode": "coordinated+delegation", "incidents_opened": 1, "model_calls": 9,
             "specialist_starts": 1}]


def test_gates_and_grouping_per_mode():
    by_mode = summarize_by_mode(rows())
    assert set(by_mode) == {"disabled", "coordinated", "coordinated+delegation"}
    coordinated = by_mode["coordinated"]["bad-deploy"]["orchestration"]
    assert coordinated["grouping_exact"] == 0.5 and coordinated["model_calls"]["worst"] == 6
    assert coordinated["gates"] == {"no_unneeded_specialists": True, "within_request_budget": True}
    # a clear single fault never needs a specialist: one start fails the gate
    assert by_mode["coordinated+delegation"]["bad-deploy"]["orchestration"]["gates"]["no_unneeded_specialists"] is False
