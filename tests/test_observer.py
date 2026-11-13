import json

import httpx
from fastapi.testclient import TestClient

from observer import baselines
from observer.kube_watch import Tracker
from observer.main import Observer, create_app, require_env
from schemas import auth
from schemas import config
from schemas.db import connect

POLICY = config.load("policy")
QUERIES = config.load("queries")


def prom_result(rows):
    return {"status": "success", "data": {"resultType": "vector", "result": [
        {"metric": {"service_name": s}, "value": [0, str(v)]} for s, v in rows.items()]}}


class Backend:
    """Fake Prometheus + gateway + brain behind one httpx MockTransport."""

    def __init__(self, err, p95):
        self.err, self.p95, self.posts, self.prom_down = err, p95, [], False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/query":
            if self.prom_down:
                return httpx.Response(503)
            q = request.url.params["query"]
            return httpx.Response(200, json=prom_result(self.err if "STATUS_CODE_ERROR" in q else self.p95))
        self.posts.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={})


def make(backend, clock):
    conn = connect(":memory:", shared=True)  # same as build_from_env: endpoints run in a worker thread
    http = httpx.AsyncClient(transport=httpx.MockTransport(backend))
    obs = Observer(conn, Tracker(conn, "flagd-config"), http, "http://prom", "http://brain", "http://gw",
                   POLICY, QUERIES, ["payment", "cart"], clock=lambda: clock[0])
    return obs


async def test_readings_treat_missing_error_row_as_zero_only_with_traffic():
    obs = make(Backend({"payment": 0.4}, {"payment": 120.0, "cart": 30.0}), [0])
    assert await obs.readings() == {"payment": {"err_ratio": 0.4, "p95_ms": 120.0},
                                    "cart": {"err_ratio": 0.0, "p95_ms": 30.0}}
    obs = make(Backend({}, {"payment": 120.0}), [0])
    assert (await obs.readings())["cart"] == {"err_ratio": None, "p95_ms": None}


async def test_nan_rows_are_dropped():
    obs = make(Backend({"payment": "NaN"}, {"payment": 120.0}), [0])
    assert (await obs.readings())["payment"]["err_ratio"] == 0.0


async def test_sustained_errors_open_incident_and_tell_bus_and_brain():
    clock = [1000.0]
    backend = Backend({"payment": 0.4}, {"payment": 120.0, "cart": 30.0})
    obs = make(backend, clock)
    assert await obs.step() is None
    clock[0] = 1030.0
    kind, inc = await obs.step()
    assert (kind, inc["onset_at"], inc["unhealthy"]) == ("incident_opened", 1000.0, ["payment"])
    paths = [p for p, _ in backend.posts]
    assert paths == ["/events/publish", "/incidents"]
    assert backend.posts[0][1]["type"] == "incident_opened"
    assert backend.posts[1][1]["id"] == inc["id"]
    row = obs.conn.execute("SELECT state, onset_at FROM incidents WHERE id=?", (inc["id"],)).fetchone()
    assert tuple(row) == ("open", 1000.0)
    assert obs.health["prometheus_ok"] and obs.health["services"]["payment"]["unhealthy"]


async def test_prometheus_down_keeps_last_health_and_skips_detector():
    clock = [1000.0]
    backend = Backend({"payment": 0.4}, {"payment": 120.0})
    obs = make(backend, clock)
    await obs.step()
    backend.prom_down = True
    clock[0] = 1040.0
    assert await obs.step() is None
    assert obs.health["prometheus_ok"] is False and obs.detector.incident is None


async def test_brain_down_does_not_stop_detection():
    clock = [0.0]

    def handler(request):
        if request.url.path == "/api/v1/query":
            q = request.url.params["query"]
            return httpx.Response(200, json=prom_result({"payment": 0.4} if "ERROR" in q else {"payment": 1.0}))
        return httpx.Response(500)

    obs = make(handler, clock)
    await obs.step()
    clock[0] = 30.0
    assert (await obs.step())[0] == "incident_opened"


async def test_refresh_baselines_stores_medians():
    obs = make(Backend({}, {"payment": 100.0, "cart": 40.0}), [5.0])
    await obs.refresh_baselines(seconds=0.03, every=0.01)
    assert obs.baselines == {"payment": 100.0, "cart": 40.0}
    assert baselines.medians([{"a": {"err_ratio": 0.1, "p95_ms": 10}}, {"a": {"err_ratio": 0.3, "p95_ms": None}}]) \
        == {"a": (0.2, 10)}


def test_endpoints():
    obs = make(Backend({}, {}), [0])
    with TestClient(create_app(obs), headers=auth.headers()) as client:
        assert client.get("/health/now").status_code == 503
        obs.health = {"severity": 0, "services": {}}
        assert client.get("/health/now").json() == {"severity": 0, "services": {}}
        assert client.get("/journal", params={"since": 0, "object": "deployment/payment"}).json() == []


def test_require_env_names_missing(monkeypatch):
    monkeypatch.delenv("PROMETHEUS_URL", raising=False)
    try:
        require_env("PROMETHEUS_URL")
    except RuntimeError as e:
        assert "PROMETHEUS_URL" in str(e)
    else:
        raise AssertionError("expected RuntimeError")


# live run 2026-11-13: brain/gateway down when the incident opened -> it stayed open forever, no new pages
async def test_undelivered_incident_is_resent_until_brain_takes_it():
    clock = [1000.0]
    calls = {"brain_up": False, "incidents": 0}

    def handler(request):
        if request.url.path == "/api/v1/query":
            q = request.url.params["query"]
            return httpx.Response(200, json=prom_result({"payment": 0.4} if "ERROR" in q else {"payment": 1.0}))
        if request.url.path == "/incidents":
            calls["incidents"] += 1
            return httpx.Response(202 if calls["brain_up"] else 503, json={})
        return httpx.Response(200, json={})

    obs = make(handler, clock)
    await obs.step()
    clock[0] = 1030.0
    assert (await obs.step())[0] == "incident_opened"
    clock[0] = 1035.0
    await obs.step()
    assert calls["incidents"] == 2  # retried while the brain is down
    calls["brain_up"] = True
    clock[0] = 1040.0
    await obs.step()
    clock[0] = 1045.0
    await obs.step()
    assert calls["incidents"] == 3  # delivered once, then no more resends


# an incident nobody ended (live: a refused action sent no terminal event) blocked every later incident
async def test_stuck_incident_is_closed_and_escalated_after_max_age():
    clock = [1000.0]
    backend = Backend({"payment": 0.4}, {"payment": 120.0, "cart": 30.0})
    obs = make(backend, clock)
    await obs.step()
    clock[0] = 1030.0
    _, inc = await obs.step()
    clock[0] = 1030.0 + POLICY["detection"]["incident_max_age_seconds"] - 1
    await obs.step()
    assert obs.detector.incident is not None  # not yet
    clock[0] += 2
    backend.posts.clear()
    await obs.step()
    esc = [b for p, b in backend.posts if p == "/events/publish" and b["type"] == "escalated"]
    assert esc and esc[0]["incident_id"] == inc["id"] and "lost track" in esc[0]["payload"]["briefing"]
    assert obs.conn.execute("SELECT state FROM incidents WHERE id=?", (inc["id"],)).fetchone()[0] == "escalated"
    # payment is still sick: suppressed until it recovers once, so no re-page loop
    assert obs.detector.incident is None
