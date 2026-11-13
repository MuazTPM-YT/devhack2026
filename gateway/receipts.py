# receipts: the display copy of every executed action (SQLite) and its read routes. The card text lives in
# gateway/cards.py; its names are re-exported here so older imports keep working
import json
import sqlite3
from pathlib import Path

from fastapi import APIRouter, HTTPException

from brain.redact import redact_value
from gateway.cards import (REASONS as REASONS, build_card as build_card,
                           build_incident_card as build_incident_card, explain as explain, source as source,
                           started_by as started_by)
from schemas.models import Receipt


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
