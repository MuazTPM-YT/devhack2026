import asyncio
import json

import httpx
import pytest

from brain.coordinator import QUEUE_GRACE_S, Coordinator
from gateway.audit import AuditLog, EventBus
from schemas import config, migrations
from schemas.db import connect
from schemas.orchestration import OrchestrationPolicy, SignalBatch, SignalEpisode
from schemas.workspace import Workspace

from tests.test_brain import World, diagnosis_json, make

# the policy's max age (3 fixes per incident raised it), not a copy that goes stale
MAX_AGE = config.load("policy")["detection"]["incident_max_age_seconds"]


class Clock:
    def __init__(self, t: float = 1000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t


class BusWorld(World):
    def __init__(self):
        super().__init__()
        self.bus_down = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/events/publish" and self.bus_down:
            self.requests.append(request)
            return httpx.Response(503)
        return super().__call__(request)


def ep(service, rev=1, recovered=None, breach=960.0, eid=None):
    return SignalEpisode(episode_id=eid or f"episode-{service}", service=service, symptom="errors",
                         first_breach_at=breach, sustained_at=breach + 30, last_observed_at=breach + 30,
                         recovered_at=recovered, source_revision=rev)


def batch(*episodes, delivery="delivery-1"):
    return SignalBatch(delivery_id=delivery, source_revision=max(e.source_revision for e in episodes),
                       observed_at=1000.0, episodes=list(episodes))


def coordinated(world, tmp_path, clock, responses=4, ws=None, owner="brain-a", **policy):
    brain = make(world, [diagnosis_json()] * responses, tmp_path)
    brain.clock = clock
    if ws is None:
        wconn = connect(str(tmp_path / "ws.db"), shared=True)
        migrations.migrate(wconn)
        ws = Workspace(wconn, OrchestrationPolicy(mode="coordinated", **policy), clock=clock)
    # gateway and workspace share one database in production; mirror that for incident rows
    brain.conn = ws.conn
    brain.orch = ws.policy
    brain.coordinator = Coordinator(brain, ws, ws.policy, clock=clock, owner=owner)
    return brain


async def settle(coord):
    while any(not t.done() for t in coord.commanders.values()):
        await asyncio.gather(*coord.commanders.values(), return_exceptions=True)


def published(world, kind=None):
    return [e for e in world.published if kind is None or e["type"] == kind]


async def test_two_unrelated_faults_get_separate_owners_and_fixes(tmp_path):
    world, clock = World(), Clock()
    brain = coordinated(world, tmp_path, clock)
    coord = brain.coordinator
    await coord.start()
    await coord.on_signals(batch(ep("payment"), ep("product-catalog")))
    incidents = coord.ws.unfinished()
    assert len(incidents) == 2
    await settle(coord)
    assert {a.incident_id for a in brain.submitted} == set(incidents)
    assert [coord.ws.workspace(i)["phase"] for i in incidents] == ["awaiting_gateway"] * 2
    opened = published(world, "incident_opened")
    assert sorted(e["incident_id"] for e in opened) == sorted(incidents)
    assert all(e.get("event_id", "").startswith("evt-") for e in world.published)
    links = coord.ws.links(incidents[0])
    assert [lk.reason for lk in links] == ["unknown_topology"]  # product-catalog has no known edges
    scopes = {e["incident_id"]: e["payload"] for e in published(world, "incident_scope_changed")}
    assert all(p["related"][0]["reason"] == "unknown_topology" for p in scopes.values())
    assert {p["related"][0]["incident_id"] for p in scopes.values()} == set(incidents)


async def test_shared_cause_gets_one_commander(tmp_path):
    world, clock = World(), Clock()
    brain = coordinated(world, tmp_path, clock)
    coord = brain.coordinator
    await coord.start()
    await coord.on_signals(batch(ep("checkout", breach=965.0), ep("payment")))
    [iid] = coord.ws.unfinished()
    assert [m.service for m in coord.ws.memberships(iid)] == ["checkout", "payment"]
    assert coord.ws.workspace(iid)["cause_key"] == "dependency:payment"
    await settle(coord)
    assert len(brain.submitted) == 1


async def test_later_victim_of_same_cause_joins_without_new_scope(tmp_path):
    world, clock = World(), Clock()
    brain = coordinated(world, tmp_path, clock, max_active_commanders=1)
    coord = brain.coordinator
    await coord.start()
    await coord.on_signals(batch(ep("payment"), delivery="delivery-1"))
    [iid] = coord.ws.unfinished()
    await settle(coord)
    await coord.on_signals(batch(ep("checkout", breach=965.0), delivery="delivery-2"))
    assert coord.ws.unfinished() == [iid] and coord.ws.workspace(iid)["scope_revision"] == 0
    assert [e["payload"]["unhealthy"] for e in published(world, "alerts_grouped")] == [["checkout", "payment"]]


async def test_terminal_closes_only_its_incident_and_suppresses_its_episode(tmp_path):
    world, clock = World(), Clock()
    brain = coordinated(world, tmp_path, clock)
    coord = brain.coordinator
    await coord.start()
    await coord.on_signals(batch(ep("payment"), ep("product-catalog")))
    await settle(coord)
    owner = coord.ws.owner_of("episode-payment")
    other = coord.ws.owner_of("episode-product-catalog")
    coord.on_terminal(owner)
    assert coord.ws.workspace(owner)["phase"] == "terminal"
    assert coord.ws.workspace(other)["phase"] == "awaiting_gateway"
    assert coord.ws.owner_of("episode-product-catalog") == other
    # still sick, same spell: no second incident
    await coord.on_signals(batch(ep("payment", rev=2), delivery="delivery-2"))
    assert coord.ws.unfinished() == [other]
    # healthy, then sick again: a new spell is a new incident
    await coord.on_signals(batch(ep("payment", rev=3, recovered=1100.0), delivery="delivery-3"))
    await coord.on_signals(batch(ep("payment", rev=4, eid="episode-payment-2"), delivery="delivery-4"))
    assert len(coord.ws.unfinished()) == 2


async def test_restart_mid_diagnosis_resumes_inside_original_deadline(tmp_path):
    world, clock = World(), Clock()
    brain = coordinated(world, tmp_path, clock)
    coord = brain.coordinator
    await coord.start()
    stuck = asyncio.Event()

    async def hang(incident, **kw):
        stuck.set()
        await asyncio.Event().wait()

    real = brain.handle_safely
    brain.handle_safely = hang
    await coord.on_signals(batch(ep("payment")))
    [iid] = coord.ws.unfinished()
    await stuck.wait()
    deadline = coord.ws.workspace(iid)["deadline_at"]
    assert coord.ws.workspace(iid)["phase"] == "investigating" and deadline == 1150.0
    for task in coord.commanders.values():  # the process dies
        task.cancel()
    await settle(coord)

    clock.t += 40  # old lease expired
    again = coordinated(world, tmp_path, clock, ws=coord.ws, owner="brain-b")
    again.handle_safely = real.__func__.__get__(again)  # fresh process, real diagnosis
    await again.coordinator.start()
    await settle(again.coordinator)
    w = again.coordinator.ws.workspace(iid)
    assert w["deadline_at"] == deadline and w["phase"] == "awaiting_gateway"
    assert [a.incident_id for a in again.submitted] == [iid]


async def test_restart_never_resubmits_when_gateway_already_has_it(tmp_path):
    world, clock = World(), Clock()
    brain = coordinated(world, tmp_path, clock)
    coord = brain.coordinator
    await coord.start()
    brain.handle_safely = lambda incident, **kw: asyncio.Event().wait()
    await coord.on_signals(batch(ep("payment")))
    [iid] = coord.ws.unfinished()
    await asyncio.sleep(0)
    for task in coord.commanders.values():
        task.cancel()
    await settle(coord)
    coord.ws.conn.execute("INSERT INTO approvals (id, incident_id, state) VALUES ('a1', ?, 'pending')", (iid,))
    coord.ws.conn.commit()
    clock.t += 40
    again = coordinated(world, tmp_path, clock, ws=coord.ws, owner="brain-b")
    await again.coordinator.start()
    await settle(again.coordinator)
    assert again.submitted == [] and again.coordinator.ws.workspace(iid)["phase"] == "awaiting_gateway"


async def test_restart_after_hand_over_without_gateway_trace_escalates(tmp_path):
    world, clock = World(), Clock()
    brain = coordinated(world, tmp_path, clock)
    coord = brain.coordinator
    await coord.start()
    await coord.on_signals(batch(ep("payment")))
    [iid] = coord.ws.unfinished()
    await settle(coord)  # phase awaiting_gateway; the fake gateway kept no approval row
    clock.t += 40
    again = coordinated(world, tmp_path, clock, ws=coord.ws, owner="brain-b")
    await again.coordinator.start()
    w = again.coordinator.ws.workspace(iid)
    assert (w["phase"], w["last_error"]) == ("needs_human", "restart")
    assert published(world, "escalated")[-1]["incident_id"] == iid


async def test_second_coordinator_refuses_to_start(tmp_path):
    world, clock = World(), Clock()
    first = coordinated(world, tmp_path, clock)
    await first.coordinator.start()
    second = coordinated(world, tmp_path, clock, ws=first.coordinator.ws, owner="brain-b")
    with pytest.raises(RuntimeError, match="lease"):
        await second.coordinator.start(wait_s=0.05, poll_s=0.01)


# live: a restarted brain died on start because the stopped one still held the lease
async def test_clean_stop_lets_the_next_brain_start_at_once(tmp_path):
    world, clock = World(), Clock()
    first = coordinated(world, tmp_path, clock)
    await first.coordinator.start()
    first.coordinator.stop()
    second = coordinated(world, tmp_path, clock, ws=first.coordinator.ws, owner="brain-b")
    await second.coordinator.start(wait_s=0, poll_s=0.01)
    assert second.coordinator.epoch == 2


async def test_restart_after_crash_waits_for_the_lease_to_lapse(tmp_path):
    world, clock = World(), Clock()
    first = coordinated(world, tmp_path, clock)
    await first.coordinator.start()  # crashes: never stops
    second = coordinated(world, tmp_path, clock, ws=first.coordinator.ws, owner="brain-b")

    async def lapse():
        await asyncio.sleep(0.03)
        clock.t += 31

    await asyncio.gather(second.coordinator.start(wait_s=1, poll_s=0.01), lapse())
    assert second.coordinator.epoch == 2


async def test_outbox_survives_bus_outage_and_delivers_once(tmp_path):
    world, clock = BusWorld(), Clock()
    brain = coordinated(world, tmp_path, clock)
    coord = brain.coordinator
    await coord.start()
    world.bus_down = True
    await brain.publish("incident_opened", None, {"note": "held"})
    assert coord.ws.pending_count("gateway") == 1 and world.published == []
    world.bus_down = False
    clock.t += 2
    await coord.flush()
    await coord.flush()
    assert [e["payload"] for e in world.published] == [{"note": "held"}]
    assert coord.ws.pending_count("gateway") == 0


async def test_max_age_escalates_once(tmp_path):
    world, clock = World(), Clock()
    brain = coordinated(world, tmp_path, clock)
    coord = brain.coordinator
    await coord.start()
    brain.handle_safely = lambda incident, **kw: asyncio.Event().wait()
    await coord.on_signals(batch(ep("payment")))
    [iid] = coord.ws.unfinished()
    await asyncio.sleep(0)  # commander picks it up
    assert coord.ws.workspace(iid)["phase"] == "investigating"
    clock.t += MAX_AGE
    await coord.expire()
    await coord.expire()
    assert [e["incident_id"] for e in published(world, "escalated")] == [iid]
    assert coord.ws.workspace(iid)["last_error"] == "max_age"
    for task in coord.commanders.values():
        task.cancel()
    await settle(coord)


async def test_queued_incident_escalates_before_max_age(tmp_path):
    world, clock = World(), Clock()
    brain = coordinated(world, tmp_path, clock, max_active_commanders=1)
    coord = brain.coordinator
    await coord.start()
    brain.handle_safely = lambda incident, **kw: asyncio.Event().wait()
    await coord.on_signals(batch(ep("payment"), ep("product-catalog")))
    phases = {i: coord.ws.workspace(i)["phase"] for i in coord.ws.unfinished()}
    waiting = next(i for i, p in phases.items() if p == "queued")
    clock.t += MAX_AGE - QUEUE_GRACE_S
    await coord.expire()
    assert coord.ws.workspace(waiting)["last_error"] == "queue_wait"
    for task in coord.commanders.values():
        task.cancel()
    await settle(coord)


async def test_scope_change_before_hand_over_replans_without_sending_stale_fix(tmp_path):
    world, clock = World(), Clock()
    brain = coordinated(world, tmp_path, clock)
    coord = brain.coordinator
    await coord.start()
    real, calls = brain.handle, []

    async def growing(incident, **kw):
        calls.append(incident.unhealthy)
        if len(calls) == 1:  # a victim joins while the first diagnosis runs
            with coord.ws.tx() as c:
                coord.ws.bump(c, incident.id, "scope")
        return await real(incident, **kw)

    brain.handle = growing
    await coord.on_signals(batch(ep("payment")))
    await settle(coord)
    assert len(calls) == 2 and len(brain.submitted) == 1


async def test_event_id_redelivery_appends_once_even_after_restart(tmp_path):
    path = tmp_path / "audit.jsonl"
    bus = EventBus(AuditLog(path))
    event = {"type": "incident_opened", "incident_id": "inc-1", "payload": {}, "event_id": "evt-1"}
    first = await bus.publish(event)
    again = await bus.publish(event)
    assert again == first and len(bus.audit.records) == 1
    restarted = EventBus(AuditLog(path))
    assert await restarted.publish(event) == first and len(restarted.audit.records) == 1
    plain = await restarted.publish({"type": "incident_opened", "incident_id": "inc-1", "payload": {}})
    assert plain["seq"] == 2 and "event_id" not in plain["event"]
    assert json.loads(path.read_text().splitlines()[0])["event"]["event_id"] == "evt-1"


async def test_gateway_progress_moves_the_phase(tmp_path):
    world, clock = World(), Clock()
    brain = coordinated(world, tmp_path, clock)
    coord = brain.coordinator
    await coord.start()
    await coord.on_signals(batch(ep("payment")))
    [iid] = coord.ws.unfinished()
    await settle(coord)
    assert coord.ws.workspace(iid)["phase"] == "awaiting_gateway"
    coord.on_intent(iid, "verifying")
    assert coord.ws.workspace(iid)["phase"] == "monitoring"
    coord.on_terminal(iid)
    coord.on_intent(iid, "awaiting_approval")  # late event after the end changes nothing
    assert coord.ws.workspace(iid)["phase"] == "terminal"


# live (phase D): checkout joined as a victim of the same cause mid-diagnosis, the right answer was thrown
# away and the out-of-budget rerun fell back to the decoy fix. Same cause = nothing to replan
async def test_victim_of_same_cause_joining_mid_diagnosis_does_not_replan(tmp_path):
    world, clock = World(), Clock()
    brain = coordinated(world, tmp_path, clock)
    coord = brain.coordinator
    await coord.start()
    real, calls = brain.handle, []

    async def joined_meanwhile(incident, **kw):
        calls.append(incident.unhealthy)
        if len(calls) == 1:
            await coord.on_signals(batch(ep("checkout", breach=965.0), delivery="delivery-2"))
        return await real(incident, **kw)

    brain.handle = joined_meanwhile
    await coord.on_signals(batch(ep("payment")))
    [iid] = coord.ws.unfinished()
    await settle(coord)
    assert len(calls) == 1 and len(brain.submitted) == 1
    assert [m.service for m in coord.ws.memberships(iid)] == ["checkout", "payment"]
