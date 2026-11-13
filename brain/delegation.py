# code-owned delegation gate (handoff §7): the commander may only ask for a question code found in the
# evidence; code picks role, scope, budget and deadline, admits atomically against durable caps, runs the
# read-only specialist outside any transaction and hands back a checked finding.
import asyncio
import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from typing import Any

from pydantic_ai.exceptions import AgentRunError, UsageLimitExceeded
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import RunUsage, UsageLimits

from brain.budget import DEFAULT_OUTPUT, BudgetedModel
from brain.redact import redact_value
from brain.specialists import TOOL_NAMES, change_causality_agent
from brain.tools import ToolBox
from schemas.orchestration import (AdmissionResult, DelegationRecord, DenialReason, EligibleQuestion, FindingResult,
                                   OrchestrationPolicy, fingerprint)
from schemas.workspace import Workspace

log = logging.getLogger("brain.delegation")
MIN_SPECIALIST_S = 15  # less than this left: the commander answers with what it has
MAX_HYPOTHESES = 3
EXPLAIN: dict[str, str] = {
    "simple_read_sufficient": "Read the competing changes yourself first; one read may settle it",
    "no_eligible_question": "No specialist needed: that question is not open for this incident",
    "already_answered": "Already checked for this incident and scope; use the earlier finding",
    "duplicate_active": "A specialist is already on this question",
    "stale_plan": "The plan changed; look at the current one",
    "incident_terminal": "The incident is over",
    "scope_denied": "Outside this incident's scope",
    "child_limit": "This incident already used its specialists",
    "fleet_busy": "All specialist slots are busy",
    "request_budget": "Not enough model requests left for a specialist and the final answer",
    "token_budget": "Not enough tokens left for a specialist",
    "deadline": "Too little time left for a specialist",
}


@dataclass
class DelegationContext:
    gate: "Delegation"
    incident_id: str
    plan_revision: int
    questions: list[EligibleQuestion]
    candidates: list[dict] = field(default_factory=list)
    findings: list[FindingResult] = field(default_factory=list)

    # what the commander's brief shows; empty lists keep the brief honest about "nothing to delegate"
    def brief(self) -> dict[str, Any]:
        return {"plan_revision": self.plan_revision,
                "eligible_questions": [{"question_id": q.question_id, "type": q.type, "journal_ids": q.journal_ids,
                                        "hypotheses": q.hypotheses} for q in self.questions],
                "findings": [f.model_dump(mode="json", exclude_none=True) for f in self.findings]}

    async def request(self, box: ToolBox, question_id: str, expected_plan_revision: int, usage: RunUsage,
                      limits: UsageLimits | None) -> AdmissionResult:
        result = await self.gate.admit(self, question_id, expected_plan_revision, set(box.ledger))
        if result.status == "admitted" and result.task_id is not None:
            finding = await self.gate.run_specialist(self, result.task_id, box, usage, limits)
            return result.model_copy(update={"finding": finding})
        return result


# change questions only: two or more recorded changes behind candidates on services in scope
def catalog(incident_id: str, candidates: list[dict], scope: list[str], plan_revision: int) -> list[EligibleQuestion]:
    in_scope = set(scope)
    by_change: dict[int, dict] = {}
    for c in candidates:
        a = c["action"]
        if a.get("journal_entry") is not None and a["target"] in in_scope:
            by_change.setdefault(int(a["journal_entry"]), c)
    if len(by_change) < 2:
        return []
    picked = sorted(by_change.items())[:MAX_HYPOTHESES]
    journal_ids = [j for j, _ in picked]
    q_scope = sorted(in_scope | {c["action"]["target"] for _, c in picked})
    # no incident id: the same changes on the same services are the same question for any incident
    fp = fingerprint({"type": "change_causality", "journal_ids": journal_ids, "scope": q_scope})
    return [EligibleQuestion(question_id=f"q-{fp[:12]}", type="change_causality", incident_id=incident_id,
                             scope=q_scope, journal_ids=journal_ids, hypotheses=[c["id"] for _, c in picked],
                             plan_revision=plan_revision, fingerprint=fp)]


class Delegation:
    def __init__(self, workspace: Workspace, policy: OrchestrationPolicy, model: Model,
                 publish: Callable[[str, str | None, dict], Awaitable[None]], clock: Callable[[], float] = time.time,
                 owner: str = "brain"):
        self.ws, self.policy, self.model, self.publish, self.clock = workspace, policy, model, publish, clock
        self.owner = owner
        self.agent = change_causality_agent(model, policy.max_specialist_tool_calls)

    # built once per commander run; says why nobody else starts when there is nothing to ask
    async def context(self, incident_id: str, candidates: list[dict], scope: list[str]) -> DelegationContext:
        w = self.ws.workspace(incident_id)
        plan = int(w["plan_revision"]) if w else 0
        questions = catalog(incident_id, candidates, scope, plan)
        findings = [f for q in questions if (f := self.ws.finding_for(q.fingerprint)) is not None]
        ctx = DelegationContext(self, incident_id, plan, questions, candidates, findings)
        if not questions:
            cause = (w["cause_key"] or "") if w else ""
            why = (f"No specialist needed: shared cause {cause.split(':', 1)[1]} already supported"
                   if cause.startswith("dependency:") and len(scope) > 1
                   else "No specialist needed: at most one recorded change fits")
            await self.decide(incident_id, DelegationRecord(status="none_needed", explanation=why, ts=self.clock()))
        return ctx

    async def decide(self, incident_id: str, record: DelegationRecord, task_id: str | None = None) -> None:
        with self.ws.tx() as c:
            self.ws.record_delegation(c, incident_id, record)
        await self.publish("delegation_decided", incident_id, {
            "status": record.status, "explanation": record.explanation, "reason": record.reason,
            "question_id": record.question_id, "task_id": task_id})

    async def deny(self, ctx: DelegationContext, question_id: str, reason: DenialReason) -> AdmissionResult:
        await self.decide(ctx.incident_id, DelegationRecord(status="denied", reason=reason, question_id=question_id,
                                                            explanation=EXPLAIN[reason], ts=self.clock()))
        return AdmissionResult(status="denied", reason=reason)

    # the full gate, again, every time the model asks: the hidden tool is not the only guard
    async def admit(self, ctx: DelegationContext, question_id: str, expected_plan: int,
                    delivered: set[str]) -> AdmissionResult:
        q = next((q for q in ctx.questions if q.question_id == question_id), None)
        if q is None:
            return await self.deny(ctx, question_id, "no_eligible_question")
        w = self.ws.workspace(ctx.incident_id)
        if w is None or w["phase"] == "terminal":
            return await self.deny(ctx, question_id, "incident_terminal")
        if w["plan_revision"] != expected_plan:
            return await self.deny(ctx, question_id, "stale_plan")
        if any(f"journal:{j}" not in delivered for j in q.journal_ids):
            return await self.deny(ctx, question_id, "simple_read_sufficient")
        if (found := self.ws.finding_for(q.fingerprint)) is not None:
            await self.decide(ctx.incident_id, DelegationRecord(status="reused", question_id=question_id, ts=self.clock(),
                                                                explanation="Reused an earlier finding; no new reads"))
            return AdmissionResult(status="reused", finding=found)
        now = self.clock()
        deadline_at = w["deadline_at"] or now + self.policy.investigation_deadline_seconds
        if deadline_at - now < MIN_SPECIALIST_S:
            return await self.deny(ctx, question_id, "deadline")
        task_deadline = now + min(self.policy.specialist_deadline_seconds, deadline_at - now - MIN_SPECIALIST_S / 3)
        task_id = f"task-{uuid.uuid4().hex[:12]}"
        reason: DenialReason | None = None
        with self.ws.tx() as c:
            prior = c.execute("SELECT state FROM investigation_tasks WHERE incident_id=? AND fingerprint=? AND "
                              "scope_revision=?", (ctx.incident_id, q.fingerprint, w["scope_revision"])).fetchone()
            started = c.execute("SELECT specialists_started FROM orchestration_workspaces WHERE incident_id=?",
                                (ctx.incident_id,)).fetchone()[0]
            fleet = c.execute("SELECT COUNT(*) FROM investigation_tasks WHERE state IN ('pending', 'running')"
                              ).fetchone()[0]
            used = c.execute("SELECT COUNT(*) FROM model_calls WHERE incident_id=?", (ctx.incident_id,)).fetchone()[0]
            spent = self.ws.spent(c, ctx.incident_id)
            if prior is not None:
                reason = "duplicate_active" if prior["state"] in ("pending", "running") else "already_answered"
            elif started >= self.policy.max_specialists_per_incident:
                reason = "child_limit"
            elif fleet >= self.policy.max_active_specialists:
                reason = "fleet_busy"
            elif used + self.policy.reserved_commander_requests + 1 > self.policy.max_model_requests:
                reason = "request_budget"
            elif self.policy.max_total_tokens is not None and spent + 2 * DEFAULT_OUTPUT > self.policy.max_total_tokens:
                reason = "token_budget"
            else:
                self.ws.create_task(c, task_id, ctx.incident_id, q.question_id, q.type, q.fingerprint,
                                    w["scope_revision"], w["plan_revision"],
                                    {"scope": q.scope, "journal_ids": q.journal_ids, "hypotheses": q.hypotheses},
                                    TOOL_NAMES[q.type], task_deadline, self.policy.max_requests_per_specialist,
                                    self.policy.max_specialist_tool_calls)
                c.execute("UPDATE orchestration_workspaces SET specialists_started=specialists_started+1, "
                          "revision=revision+1 WHERE incident_id=?", (ctx.incident_id,))
                self.ws.record_delegation(c, ctx.incident_id, DelegationRecord(
                    status="admitted", question_id=question_id, ts=now,
                    explanation=f"Change check started: {len(q.journal_ids)} recorded changes still plausible"))
        if reason is not None:
            return await self.deny(ctx, question_id, reason)
        await self.publish("delegation_decided", ctx.incident_id, {
            "status": "admitted", "question_id": question_id, "task_id": task_id,
            "explanation": f"Change check started: {len(q.journal_ids)} recorded changes still plausible"})
        return AdmissionResult(status="admitted", task_id=task_id)

    async def task_event(self, incident_id: str, task_id: str, question_id: str, state: str, attempt: int) -> None:
        await self.publish("investigation_task_changed", incident_id, {
            "task_id": task_id, "question_id": question_id, "state": state, "attempt": attempt})

    # outside any transaction; shares the parent's usage and limits; a late or bad result never lands
    async def run_specialist(self, ctx: DelegationContext, task_id: str, parent: ToolBox, usage: RunUsage,
                             limits: UsageLimits | None) -> FindingResult | None:
        task = self.ws.task(task_id)
        q = next(q for q in ctx.questions if q.question_id == task["question_id"]) if task else None
        token = self.ws.claim_task(task_id, self.owner, 0) if task else None
        if task is None or q is None or token is None:
            return None
        await self.task_event(ctx.incident_id, task_id, q.question_id, "running", token)
        child = replace(parent, services=list(q.scope), ledger={}, calls=0, choose=False, candidates=[],
                        tools_ok=set(), run_id=task_id, question=q, orch=None, needs_prediction=False)
        model = BudgetedModel(self.model, self.ws, ctx.incident_id, task_id, "specialist", task_id=task_id,
                              task_limit=self.policy.max_requests_per_specialist, publish=self.publish,
                              clock=self.clock)
        brief = redact_value({"question_id": q.question_id, "scope": q.scope,
                              "seconds_since_onset": round(parent.now - parent.incident.onset_at),
                              "candidates": [{"id": c["id"], "basis": c["basis"], "journal_entry":
                                              c["action"].get("journal_entry"), "tool": c["action"]["tool"],
                                              "target": c["action"]["target"]}
                                             for c in ctx.candidates if c["id"] in q.hypotheses]})
        beat = asyncio.create_task(self._heartbeat(task_id, token))
        state, finding, error = "failed", None, None
        try:
            async with asyncio.timeout(max(0.0, task["deadline_at"] - self.clock())):
                run = await self.agent.run(json.dumps(brief, sort_keys=True), deps=child, model=model, usage=usage,
                                           usage_limits=limits, model_settings=ModelSettings(max_tokens=DEFAULT_OUTPUT))
            finding, state = run.output, "succeeded"
        except TimeoutError:
            state, error = "timed_out", "deadline"
        except UsageLimitExceeded as e:
            error = f"budget: {e}"
        except (AgentRunError, Exception) as e:  # bad output or provider trouble: a bounded failure, no respawn
            error = type(e).__name__
        finally:
            beat.cancel()
        if self.ws.complete_task(task_id, token, state, finding, error) == "stale":
            log.info("task %s finished after its lease moved on; result dropped", task_id)
            return None
        await self.task_event(ctx.incident_id, task_id, q.question_id, state, token)
        if finding is None:
            return None
        # only what the specialist was actually shown becomes citable for the commander
        cited = [i for i in finding.evidence_ids + finding.counterevidence_ids if i in child.ledger]
        parent.ledger.update((i, child.ledger[i]) for i in cited)
        if parent.workspace is not None and parent.run_id:
            parent.workspace.deliver(parent.run_id, ctx.incident_id, [(i, None) for i in cited])
        with self.ws.tx() as c:
            self.ws.bump(c, ctx.incident_id, "plan")
        task = self.ws.task(task_id)
        await self.publish("finding_recorded", ctx.incident_id, {
            "task_id": task_id, "finding_id": task["finding_id"] if task else "", "question_id": q.question_id,
            "verdict": finding.verdict, "summary": finding.summary, "evidence_ids": finding.evidence_ids})
        ctx.findings.append(finding)
        return finding

    async def _heartbeat(self, task_id: str, token: int) -> None:
        while True:
            await asyncio.sleep(self.policy.task_heartbeat_seconds)
            if not self.ws.heartbeat(task_id, token):
                return
