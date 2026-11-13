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


# live smoke: checkout crossed its sustain window 10 s after a good rollback, sev 7->8, the fix got aborted
def test_brief_severity_rise_after_action_does_not_abort():
    before = {"severity": 7, "services": {"payment": service(True, 0.4), "checkout": service(True, 0.3)}}
    verifier = Verification(0, before, "payment", ["checkout"], None, 120, True)
    lagging = {**before, "severity": 8}
    assert verifier.step(5, lagging, False) is None
    assert verifier.step(10, lagging, False) is None
    healthy = {"severity": 0, "services": {"payment": service(False, 0.0), "checkout": service(False, 0.0)}}
    verifier.step(15, healthy, False)
    assert verifier.step(30, healthy, False) == "recovered"


def test_severity_rise_held_for_abort_window_aborts_and_dip_resets_clock():
    before = {"severity": 4, "services": {"payment": service(True, 0.4)}}
    verifier = Verification(0, before, "payment", [], None, 120, True)
    worse, same = {**before, "severity": 9}, before
    assert verifier.step(5, worse, False) is None
    assert verifier.step(10, same, False) is None
    for t in range(15, 45, 5):
        assert verifier.step(t, worse, False) is None
    assert verifier.step(45, worse, False) == "early_abort"
