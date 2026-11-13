import asyncio
import copy
import json

import httpx
import pytest

from gateway.dryrun import RESTART_KEY
from test_gateway import World, action


def autonomous_world(tmp_path, kind):
    from observer import journal
    from test_flags import FlagCore, cm, flagd

    w = World(tmp_path)
    w.gw.policy = copy.deepcopy(w.gw.policy)
    w.gw.policy["autonomy"] = {"journal_reverts": ["ad", "email", "recommendation"],
                               "memory_restores": ["ad", "email", "recommendation"]}
    w.apps.dep["metadata"]["name"] = "ad"
    c = w.apps.dep["spec"]["template"]["spec"]["containers"][0]
    c["name"], c["image"] = "ad", "ghcr.io/open-telemetry/demo:3.1.0-ad"
    old = copy.deepcopy(w.apps.dep)
    if kind == "flag":
        w.core = FlagCore(flagd(ad="on"))
        w.gw.core, w.gw.flag_map = w.core, {"adFailure": "ad", "paymentFailure": "payment"}
        e = journal.entry("configmap", cm(flagd()), w.core.cm, 950.0, "flagd-config")
    else:
        if kind == "env":
            c["env"] = [{"name": "MODE", "value": "broken"}]
        elif kind == "memory":
            resources = {"requests": {"memory": "16Mi"}, "limits": {"memory": "256Mi", "cpu": "1"}}
            old["spec"]["template"]["spec"]["containers"][0]["resources"] = copy.deepcopy(resources)
            c["resources"] = copy.deepcopy(resources)
            c["resources"]["limits"]["memory"] = "32Mi"
        else:
            w.apps.dep["spec"]["replicas"] = 1
        e = journal.entry("deployment", old, w.apps.dep, 950.0, "flagd-config")
    w.obs.journal = [{**e, "id": 42, "by_agent": False, "field_manager": "chaos-panel"}]
    w.conn.execute("UPDATE incidents SET culprit='ad', victims_json='[]'")
    status = {"recovered": False, "prometheus_ok": True, "age": 0}

    def observer(request):
        if request.url.path == "/journal":
            return w.obs(request)
        w.now[0] += 5
        return httpx.Response(200, json={"ts": w.now[0] - status["age"],
            "prometheus_ok": status["prometheus_ok"], "severity": 0 if status["recovered"] else 4,
            "services": {"ad": {"unhealthy": not status["recovered"],
                                  "err_ratio": 0.0 if status["recovered"] else 0.4}}})

    w.gw.http = httpx.AsyncClient(transport=httpx.MockTransport(observer))
    w.gw.verify_every = 0
    a = action(tool="scale" if kind == "replicas" else "revert_config", target="ad", journal_entry=42,
               evidence_ids=["journal:42"], params={"replicas": 2} if kind == "replicas" else {},
               prediction={"metric": "err_ratio", "target": "ad", "below": 0.05, "within_s": 90})
    if kind == "memory":
        from brain import runbooks
        w.gw.books = runbooks.load()
        a.update(tool="raise_limit", params={"memory": "256Mi", "container": "ad"})
    return w, a, status


@pytest.mark.parametrize("kind", ["flag", "env", "replicas", "memory"])
@pytest.mark.parametrize("origin", ["rule", "model"])
async def test_autonomous_journal_revert_verifies_and_reports_without_approval(tmp_path, kind, origin):
    from notifier.consumer import NotificationConsumer
    from notifier.state import NotifierState

    w, a, status = autonomous_world(tmp_path, kind)
    d = await w.gw.submit({**a, "origin": origin})
    assert d.decision == "executed"
    assert "approval_requested" not in w.types()
    status["recovered"] = True
    assert await asyncio.wait_for(next(iter(w.gw.tasks)), 5) == "success"
    receipt = w.gw.receipts.get(d.receipt_id)
    assert receipt.trust["autonomy_policy"] == f"journal_revert:{kind}"
    assert receipt.harm_clean and receipt.prediction_held
    assert "automatic; policy journal_revert:" in w.events[-1]["payload"]["card"]["text"]

    class ReportOnly:
        reports = []

        async def fyi(self, card, url, details=None):
            self.reports.append((card, url))

    notifier = ReportOnly()
    consumer = NotificationConsumer(w.gw.http, "http://gw", notifier, NotifierState(tmp_path / "notify.db"))
    await consumer.handle({"seq": 1, "event": w.events[-1]})
    assert len(notifier.reports) == 1 and notifier.reports[0][1] == f"http://gw/receipts/{d.receipt_id}"
    assert not consumer.state.get("wakes", {})


@pytest.mark.parametrize("blocker", ["disabled", "critical", "runbook", "failure", "stale", "wrong_count",
                                    "mixed_flags", "no_prediction", "wrong_prediction", "older_change",
                                    "protected", "budget", "human_change", "no_inverse", "in_flight", "major"])
async def test_autonomous_reverts_keep_approval_for_unsafe_cases(tmp_path, blocker):
    from gateway import trust
    from test_flags import flagd

    kind = "replicas" if blocker == "wrong_count" else "flag"
    w, a, status = autonomous_world(tmp_path, kind)
    if blocker == "disabled":
        w.gw.policy.pop("autonomy")
    elif blocker == "critical":
        w.gw.services = {**w.gw.services, "ad": {**w.gw.services["ad"], "critical": True}}
    elif blocker == "runbook":
        w.gw.books = [{"id": "ASK", "title": "Ask", "steps": ["Ask"], "require_approval": True}]
    elif blocker == "failure":
        trust.record(w.conn, "recent_change", "revert_config", "ad", "real", False, 999)
    elif blocker == "stale":
        status["age"] = 60
    elif blocker == "wrong_count":
        a["params"] = {"replicas": 3}
    elif blocker == "mixed_flags":
        from observer import journal
        from test_flags import cm
        w.core.cm = cm(flagd(payment="50%", ad="on"))
        e = journal.entry("configmap", cm(flagd()), w.core.cm, 950.0, "flagd-config")
        w.obs.journal = [{**e, "id": 42}]
    elif blocker == "no_prediction":
        a["prediction"] = None
    elif blocker == "wrong_prediction":
        a["prediction"]["target"] = "payment"
    elif blocker == "older_change":
        newer = {**copy.deepcopy(w.obs.journal[0]), "id": 43, "ts": 955}
        w.obs.journal.append(newer)
        a["origin"] = "model"
    elif blocker == "protected":
        w.gw.services = {**w.gw.services, "ad": {**w.gw.services["ad"], "protected": True}}
    elif blocker == "budget":
        w.gw.policy["budgets"]["max_actions_per_incident"] = 0
    elif blocker == "human_change":
        w.obs.journal.append({**w.obs.journal[0], "id": 43, "ts": 1001, "field_manager": "kubectl"})
    elif blocker == "no_inverse":
        w.obs.journal[0]["inverse"] = []
    elif blocker == "in_flight":
        a["origin"] = "model"
        w.conn.execute("INSERT INTO receipts (incident_id, ts, outcome) VALUES ('another', 1000, 'pending')")
    elif blocker == "major":
        w.conn.execute("UPDATE incidents SET major=1")
    d = await w.gw.submit(a)
    assert d.decision == ({"protected": "escalated", "budget": "escalated", "human_change": "handed_off",
                           "no_inverse": "refused", "in_flight": "refused"}.get(blocker, "awaiting_approval"))
    assert w.conn.execute("SELECT COUNT(*) FROM receipts").fetchone()[0] == (1 if blocker == "in_flight" else 0)


async def test_autonomous_model_failure_undoes_and_suspends_next_attempt(tmp_path):
    from gateway import trust

    w, a, _ = autonomous_world(tmp_path, "flag")
    d = await w.gw.submit({**a, "origin": "model"})
    assert d.decision == "executed"
    assert await asyncio.wait_for(next(iter(w.gw.tasks)), 5) == "undone"
    assert json.loads(w.core.cm["data"]["demo.flagd.json"])["flags"]["adFailure"]["defaultVariant"] == "on"
    assert trust.counts(w.conn, "recent_change", "revert_config", "ad")["real"] == (0, 1)
    assert w.types()[-1] == "escalated"
    w.conn.execute("UPDATE incidents SET state='open'")
    assert (await w.gw.submit(a)).decision == "awaiting_approval"


@pytest.mark.parametrize("blocker", ["general_increase", "critical", "mixed_resources", "disabled", "runbook"])
async def test_memory_restore_exception_never_authorizes_general_capacity_changes(tmp_path, blocker):
    w, a, _ = autonomous_world(tmp_path, "memory")
    if blocker == "general_increase":
        a["params"]["memory"] = "384Mi"
    elif blocker == "critical":
        w.gw.services = {**w.gw.services, "ad": {**w.gw.services["ad"], "critical": True}}
    elif blocker == "mixed_resources":
        w.obs.journal[0]["diff"]["containers[ad].resources"]["old"]["limits"]["cpu"] = "2"
    elif blocker == "disabled":
        w.gw.policy["autonomy"].pop("memory_restores")
    elif blocker == "runbook":
        w.gw.books.append({"id": "ASK", "require_approval": True, "steps": ["Ask"], "match": {}})
    assert (await w.gw.submit(a)).decision == "awaiting_approval"
    assert w.conn.execute("SELECT COUNT(*) FROM receipts").fetchone()[0] == 0


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
