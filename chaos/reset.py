import json
from pathlib import Path
from typing import Any

from chaos.faults import (FIELD_MANAGER, FLAG_CONFIGMAP, Kubectl, kubectl, read_flags,
                          read_live_flags, write_flags)
from schemas import config

TARGETS = list(config.load("services")["services"])

# {"deployments": {name: state}, "flags": flagd-config file text}
Snapshot = dict[str, Any]


def _state(deployment: dict[str, Any]) -> dict[str, Any]:
    spec = deployment["spec"]
    return {
        "replicas": spec.get("replicas", 1),
        "paused": spec.get("paused", False),
        "containers": [{"name": c["name"], "image": c["image"], "env": c.get("env", []),
                        "resources": c.get("resources", {})}
                       for c in spec["template"]["spec"]["containers"]],
    }


def read_cluster(run: Kubectl = kubectl) -> dict[str, dict[str, Any]]:
    items = json.loads(run("get", "deployments", "-o", "json"))["items"]
    return {d["metadata"]["name"]: _state(d) for d in items if d["metadata"]["name"] in TARGETS}


# first start only: an existing file is the known-healthy state, never overwrite it
def ensure_snapshot(path: Path, run: Kubectl = kubectl) -> Snapshot:
    if path.exists():
        snapshot = json.loads(path.read_text())
        if set(snapshot) != {"deployments", "flags"}:
            raise RuntimeError(f"{path} is an old format; delete it while the shop is healthy")
        return snapshot
    deployments = read_cluster(run)
    missing = sorted(set(TARGETS) - deployments.keys())
    if missing:
        raise RuntimeError(f"cannot snapshot, deployments missing: {missing}")
    snapshot = {"deployments": deployments, "flags": read_flags(run)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True))
    return snapshot


# JSON patch ops that turn current back into healthy; "add" replaces, so extra env is dropped too
def diff_ops(healthy: dict[str, Any], current: dict[str, Any]) -> list[dict[str, Any]]:
    ops: list[dict[str, Any]] = []
    if current["replicas"] != healthy["replicas"]:
        ops.append({"op": "add", "path": "/spec/replicas", "value": healthy["replicas"]})
    # a failed undo once left payment paused; a paused Deployment never rolls the next fault out
    if current.get("paused") and not healthy.get("paused"):
        ops.append({"op": "add", "path": "/spec/paused", "value": False})
    now = {c["name"]: (i, c) for i, c in enumerate(current["containers"])}
    for want in healthy["containers"]:
        if want["name"] not in now:
            raise RuntimeError(f"container {want['name']} gone, cannot restore")
        i, have = now[want["name"]]
        base = f"/spec/template/spec/containers/{i}"
        # snapshots taken before resources were recorded skip them (no key)
        for field in [f for f in ("image", "env", "resources") if f in want]:
            if have.get(field) != want[field]:
                ops.append({"op": "add", "path": f"{base}/{field}", "value": want[field]})
    return ops


# shortcut: waits for rollouts, not observer severity 0 (C4 /health/now not wired); switch when it is
def reset(snapshot: Snapshot, run: Kubectl = kubectl) -> list[str]:
    current = read_cluster(run)
    restored = []
    for name, healthy in snapshot["deployments"].items():
        ops = diff_ops(healthy, current[name])
        if ops:
            run("patch", "deployment", name, "--type=json", "-p", json.dumps(ops),
                f"--field-manager={FIELD_MANAGER}")
            restored.append(name)
    # live file too: a judge may have flipped a flag in the flagd UI
    if snapshot["flags"] != read_flags(run) or snapshot["flags"] != read_live_flags(run):
        write_flags(snapshot["flags"], run)
        restored.append(f"configmap/{FLAG_CONFIGMAP}")
    for name in restored:
        if not name.startswith("configmap/"):
            run("rollout", "status", f"deployment/{name}", "--timeout=5m")
    return restored
