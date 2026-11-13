import httpx

from notifier import embeds
from notifier.consumer import NotificationConsumer
from notifier.state import NotifierState
from schemas.models import Card

FIXED = Card(incident_id="inc-1", status="FIXED", evidence_ids=["journal:41", "query:err_ratio:service=payment"], text=(
    "FIXED in 1m 32s: payment; payment errors 38.0% -> 0.4%\n"
    "Why: payment image changed to v2-bad; errors began 40 s later [journal:41]\n"
    "Did: rolled back payment to revision 3 (approved by 111). Receipt #2\n"
    "Checked: prediction held; nothing else got worse\n"
    "Undo: kubectl rollout undo deploy/payment -n shop"))
RB = {"id": "RB-01", "title": "Bad deploy", "owner": "service team", "severity": "SEV-2", "steps": ["Roll back.", "Block the tag."],
      "require_approval": True, "forbid_tools": []}


def fields(embed):
    return {f.name: f.value for f in embed.fields}


def test_fixed_card_becomes_a_green_embed_for_everyone():
    e = embeds.build("fyi", FIXED, {"seen_before": "1 similar before"}, receipt_url="http://gw/receipts/2", now=100)
    f = fields(e)
    assert e.color.value == embeds.GREEN and e.title.startswith("FIXED in 1m 32s: payment")
    assert e.author.name == "For: everyone. No action needed."
    assert e.description.startswith("payment image changed to v2-bad")
    assert f["Did"].startswith("rolled back payment") and f["Checked"].startswith("prediction held")
    assert f["Undo"] == "`kubectl rollout undo deploy/payment -n shop`"
    assert f["Evidence"] == "`journal:41` `query:err_ratio:service=payment`"
    assert f["Receipt"] == "http://gw/receipts/2" and f["Seen before"] == "1 similar before"
    assert e.footer.text == "Incident inc-1" and e.timestamp.timestamp() == 100


def test_approval_embed_names_who_can_approve_and_the_runbook():
    card = FIXED.model_copy(update={"status": "NEEDS APPROVAL", "text": "NEEDS APPROVAL: payment\nWhy: bad image"})
    e = embeds.build("approval", card, {"runbook": RB}, diff="rollback_deploy payment: to revision 3",
                     forecast="about 0 s", expires_at=1000, approvers={"222", "111", "rehearsal-harness"},
                     approval_id="a1")
    f = fields(e)
    assert e.color.value == embeds.ORANGE and e.author.name.startswith("For: approvers")
    assert f["Who can approve"] == "<@111>, <@222>"  # never the rehearsal identity
    assert f["Expires"] == "<t:1000:R> (<t:1000:t>)" and f["Change"].startswith("```rollback_deploy")
    assert f["Runbook"].startswith("**RB-01 Bad deploy** [SEV-2] (owner: service team)")
    assert "Rule: a human approves every action" in f["Runbook"] and "1. Roll back.\n2. Block the tag." in f["Runbook"]
    assert e.footer.text == "Incident inc-1 · Approval a1"


def test_status_colors_and_wake_page_counter():
    assert embeds.color_of("MAJOR INCIDENT: WOKE YOU BECAUSE") == embeds.DARK_RED
    assert embeds.color_of("MITIGATED, NOT FIXED") == embeds.YELLOW
    assert embeds.color_of("HANDED OFF") == embeds.GREY and embeds.color_of("odd") == embeds.BLURPLE
    card = Card(incident_id="i", status="WOKE YOU BECAUSE", text="WOKE YOU BECAUSE: kafka\nWhy: no outcome",
                evidence_ids=[])
    e = embeds.build("wake", card, {"page": 3}, briefing="look by hand")
    assert fields(e)["Briefing"] == "look by hand" and fields(e)["Page"].startswith("#3")
    assert "Page" not in fields(embeds.build("wake", card, {}, briefing="b"))


def test_secrets_are_redacted_and_discord_limits_hold():
    card = Card(incident_id="i", status="WOKE YOU BECAUSE", evidence_ids=[f"log:{n}" for n in range(400)],
                text="WOKE YOU BECAUSE: " + "x" * 400 + "\nWhy: password=hunter2 " + "y" * 9000 +
                     "\nDid: " + "z" * 3000)
    e = embeds.build("wake", card, {"seen_before": "token=abc123"}, briefing="api_key=sk-secretvalue " * 200)
    text = str(e.to_dict())
    assert "hunter2" not in text and "abc123" not in text and "sk-secretvalue" not in text
    assert len(e) <= 6000 and len(e.title) <= 256 and all(len(f.value) <= 1024 for f in e.fields)
    assert fields(e)["Briefing"]  # the most important field survives the trim


def test_decided_keeps_the_card_and_adds_who_and_when():
    e = embeds.build("approval", FIXED, {}, approvers={"111"}, approval_id="a1")
    out = embeds.decided(e, "approved", "111", now=50)
    assert out.color.value == embeds.GREEN and out.title == e.title
    assert fields(out)["Outcome"] == "**approved** by <@111> <t:50:R>" and fields(out)["Did"] == fields(e)["Did"]
    assert fields(embeds.decided(e, "expired", None, now=50))["Outcome"] == "**expired** <t:50:R>"
    assert embeds.decided(None, "approved", "1") is None


def test_short_observer_card_still_parses():
    head, parts = embeds.card_parts(Card(incident_id="i", status="WOKE YOU BECAUSE", evidence_ids=[],
                                         text="WOKE YOU BECAUSE: cart\nWhy: lost track\nextra line"))
    assert head == "WOKE YOU BECAUSE: cart" and parts == {"Why": "lost track\nextra line"}


class Recorder:
    def __init__(self):
        self.calls = []

    async def request_approval(self, *args, details=None):
        self.calls.append(("approval", details))

    async def wake(self, card, briefing, details=None):
        self.calls.append(("wake", details))
        return 7


# runbook + seen-before travel from the gateway payload to the embed, and re-pages count up
async def test_consumer_passes_details_and_counts_pages(tmp_path, monkeypatch):
    monkeypatch.setattr("notifier.consumer.time.time", lambda: 0)
    card = {"incident_id": "i", "status": "WOKE YOU BECAUSE", "text": "help", "evidence_ids": []}
    state, notifier = NotifierState(tmp_path / "s.db"), Recorder()
    async with httpx.AsyncClient() as client:
        consumer = NotificationConsumer(client, "http://gw", notifier, state, repage_s=10)
        await consumer.handle({"seq": 1, "event": {"type": "escalated", "incident_id": "i", "payload": {
            "card": card, "briefing": "b", "runbook": RB, "seen_before": "2 similar before"}}})
        for t in (20, 40):
            monkeypatch.setattr("notifier.consumer.time.time", lambda t=t: t)
            await consumer.repage_once()
    assert notifier.calls[0] == ("wake", {"runbook": RB, "seen_before": "2 similar before"})
    assert [c[1]["page"] for c in notifier.calls[1:]] == [2, 3]
    assert state.get("wakes")["i"]["pages"] == 3


async def test_wake_pings_only_the_role_and_sends_an_embed():
    import discord

    from notifier.discord_bot import ApprovalController, DiscordNotifier

    sent = {}

    class Channel:
        async def send(self, content, **kw):
            sent.update(kw, content=content)
            return type("M", (), {"id": 9, "channel": type("C", (), {"id": 1})()})()

    async with httpx.AsyncClient() as client:
        bot = DiscordNotifier(ApprovalController(client, "http://gw", {"111"}, None), 1, 2, 3, 42)  # type: ignore[arg-type]

        async def channel(_):
            return Channel()

        bot.channel = channel  # type: ignore[method-assign]
        assert await bot.wake(FIXED.model_copy(update={"status": "WOKE YOU BECAUSE"}), "b") == 9
        assert sent["content"].startswith("<@&42> FIXED in 1m 32s") and isinstance(sent["embed"], discord.Embed)
        assert sent["allowed_mentions"].users is False and sent["allowed_mentions"].everyone is False
        await bot.fyi(FIXED, "u")
        assert sent["content"] is None and sent["embed"].author.name.startswith("For: everyone")
        await bot.close()
