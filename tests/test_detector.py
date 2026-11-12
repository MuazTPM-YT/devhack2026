import unittest

from observer.detector import Detector


def det():
    return Detector(err_threshold=0.05, latency_multiplier=2.0, sustain_s=30, group_within_s=120)


class DetectorTest(unittest.TestCase):
    def test_healthy_opens_nothing(self):
        health, event = det().tick(0, {"payment": {"err_ratio": 0.01, "p95_ms": 100}}, {"payment": 100}, {})
        self.assertIsNone(event)
        self.assertEqual(health["severity"], 0)
        self.assertFalse(health["services"]["payment"]["unhealthy"])

    def test_error_breach_must_sustain_30s(self):
        d = det()
        bad = {"payment": {"err_ratio": 0.4}}
        health, event = d.tick(100, bad, {}, {})
        self.assertTrue(health["services"]["payment"]["breaching"])
        self.assertIsNone(event)
        self.assertIsNone(d.tick(129, bad, {}, {})[1])
        health, event = d.tick(130, bad, {}, {})
        self.assertEqual(event[0], "incident_opened")
        self.assertEqual(event[1]["onset_at"], 100)
        self.assertEqual(event[1]["unhealthy"], ["payment"])
        self.assertEqual(health["severity"], 3 + 1)

    def test_recovery_resets_sustain_clock(self):
        d = det()
        d.tick(0, {"payment": {"err_ratio": 0.4}}, {}, {})
        d.tick(20, {"payment": {"err_ratio": 0.0}}, {}, {})
        d.tick(25, {"payment": {"err_ratio": 0.4}}, {}, {})
        self.assertIsNone(d.tick(50, {"payment": {"err_ratio": 0.4}}, {}, {})[1])
        self.assertEqual(d.tick(55, {"payment": {"err_ratio": 0.4}}, {}, {})[1][1]["onset_at"], 25)

    def test_latency_breach_needs_baseline(self):
        d = det()
        self.assertFalse(d.tick(0, {"cart": {"p95_ms": 500}}, {}, {})[0]["services"]["cart"]["breaching"])
        self.assertFalse(d.tick(0, {"cart": {"p95_ms": 200}}, {"cart": 100}, {})[0]["services"]["cart"]["breaching"])
        self.assertTrue(d.tick(0, {"cart": {"p95_ms": 201}}, {"cart": 100}, {})[0]["services"]["cart"]["breaching"])

    def test_bad_pod_is_unhealthy_at_once(self):
        health, event = det().tick(10, {}, {}, {"recommendation": 1})
        self.assertEqual(event[0], "incident_opened")
        self.assertEqual(event[1]["onset_at"], 10)
        self.assertEqual(health["severity"], 2 + 1)

    def test_grouping_inside_window_only(self):
        d = det()
        d.tick(0, {}, {}, {"payment": 1})
        _, event = d.tick(60, {}, {}, {"payment": 1, "checkout": 1})
        self.assertEqual(event[0], "alerts_grouped")
        self.assertEqual(event[1]["unhealthy"], ["checkout", "payment"])
        self.assertIsNone(d.tick(200, {}, {}, {"payment": 1, "checkout": 1, "cart": 1})[1])
        self.assertEqual(d.incident["unhealthy"], ["checkout", "payment"])

    def test_close_lets_next_incident_open(self):
        d = det()
        d.tick(0, {}, {}, {"payment": 1})
        self.assertIsNone(d.tick(5, {}, {}, {"payment": 1})[1])
        d.close_incident()
        self.assertEqual(d.tick(10, {}, {}, {"payment": 1})[1][0], "incident_opened")


if __name__ == "__main__":
    unittest.main()
