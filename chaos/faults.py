import json
import subprocess
from collections.abc import Callable

# chaos runs as cluster admin through the normal kubeconfig (plan §3.5)
KUBECTL = ["kubectl", "--context", "k3d-oncall", "-n", "shop"]
# agreed in SHARED_CONTEXT Q4: the agent's hands-off check keys on this
FIELD_MANAGER = "chaos-panel"
BAD_PAYMENT_IMAGE = "payment:v2-bad"

Kubectl = Callable[..., str]


class KubectlError(RuntimeError):
    pass


def kubectl(*args: str) -> str:
    done = subprocess.run([*KUBECTL, *args], capture_output=True, text=True, timeout=360)
    if done.returncode != 0:
        raise KubectlError(f"kubectl {' '.join(args[:2])}: {done.stderr.strip()}")
    return done.stdout


def bad_deploy(run: Kubectl = kubectl) -> dict[str, str]:
    patch = {"spec": {"template": {"spec": {"containers": [
        {"name": "payment", "image": BAD_PAYMENT_IMAGE}]}}}}
    run("patch", "deployment", "payment", "--type=strategic", "-p", json.dumps(patch),
        f"--field-manager={FIELD_MANAGER}")
    return {"type": "bad_deploy", "target": "payment"}
