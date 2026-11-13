# checklist step 3 (IMPLEMENTATION.md §6.4.2): tool, target, budgets, nothing in flight. Pure.
import math
import sqlite3
import time

from brain.rules import to_bytes
from observer import journal


# authorize exact recent-change inverses; model origin never supplies permission
def journal_revert(action: dict, services: dict, cfg: dict, entry: dict | None, latest: dict | None,
                   plan: dict, health: dict, gate: dict, now: float, flag_map: dict) -> str | None:
    target, tool = action["target"], action["tool"]
    svc = services.get(target, {})
    tool_cfg = cfg["tools"][tool]
    if (target not in cfg.get("autonomy", {}).get("journal_reverts", [])
            or not svc.get("actable") or svc.get("critical") is not False or svc.get("protected")
            or svc.get("kind") != "stateless" or tool_cfg.get("auto_eligible") is not True
            or tool_cfg.get("reversible") is not True or gate["failures"]
            or action["pattern"] != "recent_change" or not action.get("prediction")
            or action["prediction"]["target"] != target):
        return None
    stamp = health.get("ts")
    if (health.get("prometheus_ok") is not True or not isinstance(stamp, (int, float))
            or not math.isfinite(stamp) or not 0 <= now - stamp <= 3 * cfg["detection"]["poll_seconds"]):
        return None
    if (not entry or not latest or entry["id"] != latest["id"] or entry.get("by_agent") is not False
            or f"journal:{entry['id']}" not in action["evidence_ids"]
            or plan["inverse"].get("op") not in ("restore_configmap", "restore_template", "scale")):
        return None
    changes = entry.get("diff") or {}
    expected = {p: {"old": v["new"], "new": v["old"]} for p, v in changes.items()}
    if not expected:
        return None
    kind = entry["kind"]
    if tool == "revert_config" and not action["params"]:
        if kind == "flag" and entry["object"] == "configmap/flagd-config":
            if (plan["diff"] == expected and all(p.startswith("flags[") and p.endswith("].defaultVariant")
                    and flag_map.get(p[len("flags["):].split("]", 1)[0]) == target for p in changes)):
                return "journal_revert:flag"
        if kind == "env" and entry["object"] == f"deployment/{target}":
            moved = journal.entry("deployment", plan["live"], plan["after"], now, "flagd-config")
            if (moved and moved["diff"] == expected
                    and all(p.startswith("containers[") and p.endswith("].env") for p in changes)):
                return "journal_revert:env"
    if (tool == "scale" and kind == "replicas" and entry["object"] == f"deployment/{target}"
            and set(changes) == {"replicas"} and plan["diff"] == expected
            and action["params"] == {"replicas": changes["replicas"]["old"]}
            and changes["replicas"]["new"] < changes["replicas"]["old"]
            and plan["inverse"].get("op") == "scale"):
        return "journal_revert:replicas"
    return None


def usage(conn: sqlite3.Connection, incident_id: str, now: float | None = None) -> dict[str, int]:
    now = time.time() if now is None else now
    one = conn.execute("SELECT COUNT(*) FROM receipts WHERE incident_id=?", (incident_id,)).fetchone()[0]
    hour = conn.execute("SELECT COUNT(*) FROM receipts WHERE ts >= ?", (now - 3600,)).fetchone()[0]
    # a failed watchdog undo keeps blocking new actions until a human clears it
    flight = conn.execute("SELECT COUNT(*) FROM receipts WHERE outcome IN ('pending', 'watchdog_failed')").fetchone()[0]
    # orchestration: a write started but not yet receipted, or one whose outcome is unknown, holds the slot too
    try:
        flight += conn.execute("SELECT COUNT(*) FROM action_intents WHERE status IN "
                               "('executing', 'execution_unknown')").fetchone()[0]
    except sqlite3.OperationalError:  # no orchestration tables: legacy database
        pass
    return {"incident": one, "hour": hour, "in_flight": flight}


# -> (passed, outcome on failure, reason)
# asking=True: the call can only end in an approval request, so an action still in flight doesn't block it
def check(action: dict, services: dict, policy: dict, used: dict[str, int],
          asking: bool = False) -> tuple[bool, str, str | None]:
    if action["tool"] not in policy["tools"]:
        return False, "refused", f"tool {action['tool']} not allowed"
    svc = services.get(action["target"])
    if svc is None:
        return False, "refused", f"unknown service {action['target']}"
    # a data store may only be scaled back, and the checklist always asks a human first (Muaz chose)
    if svc.get("protected") and action["tool"] != "scale":
        return False, "escalated", f"{action['target']} is protected; a human must act"
    if not svc.get("actable") and not svc.get("protected"):
        return False, "refused", f"{action['target']} is not actable"
    bad = bounds(action, policy["tools"][action["tool"]])
    if bad:
        return False, "refused", bad
    b = policy["budgets"]
    if used["incident"] >= b["max_actions_per_incident"] or used["hour"] >= b["max_actions_per_hour"]:
        return False, "escalated", "action budget used up"
    if used["in_flight"] >= b["max_in_flight"] and not asking:
        return False, "refused", "another action is still being verified"
    return True, "", None


# tool params inside config/policy.yaml limits; the admission policy re-checks replicas on the cluster
def bounds(action: dict, tool: dict) -> str | None:
    p = action.get("params") or {}
    if action["tool"] == "scale":
        n = p.get("replicas")
        if type(n) is not int or not tool["min"] <= n <= tool["max"]:
            return f"scale needs integer replicas in [{tool['min']}, {tool['max']}]"
    if action["tool"] == "raise_limit":
        try:
            ok = 0 < to_bytes(str(p.get("memory"))) <= to_bytes(tool["max_memory"])
        except ValueError:
            ok = False
        if not ok:
            return f"raise_limit needs memory up to {tool['max_memory']}"
    return None


# major incident (§6.4.2 step 3): act only on the ranked root cause, one restart, never scale up
def major_check(action: dict, root_cause: str | None, restarts_done: int) -> str | None:
    if action["target"] != root_cause:
        return f"major incident: only the ranked root cause ({root_cause}) may be acted on"
    if action["tool"] == "restart_service" and restarts_done >= 1:
        return "major incident: one restart per incident"
    return None
