import pytest

from gateway.dryrun import RESTART_KEY
from test_gateway import World, action


async def run_tool(tmp_path, **over):
    w = World(tmp_path)
    w.gw.verify_every = 3600  # keep the verifier parked; these tests stop at execute
    d = await w.gw.submit(action(**over))
    if d.decision == "awaiting_approval":
        d = await w.gw.decide(d.approval_id, "approved", "u1")
    for t in w.gw.tasks:
        t.cancel()
    return w, d


def container(w):
    return w.apps.dep["spec"]["template"]["spec"]["containers"][0]


async def test_restart_sets_restarted_at_only(tmp_path):
    w, d = await run_tool(tmp_path, tool="restart_service", pattern="resource", journal_entry=None,
                          evidence_ids=["event:x"])
    assert d.decision == "executed"
    assert RESTART_KEY in w.apps.dep["spec"]["template"]["metadata"]["annotations"]
    real = w.apps.patches[-1]
    assert real["content_type"] == "application/strategic-merge-patch+json" and real["dry_run"] is None


async def test_scale_uses_subresource_and_bounds(tmp_path):
    w, d = await run_tool(tmp_path, tool="scale", pattern="resource", journal_entry=None, params={"replicas": 3})
    assert d.decision == "executed" and w.apps.dep["spec"]["replicas"] == 3
    assert w.apps.patches[-1]["scale"] and w.apps.patches[-1]["content_type"] == "application/merge-patch+json"
    row = w.conn.execute("SELECT inverse_json FROM receipts").fetchone()[0]
    assert '"replicas": 2' in row
    w2, d2 = await run_tool(tmp_path / "b", tool="scale", pattern="resource", journal_entry=None,
                            params={"replicas": 5})
    assert (d2.decision, d2.failed_step) == ("refused", "policy") and w2.apps.patches == []


async def test_raise_limit_bounded_and_must_raise(tmp_path):
    w = World(tmp_path)
    container(w)["resources"] = {"limits": {"memory": "256Mi"}}
    w.gw.verify_every = 3600
    d = await w.gw.submit(action(tool="raise_limit", pattern="resource", journal_entry=None,
                                 params={"memory": "512Mi"}))
    d = await w.gw.decide(d.approval_id, "approved", "u1")
    assert d.decision == "executed" and container(w)["resources"]["limits"]["memory"] == "512Mi"
    for over, step in (({"memory": "2Gi"}, "policy"), ({"memory": "128Mi"}, "dry_run")):
        w2 = World(tmp_path / step)
        container(w2)["resources"] = {"limits": {"memory": "256Mi"}}
        d2 = await w2.gw.submit(action(tool="raise_limit", pattern="resource", journal_entry=None, params=over))
        assert (d2.decision, d2.failed_step) == ("refused", step)


async def test_revert_env_from_journal_inverse(tmp_path):
    w = World(tmp_path)
    w.gw.verify_every = 3600
    container(w)["env"] = [{"name": "PAYMENT_ADDR", "value": "wrong:1"}, {"name": "NEW", "value": "x"}]
    inverse_body = {"spec": {"template": {"spec": {"containers": [
        {"name": "payment", "env": [{"name": "PAYMENT_ADDR", "value": "payment:8080"},
                                    {"name": "NEW", "$patch": "delete"}]}]}}}}
    w.obs.journal = [{"id": 7, "object": "deployment/payment", "kind": "env", "ts": 950.0,
                      "field_manager": "chaos-panel", "by_agent": False,
                      "diff": {"containers[payment].env": {
                          "old": [{"name": "PAYMENT_ADDR", "value": "payment:8080"}],
                          "new": [{"name": "PAYMENT_ADDR", "value": "wrong:1"}, {"name": "NEW", "value": "x"}]}},
                      "inverse": [{"op": "patch", "body": inverse_body}]}]
    d = await w.gw.submit(action(tool="revert_config", journal_entry=7, evidence_ids=["journal:7"]))
    d = await w.gw.decide(d.approval_id, "approved", "u1")
    assert d.decision == "executed"
    assert container(w)["env"] == [{"name": "PAYMENT_ADDR", "value": "payment:8080"}]
    assert w.apps.patches[-1]["patch"]["metadata"]["resourceVersion"] == "100"


async def test_revert_without_env_entry_is_refused(tmp_path):
    w, d = await run_tool(tmp_path, tool="revert_config")  # entry 41 is an image change
    assert (d.decision, d.failed_step) == ("refused", "dry_run") and "env journal entry" in d.reason


@pytest.mark.parametrize("tool", ["enable_degraded_mode"])
async def test_flag_tools_not_built_yet(tmp_path, tool):
    w, d = await run_tool(tmp_path, tool=tool, target="recommendation", pattern="resource", journal_entry=None)
    assert (d.decision, d.failed_step) == ("refused", "dry_run")


async def test_undo_of_scale_scales_back(tmp_path):
    w, d = await run_tool(tmp_path, tool="scale", pattern="resource", journal_entry=None, params={"replicas": 3})
    import json
    inverse = json.loads(w.conn.execute("SELECT inverse_json FROM receipts").fetchone()[0])
    w.gw.undo("payment", inverse, pause=True)
    assert w.apps.dep["spec"]["replicas"] == 2
