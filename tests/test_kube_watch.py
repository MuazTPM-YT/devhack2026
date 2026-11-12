import threading
from datetime import datetime, timezone

from observer import journal
from observer.kube_watch import Tracker, bad_pods, pod_bad, run_watch, service_of
from schemas.db import connect

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc).timestamp()


def iso(seconds_ago):
    return datetime.fromtimestamp(NOW - seconds_ago, timezone.utc).isoformat().replace("+00:00", "Z")


def pod(name="payment-7d9f-abc", rs="payment-7d9f", containers=None, ready=True, ready_since=600, deleting=False):
    meta = {"name": name, "ownerReferences": [{"kind": "ReplicaSet", "name": rs}]}
    if deleting:
        meta["deletionTimestamp"] = iso(1)
    return {"metadata": meta, "status": {
        "containerStatuses": containers or [{"name": "app", "state": {"running": {}}}],
        "conditions": [{"type": "Ready", "status": "True" if ready else "False",
                        "lastTransitionTime": iso(ready_since)}]}}


def test_service_from_replicaset_owner():
    assert service_of(pod(rs="valkey-cart-5c8b")) == "valkey-cart"
    assert service_of({"metadata": {"name": "job-x", "ownerReferences": [{"kind": "Job", "name": "j"}]}}) is None


def test_bad_pod_rules():
    assert not pod_bad(pod(), NOW)
    assert pod_bad(pod(containers=[{"state": {"waiting": {"reason": "CrashLoopBackOff"}}}]), NOW)
    oom = {"state": {"running": {}}, "lastState": {"terminated": {"reason": "OOMKilled", "finishedAt": iso(60)}}}
    assert pod_bad(pod(containers=[oom]), NOW)
    oom["lastState"]["terminated"]["finishedAt"] = iso(121)
    assert not pod_bad(pod(containers=[oom]), NOW)
    assert not pod_bad(pod(ready=False, ready_since=29), NOW)
    assert pod_bad(pod(ready=False, ready_since=30), NOW)
    assert not pod_bad(pod(ready=False, ready_since=300, deleting=True), NOW)


def test_bad_pods_counts_per_service():
    crash = [{"state": {"waiting": {"reason": "CrashLoopBackOff"}}}]
    pods = [pod("payment-1-a", "payment-1", crash), pod("payment-1-b", "payment-1", crash), pod("cart-2-a", "cart-2")]
    assert bad_pods(pods, NOW) == {"payment": 2}


def deployment(image, rv):
    return {"metadata": {"name": "payment", "resourceVersion": rv,
                         "managedFields": [{"manager": "chaos-panel", "time": iso(5)}]},
            "spec": {"replicas": 2, "template": {"spec": {"containers": [{"name": "payment", "image": image}]}}}}


def test_tracker_journals_changes_including_after_relist():
    conn = connect(":memory:")
    t = Tracker(conn, "flagd-config", clock=lambda: NOW)
    assert t.handle("deployment", "ADDED", deployment("ghcr.io/open-telemetry/demo:3.1.0-payment", "1")) is None
    assert t.handle("deployment", "ADDED", deployment("ghcr.io/open-telemetry/demo:3.1.0-payment", "1")) is None
    e = t.handle("deployment", "MODIFIED", deployment("payment:v2-bad", "2"))
    assert (e["kind"], e["field_manager"], e["ts"]) == ("image", "chaos-panel", NOW)
    # relist after a watch gap: same object comes back as ADDED with a newer version
    e2 = t.handle("deployment", "ADDED", deployment("ghcr.io/open-telemetry/demo:3.1.0-payment", "3"))
    assert e2["diff"]["containers[payment].image"]["new"] == "ghcr.io/open-telemetry/demo:3.1.0-payment"
    assert [r["id"] for r in journal.read(conn)] == [e["id"], e2["id"]]


def test_tracker_pods_feed_bad_pods():
    t = Tracker(connect(":memory:"), "flagd-config")
    crash = [{"state": {"waiting": {"reason": "CrashLoopBackOff"}}}]
    t.handle("pod", "ADDED", pod(containers=crash))
    assert t.bad_pods(NOW) == {"payment": 1}
    t.handle("pod", "DELETED", pod())
    assert t.bad_pods(NOW) == {}


class FakeResp:
    def __init__(self, data):
        self.data = data


def test_run_watch_relists_after_error(monkeypatch):
    stop = threading.Event()
    calls = []

    def list_fn(namespace, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise ConnectionError("blip")
        stop.set()
        return FakeResp(b'{"metadata": {"resourceVersion": "9"}, "items": [{"metadata": {"name": "p-1-a"}}]}')

    class FakeWatch:
        def stream(self, fn, namespace, **kwargs):
            assert kwargs["resource_version"] == "9"
            yield {"type": "DELETED", "raw_object": {"metadata": {"name": "p-1-a"}}}

        def stop(self):
            pass

    import kubernetes.watch
    monkeypatch.setattr(kubernetes.watch, "Watch", FakeWatch)
    t = Tracker(connect(":memory:"), "flagd-config")
    run_watch(list_fn, "pod", t, "shop", stop, sleep=lambda s: None)
    assert len(calls) == 2 and t.pods == {}
