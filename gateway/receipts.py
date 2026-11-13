import json
import re
import sqlite3
from pathlib import Path

from fastapi import APIRouter, HTTPException

from brain.redact import redact_value
from gateway.executor import NAMESPACE
from schemas.models import Card, Diagnosis, GatewayDecision, Incident, Receipt


class ReceiptStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS receipt_views (id INTEGER PRIMARY KEY, body TEXT NOT NULL)")

    def connect(self):
        return sqlite3.connect(self.path)

    # store display data; executor keeps its undo snapshot separately
    def save(self, receipt: Receipt) -> int:
        with self.connect() as db:
            cursor = db.execute("INSERT INTO receipt_views(body) VALUES (?)",
                                (json.dumps(redact_value(receipt.model_dump(mode="json"))),))
            return int(cursor.lastrowid)

    # the verifier fills outcome / prediction_held / harm_clean once it decides
    def update(self, receipt_id: int, receipt: Receipt) -> None:
        with self.connect() as db:
            db.execute("UPDATE receipt_views SET body=? WHERE id=?",
                       (json.dumps(redact_value(receipt.model_dump(mode="json"))), receipt_id))

    # newest first, for the UI's /receipts page
    def recent(self, limit: int = 100) -> list[tuple[int, Receipt]]:
        with self.connect() as db:
            rows = db.execute("SELECT id, body FROM receipt_views ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [(row[0], Receipt.model_validate_json(row[1])) for row in rows]

    def get(self, receipt_id: int) -> Receipt | None:
        with self.connect() as db:
            row = db.execute("SELECT body FROM receipt_views WHERE id=?", (receipt_id,)).fetchone()
        return Receipt.model_validate_json(row[0]) if row else None


def build_card(receipt: Receipt, receipt_id: int) -> Card:
    proven = receipt.outcome == "success" and receipt.prediction_held is True and receipt.harm_clean is True
    status = "FIXED" if proven else {
        "undone": "WOKE YOU BECAUSE", "undo_failed": "WOKE YOU BECAUSE", "handed_off": "HANDED OFF",
        "right_by_accident": "RECOVERED; PREDICTION FAILED" if receipt.prediction_held is False
        else "RECOVERED; NO PREDICTION",
    }.get(receipt.outcome, "VERIFICATION PENDING")
    refs = " ".join(f"[{' '.join(value.split())}]" for value in receipt.evidence_ids)
    text = "\n".join([
        f"{status}: {' '.join(receipt.target.split())}",
        f"Evidence: {refs or 'not supplied'}",
        f"Did: {receipt.tool}; receipt #{receipt_id}",
        f"Checked: prediction={receipt.prediction_held}; harm clean={receipt.harm_clean}",
        f"Undo: inspect receipt #{receipt_id} and request gateway approval",
    ])
    return Card(incident_id=receipt.incident_id, status=status,
                text=redact_value(text), evidence_ids=receipt.evidence_ids)


def create_receipts_router(store: ReceiptStore) -> APIRouter:
    router = APIRouter()

    @router.get("/receipts")
    def recent(limit: int = 100):
        return [{"id": i, "receipt": r, "card": build_card(r, i)} for i, r in store.recent(min(max(limit, 1), 500))]

    @router.get("/receipts/{receipt_id}")
    def get(receipt_id: int):
        receipt = store.get(receipt_id)
        if receipt is None:
            raise HTTPException(404, "Receipt not found")
        return {"id": receipt_id, "receipt": receipt, "card": build_card(receipt, receipt_id)}

    return router


def _took(seconds: float) -> str:
    s = max(0, int(round(seconds)))
    return f"{s // 60}m {s % 60:02d}s" if s >= 60 else f"{s}s"


# "automatic; trust 30 rehearsals, 0 real; proven at least 90%" or "approved by <id>" (plan §6.7.1)
def _mode(trust: dict) -> str:
    if trust.get("approved_by"):
        return f"approved by {trust['approved_by']}"
    rehearsal, real = trust.get("rehearsal") or [0, 0], trust.get("real") or [0, 0]
    bound = trust.get("lower_bound")
    proven = f"; proven at least {bound:.0%}" if isinstance(bound, (int, float)) else ""
    return f"automatic; trust {rehearsal[0]} rehearsals, {real[0]} real{proven}"


def _checked(receipt: Receipt) -> str:
    if receipt.outcome == "pending":
        return "verification still running"
    prediction = {True: "prediction held", False: "prediction missed", None: "no prediction to check"}
    harm = {True: "nothing else got worse", False: "harm found", None: "harm check not run"}
    parts = [prediction[receipt.prediction_held], harm[receipt.harm_clean]]
    if receipt.added_disruption_s is not None:
        forecast = f" (forecast {receipt.forecast_s:.0f} s)" if receipt.forecast_s is not None else ""
        parts.append(f"added disruption {receipt.added_disruption_s:.0f} s{forecast}")
    return "; ".join(parts)


# a command a tired human can paste to take the agent's action back; only plain k8s names go into one
def _undo(receipt: Receipt, receipt_id: int) -> str:
    op, target = receipt.inverse.get("op"), receipt.target
    if receipt.outcome in ("undone", "undo_failed"):
        return f"already undone by the agent; receipt #{receipt_id}" if receipt.outcome == "undone" \
            else f"the agent's undo FAILED; restore from receipt #{receipt_id} by hand"
    if not re.fullmatch(r"[a-z0-9-]+", target):
        return f"restore from receipt #{receipt_id} by hand"
    if op == "restore_template":
        return f"kubectl rollout undo deploy/{target} -n {NAMESPACE}"
    if op == "scale" and isinstance(receipt.inverse.get("replicas"), int):
        return f"kubectl scale deploy/{target} -n {NAMESPACE} --replicas={receipt.inverse['replicas']}"
    return f"put configmap/{receipt.inverse.get('name')} back from receipt #{receipt_id}"


# plain fallback when no journal fact explains it (keys: Pattern and Cause.cause_class)
WHY = {
    "recent_change": "a change to {svc} landed just before it started failing",
    "resource": "{svc} ran out of memory or CPU",
    "resource_exhaustion": "{svc} ran out of memory or CPU",
    "failing_dependency": "something {svc} depends on is failing",
    "protected": "{svc} is a protected datastore, so the agent may not touch it",
    "unknown": "no clear cause found yet",
}


def shorten(text: str, limit: int = 220) -> str:
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "..."


# the 5-line card (plan §6.7.1), built by code from incident, diagnosis, decision and receipt
def build_incident_card(incident: Incident, diagnosis: Diagnosis | None = None,
                        decision: GatewayDecision | None = None, receipt: Receipt | None = None,
                        receipt_id: int | None = None, mitigated: bool = False, why: str | None = None,
                        took_s: float | None = None, metric: str | None = None, did: str | None = None,
                        pattern: str | None = None, model_says: str | None = None) -> Card:
    if receipt and receipt_id is not None:
        card = build_card(receipt, receipt_id)
    else:
        card = Card(incident_id=incident.id, status="WOKE YOU BECAUSE", text="", evidence_ids=[])
    if decision:
        card.status = {"awaiting_approval": "NEEDS APPROVAL", "handed_off": "HANDED OFF",
                       "escalated": "WOKE YOU BECAUSE", "refused": "NO ACTION"}.get(decision.decision, card.status)
    if mitigated:
        card.status = "MITIGATED, NOT FIXED"
    if incident.major:
        card.status = f"MAJOR INCIDENT: {card.status}"
    causes = diagnosis.causes if diagnosis else []
    ids = list(dict.fromkeys(card.evidence_ids + [value for cause in causes for value in cause.evidence_ids]))

    def clean(text):
        return " ".join(redact_value(str(text)).split())

    # our fact first; the model read untrusted evidence, so its sentence is labelled, never alone
    kind = causes[0].cause_class if causes else (pattern or "unknown")
    reason = why or WHY.get(kind, WHY["unknown"]).format(svc=clean(incident.culprit or "the service"))
    said = clean(model_says or (causes[0].explanation if causes else ""))
    if said:
        reason = f"{clean(reason)[:300]}. Model says: {shorten(said)}"
    refs = " ".join(f"[{clean(value)}]" for value in ids) or "none supplied"
    head = f"{card.status}" + (f" in {_took(took_s)}" if took_s is not None and receipt else "")
    subject = clean(incident.culprit or "cause unknown") + (f"; {clean(metric)}" if metric else "")
    if receipt and receipt_id is not None:
        action = f"{clean(did or receipt.tool)} on {clean(receipt.target)} ({clean(_mode(receipt.trust))}). " \
                 f"Receipt #{receipt_id}"
        check, undo = _checked(receipt), _undo(receipt, receipt_id)
    else:
        action = clean(did) if did else "nothing yet"
        check, undo = "verification not run", "nothing to undo; inspect the evidence first"
    if decision and decision.reason:
        action += f" ({clean(decision.reason)[:200]})"
    card.text = "\n".join([
        f"{head}: {subject}",
        f"Why: {clean(reason)} {refs}",
        f"Did: {action}", f"Checked: {check}", f"Undo: {clean(undo)}",
    ])
    card.evidence_ids = ids
    return card
