# culprit from Jaeger traces (IMPLEMENTATION.md §6.3.2). Traces are Jaeger query API JSON:
# {"spans": [{"spanID", "processID", "references", "tags"}], "processes": {pid: {"serviceName"}}}.
from collections import Counter


def is_error(span: dict) -> bool:
    return any((t["key"] == "error" and t.get("value") in (True, "true"))
               or (t["key"] == "otel.status_code" and t.get("value") == "ERROR") for t in span.get("tags", []))


# error span with no erroring child failed on its own: its service is the origin
def from_traces(traces: list[dict]) -> tuple[str | None, list[str]]:
    origin: Counter[str] = Counter()
    failed: set[str] = set()
    for trace in traces:
        service = {pid: p["serviceName"] for pid, p in trace.get("processes", {}).items()}
        errors = [s for s in trace.get("spans", []) if is_error(s)]
        error_parents = {r["spanID"] for s in errors for r in s.get("references", []) if r.get("refType") == "CHILD_OF"}
        for s in errors:
            failed.add(service[s["processID"]])
            if s["spanID"] not in error_parents:
                origin[service[s["processID"]]] += 1
    culprit = origin.most_common(1)[0][0] if origin else None
    return culprit, sorted(failed - {culprit})


# no traces (service fully down): deepest unhealthy service in the call graph, earliest onset breaks ties
def deepest_unhealthy(unhealthy: list[str], edges: list[tuple[str, str, float]],
                      first_breach: dict[str, float]) -> str | None:
    callers: dict[str, set[str]] = {}
    for caller, callee, _ in edges:
        callers.setdefault(callee, set()).add(caller)

    def depth(svc: str, seen: frozenset = frozenset()) -> int:
        up = callers.get(svc, set()) - seen
        return 1 + max((depth(c, seen | {svc}) for c in up), default=-1)

    if not unhealthy:
        return None
    return min(unhealthy, key=lambda s: (-depth(s), first_breach.get(s, float("inf")), s))


def find_culprit(traces: list[dict], unhealthy: list[str], edges: list[tuple[str, str, float]],
                 first_breach: dict[str, float]) -> tuple[str | None, list[str]]:
    culprit, victims = from_traces(traces)
    if culprit is not None:
        return culprit, victims
    culprit = deepest_unhealthy(unhealthy, edges, first_breach)
    return culprit, sorted(set(unhealthy) - {culprit})
