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


async def test_success_status_with_refusal_body_is_not_approval(tmp_path):
    state = NotifierState(tmp_path / "notifier.db")
    state.set("approval:a", {"expires_at": time.time() + 60})
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json={"decision": "refused", "reason": "stale"})
    )) as client:
        controller = ApprovalController(client, "http://gateway", {"approver"}, state)
        assert await controller.decide("a", "approver", "approved") == "gateway refused decision"
    assert not state.get("approval:a").get("decision")


async def test_repage_expiry_and_persistent_buttons(tmp_path, monkeypatch):
    from notifier.discord_bot import ApprovalView
    class FakeNotifier:
        def __init__(self):
            self.pages, self.closed = [], []
        async def wake(self, card, briefing):
            self.pages.append(card.incident_id)
        async def close_approval(self, approval_id, row, decision):
            self.closed.append((approval_id, decision))
    monkeypatch.setattr("notifier.consumer.time.time", lambda: 100)
    state = NotifierState(tmp_path / "state.db")
    state.set("approval:a", {"expires_at": 99, "message_id": 1, "channel_id": 2})
    state.set("wakes", {"i": {"card": {"incident_id": "i", "status": "ESCALATED",
                                         "text": "needs help", "evidence_ids": []},
                               "briefing": "help", "last_page": 0}})
    notifier = FakeNotifier()
    async with httpx.AsyncClient() as client:
        consumer = NotificationConsumer(client, "http://gateway", notifier, state, repage_s=10)
        await consumer.repage_once()
        await consumer.repage_once()
        assert notifier.pages == ["i"]
        await consumer.expire_once()
        await consumer.expire_once()
        assert notifier.closed == [("a", "expired")]
        assert state.get("approval:a")["view_closed"]
        controller = ApprovalController(client, "http://gateway", {"approver"}, state)
        view = ApprovalView("a", controller)
        assert view.is_persistent()
        assert {button.custom_id for button in view.children} == {"approval:a:approved", "approval:a:rejected"}
