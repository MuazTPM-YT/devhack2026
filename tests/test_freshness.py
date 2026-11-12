import unittest

from gateway.freshness import check
from observer import journal
from test_journal import deploy

SICK = {"services": {"payment": {"unhealthy": True}}}
RULE = ("recent_change", 41)


def bad_deploy_entry():
    e = journal.entry("deployment", deploy(), deploy(image="payment:v2-bad"), 1.0, "flagd-config")
    return {**e, "id": 41}


class FreshnessTest(unittest.TestCase):
    def test_ok_when_still_sick_and_change_still_live(self):
        self.assertEqual(check(SICK, "payment", RULE, RULE, bad_deploy_entry(), deploy(image="payment:v2-bad")),
                         ("ok", None))

    def test_refuse_when_problem_gone(self):
        healthy = {"services": {"payment": {"unhealthy": False}}}
        self.assertEqual(check(healthy, "payment", RULE, RULE, None, None)[0], "refused")
        self.assertEqual(check({"services": {}}, "payment", RULE, RULE, None, None)[0], "refused")

    def test_rule_changed_goes_to_approval(self):
        self.assertEqual(check(SICK, "payment", RULE, ("recent_change", 42), None, None)[0], "awaiting_approval")

    def test_someone_already_reverted_goes_to_approval(self):
        outcome, reason = check(SICK, "payment", RULE, RULE, bad_deploy_entry(), deploy())
        self.assertEqual(outcome, "awaiting_approval")
        self.assertIn("41", reason)

    def test_still_live_reads_every_path_kind(self):
        old = deploy(env=[{"name": "A", "value": "1"}])
        new = deploy(image="payment:v2", env=[{"name": "A", "value": "2"}], replicas=3,
                     annotations={journal.RESTART_KEY: "now"})
        new["spec"]["template"]["spec"]["containers"][0]["resources"] = {"limits": {"memory": "1Gi"}}
        e = journal.entry("deployment", old, new, 1.0, "flagd-config")
        self.assertEqual(len(e["diff"]), 5)
        self.assertTrue(journal.still_live(e, new))
        self.assertFalse(journal.still_live(e, old))


if __name__ == "__main__":
    unittest.main()
