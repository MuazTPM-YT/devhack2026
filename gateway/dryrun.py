# dry run + snapshot (IMPLEMENTATION.md §6.4.3). Pure part only for now: namespace hashes.
import hashlib
import json


# SHA-256 of canonical spec (Deployments) / data (ConfigMaps); never status or metadata
def spec_hashes(deployments: list[dict], configmaps: list[dict]) -> dict[str, str]:
    def h(part) -> str:
        return hashlib.sha256(json.dumps(part, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    out = {f"deployment/{d['metadata']['name']}": h(d.get("spec")) for d in deployments}
    out.update({f"configmap/{c['metadata']['name']}": h(c.get("data")) for c in configmaps})
    return out
