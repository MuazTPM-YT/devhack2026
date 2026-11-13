from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from fastapi import FastAPI

from gateway.audit import AuditLog, EventBus, verify
from gateway.events import create_events_router
from gateway.receipts import ReceiptStore, build_card, create_receipts_router
from schemas.models import Receipt


def test_chain_tamper_and_concurrent_append(tmp_path):
    path = tmp_path / "audit.jsonl"
    audit = AuditLog(path)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda i: audit.append({"type": "blocked", "payload": {"i": i}}), range(20)))
    assert len(verify(path)) == 20
    path.write_text(path.read_text().replace('"i": 0', '"i": 9', 1))
    with pytest.raises(ValueError, match="seq 1"):
        verify(path)
    with pytest.raises(ValueError):
        AuditLog(path)


async def test_events_replay_and_overflow(tmp_path):
    bus = EventBus(AuditLog(tmp_path / "audit.jsonl"), queue_size=1)
    await bus.publish({"type": "incident_opened"})
    subscription = bus.subscribe(0)
    assert (await anext(subscription))["seq"] == 1
    await bus.publish({"type": "blocked"})
    await bus.publish({"type": "escalated"})
    with pytest.raises(StopAsyncIteration):
        await anext(subscription)
    assert not bus.subscribers
    replay = bus.subscribe(1)
    assert (await anext(replay))["seq"] == 2
    await replay.aclose()


async def test_publish_does_not_emit_if_disk_fails(tmp_path, monkeypatch):
    bus = EventBus(AuditLog(tmp_path / "audit.jsonl"))
    def fail(event):
        raise OSError("disk full")
    monkeypatch.setattr(bus.audit, "append", fail)
    with pytest.raises(OSError):
        await bus.publish({"type": "blocked"})
    assert bus.audit.records == []


async def test_routes_and_receipt_card(tmp_path):
    app = FastAPI()
    bus = EventBus(AuditLog(tmp_path / "audit.jsonl"))
    store = ReceiptStore(tmp_path / "oncall.db")
    app.include_router(create_events_router(bus))
    app.include_router(create_receipts_router(store))
    receipt = Receipt(incident_id="inc-1", tool="rollback_deploy", target="payment",
                      diff={"image": "old"}, inverse={"image": "good"}, evidence_ids=["journal:41"])
    receipt_id = store.save(receipt)
    assert "FIXED" not in build_card(receipt, receipt_id).text
    receipt.outcome, receipt.prediction_held, receipt.harm_clean = "success", True, True
    assert build_card(receipt, receipt_id).status == "FIXED"
    assert len(build_card(receipt, receipt_id).text.splitlines()) == 5
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get(f"/receipts/{receipt_id}")).status_code == 200
        assert (await client.get("/receipts/999")).status_code == 404
        assert (await client.post("/events/publish", json={"type": "blocked"})).status_code == 200
        assert (await client.get("/events", headers={"Last-Event-ID": "bad"})).status_code == 400


async def test_disconnect_cleans_subscription(tmp_path):
    bus = EventBus(AuditLog(tmp_path / "audit.jsonl"))
    await bus.publish({"type": "blocked"})
    subscription = bus.subscribe(0)
    await anext(subscription)
    await subscription.aclose()
    assert not bus.subscribers


def test_card_stays_five_lines_with_multiline_fields():
    receipt = Receipt(incident_id="i", tool="rollback_deploy", target="payment\nextra",
                      diff={}, inverse={"image": "old"}, evidence_ids=["journal:41\nextra"])
    assert len(build_card(receipt, 1).text.splitlines()) == 5


@pytest.mark.parametrize("decision,status", [
    ("awaiting_approval", "NEEDS APPROVAL"), ("escalated", "NEEDS YOU"),
    ("handed_off", "HANDED OFF"), ("refused", "NO ACTION"),
])
def test_incident_card_variants(bundle, decision, status):
    from gateway.receipts import build_incident_card
    from schemas.models import GatewayDecision
    card = build_incident_card(bundle.incident, decision=GatewayDecision(decision=decision))
    assert card.status == status
    assert len(card.text.splitlines()) == 5
    assert "the agent made no change" in card.text


def test_major_mitigation_card(bundle):
    from gateway.receipts import build_incident_card
    bundle.incident.major = True
    card = build_incident_card(bundle.incident, mitigated=True)
    assert card.status == "MAJOR INCIDENT: MITIGATED, NOT FIXED"
    assert len(card.text.splitlines()) == 5


@pytest.mark.parametrize("line", ["null", "42", "[]", "{bad json"])
def test_corrupt_record_reports_sequence(tmp_path, line):
    path = tmp_path / "audit.jsonl"
    path.write_text(line + "\n")
    with pytest.raises(ValueError, match="seq 1"):
        verify(path)


def test_audit_cli_runs_from_repository_root(tmp_path):
    import subprocess
    import sys
    path = tmp_path / "audit.jsonl"
    AuditLog(path).append({"type": "blocked"})
    result = subprocess.run([sys.executable, "scripts/verify_audit.py", str(path)],
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert "1 records" in result.stdout
