import copy
import json

import pytest
from fastapi.testclient import TestClient

from chaos import ground_truth
from chaos.faults import BAD_PAYMENT_IMAGE, KubectlError, bad_deploy
from chaos.main import create_app
from chaos.reset import TARGETS, diff_ops, ensure_snapshot, reset

GOOD_IMAGE = "ghcr.io/open-telemetry/demo:3.1.0-payment"


def deployment(name, image=None, replicas=1, env=None):
    return {"metadata": {"name": name}, "spec": {"replicas": replicas, "template": {"spec": {
        "containers": [{"name": name, "image": image or f"demo:{name}",
                        "env": env if env is not None else [{"name": "PORT", "value": "8080"}]}]}}}}


# in-memory cluster that applies the patch types chaos sends and logs every call
class FakeKubectl:
    def __init__(self):
        self.deployments = {name: deployment(name) for name in TARGETS}
        self.deployments["payment"] = deployment("payment", GOOD_IMAGE, replicas=2)
        self.deployments["jaeger"] = deployment("jaeger")
        self.calls = []
        self.fail_on = None

    def __call__(self, *args):
        self.calls.append(args)
        if args[0] == self.fail_on:
            raise KubectlError(f"kubectl {args[0]} {args[1]}: forbidden")
        if args[:2] == ("get", "deployments"):
            return json.dumps({"items": list(self.deployments.values())})
        if args[:2] == ("patch", "deployment"):
            target = self.deployments[args[2]]
            patch = json.loads(args[args.index("-p") + 1])
            if "--type=json" in args:
                for op in patch:
                    assert op["op"] == "add"
                    *parents, leaf = op["path"].strip("/").split("/")
                    node = target
                    for key in parents:
                        node = node[int(key)] if isinstance(node, list) else node[key]
                    node[leaf] = op["value"]
            else:
                for change in patch["spec"]["template"]["spec"]["containers"]:
                    for container in target["spec"]["template"]["spec"]["containers"]:
                        if container["name"] == change["name"]:
                            container.update(change)
            return ""
        if args[:2] == ("rollout", "status"):
            return ""
        raise AssertionError(f"unexpected kubectl call {args}")

    def image(self, name):
        return self.deployments[name]["spec"]["template"]["spec"]["containers"][0]["image"]


def test_record_appends_lines_with_ts_type_target(tmp_path):
    path = tmp_path / "data" / "ground_truth.jsonl"
    first = ground_truth.record(path, "bad_deploy", "payment")
    second = ground_truth.record(path, "reset", restored=["payment"])
    assert set(first) == {"ts", "type", "target"}
    assert "target" not in second and second["restored"] == ["payment"]
    assert ground_truth.read_all(path) == [first, second]
    assert first["ts"] <= second["ts"]


def test_read_all_missing_file_is_empty(tmp_path):
    assert ground_truth.read_all(tmp_path / "nope.jsonl") == []


def test_bad_deploy_patches_payment_image_as_chaos_panel():
    fake = FakeKubectl()
    assert bad_deploy(fake) == {"type": "bad_deploy", "target": "payment"}
    assert fake.image("payment") == BAD_PAYMENT_IMAGE
    assert "--field-manager=chaos-panel" in fake.calls[-1]


def test_diff_ops_empty_when_healthy():
    state = {"replicas": 2, "containers": [{"name": "a", "image": "x", "env": []}]}
    assert diff_ops(state, copy.deepcopy(state)) == []


def test_diff_ops_restores_replicas_image_and_drops_added_env():
    healthy = {"replicas": 2, "containers": [
        {"name": "side", "image": "s", "env": []},
        {"name": "a", "image": "x", "env": [{"name": "K", "value": "1"}]}]}
    current = {"replicas": 0, "containers": [
        {"name": "a", "image": "bad", "env": [{"name": "K", "value": "1"}, {"name": "X", "value": "2"}]},
        {"name": "side", "image": "s", "env": []}]}
    assert diff_ops(healthy, current) == [
        {"op": "add", "path": "/spec/replicas", "value": 2},
        {"op": "add", "path": "/spec/template/spec/containers/0/image", "value": "x"},
        {"op": "add", "path": "/spec/template/spec/containers/0/env",
         "value": [{"name": "K", "value": "1"}]},
    ]


def test_diff_ops_refuses_when_container_is_gone():
    healthy = {"replicas": 1, "containers": [{"name": "a", "image": "x", "env": []}]}
    with pytest.raises(RuntimeError, match="container a gone"):
        diff_ops(healthy, {"replicas": 1, "containers": []})


def test_snapshot_written_once_and_never_overwritten(tmp_path):
    path = tmp_path / "healthy_snapshot.json"
    fake = FakeKubectl()
    snapshot = ensure_snapshot(path, fake)
    assert set(snapshot) == set(TARGETS)
    assert snapshot["payment"]["replicas"] == 2
    bad_deploy(fake)
    assert ensure_snapshot(path, fake)["payment"]["containers"][0]["image"] == GOOD_IMAGE


def test_snapshot_refuses_when_target_missing(tmp_path):
    fake = FakeKubectl()
    del fake.deployments["kafka"]
    with pytest.raises(RuntimeError, match="kafka"):
        ensure_snapshot(tmp_path / "s.json", fake)
    assert not (tmp_path / "s.json").exists()


def test_reset_patches_only_changed_and_waits_for_rollout(tmp_path):
    fake = FakeKubectl()
    snapshot = ensure_snapshot(tmp_path / "s.json", fake)
    assert reset(snapshot, fake) == []
    bad_deploy(fake)
    fake.calls.clear()
    assert reset(snapshot, fake) == ["payment"]
    assert fake.image("payment") == GOOD_IMAGE
    patches = [c for c in fake.calls if c[0] == "patch"]
    assert len(patches) == 1 and "--field-manager=chaos-panel" in patches[0]
    assert fake.calls[-1] == ("rollout", "status", "deployment/payment", "--timeout=5m")


def test_http_inject_then_reset_records_ground_truth(tmp_path):
    fake = FakeKubectl()
    with TestClient(create_app(tmp_path, fake)) as client:
        injected = client.post("/chaos/bad-deploy").json()
        assert injected["type"] == "bad_deploy" and injected["target"] == "payment"
        assert fake.image("payment") == BAD_PAYMENT_IMAGE
        reset_entry = client.post("/chaos/reset").json()
        assert reset_entry["type"] == "reset" and reset_entry["restored"] == ["payment"]
        assert fake.image("payment") == GOOD_IMAGE
        assert client.get("/chaos/ground-truth").json() == [injected, reset_entry]


def test_http_kubectl_failure_is_502_and_not_recorded(tmp_path):
    fake = FakeKubectl()
    with TestClient(create_app(tmp_path, fake)) as client:
        fake.fail_on = "patch"
        response = client.post("/chaos/bad-deploy")
        assert response.status_code == 502 and "forbidden" in response.json()["detail"]
        assert client.get("/chaos/ground-truth").json() == []
