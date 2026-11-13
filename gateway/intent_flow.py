# orchestration intents (handoff §9): durable action requests the checklist runs one by one. Methods of Gateway (gateway/checklist.py binds them)
import json
import logging
from typing import TYPE_CHECKING, Any

from gateway import policy
from gateway.intents import submission
from gateway.shared import _intent
from schemas.models import ActionRequest, GatewayDecision
from schemas.orchestration import IntentEnvelope, IntentSubmission

if TYPE_CHECKING:
    from gateway.checklist import Gateway

log = logging.getLogger("gateway")


# ---- orchestration intents (handoff §9) ------------------------------------------------------------

async def moved(self: "Gateway", intent_id: str, to: str, **fields: Any) -> bool:
    assert self.intents is not None
    if not self.intents.move(intent_id, to, **fields):
        return False
    row = self.intents.get(intent_id)
    assert row is not None
    await self.publish({"type": "action_intent_changed", "incident_id": row["incident_id"], "payload": {
        "intent_id": intent_id, "status": to, "plan_revision": row["plan_revision"],
        "approval_id": row["approval_id"], "receipt_id": row["receipt_id"], "reason": row["reason"]}})
    return True


# why this intent may no longer run; None while it is the brain's current plan

def stale_intent(self: "Gateway", intent_id: str) -> str | None:
    assert self.intents is not None
    row = self.intents.get(intent_id)
    if row is None:
        return "unknown intent"
    if row["status"] == "superseded":
        return "superseded by a newer plan"
    current = self.intents.current_plan(row["incident_id"])
    if current is not None and current != row["plan_revision"]:
        return f"plan {row['plan_revision']} replaced by plan {current}"
    return None


def slot_busy(self: "Gateway") -> bool:
    with self.lock:
        used = policy.usage(self.conn, "", self.clock())["in_flight"]
    return used >= self.policy["budgets"]["max_in_flight"]


# step 3's "asking": these end in an approval request, so a busy slot does not hold them back

def will_ask(self: "Gateway", action: ActionRequest) -> bool:
    protected = bool(self.services.get(action.target, {}).get("protected"))
    return (self.policy["tools"].get(action.tool, {}).get("auto_eligible") is False or protected
            or action.origin == "model")


async def submit_intent(self: "Gateway", env: IntentEnvelope) -> IntentSubmission:
    if self.intents is None:
        raise RuntimeError("orchestration intents are off in this gateway")
    row, created = self.intents.create_or_get(env)  # Conflict when the id holds another action
    if not created:
        return submission(row)
    steps: list[dict] = []
    await self.step(env.incident_id, steps, "schema", True)
    return await self.run_intent(row, steps)


# busy slot: queue, never refuse; the queue drains in upkeep and reruns the whole checklist then

async def run_intent(self: "Gateway", row: dict, steps: list[dict]) -> IntentSubmission:
    assert self.intents is not None
    intent_id = row["intent_id"]
    action = ActionRequest.model_validate_json(row["action_json"])
    async with self.run_lock:
        if stale := self.stale_intent(intent_id):
            await self.moved(intent_id, "superseded", reason=stale)
        elif self.slot_busy() and not self.will_ask(action):
            if row["status"] != "queued":
                await self.moved(intent_id, "queued", reason="another action is being verified")
        else:
            token = _intent.set(intent_id)
            try:
                decision = await self._run(action, steps, approved=False)
            finally:
                _intent.reset(token)
            await self.settle_intent(intent_id, decision)
    latest = self.intents.get(intent_id)
    assert latest is not None
    return submission(latest)


# the checklist ended without a write or an approval request: the intent ends with it

async def settle_intent(self: "Gateway", intent_id: str, decision: GatewayDecision) -> None:
    assert self.intents is not None
    row = self.intents.get(intent_id)
    if row is None or row["status"] not in ("new", "queued", "awaiting_approval"):
        return
    if decision.decision == "awaiting_approval":
        return
    await self.moved(intent_id, "terminal", reason=f"{decision.decision}: {decision.reason or decision.failed_step}")


async def drain_intents(self: "Gateway") -> None:
    assert self.intents is not None
    row = self.intents.oldest("queued")
    if row is not None and not self.slot_busy():
        await self.run_intent(row, [])


# verification finished (any path: close, undo, keep and page, watchdog): the intent is done

async def sync_intents(self: "Gateway") -> None:
    assert self.intents is not None
    for row in self.intents.with_status("verifying"):
        with self.lock:
            r = self.conn.execute("SELECT outcome FROM receipts WHERE id=?", (row["receipt_id"],)).fetchone()
        if r is not None and r["outcome"] not in ("pending", "watchdog_failed"):
            await self.moved(row["intent_id"], "terminal", reason=f"receipt #{row['receipt_id']}: {r['outcome']}")


# services this action answers for, and services another open incident broke on its own before it

def verification_scope(self: "Gateway", action: ActionRequest, row: dict, plan: dict) -> dict:
    victims = json.loads(row.get("victims_json") or "[]")
    with self.lock:
        own = {r[0] for r in self.conn.execute(
            "SELECT service FROM incident_memberships WHERE incident_id=?", (action.incident_id,))}
        others = self.conn.execute(
            "SELECT m.service, e.first_breach_at, e.sustained_at FROM incident_memberships m "
            "JOIN signal_episodes e ON e.episode_id = m.episode_id "
            "JOIN orchestration_workspaces w ON w.incident_id = m.incident_id "
            "WHERE m.closed = 0 AND m.incident_id != ? AND w.phase != 'terminal'", (action.incident_id,)).fetchall()
    mine = {action.target, *victims, *own, *(plan.get("blast") or {}).get("upstream", [])}
    now = self.clock()
    unrelated = {r["service"] for r in others if (r["first_breach_at"] or r["sustained_at"]) < now} - mine
    return {"services": sorted(mine), "unrelated": sorted(unrelated)}


# restart: a write that started but left no receipt is unknown; never replay it, never undo it blind

async def reconcile_intents(self: "Gateway") -> list[str]:
    if self.intents is None:
        return []
    unknown = []
    for row in self.intents.with_status("executing"):
        action = ActionRequest.model_validate_json(row["action_json"])
        with self.lock:
            rec = self.conn.execute("SELECT id FROM receipts WHERE incident_id=? AND tool=? AND target=? AND "
                                    "ts >= ? ORDER BY ts LIMIT 1", (row["incident_id"], action.tool, action.target,
                                                                    row["executing_at"] or 0)).fetchone()
        if rec is not None:  # receipted: the watchdog takes over the lost verifier
            await self.moved(row["intent_id"], "verifying", receipt_id=rec["id"])
            continue
        why = (f"gateway restarted during the write of intent {row['intent_id']}; outcome unknown. Check "
               f"{action.target} by hand, then clear the intent")
        await self.moved(row["intent_id"], "execution_unknown", reason=why)
        if (inc := self.incident(row["incident_id"])) is not None:
            await self.stop(action, inc, [], "execute", "escalated", why)
        unknown.append(row["intent_id"])
    with self.lock:
        receipted = {r[0] for r in self.conn.execute("SELECT id FROM receipts")}
    orphans = [rid for rid, _ in self.receipts.recent(1000) if rid not in receipted]
    if orphans:
        log.error("receipt views without a receipt row (crash between the two writes): %s", orphans)
    return unknown


# an approver checked the cluster after an unknown write: the slot frees, audited

async def clear_intent(self: "Gateway", intent_id: str, decided_by: str) -> dict:
    if self.intents is None or decided_by not in self.approvers:
        return {"cleared": False, "reason": "not an approver" if self.intents else "orchestration off"}
    row = self.intents.get(intent_id)
    if row is None or row["status"] != "execution_unknown":
        return {"cleared": False, "reason": f"intent is {row['status'] if row else 'unknown'}"}
    await self.moved(intent_id, "terminal", reason=f"cleared by {decided_by} after checking the cluster")
    await self.publish({"type": "checklist_step", "incident_id": row["incident_id"], "payload": {
        "name": "human_clear", "passed": True, "reason": f"intent {intent_id} cleared by {decided_by}"}})
    return {"cleared": True}
