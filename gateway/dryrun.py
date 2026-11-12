# dry run + snapshot (IMPLEMENTATION.md §6.4.3). All writes: agent identity, field manager oncall-agent.
import copy
import hashlib
import json
from typing import Any

FIELD_MANAGER = "oncall-agent"
JSON_PATCH = "application/json-patch+json"  # kubernetes 36 defaults every patch to this; we pass it explicitly
REVISION = "deployment.kubernetes.io/revision"


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
