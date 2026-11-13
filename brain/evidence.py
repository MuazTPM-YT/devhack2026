# shared read cache for agent tools: one upstream fetch serves every incident that asks within the
# freshness window; each fetch is kept as an immutable, redacted evidence snapshot. A miss fetches, never
# spawns an agent. Hits are served from memory (raw), so tool parsing is the same as without a cache.
import asyncio
import json
import logging
import math
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

from brain.redact import redact, redact_value
from schemas.orchestration import fingerprint
from schemas.workspace import Workspace

log = logging.getLogger("brain.evidence")

# seconds a read stays reusable (handoff §6.2); logs/traces arrive late, so recent windows stay short
TTL_S: dict[str, float] = {"health": 5, "pods": 5, "events": 5, "logs": 5, "usage": 5, "traces": 5,
                           "journal": 30, "metrics": 30, "other": 5}
RANGE_BUCKET_S = 30
MEM_PRUNE_AT = 256


@dataclass
class CacheRead:
    key: str
    kind: str
    value: Any
    snapshot_id: str
    source: Literal["fetch", "cache", "inflight"]
    age_s: float

    @property
    def cached(self) -> bool:
        return self.source != "fetch"


@dataclass
class _Entry:
    snapshot_id: str
    fetched_at: float
    valid_until: float
    value: Any


def kind_of(url: str) -> str:
    for part, kind in (("/health/now", "health"), ("/journal", "journal"), ("/api/v1/query_range", "metrics"),
                       ("/api/traces", "traces")):
        if part in url:
            return kind
    return "other"


def http_key(url: str, params: dict[str, Any]) -> str:
    return f"http:{url}?{json.dumps(params, sort_keys=True, default=str)}"


# a range query ending "now" never repeats; snap its end down so incidents seconds apart share it
def bucket_range(params: dict[str, Any]) -> dict[str, Any]:
    if "start" not in params or "end" not in params:
        return params
    end = math.floor(float(params["end"]) / RANGE_BUCKET_S) * RANGE_BUCKET_S
    return {**params, "start": end - (float(params["end"]) - float(params["start"])), "end": end}


# mutable observations (query:...) get the snapshot they came from, so one id never means two values;
# journal:N, trace:, event:, log: ids already name one immutable thing
def pin(evidence_id: str, snapshot_ids: list[str]) -> str:
    if not evidence_id.startswith("query:") or not snapshot_ids or "@" in evidence_id:
        return evidence_id
    return f"{evidence_id}@{fingerprint(sorted(snapshot_ids))[:8]}"


def base_id(evidence_id: str) -> str:
    return evidence_id.split("@", 1)[0]


class EvidenceCache:
    def __init__(self, workspace: Workspace | None, clock: Callable[[], float] = time.time):
        self.workspace, self.clock = workspace, clock
        self.mem: dict[str, _Entry] = {}
        self.inflight: dict[str, asyncio.Future] = {}
        self.fetches: set[asyncio.Task] = set()  # strong refs: a fetch outlives a cancelled first caller
        self.upstream_fetches = 0

    async def read(self, key: str, kind: str, fetch: Callable[[], Awaitable[Any]]) -> CacheRead:
        now = self.clock()
        entry = self.mem.get(key)
        if entry is not None and entry.valid_until > now:
            return CacheRead(key, kind, entry.value, entry.snapshot_id, "cache", max(0.0, now - entry.fetched_at))
        future = self.inflight.get(key)
        if future is not None:
            value, snapshot_id = await asyncio.shield(future)
            return CacheRead(key, kind, value, snapshot_id, "inflight", 0.0)
        future = asyncio.get_running_loop().create_future()
        future.add_done_callback(lambda f: f.cancelled() or f.exception())  # no "never retrieved" noise
        self.inflight[key] = future
        task = asyncio.create_task(self._fetch(key, kind, fetch, future))
        self.fetches.add(task)
        task.add_done_callback(self.fetches.discard)
        value, snapshot_id = await asyncio.shield(future)
        return CacheRead(key, kind, value, snapshot_id, "fetch", 0.0)

    async def _fetch(self, key: str, kind: str, fetch: Callable[[], Awaitable[Any]], future: asyncio.Future) -> None:
        try:
            value = await fetch()
            self.upstream_fetches += 1
            fetched = self.clock()
            stored = redact_value(value)
            snapshot_id = "snap:" + fingerprint({"key": key, "at": fetched, "hash": fingerprint(stored)})[:16]
            valid_until = fetched + TTL_S.get(kind, TTL_S["other"])
            if self.workspace is not None:
                try:
                    self.workspace.put_snapshot(snapshot_id, redact(key)[:500], kind, fetched, valid_until, stored)
                except Exception as e:  # history is best effort; the read itself still succeeds
                    log.warning("evidence snapshot not stored: %s", type(e).__name__)
            self.mem[key] = _Entry(snapshot_id, fetched, valid_until, value)
            self._prune(fetched)
            future.set_result((value, snapshot_id))
        except BaseException as e:  # failures are never cached; every waiter hears the error
            if not future.done():
                future.set_exception(e if isinstance(e, Exception) else RuntimeError("fetch cancelled"))
            if not isinstance(e, Exception):
                raise
        finally:
            self.inflight.pop(key, None)

    def _prune(self, now: float) -> None:
        if len(self.mem) > MEM_PRUNE_AT:
            for k in [k for k, e in self.mem.items() if e.valid_until <= now]:
                del self.mem[k]
