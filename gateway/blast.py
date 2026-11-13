# blast radius + net benefit (IMPLEMENTATION.md §6.4.4). Pure; the checklist feeds it graph, health, pods.
from datetime import datetime
from statistics import median

from brain.graph import upstream

ROLLOUT_TOOLS = {"rollback_deploy", "revert_config", "restart_service", "raise_limit"}
DEFAULT_STARTUP_S = 30.0  # ponytail: used only when no Ready pod tells us; measured value wins


def blast_radius(target: str, edges: list[tuple[str, str, float]], health: dict) -> dict:
    up = upstream(edges, target)
    services = health.get("services", {})
    # missing reading = not proven healthy-and-unaffected; count it as healthy so it is protected
    healthy_hit = sorted(s for s in up if not services.get(s, {}).get("unhealthy"))
    return {"upstream": sorted(up), "healthy_affected": healthy_hit}


# creation -> Ready of the target's current pods; what a fresh pod costs us
def startup_seconds(pods: list[dict]) -> float:
    def ts(v: str) -> float:
        return datetime.fromisoformat(v).timestamp()

    samples = []
    for p in pods:
        ready = next((c for c in (p.get("status") or {}).get("conditions") or []
                      if c.get("type") == "Ready" and c.get("status") == "True"), None)
        created = p["metadata"].get("creationTimestamp")
        if ready and created and ready.get("lastTransitionTime"):
            samples.append(max(0.0, ts(ready["lastTransitionTime"]) - ts(created)))
    return median(samples) if samples else DEFAULT_STARTUP_S


def surge_ok(deployment: dict) -> bool:
    s = deployment["spec"].get("strategy") or {}
    rolling = s.get("rollingUpdate") or {}
    surge = str(rolling.get("maxSurge", "25%")).removesuffix("%")
    return (s.get("type") == "RollingUpdate" and str(rolling.get("maxUnavailable")) in ("0", "0%")
            and surge.isdecimal() and int(surge) > 0)


# seconds of lost capacity the action itself may cause
def forecast_added_seconds(tool: str, replicas: int, surge: bool, startup_s: float) -> float:
    if tool not in ROLLOUT_TOOLS:
        return 0.0  # scale changes capacity without restarting the running pods
    if replicas >= 1 and surge:
        return 0.0  # a new pod is Ready before an old one goes
    return startup_s


def net_benefit(severity_now: float, blast: dict, forecast_s: float, services: dict, policy: dict) -> tuple[bool, dict]:
    nb = policy["net_benefit"]
    critical_hit = sum(1 for s in blast["healthy_affected"] if services.get(s, {}).get("critical"))
    added = forecast_s * critical_hit
    removed = severity_now
    ok = forecast_s <= nb["max_added_harm_seconds"] and (added == 0 or removed >= nb["min_benefit_ratio"] * added)
    return ok, {"added": added, "removed": removed, "forecast_s": forecast_s, "critical_hit": critical_hit}
