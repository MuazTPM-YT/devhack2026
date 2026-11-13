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

    def get(self, receipt_id: int) -> Receipt | None:
        with self.connect() as db:
            row = db.execute("SELECT body FROM receipt_views WHERE id=?", (receipt_id,)).fetchone()
        return Receipt.model_validate_json(row[0]) if row else None


# plain words for the human reading the card; keys are Pattern and Cause.cause_class values
WHY = {
    "recent_change": "a change to {svc} landed just before it started failing",
    "resource": "{svc} ran out of memory or CPU",
    "resource_exhaustion": "{svc} ran out of memory or CPU",
    "failing_dependency": "something {svc} depends on is failing",
    "protected": "{svc} is a protected datastore, so the agent may not touch it",
    "unknown": "no clear cause found yet",
}
DID = {
    "rollback_deploy": "rolled {svc} back to its previous version",
    "revert_config": "set the changed feature flag for {svc} back",
    "restart_service": "restarted {svc}",
    "scale": "changed how many copies of {svc} run",
    "raise_limit": "raised the memory limit of {svc}",
    "enable_degraded_mode": "switched {svc} to degraded mode",
}
HEADLINE = {
    "FIXED": "{svc} is healthy again",
    "RECOVERED; PREDICTION FAILED": "{svc} is healthy again, but not proven, so the agent earns no trust",
    "WOKE YOU BECAUSE": "{svc} is failing and the agent did not fix it",
    "HANDED OFF": "someone else changed {svc}, so the agent stepped back",
    "VERIFICATION PENDING": "the agent acted on {svc} and is checking the result",
    "NEEDS APPROVAL": "{svc} is failing; the agent wants your OK before it acts",
    "NO ACTION": "{svc} is failing; policy refused the agent's action",
    "MITIGATED, NOT FIXED": "{svc} is up again after a restart, but the cause is still there",
}


def one_line(text: object) -> str:
    return " ".join(redact_value(str(text)).split())


def shorten(text: str, limit: int = 220) -> str:
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "..."


def duration(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s}s" if m else f"{s}s"


def status_of(receipt: Receipt) -> str:
    proven = receipt.outcome == "success" and receipt.prediction_held is True and receipt.harm_clean is True
    return "FIXED" if proven else {
        "undone": "WOKE YOU BECAUSE", "handed_off": "HANDED OFF",
        "right_by_accident": "RECOVERED; PREDICTION FAILED",
    }.get(receipt.outcome, "VERIFICATION PENDING")


def checked(receipt: Receipt) -> str:
    held, harm = receipt.prediction_held, receipt.harm_clean
    parts = ["no prediction was made" if held is None else
             "its prediction held" if held else "its prediction did not hold",
             "side effects not checked yet" if harm is None else
             "nothing else changed or got worse" if harm else "something else changed or got worse"]
    if receipt.outcome == "undone":
        parts.append("the agent undid its change")
    elif receipt.elapsed_s is not None and receipt.outcome in ("success", "right_by_accident"):
        parts.append(f"healthy {duration(receipt.elapsed_s)} after the action")
    return "; ".join(parts)


# a command the human can run, or why there is nothing to run; only plain k8s names go into a command
def undo(receipt: Receipt, target: str) -> str:
    if receipt.outcome == "undone":
        return "nothing to do, the agent already undid it"
    if receipt.tool == "restart_service":
        return "nothing to undo, a restart changes no settings"
    if not re.fullmatch(r"[a-z0-9-]+", target):
        return "see the receipt for the saved previous state"
    if receipt.tool in ("rollback_deploy", "raise_limit"):
        return f"kubectl rollout undo deploy/{target} -n {NAMESPACE}"
    if receipt.tool == "scale" and isinstance(receipt.inverse.get("replicas"), int):
        return f"kubectl scale deploy/{target} -n {NAMESPACE} --replicas={receipt.inverse['replicas']}"
    return "see the receipt for the saved previous state"


def build_card(receipt: Receipt, receipt_id: int) -> Card:
    return build_incident_card(Incident(id=receipt.incident_id, opened_at=0, onset_at=0, unhealthy=[receipt.target],
                                        culprit=receipt.target, severity=0), receipt=receipt, receipt_id=receipt_id)


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
                        receipt_id: int | None = None, mitigated: bool = False,
                        pattern: str | None = None, why: str | None = None) -> Card:
    status = status_of(receipt) if receipt else "WOKE YOU BECAUSE"
    if decision:
        status = {"awaiting_approval": "NEEDS APPROVAL", "handed_off": "HANDED OFF",
                  "escalated": "WOKE YOU BECAUSE", "refused": "NO ACTION"}.get(decision.decision, status)
    if mitigated:
        status = "MITIGATED, NOT FIXED"
    svc = one_line(incident.culprit or (receipt.target if receipt else "") or "an unknown service")
    causes = diagnosis.causes if diagnosis else []
    ids = list(dict.fromkeys((receipt.evidence_ids if receipt else []) + [v for c in causes for v in c.evidence_ids]))
    refs = " ".join(f"[{one_line(v)}]" for v in ids)
    # the model's own sentence when we have one; the pattern template otherwise
    said = one_line(causes[0].explanation if causes else (why or ""))
    reason = causes[0].cause_class if causes else (pattern or "unknown")
    why = shorten(said) if said else WHY.get(reason, WHY["unknown"]).format(svc=svc)
    if receipt and receipt_id is not None:
        target = one_line(receipt.target)
        did = f"{DID.get(receipt.tool, receipt.tool).format(svc=target)} (receipt #{receipt_id})"
        last = f"Undo: {undo(receipt, target)}"
        check = checked(receipt)
    else:
        did = "nothing yet"
        last = "Next: " + ("press Approve or Reject" if status == "NEEDS APPROVAL"
                           else "read the evidence and take over")
        check = "verification not run, no action taken"
    headline = f"{status}: {HEADLINE.get(status, '{svc}').format(svc=svc)}"
    if incident.major:
        status = f"MAJOR INCIDENT: {status}"
        headline = f"MAJOR INCIDENT: {headline}"
    text = "\n".join([headline, f"Why: {why} {refs}".rstrip(), f"Did: {did}", f"Checked: {check}", last])
    return Card(incident_id=incident.id, status=status, text=text, evidence_ids=ids)
