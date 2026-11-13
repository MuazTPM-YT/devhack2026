# freshness, right before the trust gate (IMPLEMENTATION.md §6.4.5). Pure: caller fetches health, rule, live object.
from observer.journal import still_live


# -> ("ok" | "refused" | "awaiting_approval", reason)
# a culprit with no readings (a data store emits no spans, a service scaled to 0 has no pods) proves
# nothing by looking fine; then its sick victims say whether the problem is still there
def check(health: dict, culprit: str, rule_then: tuple, rule_now: tuple, entry: dict | None,
          live_obj: dict | None, victims: list[str] | tuple = ()) -> tuple[str, str | None]:
    services = health["services"]
    c = services.get(culprit, {})
    measured = _measured(c)
    sick = c.get("unhealthy") or (not measured and any(services.get(v, {}).get("unhealthy") for v in victims))
    # metrics that stop arriving read as None, not as healthy: with nothing measured, a human decides
    if not sick and not measured and not any(_measured(services.get(v, {})) for v in victims):
        return "awaiting_approval", f"no health readings for {culprit}; cannot tell if the problem is still there"
    if not sick:
        return "refused", "problem no longer present"
    if rule_now != rule_then:
        return "awaiting_approval", f"rule result changed: {rule_then} -> {rule_now}"
    if entry is not None and (live_obj is None or not still_live(entry, live_obj)):
        return "awaiting_approval", f"journal entry {entry.get('id')} no longer matches the live object"
    return "ok", None


def _measured(readings: dict) -> bool:
    return readings.get("err_ratio") is not None or readings.get("p95_ms") is not None \
        or bool(readings.get("bad_pods"))
