# major-incident analysis (IMPLEMENTATION.md §6.3.3): many services down together usually share one cause.
# ponytail: no "shared node" signal; the k3d cluster has one node, so every pod shares it and it tells us nothing.
from brain.graph import downstream


# >= min_services or >= min_fraction of all services first breached within within_seconds of each other
def is_major(unhealthy: list[str], first_breach: dict[str, float], total_services: int, policy: dict) -> bool:
    m = policy["major_incident"]
    times = sorted(first_breach[s] for s in unhealthy if s in first_breach)
    if not times:
        return False
    close = [t for t in times if t - times[0] <= m["within_seconds"]]
    return len(close) >= m["min_services"] or len(close) >= m["min_fraction"] * max(total_services, 1)


# the non-agent journal change closest before the earliest onset, inside the change window
def shared_change(journal: list[dict], onset: float, window_s: float) -> dict | None:
    hits = [j for j in journal if not j["by_agent"] and onset - window_s <= j["ts"] <= onset]
    return max(hits, key=lambda j: (j["ts"], j["id"]), default=None)


# ranked candidates: shared change, then shared dependencies (earliest to fail first)
def analyse(unhealthy: list[str], edges: list[tuple[str, str, float]], first_breach: dict[str, float],
            journal: list[dict], onset: float, window_s: float) -> list[dict]:
    ranked = []
    change = shared_change(journal, onset, window_s)
    if change:
        ranked.append({"kind": "shared_change", "target": change["object"].split("/", 1)[1],
                       "evidence_ids": [f"journal:{change['id']}"], "journal_entry": change["id"]})
    if unhealthy and edges:
        common = set.intersection(*({s, *downstream(edges, s)} for s in unhealthy))
        for dep in sorted(common, key=lambda s: (first_breach.get(s, float("inf")), s)):
            if not any(c["target"] == dep for c in ranked):
                ranked.append({"kind": "shared_dependency", "target": dep, "evidence_ids": [], "journal_entry": None})
    order = sorted((s for s in unhealthy if s in first_breach), key=lambda s: first_breach[s])
    for c in ranked:
        c["failure_order"] = order
    return ranked
