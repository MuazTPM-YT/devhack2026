# culprit from Jaeger traces (IMPLEMENTATION.md §6.3.2). Traces are Jaeger query API JSON:
# {"spans": [{"spanID", "processID", "references", "tags"}], "processes": {pid: {"serviceName"}}}.
import json
from collections import Counter

import httpx

from brain.graph import downstream
from brain.rules import latest_change_before_onset


# ~20 recent error traces per service, last 5 min. VERIFY params/path on A's cluster (internal Jaeger API)
async def fetch_error_traces(http: httpx.AsyncClient, jaeger_url: str, services: list[str], now: float,
                             lookback_s: float = 300, limit: int = 20) -> list[dict]:
    traces: dict[str, dict] = {}
    for svc in services:
        r = await http.get(f"{jaeger_url}/api/traces", timeout=10, params={
            "service": svc, "tags": json.dumps({"error": "true"}), "limit": limit,
            "start": int((now - lookback_s) * 1e6), "end": int(now * 1e6)})
        r.raise_for_status()
        for t in r.json().get("data") or []:
            traces[t["traceID"]] = t
    return list(traces.values())


def is_error(span: dict) -> bool:
    return any((t["key"] == "error" and t.get("value") in (True, "true"))
               or (t["key"] == "otel.status_code" and t.get("value") == "ERROR") for t in span.get("tags", []))


# any erroring span anywhere under span_id (a clean span in between does not hide it)
def error_below(span_id: str, children: dict[str, list[str]], erroring: set[str]) -> bool:
    todo, seen = list(children.get(span_id, [])), set()
    while todo:
        cur = todo.pop()
        if cur in erroring:
            return True
        if cur not in seen:
            seen.add(cur)
            todo.extend(children.get(cur, []))
    return False


# error span with no erroring descendant failed on its own: its service is the origin
def from_traces(traces: list[dict]) -> tuple[str | None, list[str]]:
    origin: Counter[str] = Counter()
    failed: set[str] = set()
    for trace in traces:
        service = {pid: p["serviceName"] for pid, p in trace.get("processes", {}).items()}
        spans = trace.get("spans", [])
        children: dict[str, list[str]] = {}
        for s in spans:
            for r in s.get("references", []):
                if r.get("refType") == "CHILD_OF":
                    children.setdefault(r["spanID"], []).append(s["spanID"])
        errors = [s for s in spans if is_error(s)]
        erroring = {s["spanID"] for s in errors}
        for s in errors:
            failed.add(service[s["processID"]])
            if not error_below(s["spanID"], children, erroring):
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


# culprit had no change of its own: a recent change on something it depends on is the likelier root
# (scenario 5: valkey-cart scaled to 0, cart shows the errors)
def dependency_change(journal: list[dict], culprit: str, edges: list[tuple[str, str, float]], services: dict,
                      onset: float, window_s: float, flag_map: dict | None = None) -> dict | None:
    own = latest_change_before_onset(journal, culprit, onset, window_s, flag_map)
    if own and not own["by_agent"]:
        return None
    # ponytail: datastores emit no spans, so Jaeger has no edge to them; treat stateful services as dependencies
    deps = (downstream(edges, culprit) | {s for s, v in services.items() if v.get("kind") == "stateful"}) - {culprit}
    hits = [j for j in journal if not j["by_agent"] and j["kind"] != "restart"
            and onset - window_s <= j["ts"] <= onset and j["object"].startswith("deployment/")
            and j["object"].split("/", 1)[1] in deps]
    return max(hits, key=lambda j: (j["ts"], j["id"]), default=None)
