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
