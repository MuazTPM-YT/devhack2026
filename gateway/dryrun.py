# dry run + snapshot (IMPLEMENTATION.md §6.4.3). All writes: agent identity, field manager oncall-agent.
import copy
import hashlib
import json
from typing import Any

FIELD_MANAGER = "oncall-agent"
JSON_PATCH = "application/json-patch+json"  # kubernetes 36 defaults every patch to this; we pass it explicitly
STRATEGIC = "application/strategic-merge-patch+json"
MERGE = "application/merge-patch+json"
REVISION = "deployment.kubernetes.io/revision"
RESTART_KEY = "kubectl.kubernetes.io/restartedAt"


class WriteRefused(Exception):
    def __init__(self, outcome: str, reason: str):
        super().__init__(reason)
        self.outcome, self.reason = outcome, reason


def _h(part: Any) -> str:
    return hashlib.sha256(json.dumps(part, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


# SHA-256 of canonical spec (Deployments) / data (ConfigMaps); never status or metadata
def spec_hashes(deployments: list[dict], configmaps: list[dict]) -> dict[str, str]:
    out = {f"deployment/{d['metadata']['name']}": _h(d.get("spec")) for d in deployments}
    out.update({f"configmap/{c['metadata']['name']}": _h(c.get("data")) for c in configmaps})
    return out


def namespace_hash(hashes: dict[str, str]) -> str:
    return _h(hashes)


# template of the newest ReplicaSet older than the live revision, pod-template-hash label dropped
def previous_template(deployment: dict, replicasets: list[dict]) -> tuple[dict, str] | None:
    name = deployment["metadata"]["name"]
    current = int((deployment["metadata"].get("annotations") or {}).get(REVISION, 0))
    owned = []
    for rs in replicasets:
        if any(o.get("kind") == "Deployment" and o.get("name") == name
               for o in rs["metadata"].get("ownerReferences") or []):
            rev = int((rs["metadata"].get("annotations") or {}).get(REVISION, 0))
            if 0 < rev < current:
                owned.append((rev, rs))
    if not owned:
        return None
    rev, rs = max(owned, key=lambda x: x[0])
    template = copy.deepcopy(rs["spec"]["template"])
    (template.get("metadata", {}).get("labels") or {}).pop("pod-template-hash", None)
    return template, str(rev)


def rollback_patch(resource_version: str, template: dict) -> list[dict]:
    return [{"op": "test", "path": "/metadata/resourceVersion", "value": resource_version},
            {"op": "replace", "path": "/spec/template", "value": template}]


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict) and value:
        out: dict[str, Any] = {}
        for k, v in value.items():
            out.update(_flatten(v, f"{prefix}.{k}" if prefix else k))
        return out
    return {prefix: value}


# spec paths that differ; the receipt's diff
def spec_diff(old_spec: dict, new_spec: dict) -> dict[str, dict]:
    a, b = _flatten(old_spec), _flatten(new_spec)
    return {p: {"old": a.get(p), "new": b.get(p)} for p in sorted(a.keys() | b.keys()) if a.get(p) != b.get(p)}


# a rollback may only touch spec.template; anything else fails the step
def outside_allowed(diff: dict[str, dict], allowed_prefix: str = "template") -> list[str]:
    return [p for p in diff if p != allowed_prefix and not p.startswith(allowed_prefix + ".")]


def _single_container(live: dict, wanted: str | None) -> dict:
    containers = live["spec"]["template"]["spec"]["containers"]
    named = [c for c in containers if c["name"] == wanted] if wanted else containers
    if len(named) != 1:
        raise WriteRefused("refused", f"name one container of {[c['name'] for c in containers]} in params.container")
    return named[0]


# one patch per tool (§6.4.7); every body carries the live resourceVersion so a concurrent edit 409s
def build_patch(tool: str, live: dict, params: dict, entry: dict | None, replicasets: list[dict],
                now_iso: str) -> dict:
    rv = live["metadata"]["resourceVersion"]
    name = live["metadata"]["name"]
    pin = {"metadata": {"resourceVersion": rv}}
    if tool == "rollback_deploy":
        prev = previous_template(live, replicasets)
        if prev is None:
            raise WriteRefused("escalated", f"{name} has no earlier revision to roll back to")
        template, rev = prev
        return {"kind": "deployment", "content_type": JSON_PATCH, "body": rollback_patch(rv, template),
                "allowed": "template", "summary": f"back to revision {rev}"}
    if tool == "revert_config":
        if entry is None or entry["object"] != f"deployment/{name}" or entry["kind"] != "env":
            raise WriteRefused("refused", "revert_config needs an env journal entry on this Deployment "
                                          "(ConfigMap/flag reverts are not built yet)")
        body = next((op["body"] for op in entry["inverse"] if op["op"] == "patch"), None)
        if body is None:
            raise WriteRefused("refused", f"journal entry {entry['id']} has no patch inverse")
        return {"kind": "deployment", "content_type": STRATEGIC, "body": {**copy.deepcopy(body), **pin},
                "allowed": "template.spec.containers", "summary": f"env back to before journal entry {entry['id']}"}
    if tool == "restart_service":
        return {"kind": "deployment", "content_type": STRATEGIC, "allowed": "template.metadata.annotations",
                "body": {**pin, "spec": {"template": {"metadata": {"annotations": {RESTART_KEY: now_iso}}}}},
                "summary": "rolling restart"}
    if tool == "scale":
        n = params["replicas"]
        return {"kind": "scale", "content_type": MERGE, "allowed": "replicas", "body": {**pin, "spec": {"replicas": n}},
                "summary": f"replicas {live['spec'].get('replicas')} -> {n}"}
    if tool == "raise_limit":
        c = _single_container(live, params.get("container"))
        old = ((c.get("resources") or {}).get("limits") or {}).get("memory")
        from brain.rules import to_bytes
        if old and to_bytes(params["memory"]) <= to_bytes(old):
            raise WriteRefused("refused", f"{params['memory']} does not raise the current limit {old}")
        return {"kind": "deployment", "content_type": STRATEGIC, "allowed": "template.spec.containers",
                "body": {**pin, "spec": {"template": {"spec": {"containers": [
                    {"name": c["name"], "resources": {"limits": {"memory": params["memory"]}}}]}}}},
                "summary": f"memory limit of {c['name']} {old} -> {params['memory']}"}
    raise WriteRefused("refused", f"{tool} not built yet")
