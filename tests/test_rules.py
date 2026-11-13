import copy
import unittest

import pytest

from brain.rules import candidates, match, to_bytes

SERVICES = {"payment": {"kind": "stateless", "actable": True}, "recommendation": {"kind": "stateless", "actable": True},
            "valkey-cart": {"kind": "stateful", "protected": True}}
POLICY = {"change_window_minutes": 10, "tools": {"raise_limit": {"max_memory": "1Gi"}}}


def incident(culprit, onset=1000.0):
    return {"id": "inc-1", "culprit": culprit, "onset_at": onset}


def change(id_, kind, obj="deployment/payment", ts=960.0, by_agent=False, diff=None):
    return {"id": id_, "kind": kind, "object": obj, "ts": ts, "by_agent": by_agent, "diff": diff or {}}


class RulesTest(unittest.TestCase):
    # live: OOMKilled fraud-detection (watched, never acted on) got a restart proposal the gateway refused
    def test_watch_only_service_keeps_pattern_but_gets_no_action(self):
        services = {**SERVICES, "fraud-detection": {"kind": "stateless"}}
        oom = [{"id": "event:fd:last", "summary": "container app last ended OOMKilled, exit 137"}]
        pattern, actions = match(incident("fraud-detection"), [], oom, services, POLICY, 0.95, "300Mi")
        self.assertEqual((pattern, actions), ("resource", []))

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

    # the rule's own pick is always c1; the rest is what else the evidence supports
    def test_candidates_start_with_the_rule_pick_then_older_changes(self):
        journal = [change(40, "image", ts=900), change(42, "env", ts=980), change(43, "restart", ts=990)]
        pattern, cands = candidates(incident("payment"), journal, [], SERVICES, POLICY)
        _, actions = match(incident("payment"), journal, [], SERVICES, POLICY)
        self.assertEqual(pattern, "recent_change")
        self.assertEqual(cands[0]["action"], actions[0])
        self.assertEqual([(c["id"], c["action"]["tool"], c["action"]["journal_entry"]) for c in cands],
                         [("c1", "revert_config", 42), ("c2", "rollback_deploy", 40)])
        self.assertEqual(cands[0]["basis"], "newest change, env on deployment/payment 20 s before errors began")
        self.assertTrue(cands[1]["basis"].startswith("older change, image"))

    # chaos lab decoy: a harmless env change lands after the real flag change, so the rule points at the decoy
    def test_decoy_is_first_but_the_real_cause_is_on_the_list(self):
        flags = {"paymentFailure": "payment"}
        journal = [change(50, "flag", obj="configmap/flagd-config", ts=940,
                          diff={"flags[paymentFailure].defaultVariant": {"old": "off", "new": "50%"}}),
                   change(51, "env", ts=955)]
        _, cands = candidates(incident("payment"), journal, [], SERVICES, POLICY, flag_map=flags)
        self.assertEqual([(c["action"]["tool"], c["action"]["journal_entry"]) for c in cands],
                         [("revert_config", 51), ("revert_config", 50)])

    def test_resource_fixes_follow_a_recent_change_instead_of_being_dropped(self):
        events = [{"id": "event:abc", "summary": "container recommendation OOMKilled, exit 137"}]
        journal = [change(60, "flag", obj="configmap/flagd-config", ts=950,
                          diff={"flags[recommendationCacheFailure].defaultVariant": {"old": "off", "new": "on"}})]
        pattern, cands = candidates(incident("recommendation"), journal, events, SERVICES, POLICY, memory_limit="256Mi",
                                    flag_map={"recommendationCacheFailure": "recommendation"})
        self.assertEqual(pattern, "recent_change")
        self.assertEqual([c["action"]["tool"] for c in cands], ["revert_config", "restart_service", "raise_limit"])
        self.assertEqual([c["action"]["pattern"] for c in cands], ["recent_change", "resource", "resource"])

    def test_candidates_never_widen_what_may_be_touched(self):
        services = {**SERVICES, "fraud-detection": {"kind": "stateless"}}
        self.assertEqual(candidates(incident("fraud-detection"), [change(1, "image", obj="deployment/fraud-detection")],
                                    [], services, POLICY)[1], [])
        store = [change(7, "replicas", obj="deployment/valkey-cart", diff={"replicas": {"old": 1, "new": 0}}),
                 change(6, "image", obj="deployment/valkey-cart", ts=900)]
        _, cands = candidates(incident("valkey-cart"), store, [], SERVICES, POLICY)
        self.assertEqual([c["action"]["tool"] for c in cands], ["scale"])
        self.assertEqual(candidates(incident(None), [], [], SERVICES, POLICY), ("unknown", []))
        agent_only = [change(5, "image", by_agent=True)]
        self.assertEqual(candidates(incident("payment"), agent_only, [], SERVICES, POLICY), ("unknown", []))

    def test_candidates_are_capped(self):
        journal = [change(i, "env", ts=900 + i) for i in range(1, 8)]
        self.assertEqual(len(candidates(incident("payment"), journal, [], SERVICES, POLICY)[1]), 4)

    def test_to_bytes(self):
        self.assertEqual((to_bytes("1Gi"), to_bytes("256Mi"), to_bytes("500M"), to_bytes("1024")),
                         (2**30, 256 * 2**20, 500 * 10**6, 1024))


if __name__ == "__main__":
    unittest.main()


def test_capabilities_list_only_tools_the_gateway_can_build():
    from brain.capabilities import available
    from gateway.mcp_server import TOOLS
    from schemas import config
    caps = available(config.load("policy"), config.load("services")["services"])
    names = [c["tool"] for c in caps]
    assert names == ["rollback_deploy", "revert_config", "restart_service", "scale", "raise_limit"]
    assert set(names) < set(TOOLS) and "enable_degraded_mode" not in names
    by = {c["tool"]: c for c in caps}
    assert "valkey-cart" in by["scale"]["targets"] and "valkey-cart" not in by["restart_service"]["targets"]
    assert "accounting" not in by["scale"]["targets"]
    assert by["raise_limit"]["approval"] == "always asks a human" and "approval" not in by["revert_config"]
    assert by["scale"]["limits"] == {"min": 1, "max": 3}


def test_lowered_memory_limit_proposes_exact_restore_instead_of_whole_rollback():
    old = {"requests": {"memory": "16Mi"}, "limits": {"memory": "200Mi", "cpu": "1"}}
    new = copy.deepcopy(old)
    new["limits"]["memory"] = "32Mi"
    entry = change(41, "resources", obj="deployment/recommendation",
                   diff={"containers[recommendation].resources": {"old": old, "new": new}})
    pattern, found = candidates(incident("recommendation"), [entry], [], SERVICES, POLICY)
    assert pattern == "recent_change"
    assert found[0]["action"]["tool"] == "raise_limit"
    assert found[0]["action"]["params"] == {"memory": "200Mi", "container": "recommendation"}
    assert found[0]["action"]["journal_entry"] == 41


@pytest.mark.parametrize("old,new", [("2Gi", "32Mi"), ("32Mi", "200Mi"), ("bad", "32Mi")])
def test_other_resource_changes_keep_rollback(old, new):
    entry = change(41, "resources", diff={"containers[payment].resources": {
        "old": {"limits": {"memory": old}}, "new": {"limits": {"memory": new}}}})
    assert match(incident("payment"), [entry], [], SERVICES, POLICY)[1][0]["tool"] == "rollback_deploy"
