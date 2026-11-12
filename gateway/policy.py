# checklist step 3 (IMPLEMENTATION.md §6.4.2): tool, target, budgets, nothing in flight. Pure.
import sqlite3
import time

from brain.rules import to_bytes


def usage(conn: sqlite3.Connection, incident_id: str, now: float | None = None) -> dict[str, int]:
    now = time.time() if now is None else now
    one = conn.execute("SELECT COUNT(*) FROM receipts WHERE incident_id=?", (incident_id,)).fetchone()[0]
    hour = conn.execute("SELECT COUNT(*) FROM receipts WHERE ts >= ?", (now - 3600,)).fetchone()[0]
    # a failed watchdog undo keeps blocking new actions until a human clears it
    flight = conn.execute("SELECT COUNT(*) FROM receipts WHERE outcome IN ('pending', 'watchdog_failed')").fetchone()[0]
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
    if svc.get("protected"):
        return False, "escalated", f"{action['target']} is protected; a human must act"
    if not svc.get("actable"):
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
