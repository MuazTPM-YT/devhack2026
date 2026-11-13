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
        healthy = {"services": {"payment": {"unhealthy": False, "err_ratio": 0.0}}}
        self.assertEqual(check(healthy, "payment", RULE, RULE, None, None)[0], "refused")

    # live smoke inc-1794562461681: metrics stopped arriving, payment read None, and the bad image
    # stayed live while the incident closed as "problem no longer present"
    def test_no_readings_anywhere_asks_a_human(self):
        blind = {"err_ratio": None, "p95_ms": None, "bad_pods": 0, "unhealthy": False}
        health = {"services": {"payment": blind, "checkout": dict(blind)}}
        outcome, reason = check(health, "payment", RULE, RULE, None, None, ["checkout"])
        self.assertEqual(outcome, "awaiting_approval")
        self.assertIn("no health readings", reason)
        self.assertEqual(check({"services": {}}, "payment", RULE, RULE, None, None)[0], "awaiting_approval")

    # valkey-cart scaled to 0 has no spans and no pods: only its sick caller shows the problem
    def test_unmeasured_culprit_judged_by_its_victims(self):
        store = {"err_ratio": None, "p95_ms": None, "bad_pods": 0, "unhealthy": False}
        cart = {"services": {"valkey-cart": store, "cart": {"unhealthy": True, "err_ratio": 1.0}}}
        self.assertEqual(check(cart, "valkey-cart", RULE, RULE, None, None, ["cart"])[0], "ok")
        cart["services"]["cart"]["unhealthy"] = False
        self.assertEqual(check(cart, "valkey-cart", RULE, RULE, None, None, ["cart"])[0], "refused")
        measured = {"services": {"payment": {"unhealthy": False, "err_ratio": 0.0}, "cart": {"unhealthy": True}}}
        self.assertEqual(check(measured, "payment", RULE, RULE, None, None, ["cart"])[0], "refused")

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


# chaos lab decoy: a later, unrelated env var on the same Deployment must not make the older env change
# look gone; live it would turn an approved revert into an escalation
def test_env_entry_stays_live_when_another_var_is_added_later():
    from tests.test_journal import deploy
    good = [{"name": "PAYMENT_ADDR", "value": "payment:8080"}]
    broken = [{"name": "PAYMENT_ADDR", "value": "payment:9999"}]
    e = journal.entry("deployment", deploy(env=good), deploy(env=broken), 100.0, "flagd-config")
    later = deploy(env=broken + [{"name": "PROMO_BANNER", "value": "autumn"}])
    assert journal.still_live(e, later)
    assert not journal.still_live(e, deploy(env=good + [{"name": "PROMO_BANNER", "value": "autumn"}]))
    # a var the entry added, since removed: gone
    added = journal.entry("deployment", deploy(env=good), deploy(env=good + [{"name": "X", "value": "1"}]), 100.0,
                          "flagd-config")
    assert journal.still_live(added, deploy(env=good + [{"name": "X", "value": "1"}, {"name": "Y", "value": "2"}]))
    assert not journal.still_live(added, deploy(env=good))
    # a var the entry removed, since put back: gone
    removed = journal.entry("deployment", deploy(env=good + [{"name": "X", "value": "1"}]), deploy(env=good), 100.0,
                            "flagd-config")
    assert journal.still_live(removed, deploy(env=good)) and not journal.still_live(
        removed, deploy(env=good + [{"name": "X", "value": "1"}]))
