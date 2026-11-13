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
    assert notifier.calls[0] == {"runbook": RB, "seen_before": "2 similar before"}
    assert [c["page"] for c in notifier.calls[1:]] == [2, 3]
    assert state.get("wakes")["i"]["pages"] == 3
