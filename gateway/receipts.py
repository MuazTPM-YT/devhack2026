import json
import sqlite3
from pathlib import Path

from fastapi import APIRouter, HTTPException

from brain.redact import redact_value
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

    def get(self, receipt_id: int) -> Receipt | None:
        with self.connect() as db:
            row = db.execute("SELECT body FROM receipt_views WHERE id=?", (receipt_id,)).fetchone()
        return Receipt.model_validate_json(row[0]) if row else None


def build_card(receipt: Receipt, receipt_id: int) -> Card:
    proven = receipt.outcome == "success" and receipt.prediction_held is True and receipt.harm_clean is True
    status = "FIXED" if proven else {
        "undone": "WOKE YOU BECAUSE", "handed_off": "HANDED OFF",
        "right_by_accident": "RECOVERED; PREDICTION FAILED",
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

    @router.get("/receipts/{receipt_id}")
    def get(receipt_id: int):
        receipt = store.get(receipt_id)
        if receipt is None:
            raise HTTPException(404, "Receipt not found")
        return {"id": receipt_id, "receipt": receipt, "card": build_card(receipt, receipt_id)}

    return router


def build_incident_card(incident: Incident, diagnosis: Diagnosis | None = None,
                        decision: GatewayDecision | None = None, receipt: Receipt | None = None,
                        receipt_id: int | None = None, mitigated: bool = False) -> Card:
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
    cause_class = causes[0].cause_class if causes else "unknown"
    def clean(text):
        return " ".join(redact_value(str(text)).split())
    refs = " ".join(f"[{clean(value)}]" for value in ids) or "none supplied"
    action = f"{receipt.tool} on {clean(receipt.target)}; receipt #{receipt_id}" if receipt else "nothing"
    check = (f"prediction={receipt.prediction_held}; harm clean={receipt.harm_clean}"
             if receipt else "verification not run")
    undo = f"inspect receipt #{receipt_id}; request gateway approval" if receipt else "inspect evidence before approving"
    card.text = "\n".join([
        f"{card.status}: {clean(incident.culprit or 'cause unknown')}",
        f"Why: {cause_class}; evidence {refs}",
        f"Did: {action}", f"Checked: {check}", f"Undo / ask: {undo}",
    ])
    card.evidence_ids = ids
    return card
