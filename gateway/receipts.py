import json
import re
import sqlite3
from collections import Counter
from pathlib import Path

from fastapi import APIRouter, HTTPException

from brain.redact import redact_value
from gateway.executor import NAMESPACE
from schemas.models import ActionRequest, Card, CardField, Diagnosis, GatewayDecision, Incident, Prediction, Receipt


class ReceiptStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS receipt_views (id INTEGER PRIMARY KEY, body TEXT NOT NULL)")

    def connect(self):
        return sqlite3.connect(self.path)

    # store display data; executor keeps its undo snapshot separately
    def save(self, receipt: Receipt) -> int:
        with self.connect() as db:
            cursor = db.execute("INSERT INTO receipt_views(body) VALUES (?)",
                                (json.dumps(redact_value(receipt.model_dump(mode="json"))),))
            return int(cursor.lastrowid)

    # the verifier fills outcome / prediction_held / harm_clean once it decides
    def update(self, receipt_id: int, receipt: Receipt) -> None:
        with self.connect() as db:
            db.execute("UPDATE receipt_views SET body=? WHERE id=?",
                       (json.dumps(redact_value(receipt.model_dump(mode="json"))), receipt_id))

    # newest first, for the UI's /receipts page
    def recent(self, limit: int = 100) -> list[tuple[int, Receipt]]:
        with self.connect() as db:
            rows = db.execute("SELECT id, body FROM receipt_views ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [(row[0], Receipt.model_validate_json(row[1])) for row in rows]

    def get(self, receipt_id: int) -> Receipt | None:
        with self.connect() as db:
            row = db.execute("SELECT body FROM receipt_views WHERE id=?", (receipt_id,)).fetchone()
        return Receipt.model_validate_json(row[0]) if row else None


def build_card(receipt: Receipt, receipt_id: int) -> Card:
    proven = receipt.outcome == "success" and receipt.prediction_held is True and receipt.harm_clean is True
    status = "FIXED" if proven else {
        "undone": "NEEDS YOU", "undo_failed": "NEEDS YOU", "handed_off": "HANDED OFF",
        "right_by_accident": "RECOVERED, FIX NOT PROVEN",
    }.get(receipt.outcome, "CHECKING FIX")
    refs = " ".join(f"[{' '.join(value.split())}]" for value in receipt.evidence_ids)
    text = "\n".join([
        f"{status}: {' '.join(receipt.target.split())}",
        f"Evidence: {refs or 'not supplied'}",
        f"Did: {receipt.tool}; receipt #{receipt_id}",
        f"Checked: {_checked(receipt)}",
        f"Undo: {_undo(receipt, receipt_id)}",
    ])
    return Card(incident_id=receipt.incident_id, status=status,
                text=redact_value(text), evidence_ids=receipt.evidence_ids)


def create_receipts_router(store: ReceiptStore) -> APIRouter:
    router = APIRouter()

    @router.get("/receipts")
    def recent(limit: int = 100):
        return [{"id": i, "receipt": r, "card": build_card(r, i)} for i, r in store.recent(min(max(limit, 1), 500))]

    @router.get("/receipts/{receipt_id}")
    def get(receipt_id: int):
        receipt = store.get(receipt_id)
        if receipt is None:
            raise HTTPException(404, "Receipt not found")
        return {"id": receipt_id, "receipt": receipt, "card": build_card(receipt, receipt_id)}

    return router


def _took(seconds: float) -> str:
    s = max(0, int(round(seconds)))
    return f"{s // 60}m {s % 60:02d}s" if s >= 60 else f"{s}s"


# "automatic; trust 30 rehearsals, 0 real; proven at least 90%" or "approved by <id>" (plan §6.7.1)
def _mode(trust: dict) -> str:
    if trust.get("approved_by"):
        return f"approved by {trust['approved_by']}"
    rehearsal, real = trust.get("rehearsal") or [0, 0], trust.get("real") or [0, 0]
    bound = trust.get("lower_bound")
    proven = f"; proven at least {bound:.0%}" if isinstance(bound, (int, float)) else ""
    return f"automatic; trust {rehearsal[0]} rehearsals, {real[0]} real{proven}"


def _checked(receipt: Receipt) -> str:
    if receipt.outcome == "pending":
        return "still checking the fix"
    prediction = {True: "recovery matched the agent's prediction",
                  False: "recovery did not match the agent's prediction", None: "no prediction to check"}
    harm = {True: "nothing else got worse", False: "something else got worse", None: "other services not checked"}
    parts = [prediction[receipt.prediction_held], harm[receipt.harm_clean]]
    if receipt.added_disruption_s is not None:
        forecast = f" (expected {receipt.forecast_s:.0f} s)" if receipt.forecast_s is not None else ""
        parts.append(f"extra disruption {receipt.added_disruption_s:.0f} s{forecast}")
    return "; ".join(parts)


# a command a tired human can paste to take the agent's action back; only plain k8s names go into one
def _undo(receipt: Receipt, receipt_id: int) -> str:
    op, target = receipt.inverse.get("op"), receipt.target
    if receipt.outcome in ("undone", "undo_failed"):
        return f"already undone by the agent; receipt #{receipt_id}" if receipt.outcome == "undone" \
            else f"the agent's undo FAILED; restore from receipt #{receipt_id} by hand"
    if not re.fullmatch(r"[a-z0-9-]+", target):
        return f"restore from receipt #{receipt_id} by hand"
    if op == "restore_template":
        return f"kubectl rollout undo deploy/{target} -n {NAMESPACE}"
    if op == "scale" and isinstance(receipt.inverse.get("replicas"), int):
        return f"kubectl scale deploy/{target} -n {NAMESPACE} --replicas={receipt.inverse['replicas']}"
    return f"put configmap/{receipt.inverse.get('name')} back from receipt #{receipt_id}"


# plain fallback when no journal fact explains it (keys: Pattern and Cause.cause_class)
WHY = {
    "recent_change": "a change to {svc} landed just before it started failing",
    "resource": "{svc} ran out of memory or CPU",
    "resource_exhaustion": "{svc} ran out of memory or CPU",
    "failing_dependency": "something {svc} depends on is failing",
    "protected": "{svc} is a protected datastore, so the agent may not touch it",
    "unknown": "no clear cause found yet",
}

# gateway and brain stop reasons in plain words; first match wins, {0} {1} are the regex groups
REASONS = [
    (r"action budget used up", "Safety limit: the agent already made as many changes this hour as it may. "
                               "It stops on purpose; nothing in the agent is broken."),
    (r"no safe action \(unknown\)", "No cause found. The agent acts only when it can name a cause."),
    (r"no safe action", "The agent found a likely cause but has no safe fix for it."),
    (r"(\S+) is protected; a human must act", "{0} holds data, so the agent may never change it. A person must act."),
    (r"(\S+) is a protected data store", "{0} holds data, so a person must approve any change to it."),
    (r"another action is still being verified", "The agent is still checking an earlier fix, "
                                                "so it will not start another one yet."),
    (r"problem no longer present", "The problem went away before the agent acted."),
    (r"rule result changed", "The situation changed while the agent was deciding, so a person should check."),
    (r"journal entry \d+ (?:no longer matches|not found)", "The change the agent wanted to undo has changed again "
                                                           "since. A person should check."),
    (r"observer unreachable", "The agent cannot read health data right now, so it will not act."),
    (r"action refused|not allowed|unknown service|is not actable", "The fix the agent proposed is not allowed by "
                                                                   "its rules."),
    (r"trust bound", "The agent has not proven this fix often enough yet to run it alone."),
    (r"major incident: a human approves", "Many services are failing at once. In a major incident a person "
                                          "approves every fix."),
    (r"major incident", "Many services are failing at once, so the agent only takes limited actions."),
    (r"blast radius unknown", "The fix restarts pods, and the agent cannot tell which other services that hurts."),
    (r"net benefit too low", "The fix may cost more than it saves: it restarts pods while few users are hurt."),
    (r"API server refused", "Kubernetes refused the change (permissions or an admission rule)."),
    (r"approval expired", "Nobody approved in time. The agent changed nothing."),
    (r"approval rejected", "A person rejected the fix. The agent changed nothing."),
    (r"severity rose after the action", "Things got worse right after the fix, so the agent undid it."),
    (r"did not recover", "The fix did not bring the service back in time, so the agent undid it."),
    (r"harm check failed", "After the fix, another service got worse, so the agent undid it."),
    (r"UNDO FAILED", "The agent could not undo its own change. The system may be half changed."),
    (r"watchdog", "The agent lost track of its fix while checking it, so it undid it to be safe."),
    (r"(\S+) changed by (\S+)", "A person ({1}) changed {0} during the incident, so the agent stepped back."),
]


def plain(text: object) -> str:
    return " ".join(redact_value(str(text)).split())


# reason codes like "action budget used up" read as a crash to a tired human
def explain(reason: str, failed_step: str | None = None) -> str:
    if failed_step == "gateway":
        return "The agent's safety checker did not answer, so it will not act."
    for pattern, sentence in REASONS:
        if m := re.search(pattern, reason):
            return sentence.format(*(plain(g) for g in m.groups()))
    return f"The agent stopped: {plain(reason)}."


def shorten(text: str, limit: int = 220) -> str:
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "..."


def cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def pct(x: float) -> str:
    return f"{x:.0%}" if x >= 0.095 else f"{x:.1%}".replace(".0%", "%")


def ms(x: float) -> str:
    return f"{x / 1000:.1f} s" if x >= 1000 else f"{x:.0f} ms"


# "36% of payment requests are failing" from live health, culprit first; numbers always with units
def symptom(health: dict | None, services: list[str]) -> str | None:
    for s in services:
        v = ((health or {}).get("services") or {}).get(s) or {}
        err, p95, base = v.get("err_ratio"), v.get("p95_ms"), v.get("baseline_p95_ms")
        if isinstance(err, (int, float)) and err >= 0.01:
            return f"{pct(err)} of {s} requests are failing"
        if isinstance(p95, (int, float)) and isinstance(base, (int, float)) and 0 < base < p95:
            fine = "; no requests are failing" if err is not None else ""
            return f"{s} is slow: 95% of requests finish within {ms(p95)}, normal is {ms(base)}{fine}"
    return None


ACTION = {
    "rollback_deploy": "roll {t} back to its previous version",
    "revert_config": "put {t}'s config back to how it was before the change",
    "restart_service": "restart {t}",
    "scale": "change how many copies of {t} run",
    "raise_limit": "raise {t}'s memory limit",
    "enable_degraded_mode": "switch {t} to degraded mode",
}


DONE = {
    "rollback_deploy": "rolled {t} back to its previous version",
    "revert_config": "put {t}'s config back to how it was before the change",
    "restart_service": "restarted {t}",
    "scale": "changed how many copies of {t} run",
    "raise_limit": "raised {t}'s memory limit",
    "enable_degraded_mode": "switched {t} to degraded mode",
}


def _action(tool: str, target: str, summary: str | None = None, done: bool = False) -> str:
    text = (DONE if done else ACTION).get(tool, tool + " on {t}").format(t=target)
    return f"{text} ({summary})" if summary else text


# the command a human would run to do the agent's proposed fix by hand
def _command(tool: str, target: str, params: dict) -> str | None:
    if not re.fullmatch(r"[a-z0-9-]+", target):
        return None
    if tool == "rollback_deploy":
        return f"kubectl rollout undo deploy/{target} -n {NAMESPACE}"
    if tool == "restart_service":
        return f"kubectl rollout restart deploy/{target} -n {NAMESPACE}"
    if tool == "scale" and isinstance(params.get("replicas"), int):
        return f"kubectl scale deploy/{target} -n {NAMESPACE} --replicas={params['replicas']}"
    return None


def _expect(p: Prediction) -> str:
    t = plain(p.target)
    goal = {"err_ratio": f"{t} errors must fall below {pct(p.below)}",
            "p95_ms": f"95% of {t} requests must finish within {ms(p.below)}"}.get(
        p.metric, f"{t} {plain(p.metric)} must fall below {p.below:g}")
    return f"{goal} within {p.within_s} s, or the agent undoes the fix"


KINDS = {"journal": "change record", "query": "metric", "trace": "trace", "event": "Kubernetes event", "log": "log line"}


def _evidence(ids: list[str]) -> str:
    counts = Counter(i.split(":", 1)[0] for i in ids)
    return ", ".join(f"{n} {KINDS.get(k, k)}{'' if n == 1 else 's'}" for k, n in counts.items()) or "none"


# untrusted prose: no raw epoch times, no evidence ids, no markdown that could fake a link or a command
def _tidy(text: str) -> str:
    text = re.sub(r"\[[a-z_]+:[^\]]*\]", "", text)
    text = re.sub(r"\s*(?:\b(?:at|since|on)\s+)?\b1\d{9}(?:\.\d+)?\b", "", text)
    text = text.replace("err_ratio", "error rate").replace("p95_ms", "p95 latency")
    text = re.sub(r"[\[\]`*~|>]", "", text)
    return " ".join(text.split()).replace(" ,", ",").replace(" .", ".")


# plan §6.7.1 card: 5-line text for the UI, plus the same words split into discord embed parts
def build_incident_card(incident: Incident, diagnosis: Diagnosis | None = None,
                        decision: GatewayDecision | None = None, receipt: Receipt | None = None,
                        receipt_id: int | None = None, mitigated: bool = False, why: str | None = None,
                        took_s: float | None = None, metric: str | None = None, did: str | None = None,
                        pattern: str | None = None, model_says: str | None = None, health: dict | None = None,
                        proposal: ActionRequest | None = None, reason: str | None = None) -> Card:
    acted = receipt is not None and receipt_id is not None
    if receipt is not None and receipt_id is not None:
        card = build_card(receipt, receipt_id)
    else:
        card = Card(incident_id=incident.id, status="NEEDS YOU", text="", evidence_ids=[])
    if decision:
        card.status = {"awaiting_approval": "NEEDS APPROVAL", "handed_off": "HANDED OFF",
                       "escalated": "NEEDS YOU", "refused": "NO ACTION"}.get(decision.decision, card.status)
    if mitigated:
        card.status = "MITIGATED, NOT FIXED"
    state = card.status
    asking = state == "NEEDS APPROVAL"
    level = {"NEEDS YOU": "page", "NEEDS APPROVAL": "ask", "MITIGATED, NOT FIXED": "ask",
             "FIXED": "ok", "RECOVERED, FIX NOT PROVEN": "ok"}.get(state, "info")
    if incident.major:
        card.status = f"MAJOR INCIDENT: {card.status}"
    causes = diagnosis.causes if diagnosis else []
    ids = list(dict.fromkeys(card.evidence_ids + [value for cause in causes for value in cause.evidence_ids]))

    svc = plain(incident.culprit or "the service")
    kind = causes[0].cause_class if causes else (pattern or "unknown")
    found = bool(why) or kind != "unknown"
    cause = plain(why) if why else cap(WHY.get(kind, WHY["unknown"]).format(svc=svc))
    said = shorten(_tidy(plain(model_says or (causes[0].explanation if causes else ""))))
    stop = reason or (decision.reason if decision else None)
    because = explain(stop, decision.failed_step if decision else None) if stop else None
    services = list(dict.fromkeys(s for s in [incident.culprit, *incident.victims, *incident.unhealthy] if s))
    change = plain(metric).replace("->", "→") if metric else None  # "payment errors 38.0% → 0.4%"
    if acted and level == "ok":
        summary = change or f"{svc} is healthy again"
    else:
        summary = plain(symptom(health, services) or change or f"{svc} is unhealthy")
    took = f" in {_took(took_s)}" if took_s is not None and acted and level == "ok" else ""
    head = card.status + took

    fields: list[CardField] = []

    def add(name: str, value: str, inline: bool = False):
        fields.append(CardField(label=name, body=shorten(redact_value(value), 1000), inline=inline))

    if receipt is not None and receipt_id is not None:
        done = _action(receipt.tool, plain(receipt.target), plain(did) if did else None, done=True)
        mode = plain(_mode(receipt.trust))
        undo = plain(_undo(receipt, receipt_id))
        if because or (change and level != "ok"):
            add("What happened", " ".join(filter(None, [because, f"During the fix: {change}." if change and
                                                        level != "ok" else None])))
        add("Cause" if level == "ok" else "Likely cause", cause)
        add("The agent did", f"{cap(done)}; {mode}. Receipt #{receipt_id}", inline=True)
        add("Checks", "\n".join(cap(p) for p in _checked(receipt).split("; ")), inline=True)
        add("To undo", f"`{undo}`" if undo.startswith("kubectl") else cap(undo))
        did_line, check = f"{done}; {mode}. Receipt #{receipt_id}", _checked(receipt)
    else:
        wanted = _action(proposal.tool, plain(proposal.target), plain(did) if did else None) if proposal else None
        if because and not asking:
            add("Why the agent stepped back" if state == "HANDED OFF" else "Why the agent stopped", because)
        if proposal and wanted:
            cmd = _command(proposal.tool, plain(proposal.target), proposal.params)
            add("The agent wants to" if asking else "Suggested fix (not run)",
                f"{cap(wanted)}." + (f"\n`{cmd}`" if cmd else ""))
            if asking and proposal.prediction:
                add("If you approve", _expect(proposal.prediction) + ".")
        if because and asking:
            add("Why it asks you", because)
        if found:
            add("Likely cause", cause)
        add("Changes by the agent", "None yet. Nothing to undo.")
        did_line = "nothing yet" + (f"; it {'wants to' if asking else 'would'} {wanted}" if wanted else "") \
            + (f". {because}" if because else "")
        check, undo = "nothing yet; the agent made no change", "nothing to undo"
    if said:
        add("AI reading (not checked)", said)

    # summary always names the service, so the push line leads with it; service names stay lower case
    if receipt is not None and receipt.outcome == "undo_failed":
        headline = f"{summary}. The agent could not undo its own change: act now"
    elif receipt is not None and receipt.outcome == "undone":
        headline = f"{summary}. {because or 'The agent undid its fix.'}"
    elif asking and proposal:
        headline = f"{summary}. The agent wants your OK to {_action(proposal.tool, plain(proposal.target))}"
    elif state == "NEEDS YOU":
        headline = f"{summary}. The agent changed nothing"
    elif level == "ok":
        headline = f"{svc} {'fixed' if state == 'FIXED' else 'recovered'}{took}: {summary}"
    elif state == "MITIGATED, NOT FIXED":
        headline = f"{svc} works again after a restart, but the cause is not fixed"
    elif state == "HANDED OFF":
        headline = f"{svc}: a person changed something, so the agent stepped back"
    elif state == "NO ACTION":
        headline = f"{svc}: the agent took no action. {because or ''}"
    else:
        headline = f"{svc}: {summary}"
    major = "MAJOR INCIDENT. " if incident.major else ""

    card.text = "\n".join(plain(line) for line in [
        f"{head}: {summary}",
        f"Why: {cause}" + (f". AI reading (not checked): {said}" if said else ""),
        f"Did: {did_line}", f"Checked: {check}", f"Undo: {undo}",
    ])
    card.headline = plain(major + headline.rstrip(". ") + ".")
    card.title = plain(f"{head} · {svc}")[:256]
    card.summary = summary + "."
    card.fields = fields
    card.footer = plain(f"Incident {incident.id}" + (f" · Evidence: {_evidence(ids)}" if ids else "")
                        + (f" · Receipt #{receipt_id}" if acted else ""))
    card.level = level  # type: ignore[assignment]
    card.evidence_ids = ids
    return card
