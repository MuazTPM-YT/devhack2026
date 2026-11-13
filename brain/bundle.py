# evidence bundle (IMPLEMENTATION.md §6.3.4): every item has an ID the model must cite; DiagnosisService
# re-checks those IDs and redacts the whole bundle before it leaves the process.
import hashlib
import json
import re
from typing import Any

from brain.culprit import is_error
from brain.graph import downstream
from brain.rules import to_bytes
from observer.kube_watch import service_of
from schemas.models import Evidence, EvidenceBundle, Incident

ERROR_LINE = re.compile(r"\b(error|fatal|exception|panic|failed)\b", re.I)


# env values can be secrets: name the changed vars, never their values
def change_evidence(row: dict) -> Evidence:
    parts = []
    for path, d in row["diff"].items():
        if path.endswith(".env"):
            names = sorted({e["name"] for e in (d["old"] or []) + (d["new"] or [])
                            if e not in (d["old"] or []) or e not in (d["new"] or [])})
            parts.append(f"{path} changed: {', '.join(names)}")
        else:
            parts.append(f"{path}: {json.dumps(d['old'])} -> {json.dumps(d['new'])}")
    who = row.get("field_manager") or "unknown"
    return Evidence(id=f"journal:{row['id']}", kind="journal", ts=row["ts"],
                    summary=f"{row['object']} {row['kind']} change by {who}: {'; '.join(parts)}"[:600])


# the card's "Why" line from the journal entry a fix reverts (env values never shown)
def why_text(entry: dict | None, onset: float | None) -> str | None:
    if entry is None:
        return None
    lag = f"; errors began {onset - entry['ts']:.0f} s later" if onset and onset >= entry["ts"] else ""
    return change_evidence(entry).summary + lag


def metric_evidence(health: dict, services: list[str]) -> list[Evidence]:
    out = []
    for s in services:
        v = health["services"].get(s)
        if not v:
            continue
        if v.get("err_ratio") is not None:
            out.append(Evidence(id=f"query:err_ratio:service={s}", kind="query", value=v["err_ratio"],
                                ts=health["ts"], summary=f"{s} error ratio now {v['err_ratio']:.3f}"))
        if v.get("p95_ms") is not None:
            base = v.get("baseline_p95_ms")
            note = f", baseline {base:.0f} ms" if base is not None else ", no baseline yet"
            out.append(Evidence(id=f"query:p95_ms:service={s}", kind="query", value=v["p95_ms"],
                                ts=health["ts"], summary=f"{s} p95 latency now {v['p95_ms']:.0f} ms{note}"))
    return out


def _span_error_text(span: dict) -> str:
    for t in span.get("tags", []):
        if t["key"] in ("error.message", "exception.message", "otel.status_description"):
            return str(t.get("value"))[:160]
    return ""


def trace_evidence(traces: list[dict], now: float, limit: int = 5) -> list[Evidence]:
    out = []
    for t in traces[:limit]:
        svc = {pid: p["serviceName"] for pid, p in t.get("processes", {}).items()}
        spans = t.get("spans", [])
        path = " > ".join(dict.fromkeys(svc.get(s["processID"], "?") for s in spans))
        errors = [f"{svc.get(s['processID'], '?')}:{s.get('operationName', '?')} {_span_error_text(s)}".strip()
                  for s in spans if is_error(s)][:3]
        out.append(Evidence(id=f"trace:{t['traceID']}", kind="trace", ts=now,
                            summary=f"{path}; errors: {' | '.join(errors) or 'none'}"[:600]))
    return out


# Kubernetes events on the culprit's pods, plus each container's last termination (OOMKilled, exit code)
def k8s_evidence(pods: list[dict], events: list[dict], now: float) -> list[Evidence]:
    names = {p["metadata"]["name"] for p in pods}
    out = [Evidence(id=f"event:{e['metadata']['uid']}", kind="event", ts=now,
                    summary=f"{e['involvedObject']['name']}: {e.get('reason')} {e.get('message', '')}"[:400])
           for e in events if e.get("involvedObject", {}).get("name") in names]
    for p in pods:
        for c in (p.get("status") or {}).get("containerStatuses") or []:
            term = (c.get("lastState") or {}).get("terminated")
            if term:
                out.append(Evidence(id=f"event:{p['metadata']['name']}:{c['name']}:last", kind="event", ts=now,
                                    summary=f"container {c['name']} in {p['metadata']['name']} last ended "
                                            f"{term.get('reason')}, exit {term.get('exitCode')}, restarts "
                                            f"{c.get('restartCount', 0)}"))
    return out


def log_evidence(pod: str, text: str, now: float, cap: int = 50) -> Evidence | None:
    lines = [line for line in text.splitlines() if ERROR_LINE.search(line)][-cap:]
    if not lines:
        return None
    body = "\n".join(lines)
    return Evidence(id=f"log:{pod}:{hashlib.sha256(body.encode()).hexdigest()[:12]}", kind="log", ts=now,
                    summary=body)


# highest usage/limit across the culprit's containers; None when unknown
def memory_ratio(pods: list[dict], usage: dict[str, dict[str, str]]) -> tuple[float | None, str | None]:
    best, limit_of_best = None, None
    for p in pods:
        for c in p["spec"]["containers"]:
            limit = ((c.get("resources") or {}).get("limits") or {}).get("memory")
            used = usage.get(p["metadata"]["name"], {}).get(c["name"])
            if limit and used:
                ratio = to_bytes(used) / to_bytes(limit)
                if best is None or ratio > best:
                    best, limit_of_best = ratio, limit
    return best, limit_of_best


# blocking reads with the reader identity; run in a thread
def collect_k8s(core: Any, custom: Any, namespace: str, service: str, now: float) -> dict:
    pods = [p for p in json.loads(core.list_namespaced_pod(namespace, _preload_content=False).data)["items"]
            if service_of(p) == service]
    events = json.loads(core.list_namespaced_event(namespace, _preload_content=False).data)["items"]
    logs = []
    usage: dict[str, dict[str, str]] = {}
    for p in pods:
        name = p["metadata"]["name"]
        crashed = any((c.get("restartCount") or 0) > 0 for c in (p.get("status") or {}).get("containerStatuses") or [])
        try:
            text = core.read_namespaced_pod_log(name, namespace, since_seconds=300, tail_lines=2000,
                                                previous=crashed)
            if (ev := log_evidence(name, text, now)) is not None:
                logs.append(ev)
        except Exception:  # no previous container, pod gone: logs are best effort
            pass
        try:
            m = custom.get_namespaced_custom_object("metrics.k8s.io", "v1beta1", namespace, "pods", name)
            usage[name] = {c["name"]: c["usage"]["memory"] for c in m.get("containers", [])}
        except Exception:
            pass
    ratio, limit = memory_ratio(pods, usage)
    return {"events": k8s_evidence(pods, events, now), "logs": logs, "memory_ratio": ratio, "memory_limit": limit}


def build_bundle(incident: Incident, journal_rows: list[dict], health: dict, traces: list[dict],
                 k8s: dict, edges: list[tuple[str, str, float]], window_s: float, now: float) -> EvidenceBundle:
    related = {incident.culprit, *downstream(edges, incident.culprit)} if incident.culprit else set()
    objects = {f"deployment/{s}" for s in related}
    changes = [change_evidence(r) for r in journal_rows
               if incident.onset_at - window_s <= r["ts"] <= incident.onset_at
               and (r["object"] in objects or r["kind"] in ("flag", "configmap"))]
    watched = [s for s in [incident.culprit, *incident.victims] if s]
    onset = sorted(((s, v["first_breach_ts"]) for s, v in health["services"].items()
                    if v.get("first_breach_ts") is not None), key=lambda x: x[1])
    return EvidenceBundle(incident=incident, changes=changes, metrics=metric_evidence(health, watched),
                          traces=trace_evidence(traces, now), events=k8s.get("events", []), logs=k8s.get("logs", []),
                          dependency_edges=edges, onset_order=onset)
