# service call graph from Jaeger dependencies (IMPLEMENTATION.md §6.3.1), cached 60 s
import time
from collections.abc import Callable

import httpx


class DependencyGraph:
    def __init__(self, http: httpx.AsyncClient, jaeger_url: str, ttl_s: float = 60,
                 clock: Callable[[], float] = time.time):
        self.http, self.jaeger_url, self.ttl_s, self.clock = http, jaeger_url, ttl_s, clock
        self.edges: list[tuple[str, str, float]] = []
        self.fetched_at: float | None = None

    # VERIFY on A's cluster: internal Jaeger UI API, links are {parent, child, callCount}
    async def get(self, lookback_s: float = 3600) -> list[tuple[str, str, float]]:
        now = self.clock()
        if self.fetched_at is not None and now - self.fetched_at < self.ttl_s:
            return self.edges
        r = await self.http.get(f"{self.jaeger_url}/api/dependencies",
                                params={"endTs": int(now * 1000), "lookback": int(lookback_s * 1000)}, timeout=10)
        r.raise_for_status()
        self.edges = [(d["parent"], d["child"], float(d.get("callCount", 0))) for d in r.json().get("data") or []
                      if d["parent"] != d["child"]]
        self.fetched_at = now
        return self.edges


# everything that calls svc, directly or not (who breaks if svc does)
def upstream(edges: list[tuple[str, str, float]], svc: str) -> set[str]:
    return downstream([(callee, caller, n) for caller, callee, n in edges], svc)


# everything svc calls, directly or not (its dependencies)
def downstream(edges: list[tuple[str, str, float]], svc: str) -> set[str]:
    out: set[str] = set()
    todo = [svc]
    while todo:
        cur = todo.pop()
        for caller, callee, _ in edges:
            if caller == cur and callee not in out and callee != svc:
                out.add(callee)
                todo.append(callee)
    return out
