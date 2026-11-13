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


# live discord: "Why: unknown" on every gateway card; with no journal fact the pattern still says something
def test_why_without_journal_fact_uses_pattern_not_unknown():
    text = build_incident_card(INC, receipt=receipt(outcome="right_by_accident", prediction_held=False),
                               receipt_id=2, pattern="recent_change").text
    assert text.splitlines()[1] == "Why: a change to payment landed just before it started failing [journal:7]"
    assert "unknown" not in text


# the model read untrusted evidence: its sentence comes after our fact, labelled, on one line
def test_llm_explanation_is_labelled_after_the_fixed_sentence():
    cause = Cause(cause_class="recent_change", culprit="payment", evidence_ids=["journal:7"],
                  explanation="image changed to v2-bad\n30 s before errors")
    text = build_incident_card(INC, Diagnosis(causes=[cause], confidence=0.8),
                               decision=GatewayDecision(decision="escalated")).text
    assert ("Why: a change to payment landed just before it started failing. "
            "Model says: image changed to v2-bad 30 s before errors [journal:7]") in text
    assert len(text.splitlines()) == 5


def test_journal_fact_stays_first_when_the_model_also_speaks():
    line = build_incident_card(INC, receipt=receipt(), receipt_id=2, why="payment image changed to v2-bad",
                               model_says="bad image broke payment").text.splitlines()[1]
    assert line == "Why: payment image changed to v2-bad. Model says: bad image broke payment [journal:7]"


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
    lines = build_incident_card(INC, receipt=receipt(target="pay;rm -rf"), receipt_id=5).text.splitlines()
    assert "kubectl" not in lines[4]


# gateway reads the LLM's sentence from the incident row the brain wrote
def test_llm_why_reaches_gateway_cards_labelled(tmp_path):
    from test_gateway import World
    w = World(tmp_path)
    w.conn.execute("UPDATE incidents SET pattern='recent_change', llm_why='payment image went bad, errors 40 s later.'")
    row = dict(w.conn.execute("SELECT * FROM incidents").fetchone())
    line = w.gw.card(row, "payment", receipt=receipt(), receipt_id=2).text.splitlines()[1]
    assert line == ("Why: a change to payment landed just before it started failing. "
                    "Model says: payment image went bad, errors 40 s later. [journal:7]")
