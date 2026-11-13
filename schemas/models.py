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
]


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


class Diagnosis(Model):
    causes: list[Cause] = Field(max_length=3)
    prediction: Prediction | None = None
    proposed: ActionRequest | None = None
    confidence: float = Field(ge=0, le=1)


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


PAYLOADS: dict[str, type[Payload]] = {
    "approval_requested": ApprovalRequestedPayload,
    "approval_decided": ApprovalDecidedPayload,
    "diagnosis_ready": DiagnosisReadyPayload,
    "checklist_step": ChecklistPayload,
    "injection_quarantined": QuarantinePayload,
    "llm_called": InferencePayload,
    "incident_resolved": CardPayload,
    "escalated": CardPayload,
    "handed_off": CardPayload,
}


class Event(Model):
    type: EventType
    incident_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

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
