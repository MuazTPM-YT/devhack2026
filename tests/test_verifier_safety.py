from gateway.verifier import Verification


def service(unhealthy, error):
    return {"unhealthy": unhealthy, "breaching": unhealthy, "bad_pods": 0, "err_ratio": error}


def verification():
    before = {"severity": 4, "services": {"payment": service(True, 0.4)}}
    prediction = {"metric": "err_ratio", "target": "payment", "below": 0.05, "within_s": 60}
    return Verification(0, before, "payment", [], prediction, 120, True)


def test_missing_service_cannot_confirm_recovery_after_prediction():
    verifier = verification()
    verifier.step(5, {"severity": 0, "services": {"payment": service(False, 0.01)}}, False)
    assert verifier.step(25, {"severity": 0, "services": {}}, False) != "recovered"
    assert verifier.outcome(True) == "undo"


def test_human_change_takes_priority_over_early_abort():
    verifier = verification()
    health = {"severity": 9, "services": {"payment": service(True, 0.8)}}
    assert verifier.step(5, health, non_agent_change=True) == "handed_off"
