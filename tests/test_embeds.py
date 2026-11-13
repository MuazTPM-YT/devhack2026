import httpx

from gateway.receipts import build_incident_card
from notifier import embeds
from notifier.consumer import NotificationConsumer
from notifier.discord_bot import DiscordNotifier, embed_of
from notifier.state import NotifierState
from schemas.models import Card, GatewayDecision, Incident

INC = Incident(id="inc-1", opened_at=100, onset_at=90, unhealthy=["payment"], culprit="payment", severity=4)
CARD = build_incident_card(INC, decision=GatewayDecision(decision="awaiting_approval", reason="trust"))
RB = {"id": "RB-01", "title": "Bad deploy", "owner": "service team", "severity": "SEV-2",
      "steps": ["Roll back.", "Block the tag."], "require_approval": True, "forbid_tools": []}


def fields(embed):
    return {f.name: f.value for f in embed.fields}


class Sent(DiscordNotifier):
    def __init__(self, approvers=frozenset()):  # no discord login: record what would go out
        self.sent, self.role_id = [], 9
        self.controller = type("C", (), {"approvers": set(approvers)})()
        self.wake_channel = self.fyi_channel = self.tickets_channel = 1

    async def send_text(self, channel_id, text, *, wake=False, view=None, embed=None):
        self.sent.append((text, embed, wake))
        return type("M", (), {"id": 1, "channel": type("Ch", (), {"id": 1})()})()


def test_runbook_text_shows_severity_owner_rules_steps():
    text = embeds.runbook_text(RB)
    assert text.startswith("**RB-01 Bad deploy** [SEV-2] (owner: service team)")
    assert "Rule: a human approves every action" in text and "1. Roll back.\n2. Block the tag." in text


def test_mentions_skip_non_discord_ids():
    assert embeds.mentions({"222", "111", "rehearsal-harness"}) == "<@111>, <@222>"
    assert embeds.mentions(set()) == "none configured"


async def test_approval_embed_says_who_it_is_for_and_who_can_approve(monkeypatch):
    monkeypatch.setattr("notifier.discord_bot.ApprovalView", lambda *a: None)
    bot = Sent({"111", "rehearsal-harness"})
    bot.controller.state = type("S", (), {"get": lambda self, k: None, "set": lambda self, k, v: None})()
    await bot.request_approval("a1", CARD, "rollback payment", "0 s", 1000,
                               details={"runbook": RB, "seen_before": "2 similar before"})
    text, embed, wake = bot.sent[0]
    f = fields(embed)
    assert wake and text == CARD.headline and embed.author.name.startswith("For: approvers")
    assert f["Who can approve"] == "<@111>" and f["Expires"] == "<t:1000:R> (<t:1000:t>)"
    assert f["Runbook"].startswith("**RB-01 Bad deploy** [SEV-2]") and f["Seen before"] == "2 similar before"
    assert len(embed) <= 6000


async def test_wake_page_counter_and_audience():
    bot = Sent()
    await bot.wake(CARD, "b", details={"page": 3})
    embed = bot.sent[0][1]
    assert embed.author.name == "For: on-call. A human must look now." and fields(embed)["Page"].startswith("#3")
    await bot.wake(CARD, "b")
    assert "Page" not in fields(bot.sent[1][1])


async def test_fyi_and_ticket_audience():
    bot = Sent()
    await bot.fyi(CARD, "http://gw/receipts/2")
    await bot.ticket(CARD)
    assert bot.sent[0][1].author.name.startswith("For: everyone")
    assert bot.sent[1][1].author.name.startswith("For: the day team")


def test_secrets_redacted_and_limits_hold_with_extras():
    rb = {**RB, "steps": ["password=hunter2 " + "y" * 3000] * 3}
    embed = embed_of(CARD, [("Runbook", embeds.runbook_text(rb)), ("Seen before", "token=abc123 " * 300)])
    text = str(embed.to_dict())
    assert "hunter2" not in text and "abc123" not in text
    assert len(embed) <= 6000 and all(len(f.value) <= 1024 for f in embed.fields)


def test_decided_keeps_the_card_and_adds_who_and_when():
    e = embed_of(CARD)
    out = embeds.decided(e, "approved", "111", now=50)
    assert out.colour.value == embeds.DECISION_COLOURS["approved"] and out.title == e.title
    assert fields(out)["Outcome"] == "**approved** by <@111> <t:50:R>"
    assert fields(embeds.decided(e, "expired", None, now=50))["Outcome"] == "**expired** <t:50:R>"
    assert embeds.decided(None, "approved", "1") is None


class Recorder:
    def __init__(self):
        self.calls = []

    async def wake(self, card, briefing, details=None):
        self.calls.append(details)
        return 7


# runbook + seen-before travel from the gateway payload to the embed, and re-pages count up
async def test_consumer_passes_details_and_counts_pages(tmp_path, monkeypatch):
    monkeypatch.setattr("notifier.consumer.time.time", lambda: 0)
    card = Card(incident_id="i", status="WOKE YOU BECAUSE", text="help", evidence_ids=[]).model_dump()
    state, notifier = NotifierState(tmp_path / "s.db"), Recorder()
    async with httpx.AsyncClient() as client:
        consumer = NotificationConsumer(client, "http://gw", notifier, state, repage_s=10)
        await consumer.handle({"seq": 1, "event": {"type": "escalated", "incident_id": "i", "payload": {
            "card": card, "briefing": "b", "runbook": RB, "seen_before": "2 similar before"}}})
        for t in (20, 40):
            monkeypatch.setattr("notifier.consumer.time.time", lambda t=t: t)
            await consumer.repage_once()
    first = notifier.calls[0]
    assert {k: v for k, v in first.items() if k != "event"} == {"runbook": RB, "seen_before": "2 similar before"}
    assert first["event"] == {"type": "escalated", "seq": 1, "ts": None}  # the bus record's place and time
    assert [c["page"] for c in notifier.calls[1:]] == [2, 3]
    assert state.get("wakes")["i"]["pages"] == 3


# ---- origin, timeline, what to do (Muaz: show where a message came from, what started it, when) ----------
SOURCE = {"part": "gateway", "step": "trust gate", "host": "backend-1", "mode": "live"}
STARTED = {"onset_at": 960.0, "opened_at": 990.0, "change": "image change on deployment/payment",
           "by": "chaos-panel", "change_ts": 930.0}
EVENT = {"type": "approval_requested", "seq": 812, "ts": 1000.0}


async def test_approval_shows_your_move_origin_timeline_and_ids(monkeypatch):
    monkeypatch.setattr("notifier.discord_bot.ApprovalView", lambda *a: None)
    bot = Sent({"111"})
    bot.controller.state = type("S", (), {"get": lambda self, k: None, "set": lambda self, k, v: None})()
    await bot.request_approval("a1b2", CARD, "rollback payment", "0 s", 1300,
                               details={"source": SOURCE, "started": STARTED, "event": EVENT})
    text, embed, _ = bot.sent[0]
    f = fields(embed)
    assert "**Your move:** Press Approve or Reject below before <t:1300:t> (<t:1300:R>)" in embed.description
    assert f["Origin"].splitlines() == [
        "Started by: image change on deployment/payment, made by chaos-panel, 30 s before the first errors.",
        "Sent by: Gateway (safety checks), step: trust gate. Machine: backend-1.", "Mode: LIVE."]
    assert f["Timeline"].splitlines() == ["First errors: <t:960:T> (<t:960:R>)", "Incident opened: <t:990:T>",
                                          "This message: <t:1000:T> (<t:1000:R>)"]
    assert embed.footer.text.endswith("Event #812 · Approval a1b2") and embed.timestamp.timestamp() == 1000
    assert not embed.title.startswith("[REHEARSAL]") and text == CARD.headline


async def test_rehearsal_is_marked_in_title_line_and_origin():
    bot = Sent()
    await bot.wake(CARD, "b", details={"source": {**SOURCE, "mode": "rehearsal"}, "event": EVENT})
    text, embed, _ = bot.sent[0]
    assert text.startswith("[REHEARSAL] ") and embed.title.startswith("[REHEARSAL] ")
    assert "Mode: **REHEARSAL**. A bench test run" in fields(embed)["Origin"]
    assert "Look at it now. Press Acknowledge" in embed.description


async def test_repage_says_the_notifier_sent_it_and_when_it_was_first_sent():
    bot = Sent()
    await bot.wake(CARD, "b", details={"source": SOURCE, "started": STARTED, "event": EVENT, "page": 2})
    f = fields(bot.sent[0][1])
    assert f["Origin"].endswith("Re-sent by the Notifier: page #2.")
    assert "First sent: <t:1000:T>" in f["Timeline"] and "This re-page: <t:" in f["Timeline"]


def test_no_recorded_change_and_a_change_after_onset_read_plainly():
    assert embeds.origin_text(None, {"change": None}) == "Started by: no recorded change found before the first errors."
    late = embeds.origin_text(None, {**STARTED, "change_ts": 970.0})
    assert late.endswith("made by chaos-panel, after the first errors.")
    assert embeds.origin_text(None, None) is None and embeds.timeline_text(None, None) is None


def test_your_move_per_kind():
    assert embeds.your_move("fyi", "FIXED in 2m").startswith("Nothing. This is for your information")
    assert embeds.your_move("fyi", "TRYING ANOTHER FIX").startswith("Nothing yet. You get a page if every fix")
    assert embeds.your_move("fyi", "HANDED OFF").startswith("Nothing from the agent")
    assert embeds.your_move("ticket", "MITIGATED, NOT FIXED").startswith("Plan a follow-up")


async def test_origin_and_timeline_survive_a_huge_card():
    bot = Sent()
    rb = {**RB, "steps": ["x" * 1000] * 3}
    await bot.wake(CARD, "b", details={"source": SOURCE, "started": STARTED, "event": EVENT, "runbook": rb,
                                       "seen_before": "y" * 1000})
    embed = bot.sent[0][1]
    assert len(embed) <= embeds.MAX_TOTAL and "Origin" in fields(embed) and "Timeline" in fields(embed)


async def test_retry_started_goes_to_fyi_with_its_origin(tmp_path):
    card = build_incident_card(INC, retry={"tries": [{"attempt": 1, "tool": "rollback_deploy", "target": "payment",
                                                      "why_undone": "did not recover", "receipt_id": 3}],
                                           "max": 3, "next": 2})
    assert card.status == "TRYING ANOTHER FIX" and card.level == "info"
    assert card.headline == ("payment: fix 1 of 3 did not work, so the agent undid it and is trying fix 2.")

    class Fyi:
        calls = []

        async def fyi(self, card, url, details=None):
            self.calls.append((card.status, url, details))

    async with httpx.AsyncClient() as client:
        consumer = NotificationConsumer(client, "http://gw", Fyi(), NotifierState(tmp_path / "s.db"))
        await consumer.handle({"seq": 9, "ts": 1000.0, "event": {"type": "retry_started", "incident_id": "inc-1",
                                                                 "payload": {"card": card.model_dump(), "source": SOURCE,
                                                                             "receipt_url": "/receipts/3"}}})
    status, url, details = Fyi.calls[0]
    assert status == "TRYING ANOTHER FIX" and url == "http://gw/receipts/3"
    assert details["source"] == SOURCE and details["event"] == {"type": "retry_started", "seq": 9, "ts": 1000.0}
    assert consumer.state.get("wakes", {}) == {}  # an FYI: nobody is paged


def test_bus_stamps_live_or_rehearsal_only_where_a_source_is_named(monkeypatch):
    from gateway.events import stamp

    monkeypatch.setenv("ONCALL_REHEARSAL", "1")
    assert stamp({"type": "escalated", "payload": {"source": {"part": "brain"}}})["payload"]["source"]["mode"] == \
        "rehearsal"
    monkeypatch.setenv("ONCALL_REHEARSAL", "0")
    assert stamp({"type": "escalated", "payload": {"source": {"part": "brain"}}})["payload"]["source"]["mode"] == "live"
    assert stamp({"type": "verify_tick", "payload": {"severity": 3}}) == {"type": "verify_tick",
                                                                          "payload": {"severity": 3}}


def test_impact_lists_every_sick_service_with_numbers():
    health = {"severity": 7, "services": {
        "payment": {"err_ratio": 0.36}, "checkout": {"err_ratio": 0.0, "p95_ms": 1200.0, "baseline_p95_ms": 80.0}}}
    inc = Incident(id="inc-1", opened_at=100, onset_at=90, unhealthy=["payment", "checkout"], culprit="payment",
                   victims=["checkout"], severity=7)
    card = build_incident_card(inc, decision=GatewayDecision(decision="escalated", reason="no safe action (unknown)"),
                               health=health)
    assert fields_of(card)["Impact"].splitlines() == [
        "Severity 7. 2 services affected:", "- 36% of payment requests are failing",
        "- checkout is slow: 95% of requests finish within 1.2 s, normal is 80 ms; no requests are failing"]


def fields_of(card):
    return {f.label: f.body for f in card.fields}


# live 2026-11-14: the retry FYI is built from the undone receipt; its push line said only "undid it"
def test_retry_card_from_an_undone_receipt_says_it_tries_again():
    from schemas.models import Receipt
    r = Receipt(incident_id="inc-1", tool="rollback_deploy", target="payment", diff={"x": 1},
                inverse={"op": "restore_template"}, evidence_ids=[], outcome="undone")
    card = build_incident_card(INC, receipt=r, receipt_id=2, reason="did not recover",
                               retry={"tries": [{"attempt": 1, "tool": "rollback_deploy", "target": "payment",
                                                 "why_undone": "did not recover", "receipt_id": 2}], "max": 3, "next": 2})
    assert card.status == "TRYING ANOTHER FIX" and card.level == "info"
    assert card.headline == "payment: fix 1 of 3 did not work, so the agent undid it and is trying fix 2."
