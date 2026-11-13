# the checklist (IMPLEMENTATION.md §6.4.2): first failing step decides. The gateway never calls an LLM.
import asyncio
import json
import logging
import sqlite3
import threading
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

import httpx
from pydantic import ValidationError

from brain import memory, runbooks
from brain.bundle import why_text
from brain.major import shared_change
from brain.rules import latest_change_before_onset
from gateway import approvals, blast, freshness, intent_flow, policy, retries, trust, upkeep, verify_loop
from gateway.cards import build_incident_card, source, started_by
from gateway.dryrun import (
    build_flag_patch,
    build_patch,
    namespace_hash,
    outside_allowed,
    spec_diff,
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
from gateway.intents import IntentStore, precondition
from gateway.receipts import ReceiptStore
from gateway.retries import RETRY_DEADLINE_S as RETRY_DEADLINE_S
from gateway.retries import RETRY_REASONS as RETRY_REASONS
from gateway.retries import brain_retry as brain_retry
from gateway.shared import CHAOS_MANAGER as CHAOS_MANAGER
from gateway.shared import STEP_WORDS, _intent, forecast_text, tier_of
from gateway.verify_loop import error_change as error_change
from gateway.verify_loop import failed_try as failed_try
from observer import journal
from observer.kube_watch import service_of
from schemas import auth
from schemas.models import ActionRequest, Card, GatewayDecision, Incident, Receipt

log = logging.getLogger("gateway")


class Gateway:
    def __init__(self, conn: sqlite3.Connection, apps: Any, core: Any, http: httpx.AsyncClient, observer_url: str,
                 services: dict, policy_cfg: dict, publish: Callable[[dict], Awaitable[Any]],
                 receipts: ReceiptStore, approvers: set[str], clock: Callable[[], float] = time.time,
                 graph: Any = None, flag_map: dict | None = None, rehearsal: bool = False,
                 books: list[dict] | None = None,
                 request_retry: Callable[[dict], Awaitable[tuple[bool, str]]] | None = None):
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
        self.started: dict[str, dict] = {}  # incident id -> the change that started it, for Discord; same ponytail
        # retry after a clean undo (§6.4.11): None = retries off. ponytail: tries and grants live in memory;
        # a gateway restart forgets them, so the next fix the brain sends is treated as a first pick (asks more)
        self.request_retry = request_retry
        self.tries: dict[str, list[dict]] = {}  # incident id -> failed fixes, the brain's error context
        # incident id -> (granted at, attempt number); attempt None = adopted after a restart, not a retry
        self.retry_grants: dict[str, tuple[float, int | None]] = {}
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
        retry = {"tries": self.tries.get(row["id"], []), "max": self.max_tries, **kw.pop("retry", {})}
        return build_incident_card(self.card_incident(row, target), why=self.why.get(row["id"]),
                                   pattern=row.get("pattern"), model_says=row.get("llm_why"),
                                   health=self.health.get(row["id"]), retry=retry, **kw)

    @property
    def max_tries(self) -> int:
        return 1 + int(self.policy["budgets"]["max_retries"])

    # Discord's Origin block: which part of the gateway sent it, and the change that started the incident
    def facts(self, incident_id: str, row: dict | None, part: str, step: str) -> dict:
        return {"source": source(part, step),
                "started": self.started.get(incident_id) or started_by(None, row or {})}

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
                   outcome: str, reason: str | None, sent_by: tuple[str, str] | None = None) -> GatewayDecision:
        incident_id = action.incident_id if isinstance(action, ActionRequest) else str(action.get("incident_id"))
        target = action.target if isinstance(action, ActionRequest) else action.get("target")
        part, step = sent_by or ("gateway", STEP_WORDS.get(name, name))
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
                                            "briefing": f"follow-up not done: {reason}",
                                            **self.facts(incident_id, row, part, step)}})
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
                                            **self.guidance(incident_id, pattern, tool, target),
                                            **self.facts(incident_id, row, part, step)}})
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
            return await self.stop(action, inc, [], "approval", "escalated", f"approval {state}",
                                   sent_by=("gateway", "approval decision"))
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
        # the change behind the incident for Discord: the one this fix reverts, else the newest on the target
        first = entry or latest_change_before_onset(journal_rows, action.target, row["onset_at"] or 0, window_s,
                                                    self.flag_map)
        if first is not None or action.incident_id not in self.started:
            self.started[action.incident_id] = started_by(first, row)
        # a retry this gateway granted after a clean undo (close()); the brain cannot claim one
        retry = None if approved else self.retry_grants.pop(action.incident_id, (0.0, None))[1]
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
        # a fix the model chose itself (not the rule's first pick) goes to a human, except a granted retry
        # (Muaz chose): it still meets every other check, the trust gate included
        chosen_by_model = action.origin == "model"
        ask_model = chosen_by_model and retry is None
        asking = not approved and (self.policy["tools"][action.tool]["auto_eligible"] is False or protected
                                   or ask_model)
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
        if not approved and ask_model:
            return await self.ask(action, row, steps, plan, "the agent chose this fix itself, not the rule's "
                                                            "first pick; a human must approve", gate)
        if not approved:
            if not gate["open"]:
                return await self.ask(action, row, steps, plan, f"trust bound {gate['lower_bound']} < {gate['bar']}",
                                      gate)
            await self.step(action.incident_id, steps, "trust_gate", True, f"bound {gate['lower_bound']}")

        # 8 execute
        return await self.execute(action, row, steps, plan, {**gate, "approved_by": approved_by, "pattern": action.pattern,
                                                             "origin": action.origin, "attempt": retry or 1})

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
            "forecast": forecast_text(plan), **self.guidance(action.incident_id),
            **self.facts(action.incident_id, row, "gateway", STEP_WORDS.get(step_name, step_name))}})
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

    # ---- the rest of the gateway, one module per concern; each is a plain function taking the gateway -------
    # verification, undo, close (§6.4.9): gateway/verify_loop.py
    verify = verify_loop.verify
    undo_and_close = verify_loop.undo_and_close
    keep_and_page = verify_loop.keep_and_page
    undo = verify_loop.undo
    close = verify_loop.close
    rehearsal_credit = verify_loop.rehearsal_credit
    clear_receipt = verify_loop.clear_receipt
    # retry after a clean undo (§6.4.11): gateway/retries.py
    retry_blocker = retries.retry_blocker
    start_retry = retries.start_retry
    retry_timeouts = retries.retry_timeouts
    # background upkeep (§6.4.8, §6.4.10): gateway/upkeep.py
    expire_approvals = upkeep.expire_approvals
    watchdog = upkeep.watchdog
    upkeep = upkeep.upkeep
    # orchestration intents (handoff §9): gateway/intent_flow.py
    moved = intent_flow.moved
    stale_intent = intent_flow.stale_intent
    slot_busy = intent_flow.slot_busy
    will_ask = intent_flow.will_ask
    submit_intent = intent_flow.submit_intent
    run_intent = intent_flow.run_intent
    settle_intent = intent_flow.settle_intent
    drain_intents = intent_flow.drain_intents
    sync_intents = intent_flow.sync_intents
    verification_scope = intent_flow.verification_scope
    reconcile_intents = intent_flow.reconcile_intents
    clear_intent = intent_flow.clear_intent
