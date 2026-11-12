from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

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
    model_config = ConfigDict(extra="forbid")


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
    pattern: str
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


class Event(Model):
    type: EventType
    incident_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class Receipt(Model):
    incident_id: str
    tool: Tool
    target: str
    diff: dict[str, Any]
    inverse: dict[str, Any] = Field(min_length=1)
    evidence_ids: list[str]
    outcome: Literal["pending", "success", "undone", "handed_off", "right_by_accident"] = "pending"
    prediction_held: bool | None = None
    harm_clean: bool | None = None
    elapsed_s: float | None = None
    added_disruption_s: float | None = None
    forecast_s: float | None = None


class Card(Model):
    incident_id: str
    status: str
    text: str
    evidence_ids: list[str]
