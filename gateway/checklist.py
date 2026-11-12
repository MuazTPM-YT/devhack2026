# the checklist (IMPLEMENTATION.md §6.4.2): first failing step decides. The gateway never calls an LLM.
import asyncio
import json
import logging
import sqlite3
import threading
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from pydantic import ValidationError

from brain.rules import latest_change_before_onset
from gateway import approvals, freshness, policy, trust
from gateway.dryrun import namespace_hash, outside_allowed, previous_template, rollback_patch, spec_diff, spec_hashes
from gateway.executor import WriteRefused, list_json, patch_deployment, read_deployment
from gateway.receipts import ReceiptStore, build_incident_card
from observer.kube_watch import service_of
from schemas.models import ActionRequest, GatewayDecision, Incident, Receipt

log = logging.getLogger("gateway")
BUILT_TOOLS = {"rollback_deploy"}  # ponytail: Phase 1; the other five land in Phase 2 (executor)


class Gateway:
    def __init__(self, conn: sqlite3.Connection, apps: Any, core: Any, http: httpx.AsyncClient, observer_url: str,
                 services: dict, policy_cfg: dict, publish: Callable[[dict], Awaitable[Any]],
                 receipts: ReceiptStore, approvers: set[str], clock: Callable[[], float] = time.time):
        self.conn, self.apps, self.core, self.http, self.observer_url = conn, apps, core, http, observer_url
        self.services, self.policy, self.publish, self.receipts = services, policy_cfg, publish, receipts
        self.approvers, self.clock = approvers, clock
        self.lock = threading.Lock()

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
        state = "expired" if expired else ("approved" if decision == "approved" else "rejected")
        approvals.set_state(self.conn, approval_id, state, decided_by)
        await self.publish({"type": "approval_decided", "incident_id": action.incident_id,
                            "payload": {"approval_id": approval_id, "decision": state}})
        if state != "approved":
            return await self.stop(action, inc, [], "approval", "escalated", f"approval {state}")
        # things may have changed while we waited: steps 2 to 6 again, trust gate skipped
        return await self.run(action, [{"name": "approval", "passed": True, "reason": decided_by}], approved=True)

    # ---- steps 2 to 8 --------------------------------------------------------------------------
    async def run(self, action: ActionRequest, steps: list[dict], approved: bool) -> GatewayDecision:
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
        ok, outcome, reason = policy.check(action.model_dump(), self.services, self.policy, used)
        if not ok:
            return await self.stop(action, row, steps, "policy", outcome, reason)
        await self.step(action.incident_id, steps, "policy", True)

        # 4 dry run + snapshot
        if action.tool not in BUILT_TOOLS:
            return await self.stop(action, row, steps, "dry_run", "refused", f"{action.tool} not built yet")
        try:
            plan = await asyncio.to_thread(self.prepare_rollback, action.target)
        except WriteRefused as e:
            return await self.stop(action, row, steps, "dry_run", e.outcome, e.reason)
        await self.step(action.incident_id, steps, "dry_run", True, f"{len(plan['diff'])} spec paths change")

        # 5 net benefit
        # ponytail: P1 (§6.4.4); with 2 replicas + surge the forecast is 0 s anyway
        await self.step(action.incident_id, steps, "net_benefit", True, "not built (P1); passes")

        # 6 freshness
        latest = latest_change_before_onset(journal_rows, action.target, row["onset_at"] or 0, window_s)
        rule_now = (action.pattern, latest["id"] if latest else None)
        entry = next((r for r in journal_rows if r["id"] == action.journal_entry), None)
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
        return await self.execute(action, row, steps, plan, gate)

    async def ask(self, action: ActionRequest, row: dict, steps: list[dict], plan: dict, reason: str | None,
                  gate: dict | None = None) -> GatewayDecision:
        await self.step(action.incident_id, steps, "trust_gate", False, reason)
        with self.lock:
            appr = approvals.create(self.conn, action.incident_id, action.model_dump(mode="json"), self.clock(),
                                    self.policy["approval"]["expiry_seconds"])
        decision = GatewayDecision(decision="awaiting_approval", failed_step="trust_gate", reason=reason,
                                   approval_id=appr["id"])
        card = build_incident_card(self.card_incident(row, action.target), decision=decision)
        changed = ", ".join(sorted(plan["diff"]))[:500]
        await self.publish({"type": "approval_requested", "incident_id": action.incident_id, "payload": {
            "card": card.model_dump(mode="json"), "approval_id": appr["id"], "expires_at": appr["expires_at"],
            "diff": f"{action.tool} {action.target}: back to revision {plan['to_revision']}; changes {changed}",
            "forecast": f"{plan['replicas']} replicas with surge: no added downtime expected (forecast not built, P1)"}})
        self.set_state(action.incident_id, "awaiting_approval")
        return decision

    # blocking reads + dry run with the agent identity; runs in a thread
    def prepare_rollback(self, target: str) -> dict:
        live = read_deployment(self.apps, target)
        prev = previous_template(live, list_json(self.apps.list_namespaced_replica_set))
        if prev is None:
            raise WriteRefused("escalated", f"{target} has no earlier revision to roll back to")
        template, to_rev = prev
        patch = rollback_patch(live["metadata"]["resourceVersion"], template)
        dry = patch_deployment(self.apps, target, patch, dry_run=True)
        diff = spec_diff(live["spec"], dry["spec"])
        if not diff:
            raise WriteRefused("refused", "rollback would change nothing")
        if bad := outside_allowed(diff):
            raise WriteRefused("escalated", f"dry run touched paths a rollback must not: {bad[:5]}")
        hashes = spec_hashes(list_json(self.apps.list_namespaced_deployment), list_json(self.core.list_namespaced_config_map))
        pods = [p["metadata"]["name"] for p in list_json(self.core.list_namespaced_pod) if service_of(p) == target]
        return {"live": live, "patch": patch, "diff": diff, "to_revision": to_rev, "hashes": hashes, "pods": pods,
                "replicas": live["spec"].get("replicas", 1)}

    async def execute(self, action: ActionRequest, row: dict, steps: list[dict], plan: dict,
                      gate: dict) -> GatewayDecision:
        try:
            await asyncio.to_thread(patch_deployment, self.apps, action.target, plan["patch"], False)
        except WriteRefused as e:
            return await self.stop(action, row, steps, "execute", e.outcome, e.reason)
        await self.step(action.incident_id, steps, "execute", True)
        # undo = put the pre-action template back (also via JSON Patch, agent identity)
        inverse = {"op": "restore_template", "target": action.target, "template": plan["live"]["spec"]["template"],
                   "from_revision": plan["to_revision"]}
        receipt = Receipt(incident_id=action.incident_id, tool=action.tool, target=action.target, diff=plan["diff"],
                          inverse=inverse, evidence_ids=action.evidence_ids, pods_touched=plan["pods"], trust=gate,
                          checklist=steps, hash_before=namespace_hash(plan["hashes"]))
        receipt_id = self.receipts.save(receipt)
        with self.lock:
            self.conn.execute(
                "INSERT INTO receipts (id, incident_id, ts, tool, target, diff_json, pods_touched_json, inverse_json, "
                "hash_before, checklist_json, trust_json, forecast_json, outcome) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')",
                (receipt_id, action.incident_id, self.clock(), action.tool, action.target, json.dumps(plan["diff"]),
                 json.dumps(plan["pods"]), json.dumps(inverse), json.dumps(plan["hashes"]), json.dumps(steps),
                 json.dumps(gate), json.dumps({"prediction": action.prediction.model_dump() if action.prediction
                                               else None})))
            self.conn.execute("UPDATE incidents SET state='verifying', tier=? WHERE id=?",
                              ("auto" if gate.get("open") else "ask", action.incident_id))
            self.conn.commit()
        await self.publish({"type": "action_executed", "incident_id": action.incident_id,
                            "payload": {"receipt_id": receipt_id, "tool": action.tool, "target": action.target}})
        return GatewayDecision(decision="executed", receipt_id=receipt_id)
