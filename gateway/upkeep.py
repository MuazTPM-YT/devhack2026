# background upkeep (§6.4.8 expiry, §6.4.10 watchdog). Methods of Gateway (gateway/checklist.py binds them)
import asyncio
import json
import logging
from typing import TYPE_CHECKING

from gateway import approvals, trust
from gateway.executor import (
    WriteRefused,
)
from schemas.models import ActionRequest, Receipt

if TYPE_CHECKING:
    from gateway.checklist import Gateway

log = logging.getLogger("gateway")


# ---- background upkeep (§6.4.8 expiry, §6.4.10 watchdog) ------------------------------------

async def expire_approvals(self: "Gateway") -> int:
    now = self.clock()
    with self.lock:
        rows = [dict(r) for r in self.conn.execute(
            "SELECT * FROM approvals WHERE state='pending' AND expires_at < ?", (now,))]
    for r in rows:
        approvals.set_state(self.conn, r["id"], "expired", None)
        action = ActionRequest.model_validate_json(r["action_json"])
        await self.publish({"type": "approval_decided", "incident_id": action.incident_id,
                            "payload": {"approval_id": r["id"], "decision": "expired"}})
        await self.stop(action, self.incident(action.incident_id), [], "approval", "escalated",
                        "approval expired", sent_by=("gateway", "approval expiry"))
        if self.intents is not None and r.get("intent_id"):
            await self.moved(r["intent_id"], "terminal", reason="approval expired")
    return len(rows)


# an action older than 180 s whose verifier stopped ticking gets undone and a human woken

async def watchdog(self: "Gateway", stale_after_s: float = 180, heartbeat_s: float = 30) -> int:
    now = self.clock()
    with self.lock:
        rows = [dict(r) for r in self.conn.execute(
            "SELECT * FROM receipts WHERE outcome='pending' AND ts < ?", (now - stale_after_s,))]
    done = 0
    for r in rows:
        beat = self.heartbeats.get(r["id"])
        if beat is not None and now - beat <= heartbeat_s:
            continue
        if (task := self.verifying.pop(r["id"], None)) is not None:
            task.cancel()
        inverse, gate = json.loads(r["inverse_json"]), json.loads(r["trust_json"] or "{}")
        row = self.incident(r["incident_id"]) or {"id": r["incident_id"]}
        reason = f"watchdog: verifier silent for receipt #{r['id']}"
        if inverse.get("op") == "none":
            # nothing safe to undo (a store scaled back from 0): keep the fix, page, don't block (Muaz chose);
            # losing track says nothing about the fix, so no trust failure
            view = self.receipts.get(r["id"])
            lost = ActionRequest(incident_id=r["incident_id"], tool=r["tool"], target=r["target"],
                                 pattern=gate.get("pattern") or "unknown",
                                 evidence_ids=view.evidence_ids if view else [])
            await self.keep_and_page(r["id"], lost, row, view or Receipt(
                incident_id=r["incident_id"], tool=r["tool"], target=r["target"], diff={}, inverse=inverse,
                evidence_ids=[]), f"{reason}; no safe undo, fix kept", failure=False,
                sent_by=("watchdog", "lost verifier"))
            self.set_state(r["incident_id"], "escalated")
            done += 1
            continue
        try:
            await asyncio.to_thread(self.undo, r["target"], inverse, inverse["op"] == "restore_template")
            outcome = "undone"
        except WriteRefused as e:
            reason, outcome = f"{reason}; UNDO FAILED ({e.reason})", "pending"
            log.error("receipt #%s: %s", r["id"], reason)
        with self.lock:
            self.conn.execute("UPDATE receipts SET outcome=? WHERE id=?",
                              ("undone" if outcome == "undone" else "watchdog_failed", r["id"]))
            if outcome == "undone" and gate.get("approved_by") != approvals.REHEARSAL_APPROVER:
                trust.record(self.conn, gate.get("pattern"), r["tool"], r["target"], "real", False, now)
            self.conn.commit()
        if (view := self.receipts.get(r["id"])) is not None:  # the /receipts page reads the view
            view = view.model_copy(update={"outcome": "undone" if outcome == "undone" else "undo_failed"})
            self.receipts.update(r["id"], view)
        self.heartbeats.pop(r["id"], None)
        if outcome == "undone":
            await self.publish({"type": "action_undone", "incident_id": r["incident_id"],
                                "payload": {"receipt_id": r["id"], "reason": "watchdog"}})
        self.set_state(r["incident_id"], "escalated")
        card = self.card(row, r["target"], receipt=view, receipt_id=r["id"] if view else None, reason=reason)
        await self.publish({"type": "escalated", "incident_id": r["incident_id"],
                            "payload": {"card": card.model_dump(mode="json"), "briefing": reason,
                                        **self.guidance(r["incident_id"], gate.get("pattern"), r["tool"],
                                                        r["target"]),
                                        **self.facts(r["incident_id"], row, "watchdog", "lost verifier")}})
        done += 1
    return done


async def upkeep(self: "Gateway", every_s: float = 5) -> None:
    while True:
        try:
            await self.expire_approvals()
            await self.watchdog()
            await self.retry_timeouts()
            if self.intents is not None:
                await self.sync_intents()
                await self.drain_intents()
        except Exception as e:  # never let upkeep die quietly
            log.error("upkeep failed: %r", e)
        await asyncio.sleep(every_s)
