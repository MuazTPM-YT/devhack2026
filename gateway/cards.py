# incident cards: the 5-line text the UI shows and the same words split into Discord embed parts
# (plan §6.7.1). Pure: no store, no cluster, no HTTP; brain, observer and gateway all build cards here.
import re
import socket
from collections import Counter

from brain.redact import redact_value
from gateway.executor import NAMESPACE
from schemas.models import ActionRequest, Card, CardField, Diagnosis, GatewayDecision, Incident, Prediction, Receipt


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


def _took(seconds: float) -> str:
    s = max(0, int(round(seconds)))
    return f"{s // 60}m {s % 60:02d}s" if s >= 60 else f"{s}s"


# "automatic; trust 30 rehearsals, 0 real; proven at least 90%" or "approved by <id>" (plan §6.7.1)
def _mode(trust: dict) -> str:
    n = trust.get("attempt") or 1
    retry = f"try {n}, after {n - 1} failed fix{'es' if n > 2 else ''}; " if n > 1 else ""
    return retry + _gate(trust)


def _gate(trust: dict) -> str:
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
    if op == "none":
        return "none is safe: the agent kept its fix, because undoing it would break things again"
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
# names copied into a page: k8s object names and field managers only, never markdown or links
OBJ = r"[a-z0-9][a-z0-9./-]{0,252}"
WHO = r"[A-Za-z0-9][A-Za-z0-9.:-]{0,127}"
REASONS = [
    (r"action budget used up", "Safety limit: the agent already made as many changes this hour as it may. "
                               "It stops on purpose; nothing in the agent is broken."),
    (r"no safe action \(unknown\)", "No cause found. The agent acts only when it can name a cause."),
    (r"no safe action", "The agent found a likely cause but has no safe fix for it."),
    (rf"^({OBJ}) is protected; a human must act", "{0} holds data, so the agent may never change it. A person must act."),
    (rf"^({OBJ}) is a protected data store", "{0} holds data, so a person must approve any change to it."),
    (r"another action is still being verified", "The agent is still checking an earlier fix, "
                                                "so it will not start another one yet."),
    (r"problem no longer present", "The problem went away before the agent acted."),
    (r"health data is stale", "Health data stopped arriving, so the agent will not act on old numbers. "
                              "A person must check."),
    (r"could not check the fix", "Health data stopped arriving while the agent checked its fix. It kept the "
                                 "fix and did not undo it. A person must check."),
    (r"no health readings","Health data stopped arriving, so the agent cannot tell if the problem is still "
                            "there. A person must check."),
    (r"no safe undo", "The fix has not proven itself yet, but undoing it would break things again, so the agent "
                      "kept it. A person must check."),
    (r"rule result changed", "The situation changed while the agent was deciding, so a person should check."),
    (r"journal entry \d+ (?:no longer matches|not found)", "The change the agent wanted to undo has changed again "
                                                           "since. A person should check."),
    (r"observer unreachable", "The agent cannot read health data right now, so it will not act."),
    (r"literal_error, input_value='([a-z0-9-]{1,63})'", "{0} is not on the list of services the agent may change, "
                                                        "so it was blocked."),
    (r"action refused|not allowed|unknown service|is not actable|validation error",
     "The fix the agent proposed is not allowed by its rules, so it was blocked."),
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
    (r"no untried safe fix left", "Every safe fix the agent could find was tried and failed. A person must look."),
    (r"the brain sent no new fix", "The agent undid a failed fix but then sent no new one in time. "
                                   "A person must look."),
    (r"the brain never handed this incident", "The agent started on this incident but never finished deciding "
                                              "(it may have crashed). A person must look."),
    (r"watchdog", "The agent lost track of its fix while checking it, so it undid it to be safe."),
    (r"write outcome unknown", "Kubernetes stopped answering during the change, so it may or may not have "
                               "happened. The agent will not guess or undo. A person must check the cluster."),
    (r"Kubernetes API unreachable|API error \d+", "Kubernetes did not answer, so the agent changed nothing. "
                                                  "A person must check."),
    (rf"^({OBJ}) changed by ({WHO})$", "A person ({1}) changed {0} during the incident, so the agent stepped back."),
]


# the agent stopped on its own limits: its fix was allowed, so a human may run it by hand
RERUNNABLE = r"(?:action budget used up|another action is still being verified|approval expired|observer unreachable)"


def plain(text: object) -> str:
    return " ".join(redact_value(str(text)).split())


# reason codes like "action budget used up" read as a crash to a tired human
def explain(reason: str, failed_step: str | None = None) -> str:
    if failed_step == "gateway":
        return "The agent's safety checker did not answer, so it will not act."
    for pattern, sentence in REASONS:
        if m := re.search(pattern, reason):
            return sentence.format(*(plain(g) for g in m.groups()))
    # unknown reason, printed raw: no links (discord makes bare URLs clickable) and no markdown
    # strip first, then drop links, so stripping can't rebuild one ("ht`tp" -> "http")
    text = re.sub(r"[()<>]", "", _tidy(plain(reason)))
    while (cleaner := re.sub(r"\S*(?:[a-z][a-z0-9+.-]*://|www\.)\S*", "link removed", text, flags=re.I)) != text:
        text = cleaner
    return f"The agent stopped: {text}."


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
    return next(iter(impact(health, services, 1)), None)


# one plain line per sick service, culprit first (Discord "Impact")
def impact(health: dict | None, services: list[str], limit: int = 6) -> list[str]:
    out = []
    for s in services:
        v = ((health or {}).get("services") or {}).get(s) or {}
        if (line := _symptom(s, v)) is not None:
            out.append(line)
    return out[:limit]


def _symptom(s: str, v: dict) -> str | None:
    err, p95, base = v.get("err_ratio"), v.get("p95_ms"), v.get("baseline_p95_ms")
    if isinstance(err, (int, float)) and err >= 0.01:
        return f"{pct(err)} of {s} requests are failing"
    if isinstance(p95, (int, float)) and isinstance(base, (int, float)) and 0 < base < p95:
        fine = "; no requests are failing" if err is not None else ""
        return f"{s} is slow: 95% of requests finish within {ms(p95)}, normal is {ms(base)}{fine}"
    # datastores have no request metrics; the kube watch counts their sick pods (observer pod_bad)
    if (n := v.get("bad_pods")) and isinstance(n, int):
        return f"{n} {s} pod{'s are' if n > 1 else ' is'} crashing, out of memory or not ready"
    return None


# where a Discord-bound event came from: which part of the agent, which step, which machine.
# The gateway's event bus adds "mode" (live or rehearsal); only the gateway knows it
def source(part: str, step: str) -> dict:
    return {"part": part, "step": step, "host": socket.gethostname()}


# the recorded change behind an incident, and the incident's clock, for Discord's Origin and Timeline.
# Names and paths only: env values never leave the journal
def started_by(entry: dict | None, incident: dict) -> dict:
    out: dict = {"onset_at": incident.get("onset_at"), "opened_at": incident.get("opened_at"), "change": None}
    if entry is not None:
        flags = sorted({p[len("flags["):].split("]", 1)[0] for p in entry.get("diff") or {} if p.startswith("flags[")})
        what = f"{entry['kind']} change on {entry['object']}" + (f" ({', '.join(flags[:3])})" if flags else "")
        out.update(change=what, by="the agent" if entry.get("by_agent") else (entry.get("field_manager") or "unknown"),
                   change_ts=entry.get("ts"))
    return out


# why a failed fix was undone, short, for the "Fixes tried" list
TRY_WHY = {"did not recover": "it did not bring the service back in time",
           "severity rose after the action": "things got worse after it",
           "harm check failed": "it hurt another service"}


def _tries(retry: dict) -> str | None:
    lines: list[str] = []
    for t in retry.get("tries") or []:
        done = cap(_action(str(t.get("tool")), plain(t.get("target")), done=True))
        why = TRY_WHY.get(str(t.get("why_undone")), plain(t.get("why_undone") or "it failed its check"))
        ran = f", ran {_took(t['ran_s'])}" if isinstance(t.get("ran_s"), (int, float)) else ""
        lines.append(f"{t.get('attempt', len(lines) + 1)}. {done}: {why}, so the agent undid it "
                     f"(receipt #{t.get('receipt_id')}{ran}).")
    if not lines:
        return None
    if retry.get("next"):
        lines.append(f"Now trying fix {retry['next']} of {retry.get('max')}.")
    elif retry.get("stop"):
        lines.append(f"No more tries: {plain(retry['stop'])}.")
    return "\n".join(lines)


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
                        proposal: ActionRequest | None = None, reason: str | None = None,
                        retry: dict | None = None) -> Card:
    # retry: {"tries": failed fixes (gateway failed_try), "max": n, "next": fix number now tried | None,
    # "stop": why no more tries | None}
    retry = retry or {}
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
    if retry.get("next"):
        card.status = "TRYING ANOTHER FIX"
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
    template = WHY.get(kind, WHY["unknown"])  # sentences that open with a service name keep it lower case
    cause = plain(why) if why else (template.format(svc=svc) if template.startswith("{svc}")
                                    else cap(template.format(svc=svc)))
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
            # no paste-ready command when rules refused the fix, nor beside Approve (by hand skips verification)
            # gateway reasons start with their code; a schema refusal echoes model text, so it never counts
            step = decision.failed_step if decision else None
            allowed = bool(stop and step != "schema" and (re.match(RERUNNABLE, stop) or step == "gateway"))
            cmd = _command(proposal.tool, plain(proposal.target), proposal.params) if allowed and not asking else None
            add("The agent wants to" if asking else "Suggested fix (not run)" if allowed
                else "Blocked proposal (not run)", f"{cap(wanted)}." + (f"\n`{cmd}`" if cmd else ""))
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
    # every sick service, not only the first; a fixed card's health is the "before" picture, so none there
    sick = impact(health, services) if not (acted and level == "ok") else []
    if sick:
        sev = (health or {}).get("severity")
        head_line = f"Severity {sev:g}. " if isinstance(sev, (int, float)) else ""
        add("Impact", head_line + f"{len(sick)} service{'s' if len(sick) > 1 else ''} affected:\n"
            + "\n".join(f"- {line}" for line in sick))  # service names stay lower case
    if tried := _tries(retry):
        add("Fixes tried", tried)
    if said:
        add("AI reading (not checked)", said)

    # summary always names the service, so the push line leads with it; service names stay lower case
    if state == "TRYING ANOTHER FIX":  # before the undone line: the retry FYI is built from the undone receipt
        headline = (f"{svc}: fix {retry['next'] - 1} of {retry.get('max')} did not work, so the agent undid it "
                    f"and is trying fix {retry['next']}")
    elif receipt is not None and receipt.outcome == "undo_failed":
        headline = f"{summary}. The agent could not undo its own change: act now"
    elif receipt is not None and receipt.outcome == "undone" and retry.get("stop") and len(retry.get("tries") or []) > 1:
        headline = f"{summary}. The agent tried {len(retry['tries'])} fixes; each failed and was undone"
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
