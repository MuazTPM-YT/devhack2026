# durable action intents (handoff §9): one identity per proposed execution, its state across approval,
# queue, write and verification, and what to do when a write's outcome is unknown. The gateway owns these.
import json
import sqlite3
import threading
import time
from collections.abc import Callable
from typing import Any

from schemas.orchestration import IntentEnvelope, IntentSubmission

# what an intent may move to from each state; anything else is a bug or a race lost
MOVES: dict[str, set[str]] = {
    "new": {"queued", "awaiting_approval", "executing", "terminal", "superseded", "refused"},
    "queued": {"executing", "awaiting_approval", "terminal", "superseded", "refused"},
    "awaiting_approval": {"executing", "terminal", "superseded", "refused", "awaiting_approval"},
    "executing": {"verifying", "terminal", "execution_unknown"},
    "verifying": {"terminal"},
    "execution_unknown": {"terminal"},
}
HOLDS_SLOT = ("executing", "execution_unknown")  # an unknown write blocks the slot until a human clears it


class Conflict(Exception):
    pass


class IntentStore:
    def __init__(self, conn: sqlite3.Connection, lock: threading.Lock, clock: Callable[[], float] = time.time):
        self.conn, self.lock, self.clock = conn, lock, clock

    def get(self, intent_id: str) -> dict[str, Any] | None:
        with self.lock:
            r = self.conn.execute("SELECT * FROM action_intents WHERE intent_id=?", (intent_id,)).fetchone()
        return dict(r) if r else None

    # same id + same fingerprint: the stored one; same id, other payload: Conflict; another id for the very
    # same execution: the stored one too, so a retry with a fresh id still runs once
    def create_or_get(self, env: IntentEnvelope) -> tuple[dict[str, Any], bool]:
        now = self.clock()
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                old = self.conn.execute("SELECT * FROM action_intents WHERE intent_id=? OR (incident_id=? AND "
                                        "fingerprint=?)", (env.intent_id, env.incident_id, env.fingerprint)).fetchone()
                if old is not None:
                    self.conn.rollback()
                    if old["fingerprint"] != env.fingerprint:
                        raise Conflict(f"intent {env.intent_id} already holds another action")
                    return dict(old), False
                self.conn.execute(
                    "INSERT INTO action_intents (intent_id, incident_id, fingerprint, scope_revision, plan_revision, "
                    "action_json, parent_intent_id, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,'new',?,?)",
                    (env.intent_id, env.incident_id, env.fingerprint, env.scope_revision, env.plan_revision,
                     env.action.model_dump_json(), env.parent_intent_id, now, now))
                self.conn.commit()
            except BaseException:
                if self.conn.in_transaction:
                    self.conn.rollback()
                raise
        row = self.get(env.intent_id)
        assert row is not None
        return row, True

    # compare-and-swap on status; False when the intent already moved (superseded, cleared, raced)
    def move(self, intent_id: str, to: str, **fields: Any) -> bool:
        allowed = {"approval_id", "receipt_id", "reason", "precondition_json", "executing_at"}
        if bad := set(fields) - allowed:
            raise ValueError(f"not an intent field: {sorted(bad)}")
        sources = [s for s, targets in MOVES.items() if to in targets]
        sets = "".join(f", {k}=?" for k in fields)
        with self.lock:
            cur = self.conn.execute(
                f"UPDATE action_intents SET status=?, updated_at=?{sets} WHERE intent_id=? AND status IN "
                f"({','.join('?' * len(sources))})", (to, self.clock(), *fields.values(), intent_id, *sources))
            self.conn.commit()
            return cur.rowcount == 1

    def oldest(self, status: str) -> dict[str, Any] | None:
        with self.lock:
            r = self.conn.execute("SELECT * FROM action_intents WHERE status=? ORDER BY created_at, rowid LIMIT 1",
                                  (status,)).fetchone()
        return dict(r) if r else None

    def with_status(self, *statuses: str) -> list[dict[str, Any]]:
        with self.lock:
            return [dict(r) for r in self.conn.execute(
                f"SELECT * FROM action_intents WHERE status IN ({','.join('?' * len(statuses))}) ORDER BY created_at",
                statuses)]

    # the brain's current plan for this incident; None when there is no workspace (legacy incident)
    def current_plan(self, incident_id: str) -> int | None:
        with self.lock:
            r = self.conn.execute("SELECT plan_revision, phase FROM orchestration_workspaces WHERE incident_id=?",
                                  (incident_id,)).fetchone()
        return None if r is None else int(r["plan_revision"])

    def first_for(self, incident_id: str, plan_revision: int) -> str | None:
        with self.lock:
            r = self.conn.execute("SELECT intent_id FROM action_intents WHERE incident_id=? AND plan_revision=? "
                                  "AND parent_intent_id IS NULL ORDER BY created_at LIMIT 1",
                                  (incident_id, plan_revision)).fetchone()
        return r[0] if r else None


def submission(row: dict[str, Any]) -> IntentSubmission:
    return IntentSubmission.model_validate({"intent_id": row["intent_id"], "reason": row.get("reason"),
                                            "status": "queued" if row["status"] == "new" else row["status"],
                                            "approval_id": row.get("approval_id"),
                                            "receipt_id": row.get("receipt_id")})


def precondition(plan: dict) -> str:
    live = plan.get("live") or {}
    return json.dumps({"resource_version": (live.get("metadata") or {}).get("resourceVersion"),
                       "declared": plan.get("declared"), "hashes": plan.get("hashes")}, sort_keys=True, default=str)
