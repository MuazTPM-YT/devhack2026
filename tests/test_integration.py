import httpx
from fastapi import FastAPI

from brain.llm import DiagnosisService
from brain.providers.base import InferenceResponse
from gateway.audit import AuditLog, EventBus, verify
from gateway.events import create_events_router
from gateway.receipts import ReceiptStore, create_receipts_router
from schemas.models import Receipt


async def test_diagnosis_audit_and_receipt_round_trip(bundle, action, tmp_path):
    class Provider:
        name, model = "fake", "integration"
        async def generate(self, request):
            return InferenceResponse('{"causes": [], "confidence": 0.9}', self.name,
                                     self.model, {"prompt_tokens": 14})
    result = await DiagnosisService(Provider(), tmp_path / "cache").diagnose(bundle, "recent_change", action)
    assert result.action == action
    audit = AuditLog(tmp_path / "audit.jsonl")
    app = FastAPI()
    app.include_router(create_events_router(EventBus(audit)))
    store = ReceiptStore(tmp_path / "oncall.db")
    app.include_router(create_receipts_router(store))
    receipt_id = store.save(Receipt(incident_id=action.incident_id, tool=action.tool,
                                    target=action.target, diff={"image": "new -> old"},
                                    inverse={"image": "new"}, evidence_ids=action.evidence_ids,
                                    outcome="success", prediction_held=True, harm_clean=True))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        for event in result.events:
            response = await client.post("/events/publish", json=event)
            assert response.status_code == 200
        response = await client.get(f"/receipts/{receipt_id}")
        assert response.json()["card"]["status"] == "FIXED"
    assert verify(audit.path)[0]["event"]["payload"]["usage"]["prompt_tokens"] == 14


async def test_mountable_event_router_shares_in_process_and_http_bus(tmp_path):
    import pytest
    from gateway import events
    app = FastAPI()
    app.state.audit_path = tmp_path / "audit.jsonl"
    app.include_router(events.router)
    async with app.router.lifespan_context(app):
        first = await events.publish({"type": "blocked", "payload": {"source": "gateway"}})
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
            response = await client.post("/events/publish", json={"type": "blocked"})
        assert first["seq"] == 1
        assert response.json()["seq"] == 2
        assert response.json()["prev_hash"] == first["hash"]
    assert len(verify(app.state.audit_path)) == 2
    with pytest.raises(RuntimeError, match="not started"):
        await events.publish({"type": "blocked"})
    async with app.router.lifespan_context(app):
        assert (await events.publish({"type": "blocked"}))["seq"] == 3


async def test_event_router_rejects_second_active_application(tmp_path):
    import pytest
    from gateway import events
    first, second = FastAPI(), FastAPI()
    for index, app in enumerate((first, second)):
        app.state.audit_path = tmp_path / f"audit-{index}.jsonl"
        app.include_router(events.router)
    async with first.router.lifespan_context(first):
        with pytest.raises(RuntimeError, match="already active"):
            async with second.router.lifespan_context(second):
                pass
        assert (await events.publish({"type": "blocked"}))["seq"] == 1
    assert not second.state.audit_path.exists()


async def test_event_router_validates_before_persisting_and_shares_database(tmp_path):
    import pytest
    from pydantic import ValidationError
    from gateway import events
    from schemas.db import connect
    path = tmp_path / "oncall.db"
    db = connect(str(path))
    db.execute("INSERT INTO incidents(id, state) VALUES ('inc-1', 'open')")
    db.commit()
    store = ReceiptStore(path)
    receipt_id = store.save(Receipt(incident_id="inc-1", tool="rollback_deploy", target="payment",
                                    diff={}, inverse={"image": "old"}, evidence_ids=["journal:41"]))
    assert db.execute("SELECT state FROM incidents WHERE id='inc-1'").fetchone()["state"] == "open"
    assert db.execute("SELECT count(*) FROM receipts").fetchone()[0] == 0
    assert store.get(receipt_id).inverse == {"image": "old"}
    db.close()
    app = FastAPI()
    app.state.audit_path = tmp_path / "audit.jsonl"
    app.include_router(events.router)
    async with app.router.lifespan_context(app):
        with pytest.raises(ValidationError):
            await events.publish({"type": "approval_requested", "incident_id": "inc-1", "payload": {}})
        assert not app.state.audit_path.exists()
        record = await events.publish({"type": "blocked", "payload": {"password": "fake-private-value"}})
        assert record["event"]["payload"]["password"] == "[REDACTED]"
    assert "fake-private-value" not in app.state.audit_path.read_text()
