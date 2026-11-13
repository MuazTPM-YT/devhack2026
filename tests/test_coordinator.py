import json

import pytest
from fastapi.testclient import TestClient

from brain.coordinator import Coordinator, ModeMismatch
from brain.main import create_app
from schemas import auth, migrations
from schemas.db import connect
from schemas.orchestration import OrchestrationPolicy, SignalBatch, SignalEpisode
from schemas.workspace import Workspace
from tests.test_brain import World, make


def ep(service, rev=1, recovered=None, breach=960.0):
    return SignalEpisode(episode_id=f"episode-{service}", service=service, symptom="errors", first_breach_at=breach,
                         sustained_at=breach + 30, last_observed_at=breach + 30, recovered_at=recovered,
                         source_revision=rev)


def batch(*episodes, delivery="delivery-1", shadow=True):
    return SignalBatch(delivery_id=delivery, source_revision=max(e.source_revision for e in episodes),
                       observed_at=1000.0, shadow=shadow, episodes=list(episodes))


def shadow_brain(world, tmp_path, mode="shadow"):
    brain = make(world, [], tmp_path)
    wconn = connect(str(tmp_path / "ws.db"), shared=True)
    migrations.migrate(wconn)
    brain.orch = OrchestrationPolicy(mode=mode)
    brain.coordinator = Coordinator(brain, Workspace(wconn, brain.orch, clock=lambda: 1000.0), brain.orch,
                                    clock=lambda: 1000.0)
    return brain


async def test_shadow_groups_victim_with_traced_root_and_writes_nothing_else(tmp_path):
    world = World()
    brain = shadow_brain(world, tmp_path)
    coord = brain.coordinator
    ack = await coord.on_signals(batch(ep("checkout", breach=965.0), ep("payment")))
    assert ack.accepted == 2 and not ack.duplicate
    [row] = coord.ws.rows("SELECT * FROM shadow_decisions")
    decision = json.loads(row["decision_json"])
    assert [g["services"] for g in decision["groups"]] == [["checkout", "payment"]]
    assert decision["groups"][0]["cause"] == "dependency:payment"
    assert row["legacy_incident_id"] == "inc-1"
    # shadow: no workspace incidents, no gateway or model traffic, no events
    assert coord.ws.rows("SELECT * FROM orchestration_workspaces") == []
    assert brain.submitted == [] and world.published == []
    assert all(r.url.path in ("/journal",) or r.url.path.startswith("/jaeger") for r in world.requests)


async def test_redelivery_returns_stored_ack_and_decides_once(tmp_path):
    brain = shadow_brain(World(), tmp_path)
    coord = brain.coordinator
    first = await coord.on_signals(batch(ep("payment")))
    again = await coord.on_signals(batch(ep("payment")))
    assert again.duplicate and again.accepted == first.accepted
    assert len(coord.ws.rows("SELECT * FROM shadow_decisions")) == 1


async def test_later_victim_joins_shadow_group_and_recovery_closes_it(tmp_path):
    brain = shadow_brain(World(), tmp_path)
    coord = brain.coordinator
    await coord.on_signals(batch(ep("payment"), delivery="delivery-1"))
    await coord.on_signals(batch(ep("checkout", breach=965.0), delivery="delivery-2"))
    assert list(coord.shadow_groups) == ["shadow-1"]
    assert coord.shadow_groups["shadow-1"]["episodes"] == {"episode-payment", "episode-checkout"}
    await coord.on_signals(batch(ep("payment", 2, recovered=1100.0), ep("checkout", 2, recovered=1100.0),
                                 delivery="delivery-3"))
    assert coord.shadow_groups == {}


async def test_mode_mismatch_is_refused(tmp_path):
    brain = shadow_brain(World(), tmp_path)
    with pytest.raises(ModeMismatch):
        await brain.coordinator.on_signals(batch(ep("payment"), shadow=False))


def test_signals_route_refused_when_disabled(tmp_path):
    brain = make(World(), [], tmp_path)
    with TestClient(create_app(brain)) as client:
        r = client.post("/signals", headers=auth.headers(), json=batch(ep("payment")).model_dump(mode="json"))
    assert r.status_code == 409 and "disabled" in r.json()["detail"]


def test_signals_route_needs_token(tmp_path):
    brain = shadow_brain(World(), tmp_path)
    with TestClient(create_app(brain)) as client:
        assert client.post("/signals", json=batch(ep("payment")).model_dump(mode="json")).status_code == 401


def test_signals_route_accepts_in_shadow(tmp_path):
    brain = shadow_brain(World(), tmp_path)
    with TestClient(create_app(brain)) as client:
        r = client.post("/signals", headers=auth.headers(), json=batch(ep("payment")).model_dump(mode="json"))
    assert r.status_code == 200 and r.json()["accepted"] == 1


def test_legacy_incidents_refused_when_coordinated(tmp_path):
    brain = shadow_brain(World(), tmp_path, mode="coordinated")
    with TestClient(create_app(brain)) as client:
        r = client.post("/incidents", headers=auth.headers(), json={
            "id": "inc-2", "opened_at": 990, "onset_at": 960, "unhealthy": ["payment"], "severity": 3})
    assert r.status_code == 409

