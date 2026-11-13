import json
import subprocess
from collections.abc import Callable

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
# flagd reads this emptyDir copy and hot-reloads it; flagd-ui mounts the same dir here
LIVE_FLAGS = ["exec", "-i", "deploy/flagd", "-c", "flagd-ui", "--"]
LIVE_FLAG_PATH = f"/app/data/{FLAG_FILE}"

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


def bad_deploy(run: Kubectl = kubectl) -> dict[str, str]:
    patch = {"spec": {"template": {"spec": {"containers": [
        {"name": "payment", "image": BAD_PAYMENT_IMAGE}]}}}}
    run("patch", "deployment", "payment", "--type=strategic", "-p", json.dumps(patch),
        f"--field-manager={FIELD_MANAGER}")
    return {"type": "bad_deploy", "target": "payment"}


def broken_config(run: Kubectl = kubectl) -> dict[str, str]:
    patch = {"spec": {"template": {"spec": {"containers": [
        {"name": "checkout", "env": [{"name": "PAYMENT_ADDR", "value": BROKEN_PAYMENT_ADDR}]}]}}}}
    run("patch", "deployment", "checkout", "--type=strategic", "-p", json.dumps(patch),
        f"--field-manager={FIELD_MANAGER}")
    return {"type": "broken_config", "target": "checkout", "key": "PAYMENT_ADDR"}


def datastore_down(run: Kubectl = kubectl) -> dict[str, str]:
    run("patch", "deployment", "valkey-cart", "--type=merge", "-p", '{"spec":{"replicas":0}}',
        f"--field-manager={FIELD_MANAGER}")
    return {"type": "failing_dependency", "target": "valkey-cart"}


# §7 scenario 10: kafka is a shared dependency; a wide outage should trip major-incident mode
def shared_outage(run: Kubectl = kubectl) -> dict[str, str]:
    run("patch", "deployment", "kafka", "--type=merge", "-p", '{"spec":{"replicas":0}}',
        f"--field-manager={FIELD_MANAGER}")
    return {"type": "shared_dependency", "target": "kafka"}


def read_flags(run: Kubectl = kubectl) -> str:
    return json.loads(run("get", "configmap", FLAG_CONFIGMAP, "-o", "json"))["data"][FLAG_FILE]


def read_live_flags(run: Kubectl = kubectl) -> str:
    return run(*LIVE_FLAGS, "cat", LIVE_FLAG_PATH)


# ConfigMap: survives flagd restarts and the observer journals it. Live file: takes effect now.
# Never restart flagd: services' flagd clients go stale and keep the old value.
def write_flags(text: str, run: Kubectl = kubectl) -> None:
    run("patch", "configmap", FLAG_CONFIGMAP, "--type=merge",
        "-p", json.dumps({"data": {FLAG_FILE: text}}), f"--field-manager={FIELD_MANAGER}")
    run(*LIVE_FLAGS, "sh", "-c", f"cat > {LIVE_FLAG_PATH}", input=text)


# scenario 3: a plain bad flag change, half of payments fail; the fix is reverting the flag
def flag_flip(run: Kubectl = kubectl) -> dict[str, str]:
    flags = json.loads(read_flags(run))
    flags["flags"][FLIP_FLAG]["defaultVariant"] = FLIP_VARIANT
    write_flags(json.dumps(flags, indent=2), run)
    return {"type": "broken_config", "target": "payment", "key": FLIP_FLAG}


def memory_leak(run: Kubectl = kubectl) -> dict[str, str]:
    flags = json.loads(read_flags(run))
    flags["flags"][LEAK_FLAG]["defaultVariant"] = "on"
    write_flags(json.dumps(flags, indent=2), run)
    return {"type": "resource_exhaustion", "target": "recommendation"}
