import httpx

from gateway.receipts import build_incident_card
from notifier.consumer import NotificationConsumer
from notifier.state import NotifierState
from schemas.models import Cause, Diagnosis, GatewayDecision, Incident, Receipt

INC = Incident(id="i", opened_at=0, onset_at=0, unhealthy=["payment"], culprit="payment",
               victims=["checkout"], severity=7)


def receipt(**changes):
    base = {"incident_id": "i", "tool": "rollback_deploy", "target": "payment", "diff": {},
            "inverse": {"op": "restore_template"}, "evidence_ids": ["journal:7"], "outcome": "success",
            "prediction_held": True, "harm_clean": True, "elapsed_s": 81}
    return Receipt(**{**base, **changes})


# live discord: "Why: unknown", "prediction=False; harm clean=True" meant nothing to the human reading it
def test_fixed_card_reads_as_plain_sentences():
    lines = build_incident_card(INC, receipt=receipt(), receipt_id=2, pattern="recent_change").text.splitlines()
    assert lines == [
        "FIXED: payment is healthy again",
        "Why: a change to payment landed just before it started failing [journal:7]",
        "Did: rolled payment back to its previous version (receipt #2)",
        "Checked: its prediction held; nothing else changed or got worse; healthy 1m 21s after the action",
        "Undo: kubectl rollout undo deploy/payment -n shop",
    ]


# gateway cards carry no diagnosis; the stored pattern still explains why
def test_recovered_without_prediction_explains_no_trust_and_never_says_unknown():
    text = build_incident_card(INC, receipt=receipt(outcome="right_by_accident", prediction_held=False),
                               receipt_id=2, pattern="recent_change").text
    assert text.splitlines()[0] == ("RECOVERED; PREDICTION FAILED: payment is healthy again, "
                                    "but not proven, so the agent earns no trust")
    assert "its prediction did not hold" in text and "unknown" not in text


def test_approval_card_says_what_it_needs():
    lines = build_incident_card(INC, decision=GatewayDecision(decision="awaiting_approval"),
                                pattern="recent_change").text.splitlines()
    assert lines[0] == "NEEDS APPROVAL: payment is failing; the agent wants your OK before it acts"
    assert lines[2] == "Did: nothing yet"
    assert lines[4] == "Next: press Approve or Reject"


def test_llm_explanation_joins_the_why_line_on_one_line():
    cause = Cause(cause_class="recent_change", culprit="payment", evidence_ids=["journal:7"],
                  explanation="image changed to v2-bad\n30 s before errors")
    text = build_incident_card(INC, Diagnosis(causes=[cause], confidence=0.8),
                               decision=GatewayDecision(decision="escalated")).text
    assert "Why: image changed to v2-bad 30 s before errors [journal:7]" in text
    assert len(text.splitlines()) == 5


# discord showed "/receipts/2": a relative link nobody can click
async def test_fyi_receipt_link_is_absolute(tmp_path):
    class Notifier:
        urls: list[str] = []

        async def fyi(self, card, url):
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
    assert lines[2] == "Did: rolled valkey-cart back to its previous version (receipt #4)"
    assert lines[4] == "Undo: kubectl rollout undo deploy/valkey-cart -n shop"


def test_odd_target_name_never_becomes_a_command():
    lines = build_incident_card(INC, receipt=receipt(target="pay;rm -rf"), receipt_id=5).text.splitlines()
    assert "kubectl" not in lines[4]


# the LLM's sentence beats the template; gateway reads it from the incident row
def test_llm_why_replaces_template_on_gateway_cards(tmp_path):
    from test_gateway import World
    w = World(tmp_path)
    w.conn.execute("UPDATE incidents SET why='payment image changed to v2-bad, errors began 40 s later.'")
    row = dict(w.conn.execute("SELECT * FROM incidents").fetchone())
    line = w.gw.card(row, "payment", "recent_change", receipt=receipt(), receipt_id=2).text.splitlines()[1]
    assert line == "Why: payment image changed to v2-bad, errors began 40 s later. [journal:7]"
