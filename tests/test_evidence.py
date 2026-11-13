import asyncio
import json

import pytest

from brain.evidence import EvidenceCache, base_id, bucket_range, pin
from brain.llm import check
from schemas import migrations
from schemas.db import connect
from schemas.models import Cause, Diagnosis
from schemas.orchestration import OrchestrationPolicy
from schemas.workspace import Workspace
from tests.test_agent_tools import FakeKube, Upstreams, make_box


class Clock:
    def __init__(self, t: float = 1000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t


def workspace(tmp_path, clock):
    conn = connect(str(tmp_path / "e.db"), shared=True)
    migrations.migrate(conn)
    return Workspace(conn, OrchestrationPolicy(), clock=clock)


async def test_fresh_read_is_reused_then_expires(tmp_path):
    clock = Clock()
    cache = EvidenceCache(workspace(tmp_path, clock), clock)
    calls = []

    async def fetch():
        calls.append(1)
        return {"n": len(calls)}

    first = await cache.read("k", "health", fetch)
    again = await cache.read("k", "health", fetch)
    assert (first.source, again.source) == ("fetch", "cache") and again.value == {"n": 1}
    assert again.snapshot_id == first.snapshot_id
    clock.t += 5  # health ttl 5 s
    later = await cache.read("k", "health", fetch)
    assert later.source == "fetch" and later.value == {"n": 2} and later.snapshot_id != first.snapshot_id
    assert cache.upstream_fetches == 2


async def test_concurrent_reads_share_one_fetch():
    gate = asyncio.Event()
    calls = []

    async def fetch():
        calls.append(1)
        await gate.wait()
        return [1, 2]

    cache = EvidenceCache(None, Clock())
    a = asyncio.create_task(cache.read("k", "pods", fetch))
    b = asyncio.create_task(cache.read("k", "pods", fetch))
    await asyncio.sleep(0)
    gate.set()
    ra, rb = await asyncio.gather(a, b)
    assert len(calls) == 1 and {ra.source, rb.source} == {"fetch", "inflight"} and ra.value == rb.value


async def test_cancelled_first_caller_does_not_kill_shared_fetch():
    gate = asyncio.Event()

    async def fetch():
        await gate.wait()
        return "ok"

    cache = EvidenceCache(None, Clock())
    first = asyncio.create_task(cache.read("k", "pods", fetch))
    await asyncio.sleep(0)
    second = asyncio.create_task(cache.read("k", "pods", fetch))
    await asyncio.sleep(0)
    first.cancel()
    gate.set()
    assert (await second).value == "ok"
    with pytest.raises(asyncio.CancelledError):
        await first


async def test_failures_are_not_cached():
    attempts = []

    async def fetch():
        attempts.append(1)
        if len(attempts) == 1:
            raise ConnectionError("down")
        return "up"

    cache = EvidenceCache(None, Clock())
    with pytest.raises(ConnectionError):
        await cache.read("k", "health", fetch)
    assert (await cache.read("k", "health", fetch)).value == "up"


async def test_snapshot_stored_redacted_but_served_raw(tmp_path):
    clock = Clock()
    ws = workspace(tmp_path, clock)
    cache = EvidenceCache(ws, clock)
    raw = {"env": [{"name": "DB_PASSWORD", "value": "hunter2"}]}

    async def fetch():
        return raw

    got = await cache.read("k", "pods", fetch)
    assert got.value is raw
    assert "hunter2" not in json.dumps(ws.snapshot_payload(got.snapshot_id))


def test_range_bucket_keeps_width():
    out = bucket_range({"query": "q", "start": 1000 - 900, "end": 1014, "step": 30})
    assert out["end"] == 990 and out["end"] - out["start"] == 914
    assert bucket_range({"since": 5}) == {"since": 5}


def test_pin_only_mutable_ids():
    assert pin("journal:41", ["snap:a"]) == "journal:41"
    pinned = pin("query:err_ratio:service=cart", ["snap:a"])
    assert pinned.startswith("query:err_ratio:service=cart@") and base_id(pinned) == "query:err_ratio:service=cart"
    assert pin(pinned, ["snap:b"]) == pinned
    assert pin("query:x", []) == "query:x"


def cached_box(tmp_path, clock, up=None, run_id="run-1"):
    box = make_box(up or Upstreams(), FakeKube())
    ws = workspace(tmp_path, clock)
    ws.conn.execute("INSERT INTO incidents (id, opened_at, onset_at, state) VALUES ('inc-1', 990, 960, 'open')")
    ws.conn.commit()
    box.cache, box.workspace, box.run_id = EvidenceCache(ws, clock), ws, run_id
    return box, ws


async def test_toolbox_pins_metric_ids_and_records_delivery(tmp_path):
    clock = Clock()
    box, ws = cached_box(tmp_path, clock)
    out = json.loads(await box.call("get_service_health", {}, box.health(None)))
    ids = out[1]["evidence_ids"]
    assert all("@" in i for i in ids) and set(ids) <= set(box.ledger)
    assert ws.delivered("run-1") == set(box.ledger)
    kind, payload = box.published[-1]
    assert kind == "tool_called" and payload["cached"] is False


async def test_second_incident_reuses_read_without_upstream_fetch(tmp_path):
    clock = Clock()
    up = Upstreams()
    box, ws = cached_box(tmp_path, clock, up)
    await box.call("get_metric_history", {}, box.history("payment", "err_ratio", 10, 30))
    other = make_box(up, FakeKube())
    other.cache, other.workspace, other.run_id = box.cache, ws, "run-2"
    other.now = box.now + 3  # seconds later, same 30 s bucket
    await other.call("get_metric_history", {}, other.history("payment", "err_ratio", 10, 30))
    assert len(up.queries) == 1
    kinds = [k for k, _ in other.published]
    assert kinds == ["tool_called", "evidence_reused"]
    assert other.published[0][1]["cached"] is True and other.published[1][1]["source"] == "cache"


async def test_kube_reads_go_through_cache(tmp_path):
    clock = Clock()
    box, _ = cached_box(tmp_path, clock)
    calls = []
    real = box.kube.pods

    def counting(service):
        calls.append(service)
        return real(service)

    box.kube.pods = counting
    await box.call("get_pods", {}, box.pods("payment"))
    await box.call("get_k8s_events", {}, box.events("payment", 5))
    assert calls == ["payment"]


async def test_delivered_journal_id_still_passes_check(tmp_path):
    clock = Clock()
    box, _ = cached_box(tmp_path, clock)
    await box.call("get_recent_changes", {}, box.changes(10, None))
    assert "journal:41" in box.ledger  # immutable id unchanged
    diag = Diagnosis(causes=[Cause(cause_class="recent_change", culprit="payment", evidence_ids=["journal:41"],
                                   explanation="env change on payment broke charges")], confidence=0.8)
    assert check(diag, box.bundle()) == diag


async def test_db_existence_alone_does_not_make_an_id_citable(tmp_path):
    clock = Clock()
    box, ws = cached_box(tmp_path, clock)
    await box.call("get_service_health", {}, box.health(None))
    fresh = make_box(Upstreams(), FakeKube())
    fresh.cache, fresh.workspace, fresh.run_id = box.cache, ws, "run-2"
    pinned = next(i for i in box.ledger if i.startswith("query:"))
    diag = Diagnosis(causes=[Cause(cause_class="recent_change", culprit="payment", evidence_ids=[pinned],
                                   explanation="payment errors jumped right after the change")], confidence=0.5)
    with pytest.raises(ValueError):
        check(diag, fresh.bundle())
