import time

import httpx

from notifier.consumer import NotificationConsumer
from notifier.discord_bot import ApprovalController
from notifier.state import NotifierState


async def test_approval_auth_expiry_duplicate_and_gateway_refusal(tmp_path):
    calls = []
    def handle(request):
        calls.append(request)
        return httpx.Response(200, json={"decision": "executed"})
    state = NotifierState(tmp_path / "notifier.db")
    state.set("approval:a", {"expires_at": time.time() + 60})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        controller = ApprovalController(client, "http://gateway", {"approver"}, state)
        assert await controller.decide("a", "outsider", "approved") == "not authorised"
        assert not calls
        assert await controller.decide("a", "approver", "approved") == "approved"
        assert await controller.decide("a", "approver", "approved") == "already decided"
        assert len(calls) == 1
        state.set("approval:b", {"expires_at": time.time() - 1})
        assert await controller.decide("b", "approver", "approved") == "expired"
        assert len(calls) == 1
    assert NotifierState(tmp_path / "notifier.db").get("approval:a")["decision"] == "approved"


async def test_gateway_refusal_does_not_record_approval(tmp_path):
    state = NotifierState(tmp_path / "notifier.db")
    state.set("approval:a", {"expires_at": time.time() + 60})
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(409))) as client:
        controller = ApprovalController(client, "http://gateway", {"approver"}, state)
        assert await controller.decide("a", "approver", "approved") == "gateway refused decision"
    assert not state.get("approval:a").get("decision")


async def test_consumer_restart_deduplicates_and_resolves_wake(tmp_path):
    class FakeNotifier:
        calls = []
        async def wake(self, card, briefing):
            self.calls.append("wake")
        async def fyi(self, card, url):
            self.calls.append("fyi")
    card = {"incident_id": "i", "status": "ESCALATED", "text": "needs help", "evidence_ids": []}
    record = {"seq": 1, "event": {"type": "escalated", "incident_id": "i", "payload": {"card": card}}}
    state = NotifierState(tmp_path / "state.db")
    notifier = FakeNotifier()
    async with httpx.AsyncClient() as client:
        consumer = NotificationConsumer(client, "http://gateway", notifier, state)
        await consumer.handle(record)
        await NotificationConsumer(client, "http://gateway", notifier,
                                   NotifierState(tmp_path / "state.db")).handle(record)
        assert notifier.calls == ["wake"]
        assert "i" in state.get("wakes")
        record = {"seq": 2, "event": {"type": "incident_resolved", "incident_id": "i", "payload": {"card": card}}}
        await consumer.handle(record)
        assert state.get("wakes") == {}
