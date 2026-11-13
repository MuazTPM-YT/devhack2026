# approval rows (IMPLEMENTATION.md §6.4.8). The gateway re-runs its checks on approve; this file only stores.
import json
import os
import sqlite3
import uuid

REHEARSAL_APPROVER = "rehearsal-harness"


# ONCALL_APPROVER_IDS, plus the rehearsal identity only when ONCALL_REHEARSAL=1 (Q3)
def approvers_from_env() -> set[str]:
    raw = os.environ.get("ONCALL_APPROVER_IDS", "")
    ids = {v.strip() for v in raw.split(",") if v.strip()}
    if not ids:
        raise RuntimeError("missing required env var(s): ONCALL_APPROVER_IDS")
    if REHEARSAL_APPROVER in ids:
        raise RuntimeError(f"{REHEARSAL_APPROVER} is forbidden in ONCALL_APPROVER_IDS")
    if os.environ.get("ONCALL_REHEARSAL") == "1":
        ids.add(REHEARSAL_APPROVER)
    return ids


# intent_id only with orchestration (migration v2 adds the column); legacy rows never name one
def create(conn: sqlite3.Connection, incident_id: str, action: dict, now: float, expiry_s: float,
           intent_id: str | None = None) -> dict:
    row = {"id": uuid.uuid4().hex[:12], "incident_id": incident_id, "action_json": json.dumps(action),
           "created_at": now, "expires_at": now + expiry_s, "state": "pending", "decided_by": None}
    if intent_id is not None:
        row["intent_id"] = intent_id
    conn.execute(f"INSERT INTO approvals ({', '.join(row)}) VALUES ({', '.join(':' + k for k in row)})", row)
    conn.commit()
    return row


def get(conn: sqlite3.Connection, approval_id: str) -> dict | None:
    r = conn.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
    return dict(r) if r else None


def set_state(conn: sqlite3.Connection, approval_id: str, state: str, decided_by: str | None) -> None:
    conn.execute("UPDATE approvals SET state=?, decided_by=? WHERE id=?", (state, decided_by, approval_id))
    conn.commit()
