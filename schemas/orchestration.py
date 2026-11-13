# orchestration contracts (reports/akira-orchestration-implementation-handoff.md): episodes, workspace,
# delegation, findings, action intents, and the startup-checked config block. Mode "disabled" = legacy path.
import hashlib
import json
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import Field, model_validator

from schemas import config
from schemas.models import (ActionRequest, AdmissionStatus, IntentStatus, Model, TaskState, Verdict)

Mode = Literal["disabled", "shadow", "coordinated"]
Phase = Literal["queued", "investigating", "ready_for_action", "awaiting_gateway", "monitoring", "needs_human",
                "terminal"]
CorrelationReason = Literal["shared_dependency", "shared_change", "recurring_signature", "timing_only",
                            "contradicted", "unknown_topology", "independent"]
Symptom = Literal["errors", "latency", "pods", "mixed"]
QuestionType = Literal["change_causality"]  # dependency_origin, runtime_mechanism: later, each with a fixture
DenialReason = Literal["simple_read_sufficient", "no_eligible_question", "already_answered", "duplicate_active",
                       "stale_plan", "incident_terminal", "scope_denied", "child_limit", "fleet_busy",
                       "request_budget", "token_budget", "deadline"]


# stable identity of any json-able value: tasks, intents and evidence dedupe on it
def fingerprint(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode()).hexdigest()


class OrchestrationPolicy(Model):
    mode: Mode = "disabled"
    delegation_enabled: bool = False
    max_active_commanders: int = Field(default=2, gt=0)
    max_specialists_per_incident: int = Field(default=2, ge=0)  # lifetime starts, replacements included
    max_active_specialists: int = Field(default=2, ge=0)  # fleet-wide; commanders have their own slots
    max_delegation_depth: int = 1
    max_model_requests: int = Field(default=9, gt=0)  # commander + specialists + retries + resumes, combined
    max_requests_per_specialist: int = Field(default=2, gt=0)
    reserved_commander_requests: int = Field(default=2, gt=0)
    max_tool_calls: int = Field(default=24, gt=0)  # cache hits still count
    max_specialist_tool_calls: int = Field(default=6, gt=0)
    investigation_deadline_seconds: float = Field(default=150, gt=0)
    specialist_deadline_seconds: float = Field(default=45, gt=0)
    task_lease_seconds: float = Field(default=30, gt=0)
    task_heartbeat_seconds: float = Field(default=10, gt=0)
    # no defensible default yet: measure real prompts first; delegation stays off until both are set
    max_input_tokens_per_request: int | None = Field(default=None, gt=0)
    max_total_tokens: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def coherent(self) -> Self:
        problems = []
        if self.max_delegation_depth != 1:
            problems.append("max_delegation_depth must be 1")
        if self.reserved_commander_requests >= self.max_model_requests:
            problems.append("reserved_commander_requests must be below max_model_requests")
        if self.max_requests_per_specialist > self.max_model_requests - self.reserved_commander_requests:
            problems.append("max_requests_per_specialist exceeds what the commander reserve leaves")
        if self.max_specialist_tool_calls > self.max_tool_calls:
            problems.append("max_specialist_tool_calls exceeds max_tool_calls")
        if self.specialist_deadline_seconds > self.investigation_deadline_seconds:
            problems.append("specialist_deadline_seconds exceeds investigation_deadline_seconds")
        if self.task_heartbeat_seconds >= self.task_lease_seconds:
            problems.append("task_heartbeat_seconds must be below task_lease_seconds")
        if self.delegation_enabled:
            if self.mode != "coordinated":
                problems.append("delegation_enabled needs mode coordinated")
            if self.max_input_tokens_per_request is None or self.max_total_tokens is None:
                problems.append("delegation_enabled needs max_input_tokens_per_request and max_total_tokens")
        if problems:
            raise ValueError("; ".join(problems))
        return self


# config/orchestration.yaml; no file = disabled, so old checkouts keep the legacy path
def load_policy(root: str = "config") -> OrchestrationPolicy:
    if not (Path(root) / "orchestration.yaml").exists():
        return OrchestrationPolicy()
    return OrchestrationPolicy.model_validate(config.load("orchestration", root) or {})


# one service's sick spell as the observer saw it; the coordinator decides which incident owns it
class SignalEpisode(Model):
    episode_id: str = Field(min_length=8, max_length=64)
    cluster: str = "local"
    namespace: str = "shop"
    service: str
    symptom: Symptom
    first_breach_at: float | None = None
    sustained_at: float
    last_observed_at: float
    recovered_at: float | None = None
    source_revision: int = Field(ge=0)
    evidence_ids: list[str] = Field(default_factory=list)


class SignalBatch(Model):
    delivery_id: str = Field(min_length=8, max_length=64)
    source_revision: int = Field(ge=0)
    observed_at: float
    shadow: bool = False
    episodes: list[SignalEpisode] = Field(max_length=200)


class SignalAck(Model):
    delivery_id: str
    accepted: int = Field(ge=0)
    duplicate: bool = False


class Membership(Model):
    incident_id: str
    episode_id: str
    service: str
    reason: CorrelationReason
    evidence_ids: list[str] = Field(default_factory=list)
    added_revision: int = Field(ge=0)


# two incidents that may share a cause; never moves permission from one to the other
class IncidentLink(Model):
    incident_a: str
    incident_b: str
    relation: Literal["related", "possible_shared_cause", "contradicted"]
    reason: CorrelationReason
    supporting_ids: list[str] = Field(default_factory=list)
    contradicting_ids: list[str] = Field(default_factory=list)
    status: Literal["open", "confirmed", "rejected"] = "open"
    revision: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.incident_a >= self.incident_b:
            raise ValueError("incident_a must sort before incident_b")
        return self


# a question code found in the evidence; the commander can only ask for one of these, by id
class EligibleQuestion(Model):
    question_id: str
    type: QuestionType
    incident_id: str
    scope: list[str] = Field(min_length=1)  # services the specialist may read
    journal_ids: list[int] = Field(default_factory=list)
    hypotheses: list[str] = Field(min_length=2)  # candidate ids still in play
    plan_revision: int = Field(ge=0)
    fingerprint: str


# specialist output: findings only, no action, no instructions for anyone
class FindingResult(Model):
    question_id: str
    hypothesis_id: str
    verdict: Verdict
    summary: str = Field(min_length=1, max_length=400)
    evidence_ids: list[str] = Field(default_factory=list)
    counterevidence_ids: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list, max_length=5)
    applicability: dict[str, str] = Field(default_factory=dict)  # scope + source versions it holds for
    next_read: str | None = Field(default=None, max_length=200)


class AdmissionResult(Model):
    status: AdmissionStatus
    reason: DenialReason | None = None
    task_id: str | None = None
    finding: FindingResult | None = None

    @model_validator(mode="after")
    def reason_iff_denied(self) -> Self:
        if (self.status == "denied") != (self.reason is not None):
            raise ValueError("a denial needs a reason; anything else has none")
        return self


class TaskSummary(Model):
    task_id: str
    question_id: str
    type: QuestionType
    state: TaskState
    attempt: int = Field(ge=0)
    scope: list[str] = Field(default_factory=list)
    deadline_at: float | None = None


class BudgetUse(Model):
    requests_used: int = Field(default=0, ge=0)
    requests_limit: int = Field(gt=0)
    tool_calls_used: int = Field(default=0, ge=0)
    tool_calls_limit: int = Field(gt=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    unknown_calls: int = Field(default=0, ge=0)  # cost uncertain: provider may have charged after a timeout
    specialists_started: int = Field(default=0, ge=0)
    specialists_limit: int = Field(ge=0)


# intent fingerprint: same incident + plan + action = same intent; changed assumptions need a new plan
def intent_fingerprint(incident_id: str, plan_revision: int, action: ActionRequest) -> str:
    a = action.model_dump(mode="json")
    return fingerprint({"incident_id": incident_id, "plan_revision": plan_revision,
                        **{k: a[k] for k in ("tool", "target", "params", "journal_entry", "origin", "prediction")}})


# what the brain asks the gateway to do, with identity; the ActionRequest inside stays the legacy shape
class IntentEnvelope(Model):
    intent_id: str = Field(min_length=8, max_length=64)
    incident_id: str
    scope_revision: int = Field(ge=0)
    plan_revision: int = Field(ge=0)
    fingerprint: str
    action: ActionRequest
    parent_intent_id: str | None = None  # raise_limit follow-up of the rule's own pick

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.action.incident_id != self.incident_id:
            raise ValueError("action belongs to another incident")
        if self.fingerprint != intent_fingerprint(self.incident_id, self.plan_revision, self.action):
            raise ValueError("fingerprint does not match the action and plan revision")
        return self


class IntentSubmission(Model):
    intent_id: str
    status: IntentStatus
    reason: str | None = None
    approval_id: str | None = None
    receipt_id: int | None = None


class IntentSummary(Model):
    intent_id: str
    status: IntentStatus
    plan_revision: int = Field(ge=0)
    tool: str
    target: str
    approval_id: str | None = None
    receipt_id: int | None = None


class DelegationRecord(Model):
    status: AdmissionStatus | Literal["none_needed"]
    explanation: str
    reason: DenialReason | None = None
    question_id: str | None = None
    ts: float


class FindingSummary(Model):
    finding_id: str
    task_id: str
    question_id: str
    verdict: Verdict
    summary: str
    evidence_ids: list[str] = Field(default_factory=list)


# GET /incidents/{id} "orchestration"; old incidents have none
class WorkspaceSnapshot(Model):
    schema_version: int = 1
    incident_id: str
    revision: int = Field(ge=0)
    phase: Phase
    scope_revision: int = Field(ge=0)
    plan_revision: int = Field(ge=0)
    created_at: float
    deadline_at: float | None = None
    memberships: list[Membership] = Field(default_factory=list)
    links: list[IncidentLink] = Field(default_factory=list)
    tasks: list[TaskSummary] = Field(default_factory=list)
    findings: list[FindingSummary] = Field(default_factory=list)
    delegation: list[DelegationRecord] = Field(default_factory=list)
    intents: list[IntentSummary] = Field(default_factory=list)
    budget: BudgetUse
    last_error: str | None = None
