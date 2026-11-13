from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Pattern = Literal["recent_change", "resource", "protected", "unknown"]

Tool = Literal[
    "rollback_deploy", "revert_config", "restart_service", "scale", "raise_limit",
    "enable_degraded_mode",
]
EventType = Literal[
    "incident_opened", "alerts_grouped", "culprit_found", "major_incident", "bundle_built",
    "rule_matched", "llm_called", "diagnosis_ready", "checklist_step", "approval_requested",
    "approval_decided", "action_executed", "verify_tick", "early_abort", "action_undone",
    "harm_check", "incident_resolved", "escalated", "handed_off", "injection_quarantined", "blocked",
    "tool_called",
    # orchestration (schemas/orchestration.py); only emitted when orchestration mode is not disabled
    "incident_scope_changed", "delegation_decided", "investigation_task_changed", "finding_recorded",
    "evidence_reused", "orchestration_budget_changed", "action_intent_changed",
]
# shared by orchestration payloads here and the contracts in schemas/orchestration.py
TaskState = Literal["pending", "running", "succeeded", "failed", "timed_out", "cancelled", "lease_expired"]
Verdict = Literal["supported", "refuted", "inconclusive"]
AdmissionStatus = Literal["admitted", "reused", "waiting", "denied"]
IntentStatus = Literal["queued", "awaiting_approval", "executing", "verifying", "terminal", "execution_unknown",
                       "superseded", "refused"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Evidence(Model):
    id: str
    kind: Literal["query", "journal", "trace", "event", "log"]
    summary: str
    value: float | None = None
    ts: float


class Incident(Model):
    id: str
    opened_at: float
    onset_at: float
    unhealthy: list[str]
    culprit: str | None = None
    victims: list[str] = Field(default_factory=list)
    major: bool = False
    severity: float = Field(ge=0)


class EvidenceBundle(Model):
    incident: Incident
    changes: list[Evidence] = Field(default_factory=list)
    metrics: list[Evidence] = Field(default_factory=list)
    traces: list[Evidence] = Field(default_factory=list)
    events: list[Evidence] = Field(default_factory=list)
    logs: list[Evidence] = Field(default_factory=list)
    dependency_edges: list[tuple[str, str, float]] = Field(default_factory=list)
    onset_order: list[tuple[str, float]] = Field(default_factory=list)


class Prediction(Model):
    metric: str
    target: str
    below: float = Field(allow_inf_nan=False)
    within_s: int = Field(gt=0, le=120)


class Cause(Model):
    cause_class: Literal["recent_change", "resource_exhaustion", "failing_dependency", "unknown"]
    culprit: str
    evidence_ids: list[str]
    explanation: str


class ActionRequest(Model):
    incident_id: str
    tool: Tool
    target: str
    params: dict[str, Any] = Field(default_factory=dict)
    pattern: Pattern
    evidence_ids: list[str]
    prediction: Prediction | None = None
    journal_entry: int | None = None
    # who picked the fix: the rule's first candidate, or the model (another candidate or its own proposal).
    # Set by brain code, never by the model; the gateway asks a human for every "model" action
    origin: Literal["rule", "model"] = "rule"


class Diagnosis(Model):
    causes: list[Cause] = Field(max_length=3)
    prediction: Prediction | None = None
    proposed: ActionRequest | None = None
    confidence: float = Field(ge=0, le=1)
    # agent mode: accept a rule candidate (by id), propose another available tool, or decline to act
    decision: Literal["accept", "other", "decline"] | None = None
    candidate: str | None = None
    reason: str | None = Field(default=None, max_length=400)
    alternative: str | None = Field(default=None, max_length=400)


class GatewayDecision(Model):
    decision: Literal["executed", "awaiting_approval", "escalated", "refused", "handed_off"]
    failed_step: str | None = None
    reason: str | None = None
    receipt_id: int | None = None
    approval_id: str | None = None


class Receipt(Model):
    incident_id: str
    tool: Tool
    target: str
    diff: dict[str, Any]
    inverse: dict[str, Any] = Field(min_length=1)
    evidence_ids: list[str]
    outcome: Literal["pending", "success", "undone", "handed_off", "right_by_accident", "undo_failed"] = "pending"
    prediction_held: bool | None = None
    harm_clean: bool | None = None
    elapsed_s: float | None = None
    added_disruption_s: float | None = None
    forecast_s: float | None = None
    pods_touched: list[str] = Field(default_factory=list)
    blast: dict[str, Any] = Field(default_factory=dict)
    trust: dict[str, Any] = Field(default_factory=dict)
    checklist: list[dict[str, Any]] = Field(default_factory=list)
    hash_before: str | None = None
    hash_after: str | None = None


# not name/value: the redactor blanks any {name, value} dict as a k8s env var
class CardField(Model):
    label: str
    body: str
    inline: bool = False


class Card(Model):
    incident_id: str
    status: str
    text: str
    evidence_ids: list[str]
    # discord embed parts; text stays the 5-line card for the UI; old events carry none of these
    headline: str = ""  # push line under the ping: the whole story in one sentence
    title: str = ""
    summary: str = ""
    fields: list[CardField] = Field(default_factory=list)
    footer: str = ""
    level: Literal["page", "ask", "ok", "info"] = "info"


class Payload(BaseModel):
    model_config = ConfigDict(extra="allow", allow_inf_nan=False)


class CardPayload(Payload):
    card: Card
    receipt_url: str = ""
    briefing: str = ""


class ApprovalRequestedPayload(CardPayload):
    approval_id: str
    diff: str
    forecast: str
    expires_at: float


class ApprovalDecidedPayload(Payload):
    approval_id: str
    decision: Literal["approved", "rejected", "expired"]
    acknowledged: bool = False
    decided_by: str | None = None
    via: Literal["discord", "akira-mcp"] | None = None


class DiagnosisReadyPayload(Payload):
    pattern: Pattern
    culprit: str | None


class ChecklistPayload(Payload):
    name: str
    passed: bool
    reason: str | None = None


class QuarantinePayload(Payload):
    line_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class InferencePayload(Payload):
    provider: str | None = None
    model: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)
    attempt: int | None = None
    error: str | None = None
    cached: bool = False


# one read-tool call of the diagnosis agent (brain/tools.py): a read, not a model request
class ToolCalledPayload(Payload):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    ms: float | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class ScopeChangedPayload(Payload):
    scope_revision: int = Field(ge=0)
    services: list[str]
    reasons: list[str] = Field(default_factory=list)


# why a specialist did or did not start; "none_needed" = commander alone, the common case
class DelegationDecidedPayload(Payload):
    status: AdmissionStatus | Literal["none_needed"]
    explanation: str
    reason: str | None = None
    question_id: str | None = None
    task_id: str | None = None


class TaskChangedPayload(Payload):
    task_id: str
    question_id: str
    state: TaskState
    attempt: int = Field(ge=0)


class FindingRecordedPayload(Payload):
    task_id: str
    finding_id: str
    question_id: str
    verdict: Verdict
    summary: str
    evidence_ids: list[str] = Field(default_factory=list)


# a read served from the shared cache, not a fresh upstream fetch
class EvidenceReusedPayload(Payload):
    query_key: str
    source: Literal["cache", "inflight"]
    age_s: float = Field(ge=0)
    evidence_ids: list[str] = Field(default_factory=list)


class BudgetChangedPayload(Payload):
    requests_used: int = Field(ge=0)
    requests_limit: int = Field(gt=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)


class IntentChangedPayload(Payload):
    intent_id: str
    status: IntentStatus
    plan_revision: int = Field(ge=0)
    approval_id: str | None = None
    receipt_id: int | None = None
    reason: str | None = None


PAYLOADS: dict[str, type[Payload]] = {
    "incident_scope_changed": ScopeChangedPayload,
    "delegation_decided": DelegationDecidedPayload,
    "investigation_task_changed": TaskChangedPayload,
    "finding_recorded": FindingRecordedPayload,
    "evidence_reused": EvidenceReusedPayload,
    "orchestration_budget_changed": BudgetChangedPayload,
    "action_intent_changed": IntentChangedPayload,
    "approval_requested": ApprovalRequestedPayload,
    "approval_decided": ApprovalDecidedPayload,
    "diagnosis_ready": DiagnosisReadyPayload,
    "checklist_step": ChecklistPayload,
    "injection_quarantined": QuarantinePayload,
    "llm_called": InferencePayload,
    "tool_called": ToolCalledPayload,
    "incident_resolved": CardPayload,
    "escalated": CardPayload,
    "handed_off": CardPayload,
}


class Event(Model):
    type: EventType
    incident_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    # set by the orchestration outbox so a redelivery dedupes; left out of dumps when unset (old record shape)
    event_id: str | None = Field(default=None, min_length=1, max_length=64, exclude_if=lambda v: v is None)

    @model_validator(mode="after")
    def check_payload(self) -> Self:
        payload_type = PAYLOADS.get(self.type)
        if payload_type:
            if not self.incident_id:
                raise ValueError("Lifecycle event requires incident_id")
            validated = payload_type.model_validate(self.payload)
            if isinstance(validated, CardPayload) and validated.card.incident_id != self.incident_id:
                raise ValueError("Card incident_id does not match event")
            self.payload = validated.model_dump(mode="json")
        return self
