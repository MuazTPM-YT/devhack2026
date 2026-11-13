# deterministic rules (IMPLEMENTATION.md §6.3.6). The LLM never picks the action when a rule matches.
# Dict-based until schemas/ (C1) lands; actions follow the ActionRequest fields.

# template-level changes undo by rollback; env by revert_config; replica count by scale
TOOL_FOR_KIND = {"image": "rollback_deploy", "resources": "rollback_deploy", "other": "rollback_deploy",
                 "flag": "revert_config",
                 "env": "revert_config", "replicas": "scale"}
UNITS = {"Ki": 2**10, "Mi": 2**20, "Gi": 2**30, "K": 10**3, "M": 10**6, "G": 10**9}


def to_bytes(q: str) -> int:
    for u in sorted(UNITS, key=len, reverse=True):
        if q.endswith(u):
            return int(float(q[: -len(u)]) * UNITS[u])
    return int(q)


def _action(incident: dict, tool: str, target: str, pattern: str, evidence: list[str], params=None,
            journal_entry=None) -> dict:
    return {"incident_id": incident["id"], "tool": tool, "target": target, "params": params or {},
            "pattern": pattern, "evidence_ids": evidence, "prediction": None, "journal_entry": journal_entry}


# services a flag journal entry touches, via config/services.yaml `flags:`
def _flag_targets(entry: dict, flag_map: dict) -> set[str]:
    names = [p[len("flags["):].split("]", 1)[0] for p in entry.get("diff", {}) if p.startswith("flags[")]
    return {flag_map[n] for n in names if n in flag_map}


# THE GENERAL RULE input: newest non-restart change on the culprit's Deployment, or on a flag that
# config/services.yaml `flags:` maps to the culprit, inside the window
def latest_change_before_onset(journal: list[dict], culprit: str, onset: float, window_s: float,
                               flag_map: dict | None = None) -> dict | None:
    hits = [j for j in journal if onset - window_s <= j["ts"] <= onset and j["kind"] != "restart"
            and (j["object"] == f"deployment/{culprit}"
                 or (j["kind"] == "flag" and culprit in _flag_targets(j, flag_map or {})))]
    return max(hits, key=lambda j: (j["ts"], j["id"]), default=None)


# -> (pattern, actions). pattern: recent_change | resource | protected | unknown
def match(incident: dict, journal: list[dict], events: list[dict], services: dict, policy: dict,
          memory_ratio: float | None = None, memory_limit: str | None = None,
          flag_map: dict | None = None) -> tuple[str, list[dict]]:
    culprit = incident.get("culprit")
    if culprit is None or culprit not in services:
        return "unknown", []
    window_s = policy["change_window_minutes"] * 60
    change = latest_change_before_onset(journal, culprit, incident["onset_at"], window_s, flag_map)

    if services[culprit].get("protected"):
        # propose the obvious inverse anyway; the gateway always escalates protected targets
        if change and change["kind"] == "replicas":
            old = change["diff"]["replicas"]["old"]
            return "protected", [_action(incident, "scale", culprit, "protected", [f"journal:{change['id']}"],
                                         {"replicas": old}, change["id"])]
        return "protected", []

    if change and not change["by_agent"] and change["kind"] in TOOL_FOR_KIND:
        tool = TOOL_FOR_KIND[change["kind"]]
        params = {"replicas": change["diff"]["replicas"]["old"]} if tool == "scale" else {}
        return "recent_change", [_action(incident, tool, culprit, "recent_change", [f"journal:{change['id']}"],
                                         params, change["id"])]

    oom = [e["id"] for e in events if "OOMKilled" in e.get("summary", "")]
    if oom or (memory_ratio is not None and memory_ratio >= 0.9):
        evidence = oom or [f"query:memory_ratio:service={culprit}"]
        actions = [_action(incident, "restart_service", culprit, "resource", evidence)]
        if memory_limit:
            cap = to_bytes(policy["tools"]["raise_limit"]["max_memory"])
            new = min(2 * to_bytes(memory_limit), cap)
            if new > to_bytes(memory_limit):
                actions.append(_action(incident, "raise_limit", culprit, "resource", evidence,
                                       {"memory": f"{new // 2**20}Mi"}))
        return "resource", actions

    return "unknown", []
