import json

import discord
import httpx
import pytest

from gateway.receipts import REASONS, build_incident_card, explain
from notifier.consumer import NotificationConsumer
from notifier.discord_bot import COLOUR, DiscordNotifier, embed_of
from notifier.state import NotifierState
from schemas.models import ActionRequest, Card, Cause, Diagnosis, GatewayDecision, Incident, Prediction, Receipt

INC = Incident(id="i", opened_at=0, onset_at=0, unhealthy=["payment"], culprit="payment",
               victims=["checkout"], severity=7)
REC = Incident(id="r", opened_at=0, onset_at=0, unhealthy=["recommendation"], culprit="recommendation", severity=3)
HEALTH = {"ts": 0, "services": {"payment": {"err_ratio": 0.361, "p95_ms": 2400, "baseline_p95_ms": 300},
                                "recommendation": {"err_ratio": 0.0, "p95_ms": 15, "baseline_p95_ms": 5}}}
ROLLBACK = ActionRequest(incident_id="i", tool="rollback_deploy", target="payment", pattern="recent_change",
                         evidence_ids=["journal:7"],
                         prediction=Prediction(metric="err_ratio", target="payment", below=0.05, within_s=120))


def receipt(**changes):
    base = {"incident_id": "i", "tool": "rollback_deploy", "target": "payment", "diff": {},
            "inverse": {"op": "restore_template"}, "evidence_ids": ["journal:7"], "outcome": "success",
            "prediction_held": True, "harm_clean": True, "elapsed_s": 81}
    return Receipt(**{**base, **changes})


def everything(card: Card) -> str:
    return json.dumps(card.model_dump())


def field(card: Card, name: str) -> str:
    return next(f.body for f in card.fields if f.label == name)


# live discord: "Why: unknown" on every gateway card; with no journal fact the pattern still says something
def test_why_without_journal_fact_uses_pattern_not_unknown():
    text = build_incident_card(INC, receipt=receipt(outcome="right_by_accident", prediction_held=False),
                               receipt_id=2, pattern="recent_change").text
    assert text.splitlines()[1] == "Why: A change to payment landed just before it started failing"
    assert "unknown" not in text


# the model read untrusted evidence: its sentence comes after our fact, labelled
def test_llm_explanation_is_labelled_after_the_fixed_sentence():
    cause = Cause(cause_class="recent_change", culprit="payment", evidence_ids=["journal:7"],
                  explanation="image changed to v2-bad\n30 s before errors")
    card = build_incident_card(INC, Diagnosis(causes=[cause], confidence=0.8),
                               decision=GatewayDecision(decision="escalated"))
    assert card.text.splitlines()[1] == ("Why: A change to payment landed just before it started failing. "
                                         "AI reading (not checked): image changed to v2-bad 30 s before errors")
    assert len(card.text.splitlines()) == 5
    assert [f.label for f in card.fields][-1] == "AI reading (not checked)"


def test_journal_fact_stays_first_when_the_model_also_speaks():
    line = build_incident_card(INC, receipt=receipt(), receipt_id=2, why="payment image changed to v2-bad",
                               model_says="bad image broke payment").text.splitlines()[1]
    assert line == "Why: payment image changed to v2-bad. AI reading (not checked): bad image broke payment"


# discord showed "/receipts/2": a relative link nobody can click
async def test_fyi_receipt_link_is_absolute(tmp_path):
    class Notifier:
        urls: list[str] = []

        async def fyi(self, card, url, details=None):
            self.urls.append(url)

    card = {"incident_id": "i", "status": "FIXED", "text": "fixed", "evidence_ids": []}
    record = {"seq": 1, "event": {"type": "incident_resolved", "incident_id": "i",
                                  "payload": {"card": card, "receipt_url": "/receipts/2"}}}
    notifier = Notifier()
    async with httpx.AsyncClient() as client:
        await NotificationConsumer(client, "http://127.0.0.1:7003/", notifier,
                                   NotifierState(tmp_path / "s.db")).handle(record)
    assert notifier.urls == ["http://127.0.0.1:7003/receipts/2"]


# action can target a dependency (valkey-cart) while the culprit is cart: undo must name what was touched
def test_did_and_undo_name_the_action_target_not_the_culprit():
    cart = INC.model_copy(update={"culprit": "cart"})
    lines = build_incident_card(cart, receipt=receipt(target="valkey-cart"), receipt_id=4).text.splitlines()
    assert "valkey-cart" in lines[2]
    assert lines[4] == "Undo: kubectl rollout undo deploy/valkey-cart -n shop"


def test_odd_target_name_never_becomes_a_command():
    card = build_incident_card(INC, receipt=receipt(target="pay;rm -rf"), receipt_id=5)
    assert "kubectl" not in card.text.splitlines()[4] and "kubectl" not in field(card, "To undo")


# gateway reads the LLM's sentence from the incident row the brain wrote
def test_llm_why_reaches_gateway_cards_labelled(tmp_path):
    from test_gateway import World
    w = World(tmp_path)
    w.conn.execute("UPDATE incidents SET pattern='recent_change', llm_why='payment image went bad, errors 40 s later.'")
    row = dict(w.conn.execute("SELECT * FROM incidents").fetchone())
    card = w.gw.card(row, "payment", receipt=receipt(), receipt_id=2)
    assert card.text.splitlines()[1] == ("Why: A change to payment landed just before it started failing. "
                                         "AI reading (not checked): payment image went bad, errors 40 s later.")
    assert field(card, "AI reading (not checked)") == "payment image went bad, errors 40 s later."


# live: "action budget used up" read as if the agent had crashed
def test_budget_card_says_safety_limit_and_what_it_would_have_done():
    card = build_incident_card(INC, decision=GatewayDecision(decision="escalated", reason="action budget used up"),
                               health=HEALTH, proposal=ROLLBACK, why="payment image changed to v2-bad")
    assert card.headline == "36% of payment requests are failing. The agent changed nothing."
    assert field(card, "Why the agent stopped").startswith("Safety limit:")
    assert "nothing in the agent is broken" in field(card, "Why the agent stopped")
    assert field(card, "Suggested fix (not run)").endswith("`kubectl rollout undo deploy/payment -n shop`")
    assert field(card, "Changes by the agent") == "None yet. Nothing to undo."
    assert "budget used up" not in everything(card)
    assert card.level == "page" and card.title == "NEEDS YOU · payment"


# live: "[query:p95_ms:service=recommendation]" and "no safe action (unknown)" told the human nothing
def test_no_cause_card_has_numbers_with_units_and_no_codes():
    cause = Cause(cause_class="unknown", culprit="recommendation",
                  evidence_ids=["query:p95_ms:service=recommendation", "query:err_ratio:service=recommendation"],
                  explanation="Recommendation p95_ms is 15 versus 5. No cause [query:p95_ms:service=recommendation]")
    card = build_incident_card(REC, Diagnosis(causes=[cause], confidence=0.2), health=HEALTH,
                               decision=GatewayDecision(decision="escalated", failed_step="rules",
                                                        reason="no safe action (unknown)"))
    assert card.headline == ("recommendation is slow: 95% of requests finish within 15 ms, normal is 5 ms; "
                             "no requests are failing. The agent changed nothing.")
    assert field(card, "Why the agent stopped") == "No cause found. The agent acts only when it can name a cause."
    assert "Likely cause" not in [f.label for f in card.fields]  # "no cause" is already said once
    text = everything(card.model_copy(update={"evidence_ids": []}))
    for code in ("[query:", "p95_ms", "err_ratio", "no safe action", "(unknown)"):
        assert code not in text, code
    assert card.footer == "Incident r · Evidence: 2 metrics"


def test_approval_card_leads_with_the_action_and_its_promise():
    card = build_incident_card(INC, decision=GatewayDecision(decision="awaiting_approval",
                                                             reason="trust bound 0.4 < 0.9"),
                               health=HEALTH, proposal=ROLLBACK, did="back to revision 3")
    assert card.headline == ("36% of payment requests are failing. "
                             "The agent wants your OK to roll payment back to its previous version.")
    assert [f.label for f in card.fields][:3] == ["The agent wants to", "If you approve", "Why it asks you"]
    assert field(card, "If you approve") == ("payment errors must fall below 5% within 120 s, "
                                             "or the agent undoes the fix.")
    assert "trust bound" not in everything(card) and card.level == "ask"


def test_undone_card_says_what_happened_not_mid_fix_numbers():
    card = build_incident_card(INC, receipt=receipt(outcome="undone", harm_clean=False), receipt_id=4,
                               health=HEALTH, reason="harm check failed", metric="payment errors 36.1% -> 31.0%")
    assert card.headline == ("36% of payment requests are failing. "
                             "After the fix, another service got worse, so the agent undid it.")
    assert "During the fix: payment errors 36.1% → 31.0%." in field(card, "What happened")
    assert field(card, "The agent did").startswith("Rolled payment back")
    assert card.title == "NEEDS YOU · payment" and card.level == "page"


def test_fixed_card_is_green_with_took_and_paste_ready_undo():
    card = build_incident_card(INC, receipt=receipt(trust={"approved_by": "u1"}), receipt_id=5, took_s=75,
                               metric="payment errors 22.5% -> 0.4%")
    assert card.title == "FIXED in 1m 15s · payment" and card.level == "ok"
    assert card.headline == "payment fixed in 1m 15s: payment errors 22.5% → 0.4%."
    assert field(card, "To undo") == "`kubectl rollout undo deploy/payment -n shop`"
    assert field(card, "Checks") == "Recovery matched the agent's prediction\nNothing else got worse"


# model prose: epoch times, evidence ids and markdown links are noise or a spoof risk on discord
def test_model_text_loses_epochs_ids_and_markdown():
    card = build_incident_card(INC, model_says="image changed at 1794545702.5, see [journal:7] "
                                                "[click](http://evil) `kubectl delete ns shop`")
    said = field(card, "AI reading (not checked)")
    assert "1794545702" not in said and "journal:7" not in said
    assert not any(c in said for c in "[]`")


# every stop reason the gateway or brain can give reads as a sentence, never as the raw code
@pytest.mark.parametrize("reason", [
    "action budget used up", "no safe action (unknown)", "no safe action (resource)",
    "valkey-cart is protected; a human must act", "valkey-cart is a protected data store; a human must approve",
    "another action is still being verified", "problem no longer present",
    "no health readings for payment; cannot tell if the problem is still there",
    "no safe undo (undo would scale valkey-cart to 0 replicas, outside the allowed 1-3); fix kept after: "
    "did not recover",
    "rule result changed: ('recent_change', 3) -> ('recent_change', 4)",
    "journal entry 41 no longer matches the live object", "journal entry 41 not found",
    "observer unreachable: ConnectError", "action refused: target not allowed", "tool scale not allowed",
    "trust bound 0.4 < 0.9", "major incident: a human approves every action except reverting the shared change",
    "major incident: one restart per incident", "blast radius unknown and the action costs capacity",
    "net benefit too low: {}", "API server refused: forbidden", "approval expired", "approval rejected",
    "severity rose after the action", "did not recover", "harm check failed", "UNDO FAILED",
    "watchdog: verifier silent for receipt #3", "deployment/payment changed by kubectl-edit",
])
def test_every_known_reason_has_a_plain_sentence(reason):
    said = explain(reason)
    assert not said.startswith("The agent stopped:") and reason not in said


# live: astronomy-db OOM; the MCP schema refused raise_limit and the page showed a pydantic error
def test_schema_refusal_reads_as_blocked_not_as_a_suggestion():
    db = INC.model_copy(update={"culprit": "astronomy-db", "unhealthy": ["astronomy-db"], "victims": []})
    raise_limit = ROLLBACK.model_copy(update={"tool": "raise_limit", "target": "astronomy-db", "prediction": None})
    card = build_incident_card(db, pattern="resource", proposal=raise_limit, decision=GatewayDecision(
        decision="escalated", failed_step="schema", reason="Error executing tool raise_limit: 1 validation error for "
                                                           "raise_limitArguments target Input should be 'payment'"))
    assert field(card, "Why the agent stopped") == ("The fix the agent proposed is not allowed by its rules, "
                                                    "so it was blocked.")
    assert field(card, "Blocked proposal (not run)") == "Raise astronomy-db's memory limit."
    assert "validation error" not in everything(card)
    assert card.text.splitlines()[1] == "Why: astronomy-db ran out of memory or CPU"


# live inc-1794552167187: the page said "blocked" but not that astronomy-db is off-limits to the agent
def test_schema_refusal_names_the_service_the_agent_may_not_change():
    reason = ("Error executing tool raise_limit: 1 validation error for raise_limitArguments\ntarget\n  Input should "
              "be 'payment', 'checkout' or 'kafka' [type=literal_error, input_value='astronomy-db', input_type=str]\n"
              "    For further information vis")
    assert explain(reason) == "astronomy-db is not on the list of services the agent may change, so it was blocked."


# the refused target is the model's own text: only a plain k8s name may reach the page
def test_schema_refusal_hides_a_target_that_is_not_a_plain_name():
    reason = "1 validation error [type=literal_error, input_value='[click](https://evil.example) @everyone', x]"
    assert explain(reason) == "The fix the agent proposed is not allowed by its rules, so it was blocked."


# live: "astronomy-db is unhealthy" said nothing; a datastore has no request metrics, only sick pods
def test_datastore_symptom_counts_sick_pods():
    db = INC.model_copy(update={"culprit": "astronomy-db", "unhealthy": ["astronomy-db"], "victims": []})
    card = build_incident_card(db, health={"services": {"astronomy-db": {"err_ratio": None, "bad_pods": 1}}})
    assert card.summary == "1 astronomy-db pod is crashing, out of memory or not ready."


# security review: a refused fix must not come with a command that walks around the policy
@pytest.mark.parametrize("reason", ["valkey-cart is protected; a human must act", "tool scale not allowed",
                                    "approval rejected", "major incident: one restart per incident"])
def test_refused_fix_never_gets_a_paste_ready_command(reason):
    card = build_incident_card(INC, decision=GatewayDecision(decision="escalated", reason=reason),
                               health=HEALTH, proposal=ROLLBACK)
    assert field(card, "Blocked proposal (not run)") == "Roll payment back to its previous version."
    assert "kubectl" not in everything(card)


def test_approval_card_has_no_command_beside_approve():
    card = build_incident_card(INC, decision=GatewayDecision(decision="awaiting_approval", reason="trust bound 0.4"),
                               health=HEALTH, proposal=ROLLBACK)
    assert "kubectl" not in everything(card)


def test_unknown_reason_still_shown_labelled():
    assert explain("brand new thing") == "The agent stopped: brand new thing."
    assert explain("ConnectError", "gateway").startswith("The agent's safety checker")
    assert len(REASONS) >= 20


# live: the audit redactor blanked every field: {name, value} dicts look like k8s env vars
def test_card_fields_survive_event_redaction():
    from brain.redact import redact_value
    card = build_incident_card(INC, decision=GatewayDecision(decision="escalated", reason="action budget used up"),
                               health=HEALTH, proposal=ROLLBACK)
    assert Card.model_validate(redact_value(card.model_dump(mode="json"))) == card


# discord limits: title 256, field 1024, whole embed 6000; colour follows the level
def test_embed_fits_discord_limits_and_colour():
    long = "x " * 3000
    card = build_incident_card(INC, decision=GatewayDecision(decision="escalated", reason=long),
                               health=HEALTH, proposal=ROLLBACK, model_says=long, why=long)
    embed = embed_of(card, [("Exact change", long)])
    assert len(embed) <= 6000 and all(len(f.value or "") <= 1024 for f in embed.fields)
    assert embed.colour == discord.Colour(COLOUR["page"])


# live fixed card said "approved by 875250916951986196": a number nobody recognises
def test_embed_names_the_approver():
    card = build_incident_card(INC, receipt=receipt(trust={"approved_by": "875250916951986196"}), receipt_id=6)
    did = next(f.value for f in embed_of(card).fields if f.name == "The agent did")
    assert "approved by <@875250916951986196>" in did


class Sent(DiscordNotifier):
    def __init__(self):  # no discord login: record what would go out
        self.sent, self.role_id, self.controller = [], 9, None
        self.wake_channel = self.fyi_channel = self.tickets_channel = 1

    async def send_text(self, channel_id, text, *, wake=False, view=None, embed=None):
        self.sent.append((text, embed, wake))

        class Message:
            id = 1
        return Message()


async def test_wake_sends_headline_as_text_and_details_as_embed():
    card = build_incident_card(INC, decision=GatewayDecision(decision="escalated", reason="action budget used up"),
                               health=HEALTH, proposal=ROLLBACK)
    bot = Sent()
    await bot.wake(card, "action budget used up")
    text, embed, wake = bot.sent[0]
    assert wake and text == "36% of payment requests are failing. The agent changed nothing."
    assert embed.title == "NEEDS YOU · payment" and "budget used up" not in json.dumps(embed.to_dict())
    await bot.wake(card, "Approval expired; no action taken")
    assert bot.sent[1][1].fields[-1].value == "Nobody approved in time. The agent changed nothing."


# events from before embeds (and re-pages of them) carry no fields: plain text as before
async def test_old_card_without_fields_still_sends_text():
    bot = Sent()
    await bot.wake(Card(incident_id="i", status="WOKE YOU BECAUSE", text="old card", evidence_ids=[]), "b")
    assert bot.sent == [("old card\nb", None, True)]


# live inc-1794564403607: the store came back but the page read "UNDO FAILED ... half changed"
def test_no_safe_undo_says_the_fix_was_kept():
    said = explain("no safe undo (undo would scale valkey-cart to 0 replicas, outside the allowed 1-3); "
                   "fix kept after: did not recover")
    assert "kept" in said and "undid" not in said


# security review: a schema refusal echoes the model's own input; text in it must not unlock a command
def test_schema_refusal_never_gets_a_paste_ready_command():
    raise_limit = ROLLBACK.model_copy(update={"tool": "restart_service", "target": "payment", "prediction": None})
    card = build_incident_card(INC, pattern="resource", proposal=raise_limit, decision=GatewayDecision(
        decision="escalated", failed_step="schema",
        reason="1 validation error: action budget used up [type=literal_error, input_value='x']"))
    assert "kubectl" not in everything(card)
    assert field(card, "Blocked proposal (not run)")


# security review: names in a reason reach a Discord page; markdown or links in them must not
@pytest.mark.parametrize("reason", [
    "[click](https://evil.example) changed by @everyone",
    "deployment/payment changed by [boss](https://evil.example)",
    "**urgent** is protected; a human must act",
])
def test_reason_names_with_markdown_never_reach_the_page(reason):
    said = explain(reason)
    assert not any(c in said for c in "[]()*`") and "evil.example" not in said


# security review: stripping after link removal rebuilt a link ("ht`tp" -> "http"); scheme case varied
@pytest.mark.parametrize("reason", ["odd ht`tp://evil.example/x", "odd HTTPS://evil.example", "odd <https://evil.example>",
                                    "odd h*t*t*p*s://evil.example"])
def test_fallback_reason_never_carries_a_link(reason):
    said = explain(reason)
    assert "evil.example" not in said and "://" not in said
