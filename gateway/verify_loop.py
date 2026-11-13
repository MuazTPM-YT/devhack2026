# verification (§6.4.9): poll health, decide, undo if needed, close, credit the ledger. Methods of Gateway (gateway/checklist.py binds them)
import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any

import httpx

from gateway import approvals, trust
from gateway.dryrun import (
    namespace_hash,
    rollback_patch,
    spec_hashes,
)
from gateway.executor import (
    WriteRefused,
    list_json,
    patch_configmap,
    patch_deployment,
    patch_scale,
    read_configmap,
    read_deployment,
)
from gateway.retries import RETRY_REASONS
from gateway.shared import CHAOS_MANAGER, tier_of
from gateway.verifier import Verification, harm_check, ledger_effect
from schemas.models import ActionRequest, Receipt

if TYPE_CHECKING:
    from gateway.checklist import Gateway

log = logging.getLogger("gateway")


# "payment errors 38.0% -> 0.4%" for the card's first line: first watched service with both readings
def error_change(before: dict, after: dict | None, services: list[str]) -> str | None:
    for s in services:
        a = before.get("services", {}).get(s, {}).get("err_ratio")
        b = (after or {}).get("services", {}).get(s, {}).get("err_ratio")
        if a is not None and b is not None:
            return f"{s} errors {a:.1%} -> {b:.1%}"
    return None


# one failed fix as the brain's error context: what ran, why it was undone, what the numbers did meanwhile
def failed_try(receipt_id: int, action: ActionRequest, v: Verification, harm: dict | None, reason: str | None,
               plan: dict | None) -> dict:
    after = v.last_health.get("services", {})
    return {"receipt_id": receipt_id, "tool": action.tool, "target": action.target, "params": action.params,
            "journal_entry": action.journal_entry, "origin": action.origin, "change": (plan or {}).get("summary"),
            "why_undone": reason, "ran_s": round(v.last_ts - v.t0, 1),
            "severity_before": v.sev_before, "severity_after": v.last_health.get("severity"),
            "recovered": v.recovered, "prediction": action.prediction.model_dump() if action.prediction else None,
            "prediction_held": v.prediction_held, "worse_services": (harm or {}).get("worse_services", []),
            "readings_after": {s: {k: after.get(s, {}).get(k) for k in ("err_ratio", "p95_ms", "unhealthy")}
                               for s in v.watched}}


# ---- verification (§6.4.9): poll health, decide, undo if needed, credit the ledger ------------

async def verify(self: "Gateway", receipt_id: int, action: ActionRequest, row: dict, plan: dict, receipt: Receipt) -> str:
    victims = json.loads(row.get("victims_json") or "[]")
    cfg = self.policy["verify"]
    extra = cfg["flag_extra_seconds"] if plan["patch"]["kind"] == "configmap" else 0  # flagd reload ~60 s
    # aborting means undoing; with no safe undo, give the fix its whole window instead
    can_undo = plan["inverse"]["op"] != "none"
    scope = plan.get("scope")  # orchestration: this action's own services, frozen at execute time
    v = Verification(self.clock(), plan["health"], action.target, victims,
                     action.prediction.model_dump() if action.prediction else None,
                     cfg["window_seconds"] + extra, cfg["early_abort"] and can_undo,
                     grace_s=cfg["early_abort_grace_seconds"] + extra, prediction_delay_s=extra,
                     scope=set(scope["services"]) if scope else None)
    health, human, others, result = plan["health"], [], [], None
    while result is None:
        await asyncio.sleep(self.verify_every)
        try:
            health = await self.get_json("/health/now")
            others = [r for r in await self.get_json("/journal", since=v.t0) if not r["by_agent"]]
            # same rule as step 2: a chaos write (fault, decoy, its cleanup) is no person taking over
            human = [r for r in others if r.get("field_manager") != CHAOS_MANAGER]
            if health.get("prometheus_ok") is False:
                # stale reading = no data: decide nothing on it, let the window run (Muaz chose)
                out_of_time = self.clock() - v.t0 >= v.window_s
                result = "handed_off" if human else ("stale" if out_of_time else None)
            else:
                result = v.step(self.clock(), health, bool(human))
        except (httpx.HTTPError, ValueError, KeyError) as e:  # observer blip: keep the clock running
            log.warning("verify tick failed: %s", type(e).__name__)
            if self.clock() - v.t0 >= v.window_s:
                result = "window_end"
        self.heartbeats[receipt_id] = self.clock()
        await self.publish({"type": "verify_tick", "incident_id": action.incident_id, "payload": {
            "receipt_id": receipt_id, "severity": health.get("severity"), "recovered": v.recovered}})

    if result == "stale":  # blind to the end: keep the fix, never undo on blindness, no trust either way
        return await self.keep_and_page(receipt_id, action, row, receipt,
                                        "could not check the fix: health data stale to the end of the window",
                                        failure=False)
    if result == "handed_off":
        return await self.close(receipt_id, action, row, receipt, v, "handed_off", None,
                                f"{human[-1]['object']} changed by {human[-1]['field_manager']}", plan=plan)
    if result == "early_abort":
        await self.publish({"type": "early_abort", "incident_id": action.incident_id,
                            "payload": {"receipt_id": receipt_id, "severity": health.get("severity"),
                                        "before": v.sev_before}})
        return await self.undo_and_close(receipt_id, action, row, receipt, v, pause=True, harm=None,
                                         reason="severity rose after the action", plan=plan)
    after = await asyncio.to_thread(lambda: spec_hashes(list_json(self.apps.list_namespaced_deployment),
                                                        list_json(self.core.list_namespaced_config_map)))
    harm = harm_check(plan["hashes"], after, plan["declared"], {r["object"] for r in others},
                      plan["health"], health, {action.target, *victims, *plan["blast"].get("upstream", [])},
                      excused=frozenset(scope["unrelated"]) if scope else frozenset())
    await self.publish({"type": "harm_check", "incident_id": action.incident_id,
                        "payload": {"receipt_id": receipt_id, **harm}})
    outcome = v.outcome(harm["clean"])
    if (scope and outcome == "undo" and v.recovered and harm["declared_changed"] and not harm["unexpected_changes"]
            and harm["worse_services"]):
        # recovered, but services nobody can tie to this fix or to another incident got worse: undoing a
        # working fix is a guess too. Keep it, page, no trust either way (pending review, handoff §9.3)
        return await self.keep_and_page(receipt_id, action, row, receipt,
                                        f"recovered, but {', '.join(harm['worse_services'])} got worse and "
                                        "nothing shows why; check by hand", failure=False)
    if outcome == "undo":
        reason = "harm check failed" if v.recovered else (
            "monitoring went blind; recovery not proven" if v.blind else "did not recover")
        return await self.undo_and_close(receipt_id, action, row, receipt, v, pause=False, harm=harm,
                                         reason=reason, hash_after=namespace_hash(after), plan=plan)
    return await self.close(receipt_id, action, row, receipt, v, outcome, harm, None, namespace_hash(after),
                            plan=plan)


async def undo_and_close(self: "Gateway", receipt_id: int, action: ActionRequest, row: dict, receipt: Receipt,
                         v: Verification, pause: bool, harm: dict | None, reason: str,
                         hash_after: str | None = None, plan: dict | None = None) -> str:
    if receipt.inverse.get("op") == "none":
        return await self.keep_and_page(receipt_id, action, row, receipt, reason)
    try:
        await asyncio.to_thread(self.undo, action.target, receipt.inverse, pause)
    except WriteRefused as e:
        # terminal, else the pending receipt counts as in flight and blocks every later action
        log.error("receipt #%s: UNDO FAILED (%s)", receipt_id, e.reason)
        with self.lock:
            self.conn.execute("UPDATE receipts SET outcome='undo_failed' WHERE id=?", (receipt_id,))
            self.conn.commit()
        failed = receipt.model_copy(update={"outcome": "undo_failed"})
        self.receipts.update(receipt_id, failed)
        self.heartbeats.pop(receipt_id, None)
        self.verifying.pop(receipt_id, None)
        card = self.card(row, action.target, receipt=failed, receipt_id=receipt_id, reason="UNDO FAILED")
        await self.publish({"type": "escalated", "incident_id": action.incident_id, "payload": {
            "card": card.model_dump(mode="json"),
            "briefing": f"UNDO FAILED ({e.reason}); receipt #{receipt_id} needs a human now",
            **self.guidance(action.incident_id, action.pattern, action.tool, action.target),
            **self.facts(action.incident_id, row, "verifier", "undo")}})
        self.set_state(action.incident_id, "escalated")
        return "undo_failed"
    await self.publish({"type": "action_undone", "incident_id": action.incident_id,
                        "payload": {"receipt_id": receipt_id, "reason": reason}})
    return await self.close(receipt_id, action, row, receipt, v, "undone", harm, reason, hash_after, plan=plan)


# fix did not prove itself but undoing it is unsafe (or we could not see): leave it, hand it to a person.

# failure=False: blind to the end, which says nothing about the fix

async def keep_and_page(self: "Gateway", receipt_id: int, action: ActionRequest, row: dict, receipt: Receipt,
                        reason: str, failure: bool = True,
                        sent_by: tuple[str, str] = ("verifier", "fix check")) -> str:
    with self.lock:
        self.conn.execute("UPDATE receipts SET outcome='handed_off' WHERE id=?", (receipt_id,))
        # unproven is a failure for trust, same as close() books an undo; the bench credits rehearsals
        if failure and receipt.trust.get("approved_by") != approvals.REHEARSAL_APPROVER:
            trust.record(self.conn, action.pattern, action.tool, action.target, "real", False, self.clock())
        self.conn.commit()
    kept = receipt.model_copy(update={"outcome": "handed_off"})
    self.receipts.update(receipt_id, kept)
    self.heartbeats.pop(receipt_id, None)
    self.verifying.pop(receipt_id, None)
    card = self.card(row, action.target, receipt=kept, receipt_id=receipt_id,
                     reason="no safe undo" if failure else reason)
    briefing = f"no safe undo ({receipt.inverse.get('why')}); fix kept after: {reason}" if failure \
        else f"{reason}; fix kept, a person must check"
    await self.publish({"type": "escalated", "incident_id": action.incident_id, "payload": {
        "card": card.model_dump(mode="json"), "briefing": briefing,
        **self.facts(action.incident_id, row, *sent_by)}})
    self.set_state(action.incident_id, "escalated")
    return "handed_off"


# pause an in-progress rollout first so the inverse lands on a still object (§6.4.9 Undo);

# always unpause, a failed undo must not leave the Deployment paused

def undo(self: "Gateway", target: str, inverse: dict, pause: bool) -> None:
    def rv() -> str:
        return read_deployment(self.apps, target)["metadata"]["resourceVersion"]

    def gen() -> int:
        return read_deployment(self.apps, target)["metadata"]["generation"]

    if inverse["op"] not in ("restore_configmap", "scale", "restore_template"):
        raise WriteRefused("refused", f"no safe undo ({inverse.get('why', inverse['op'])})")
    if inverse["op"] == "restore_configmap":
        cm = read_configmap(self.core, inverse["name"])
        patch_configmap(self.core, inverse["name"], {"metadata": {"resourceVersion": cm["metadata"]["resourceVersion"]},
                                                     "data": inverse["data"]}, False)
        return
    if inverse["op"] == "scale":
        patch_scale(self.apps, target, {"metadata": {"resourceVersion": rv()},
                                        "spec": {"replicas": inverse["replicas"]}}, False)
        return
    template = inverse["template"]

    test = {"op": "test", "path": "/metadata/generation"}
    if pause:
        patch_deployment(self.apps, target, [{**test, "value": gen()},
                                             {"op": "add", "path": "/spec/paused", "value": True}], False)
    try:
        patch_deployment(self.apps, target, rollback_patch(gen(), template), False)
    finally:
        if pause:
            patch_deployment(self.apps, target, [{**test, "value": gen()},
                                                 {"op": "replace", "path": "/spec/paused", "value": False}], False)


async def close(self: "Gateway", receipt_id: int, action: ActionRequest, row: dict, receipt: Receipt, v: Verification,
                outcome: str, harm: dict | None, reason: str | None, hash_after: str | None = None,
                plan: dict | None = None) -> str:
    final = receipt.model_copy(update={"outcome": outcome, "prediction_held": v.prediction_held,
                                       "harm_clean": harm["clean"] if harm else None,
                                       "elapsed_s": round(self.clock() - v.t0, 1),
                                       "added_disruption_s": round(sum(v.collateral.values()), 1),
                                       "hash_after": hash_after})
    self.receipts.update(receipt_id, final)
    effect = ledger_effect({"undone": "undo"}.get(outcome, outcome))
    by = receipt.trust.get("approved_by")
    with self.lock:
        self.conn.execute("UPDATE receipts SET outcome=?, hash_after=? WHERE id=?",
                          (outcome, hash_after, receipt_id))
        # real success needs a human's yes (§6.4.6); a failure always counts; the bench credits rehearsals.
        # The ledger is the rule's record: a fix the model chose earns and costs it nothing
        if (effect is not None and by != approvals.REHEARSAL_APPROVER and (by or not effect)
                and action.origin != "model"):
            trust.record(self.conn, action.pattern, action.tool, action.target, "real", effect, self.clock())
        self.conn.commit()
    # fixes run in this incident, this one included (follow-ups count: they share the per-incident budget)
    with self.lock:
        done = self.conn.execute("SELECT COUNT(*) FROM receipts WHERE incident_id=?",
                                 (action.incident_id,)).fetchone()[0]
    if outcome == "undone":
        self.tries.setdefault(action.incident_id, []).append(
            {"attempt": done, **failed_try(receipt_id, action, v, harm, reason, plan)})
    # a clean undo for a wrong fix may hand the incident back to the brain instead of paging (§6.4.11)
    retrying, no_retry = False, None
    # single-agent path only: with orchestration on, intents and the coordinator own what comes next
    if outcome == "undone" and reason in RETRY_REASONS and self.request_retry is not None and self.intents is None:
        no_retry = self.retry_blocker(action.incident_id)
        retrying = no_retry is None
    event = {"success": "incident_resolved", "right_by_accident": "incident_resolved",
             "handed_off": "handed_off"}.get(outcome, "escalated")
    state = "replanning" if retrying else {"incident_resolved": "resolved"}.get(event, event)
    # state first: the brain's next fix can reach run() before this method returns
    with self.lock:
        self.conn.execute("UPDATE incidents SET state=?, resolved_at=? WHERE id=?",
                          (state, self.clock() if state == "resolved" else None, action.incident_id))
        self.conn.commit()
    self.heartbeats.pop(receipt_id, None)
    self.verifying.pop(receipt_id, None)
    if retrying:
        no_retry = await self.start_retry(action, row, done + 1)
        retrying = no_retry is None
        if not retrying:
            self.set_state(action.incident_id, "escalated")
    mitigated = action.tool == "restart_service" and outcome in ("success", "right_by_accident")
    victims = json.loads(row.get("victims_json") or "[]")
    retry: dict[str, Any] = {"next": done + 1} if retrying else {"stop": no_retry}
    card = self.card(row, action.target, receipt=final, receipt_id=receipt_id, mitigated=mitigated,
                     reason=reason, retry=retry,
                     took_s=self.clock() - (row.get("opened_at") or v.t0), did=(plan or {}).get("summary"),
                     metric=error_change((plan or {}).get("health") or {}, v.last_health,
                                         [action.target, *victims]))
    briefing = (reason or "") + (f"; no retry: {no_retry}" if no_retry else "")
    # the bench (§9.1) reads tier, harm, prediction and forecast vs actual off the terminal event
    await self.publish({"type": "retry_started" if retrying else event, "incident_id": action.incident_id,
                        "payload": {
        "card": card.model_dump(mode="json"), "receipt_url": f"/receipts/{receipt_id}",
        "briefing": briefing, "receipt_id": receipt_id, "tier": tier_of(receipt.trust),
        "prediction_held": final.prediction_held, "harm_clean": final.harm_clean,
        "forecast_s": final.forecast_s, "actual_added_s": final.added_disruption_s,
        **({"attempt": retry["next"], "max_attempts": self.max_tries} if retrying else {}),
        **self.guidance(action.incident_id, action.pattern, action.tool, action.target),
        **self.facts(action.incident_id, row, "verifier", "fix check")}})
    return outcome


# Q2: bench reports ground truth; credit only finished rehearsal receipts, once

def rehearsal_credit(self: "Gateway", receipt_id: int, diagnosis_matched: bool) -> dict:
    with self.lock:
        r = self.conn.execute("SELECT * FROM receipts WHERE id=?", (receipt_id,)).fetchone()
        if r is None:
            return {"credited": False, "reason": "unknown receipt"}
        gate = json.loads(r["trust_json"] or "{}")
        if gate.get("approved_by") != approvals.REHEARSAL_APPROVER:
            return {"credited": False, "reason": "not a rehearsal receipt"}
        if gate.get("credited"):
            return {"credited": False, "reason": "already credited"}
        if gate.get("origin") == "model":
            return {"credited": False, "reason": "the model chose this fix; the ledger is the rule's record"}
        if r["outcome"] in ("pending", "handed_off", "right_by_accident"):
            return {"credited": False, "reason": f"outcome {r['outcome']} earns no credit"}
        success = r["outcome"] == "success" and diagnosis_matched
        trust.record(self.conn, gate["pattern"], r["tool"], r["target"], "rehearsal", success, self.clock())
        self.conn.execute("UPDATE receipts SET trust_json=? WHERE id=?",
                          (json.dumps({**gate, "credited": True}), receipt_id))
        self.conn.commit()
    return {"credited": True, "success": success}


# a failed watchdog undo blocks every action until a human has looked at the cluster; this is how

# they say so (approver only, rehearsal identity excluded). Recorded on the audit log.

async def clear_receipt(self: "Gateway", receipt_id: int, decided_by: str) -> dict:
    if decided_by not in self.approvers or decided_by == approvals.REHEARSAL_APPROVER:
        return {"cleared": False, "reason": "not an approver"}
    with self.lock:
        r = self.conn.execute("SELECT incident_id, outcome FROM receipts WHERE id=?", (receipt_id,)).fetchone()
        if r is None:
            return {"cleared": False, "reason": "unknown receipt"}
        if r["outcome"] != "watchdog_failed":
            return {"cleared": False, "reason": f"receipt is {r['outcome']}, nothing to clear"}
        self.conn.execute("UPDATE receipts SET outcome='undo_failed' WHERE id=?", (receipt_id,))
        self.conn.commit()
    await self.publish({"type": "checklist_step", "incident_id": r["incident_id"], "payload": {
        "name": "human_clear", "passed": True,
        "reason": f"receipt #{receipt_id} cleared by {decided_by} after a failed undo"}})
    return {"cleared": True}
