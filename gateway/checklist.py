# the checklist (IMPLEMENTATION.md §6.4.2): first failing step decides. The gateway never calls an LLM.
import asyncio
import json
import logging
import sqlite3
import threading
import time
from datetime import datetime, timezone
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from pydantic import ValidationError

from brain.rules import latest_change_before_onset
from gateway import approvals, blast, freshness, policy, trust
from gateway.dryrun import build_patch, namespace_hash, outside_allowed, rollback_patch, spec_diff, spec_hashes
from gateway.verifier import Verification, harm_check, ledger_effect
from gateway.executor import WriteRefused, list_json, patch_deployment, patch_scale, read_deployment
from gateway.receipts import ReceiptStore, build_incident_card
from observer.kube_watch import service_of
from schemas.models import ActionRequest, GatewayDecision, Incident, Receipt

log = logging.getLogger("gateway")


def forecast_text(plan: dict) -> str:
    f, b = plan.get("forecast") or {}, plan.get("blast") or {}
    hit = ", ".join(b.get("healthy_affected", [])) or "none known"
    return (f"about {f.get('forecast_s', 0):.0f} s of lost capacity ({plan['replicas']} replicas, "
            f"surge {'on' if plan.get('surge') else 'off'}); healthy callers at risk: {hit}")


class Gateway:
    def __init__(self, conn: sqlite3.Connection, apps: Any, core: Any, http: httpx.AsyncClient, observer_url: str,
                 services: dict, policy_cfg: dict, publish: Callable[[dict], Awaitable[Any]],
                 receipts: ReceiptStore, approvers: set[str], clock: Callable[[], float] = time.time,
                 graph: Any = None):
        self.conn, self.apps, self.core, self.http, self.observer_url = conn, apps, core, http, observer_url
        self.services, self.policy, self.publish, self.receipts = services, policy_cfg, publish, receipts
        self.approvers, self.clock = approvers, clock
        self.lock = threading.Lock()
        self.verify_every = 5.0
        self.tasks: set[asyncio.Task] = set()
        self.graph = graph  # brain.graph.DependencyGraph; None = blast radius unknown
        self.heartbeats: dict[int, float] = {}
        self.verifying: dict[int, asyncio.Task] = {}

    # ---- helpers -------------------------------------------------------------------------------
    def incident(self, incident_id: str) -> dict | None:
        with self.lock:
            r = self.conn.execute("SELECT * FROM incidents WHERE id=?", (incident_id,)).fetchone()
        return dict(r) if r else None

    def card_incident(self, row: dict, target: str | None) -> Incident:
        victims = json.loads(row.get("victims_json") or "[]")
        culprit = row.get("culprit") or target
        return Incident(id=row["id"], opened_at=row.get("opened_at") or 0, onset_at=row.get("onset_at") or 0,
                        unhealthy=[s for s in [culprit, *victims] if s], culprit=culprit, victims=victims,
                        major=bool(row.get("major")), severity=row.get("severity_at_open") or 0)

    async def step(self, incident_id: str, steps: list[dict], name: str, passed: bool, reason: str | None = None):
        steps.append({"name": name, "passed": passed, "reason": reason})
        await self.publish({"type": "checklist_step", "incident_id": incident_id,
                            "payload": {"name": name, "passed": passed, "reason": reason}})

    async def get_json(self, path: str, **params: Any) -> Any:
        r = await self.http.get(f"{self.observer_url}{path}", params=params, timeout=10)
        r.raise_for_status()
        return r.json()

    def set_state(self, incident_id: str, state: str) -> None:
        with self.lock:
            self.conn.execute("UPDATE incidents SET state=? WHERE id=?", (state, incident_id))
            self.conn.commit()

    # a failed step ends the incident's automation: tell everyone, wake a human unless it fixed itself
    async def stop(self, action: ActionRequest | dict, row: dict | None, steps: list[dict], name: str,
                   outcome: str, reason: str | None) -> GatewayDecision:
        incident_id = action.incident_id if isinstance(action, ActionRequest) else str(action.get("incident_id"))
        target = action.target if isinstance(action, ActionRequest) else action.get("target")
        await self.step(incident_id, steps, name, False, reason)
        decision = GatewayDecision(decision=outcome, failed_step=name, reason=reason)  # type: ignore[arg-type]
        if row is not None:
            gone = name == "freshness" and outcome == "refused"
            event = "incident_resolved" if gone else ("handed_off" if outcome == "handed_off" else "escalated")
            card = build_incident_card(self.card_incident(row, target), decision=decision)
            self.set_state(incident_id, {"incident_resolved": "resolved"}.get(event, event))
            await self.publish({"type": event, "incident_id": incident_id,
                                "payload": {"card": card.model_dump(mode="json"), "briefing": reason or ""}})
        return decision

    # ---- entry points --------------------------------------------------------------------------
    async def submit(self, raw: dict) -> GatewayDecision:
        steps: list[dict] = []
        try:
            action = ActionRequest.model_validate(raw)
        except ValidationError as e:
            await self.step(str(raw.get("incident_id")), steps, "schema", False, e.errors()[0]["msg"])
            return GatewayDecision(decision="refused", failed_step="schema", reason=e.errors()[0]["msg"])
        await self.step(action.incident_id, steps, "schema", True)
        return await self.run(action, steps, approved=False)

    async def decide(self, approval_id: str, decision: str, decided_by: str) -> GatewayDecision:
        row = approvals.get(self.conn, approval_id)
        if row is None:
            return GatewayDecision(decision="refused", failed_step="approval", reason="unknown approval")
        if decided_by not in self.approvers:
            return GatewayDecision(decision="refused", failed_step="approval", reason="not an approver")
        if row["state"] != "pending":
            return GatewayDecision(decision="refused", failed_step="approval", reason=f"approval is {row['state']}")
        action = ActionRequest.model_validate_json(row["action_json"])
        inc = self.incident(action.incident_id)
        expired = self.clock() > row["expires_at"]
        with self.lock:
            busy = policy.usage(self.conn, action.incident_id, self.clock())["in_flight"]
        if decision == "approved" and not expired and busy >= self.policy["budgets"]["max_in_flight"]:
            # keep the approval: it can be used once the action in flight finishes verifying
            return GatewayDecision(decision="refused", failed_step="policy", approval_id=approval_id,
                                   reason="another action is still being verified; approval kept, try again")
        state = "expired" if expired else ("approved" if decision == "approved" else "rejected")
        approvals.set_state(self.conn, approval_id, state, decided_by)
        await self.publish({"type": "approval_decided", "incident_id": action.incident_id,
                            "payload": {"approval_id": approval_id, "decision": state}})
        if state != "approved":
            return await self.stop(action, inc, [], "approval", "escalated", f"approval {state}")
        # things may have changed while we waited: steps 2 to 6 again, trust gate skipped
        return await self.run(action, [{"name": "approval", "passed": True, "reason": decided_by}], approved=True,
                              approved_by=decided_by)

    # ---- steps 2 to 8 --------------------------------------------------------------------------
    async def run(self, action: ActionRequest, steps: list[dict], approved: bool,
                  approved_by: str | None = None) -> GatewayDecision:
        row = self.incident(action.incident_id)
        if row is None:
            return await self.stop(action, None, steps, "schema", "refused", "unknown incident")
        window_s = self.policy["change_window_minutes"] * 60
        try:
            # one read covers the change window before onset and everything since the incident opened
            journal_rows = await self.get_json("/journal", since=(row["onset_at"] or 0) - window_s)
            health = await self.get_json("/health/now")
        except (httpx.HTTPError, ValueError) as e:
            return await self.stop(action, row, steps, "hands_off", "escalated", f"observer unreachable: {e}")

        # 2 hands-off: a human changed something after we opened the incident
        human = [r for r in journal_rows if not r["by_agent"] and r["ts"] >= (row["opened_at"] or 0)]
        if human:
            return await self.stop(action, row, steps, "hands_off", "handed_off",
                                   f"{human[-1]['object']} changed by {human[-1]['field_manager']}")
        await self.step(action.incident_id, steps, "hands_off", True)

        # 3 policy
        with self.lock:
            used = policy.usage(self.conn, action.incident_id, self.clock())
        asking = not approved and self.policy["tools"][action.tool]["auto_eligible"] is False
        ok, outcome, reason = policy.check(action.model_dump(), self.services, self.policy, used, asking=asking)
        if not ok:
            return await self.stop(action, row, steps, "policy", outcome, reason)
        await self.step(action.incident_id, steps, "policy", True)

        # 4 dry run + snapshot
        entry = next((r for r in journal_rows if r["id"] == action.journal_entry), None)
        try:
            plan = await asyncio.to_thread(self.prepare, action, entry)
        except WriteRefused as e:
            return await self.stop(action, row, steps, "dry_run", e.outcome, e.reason)
        await self.step(action.incident_id, steps, "dry_run", True, f"{len(plan['diff'])} spec paths change")

        # 5 blast radius + net benefit
        edges, known = [], False
        if self.graph is not None:
            try:
                edges, known = await self.graph.get(), True
            except (httpx.HTTPError, KeyError, ValueError) as e:
                log.warning("dependency graph failed: %s", type(e).__name__)
        radius = blast.blast_radius(action.target, edges, health)
        forecast_s = blast.forecast_added_seconds(action.tool, plan["replicas"], plan["surge"], plan["startup_s"])
        ok, nb = blast.net_benefit(float(health.get("severity", 0)), radius, forecast_s, self.services, self.policy)
        if not known and forecast_s > 0:
            ok, nb["reason"] = False, "blast radius unknown and the action costs capacity"
        plan["blast"], plan["forecast"] = radius, nb
        if not ok and not approved:
            return await self.ask(action, row, steps, plan, nb.get("reason") or f"net benefit too low: {nb}",
                                  step_name="net_benefit")
        await self.step(action.incident_id, steps, "net_benefit", True,
                        f"forecast {forecast_s:.0f} s" + ("" if ok else "; accepted by approver"))

        # 6 freshness
        latest = latest_change_before_onset(journal_rows, action.target, row["onset_at"] or 0, window_s)
        # only "recent change" points at a journal entry; other patterns must not trip on unrelated edits
        rule_now: tuple[str, int | None]
        if action.pattern == "recent_change":
            rule_now = (action.pattern, latest["id"] if latest else None)
        else:
            rule_now = (action.pattern, action.journal_entry)
        if action.journal_entry is not None and entry is None:
            return await self.stop(action, row, steps, "freshness", "awaiting_approval" if not approved else "escalated",
                                   f"journal entry {action.journal_entry} not found")
        outcome, reason = freshness.check(health, action.target, (action.pattern, action.journal_entry), rule_now,
                                          entry, plan["live"])
        if outcome != "ok":
            if outcome == "awaiting_approval" and not approved:
                return await self.ask(action, row, steps, plan, reason)
            return await self.stop(action, row, steps, "freshness", outcome if outcome == "refused" else "escalated",
                                   reason)
        await self.step(action.incident_id, steps, "freshness", True)
        plan["health"] = health  # the verifier's "before" picture

        # 7 trust gate (skipped after a human approval)
        kind = self.services[action.target].get("kind", "stateless")
        with self.lock:
            gate = trust.check(self.conn, self.policy["trust"], self.policy["tools"][action.tool], action.pattern,
                               action.tool, action.target, kind)
        if not approved:
            if not gate["open"]:
                return await self.ask(action, row, steps, plan, f"trust bound {gate['lower_bound']} < {gate['bar']}",
                                      gate)
            await self.step(action.incident_id, steps, "trust_gate", True, f"bound {gate['lower_bound']}")

        # 8 execute
        return await self.execute(action, row, steps, plan, {**gate, "approved_by": approved_by, "pattern": action.pattern})

    async def ask(self, action: ActionRequest, row: dict, steps: list[dict], plan: dict, reason: str | None,
                  gate: dict | None = None, step_name: str = "trust_gate") -> GatewayDecision:
        await self.step(action.incident_id, steps, step_name, False, reason)
        with self.lock:
            appr = approvals.create(self.conn, action.incident_id, action.model_dump(mode="json"), self.clock(),
                                    self.policy["approval"]["expiry_seconds"])
        decision = GatewayDecision(decision="awaiting_approval", failed_step=step_name, reason=reason,
                                   approval_id=appr["id"])
        card = build_incident_card(self.card_incident(row, action.target), decision=decision)
        changed = ", ".join(sorted(plan["diff"]))[:500]
        await self.publish({"type": "approval_requested", "incident_id": action.incident_id, "payload": {
            "card": card.model_dump(mode="json"), "approval_id": appr["id"], "expires_at": appr["expires_at"],
            "diff": f"{action.tool} {action.target}: {plan['summary']}; changes {changed}",
            "forecast": forecast_text(plan)}})
        self.set_state(action.incident_id, "awaiting_approval")
        return decision

    def write(self, target: str, patch: dict, dry_run: bool) -> dict:
        if patch["kind"] == "scale":
            return patch_scale(self.apps, target, patch["body"], dry_run)
        return patch_deployment(self.apps, target, patch["body"], dry_run, patch["content_type"])

    # blocking reads + dry run with the agent identity; runs in a thread
    def prepare(self, action: ActionRequest, entry: dict | None) -> dict:
        target = action.target
        live = read_deployment(self.apps, target)
        rss = list_json(self.apps.list_namespaced_replica_set) if action.tool == "rollback_deploy" else []
        now_iso = datetime.fromtimestamp(self.clock(), timezone.utc).isoformat()
        patch = build_patch(action.tool, live, action.params, entry, rss, now_iso)
        dry = self.write(target, patch, dry_run=True)
        if patch["kind"] == "scale":
            diff = spec_diff({"replicas": live["spec"].get("replicas")}, {"replicas": dry["spec"].get("replicas")})
            inverse = {"op": "scale", "target": target, "replicas": live["spec"].get("replicas")}
        else:
            diff = spec_diff(live["spec"], dry["spec"])
            # undo = put the pre-action template back (JSON Patch, agent identity), whatever the tool changed
            inverse = {"op": "restore_template", "target": target, "template": live["spec"]["template"]}
        if not diff:
            raise WriteRefused("refused", f"{action.tool} would change nothing")
        if bad := outside_allowed(diff, patch["allowed"]):
            raise WriteRefused("escalated", f"dry run touched paths {action.tool} must not: {bad[:5]}")
        hashes = spec_hashes(list_json(self.apps.list_namespaced_deployment), list_json(self.core.list_namespaced_config_map))
        pod_objs = [p for p in list_json(self.core.list_namespaced_pod) if service_of(p) == target]
        pods = [p["metadata"]["name"] for p in pod_objs]
        return {"live": live, "patch": patch, "diff": diff, "summary": patch["summary"], "hashes": hashes,
                "pods": pods, "replicas": live["spec"].get("replicas", 1), "inverse": inverse,
                "surge": blast.surge_ok(live), "startup_s": blast.startup_seconds(pod_objs)}

    async def execute(self, action: ActionRequest, row: dict, steps: list[dict], plan: dict,
                      gate: dict) -> GatewayDecision:
        try:
            await asyncio.to_thread(self.write, action.target, plan["patch"], False)
        except WriteRefused as e:
            return await self.stop(action, row, steps, "execute", e.outcome, e.reason)
        await self.step(action.incident_id, steps, "execute", True)
        inverse = plan["inverse"]
        receipt = Receipt(incident_id=action.incident_id, tool=action.tool, target=action.target, diff=plan["diff"],
                          inverse=inverse, evidence_ids=action.evidence_ids, pods_touched=plan["pods"], trust=gate,
                          checklist=steps, hash_before=namespace_hash(plan["hashes"]), blast=plan.get("blast", {}),
                          forecast_s=(plan.get("forecast") or {}).get("forecast_s"))
        receipt_id = self.receipts.save(receipt)
        with self.lock:
            self.conn.execute(
                "INSERT INTO receipts (id, incident_id, ts, tool, target, diff_json, pods_touched_json, inverse_json, "
                "hash_before, checklist_json, trust_json, forecast_json, blast_json, outcome) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')",
                (receipt_id, action.incident_id, self.clock(), action.tool, action.target, json.dumps(plan["diff"]),
                 json.dumps(plan["pods"]), json.dumps(inverse), json.dumps(plan["hashes"]), json.dumps(steps),
                 json.dumps(gate), json.dumps({**(plan.get("forecast") or {}), "prediction":
                                               action.prediction.model_dump() if action.prediction else None}),
                 json.dumps(plan.get("blast", {}))))
            self.conn.execute("UPDATE incidents SET state='verifying', tier=? WHERE id=?",
                              ("auto" if gate.get("open") else "ask", action.incident_id))
            self.conn.commit()
        await self.publish({"type": "action_executed", "incident_id": action.incident_id,
                            "payload": {"receipt_id": receipt_id, "tool": action.tool, "target": action.target}})
        task = asyncio.create_task(self.verify(receipt_id, action, row, plan, receipt))
        self.tasks.add(task)
        self.verifying[receipt_id] = task
        self.heartbeats[receipt_id] = self.clock()
        task.add_done_callback(self.tasks.discard)
        return GatewayDecision(decision="executed", receipt_id=receipt_id)

    # ---- verification (§6.4.9): poll health, decide, undo if needed, credit the ledger ------------
    async def verify(self, receipt_id: int, action: ActionRequest, row: dict, plan: dict, receipt: Receipt) -> str:
        victims = json.loads(row.get("victims_json") or "[]")
        cfg = self.policy["verify"]
        v = Verification(self.clock(), plan["health"], action.target, victims,
                         action.prediction.model_dump() if action.prediction else None,
                         cfg["window_seconds"], cfg["early_abort"])
        health, human, result = plan["health"], [], None
        while result is None:
            await asyncio.sleep(self.verify_every)
            try:
                health = await self.get_json("/health/now")
                human = [r for r in await self.get_json("/journal", since=v.t0) if not r["by_agent"]]
                result = v.step(self.clock(), health, bool(human))
            except (httpx.HTTPError, ValueError, KeyError) as e:  # observer blip: keep the clock running
                log.warning("verify tick failed: %s", type(e).__name__)
                if self.clock() - v.t0 >= cfg["window_seconds"]:
                    result = "window_end"
            self.heartbeats[receipt_id] = self.clock()
            await self.publish({"type": "verify_tick", "incident_id": action.incident_id, "payload": {
                "receipt_id": receipt_id, "severity": health.get("severity"), "recovered": v.recovered}})

        if result == "handed_off":
            return await self.close(receipt_id, action, row, receipt, v, "handed_off", None,
                                    f"{human[-1]['object']} changed by {human[-1]['field_manager']}")
        if result == "early_abort":
            await self.publish({"type": "early_abort", "incident_id": action.incident_id,
                                "payload": {"receipt_id": receipt_id, "severity": health.get("severity"),
                                            "before": v.sev_before}})
            return await self.undo_and_close(receipt_id, action, row, receipt, v, pause=True, harm=None,
                                             reason="severity rose after the action")
        after = await asyncio.to_thread(lambda: spec_hashes(list_json(self.apps.list_namespaced_deployment),
                                                            list_json(self.core.list_namespaced_config_map)))
        harm = harm_check(plan["hashes"], after, f"deployment/{action.target}", {r["object"] for r in human},
                          plan["health"], health, {action.target, *victims})
        await self.publish({"type": "harm_check", "incident_id": action.incident_id,
                            "payload": {"receipt_id": receipt_id, **harm}})
        outcome = v.outcome(harm["clean"])
        if outcome == "undo":
            reason = "did not recover" if not v.recovered else "harm check failed"
            return await self.undo_and_close(receipt_id, action, row, receipt, v, pause=False, harm=harm,
                                             reason=reason, hash_after=namespace_hash(after))
        return await self.close(receipt_id, action, row, receipt, v, outcome, harm, None, namespace_hash(after))

    async def undo_and_close(self, receipt_id: int, action: ActionRequest, row: dict, receipt: Receipt,
                             v: Verification, pause: bool, harm: dict | None, reason: str,
                             hash_after: str | None = None) -> str:
        try:
            await asyncio.to_thread(self.undo, action.target, receipt.inverse, pause)
        except WriteRefused as e:
            await self.publish({"type": "escalated", "incident_id": action.incident_id, "payload": {
                "card": build_incident_card(self.card_incident(row, action.target)).model_dump(mode="json"),
                "briefing": f"UNDO FAILED ({e.reason}); receipt #{receipt_id} needs a human now"}})
            self.set_state(action.incident_id, "escalated")
            return "undo_failed"
        await self.publish({"type": "action_undone", "incident_id": action.incident_id,
                            "payload": {"receipt_id": receipt_id, "reason": reason}})
        return await self.close(receipt_id, action, row, receipt, v, "undone", harm, reason, hash_after)

    # pause an in-progress rollout first so the inverse lands on a still object (§6.4.9 Undo)
    def undo(self, target: str, inverse: dict, pause: bool) -> None:
        def rv() -> str:
            return read_deployment(self.apps, target)["metadata"]["resourceVersion"]

        if inverse["op"] == "scale":
            patch_scale(self.apps, target, {"metadata": {"resourceVersion": rv()},
                                            "spec": {"replicas": inverse["replicas"]}}, False)
            return
        template = inverse["template"]

        test = {"op": "test", "path": "/metadata/resourceVersion"}
        if pause:
            patch_deployment(self.apps, target, [{**test, "value": rv()},
                                                 {"op": "add", "path": "/spec/paused", "value": True}], False)
        patch_deployment(self.apps, target, rollback_patch(rv(), template), False)
        if pause:
            patch_deployment(self.apps, target, [{**test, "value": rv()},
                                                 {"op": "replace", "path": "/spec/paused", "value": False}], False)

    async def close(self, receipt_id: int, action: ActionRequest, row: dict, receipt: Receipt, v: Verification,
                    outcome: str, harm: dict | None, reason: str | None, hash_after: str | None = None) -> str:
        final = receipt.model_copy(update={"outcome": outcome, "prediction_held": v.prediction_held,
                                           "harm_clean": harm["clean"] if harm else None,
                                           "elapsed_s": round(self.clock() - v.t0, 1),
                                           "added_disruption_s": round(sum(v.collateral.values()), 1),
                                           "hash_after": hash_after})
        self.receipts.update(receipt_id, final)
        effect = ledger_effect({"undone": "undo"}.get(outcome, outcome))
        with self.lock:
            self.conn.execute("UPDATE receipts SET outcome=?, hash_after=? WHERE id=?",
                              (outcome, hash_after, receipt_id))
            if effect is not None and receipt.trust.get("approved_by") != approvals.REHEARSAL_APPROVER:
                trust.record(self.conn, action.pattern, action.tool, action.target, "real", effect, self.clock())
            self.conn.commit()
        event = {"success": "incident_resolved", "right_by_accident": "incident_resolved",
                 "handed_off": "handed_off"}.get(outcome, "escalated")
        state = {"incident_resolved": "resolved"}.get(event, event)
        with self.lock:
            self.conn.execute("UPDATE incidents SET state=?, resolved_at=? WHERE id=?",
                              (state, self.clock() if state == "resolved" else None, action.incident_id))
            self.conn.commit()
        self.heartbeats.pop(receipt_id, None)
        self.verifying.pop(receipt_id, None)
        mitigated = action.tool == "restart_service" and outcome in ("success", "right_by_accident")
        card = build_incident_card(self.card_incident(row, action.target), receipt=final, receipt_id=receipt_id,
                                   mitigated=mitigated)
        await self.publish({"type": event, "incident_id": action.incident_id, "payload": {
            "card": card.model_dump(mode="json"), "receipt_url": f"/receipts/{receipt_id}",
            "briefing": reason or ""}})
        return outcome

    # Q2: bench reports ground truth; credit only finished rehearsal receipts, once
    def rehearsal_credit(self, receipt_id: int, diagnosis_matched: bool) -> dict:
        with self.lock:
            r = self.conn.execute("SELECT * FROM receipts WHERE id=?", (receipt_id,)).fetchone()
            if r is None:
                return {"credited": False, "reason": "unknown receipt"}
            gate = json.loads(r["trust_json"] or "{}")
            if gate.get("approved_by") != approvals.REHEARSAL_APPROVER:
                return {"credited": False, "reason": "not a rehearsal receipt"}
            if gate.get("credited"):
                return {"credited": False, "reason": "already credited"}
            if r["outcome"] in ("pending", "handed_off", "right_by_accident"):
                return {"credited": False, "reason": f"outcome {r['outcome']} earns no credit"}
            success = r["outcome"] == "success" and diagnosis_matched
            trust.record(self.conn, gate["pattern"], r["tool"], r["target"], "rehearsal", success, self.clock())
            self.conn.execute("UPDATE receipts SET trust_json=? WHERE id=?",
                              (json.dumps({**gate, "credited": True}), receipt_id))
            self.conn.commit()
        return {"credited": True, "success": success}

    # ---- background upkeep (§6.4.8 expiry, §6.4.10 watchdog) ------------------------------------
    async def expire_approvals(self) -> int:
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
                            "approval expired")
        return len(rows)

    # an action older than 180 s whose verifier stopped ticking gets undone and a human woken
    async def watchdog(self, stale_after_s: float = 180, heartbeat_s: float = 30) -> int:
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
            try:
                await asyncio.to_thread(self.undo, r["target"], inverse, inverse["op"] == "restore_template")
                outcome = "undone"
            except WriteRefused as e:
                reason, outcome = f"{reason}; UNDO FAILED ({e.reason})", "pending"
            with self.lock:
                self.conn.execute("UPDATE receipts SET outcome=? WHERE id=?",
                                  ("undone" if outcome == "undone" else "watchdog_failed", r["id"]))
                if outcome == "undone" and gate.get("approved_by") != approvals.REHEARSAL_APPROVER:
                    trust.record(self.conn, gate.get("pattern"), r["tool"], r["target"], "real", False, now)
                self.conn.commit()
            if (view := self.receipts.get(r["id"])) is not None and outcome == "undone":
                self.receipts.update(r["id"], view.model_copy(update={"outcome": "undone"}))
            self.heartbeats.pop(r["id"], None)
            if outcome == "undone":
                await self.publish({"type": "action_undone", "incident_id": r["incident_id"],
                                    "payload": {"receipt_id": r["id"], "reason": "watchdog"}})
            self.set_state(r["incident_id"], "escalated")
            card = build_incident_card(self.card_incident(row, r["target"]))
            await self.publish({"type": "escalated", "incident_id": r["incident_id"],
                                "payload": {"card": card.model_dump(mode="json"), "briefing": reason}})
            done += 1
        return done

    async def upkeep(self, every_s: float = 5) -> None:
        while True:
            try:
                await self.expire_approvals()
                await self.watchdog()
            except Exception as e:  # never let upkeep die quietly
                log.error("upkeep failed: %r", e)
            await asyncio.sleep(every_s)
