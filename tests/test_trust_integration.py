import pytest

from brain import rules
from gateway import trust
from gateway.receipts import build_card
from gateway.verifier import Verification, ledger_effect
from schemas.db import connect
from schemas.models import ActionRequest, Receipt

POLICY = {"confidence": 0.95, "bar": 0.90, "reset_on_failure": True}
KEY = ("recent_change", "rollback_deploy", "payment")


def health(unhealthy, severity=0, error=0.01):
    return {"severity": severity, "services": {"payment": {
        "unhealthy": unhealthy, "breaching": unhealthy, "bad_pods": 0, "err_ratio": error,
    }}}


@pytest.mark.parametrize("case,expected_successes,expected_failures,expected_open", [
    ("verified", 29, 0, True),
    ("late_prediction", 28, 0, False),
    ("harm", 28, 1, False),
    ("early_abort", 28, 1, False),
    ("human_edit", 28, 0, False),
    ("missing_service", 28, 1, False),
])
def test_verified_outcome_controls_persisted_trust_and_card(
    case, expected_successes, expected_failures, expected_open, tmp_path,
):
    db = connect(str(tmp_path / "oncall.db"))
    try:
        for _ in range(28):
            trust.record(db, *KEY, "rehearsal", True, 1)
        prediction = {"metric": "err_ratio", "target": "payment", "below": 0.05,
                      "within_s": 1 if case == "late_prediction" else 60}
        verifier = Verification(0, health(True, 4, 0.4), "payment", [], prediction, 120, True)
        verifier.step(5, health(False), False)
        reading = (health(True, 9, 0.8) if case in {"early_abort", "human_edit"}
                   else {"severity": 0, "services": {}} if case == "missing_service" else health(False))
        step = verifier.step(25, reading, non_agent_change=case == "human_edit")
        outcome = step if step in {"early_abort", "handed_off"} else verifier.outcome(case != "harm")
        effect = ledger_effect(outcome)
        if effect is not None:
            trust.record(db, *KEY, "real", effect, 25)
        gate = trust.check(db, POLICY, {"auto_eligible": True}, *KEY, "stateless")
        assert (gate["successes"], gate["failures"], gate["open"]) == (
            expected_successes, expected_failures, expected_open,
        )
        receipt = Receipt(incident_id="i", tool="rollback_deploy", target="payment", diff={},
                          inverse={"image": "old"}, evidence_ids=["journal:41"],
                          outcome={"undo": "undone", "early_abort": "undone"}.get(outcome, outcome),
                          prediction_held=verifier.prediction_held, harm_clean=case != "harm")
        card = build_card(receipt, 1)
        assert (card.status == "FIXED") is (case == "verified")
        assert len(card.text.splitlines()) == 5
    finally:
        db.close()


def test_resource_rule_actions_keep_different_approval_eligibility(tmp_path):
    pattern, proposals = rules.match(
        {"id": "i", "onset_at": 100, "culprit": "recommendation"}, [],
        [{"id": "event:oom", "summary": "OOMKilled"}],
        {"recommendation": {"kind": "stateless"}},
        {"change_window_minutes": 10, "tools": {"raise_limit": {"max_memory": "1Gi"}}},
        memory_limit="128Mi",
    )
    actions = [ActionRequest.model_validate(value) for value in proposals]
    assert pattern == "resource"
    assert [action.tool for action in actions] == ["restart_service", "raise_limit"]
    db = connect(str(tmp_path / "oncall.db"))
    try:
        for action in actions:
            for _ in range(30):
                trust.record(db, action.pattern, action.tool, action.target, "rehearsal", True, 1)
        tool_policies = {"restart_service": {"auto_eligible": "stateless_only"},
                         "raise_limit": {"auto_eligible": False}}
        gates = [trust.check(db, POLICY, tool_policies[action.tool], action.pattern,
                             action.tool, action.target, "stateless")["open"] for action in actions]
        assert gates == [True, False]
    finally:
        db.close()
