# what the diagnosis agent may propose: only tools the gateway can really build (gateway/dryrun.py),
# with their limits from config/policy.yaml. The model sees this list, never a tool that is not on it.
from typing import Any

# enable_degraded_mode is in the schema and policy but has no executor: leaving it out keeps the model honest
BUILT: dict[str, dict[str, str]] = {
    "rollback_deploy": {"does": "roll the Deployment back to its previous revision",
                        "needs": "a deployment change (image, resources) that came just before"},
    "revert_config": {"does": "set back one env or feature-flag change, nothing else",
                      "needs": "journal_entry: the id of that env or flag change, cited as journal:<id>"},
    "restart_service": {"does": "rolling restart; a mitigation, it does not remove a cause",
                        "needs": "evidence of a stuck or OOMKilled process"},
    "scale": {"does": "set replicas back to a count it had", "needs": "params.replicas between min and max"},
    "raise_limit": {"does": "raise memory or restore a lowered limit; a leak still needs a real fix",
                    "needs": "params.memory above the current limit; params.container names the affected container"},
}


def available(policy: dict[str, Any], services: dict[str, Any]) -> list[dict[str, Any]]:
    actable = sorted(s for s, v in services.items() if v.get("actable"))
    protected = sorted(s for s, v in services.items() if v.get("protected"))
    out = []
    for tool, text in BUILT.items():
        rules = policy["tools"].get(tool)
        if rules is None:
            continue
        entry: dict[str, Any] = {"tool": tool, **text, "targets": actable + (protected if tool == "scale" else [])}
        if tool == "scale":
            entry["limits"] = {"min": rules["min"], "max": rules["max"]}
        if tool == "raise_limit":
            entry["limits"] = {"max_memory": rules["max_memory"]}
        if rules.get("auto_eligible") is False:
            entry["approval"] = "always asks a human"
        if tool == "raise_limit" and policy.get("autonomy", {}).get("memory_restores"):
            entry["autonomous_restore"] = {
                "targets": policy["autonomy"]["memory_restores"],
                "approval": "exception: exact latest journal inverse may run without human approval",
                "needs": "journal_entry and journal:<id> evidence; params.memory must equal the previous limit",
            }
        out.append(entry)
    return out
