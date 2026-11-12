# freshness, right before the trust gate (IMPLEMENTATION.md §6.4.5). Pure: caller fetches health, rule, live object.
from observer.journal import still_live


# -> ("ok" | "refused" | "awaiting_approval", reason)
def check(health: dict, culprit: str, rule_then: tuple, rule_now: tuple, entry: dict | None,
          live_obj: dict | None) -> tuple[str, str | None]:
    if not health["services"].get(culprit, {}).get("unhealthy"):
        return "refused", "problem no longer present"
    if rule_now != rule_then:
        return "awaiting_approval", f"rule result changed: {rule_then} -> {rule_now}"
    if entry is not None and (live_obj is None or not still_live(entry, live_obj)):
        return "awaiting_approval", f"journal entry {entry.get('id')} no longer matches the live object"
    return "ok", None
