import copy
import unittest

from observer import journal
from schemas.db import connect


def deploy(image="ghcr.io/open-telemetry/demo:2.0-payment", env=None, replicas=2, annotations=None,
           managers=(("helm", "2026-11-13T00:00:00Z", None),)):
    return {
        "metadata": {"name": "payment", "resourceVersion": "42",
                     "annotations": {"deployment.kubernetes.io/revision": "3"},
                     "managedFields": [{"manager": m, "time": t, "subresource": s} for m, t, s in managers]},
        "spec": {"replicas": replicas, "template": {
            "metadata": {"annotations": annotations or {}},
            "spec": {"containers": [{"name": "payment", "image": image, "env": env or [],
                                     "resources": {"limits": {"memory": "256Mi"}}}]}}},
        "status": {"readyReplicas": replicas},
    }


class JournalTest(unittest.TestCase):
    def test_image_change(self):
        new = deploy(image="payment:v2-bad", managers=(("helm", "2026-11-13T00:00:00Z", None),
                                                       ("chaos-panel", "2026-11-13T00:05:00Z", None)))
        e = journal.entry("deployment", deploy(), new, 1.0, "flagd-config")
        self.assertEqual(e["kind"], "image")
        self.assertEqual(e["object"], "deployment/payment")
        self.assertEqual(e["field_manager"], "chaos-panel")
        self.assertFalse(e["by_agent"])
        self.assertEqual(e["diff"], {"containers[payment].image": {
            "old": "ghcr.io/open-telemetry/demo:2.0-payment", "new": "payment:v2-bad"}})
        self.assertEqual(e["inverse"], [{"op": "patch", "body": {"spec": {"template": {"spec": {"containers": [
            {"name": "payment", "image": "ghcr.io/open-telemetry/demo:2.0-payment"}]}}}}}])

    def test_status_only_change_is_ignored(self):
        new = deploy()
        new["status"]["readyReplicas"] = 0
        new["metadata"]["annotations"]["deployment.kubernetes.io/revision"] = "4"
        self.assertIsNone(journal.entry("deployment", deploy(), new, 1.0, "flagd-config"))

    def test_author_skips_status_writes(self):
        new = deploy(managers=(("oncall-agent", "2026-11-13T00:05:00Z", None),
                               ("k3s", "2026-11-13T00:06:00Z", "status")))
        self.assertEqual(journal.author(new), "oncall-agent")

    def test_env_inverse_restores_and_deletes(self):
        old = deploy(env=[{"name": "ADDR", "value": "payment:8080"}, {"name": "KEEP", "value": "1"}])
        new = deploy(env=[{"name": "ADDR", "value": "wrong:1"}, {"name": "KEEP", "value": "1"},
                          {"name": "NEW", "value": "x"}])
        e = journal.entry("deployment", old, new, 1.0, "flagd-config")
        self.assertEqual(e["kind"], "env")
        env = e["inverse"][0]["body"]["spec"]["template"]["spec"]["containers"][0]["env"]
        self.assertEqual(env, [{"name": "ADDR", "value": "payment:8080"}, {"name": "NEW", "$patch": "delete"}])

    def test_resources_inverse_nulls_added_keys(self):
        old = deploy()
        new = copy.deepcopy(old)
        new["spec"]["template"]["spec"]["containers"][0]["resources"] = {"limits": {"memory": "1Gi", "cpu": "1"}}
        e = journal.entry("deployment", old, new, 1.0, "flagd-config")
        self.assertEqual(e["kind"], "resources")
        res = e["inverse"][0]["body"]["spec"]["template"]["spec"]["containers"][0]["resources"]
        self.assertEqual(res, {"limits": {"memory": "256Mi", "cpu": None}})

    def test_replicas_and_restart(self):
        e = journal.entry("deployment", deploy(), deploy(replicas=0), 1.0, "flagd-config")
        self.assertEqual((e["kind"], e["inverse"]), ("replicas", [{"op": "scale", "replicas": 2}]))
        e = journal.entry("deployment", deploy(),
                          deploy(annotations={journal.RESTART_KEY: "2026-11-13T00:00:00Z"}), 1.0, "flagd-config")
        self.assertEqual(e["kind"], "restart")

    def test_container_set_change_rolls_back_template(self):
        new = deploy()
        new["spec"]["template"]["spec"]["containers"].append({"name": "sidecar", "image": "x"})
        e = journal.entry("deployment", deploy(), new, 1.0, "flagd-config")
        self.assertEqual((e["kind"], e["inverse"]), ("other", [{"op": "rollback", "revision": "3"}]))

    def test_flag_configmap(self):
        def cm(name, data):
            return {"metadata": {"name": name, "resourceVersion": "7", "managedFields": []}, "data": data}
        e = journal.entry("configmap", cm("flagd-config", {"a": "on", "b": "1"}),
                          cm("flagd-config", {"a": "off", "b": "1", "c": "2"}), 1.0, "flagd-config")
        self.assertEqual(e["kind"], "flag")
        self.assertEqual(e["inverse"], [{"op": "patch", "body": {"data": {"a": "on", "c": None}}}])
        e = journal.entry("configmap", cm("other", {"a": "1"}), cm("other", {"a": "2"}), 1.0, "flagd-config")
        self.assertEqual(e["kind"], "configmap")

    def test_insert_and_read(self):
        conn = connect(":memory:")
        e = journal.entry("deployment", deploy(), deploy(image="payment:v2-bad"), 5.0, "flagd-config")
        row_id = journal.insert(conn, e)
        rows = journal.read(conn, since=1.0, obj="deployment/payment")
        self.assertEqual([r["id"] for r in rows], [row_id])
        self.assertEqual(rows[0]["inverse"], e["inverse"])
        self.assertEqual(journal.read(conn, since=6.0), [])


if __name__ == "__main__":
    unittest.main()
