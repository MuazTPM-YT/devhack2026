import unittest

from brain.culprit import find_culprit

ERR = [{"key": "error", "type": "bool", "value": True}]


def trace(spans):
    # spans: (span_id, parent_id, service, error)
    services = sorted({s[2] for s in spans})
    pid = {svc: f"p{i}" for i, svc in enumerate(services)}
    return {"processes": {pid[svc]: {"serviceName": svc} for svc in services},
            "spans": [{"spanID": sid, "processID": pid[svc], "tags": ERR if err else [],
                       "references": [{"refType": "CHILD_OF", "spanID": parent}] if parent else []}
                      for sid, parent, svc, err in spans]}


class CulpritTest(unittest.TestCase):
    def test_leaf_error_is_culprit(self):
        t = trace([("a", None, "frontend", True), ("b", "a", "checkout", True),
                   ("c", "b", "payment", True), ("d", "b", "cart", False)])
        self.assertEqual(find_culprit([t, t], [], [], {}), ("payment", ["checkout", "frontend"]))

    def test_otel_status_tag_counts_as_error(self):
        t = trace([("a", None, "frontend", False), ("b", "a", "ad", False)])
        t["spans"][1]["tags"] = [{"key": "otel.status_code", "value": "ERROR"}]
        self.assertEqual(find_culprit([t], [], [], {}), ("ad", []))

    def test_majority_origin_wins(self):
        pay = trace([("a", None, "checkout", True), ("b", "a", "payment", True)])
        email = trace([("a", None, "checkout", True), ("b", "a", "email", True)])
        self.assertEqual(find_culprit([pay, pay, email], [], [], {})[0], "payment")

    def test_no_traces_falls_back_to_deepest(self):
        edges = [("frontend", "checkout", 5.0), ("checkout", "cart", 5.0), ("cart", "valkey-cart", 5.0)]
        got = find_culprit([], ["frontend", "cart", "valkey-cart"], edges, {})
        self.assertEqual(got, ("valkey-cart", ["cart", "frontend"]))

    def test_fallback_tie_breaks_on_onset(self):
        edges = [("checkout", "payment", 1.0), ("checkout", "email", 1.0)]
        got = find_culprit([], ["payment", "email"], edges, {"payment": 20.0, "email": 10.0})
        self.assertEqual(got[0], "email")

    def test_fallback_survives_cycle(self):
        edges = [("a", "b", 1.0), ("b", "a", 1.0)]
        self.assertIn(find_culprit([], ["a", "b"], edges, {})[0], ("a", "b"))

    def test_nothing_unhealthy(self):
        self.assertEqual(find_culprit([], [], [], {}), (None, []))


if __name__ == "__main__":
    unittest.main()
