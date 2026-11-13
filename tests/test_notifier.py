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
        async def wake(self, card, briefing, details=None):
            self.calls.append("wake")
        async def fyi(self, card, url, details=None):
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
        async def wake(self, card, briefing, details=None):
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


def test_notifier_uses_gateway_approver_setting(monkeypatch):
    from notifier.main import load_approvers
    monkeypatch.setenv("ONCALL_APPROVER_IDS", " 111111111111111111 , 222222222222222222 ")
    monkeypatch.setenv("DISCORD_APPROVER_IDS", "obsolete-list-must-not-win")
    assert load_approvers() == {"111111111111111111", "222222222222222222"}


def test_notifier_rejects_rehearsal_identity_in_human_allowlist(monkeypatch):
    import pytest
    from notifier.main import load_approvers
    monkeypatch.setenv("ONCALL_APPROVER_IDS", "rehearsal-harness")
    with pytest.raises(ValueError, match="rehearsal-harness"):
        load_approvers()


class PagerNotifier:
    def __init__(self):
        self.pages = []
    async def request_approval(self, *args, **kwargs):
        pass
    async def wake(self, card, briefing, details=None):
        self.pages.append(briefing)
    async def close_approval(self, approval_id, row, decision):
        pass


def approval_record(seq=1):
    card = {"incident_id": "i", "status": "AWAITING APPROVAL", "text": "approve?", "evidence_ids": []}
    return {"seq": seq, "event": {"type": "approval_requested", "incident_id": "i", "payload": {
        "approval_id": "a", "card": card, "diff": "d", "forecast": "f", "expires_at": 99}}}


async def test_approved_decision_stops_approval_repage(tmp_path, monkeypatch):
    monkeypatch.setattr("notifier.consumer.time.time", lambda: 50)
    state = NotifierState(tmp_path / "state.db")
    notifier = PagerNotifier()
    async with httpx.AsyncClient() as client:
        consumer = NotificationConsumer(client, "http://gateway", notifier, state, repage_s=10)
        await consumer.handle(approval_record())
        await consumer.handle({"seq": 2, "event": {"type": "approval_decided", "incident_id": "i",
                                                   "payload": {"approval_id": "a", "decision": "approved"}}})
        monkeypatch.setattr("notifier.consumer.time.time", lambda: 90)
        await consumer.repage_once()
    assert notifier.pages == []


async def test_expired_approval_repages_as_expired(tmp_path, monkeypatch):
    monkeypatch.setattr("notifier.consumer.time.time", lambda: 50)
    state = NotifierState(tmp_path / "state.db")
    state.set("approval:a", {"expires_at": 99, "message_id": 1, "channel_id": 2})
    notifier = PagerNotifier()
    async with httpx.AsyncClient() as client:
        consumer = NotificationConsumer(client, "http://gateway", notifier, state, repage_s=10)
        await consumer.handle(approval_record())
        monkeypatch.setattr("notifier.consumer.time.time", lambda: 120)
        await consumer.expire_once()
        await consumer.repage_once()
    assert notifier.pages == ["Approval expired; no action taken"]


# plan §6.6: wake pages re-post until acknowledged; before, nothing could ack, so they paged forever
async def test_acknowledge_stops_repaging_and_needs_an_approver(tmp_path, monkeypatch):
    from notifier.discord_bot import AckView
    monkeypatch.setattr("notifier.consumer.time.time", lambda: 50)
    state = NotifierState(tmp_path / "state.db")
    notifier = PagerNotifier()
    card = {"incident_id": "i", "status": "WOKE YOU BECAUSE", "text": "help", "evidence_ids": []}
    async with httpx.AsyncClient() as client:
        consumer = NotificationConsumer(client, "http://gateway", notifier, state, repage_s=10)
        await consumer.handle({"seq": 1, "event": {"type": "escalated", "incident_id": "i",
                                                   "payload": {"card": card, "briefing": "b"}}})
        controller = ApprovalController(client, "http://gateway", {"approver"}, state)
        assert await controller.acknowledge("i", "stranger") == "not authorised"
        monkeypatch.setattr("notifier.consumer.time.time", lambda: 70)
        await consumer.repage_once()
        assert notifier.pages == ["b", "b"]
        assert (await controller.acknowledge("i", "approver")).startswith("acknowledged by approver")
        assert await controller.acknowledge("i", "approver") == "already acknowledged"
        monkeypatch.setattr("notifier.consumer.time.time", lambda: 200)
        await consumer.repage_once()
    assert notifier.pages == ["b", "b"] and state.get("wakes") == {}
    view = AckView("i", controller)
    assert view.is_persistent() and [b.custom_id for b in view.children] == ["ack:i"]


# live: inc-1794545567530 closed (handed_off) while a re-page was talking to Discord; the
# re-page then wrote its stale list back and the closed incident paged every 2 min for 30 min
async def test_incident_closed_during_repage_stays_closed(tmp_path):
    card = {"incident_id": "i", "status": "WOKE YOU BECAUSE", "text": "help", "evidence_ids": []}
    state = NotifierState(tmp_path / "s.db")
    state.set("wakes", {"i": {"card": card, "briefing": "b", "last_page": 0}})

    class SlowDiscord:
        async def wake(self, card, briefing, details=None):
            await consumer.handle({"seq": 1, "event": {"type": "handed_off", "incident_id": "i",
                                                       "payload": {"card": card.model_dump()}}})
            return "m1"

        async def fyi(self, card, url, details=None):
            pass

    async with httpx.AsyncClient() as client:
        consumer = NotificationConsumer(client, "http://gateway", SlowDiscord(), state, repage_s=1)
        await consumer.repage_once()
    assert state.get("wakes") == {}


# live: a wake saved before the card fields were renamed failed validation and the crash stopped all paging
async def test_unreadable_saved_wake_still_pages_as_text(tmp_path):
    class FakeNotifier:
        pages: list = []

        async def wake(self, card, briefing, details=None):
            self.pages.append((card.incident_id, card.text, card.fields))

    state = NotifierState(tmp_path / "state.db")
    old = {"incident_id": "i", "status": "NEEDS YOU", "text": "payment is failing", "evidence_ids": [],
           "fields": [{"name": "Why", "value": "x"}]}
    state.set("wakes", {"i": {"card": old, "briefing": "b", "last_page": 0}})
    notifier = FakeNotifier()
    async with httpx.AsyncClient() as client:
        await NotificationConsumer(client, "http://gateway", notifier, state, repage_s=10).repage_once()
    assert notifier.pages == [("i", "payment is failing", [])]
