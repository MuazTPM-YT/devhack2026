# read-only tools the diagnosis agent calls (brain/agent.py). Every result is redacted, injection lines
# quarantined, capped at CAP chars; ids the model saw land in the ledger, the only ids it may cite.
import asyncio
import json
import logging
import math
import sqlite3
import statistics
import threading
import time
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal

import httpx
from pydantic import Field
from pydantic_ai import RunContext, Tool
from pydantic_ai.tools import ToolDefinition

from brain.bundle import change_evidence, k8s_evidence, log_evidence, memory_ratio, metric_evidence, trace_evidence
from brain.culprit import fetch_error_traces, from_traces, is_error
from brain.graph import DependencyGraph
from brain.redact import quarantine, redact_value
from observer.kube_watch import service_of
from schemas import auth
from schemas.models import Evidence, EvidenceBundle, Incident, Tool as FixTool

log = logging.getLogger("brain.tools")

CAP = 2000  # chars per tool result: history is resent every round
MAX_POINTS = 40


# blocking reads with the reader identity (same RBAC as collect_k8s); tools run these in a thread
class KubeReader:
    def __init__(self, core: Any, custom: Any, namespace: str):
        self.core, self.custom, self.namespace = core, custom, namespace

    def pods(self, service: str) -> list[dict]:
        items = json.loads(self.core.list_namespaced_pod(self.namespace, _preload_content=False).data)["items"]
        return [p for p in items if service_of(p) == service]

    def events(self) -> list[dict]:
        return json.loads(self.core.list_namespaced_event(self.namespace, _preload_content=False).data)["items"]

    def log(self, pod: str, since_s: int, previous: bool) -> str:
        return self.core.read_namespaced_pod_log(pod, self.namespace, since_seconds=since_s, tail_lines=2000,
                                                 previous=previous)

    def usage(self, pod: str) -> dict[str, str]:
        m = self.custom.get_namespaced_custom_object("metrics.k8s.io", "v1beta1", self.namespace, "pods", pod)
        return {c["name"]: c["usage"]["memory"] for c in m.get("containers", [])}


@dataclass
class ToolBox:
    incident: Incident
    now: float
    http: httpx.AsyncClient
    observer_url: str
    prom_url: str
    jaeger_url: str
    graph: DependencyGraph
    kube: Any  # KubeReader or a test fake with the same methods
    conn: sqlite3.Connection
    lock: threading.Lock
    services: list[str]
    queries: dict[str, str]
    publish: Callable[[str, str | None, dict], Awaitable[None]]
    edges: list[tuple[str, str, float]] = field(default_factory=list)
    needs_prediction: bool = False
    ledger: dict[str, Evidence] = field(default_factory=dict)
    calls: int = 0
    # agent chooses the fix: what it may accept (rule candidates) and what it may propose (built tools)
    choose: bool = False
    candidates: list[dict] = field(default_factory=list)
    tools_ok: set[str] = field(default_factory=set)
    # fixes already run and undone in this incident (gateway retry context); never chosen again
    tried: list[dict] = field(default_factory=list)

    # what the model was shown, in the shape llm.check validates against
    def bundle(self) -> EvidenceBundle:
        groups: dict[str, list[Evidence]] = {"query": [], "journal": [], "trace": [], "event": [], "log": []}
        for e in self.ledger.values():
            groups[e.kind].append(e)
        return EvidenceBundle(incident=self.incident, changes=groups["journal"], metrics=groups["query"],
                              traces=groups["trace"], events=groups["event"], logs=groups["log"],
                              dependency_edges=self.edges)

    def rel(self, ts: float | None) -> int | None:
        return None if ts is None else round(ts - self.incident.onset_at)

    def unknown(self, *names: str) -> dict | None:
        bad = [n for n in names if n not in self.services]
        return {"error": f"unknown service {', '.join(bad)}", "known": self.services} if bad else None

    # the API token goes to our observer only (GET /journal needs it), never to Prometheus or Jaeger
    async def get_json(self, url: str, **params: Any) -> Any:
        headers = auth.headers() if url.startswith(self.observer_url) else None
        r = await self.http.get(url, params=params, timeout=10, headers=headers)
        r.raise_for_status()
        return r.json()

    # one tool call: run, never raise, redact, cap, record cited ids, tell the bus
    async def call(self, name: str, args: dict, work: Awaitable[tuple[Any, list[Evidence]]]) -> str:
        started = time.monotonic()
        self.calls += 1
        try:
            payload, evidence = await work
        except Exception as e:  # upstream down, RBAC, pod gone: the model hears it and moves on
            log.warning("tool %s failed: %s", name, type(e).__name__)
            payload, evidence = {"error": f"{name} unavailable ({type(e).__name__})"}, []
        text = json.dumps(redact_value(payload), separators=(",", ":"), default=str)
        if len(text) > CAP:
            text = text[:CAP] + " ...[cut]"
        shown = [Evidence.model_validate(redact_value(e.model_dump())) for e in evidence]
        shown = [e for e in shown if e.id in text]
        self.ledger.update((e.id, e) for e in shown)
        await self.publish("tool_called", self.incident.id, {
            "tool": name, "args": redact_value(args), "ms": round((time.monotonic() - started) * 1000),
            "evidence_ids": [e.id for e in shown]})
        return text

    async def health(self, services: list[str] | None) -> tuple[Any, list[Evidence]]:
        pick = services or sorted({*self.incident.unhealthy, *([self.incident.culprit] if self.incident.culprit
                                                               else [])})
        if err := self.unknown(*pick):
            return err, []
        health = await self.get_json(f"{self.observer_url}/health/now")
        rows: list[dict[str, Any]] = []
        evidence: list[Evidence] = []
        for s in pick:
            v = health["services"].get(s)
            if not v:
                rows.append({"service": s, "note": "no reading"})
                continue
            ev = metric_evidence(health, [s])
            evidence += ev
            rows.append({"service": s, "err_ratio": v.get("err_ratio"), "p95_ms": v.get("p95_ms"),
                         "baseline_p95_ms": v.get("baseline_p95_ms"), "unhealthy": v.get("unhealthy"),
                         "bad_pods": v.get("bad_pods"), "breach_s_after_onset": self.rel(v.get("first_breach_ts")),
                         "evidence_ids": [e.id for e in ev]})
        return rows, evidence

    async def history(self, service: str, metric: str, minutes: int, step_s: int) -> tuple[Any, list[Evidence]]:
        if err := self.unknown(service):
            return err, []
        doc = await self.get_json(f"{self.prom_url}/api/v1/query_range",
                                  query=self.queries[metric].replace("$service", service),
                                  start=self.now - minutes * 60, end=self.now, step=step_s)
        result = doc["data"]["result"]
        values = [(float(t), float(v)) for t, v in (result[0]["values"] if result else [])]
        points = [(round(t - self.incident.onset_at), round(v, 4)) for t, v in values if math.isfinite(v)]
        if len(points) > MAX_POINTS:
            every = math.ceil(len(points) / MAX_POINTS)
            points = points[::every] if (len(points) - 1) % every == 0 else points[::every] + [points[-1]]
        if not points:
            return {"service": service, "metric": metric, "points": [], "note": "no data in window"}, []
        before = [v for t, v in points if t < 0]
        after = [v for t, v in points if t >= 0]
        out: dict[str, Any] = {"service": service, "metric": metric, "points_s_from_onset": [list(pt) for pt in points],
               "before_onset_median": round(statistics.median(before), 4) if before else None,
               "after_onset_max": max(after) if after else None, "now": points[-1][1]}
        ev = Evidence(id=f"query:{metric}:service={service}:range", kind="query", value=points[-1][1], ts=self.now,
                      summary=f"{service} {metric} over {minutes} min: median before onset "
                              f"{out['before_onset_median']}, max after {out['after_onset_max']}, now {out['now']}")
        return {"evidence_id": ev.id, **out}, [ev]

    async def changes(self, minutes_before_onset: int, obj: str | None) -> tuple[Any, list[Evidence]]:
        params: dict[str, Any] = {"since": self.incident.onset_at - minutes_before_onset * 60}
        if obj:
            params["object"] = obj
        rows = (await self.get_json(f"{self.observer_url}/journal", **params))[-15:]
        evidence = [change_evidence(r) for r in rows]
        return [{"evidence_id": e.id, "object": r["object"], "kind": r["kind"],
                 "s_before_onset": round(self.incident.onset_at - r["ts"]),
                 "by": "agent" if r.get("by_agent") else "other",
                 "summary": e.summary} for r, e in zip(rows, evidence)], evidence

    async def dependencies(self, service: str, direction: str) -> tuple[Any, list[Evidence]]:
        if err := self.unknown(service):
            return err, []
        edges = await self.graph.get()
        self.edges = sorted(set(self.edges) | set(edges))
        sick = set(self.incident.unhealthy)
        rows = [{"caller": p, "callee": c, "calls_1h": n, "caller_unhealthy": p in sick, "callee_unhealthy": c in sick}
                for p, c, n in edges
                if (direction in ("downstream", "both") and p == service)
                or (direction in ("upstream", "both") and c == service)]
        return rows or {"service": service, "note": "no calls seen in the last hour"}, []

    async def traces(self, service: str, minutes: int, limit: int) -> tuple[Any, list[Evidence]]:
        if err := self.unknown(service):
            return err, []
        found = await fetch_error_traces(self.http, self.jaeger_url, [service], self.now, minutes * 60, limit)
        tally: Counter[tuple[str, str]] = Counter()
        for t in found:
            names = {pid: p["serviceName"] for pid, p in t.get("processes", {}).items()}
            tally.update((names.get(s["processID"], "?"), s.get("operationName", "?"))
                         for s in t.get("spans", []) if is_error(s))
        deepest, _ = from_traces(found)
        evidence = trace_evidence(found, self.now, limit)
        return {"error_traces": len(found), "deepest_erroring": deepest,
                "by_span": [{"service": s, "operation": op, "errors": n} for (s, op), n in tally.most_common(8)],
                "traces": [{"evidence_id": e.id, "summary": e.summary} for e in evidence]}, evidence

    async def pods(self, service: str) -> tuple[Any, list[Evidence]]:
        if err := self.unknown(service):
            return err, []
        pods = await asyncio.to_thread(self.kube.pods, service)
        evidence = k8s_evidence(pods, [], self.now)
        rows = []
        for p in pods[:6]:
            name = p["metadata"]["name"]
            try:
                used = await asyncio.to_thread(self.kube.usage, name)
            except Exception:  # metrics-server lag or pod gone
                used = {}
            ratio, limit = memory_ratio([p], {name: used})
            statuses = (p.get("status") or {}).get("containerStatuses") or []
            ended = [{"container": c["name"], "reason": c["lastState"]["terminated"].get("reason"),
                      "exit_code": c["lastState"]["terminated"].get("exitCode"),
                      "evidence_id": f"event:{name}:{c['name']}:last"}
                     for c in statuses if (c.get("lastState") or {}).get("terminated")]
            created = (p.get("metadata") or {}).get("creationTimestamp")
            rows.append({"pod": name, "phase": (p.get("status") or {}).get("phase"),
                         "ready": all(c.get("ready") for c in statuses) if statuses else False,
                         "restarts": sum(c.get("restartCount", 0) for c in statuses),
                         "images": sorted({c["image"] for c in p["spec"]["containers"] if c.get("image")}),
                         "created": created, "last_end": ended, "mem_limit": limit,
                         "mem_ratio": round(ratio, 3) if ratio is not None else None})
        return rows or {"service": service, "note": "no pods"}, evidence

    async def events(self, service: str, limit: int) -> tuple[Any, list[Evidence]]:
        if err := self.unknown(service):
            return err, []
        pods = await asyncio.to_thread(self.kube.pods, service)
        events = await asyncio.to_thread(self.kube.events)
        evidence = [e for e in k8s_evidence(pods, events, self.now, limit) if not e.id.endswith(":last")]
        return [{"evidence_id": e.id, "summary": e.summary} for e in reversed(evidence)] or \
            {"service": service, "note": "no events"}, evidence

    async def logs(self, service: str, minutes: int, previous: bool, contains: str | None) -> tuple[Any, list[Evidence]]:
        if err := self.unknown(service):
            return err, []
        pods = await asyncio.to_thread(self.kube.pods, service)
        rows, evidence = [], []
        for p in pods[:3]:
            name = p["metadata"]["name"]
            try:
                text = await asyncio.to_thread(self.kube.log, name, minutes * 60, previous)
            except Exception as e:  # no previous container, pod gone
                rows.append({"pod": name, "error": type(e).__name__})
                continue
            if contains:
                text = "\n".join(line for line in text.splitlines() if contains.lower() in line.lower())
            ev = log_evidence(name, text, self.now, cap=30)
            if ev is None:
                rows.append({"pod": name, "note": "no error lines"})
                continue
            lines, hashes = quarantine(ev.summary.splitlines())
            for h in hashes:
                await self.publish("injection_quarantined", self.incident.id, {"line_hash": h})
            if lines:
                ev = ev.model_copy(update={"summary": "\n".join(lines)})
                evidence.append(ev)
            rows.append({"pod": name, "evidence_id": ev.id if lines else None, "error_lines": lines,
                         "quarantined": len(hashes)})
        return rows or {"service": service, "note": "no pods"}, evidence

    async def fix_history(self, tool: str, target: str) -> tuple[Any, list[Evidence]]:
        if err := self.unknown(target):
            return err, []
        with self.lock:
            rows = self.conn.execute(
                "SELECT r.incident_id, r.outcome, r.ts, r.forecast_json, i.resolved_at FROM receipts r "
                "LEFT JOIN incidents i ON i.id = r.incident_id WHERE r.tool=? AND r.target=? AND r.incident_id != ? "
                "AND r.outcome != 'pending' ORDER BY r.ts DESC LIMIT 5",
                (tool, target, self.incident.id)).fetchall()
        out = []
        for r in rows:
            forecast = json.loads(r["forecast_json"] or "{}")
            out.append({"incident_id": r["incident_id"], "outcome": r["outcome"],
                        # the verifier says success only when the prediction held
                        "prediction_held": {"success": True, "right_by_accident": False}.get(r["outcome"]),
                        "recovered_s_after_fix": round(r["resolved_at"] - r["ts"]) if r["resolved_at"] else None,
                        "predicted": forecast.get("prediction")})
        return out or {"tool": tool, "target": target, "note": "never run before"}, []


Minutes = Annotated[int, Field(ge=1, le=30)]


async def get_service_health(ctx: RunContext[ToolBox], services: list[str] | None = None) -> str:
    return await ctx.deps.call("get_service_health", {"services": services}, ctx.deps.health(services))


async def get_metric_history(ctx: RunContext[ToolBox], service: str, metric: Literal["err_ratio", "p95_ms"],
                             minutes: Minutes = 15, step_s: Annotated[int, Field(ge=15, le=60)] = 30) -> str:
    args = {"service": service, "metric": metric, "minutes": minutes, "step_s": step_s}
    return await ctx.deps.call("get_metric_history", args, ctx.deps.history(service, metric, minutes, step_s))


async def get_recent_changes(ctx: RunContext[ToolBox], minutes_before_onset: Minutes = 10,
                             object: Annotated[str | None, Field(pattern=r"^(deployment|configmap)/[a-z0-9-]{1,63}$")]
                             = None) -> str:
    args = {"minutes_before_onset": minutes_before_onset, "object": object}
    return await ctx.deps.call("get_recent_changes", args, ctx.deps.changes(minutes_before_onset, object))


async def get_dependencies(ctx: RunContext[ToolBox], service: str,
                           direction: Literal["upstream", "downstream", "both"] = "both") -> str:
    args = {"service": service, "direction": direction}
    return await ctx.deps.call("get_dependencies", args, ctx.deps.dependencies(service, direction))


async def search_error_traces(ctx: RunContext[ToolBox], service: str,
                              minutes: Annotated[int, Field(ge=1, le=15)] = 5,
                              limit: Annotated[int, Field(ge=1, le=10)] = 5) -> str:
    args = {"service": service, "minutes": minutes, "limit": limit}
    return await ctx.deps.call("search_error_traces", args, ctx.deps.traces(service, minutes, limit))


async def get_pods(ctx: RunContext[ToolBox], service: str) -> str:
    return await ctx.deps.call("get_pods", {"service": service}, ctx.deps.pods(service))


async def get_k8s_events(ctx: RunContext[ToolBox], service: str, limit: Annotated[int, Field(ge=1, le=20)] = 10) -> str:
    return await ctx.deps.call("get_k8s_events", {"service": service, "limit": limit}, ctx.deps.events(service, limit))


async def get_pod_logs(ctx: RunContext[ToolBox], service: str, minutes: Annotated[int, Field(ge=1, le=10)] = 5,
                       previous: bool = False, contains: Annotated[str | None, Field(max_length=40)] = None) -> str:
    args = {"service": service, "minutes": minutes, "previous": previous, "contains": contains}
    return await ctx.deps.call("get_pod_logs", args, ctx.deps.logs(service, minutes, previous, contains))


async def get_fix_history(ctx: RunContext[ToolBox], tool: FixTool, target: str) -> str:
    return await ctx.deps.call("get_fix_history", {"tool": tool, "target": target}, ctx.deps.fix_history(tool, target))


DESCRIPTIONS: dict[Callable[..., Awaitable[str]], str] = {
    get_service_health: "Error ratio, p95 latency vs baseline, bad pods and breach time (s after onset) now. "
                        "Default: the unhealthy services and the culprit guess.",
    get_metric_history: "One metric for one service over the last minutes, points as [s from onset, value], "
                        "with median before onset. Use it to pick the prediction threshold.",
    get_recent_changes: "Journal of deployment, configmap and flag changes before onset. Env values are hidden.",
    get_dependencies: "Who calls whom (last hour, from traces), with which neighbours are unhealthy.",
    search_error_traces: "Recent error traces of one service: error spans by operation and the deepest erroring "
                         "service.",
    get_pods: "Pods of one service: phase, ready, restarts, images, last termination (OOMKilled, exit code), "
              "memory use vs limit.",
    get_k8s_events: "Newest Kubernetes events on the pods of one service.",
    get_pod_logs: "Error lines from the pods of one service, repeats counted. previous=true reads the crashed "
                  "container. contains filters lines by a word.",
    get_fix_history: "Earlier runs of this fix on this target: outcome, whether the prediction held, seconds to "
                     "recover, and what was predicted. Use it to pick within_s.",
}


# tools vanish after max_rounds model turns, so the model must answer instead of looking further
def toolset(max_rounds: int) -> list[Tool[ToolBox]]:
    async def budget(ctx: RunContext[ToolBox], tool_def: ToolDefinition) -> ToolDefinition | None:
        return tool_def if ctx.run_step <= max_rounds else None

    return [Tool(fn, description=text, prepare=budget, max_retries=2) for fn, text in DESCRIPTIONS.items()]
