import unittest

from gateway.dryrun import spec_hashes
from gateway.verifier import Verification, harm_check, ledger_effect


def svc(unhealthy=False, breaching=False, err=None):
    return {"unhealthy": unhealthy, "breaching": breaching, "bad_pods": 0, "err_ratio": err}


def health(severity, **services):
    return {"severity": severity, "services": services}


START = health(8, payment=svc(True, True, 0.4), checkout=svc(True, True, 0.2), cart=svc())
FIXED = health(0, payment=svc(err=0.01), checkout=svc(err=0.0), cart=svc())
PRED = {"metric": "err_ratio", "target": "payment", "below": 0.05, "within_s": 60}


def verification(prediction=PRED):
    return Verification(0, START, "payment", ["checkout"], prediction, window_s=120, early_abort=True)


class VerifierTest(unittest.TestCase):
    def test_recovers_after_15s_stable_and_prediction_held(self):
        v = verification()
        self.assertIsNone(v.step(5, START, False))
        self.assertIsNone(v.step(10, FIXED, False))
        self.assertIsNone(v.step(20, FIXED, False))
        self.assertEqual(v.step(25, FIXED, False), "recovered")
        self.assertEqual(v.outcome(harm_clean=True), "success")
        self.assertEqual(v.outcome(harm_clean=False), "undo")

    def test_early_abort_when_severity_rises(self):
        self.assertEqual(verification().step(5, health(9, **START["services"]), False), "early_abort")

    def test_hands_off_on_non_agent_change(self):
        self.assertEqual(verification().step(5, START, True), "handed_off")

    def test_relapse_resets_stable_clock(self):
        v = verification()
        v.step(5, FIXED, False)
        v.step(15, START, False)
        self.assertIsNone(v.step(25, FIXED, False))
        self.assertEqual(v.step(40, FIXED, False), "recovered")

    def test_prediction_missed_is_right_by_accident(self):
        v = verification({**PRED, "within_s": 5})
        v.step(5, START, False)
        for t in range(10, 125, 5):
            got = v.step(t, FIXED, False)
        self.assertEqual(got, "window_end")
        self.assertEqual(v.outcome(harm_clean=True), "right_by_accident")
        self.assertIsNone(ledger_effect("right_by_accident"))

    # live flag revert: predicted "within 60 s", flagd reloads ~60 s later, recovered at ~110 s
    def test_flag_propagation_delay_extends_the_prediction_deadline(self):
        late = {"severity": 0, "services": FIXED["services"]}
        plain = verification()
        flag = Verification(0, START, "payment", ["checkout"], PRED, window_s=210, early_abort=True,
                            prediction_delay_s=90)
        for v in (plain, flag):
            v.step(100, START, False)
            v.step(110, late, False)
        self.assertFalse(plain.prediction_held)
        self.assertTrue(flag.prediction_held)
        flag.step(200, START, False)  # past within_s + delay: a late dip doesn't count, but held stays held
        self.assertTrue(flag.prediction_held)

    def test_never_recovers_is_undo(self):
        v = verification()
        for t in range(5, 125, 5):
            got = v.step(t, START, False)
        self.assertEqual((got, v.outcome(True)), ("window_end", "undo"))
        self.assertIs(ledger_effect("undo"), False)

    def test_collateral_counts_healthy_service_going_down(self):
        v = verification()
        v.step(5, START, False)
        v.step(10, health(8, **{**START["services"], "cart": svc(True)}), False)
        self.assertEqual(v.collateral, {"cart": 5})


class HarmCheckTest(unittest.TestCase):
    def setUp(self):
        dep = {"metadata": {"name": "payment"}, "spec": {"replicas": 2}}
        cm = {"metadata": {"name": "flagd-config", "resourceVersion": "1"}, "data": {"a": "1"}}
        self.before = spec_hashes([dep], [cm])
        dep2 = {**dep, "spec": {"replicas": 3}, "status": {"x": 1}}
        cm_meta_only = {**cm, "metadata": {"name": "flagd-config", "resourceVersion": "2"}}
        self.after = spec_hashes([dep2], [cm_meta_only])

    def test_hash_ignores_metadata_and_status(self):
        self.assertEqual(self.before["configmap/flagd-config"], self.after["configmap/flagd-config"])
        self.assertNotEqual(self.before["deployment/payment"], self.after["deployment/payment"])

    def test_clean_when_only_declared_changed(self):
        got = harm_check(self.before, self.after, "deployment/payment", set(), FIXED, FIXED, {"payment"})
        self.assertTrue(got["clean"])

    def test_unexpected_change_or_worse_service_is_harm(self):
        after = {**self.after, "configmap/flagd-config": "changed"}
        self.assertEqual(harm_check(self.before, after, "deployment/payment", set(), FIXED, FIXED, set())
                         ["unexpected_changes"], ["configmap/flagd-config"])
        self.assertTrue(harm_check(self.before, after, "deployment/payment", {"configmap/flagd-config"},
                                   FIXED, FIXED, set())["clean"])
        worse = health(3, **{**FIXED["services"], "cart": svc(breaching=True)})
        got = harm_check(self.before, self.after, "deployment/payment", set(), FIXED, worse, {"payment"})
        self.assertEqual((got["clean"], got["worse_services"]), (False, ["cart"]))

    def test_declared_object_unchanged_is_not_clean(self):
        self.assertFalse(harm_check(self.before, self.before, "deployment/payment", set(), FIXED, FIXED,
                                    set())["clean"])


if __name__ == "__main__":
    unittest.main()


# live run 2026-11-13: trace victim frontend-proxy is not in /health/now, so recovery could never pass
class VictimOutsideHealthTest(unittest.TestCase):
    def test_victim_the_observer_does_not_measure_is_not_waited_on(self):
        start = health(8, payment=svc(True, True, 0.4))
        v = Verification(0, start, "payment", ["frontend-proxy"], None, window_s=120, early_abort=True)
        v.step(5, health(0, payment=svc(err=0.01)), False)
        self.assertEqual(v.step(20, health(0, payment=svc(err=0.01)), False), "recovered")

    def test_measured_service_that_vanishes_still_blocks_recovery(self):
        start = health(8, payment=svc(True, True, 0.4), checkout=svc(True, True, 0.2))
        v = Verification(0, start, "payment", ["checkout"], None, window_s=120, early_abort=True)
        v.step(5, health(0, payment=svc(err=0.01)), False)
        self.assertIsNone(v.step(20, health(0, payment=svc(err=0.01)), False))


# observer down: it keeps serving its last numbers with prometheus_ok false. Old numbers prove nothing
class StaleReadingsTest(unittest.TestCase):
    def test_stale_healthy_numbers_never_count_as_recovered_or_as_the_prediction(self):
        stale = {**FIXED, "prometheus_ok": False}
        v = verification()
        for t in (5, 10, 20, 30, 60):
            self.assertIsNone(v.step(t, stale, False))
        self.assertFalse(v.prediction_held)
        self.assertFalse(v.recovered)
        self.assertEqual(v.step(120, stale, False), "window_end")
        self.assertTrue(v.blind)
        self.assertEqual(v.outcome(harm_clean=True), "undo")

    def test_fresh_numbers_after_a_blind_spell_start_the_stable_window_again(self):
        v = verification()
        self.assertIsNone(v.step(5, {**FIXED, "prometheus_ok": True}, False))
        self.assertIsNone(v.step(15, {**FIXED, "prometheus_ok": False}, False))
        self.assertIsNone(v.step(21, {**FIXED, "prometheus_ok": True}, False))  # 16 s after t=5, but not 15 s fresh
        self.assertEqual(v.step(36, {**FIXED, "prometheus_ok": True}, False), "recovered")
        self.assertFalse(v.blind)

    def test_stale_severity_is_not_harm(self):
        v = verification()
        worse = {**health(12, payment=svc(True, True, 0.4), checkout=svc(True, True, 0.2), cart=svc(True, True)),
                 "prometheus_ok": False}
        self.assertIsNone(v.step(70, worse, False))
        self.assertEqual(v.step(75, {**worse, "prometheus_ok": True}, False), "early_abort")
