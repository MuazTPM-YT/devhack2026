# the checklist (IMPLEMENTATION.md §6.4.2): first failing step decides. The gateway never calls an LLM.
import asyncio
import json
import logging
import sqlite3
import threading
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from pydantic import ValidationError

from brain import memory, runbooks
from brain.bundle import why_text
from brain.major import shared_change
from brain.rules import latest_change_before_onset
from gateway import approvals, blast, freshness, policy, trust
from gateway.dryrun import build_flag_patch, build_patch, namespace_hash, outside_allowed, rollback_patch, spec_diff, spec_hashes
from gateway.verifier import Verification, harm_check, ledger_effect
from gateway.executor import (WriteRefused, list_json, patch_configmap, patch_deployment, patch_scale,
                              read_configmap, read_deployment)
from gateway.intents import IntentStore, precondition, submission
from gateway.receipts import ReceiptStore, build_incident_card
from observer import journal
from observer.kube_watch import service_of
from schemas import auth
from schemas.models import ActionRequest, Card, GatewayDecision, Incident, Receipt
from schemas.orchestration import IntentEnvelope, IntentSubmission

log = logging.getLogger("gateway")
# chaos/faults.py FIELD_MANAGER: a fault injection is the incident's cause, not a human taking over (§6.4.2 step 2)
CHAOS_MANAGER = "chaos-panel"
# orchestration: the intent the running checklist works for (None = legacy MCP/HTTP submit)
_intent: ContextVar[str | None] = ContextVar("intent", default=None)


def forecast_text(plan: dict) -> str:
    f, b = plan.get("forecast") or {}, plan.get("blast") or {}
    hit = ", ".join(b.get("healthy_affected", [])) or "none known"
    return (f"about {f.get('forecast_s', 0):.0f} s of lost capacity ({plan['replicas']} replicas, "
            f"surge {'on' if plan.get('surge') else 'off'}); healthy callers at risk: {hit}")


def tier_of(gate: dict) -> str:
    return "ask" if gate.get("approved_by") else "auto"


# "payment errors 38.0% -> 0.4%" for the card's first line: first watched service with both readings
def error_change(before: dict, after: dict | None, services: list[str]) -> str | None:
    for s in services:
        a = before.get("services", {}).get(s, {}).get("err_ratio")
        b = (after or {}).get("services", {}).get(s, {}).get("err_ratio")
        if a is not None and b is not None:
            return f"{s} errors {a:.1%} -> {b:.1%}"
    return None



class Gateway:
    def __init__(self, conn: sqlite3.Connection, apps: Any, core: Any, http: httpx.AsyncClient, observer_url: str,
                 services: dict, policy_cfg: dict, publish: Callable[[dict], Awaitable[Any]],
                 receipts: ReceiptStore, approvers: set[str], clock: Callable[[], float] = time.time,
                 graph: Any = None, flag_map: dict | None = None, rehearsal: bool = False,
                 books: list[dict] | None = None):
        self.conn, self.apps, self.core, self.http, self.observer_url = conn, apps, core, http, observer_url
        self.services, self.policy, self.publish, self.receipts = services, policy_cfg, publish, receipts
        self.approvers, self.clock = approvers, clock
        self.lock = threading.Lock()
        self.run_lock = asyncio.Lock()
        self.verify_every = 5.0
        self.tasks: set[asyncio.Task] = set()
        self.graph = graph  # brain.graph.DependencyGraph; None = blast radius unknown
        self.flag_map = flag_map or {}  # config/services.yaml `flags:` (flag -> service)
        self.heartbeats: dict[int, float] = {}
        self.verifying: dict[int, asyncio.Task] = {}
        self.rehearsal = rehearsal  # ONCALL_REHEARSAL=1: bench trust runs, per-hour budget lifted
        self.why: dict[str, str] = {}  # incident id -> card "Why" line; ponytail: never pruned, tiny per incident
        self.books = books or []  # config/runbooks.yaml; hard rules enforced in steps 3 and 7
        self.guide: dict[str, dict] = {}  # incident id -> runbook + seen-before for Discord; same ceiling as why
        self.health: dict[str, dict] = {}  # incident id -> last health read, for the card's numbers; same ponytail
        self.intents: IntentStore | None = None  # orchestration on (migration v2): durable action intents
        self.workspace: Any = None  # schemas.workspace.Workspace on the same connection: read views only
        self.orchestration: Any = None  # schemas.orchestration.OrchestrationPolicy this gateway started with

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

    def card(self, row: dict, target: str | None, **kw: Any) -> Card:
        return build_incident_card(self.card_incident(row, target), why=self.why.get(row["id"]),
                                   pattern=row.get("pattern"), model_says=row.get("llm_why"),
                                   health=self.health.get(row["id"]), **kw)

    # runbook + "seen before" line for one incident's notification payloads; first computed in run()
    def guidance(self, incident_id: str, pattern: str | None = None, tool: str | None = None,
                 target: str | None = None, matched: list[dict] | None = None) -> dict:
        if matched is None and incident_id in self.guide:
            return self.guide[incident_id]
        if matched is None:
            matched = runbooks.match(self.books, pattern, target, tool, None)
        row = self.incident(incident_id) or {}
        with self.lock:
            past = memory.similar(self.conn, incident_id, row.get("culprit") or target, pattern or row.get("pattern"))
        self.guide[incident_id] = {"runbook": runbooks.brief(matched[0]) if matched else None,
                                   "seen_before": memory.summary(past)}
        return self.guide[incident_id]

    async def step(self, incident_id: str, steps: list[dict], name: str, passed: bool, reason: str | None = None):
        steps.append({"name": name, "passed": passed, "reason": reason})
        await self.publish({"type": "checklist_step", "incident_id": incident_id,
                            "payload": {"name": name, "passed": passed, "reason": reason}})

    async def get_json(self, path: str, **params: Any) -> Any:
        r = await self.http.get(f"{self.observer_url}{path}", params=params, timeout=10, headers=auth.headers())
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
        if reason and reason.startswith("API server refused"):  # RBAC or admission said no (scenario 12)
            await self.publish({"type": "blocked", "incident_id": incident_id,
                                "payload": {"step": name, "tool": getattr(action, "tool", None), "reason": reason}})
        decision = GatewayDecision(decision=outcome, failed_step=name, reason=reason)  # type: ignore[arg-type]
        if row is not None and name == "approval" and row.get("state") == "resolved":
            # a follow-up (raise_limit after a restart) on a fixed incident: stay resolved, ticket the day
            # team instead of waking on-call (Muaz chose); the notifier tickets a MITIGATED card
            card = self.card(row, target, decision=decision, mitigated=True, reason=reason,
                             proposal=action if isinstance(action, ActionRequest) else None)
            await self.publish({"type": "incident_resolved", "incident_id": incident_id,
                                "payload": {"card": card.model_dump(mode="json"),
                                            "briefing": f"follow-up not done: {reason}"}})
            return decision
        if row is not None:
            gone = name == "freshness" and outcome == "refused"
            event = "incident_resolved" if gone else ("handed_off" if outcome == "handed_off" else "escalated")
            card = self.card(row, target, decision=decision,
                             proposal=action if isinstance(action, ActionRequest) else None)
            self.set_state(incident_id, {"incident_resolved": "resolved"}.get(event, event))
            pattern = action.pattern if isinstance(action, ActionRequest) else action.get("pattern")
            tool = action.tool if isinstance(action, ActionRequest) else action.get("tool")
            await self.publish({"type": event, "incident_id": incident_id,
                                "payload": {"card": card.model_dump(mode="json"), "briefing": reason or "",
                                            **self.guidance(incident_id, pattern, tool, target)}})
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

    async def decide(self, approval_id: str, decision: str, decided_by: str, via: str = "discord") -> GatewayDecision:
        row = approvals.get(self.conn, approval_id)
        if row is None:
            return GatewayDecision(decision="refused", failed_step="approval", reason="unknown approval")
        if decided_by not in self.approvers:
            return GatewayDecision(decision="refused", failed_step="approval", reason="not an approver")
        if row["state"] != "pending":
            return GatewayDecision(decision="refused", failed_step="approval", reason=f"approval is {row['state']}")
        action = ActionRequest.model_validate_json(row["action_json"])
        inc = self.incident(action.incident_id)
        intent_id = row.get("intent_id") if self.intents is not None else None
        if intent_id is not None and (stale := self.stale_intent(intent_id)):
            # an approval asked for one plan never authorises another (handoff §5.3)
            approvals.set_state(self.conn, approval_id, "superseded", decided_by)
            await self.publish({"type": "approval_decided", "incident_id": action.incident_id,
                                "payload": {"approval_id": approval_id, "decision": "superseded",
                                            "decided_by": decided_by, "via": via}})
            await self.moved(intent_id, "superseded", reason=stale)
            return GatewayDecision(decision="refused", failed_step="approval", reason=f"stale_plan: {stale}")
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
                            "payload": {"approval_id": approval_id, "decision": state, "decided_by": decided_by,
                                        "via": via}})
        if state != "approved":
            if intent_id is not None:
                await self.moved(intent_id, "terminal", reason=f"approval {state}")
            return await self.stop(action, inc, [], "approval", "escalated", f"approval {state}")
        # things may have changed while we waited: steps 2 to 6 again, trust gate skipped
        token = _intent.set(intent_id)
        try:
            out = await self.run(action, [{"name": "approval", "passed": True, "reason": decided_by}], approved=True,
                                 approved_by=decided_by)
        finally:
            _intent.reset(token)
        if intent_id is not None:
            await self.settle_intent(intent_id, out)
        return out

    # ---- steps 2 to 8 --------------------------------------------------------------------------
    # one checklist at a time: step 3 counts in-flight actions, then awaits the API; a second run checking
    # in that gap passed too and both executed. ponytail: global lock, fine at one incident at a time
    async def run(self, action: ActionRequest, steps: list[dict], approved: bool,
                  approved_by: str | None = None) -> GatewayDecision:
        async with self.run_lock:
            return await self._run(action, steps, approved, approved_by)

    async def _run(self, action: ActionRequest, steps: list[dict], approved: bool,
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
        self.health[action.incident_id] = health

        entry = next((r for r in journal_rows if r["id"] == action.journal_entry), None)
        if (why := why_text(entry, row["onset_at"])) is not None:
            self.why[action.incident_id] = why
        # company runbooks, matched by code from what the gateway itself read (never the brain's word)
        matched = runbooks.match(self.books, action.pattern, action.target, action.tool,
                                 entry["kind"] if entry else None)
        self.guidance(action.incident_id, matched=matched)
        needs_human, forbidden_by = runbooks.hard_rules(matched, action.tool)

        # 2 hands-off: a human changed something after we opened the incident (chaos injections excluded:
        # live, a flag flip landing while another incident was open handed that incident off)
        human = [r for r in journal_rows if not r["by_agent"] and r["ts"] >= (row["opened_at"] or 0)
                 and r.get("field_manager") != CHAOS_MANAGER]
        if human:
            return await self.stop(action, row, steps, "hands_off", "handed_off",
                                   f"{human[-1]['object']} changed by {human[-1]['field_manager']}")
        await self.step(action.incident_id, steps, "hands_off", True)

        # 3 policy
        with self.lock:
            used = policy.usage(self.conn, action.incident_id, self.clock())
        if self.rehearsal:  # 3/hour would stretch the ~60 overnight trust runs over 20 h (Muaz chose)
            used = {**used, "hour": 0}
        protected = bool(self.services.get(action.target, {}).get("protected"))
        # these can only end in an approval request, so an action still verifying doesn't block them
        # a fix the model chose itself (not the rule's first pick) always goes to a human
        chosen_by_model = action.origin == "model"
        asking = not approved and (self.policy["tools"][action.tool]["auto_eligible"] is False or protected
                                   or chosen_by_model)
        ok, outcome, reason = policy.check(action.model_dump(), self.services, self.policy, used, asking=asking)
        if not ok:
            return await self.stop(action, row, steps, "policy", outcome, reason)
        if row.get("major"):
            with self.lock:
                restarts = self.conn.execute("SELECT COUNT(*) FROM receipts WHERE incident_id=? AND tool=?",
                                             (action.incident_id, "restart_service")).fetchone()[0]
            if bad := policy.major_check(action.model_dump(), row.get("culprit"), restarts):
                return await self.stop(action, row, steps, "policy", "refused", bad)
        if forbidden_by:
            return await self.stop(action, row, steps, "policy", "escalated",
                                   f"runbook {forbidden_by} forbids {action.tool} on {action.target}; a human must act")
        await self.step(action.incident_id, steps, "policy", True)

        # 4 dry run + snapshot
        try:
            plan = await asyncio.to_thread(self.prepare, action, entry)
        except WriteRefused as e:
            return await self.stop(action, row, steps, "dry_run", e.outcome, e.reason)
        # major incident: no scale up, except putting back exactly the count a non-agent change took away
        # (kafka scaled to 0); that restore always waits for a human (Muaz chose)
        restore = False
        if row.get("major") and action.tool == "scale" and action.params["replicas"] > plan["replicas"]:
            restore = (entry is not None and entry["kind"] == "replicas" and not entry["by_agent"]
                       and entry["object"] == f"deployment/{action.target}"
                       and action.params["replicas"] == entry["diff"]["replicas"]["old"])
            if not restore:
                return await self.stop(action, row, steps, "dry_run", "refused", "major incident: no scale up")
        await self.step(action.incident_id, steps, "dry_run", True, f"{len(plan['diff'])} spec paths change")

        # 5 blast radius + net benefit
        edges, known = [], False
        if self.graph is not None:
            try:
                edges, known = await self.graph.get(), True
            except (httpx.HTTPError, KeyError, ValueError) as e:
                log.warning("dependency graph failed: %s", type(e).__name__)
        radius = blast.blast_radius(action.target, edges, health)
        forecast_s = 0.0 if plan["patch"]["kind"] == "configmap" else blast.forecast_added_seconds(
            action.tool, plan["replicas"], plan["surge"], plan["startup_s"])  # a flag flip restarts nothing
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
        latest = latest_change_before_onset(journal_rows, action.target, row["onset_at"] or 0, window_s,
                                            self.flag_map)
        # only "recent change" points at a journal entry; other patterns must not trip on unrelated edits
        rule_now: tuple[str, int | None]
        # nor a fix the model chose: it is allowed to differ from the rule, and a human reviews it anyway.
        # Still-sick and still-live are checked for it like for any other action
        if action.pattern == "recent_change" and not chosen_by_model:
            rule_now = (action.pattern, latest["id"] if latest else None)
        else:
            rule_now = (action.pattern, action.journal_entry)
        if action.journal_entry is not None and entry is None:
            missing = f"journal entry {action.journal_entry} not found"
            if not approved:
                return await self.ask(action, row, steps, plan, missing, step_name="freshness")
            return await self.stop(action, row, steps, "freshness", "escalated", missing)
        if health.get("prometheus_ok") is False:  # observer kept its last reading: not a live picture
            stale = "health data is stale (Prometheus not answering); acting on it is a guess"
            if not approved:
                return await self.ask(action, row, steps, plan, stale, step_name="freshness")
            return await self.stop(action, row, steps, "freshness", "escalated", stale)
        victims = json.loads(row.get("victims_json") or "[]")
        outcome, reason = freshness.check(health, action.target, (action.pattern, action.journal_entry), rule_now,
                                          entry, plan["live"], victims)
        if outcome != "ok":
            if outcome == "awaiting_approval" and not approved:
                return await self.ask(action, row, steps, plan, reason, step_name="freshness")
            return await self.stop(action, row, steps, "freshness", outcome if outcome == "refused" else "escalated",
                                   reason)
        await self.step(action.incident_id, steps, "freshness", True)
        plan["health"] = health  # the verifier's "before" picture

        # 7 trust gate (skipped after a human approval)
        kind = self.services[action.target].get("kind", "stateless")
        with self.lock:
            gate = trust.check(self.conn, self.policy["trust"], self.policy["tools"][action.tool], action.pattern,
                               action.tool, action.target, kind)
        if not approved and needs_human:
            return await self.ask(action, row, steps, plan, f"runbook {', '.join(needs_human)} requires a human "
                                                            "to approve this action", gate)
        if not approved and restore:
            return await self.ask(action, row, steps, plan, "major incident: scaling back to the count before "
                                                            "the outage needs a human", gate)
        if not approved and protected:
            return await self.ask(action, row, steps, plan, f"{action.target} is a protected data store; "
                                                            "a human must approve", gate)
        if not approved and row.get("major"):
            shared = shared_change(journal_rows, row["onset_at"] or 0, window_s)
            if not (action.pattern == "recent_change" and shared and action.journal_entry == shared["id"]):
                return await self.ask(action, row, steps, plan, "major incident: a human approves every action "
                                                                "except reverting the shared change", gate)
        if not approved and chosen_by_model:
            return await self.ask(action, row, steps, plan, "the agent chose this fix itself, not the rule's "
                                                            "first pick; a human must approve", gate)
        if not approved:
            if not gate["open"]:
                return await self.ask(action, row, steps, plan, f"trust bound {gate['lower_bound']} < {gate['bar']}",
                                      gate)
            await self.step(action.incident_id, steps, "trust_gate", True, f"bound {gate['lower_bound']}")

        # 8 execute
        return await self.execute(action, row, steps, plan, {**gate, "approved_by": approved_by, "pattern": action.pattern,
                                                             "origin": action.origin})

    async def ask(self, action: ActionRequest, row: dict, steps: list[dict], plan: dict, reason: str | None,
                  gate: dict | None = None, step_name: str = "trust_gate") -> GatewayDecision:
        await self.step(action.incident_id, steps, step_name, False, reason)
        intent_id = _intent.get()
        with self.lock:
            appr = approvals.create(self.conn, action.incident_id, action.model_dump(mode="json"), self.clock(),
                                    self.policy["approval"]["expiry_seconds"], intent_id=intent_id)
        if intent_id is not None:
            await self.moved(intent_id, "awaiting_approval", approval_id=appr["id"], reason=reason)
        decision = GatewayDecision(decision="awaiting_approval", failed_step=step_name, reason=reason,
                                   approval_id=appr["id"])
        card = self.card(row, action.target, decision=decision, proposal=action, did=plan["summary"])
        changed = ", ".join(sorted(plan["diff"]))[:500]
        await self.publish({"type": "approval_requested", "incident_id": action.incident_id, "payload": {
            "card": card.model_dump(mode="json"), "approval_id": appr["id"], "expires_at": appr["expires_at"],
            "diff": f"{action.tool} {action.target}: {plan['summary']}; changes {changed}",
            "forecast": forecast_text(plan), **self.guidance(action.incident_id)}})
        self.set_state(action.incident_id, "awaiting_approval")
        return decision

    def write(self, target: str, patch: dict, dry_run: bool) -> dict:
        if patch["kind"] == "configmap":
            return patch_configmap(self.core, patch["name"], patch["body"], dry_run)
        if patch["kind"] == "scale":
            return patch_scale(self.apps, target, patch["body"], dry_run)
        return patch_deployment(self.apps, target, patch["body"], dry_run, patch["content_type"])

    # blocking reads + dry run with the agent identity; runs in a thread
    def prepare(self, action: ActionRequest, entry: dict | None) -> dict:
        if action.tool == "revert_config" and entry is not None and entry["kind"] == "flag":
            return self.prepare_flag(action, entry)
        target = action.target
        live = read_deployment(self.apps, target)
        rss = list_json(self.apps.list_namespaced_replica_set) if action.tool == "rollback_deploy" else []
        now_iso = datetime.fromtimestamp(self.clock(), timezone.utc).isoformat()
        patch = build_patch(action.tool, live, action.params, entry, rss, now_iso)
        dry = self.write(target, patch, dry_run=True)
        if patch["kind"] == "scale":
            diff = spec_diff({"replicas": live["spec"].get("replicas")}, {"replicas": dry["spec"].get("replicas")})
            inverse = {"op": "scale", "target": target, "replicas": live["spec"].get("replicas")}
            bounds = self.policy["tools"]["scale"]
            # scale 0 -> 1 brings a store back; its undo (back to 0) would re-break it and admission refuses it
            if not bounds["min"] <= (inverse["replicas"] or 0) <= bounds["max"]:
                inverse = {"op": "none", "target": target,
                           "why": f"undo would scale {target} to {inverse['replicas'] or 0} replicas, "
                                  f"outside the allowed {bounds['min']}-{bounds['max']}"}
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
                "surge": blast.surge_ok(live), "startup_s": blast.startup_seconds(pod_objs),
                "declared": f"deployment/{target}"}

    # flag revert: patch only flagd-config, check the dry run moved exactly the recorded flags
    def prepare_flag(self, action: ActionRequest, entry: dict) -> dict:
        name = entry["object"].split("/", 1)[1]
        live = read_configmap(self.core, name)
        patch = build_flag_patch(live, entry)
        dry = self.write(action.target, patch, dry_run=True)
        moved = journal.entry("configmap", live, dry, self.clock(), name)
        diff = moved["diff"] if moved else {}
        if not diff:
            raise WriteRefused("refused", "revert_config would change nothing (flag already back?)")
        if set(diff) != patch["expected"]:
            raise WriteRefused("escalated", f"dry run moved other flags too: {sorted(set(diff) - patch['expected'])}")
        hashes = spec_hashes(list_json(self.apps.list_namespaced_deployment), list_json(self.core.list_namespaced_config_map))
        pods = [p["metadata"]["name"] for p in list_json(self.core.list_namespaced_pod) if service_of(p) == action.target]
        return {"live": live, "patch": patch, "diff": diff, "summary": patch["summary"], "hashes": hashes,
                "pods": pods, "replicas": 1, "surge": True, "startup_s": 0.0, "declared": f"configmap/{name}",
                "inverse": {"op": "restore_configmap", "target": action.target, "name": name, "data": live["data"]}}

    async def execute(self, action: ActionRequest, row: dict, steps: list[dict], plan: dict,
                      gate: dict) -> GatewayDecision:
        intent_id = _intent.get()
        # intent first, committed, before the cluster sees anything: a crash after this is reconcilable
        if intent_id is not None and not await self.moved(intent_id, "executing", precondition_json=precondition(plan),
                                                          executing_at=self.clock()):
            return await self.stop(action, row, steps, "execute", "escalated",
                                   f"intent {intent_id} is no longer current; nothing written")
        try:
            await asyncio.to_thread(self.write, action.target, plan["patch"], False)
        except WriteRefused as e:
            if intent_id is not None:
                if e.unknown:  # may have landed: never retry, never undo blind; the slot stays held
                    why = f"{e.reason}; then clear intent {intent_id}"
                    await self.moved(intent_id, "execution_unknown", reason=why)
                    return await self.stop(action, row, steps, "execute", "escalated", why)
                await self.moved(intent_id, "terminal", reason=e.reason)
            return await self.stop(action, row, steps, "execute", e.outcome, e.reason)
        except Exception as e:
            if intent_id is None:
                raise
            why = f"write outcome unknown ({type(e).__name__}); check the cluster, then clear intent {intent_id}"
            await self.moved(intent_id, "execution_unknown", reason=why)
            return await self.stop(action, row, steps, "execute", "escalated", why)
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
                              (tier_of(gate), action.incident_id))
            self.conn.commit()
        await self.publish({"type": "action_executed", "incident_id": action.incident_id,
                            "payload": {"receipt_id": receipt_id, "tool": action.tool, "target": action.target,
                                        "tier": tier_of(gate)}})
        if intent_id is not None:
            await self.moved(intent_id, "verifying", receipt_id=receipt_id)
            plan["scope"] = self.verification_scope(action, row, plan)
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
        extra = cfg["flag_extra_seconds"] if plan["patch"]["kind"] == "configmap" else 0  # flagd reload ~60 s
        # aborting means undoing; with no safe undo, give the fix its whole window instead
        can_undo = plan["inverse"]["op"] != "none"
        scope = plan.get("scope")  # orchestration: this action's own services, frozen at execute time
        v = Verification(self.clock(), plan["health"], action.target, victims,
                         action.prediction.model_dump() if action.prediction else None,
                         cfg["window_seconds"] + extra, cfg["early_abort"] and can_undo,
                         grace_s=cfg["early_abort_grace_seconds"] + extra, prediction_delay_s=extra,
                         scope=set(scope["services"]) if scope else None)
        health, human, result = plan["health"], [], None
        while result is None:
            await asyncio.sleep(self.verify_every)
            try:
                health = await self.get_json("/health/now")
                human = [r for r in await self.get_json("/journal", since=v.t0) if not r["by_agent"]]
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
        harm = harm_check(plan["hashes"], after, plan["declared"], {r["object"] for r in human},
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

    async def undo_and_close(self, receipt_id: int, action: ActionRequest, row: dict, receipt: Receipt,
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
                **self.guidance(action.incident_id, action.pattern, action.tool, action.target)}})
            self.set_state(action.incident_id, "escalated")
            return "undo_failed"
        await self.publish({"type": "action_undone", "incident_id": action.incident_id,
                            "payload": {"receipt_id": receipt_id, "reason": reason}})
        return await self.close(receipt_id, action, row, receipt, v, "undone", harm, reason, hash_after, plan=plan)

    # fix did not prove itself but undoing it is unsafe (or we could not see): leave it, hand it to a person.
    # failure=False: blind to the end, which says nothing about the fix
    async def keep_and_page(self, receipt_id: int, action: ActionRequest, row: dict, receipt: Receipt,
                            reason: str, failure: bool = True) -> str:
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
            "card": card.model_dump(mode="json"), "briefing": briefing}})
        self.set_state(action.incident_id, "escalated")
        return "handed_off"

    # pause an in-progress rollout first so the inverse lands on a still object (§6.4.9 Undo);
    # always unpause, a failed undo must not leave the Deployment paused
    def undo(self, target: str, inverse: dict, pause: bool) -> None:
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

    async def close(self, receipt_id: int, action: ActionRequest, row: dict, receipt: Receipt, v: Verification,
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
        victims = json.loads(row.get("victims_json") or "[]")
        card = self.card(row, action.target, receipt=final, receipt_id=receipt_id, mitigated=mitigated,
                         reason=reason,
                         took_s=self.clock() - (row.get("opened_at") or v.t0), did=(plan or {}).get("summary"),
                         metric=error_change((plan or {}).get("health") or {}, v.last_health,
                                             [action.target, *victims]))
        # the bench (§9.1) reads tier, harm, prediction and forecast vs actual off the terminal event
        await self.publish({"type": event, "incident_id": action.incident_id, "payload": {
            "card": card.model_dump(mode="json"), "receipt_url": f"/receipts/{receipt_id}",
            "briefing": reason or "", "receipt_id": receipt_id, "tier": tier_of(receipt.trust),
            "prediction_held": final.prediction_held, "harm_clean": final.harm_clean,
            "forecast_s": final.forecast_s, "actual_added_s": final.added_disruption_s,
            **self.guidance(action.incident_id, action.pattern, action.tool, action.target)}})
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
    async def clear_receipt(self, receipt_id: int, decided_by: str) -> dict:
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
            if self.intents is not None and r.get("intent_id"):
                await self.moved(r["intent_id"], "terminal", reason="approval expired")
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
            if inverse.get("op") == "none":
                # nothing safe to undo (a store scaled back from 0): keep the fix, page, don't block (Muaz chose);
                # losing track says nothing about the fix, so no trust failure
                view = self.receipts.get(r["id"])
                lost = ActionRequest(incident_id=r["incident_id"], tool=r["tool"], target=r["target"],
                                     pattern=gate.get("pattern") or "unknown",
                                     evidence_ids=view.evidence_ids if view else [])
                await self.keep_and_page(r["id"], lost, row, view or Receipt(
                    incident_id=r["incident_id"], tool=r["tool"], target=r["target"], diff={}, inverse=inverse,
                    evidence_ids=[]), f"{reason}; no safe undo, fix kept", failure=False)
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
                                                            r["target"])}})
            done += 1
        return done

    async def upkeep(self, every_s: float = 5) -> None:
        while True:
            try:
                await self.expire_approvals()
                await self.watchdog()
                if self.intents is not None:
                    await self.sync_intents()
                    await self.drain_intents()
            except Exception as e:  # never let upkeep die quietly
                log.error("upkeep failed: %r", e)
            await asyncio.sleep(every_s)

    # ---- orchestration intents (handoff §9) ------------------------------------------------------------
    async def moved(self, intent_id: str, to: str, **fields: Any) -> bool:
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
    def stale_intent(self, intent_id: str) -> str | None:
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

    def slot_busy(self) -> bool:
        with self.lock:
            used = policy.usage(self.conn, "", self.clock())["in_flight"]
        return used >= self.policy["budgets"]["max_in_flight"]

    # step 3's "asking": these end in an approval request, so a busy slot does not hold them back
    def will_ask(self, action: ActionRequest) -> bool:
        protected = bool(self.services.get(action.target, {}).get("protected"))
        return (self.policy["tools"].get(action.tool, {}).get("auto_eligible") is False or protected
                or action.origin == "model")

    async def submit_intent(self, env: IntentEnvelope) -> IntentSubmission:
        if self.intents is None:
            raise RuntimeError("orchestration intents are off in this gateway")
        row, created = self.intents.create_or_get(env)  # Conflict when the id holds another action
        if not created:
            return submission(row)
        steps: list[dict] = []
        await self.step(env.incident_id, steps, "schema", True)
        return await self.run_intent(row, steps)

    # busy slot: queue, never refuse; the queue drains in upkeep and reruns the whole checklist then
    async def run_intent(self, row: dict, steps: list[dict]) -> IntentSubmission:
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
    async def settle_intent(self, intent_id: str, decision: GatewayDecision) -> None:
        assert self.intents is not None
        row = self.intents.get(intent_id)
        if row is None or row["status"] not in ("new", "queued", "awaiting_approval"):
            return
        if decision.decision == "awaiting_approval":
            return
        await self.moved(intent_id, "terminal", reason=f"{decision.decision}: {decision.reason or decision.failed_step}")

    async def drain_intents(self) -> None:
        assert self.intents is not None
        row = self.intents.oldest("queued")
        if row is not None and not self.slot_busy():
            await self.run_intent(row, [])

    # verification finished (any path: close, undo, keep and page, watchdog): the intent is done
    async def sync_intents(self) -> None:
        assert self.intents is not None
        for row in self.intents.with_status("verifying"):
            with self.lock:
                r = self.conn.execute("SELECT outcome FROM receipts WHERE id=?", (row["receipt_id"],)).fetchone()
            if r is not None and r["outcome"] not in ("pending", "watchdog_failed"):
                await self.moved(row["intent_id"], "terminal", reason=f"receipt #{row['receipt_id']}: {r['outcome']}")

    # services this action answers for, and services another open incident broke on its own before it
    def verification_scope(self, action: ActionRequest, row: dict, plan: dict) -> dict:
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
    async def reconcile_intents(self) -> list[str]:
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
    async def clear_intent(self, intent_id: str, decided_by: str) -> dict:
        if self.intents is None or decided_by not in self.approvers:
            return {"cleared": False, "reason": "not an approver" if self.intents else "orchestration off"}
        row = self.intents.get(intent_id)
        if row is None or row["status"] != "execution_unknown":
            return {"cleared": False, "reason": f"intent is {row['status'] if row else 'unknown'}"}
        await self.moved(intent_id, "terminal", reason=f"cleared by {decided_by} after checking the cluster")
        await self.publish({"type": "checklist_step", "incident_id": row["incident_id"], "payload": {
            "name": "human_clear", "passed": True, "reason": f"intent {intent_id} cleared by {decided_by}"}})
        return {"cleared": True}

