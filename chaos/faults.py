import json
import subprocess
from collections.abc import Callable
from typing import Any

from schemas import config

# chaos runs as cluster admin through the normal kubeconfig (plan §3.5)
KUBECTL = ["kubectl", "--context", "k3d-oncall", "-n", "shop"]
# agreed in SHARED_CONTEXT Q4: the agent's hands-off check keys on this
FIELD_MANAGER = "chaos-panel"
BAD_PAYMENT_IMAGE = "payment:v2-bad"
# wrong port: checkout keeps calling payment and every call fails to connect
BROKEN_PAYMENT_ADDR = "payment:9999"
LEAK_FLAG = "recommendationCacheFailure"
FLIP_FLAG = "paymentFailure"
FLIP_VARIANT = "50%"
FLAG_CONFIGMAP = config.load("services")["flag_config"]["configmap"]
FLAG_FILE = "demo.flagd.json"
DRY = ("--dry-run=server",)

Kubectl = Callable[..., str]


class KubectlError(RuntimeError):
    pass


def kubectl(*args: str, input: str | None = None) -> str:
    done = subprocess.run([*KUBECTL, *args], input=input, capture_output=True, text=True,
                          timeout=360)
    if done.returncode != 0:
        raise KubectlError(f"kubectl {' '.join(args[:2])}: {done.stderr.strip()}")
    return done.stdout


# judges' box on /chaos (scenario 6): any kubectl as admin, args only so no shell runs
def raw_kubectl(args: list[str]) -> tuple[bool, str]:
    try:
        done = subprocess.run([*KUBECTL, *args], capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return False, "timed out after 30 s"
    return done.returncode == 0, (done.stdout + done.stderr).strip()


# one container of a Deployment: the one named like it, else the only one
def _container(deployment: dict[str, Any]) -> dict[str, Any]:
    name = deployment["metadata"]["name"]
    containers = deployment["spec"]["template"]["spec"]["containers"]
    named = [c for c in containers if c["name"] == name]
    if len(named) != 1 and len(containers) != 1:
        raise KubectlError(f"deployment {name}: no single container to change")
    return named[0] if named else containers[0]


def read_deployment(name: str, run: Kubectl = kubectl) -> dict[str, Any]:
    items = json.loads(run("get", "deployments", "-o", "json"))["items"]
    found = [d for d in items if d["metadata"]["name"] == name]
    if not found:
        raise KubectlError(f"deployment {name} not found")
    return found[0]


def read_flags(run: Kubectl = kubectl) -> str:
    return json.loads(run("get", "configmap", FLAG_CONFIGMAP, "-o", "json"))["data"][FLAG_FILE]


# flagd reads the ConfigMap directly (k8s/values.yaml) and reloads ~60 s after a patch; never restart
# flagd: services' flagd clients go stale and keep the old value (seen live)
def write_flags(text: str, run: Kubectl = kubectl, dry: bool = False) -> None:
    run("patch", "configmap", FLAG_CONFIGMAP, "--type=merge",
        "-p", json.dumps({"data": {FLAG_FILE: text}}), f"--field-manager={FIELD_MANAGER}", *(DRY if dry else ()))


# one owned field, the unit an experiment injects, compares and restores.
# kind image | env | replicas: name is the Deployment (key = env var name); kind flag: name is the flag.
# env value None means the variable is absent
def read_field(kind: str, name: str, key: str | None, run: Kubectl = kubectl) -> Any:
    if kind == "flag":
        return json.loads(read_flags(run))["flags"][name].get("defaultVariant")
    deployment = read_deployment(name, run)
    if kind == "replicas":
        return deployment["spec"].get("replicas", 1)
    container = _container(deployment)
    if kind == "memory":
        return ((container.get("resources") or {}).get("limits") or {}).get("memory")
    if kind == "image":
        return container["image"]
    return next((e.get("value") for e in container.get("env", []) if e["name"] == key), None)


# dry: the API server checks the patch and stores nothing
def write_field(kind: str, name: str, key: str | None, value: Any, run: Kubectl = kubectl,
                dry: bool = False) -> None:
    extra = (f"--field-manager={FIELD_MANAGER}", *(DRY if dry else ()))
    if kind == "flag":
        flags = json.loads(read_flags(run))
        flags["flags"][name]["defaultVariant"] = value
        write_flags(json.dumps(flags, indent=2), run, dry)
        return
    if kind == "replicas":
        run("patch", "deployment", name, "--type=merge", "-p", json.dumps({"spec": {"replicas": value}}), *extra)
        return
    if kind == "memory":
        deployment = read_deployment(name, run)
        containers = deployment["spec"]["template"]["spec"]["containers"]
        index = containers.index(_container(deployment))
        memory_patch = [{"op": "add", "path": f"/spec/template/spec/containers/{index}/resources/limits/memory", "value": value}]
        run("patch", "deployment", name, "--type=json", "-p", json.dumps(memory_patch), *extra)
        return
    container = _container(read_deployment(name, run))["name"]
    if kind == "image":
        change: dict[str, Any] = {"image": value}
    else:
        change = {"env": [{"name": key, "$patch": "delete"} if value is None else {"name": key, "value": value}]}
    patch = {"spec": {"template": {"spec": {"containers": [{"name": container, **change}]}}}}
    run("patch", "deployment", name, "--type=strategic", "-p", json.dumps(patch), *extra)


# the six fixed scenarios: presets over write_field, kept for the bench, the CLI and smoke.sh
def bad_deploy(run: Kubectl = kubectl) -> dict[str, str]:
    write_field("image", "payment", None, BAD_PAYMENT_IMAGE, run)
    return {"type": "bad_deploy", "target": "payment"}


def broken_config(run: Kubectl = kubectl) -> dict[str, str]:
    write_field("env", "checkout", "PAYMENT_ADDR", BROKEN_PAYMENT_ADDR, run)
    return {"type": "broken_config", "target": "checkout", "key": "PAYMENT_ADDR"}


def datastore_down(run: Kubectl = kubectl) -> dict[str, str]:
    write_field("replicas", "valkey-cart", None, 0, run)
    return {"type": "failing_dependency", "target": "valkey-cart"}


# scenario 10: kafka gone takes checkout, accounting and fraud-detection down together (major incident)
def shared_outage(run: Kubectl = kubectl) -> dict[str, str]:
    write_field("replicas", "kafka", None, 0, run)
    return {"type": "shared_dependency", "target": "kafka"}


# scenario 3: a plain bad flag change, half of payments fail; the fix is reverting the flag
def flag_flip(run: Kubectl = kubectl) -> dict[str, str]:
    write_field("flag", FLIP_FLAG, None, FLIP_VARIANT, run)
    return {"type": "broken_config", "target": "payment", "key": FLIP_FLAG}


def memory_leak(run: Kubectl = kubectl) -> dict[str, str]:
    write_field("flag", LEAK_FLAG, None, "on", run)
    return {"type": "resource_exhaustion", "target": "recommendation"}
