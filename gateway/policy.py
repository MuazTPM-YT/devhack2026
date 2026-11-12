# checklist step 3 (IMPLEMENTATION.md §6.4.2): tool, target, budgets, nothing in flight. Pure.
import sqlite3
import time


def usage(conn: sqlite3.Connection, incident_id: str, now: float | None = None) -> dict[str, int]:
    now = time.time() if now is None else now
    one = conn.execute("SELECT COUNT(*) FROM receipts WHERE incident_id=?", (incident_id,)).fetchone()[0]
    hour = conn.execute("SELECT COUNT(*) FROM receipts WHERE ts >= ?", (now - 3600,)).fetchone()[0]
    flight = conn.execute("SELECT COUNT(*) FROM receipts WHERE outcome='pending'").fetchone()[0]
    return {"incident": one, "hour": hour, "in_flight": flight}


# -> (passed, outcome on failure, reason)
def check(action: dict, services: dict, policy: dict, used: dict[str, int]) -> tuple[bool, str, str | None]:
    if action["tool"] not in policy["tools"]:
        return False, "refused", f"tool {action['tool']} not allowed"
    svc = services.get(action["target"])
    if svc is None:
        return False, "refused", f"unknown service {action['target']}"
    if svc.get("protected"):
        return False, "escalated", f"{action['target']} is protected; a human must act"
    if not svc.get("actable"):
        return False, "refused", f"{action['target']} is not actable"
    b = policy["budgets"]
    if used["incident"] >= b["max_actions_per_incident"] or used["hour"] >= b["max_actions_per_hour"]:
        return False, "escalated", "action budget used up"
    if used["in_flight"] >= b["max_in_flight"]:
        return False, "refused", "another action is still being verified"
    return True, "", None
