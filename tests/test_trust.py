import unittest

from gateway import trust
from schemas.db import connect

POLICY = {"confidence": 0.95, "bar": 0.90, "reset_on_failure": True}
AUTO = {"auto_eligible": True}


class TrustTest(unittest.TestCase):
    def test_bound_reference_values(self):
        self.assertAlmostEqual(trust.lower_bound(10, 0), 0.741, places=3)
        self.assertAlmostEqual(trust.lower_bound(30, 0), 0.905, places=3)
        self.assertAlmostEqual(trust.lower_bound(59, 0), 0.950, places=3)
        self.assertEqual(trust.lower_bound(0, 0), 0.0)

    def test_eligibility(self):
        self.assertTrue(trust.eligible(AUTO, "stateful"))
        self.assertFalse(trust.eligible({"auto_eligible": False}, "stateless"))
        self.assertTrue(trust.eligible({"auto_eligible": "stateless_only"}, "stateless"))
        self.assertFalse(trust.eligible({"auto_eligible": "stateless_only"}, "stateful"))

    # 0.05**(1/28) = 0.899 < 0.90 <= 0.05**(1/29) = 0.902: gate opens at 29 clean runs
    def test_gate_opens_at_29_and_one_failure_closes_it(self):
        conn = connect(":memory:")
        key = ("recent_change", "rollback_deploy", "payment")
        for _ in range(28):
            trust.record(conn, *key, "rehearsal", True, 1.0)
        self.assertFalse(trust.check(conn, POLICY, AUTO, *key, "stateless")["open"])
        trust.record(conn, *key, "real", True, 2.0)
        got = trust.check(conn, POLICY, AUTO, *key, "stateless")
        self.assertTrue(got["open"])
        self.assertEqual((got["rehearsal"], got["real"], got["successes"]), ((28, 0), (1, 0), 29))
        trust.record(conn, *key, "real", False, 3.0)
        got = trust.check(conn, POLICY, AUTO, *key, "stateless")
        self.assertFalse(got["open"])
        self.assertEqual(got["failures"], 1)
        row = conn.execute("SELECT last_failure_at FROM ledger WHERE source='real'").fetchone()
        self.assertEqual(row[0], 3.0)

    def test_unknown_pattern_and_ineligible_never_open(self):
        conn = connect(":memory:")
        for _ in range(60):
            trust.record(conn, "unknown", "scale", "ad", "rehearsal", True, 1.0)
            trust.record(conn, "resource", "raise_limit", "ad", "rehearsal", True, 1.0)
        self.assertFalse(trust.check(conn, POLICY, AUTO, "unknown", "scale", "ad", "stateless")["open"])
        self.assertFalse(trust.check(conn, POLICY, {"auto_eligible": False}, "resource", "raise_limit", "ad",
                                     "stateless")["open"])

    def test_reset_on_failure_false_fails_loud(self):
        with self.assertRaises(ValueError):
            trust.check(connect(":memory:"), {**POLICY, "reset_on_failure": False}, AUTO, "p", "a", "t", "stateless")


if __name__ == "__main__":
    unittest.main()
