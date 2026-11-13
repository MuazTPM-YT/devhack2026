# a post-incident report from GET /incidents/{id}: what broke, what Akira did, how long each stage took.
# Stage times count from onset (first breach), like scripts/smoke.sh counts from the inject.
from typing import Any

TERMINAL = ("incident_resolved", "escalated", "handed_off")
STAGES = {"detect": "incident_opened", "diagnose": "diagnosis_ready", "act": "action_executed"}


def first(events: list[dict], kind: str) -> dict | None:
    return next((r for r in events if r["event"]["type"] == kind), None)


def incident_report(detail: dict[str, Any]) -> dict[str, Any]:
    inc, events = detail["incident"], detail.get("events") or []
    start = inc.get("onset_at") or inc.get("opened_at")
    end = next((r for r in events if r["event"]["type"] in TERMINAL), None)

    def since(record: dict | None) -> float | None:
        return round(record["ts"] - start, 1) if record and start else None

    stages = {name: since(first(events, kind)) for name, kind in STAGES.items()}
    stages["finish"] = since(end)
    diagnosis = (first(events, "diagnosis_ready") or {}).get("event", {}).get("payload", {})
    card = (end or {}).get("event", {}).get("payload", {}).get("card") or {}
    actions = [{"receipt_id": r["id"], "tool": r["receipt"]["tool"], "target": r["receipt"]["target"],
                "outcome": r["receipt"].get("outcome"), "prediction_held": r["receipt"].get("prediction_held"),
                "harm_clean": r["receipt"].get("harm_clean"), "card": r["card"]["text"]}
               for r in detail.get("receipts") or []]
    humans = [{"approval_id": a["id"], "state": a["state"], "decided_by": a.get("decided_by"),
               "action": f"{a['action'].get('tool')} {a['action'].get('target')}"}
              for a in detail.get("approvals") or []]
    notes = []
    if end and end["event"]["type"] == "incident_resolved" and not actions:
        notes.append("resolved with no action: Akira fixed nothing; the fault may have cleared or still be live")
    if detail.get("events_total", 0) > len(events):
        notes.append(f"timeline cut to the newest {len(events)} of {detail['events_total']} events")
    return {
        "incident_id": inc["id"], "state": inc.get("state"),
        "outcome": end["event"]["type"] if end else "still open",
        "culprit": inc.get("culprit"), "victims": inc.get("victims") or [], "pattern": inc.get("pattern"),
        "major": inc.get("major"), "severity_at_open": inc.get("severity_at_open"),
        "seconds_from_onset": stages,
        "diagnosis": {k: diagnosis.get(k) for k in ("pattern", "culprit", "decision", "origin", "reason") if k in diagnosis},
        "model_said": inc.get("llm_why"),
        "actions": actions, "approvals": humans,
        "card": card.get("text"), "similar_before": detail.get("similar") or [], "notes": notes,
        "orchestration": orchestration_summary(detail.get("orchestration")),
    }


# coordinated mode only: who investigated, what specialists ran and why, what it cost; None for old incidents
def orchestration_summary(o: dict[str, Any] | None) -> dict[str, Any] | None:
    if not o:
        return None
    return {"phase": o.get("phase"), "services": sorted({m["service"] for m in o.get("memberships") or []}),
            "delegation": [d.get("explanation") for d in o.get("delegation") or []],
            "specialists": [{"task_id": t["task_id"], "state": t["state"]} for t in o.get("tasks") or []],
            "findings": [{"verdict": f["verdict"], "summary": f["summary"]} for f in o.get("findings") or []],
            "model_requests": (o.get("budget") or {}).get("requests_used"),
            "fixes": [{"intent_id": i["intent_id"], "status": i["status"]} for i in o.get("intents") or []]}
