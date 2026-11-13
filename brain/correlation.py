# which new episodes share a cause (handoff §5.2). Pure and deterministic: explicit rules and reason codes,
# no scores. Timing, shared node or severity alone never groups; missing topology is unknown, not separate.
from dataclasses import dataclass, field
from typing import Any

from schemas.orchestration import CorrelationReason, SignalEpisode

ONSET_TOLERANCE_S = 30  # a dependency may breach a little after its callers on a 5 s poll


@dataclass
class Group:
    episode_ids: list[str]
    services: list[str]
    reason: CorrelationReason
    cause: str | None = None  # "dependency:<svc>" or "change:journal:<id>"; joins use it
    evidence_ids: list[str] = field(default_factory=list)


@dataclass
class Link:
    a: str  # "group:<n>" or an incident id
    b: str
    reason: CorrelationReason
    relation: str = "related"
    supporting_ids: list[str] = field(default_factory=list)


@dataclass
class Decision:
    groups: list[Group] = field(default_factory=list)
    joins: list[tuple[str, str, CorrelationReason, str]] = field(default_factory=list)  # episode, incident, why
    links: list[Link] = field(default_factory=list)
    notes: dict[str, str] = field(default_factory=dict)  # episode id -> why it landed where it did

    def as_json(self) -> dict[str, Any]:
        return {"groups": [g.__dict__ for g in self.groups], "joins": [list(j) for j in self.joins],
                "links": [lk.__dict__ for lk in self.links], "notes": self.notes}


def reach(service: str, edges: list[tuple[str, str, float]]) -> set[str]:
    callees: dict[str, set[str]] = {}
    for caller, callee, _ in edges:
        callees.setdefault(caller, set()).add(callee)
    seen, todo = set(), [service]
    while todo:
        for nxt in callees.get(todo.pop(), ()):
            if nxt not in seen:
                seen.add(nxt)
                todo.append(nxt)
    seen.discard(service)
    return seen


# the deepest failing service this one depends on; itself when nothing below it fails; None when two
# unrelated failing branches both fit (ambiguous: an open question, not a guess)
def root_of(service: str, failing: set[str], deepest_error: dict[str, str], first_breach: dict[str, float],
            edges: list[tuple[str, str, float]]) -> tuple[str | None, list[str]]:
    below = reach(service, edges)
    traced = deepest_error.get(service)
    candidates = {d for d in below if d in failing}
    if traced and traced in below:
        candidates.add(traced)
    onset = first_breach.get(service)
    if onset is not None:  # a cause cannot start well after the symptom
        candidates = {d for d in candidates if first_breach.get(d) is None or first_breach[d] <= onset + ONSET_TOLERANCE_S}
    deepest = sorted(d for d in candidates if not (reach(d, edges) & candidates))
    if not deepest:
        return service, []
    if len(deepest) > 1:
        return None, deepest
    return deepest[0], deepest


def service_of_object(obj: str, flag_map: dict[str, str]) -> str | None:
    kind, _, name = obj.partition("/")
    if kind == "deployment":
        return name
    return flag_map.get(name) if kind == "configmap" else None


def correlate(episodes: list[SignalEpisode], open_incidents: dict[str, dict[str, Any]],
              edges: list[tuple[str, str, float]], journal: list[dict], deepest_error: dict[str, str],
              failing: set[str], window_s: float, flag_map: dict[str, str] | None = None) -> Decision:
    decision = Decision()
    if not episodes:
        return decision
    first_breach = {e.service: e.first_breach_at if e.first_breach_at is not None else e.sustained_at
                    for e in episodes}
    known = {s for edge in edges for s in edge[:2]}

    # 1. shared dependency: same supported root
    roots: dict[str, list[SignalEpisode]] = {}
    loose: list[SignalEpisode] = []
    for ep in sorted(episodes, key=lambda e: (first_breach[e.service], e.service)):
        if ep.service not in known:
            decision.notes[ep.episode_id] = "unknown_topology"
            loose.append(ep)
            continue
        root, options = root_of(ep.service, failing, deepest_error, first_breach, edges)
        if root is None:
            decision.notes[ep.episode_id] = f"contradicted: {', '.join(options)} both fit"
            loose.append(ep)
            continue
        roots.setdefault(root, []).append(ep)

    for root, eps in sorted(roots.items()):
        cause = f"dependency:{root}"
        owner = next((i for i, inc in sorted(open_incidents.items()) if inc.get("cause") == cause), None)
        if owner is not None:  # same supported cause as an open incident: it joins, no second commander
            for ep in eps:
                decision.joins.append((ep.episode_id, owner, "shared_dependency", cause))
                decision.notes[ep.episode_id] = f"joins {owner}: {cause}"
            continue
        shared = len(eps) > 1 or eps[0].service != root
        reason: CorrelationReason = "shared_dependency" if shared else "independent"
        decision.groups.append(Group([e.episode_id for e in eps], sorted(e.service for e in eps), reason, cause))
        for ep in eps:
            decision.notes.setdefault(ep.episode_id, reason)

    # 2. shared change among what is still separate: only the one change that reaches every member
    singles = [g for g in decision.groups if g.reason == "independent"]
    if len(singles) > 1:
        changes = _change_candidates(journal, singles, first_breach, edges, window_s, flag_map or {})
        if len(changes) == 1:
            entry, members = changes[0]
            merged = Group([i for g in members for i in g.episode_ids], sorted(s for g in members for s in g.services),
                           "shared_change", f"change:journal:{entry['id']}", [f"journal:{entry['id']}"])
            decision.groups = [g for g in decision.groups if g not in members] + [merged]
            for i in merged.episode_ids:
                decision.notes[i] = merged.cause or "shared_change"
        elif len(changes) > 1:  # two plausible changes: related, not merged
            for entry, members in changes:
                for g in members[1:]:
                    a, b = sorted((f"group:{decision.groups.index(members[0])}", f"group:{decision.groups.index(g)}"))
                    decision.links.append(Link(a, b, "shared_change", "possible_shared_cause",
                                               [f"journal:{entry['id']}"]))

    # 3. what is left stands alone; unknown topology or contradiction gets a link, never a merge
    for ep in loose:
        decision.groups.append(Group([ep.episode_id], [ep.service],
                                     "unknown_topology" if ep.service not in known else "contradicted"))
    for n, g in enumerate(decision.groups):
        if g.reason not in ("unknown_topology", "contradicted"):
            continue
        others = [f"group:{m}" for m in range(len(decision.groups)) if m != n] + sorted(open_incidents)
        for other in others:
            a, b = sorted((f"group:{n}", other))
            if not any((lk.a, lk.b) == (a, b) for lk in decision.links):
                decision.links.append(Link(a, b, g.reason))
    co_timed = [g for g in decision.groups if g.reason == "independent"]
    if len(co_timed) > 1:
        for g in co_timed:
            for i in g.episode_ids:
                decision.notes[i] = "timing_only: same window, no shared cause found"
    return decision


# non-agent changes in the window before onset whose service every member depends on (or is)
def _change_candidates(journal: list[dict], groups: list[Group], first_breach: dict[str, float],
                       edges: list[tuple[str, str, float]], window_s: float,
                       flag_map: dict[str, str]) -> list[tuple[dict, list[Group]]]:
    onset = min(first_breach.values())
    found = []
    for entry in sorted(journal, key=lambda j: j["id"]):
        if entry.get("by_agent") or not (onset - window_s <= entry["ts"] <= onset):
            continue
        svc = service_of_object(entry.get("object", ""), flag_map)
        if svc is None:
            continue
        members = [g for g in groups if all(s == svc or svc in reach(s, edges) for s in g.services)]
        if len(members) > 1:
            found.append((entry, members))
    return found
