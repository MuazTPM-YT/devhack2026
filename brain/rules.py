# deterministic rules (IMPLEMENTATION.md §6.3.6). match() is the rule's own pick; candidates() lists every
# fix the evidence supports, so the diagnosis agent can accept the pick, take another, or decline.
# Works on plain dicts (journal rows, incident); actions follow the ActionRequest fields.
import copy
import re

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
def flag_targets(entry: dict, flag_map: dict) -> set[str]:
    names = [p[len("flags["):].split("]", 1)[0] for p in entry.get("diff", {}) if p.startswith("flags[")]
    return {flag_map[n] for n in names if n in flag_map}


# non-restart changes on the culprit's Deployment, or on a flag that config/services.yaml `flags:` maps
# to the culprit, inside the window; newest first
def changes_before_onset(journal: list[dict], culprit: str, onset: float, window_s: float,
                         flag_map: dict | None = None) -> list[dict]:
    hits = [j for j in journal if onset - window_s <= j["ts"] <= onset and j["kind"] != "restart"
            and (j["object"] == f"deployment/{culprit}"
                 or (j["kind"] == "flag" and culprit in flag_targets(j, flag_map or {})))]
    return sorted(hits, key=lambda j: (j["ts"], j["id"]), reverse=True)


# THE GENERAL RULE input: the newest of them
def latest_change_before_onset(journal: list[dict], culprit: str, onset: float, window_s: float,
                               flag_map: dict | None = None) -> dict | None:
    return next(iter(changes_before_onset(journal, culprit, onset, window_s, flag_map)), None)


# the inverse of one recorded change, as an action
def _undo(incident: dict, change: dict, culprit: str, pattern: str, policy: dict) -> dict:
    tool = TOOL_FOR_KIND[change["kind"]]
    params = {"replicas": change["diff"]["replicas"]["old"]} if tool == "scale" else {}
    if restored := memory_restore(change, policy):
        tool, params = "raise_limit", restored
    return _action(incident, tool, culprit, pattern, [f"journal:{change['id']}"], params, change["id"])


# restore one lowered memory cap; mixed resource changes need a full rollback
def memory_restore(change: dict, policy: dict) -> dict | None:
    diff = change.get("diff") or {}
    if change.get("kind") != "resources" or len(diff) != 1:
        return None
    path, values = next(iter(diff.items()))
    container = re.fullmatch(r"containers\[([^]]+)\]\.resources", path)
    if container is None:
        return None
    old, new = values.get("old") or {}, values.get("new") or {}
    before, after = (old.get("limits") or {}).get("memory"), (new.get("limits") or {}).get("memory")
    try:
        if not 0 < to_bytes(str(after)) < to_bytes(str(before)) <= to_bytes(policy["tools"]["raise_limit"]["max_memory"]):
            return None
    except (ValueError, OverflowError):
        return None
    restored = copy.deepcopy(new)
    restored["limits"]["memory"] = before
    if restored != old:
        return None
    return {"memory": before, "container": container[1]}


def _resource(incident: dict, culprit: str, events: list[dict], policy: dict, memory_ratio: float | None,
              memory_limit: str | None) -> list[dict]:
    oom = [e["id"] for e in events if "OOMKilled" in e.get("summary", "")]
    if not oom and (memory_ratio is None or memory_ratio < 0.9):
        return []
    evidence = oom or [f"query:memory_ratio:service={culprit}"]
    actions = [_action(incident, "restart_service", culprit, "resource", evidence)]
    if memory_limit:
        cap = to_bytes(policy["tools"]["raise_limit"]["max_memory"])
        new = min(2 * to_bytes(memory_limit), cap)
        if new > to_bytes(memory_limit):
            actions.append(_action(incident, "raise_limit", culprit, "resource", evidence,
                                   {"memory": f"{new // 2**20}Mi"}))
    return actions


# -> (pattern, actions). pattern: recent_change | resource | protected | unknown.
# A watch-only service (in services.yaml, neither actable nor protected: accounting, fraud-detection) keeps
# its pattern but gets no action: live, a restart_service on fraud-detection was proposed, refused by the
# MCP schema and escalated with a confusing "validation error" briefing
def match(incident: dict, journal: list[dict], events: list[dict], services: dict, policy: dict,
          memory_ratio: float | None = None, memory_limit: str | None = None,
          flag_map: dict | None = None) -> tuple[str, list[dict]]:
    pattern, actions = _match(incident, journal, events, services, policy, memory_ratio, memory_limit, flag_map)
    svc = services.get(incident.get("culprit") or "", {})
    if actions and not svc.get("actable") and not svc.get("protected"):
        return pattern, []
    return pattern, actions


def _match(incident: dict, journal: list[dict], events: list[dict], services: dict, policy: dict,
           memory_ratio: float | None, memory_limit: str | None,
           flag_map: dict | None) -> tuple[str, list[dict]]:
    culprit = incident.get("culprit")
    if culprit is None or culprit not in services:
        return "unknown", []
    window_s = policy["change_window_minutes"] * 60
    change = latest_change_before_onset(journal, culprit, incident["onset_at"], window_s, flag_map)

    if services[culprit].get("protected"):
        # propose the obvious inverse anyway; the gateway always escalates protected targets
        if change and change["kind"] == "replicas":
            return "protected", [_undo(incident, change, culprit, "protected", policy)]
        return "protected", []

    if change and not change["by_agent"] and change["kind"] in TOOL_FOR_KIND:
        return "recent_change", [_undo(incident, change, culprit, "recent_change", policy)]

    actions = _resource(incident, culprit, events, policy, memory_ratio, memory_limit)
    return ("resource", actions) if actions else ("unknown", [])


MAX_CANDIDATES = 4


def _basis(action: dict, journal: list[dict], onset: float, first: bool) -> str:
    entry = next((j for j in journal if j["id"] == action["journal_entry"]), None)
    if entry is None:
        return {"restart_service": "pod was OOMKilled or memory is at its limit",
                "raise_limit": "more memory, after a restart"}.get(action["tool"], "rule")
    newest = "newest change, " if first else "older change, "
    return f"{newest}{entry['kind']} on {entry['object']} {onset - entry['ts']:.0f} s before errors began"


# -> (pattern, candidates). Every fix the evidence supports, the rule's own pick first (c1 == match()[1][0]),
# then older changes on the culprit and the resource fixes the rule stopped short of.
# Each candidate: {"id": "c1", "basis": why it is on the list, "action": ActionRequest fields}
def candidates(incident: dict, journal: list[dict], events: list[dict], services: dict, policy: dict,
               memory_ratio: float | None = None, memory_limit: str | None = None,
               flag_map: dict | None = None) -> tuple[str, list[dict]]:
    pattern, actions = match(incident, journal, events, services, policy, memory_ratio, memory_limit, flag_map)
    culprit = incident.get("culprit")
    svc = services.get(culprit or "", {})
    found = list(actions)
    if culprit and svc.get("actable"):
        window_s = policy["change_window_minutes"] * 60
        for change in changes_before_onset(journal, culprit, incident["onset_at"], window_s, flag_map):
            if not change["by_agent"] and change["kind"] in TOOL_FOR_KIND:
                found.append(_undo(incident, change, culprit, "recent_change", policy))
        found += _resource(incident, culprit, events, policy, memory_ratio, memory_limit)
    unique: list[dict] = []
    for action in found:
        key = (action["tool"], action["target"], action["journal_entry"], str(action["params"]))
        if key not in [(u["tool"], u["target"], u["journal_entry"], str(u["params"])) for u in unique]:
            unique.append(action)
    onset = incident.get("onset_at") or 0
    return pattern, [{"id": f"c{i + 1}", "basis": _basis(a, journal, onset, i == 0), "action": a}
                     for i, a in enumerate(unique[:MAX_CANDIDATES])]
