# fleet coordinator (handoff §4-§5, §8): takes observer episodes, groups them by supported cause, owns
# incidents, runs one commander (the existing diagnosis) per incident, delivers events through an outbox
# and recovers after a restart. Deterministic code, no LLM calls of its own. Shadow mode only records.
import asyncio
import json
import logging
import time
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import httpx

from brain.correlation import Decision, correlate
from brain.culprit import fetch_error_traces, from_traces
from gateway.client import read_events
from schemas import auth
from schemas.models import GatewayDecision, Incident
from schemas.orchestration import (IncidentLink, Membership, OrchestrationPolicy, SignalAck, SignalBatch,
                                   SignalEpisode)
from schemas.workspace import Workspace

if TYPE_CHECKING:
    from brain.main import Brain

log = logging.getLogger("brain.coordinator")
TERMINAL_STATES = ("resolved", "escalated", "handed_off")
TERMINAL_EVENTS = {"incident_resolved", "escalated", "handed_off"}
LEASE_S, RENEW_S = 30.0, 10.0
QUEUE_GRACE_S = 120  # a queued incident is escalated this long before the max age, not at it
MAX_REPLANS = 1  # a scope change before hand-over reruns once; then a human looks
GIVEN_UP = ("deadline", "queue_wait", "max_age", "restart", "scope_churn")


class ModeMismatch(Exception):
    pass


def scoped_severity(health: dict, services: list[str]) -> float:
    rows = [health.get("services", {}).get(s) or {} for s in services]
    return float(sum(3 * bool(r.get("breaching")) + 2 * (r.get("bad_pods") or 0) + bool(r.get("unhealthy"))
                     for r in rows))


class Coordinator:
    def __init__(self, brain: "Brain", workspace: Workspace, policy: OrchestrationPolicy,
                 clock: Callable[[], float] = time.time, owner: str | None = None):
        self.brain, self.ws, self.policy, self.clock = brain, workspace, policy, clock
        self.owner = owner or f"brain-{uuid.uuid4().hex[:8]}"
        self.epoch: int | None = None
        self.lost = False  # lease gone: another brain schedules now, this one stops starting work
        self.commanders: dict[str, asyncio.Task] = {}
        self.flush_lock = asyncio.Lock()
        # shadow only: virtual incidents, key -> {"cause": str | None, "episodes": set[str]}
        self.shadow_groups: dict[str, dict[str, Any]] = {}
        self.shadow_seq = 0

    # ---- lifecycle

    async def start(self) -> None:
        if self.policy.mode != "coordinated":
            return
        self.epoch = self.ws.acquire_coordinator(self.owner, LEASE_S)
        if self.epoch is None:
            raise RuntimeError("another brain holds the orchestration coordinator lease; one scheduler per database")
        await self.recover()

    async def run(self, every_s: float = 1.0) -> None:
        last_renew = self.clock()
        while True:
            try:
                if self.epoch is not None and self.clock() - last_renew >= RENEW_S:
                    last_renew = self.clock()
                    if not self.ws.renew_coordinator(self.owner, self.epoch, LEASE_S):
                        self.lost = True
                        log.critical("coordinator lease lost; this brain stops scheduling")
                if not self.lost:
                    await self.flush()
                    await self.expire()
                    self.schedule()
            except Exception as e:  # one bad tick must not end coordination
                log.error("coordinator tick failed: %r", e)
            await asyncio.sleep(every_s)

    # restart: gateway state first, never resubmit; resume read-only investigation; escalate what is lost
    async def recover(self) -> None:
        self.ws.expire_leases()
        if unknown := self.ws.orphan_calls_unknown():
            log.warning("%d model calls were in flight at restart; kept as charged", unknown)
        for iid in self.ws.unfinished():
            w = self.ws.workspace(iid)
            row = self.ws.row("SELECT state FROM incidents WHERE id=?", (iid,))
            if w is None:
                continue
            if row is not None and row["state"] in TERMINAL_STATES:
                self.on_terminal(iid)
                continue
            receipts = self.ws.row("SELECT COUNT(*) FROM receipts WHERE incident_id=?", (iid,))
            approvals = self.ws.row("SELECT COUNT(*) FROM approvals WHERE incident_id=?", (iid,))
            if receipts and receipts[0]:
                self.ws.update(iid, w["revision"], phase="monitoring")
            elif approvals and approvals[0]:
                self.ws.update(iid, w["revision"], phase="awaiting_gateway")
            elif w["phase"] in ("investigating", "ready_for_action"):
                log.info("incident %s: resuming investigation after restart", iid)
                self.ws.update(iid, w["revision"], phase="queued")
            elif w["phase"] == "awaiting_gateway":
                await self.give_up(iid, "restart", "the brain restarted while handing the fix over; the gateway "
                                                   "result is unknown, look by hand")
        await self.flush()
        self.schedule()

    # ---- signals

    # idempotent on delivery_id: a redelivered batch gets the stored answer, nothing runs twice
    async def on_signals(self, batch: SignalBatch) -> SignalAck:
        if batch.shadow != (self.policy.mode == "shadow"):
            raise ModeMismatch(f"observer sent shadow={batch.shadow} but brain mode is {self.policy.mode}")
        if (seen := self.ws.delivery(batch.delivery_id)) is not None:
            return seen.model_copy(update={"duplicate": True})
        with self.ws.tx() as c:
            for ep in batch.episodes:
                self.ws.upsert(c, ep)  # no-op when the observer already wrote it to the shared database
        if self.policy.mode == "shadow":
            await self.shadow(batch)
        else:
            await self.coordinate(batch)
        ack = SignalAck(delivery_id=batch.delivery_id, accepted=len(batch.episodes))
        with self.ws.tx() as c:
            self.ws.record_delivery(c, ack)
        return ack

    # what correlation needs: topology, recent changes, deepest erroring service per symptom
    async def inputs(self, episodes: list[SignalEpisode]) -> tuple[list, list[dict], dict[str, str]]:
        b = self.brain
        try:
            edges = await b.graph.get()
        except (httpx.HTTPError, KeyError, ValueError) as e:
            log.warning("dependency graph failed: %s", type(e).__name__)
            edges = []
        onset = min((e.first_breach_at or e.sustained_at) for e in episodes)
        window_s = b.policy["change_window_minutes"] * 60
        journal = await b._get_json(f"{b.observer_url}/journal", [], since=onset - window_s)
        deepest: dict[str, str] = {}
        for svc in sorted({e.service for e in episodes}):
            try:
                found = await fetch_error_traces(b.http, b.jaeger_url, [svc], self.clock())
            except (httpx.HTTPError, KeyError, ValueError):
                continue  # no traces: unknown, the rules then lean on topology alone
            root, _ = from_traces(found)
            if root:
                deepest[svc] = root
        return list(edges), journal, deepest

    def failing(self, batch: SignalBatch) -> set[str]:
        return {e.service for e in self.ws.open_episodes()} | {e.service for e in batch.episodes
                                                               if e.recovered_at is None}

    # shadow: group as coordinated mode would, write only shadow_decisions; no incidents, no agents, no actions
    async def shadow(self, batch: SignalBatch) -> Decision:
        for ep in batch.episodes:
            if ep.recovered_at is not None:
                for virtual in self.shadow_groups.values():
                    virtual["episodes"].discard(ep.episode_id)
        self.shadow_groups = {k: g for k, g in self.shadow_groups.items() if g["episodes"]}
        owned = {i for g in self.shadow_groups.values() for i in g["episodes"]}
        fresh = [e for e in batch.episodes if e.recovered_at is None and e.episode_id not in owned]
        decision = Decision()
        if fresh:
            edges, journal, deepest = await self.inputs(fresh)
            decision = correlate(fresh, {k: {"cause": g["cause"]} for k, g in self.shadow_groups.items()}, edges,
                                 journal, deepest, self.failing(batch), self.brain.policy["change_window_minutes"] * 60,
                                 self.brain.flag_map)
            for group in decision.groups:
                self.shadow_seq += 1
                self.shadow_groups[f"shadow-{self.shadow_seq}"] = {"cause": group.cause,
                                                                   "episodes": set(group.episode_ids)}
            for episode_id, key, _, _ in decision.joins:
                self.shadow_groups[key]["episodes"].add(episode_id)
        with self.brain.lock:
            legacy = self.brain.conn.execute(
                f"SELECT id FROM incidents WHERE state NOT IN ({','.join('?' * len(TERMINAL_STATES))}) "
                "ORDER BY opened_at DESC LIMIT 1", TERMINAL_STATES).fetchone()
        body = {**decision.as_json(), "open": {k: sorted(g["episodes"]) for k, g in self.shadow_groups.items()}}
        with self.ws.tx() as c:
            c.execute("INSERT INTO shadow_decisions (delivery_id, decided_at, legacy_incident_id, decision_json) "
                      "VALUES (?, ?, ?, ?)", (batch.delivery_id, self.clock(), legacy[0] if legacy else None,
                                              json.dumps(body, sort_keys=True)))
        return decision

    # coordinated: new groups open incidents, joiners widen an open one; state + events in one transaction
    async def coordinate(self, batch: SignalBatch) -> Decision:
        fresh = [e for e in batch.episodes if e.recovered_at is None and self.ws.owner_of(e.episode_id) is None
                 and not self.ws.was_owned(e.episode_id)]
        if not fresh:
            return Decision()
        open_incidents = {}
        for iid in self.ws.unfinished():
            w = self.ws.workspace(iid)
            if w is not None:
                open_incidents[iid] = {"cause": w["cause_key"]}
        edges, journal, deepest = await self.inputs(fresh)
        decision = correlate(fresh, open_incidents, edges, journal, deepest, self.failing(batch),
                             self.brain.policy["change_window_minutes"] * 60, self.brain.flag_map)
        health = await self.brain._get_json(f"{self.brain.observer_url}/health/now", {"services": {}})
        by_id, now = {e.episode_id: e for e in fresh}, self.clock()
        events: list[tuple[str, str, dict]] = []
        names: dict[str, str] = {}
        with self.ws.tx() as c:
            for n, g in enumerate(decision.groups):
                iid = names[f"group:{n}"] = f"inc-{uuid.uuid4().hex[:12]}"
                onset = min((by_id[i].first_breach_at or by_id[i].sustained_at) for i in g.episode_ids)
                inc = {"id": iid, "opened_at": now, "onset_at": onset, "unhealthy": g.services,
                       "severity": scoped_severity(health, g.services)}
                self.ws.open_incident(c, inc, [Membership(incident_id=iid, episode_id=i, service=by_id[i].service,
                                                          reason=g.reason, evidence_ids=g.evidence_ids,
                                                          added_revision=0) for i in g.episode_ids], g.cause)
                events.append(("incident_opened", iid, Incident.model_validate(inc).model_dump(mode="json")))
                events.append(("incident_scope_changed", iid, {"scope_revision": 0, "services": g.services,
                                                               "reasons": [g.reason, *([g.cause] if g.cause else [])]}))
            for episode_id, iid, reason, cause in decision.joins:
                revision = self.ws.bump(c, iid, "scope")
                self.ws.add_membership(c, Membership(incident_id=iid, episode_id=episode_id,
                                                     service=by_id[episode_id].service, reason=reason,
                                                     added_revision=revision))
                services = sorted({r[0] for r in c.execute("SELECT service FROM incident_memberships WHERE "
                                                           "incident_id=?", (iid,))})
                row = c.execute("SELECT * FROM incidents WHERE id=?", (iid,)).fetchone()
                grouped = Incident(id=iid, opened_at=row["opened_at"], onset_at=row["onset_at"], unhealthy=services,
                                   severity=scoped_severity(health, services))
                events.append(("alerts_grouped", iid, grouped.model_dump(mode="json")))
                events.append(("incident_scope_changed", iid, {"scope_revision": revision, "services": services,
                                                               "reasons": [reason, cause]}))
            for lk in decision.links:
                a, b = sorted((names.get(lk.a, lk.a), names.get(lk.b, lk.b)))
                self.ws.link(c, IncidentLink(incident_a=a, incident_b=b, relation=lk.relation,  # type: ignore[arg-type]
                                             reason=lk.reason, supporting_ids=lk.supporting_ids))
            for kind, iid, payload in events:
                self._enqueue(c, kind, iid, payload)
        await self.flush()
        self.schedule()
        return decision

    # ---- commanders

    def schedule(self) -> None:
        if self.lost or self.policy.mode != "coordinated":
            return
        self.commanders = {k: t for k, t in self.commanders.items() if not t.done()}
        for iid in self.ws.unfinished():
            if len(self.commanders) >= self.policy.max_active_commanders:
                return
            w = self.ws.workspace(iid)
            if iid in self.commanders or w is None or w["phase"] != "queued":
                continue
            task = asyncio.create_task(self.run_commander(iid), name=f"{iid}:commander")
            self.commanders[iid] = task
            task.add_done_callback(self._finished)

    def _finished(self, task: asyncio.Task) -> None:
        if not task.cancelled() and task.exception():
            log.error("commander %s failed: %r", task.get_name(), task.exception())

    def incident_of(self, iid: str) -> Incident:
        row = self.ws.row("SELECT * FROM incidents WHERE id=?", (iid,))
        assert row is not None
        services = sorted({m.service for m in self.ws.memberships(iid)})
        return Incident(id=iid, opened_at=row["opened_at"], onset_at=row["onset_at"], unhealthy=services,
                        severity=row["severity_at_open"] or 0)

    def scope_of(self, iid: str) -> int | None:
        w = self.ws.workspace(iid)
        return None if w is None or w["phase"] == "terminal" else w["scope_revision"]

    # one commander: the existing diagnosis + hand-over, inside the incident's persisted deadline
    async def run_commander(self, iid: str) -> dict | None:
        w = self.ws.workspace(iid)
        if w is None or w["phase"] != "queued":
            return None
        deadline = w["deadline_at"] or self.clock() + self.policy.investigation_deadline_seconds
        if not self.ws.update(iid, w["revision"], phase="investigating", deadline_at=deadline, owner=self.owner):
            return None  # moved by someone else (terminal event, another tick)
        record: dict | None = None
        for attempt in range(1, MAX_REPLANS + 2):
            remaining = deadline - self.clock()
            if remaining <= 0:
                await self.give_up(iid, "deadline", "the investigation deadline passed before an answer")
                return record
            scope = self.scope_of(iid)
            if scope is None:
                return record
            record = await self.brain.handle_safely(self.incident_of(iid), still_current=lambda: self.scope_of(iid) == scope,
                                                    timeout_s=remaining, run_id=f"{iid}:cmd:{attempt}")
            if not record.get("superseded"):
                break
            log.info("incident %s: scope changed during diagnosis; replanning", iid)
        else:
            await self.give_up(iid, "scope_churn", "the incident kept growing while it was diagnosed; look by hand")
            return record
        decision = (record.get("gateway") or {}).get("decision")
        phase = {"executed": "monitoring", "awaiting_approval": "awaiting_gateway"}.get(str(decision), "needs_human")
        w = self.ws.workspace(iid)
        if w is not None and w["phase"] != "terminal":
            self.ws.update(iid, w["revision"], phase=phase)
        return record

    # a human takes it: existing escalation contract (card + escalated event), phase needs_human
    async def give_up(self, iid: str, code: str, reason: str) -> None:
        w = self.ws.workspace(iid)
        if w is None or w["phase"] == "terminal" or w["last_error"] in GIVEN_UP:
            return
        if not self.ws.update(iid, w["revision"], phase="needs_human", last_error=code):
            return
        log.error("incident %s: %s", iid, reason)
        decision = GatewayDecision(decision="escalated", failed_step="coordinator", reason=reason)
        await self.brain.escalate(self.incident_of(iid), None, decision, reason, None)

    # gateway said this incident is over: close only its memberships, cancel its reads
    def on_terminal(self, iid: str) -> None:
        w = self.ws.workspace(iid)
        if w is None or w["phase"] == "terminal":
            return
        with self.ws.tx() as c:
            self.ws.close_memberships(c, iid)
            self.ws.cancel_tasks(c, iid, "incident_terminal")
            c.execute("UPDATE orchestration_workspaces SET phase='terminal', revision=revision+1 WHERE incident_id=?",
                      (iid,))
        task = self.commanders.pop(iid, None)
        if task is not None and not task.done() and task is not asyncio.current_task():
            task.cancel()

    async def follow_terminal_events(self) -> None:
        after, down_since = 0, None
        while True:
            try:
                async for envelope in read_events(self.brain.http, self.brain.gateway_url, after):
                    after = envelope["seq"]
                    event = envelope["event"]
                    if event["type"] in TERMINAL_EVENTS and event.get("incident_id"):
                        self.on_terminal(event["incident_id"])
                down_since = None
            except Exception as e:  # any error, else incidents stop closing for good
                if down_since is None:
                    log.warning("event stream failed: %s; retrying every 2 s", type(e).__name__)
                    down_since = self.clock()
            await asyncio.sleep(2)

    # last nets: a queued incident escalates before the max age, any incident at it
    async def expire(self) -> None:
        max_age = self.brain.policy["detection"]["incident_max_age_seconds"]
        now = self.clock()
        for iid in self.ws.unfinished():
            w = self.ws.workspace(iid)
            row = self.ws.row("SELECT opened_at FROM incidents WHERE id=?", (iid,))
            if w is None or row is None:
                continue
            age = now - row["opened_at"]
            if w["phase"] == "queued" and age >= max_age - QUEUE_GRACE_S:
                await self.give_up(iid, "queue_wait", f"waited {age:.0f} s for a free investigator; look by hand")
            elif age >= max_age:
                await self.give_up(iid, "max_age", f"no outcome {age:.0f} s after opening; look by hand")

    # ---- events: outbox first, then the bus

    def _enqueue(self, c: Any, kind: str, incident_id: str | None, payload: dict) -> None:
        event_id = f"evt-{uuid.uuid4().hex}"
        self.ws.enqueue(c, event_id, "gateway", kind, incident_id,
                        {"type": kind, "incident_id": incident_id, "payload": payload, "event_id": event_id})

    async def emit(self, kind: str, incident_id: str | None, payload: dict) -> None:
        with self.ws.tx() as c:
            self._enqueue(c, kind, incident_id, payload)
        await self.flush()

    # oldest first; stop at the first failure so order holds; a permanent refusal is kept, not retried forever
    async def flush(self) -> None:
        async with self.flush_lock:
            for row in self.ws.due("gateway"):
                try:
                    r = await self.brain.http.post(f"{self.brain.gateway_url}/events/publish", timeout=5,
                                                   content=row["body_json"],
                                                   headers={**auth.headers(), "content-type": "application/json"})
                    if r.status_code in (400, 422):
                        log.error("event %s (%s) refused by the bus: %s", row["event_id"], row["event_type"],
                                  r.text[:200])
                        self.ws.mark_delivered(row["event_id"], error=f"refused {r.status_code}")
                        continue
                    r.raise_for_status()
                except httpx.HTTPError as e:
                    self.ws.mark_failed(row["event_id"], type(e).__name__)
                    return
                self.ws.mark_delivered(row["event_id"])
