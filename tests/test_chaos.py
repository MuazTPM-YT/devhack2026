import copy
import json

import pytest
from fastapi.testclient import TestClient

from chaos import ground_truth
from chaos.faults import (BAD_PAYMENT_IMAGE, BROKEN_PAYMENT_ADDR, FLAG_CONFIGMAP, FLAG_FILE,
                          FLIP_FLAG, LEAK_FLAG, LIVE_FLAG_PATH, KubectlError, bad_deploy,
                          broken_config, datastore_down, flag_flip, memory_leak, shared_outage)
from chaos.main import FAULTS, create_app
from chaos.reset import TARGETS, diff_ops, ensure_snapshot, reset

GOOD_IMAGE = "ghcr.io/open-telemetry/demo:3.1.0-payment"
GOOD_FLAGS = json.dumps({"flags": {LEAK_FLAG: {"defaultVariant": "off",
                                              "variants": {"off": False, "on": True}},
                                   "adFailure": {"defaultVariant": "off"},
                                   FLIP_FLAG: {"defaultVariant": "off",
                                               "variants": {"off": 0, "50%": 0.5}}}})


def deployment(name, image=None, replicas=1, env=None):
    return {"metadata": {"name": name}, "spec": {"replicas": replicas, "template": {"spec": {
        "containers": [{"name": name, "image": image or f"demo:{name}",
                        "env": env if env is not None else [{"name": "PORT", "value": "8080"}]}]}}}}


# in-memory cluster that applies the patch types chaos sends and logs every call
class FakeKubectl:
    def __init__(self):
        self.deployments = {name: deployment(name) for name in TARGETS}
        self.deployments["payment"] = deployment("payment", GOOD_IMAGE, replicas=2)
        self.deployments["checkout"] = deployment("checkout", env=[
            {"name": "CHECKOUT_PORT", "value": "8080"}, {"name": "PAYMENT_ADDR", "value": "payment:8080"}])
        self.deployments["jaeger"] = deployment("jaeger")
        self.configmaps = {FLAG_CONFIGMAP: {"data": {FLAG_FILE: GOOD_FLAGS}}}
        # flagd's emptyDir copy, seeded from the ConfigMap like the init container does
        self.live_flags = GOOD_FLAGS
        self.calls = []
        self.fail_on = None

    def __call__(self, *args, input=None):
        self.calls.append(args)
        if args[0] == self.fail_on:
            raise KubectlError(f"kubectl {args[0]} {args[1]}: forbidden")
        if args[:2] == ("get", "deployments"):
            return json.dumps({"items": list(self.deployments.values())})
        if args[:2] == ("patch", "deployment"):
            target = self.deployments[args[2]]
            patch = json.loads(args[args.index("-p") + 1])
            if "--type=merge" in args:
                target["spec"].update(patch["spec"])
            elif "--type=json" in args:
                for op in patch:
                    assert op["op"] == "add"
                    *parents, leaf = op["path"].strip("/").split("/")
                    node = target
                    for key in parents:
                        node = node[int(key)] if isinstance(node, list) else node[key]
                    node[leaf] = op["value"]
            else:
                # strategic merge: containers and env merge by name, like the API server
                for change in patch["spec"]["template"]["spec"]["containers"]:
                    for container in target["spec"]["template"]["spec"]["containers"]:
                        if container["name"] != change["name"]:
                            continue
                        env = {e["name"]: e for e in container["env"]}
                        env.update({e["name"]: e for e in change.pop("env", [])})
                        container.update(change, env=list(env.values()))
            return ""
        if args[:2] == ("get", "configmap"):
            return json.dumps(self.configmaps[args[2]])
        if args[:2] == ("patch", "configmap"):
            self.configmaps[args[2]]["data"].update(json.loads(args[args.index("-p") + 1])["data"])
            return ""
        if args[0] == "exec":
            command = args[args.index("--") + 1:]
            if command == ("cat", LIVE_FLAG_PATH):
                return self.live_flags
            assert command == ("sh", "-c", f"cat > {LIVE_FLAG_PATH}") and input is not None
            self.live_flags = input
            return ""
        if args[:2] == ("rollout", "status"):
            return ""
        raise AssertionError(f"unexpected kubectl call {args}")

    def image(self, name):
        return self.deployments[name]["spec"]["template"]["spec"]["containers"][0]["image"]

    def env(self, name):
        return {e["name"]: e["value"]
                for e in self.deployments[name]["spec"]["template"]["spec"]["containers"][0]["env"]}

    def replicas(self, name):
        return self.deployments[name]["spec"]["replicas"]

    def leak_variant(self, text=None):
        flags = json.loads(text or self.configmaps[FLAG_CONFIGMAP]["data"][FLAG_FILE])
        return flags["flags"][LEAK_FLAG]["defaultVariant"]


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
    assert set(snapshot["deployments"]) == set(TARGETS)
    assert snapshot["deployments"]["payment"]["replicas"] == 2
    assert snapshot["flags"] == GOOD_FLAGS
    bad_deploy(fake)
    memory_leak(fake)
    again = ensure_snapshot(path, fake)
    assert again["deployments"]["payment"]["containers"][0]["image"] == GOOD_IMAGE
    assert again["flags"] == GOOD_FLAGS


def test_snapshot_old_format_fails_loud(tmp_path):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"payment": {}}))
    with pytest.raises(RuntimeError, match="old format"):
        ensure_snapshot(path, FakeKubectl())


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


def test_broken_config_sets_wrong_payment_addr_keeps_other_env():
    fake = FakeKubectl()
    assert broken_config(fake) == {"type": "broken_config", "target": "checkout",
                                   "key": "PAYMENT_ADDR"}
    assert fake.env("checkout") == {"CHECKOUT_PORT": "8080", "PAYMENT_ADDR": BROKEN_PAYMENT_ADDR}
    assert "--field-manager=chaos-panel" in fake.calls[-1]


def test_datastore_down_scales_valkey_cart_to_zero():
    fake = FakeKubectl()
    assert datastore_down(fake) == {"type": "failing_dependency", "target": "valkey-cart"}
    assert fake.replicas("valkey-cart") == 0
    assert "--field-manager=chaos-panel" in fake.calls[-1]


def test_memory_leak_flips_flag_in_configmap_and_live_file_without_restart():
    fake = FakeKubectl()
    assert memory_leak(fake) == {"type": "resource_exhaustion", "target": "recommendation"}
    assert fake.leak_variant() == "on"
    assert fake.live_flags == fake.configmaps[FLAG_CONFIGMAP]["data"][FLAG_FILE]
    flags = json.loads(fake.live_flags)["flags"]
    assert flags["adFailure"]["defaultVariant"] == "off"
    patches = [c for c in fake.calls if c[0] == "patch"]
    assert len(patches) == 1 and "--field-manager=chaos-panel" in patches[0]
    # a flagd restart leaves services' flag clients stale (seen live), so none may happen
    assert not [c for c in fake.calls if c[:2] == ("rollout", "restart")]


def test_reset_restores_flag_flipped_only_in_flagd_ui(tmp_path):
    fake = FakeKubectl()
    snapshot = ensure_snapshot(tmp_path / "s.json", fake)
    fake.live_flags = GOOD_FLAGS.replace('"off"', '"on"', 1)
    assert reset(snapshot, fake) == [f"configmap/{FLAG_CONFIGMAP}"]
    assert fake.live_flags == GOOD_FLAGS


def test_reset_undoes_every_fault_at_once(tmp_path):
    fake = FakeKubectl()
    snapshot = ensure_snapshot(tmp_path / "s.json", fake)
    for fault in FAULTS.values():
        fault(fake)
    restored = reset(snapshot, fake)
    assert sorted(restored) == ["checkout", f"configmap/{FLAG_CONFIGMAP}", "kafka", "payment", "valkey-cart"]
    assert fake.image("payment") == GOOD_IMAGE
    assert fake.replicas("kafka") == 1
    assert fake.env("checkout")["PAYMENT_ADDR"] == "payment:8080"
    assert fake.replicas("valkey-cart") == 1
    assert fake.configmaps[FLAG_CONFIGMAP]["data"][FLAG_FILE] == GOOD_FLAGS
    assert fake.live_flags == GOOD_FLAGS
    assert reset(snapshot, fake) == []


@pytest.mark.parametrize("path, kind, target", [
    ("broken-config", "broken_config", "checkout"),
    ("memory-leak", "resource_exhaustion", "recommendation"),
    ("datastore-down", "failing_dependency", "valkey-cart"),
    ("flag-flip", "broken_config", "payment"),
    ("shared-outage", "shared_dependency", "kafka"),
])
def test_http_each_fault_records_ground_truth(tmp_path, path, kind, target):
    with TestClient(create_app(tmp_path, FakeKubectl())) as client:
        response = client.post(f"/chaos/{path}")
        assert response.status_code == 200
        entry = response.json()
        assert entry["type"] == kind and entry["target"] == target
        assert client.get("/chaos/ground-truth").json() == [entry]


def test_fault_routes_match_bench_scenarios():
    from bench.harness import SCENARIOS
    assert set(SCENARIOS) <= set(FAULTS)


def test_flag_flip_sets_payment_failure_and_leaves_other_flags():
    fake = FakeKubectl()
    assert flag_flip(fake) == {"type": "broken_config", "target": "payment", "key": FLIP_FLAG}
    flags = json.loads(fake.live_flags)["flags"]
    assert flags[FLIP_FLAG]["defaultVariant"] == "50%"
    assert flags[LEAK_FLAG]["defaultVariant"] == "off"
    assert fake.live_flags == fake.configmaps[FLAG_CONFIGMAP]["data"][FLAG_FILE]
    assert not [c for c in fake.calls if c[:2] == ("rollout", "restart")]


class FakeRaw:
    def __init__(self, result=(True, "deployment.apps/cart scaled")):
        self.result, self.calls = result, []

    def __call__(self, args):
        self.calls.append(args)
        return self.result


def test_judge_kubectl_splits_without_shell_and_records_writes(tmp_path):
    raw = FakeRaw()
    with TestClient(create_app(tmp_path, FakeKubectl(), raw)) as client:
        body = client.post("/chaos/kubectl", json={"command": "kubectl scale deploy/cart --replicas=0"}).json()
        assert body == {"ok": True, "output": "deployment.apps/cart scaled", "recorded": True}
        assert raw.calls == [["scale", "deploy/cart", "--replicas=0"]]
        truth = client.get("/chaos/ground-truth").json()
        assert truth[-1]["type"] == "judge_kubectl"
        assert truth[-1]["args"] == ["scale", "deploy/cart", "--replicas=0"]


def test_judge_kubectl_shell_metacharacters_stay_plain_args(tmp_path):
    raw = FakeRaw()
    with TestClient(create_app(tmp_path, FakeKubectl(), raw)) as client:
        client.post("/chaos/kubectl", json={"command": "get pods; rm -rf / | cat $(id)"})
        assert raw.calls == [["get", "pods;", "rm", "-rf", "/", "|", "cat", "$(id)"]]


def test_judge_kubectl_read_only_not_recorded(tmp_path):
    raw = FakeRaw((True, "NAME READY"))
    with TestClient(create_app(tmp_path, FakeKubectl(), raw)) as client:
        body = client.post("/chaos/kubectl", json={"command": "get pods -o wide"}).json()
        assert body["recorded"] is False
        assert client.get("/chaos/ground-truth").json() == []


def test_judge_kubectl_failure_returns_output_not_500(tmp_path):
    raw = FakeRaw((False, 'Error from server (NotFound): deployments.apps "nope" not found'))
    with TestClient(create_app(tmp_path, FakeKubectl(), raw)) as client:
        body = client.post("/chaos/kubectl", json={"command": "delete deploy nope"}).json()
        assert body["ok"] is False and "NotFound" in body["output"]


@pytest.mark.parametrize("command, status", [("", 422), ("kubectl", 400), ("get 'unclosed", 400)])
def test_judge_kubectl_rejects_bad_input(tmp_path, command, status):
    raw = FakeRaw()
    with TestClient(create_app(tmp_path, FakeKubectl(), raw)) as client:
        assert client.post("/chaos/kubectl", json={"command": command}).status_code == status
        assert raw.calls == []


# a failed undo left payment paused, and raise_limit leaves a bigger memory limit: reset undoes both
def test_reset_unpauses_and_restores_memory_limits(tmp_path):
    fake = FakeKubectl()
    fake.deployments["recommendation"]["spec"]["template"]["spec"]["containers"][0]["resources"] = {
        "limits": {"memory": "200Mi"}}
    snapshot = ensure_snapshot(tmp_path / "s.json", fake)
    fake.deployments["payment"]["spec"]["paused"] = True
    fake.deployments["recommendation"]["spec"]["template"]["spec"]["containers"][0]["resources"] = {
        "limits": {"memory": "400Mi"}}
    assert reset(snapshot, fake) == ["payment", "recommendation"]
    assert fake.deployments["payment"]["spec"]["paused"] is False
    assert fake.deployments["recommendation"]["spec"]["template"]["spec"]["containers"][0]["resources"] == {
        "limits": {"memory": "200Mi"}}
    assert reset(snapshot, fake) == []


def test_reset_with_old_snapshot_without_resources_still_works(tmp_path):
    fake = FakeKubectl()
    snapshot = ensure_snapshot(tmp_path / "s.json", fake)
    for state in snapshot["deployments"].values():
        state.pop("paused")
        for c in state["containers"]:
            c.pop("resources")
    shared_outage(fake)
    assert reset(snapshot, fake) == ["kafka"] and fake.replicas("kafka") == 1
