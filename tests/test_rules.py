import unittest

from brain.rules import match, to_bytes

SERVICES = {"payment": {"kind": "stateless", "actable": True}, "recommendation": {"kind": "stateless", "actable": True},
            "valkey-cart": {"kind": "stateful", "protected": True}}
POLICY = {"change_window_minutes": 10, "tools": {"raise_limit": {"max_memory": "1Gi"}}}


def incident(culprit, onset=1000.0):
    return {"id": "inc-1", "culprit": culprit, "onset_at": onset}


def change(id_, kind, obj="deployment/payment", ts=960.0, by_agent=False, diff=None):
    return {"id": id_, "kind": kind, "object": obj, "ts": ts, "by_agent": by_agent, "diff": diff or {}}


class RulesTest(unittest.TestCase):
    def test_bad_deploy_rolls_back(self):
        pattern, actions = match(incident("payment"), [change(41, "image")], [], SERVICES, POLICY)
        self.assertEqual(pattern, "recent_change")
        self.assertEqual(actions[0]["tool"], "rollback_deploy")
        self.assertEqual((actions[0]["journal_entry"], actions[0]["evidence_ids"]), (41, ["journal:41"]))

    def test_env_change_reverts_config_and_latest_wins(self):
        journal = [change(40, "image", ts=900), change(42, "env", ts=980), change(43, "restart", ts=990)]
        _, actions = match(incident("payment"), journal, [], SERVICES, POLICY)
        self.assertEqual((actions[0]["tool"], actions[0]["journal_entry"]), ("revert_config", 42))

    def test_change_outside_window_or_after_onset_is_ignored(self):
        journal = [change(1, "image", ts=1000 - 601), change(2, "image", ts=1001)]
        self.assertEqual(match(incident("payment"), journal, [], SERVICES, POLICY), ("unknown", []))

    def test_agent_change_is_not_a_cause(self):
        self.assertEqual(match(incident("payment"), [change(5, "image", by_agent=True)], [], SERVICES, POLICY)[0],
                         "unknown")

    def test_protected_proposes_inverse(self):
        c = change(7, "replicas", obj="deployment/valkey-cart", diff={"replicas": {"old": 1, "new": 0}})
        pattern, actions = match(incident("valkey-cart"), [c], [], SERVICES, POLICY)
        self.assertEqual(pattern, "protected")
        self.assertEqual((actions[0]["tool"], actions[0]["params"]), ("scale", {"replicas": 1}))

    def test_oom_restarts_then_asks_for_more_memory(self):
        events = [{"id": "event:abc", "summary": "container recommendation OOMKilled, exit 137"}]
        pattern, actions = match(incident("recommendation"), [], events, SERVICES, POLICY, memory_limit="256Mi")
        self.assertEqual(pattern, "resource")
        self.assertEqual([a["tool"] for a in actions], ["restart_service", "raise_limit"])
        self.assertEqual(actions[1]["params"], {"memory": "512Mi"})
        self.assertEqual(actions[0]["evidence_ids"], ["event:abc"])

    def test_raise_limit_capped_and_skipped_at_cap(self):
        _, actions = match(incident("recommendation"), [], [], SERVICES, POLICY, memory_ratio=0.95, memory_limit="768Mi")
        self.assertEqual(actions[1]["params"], {"memory": "1024Mi"})
        _, actions = match(incident("recommendation"), [], [], SERVICES, POLICY, memory_ratio=0.95, memory_limit="1Gi")
        self.assertEqual([a["tool"] for a in actions], ["restart_service"])

    def test_no_culprit_or_no_signal_is_unknown(self):
        self.assertEqual(match(incident(None), [], [], SERVICES, POLICY), ("unknown", []))
        self.assertEqual(match(incident("payment"), [], [], SERVICES, POLICY, memory_ratio=0.5), ("unknown", []))

    def test_to_bytes(self):
        self.assertEqual((to_bytes("1Gi"), to_bytes("256Mi"), to_bytes("500M"), to_bytes("1024")),
                         (2**30, 256 * 2**20, 500 * 10**6, 1024))


if __name__ == "__main__":
    unittest.main()
