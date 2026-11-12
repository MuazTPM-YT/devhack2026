from brain.bundle import (build_bundle, change_evidence, k8s_evidence, log_evidence, memory_ratio,
                          metric_evidence, trace_evidence)
from schemas.models import Incident

ERR = [{"key": "error", "value": True}, {"key": "otel.status_description", "value": "card declined"}]


def row(id_, obj="deployment/payment", kind="image", ts=950.0, diff=None):
    return {"id": id_, "object": obj, "kind": kind, "ts": ts, "field_manager": "chaos-panel", "by_agent": False,
            "diff": diff or {"containers[payment].image": {"old": "ghcr.io/x:1", "new": "payment:v2-bad"}}}


def test_change_evidence_hides_env_values():
    diff = {"containers[checkout].env": {"old": [{"name": "PAYMENT_ADDR", "value": "payment:8080"},
                                                 {"name": "KEEP", "value": "1"}],
                                         "new": [{"name": "PAYMENT_ADDR", "value": "s3cr3t-host:1"},
                                                 {"name": "KEEP", "value": "1"}]}}
    e = change_evidence(row(7, "deployment/checkout", "env", diff=diff))
    assert e.id == "journal:7" and "PAYMENT_ADDR" in e.summary
    assert "s3cr3t-host" not in e.summary and "KEEP" not in e.summary
    assert "payment:v2-bad" in change_evidence(row(8)).summary


def test_metric_and_trace_evidence():
    health = {"ts": 5.0, "services": {"payment": {"err_ratio": 0.4, "p95_ms": 300.0, "baseline_p95_ms": 100.0}}}
    ids = [e.id for e in metric_evidence(health, ["payment", "missing"])]
    assert ids == ["query:err_ratio:service=payment", "query:p95_ms:service=payment"]
    trace = {"traceID": "abc", "processes": {"p1": {"serviceName": "checkout"}, "p2": {"serviceName": "payment"}},
             "spans": [{"spanID": "1", "processID": "p1", "operationName": "PlaceOrder", "tags": ERR[:1]},
                       {"spanID": "2", "processID": "p2", "operationName": "Charge", "tags": ERR}]}
    e = trace_evidence([trace] * 7, 5.0)
    assert len(e) == 5 and e[0].id == "trace:abc"
    assert "checkout > payment" in e[0].summary and "payment:Charge card declined" in e[0].summary


def pod(name="recommendation-6b-x", restarts=1, reason="OOMKilled"):
    return {"metadata": {"name": name, "ownerReferences": [{"kind": "ReplicaSet", "name": "recommendation-6b"}]},
            "spec": {"containers": [{"name": "app", "resources": {"limits": {"memory": "256Mi"}}}]},
            "status": {"containerStatuses": [{"name": "app", "restartCount": restarts,
                                              "lastState": {"terminated": {"reason": reason, "exitCode": 137}}}]}}


def test_k8s_evidence_events_and_last_state():
    events = [{"metadata": {"uid": "u1"}, "involvedObject": {"name": "recommendation-6b-x"}, "reason": "BackOff",
               "message": "restarting"},
              {"metadata": {"uid": "u2"}, "involvedObject": {"name": "other-pod"}, "reason": "Pulled"}]
    ev = k8s_evidence([pod()], events, 1.0)
    assert [e.id for e in ev] == ["event:u1", "event:recommendation-6b-x:app:last"]
    assert "OOMKilled" in ev[1].summary and "exit 137" in ev[1].summary


def test_logs_keep_error_lines_capped():
    text = "\n".join(["INFO ok"] * 5 + [f"ERROR boom {i}" for i in range(60)])
    e = log_evidence("p", text, 1.0)
    assert e.id.startswith("log:p:") and len(e.summary.splitlines()) == 50 and "INFO" not in e.summary
    assert log_evidence("p", "INFO fine", 1.0) is None


def test_memory_ratio():
    assert memory_ratio([pod()], {"recommendation-6b-x": {"app": "243Mi"}}) == (243 / 256, "256Mi")
    assert memory_ratio([pod()], {}) == (None, None)


def test_build_bundle_picks_changes_on_culprit_and_its_dependencies_in_window():
    inc = Incident(id="inc-1", opened_at=1000, onset_at=1000, unhealthy=["checkout"], culprit="checkout",
                   victims=["frontend"], severity=4)
    edges = [("frontend", "checkout", 1.0), ("checkout", "payment", 1.0), ("cart", "valkey-cart", 1.0)]
    rows = [row(1), row(2, "deployment/cart"), row(3, ts=100.0), row(4, "configmap/flagd-config", "flag",
                                                                         diff={"data[x]": {"old": "a", "new": "b"}})]
    health = {"ts": 1000.0, "services": {"checkout": {"err_ratio": 0.2, "first_breach_ts": 980.0},
                                         "frontend": {"err_ratio": 0.1, "first_breach_ts": 990.0}}}
    b = build_bundle(inc, rows, health, [], {"events": [], "logs": []}, edges, 600, 1000.0)
    assert [e.id for e in b.changes] == ["journal:1", "journal:4"]
    assert b.onset_order == [("checkout", 980.0), ("frontend", 990.0)]
    assert {e.id for e in b.metrics} == {"query:err_ratio:service=checkout", "query:err_ratio:service=frontend"}
