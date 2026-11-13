# fleet coordinator (handoff §4-§5): takes observer episodes, groups them by supported cause, owns incidents.
# Deterministic code, no LLM calls. Shadow mode only records what it would have done.
import json
import logging
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import httpx

from brain.correlation import Decision, correlate
from brain.culprit import fetch_error_traces, from_traces
from schemas.orchestration import OrchestrationPolicy, SignalAck, SignalBatch, SignalEpisode
from schemas.workspace import Workspace

if TYPE_CHECKING:
    from brain.main import Brain

log = logging.getLogger("brain.coordinator")
TERMINAL_STATES = ("resolved", "escalated", "handed_off")


class ModeMismatch(Exception):
    pass


class Coordinator:
    def __init__(self, brain: "Brain", workspace: Workspace, policy: OrchestrationPolicy,
                 clock: Callable[[], float] = time.time):
        self.brain, self.ws, self.policy, self.clock = brain, workspace, policy, clock
        # shadow only: virtual incidents, key -> {"cause": str | None, "episodes": set[str]}
        self.shadow_groups: dict[str, dict[str, Any]] = {}
        self.shadow_seq = 0

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
