import json
from pathlib import Path
from typing import Any

from chaos.faults import FIELD_MANAGER, Kubectl, kubectl

# shortcut: copy of config/services.yaml names (no YAML lib yet); read the file once pyyaml lands
TARGETS = ["payment", "checkout", "cart", "frontend", "recommendation", "ad", "email",
           "valkey-cart", "kafka"]

Snapshot = dict[str, dict[str, Any]]


def _state(deployment: dict[str, Any]) -> dict[str, Any]:
    spec = deployment["spec"]
    return {
        "replicas": spec.get("replicas", 1),
        "containers": [{"name": c["name"], "image": c["image"], "env": c.get("env", [])}
                       for c in spec["template"]["spec"]["containers"]],
    }


def read_cluster(run: Kubectl = kubectl) -> Snapshot:
    items = json.loads(run("get", "deployments", "-o", "json"))["items"]
    return {d["metadata"]["name"]: _state(d) for d in items if d["metadata"]["name"] in TARGETS}


# first start only: an existing file is the known-healthy state, never overwrite it
def ensure_snapshot(path: Path, run: Kubectl = kubectl) -> Snapshot:
    if path.exists():
        return json.loads(path.read_text())
    snapshot = read_cluster(run)
    missing = sorted(set(TARGETS) - snapshot.keys())
    if missing:
        raise RuntimeError(f"cannot snapshot, deployments missing: {missing}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True))
    return snapshot


# JSON patch ops that turn current back into healthy; "add" replaces, so extra env is dropped too
def diff_ops(healthy: dict[str, Any], current: dict[str, Any]) -> list[dict[str, Any]]:
    ops: list[dict[str, Any]] = []
    if current["replicas"] != healthy["replicas"]:
        ops.append({"op": "add", "path": "/spec/replicas", "value": healthy["replicas"]})
    now = {c["name"]: (i, c) for i, c in enumerate(current["containers"])}
    for want in healthy["containers"]:
        if want["name"] not in now:
            raise RuntimeError(f"container {want['name']} gone, cannot restore")
        i, have = now[want["name"]]
        base = f"/spec/template/spec/containers/{i}"
        for field in ("image", "env"):
            if have[field] != want[field]:
                ops.append({"op": "add", "path": f"{base}/{field}", "value": want[field]})
    return ops


# shortcut: waits for rollouts, not observer severity 0 (C4 /health/now not built); switch when it is
def reset(snapshot: Snapshot, run: Kubectl = kubectl) -> list[str]:
    current = read_cluster(run)
    restored = []
    for name, healthy in snapshot.items():
        ops = diff_ops(healthy, current[name])
        if ops:
            run("patch", "deployment", name, "--type=json", "-p", json.dumps(ops),
                f"--field-manager={FIELD_MANAGER}")
            restored.append(name)
    for name in restored:
        run("rollout", "status", f"deployment/{name}", "--timeout=5m")
    return restored
