# names the checklist and its parts share (gateway/checklist.py and the mixins beside it)
import logging
from contextvars import ContextVar

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


# checklist step names in plain words, for the "Sent by" line on Discord
STEP_WORDS = {"schema": "schema check", "hands_off": "hands-off check", "policy": "policy check",
              "dry_run": "dry run", "net_benefit": "net-benefit check", "freshness": "freshness check",
              "trust_gate": "trust gate", "approval": "approval", "execute": "execute", "retry": "retry deadline"}
