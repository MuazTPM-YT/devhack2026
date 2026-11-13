import pytest
from fastapi.testclient import TestClient

from schemas import auth
from test_gateway import World


# live gap (T): any local process could POST a decision as a listed approver
def test_gateway_writes_need_the_token_reads_do_not(tmp_path):
    from gateway.main import create_app

    w = World(tmp_path)
    body = {"decision": "approved", "decided_by": "u1"}
    with TestClient(create_app(w.gw), base_url="http://127.0.0.1:7003") as client:
        assert client.post("/approvals/a/decide", json=body).status_code == 401
        assert client.post("/approvals/a/decide", json=body, headers={auth.HEADER: "x" * 20}).status_code == 401
        assert client.post("/events/publish", json={"type": "blocked"}).status_code == 401
        assert client.post("/receipts/1/clear", json={"decided_by": "u1"}).status_code == 401
        assert client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).status_code == 401
        assert client.get("/health").status_code == 200 and client.get("/ledger").status_code == 200
        ok = client.post("/approvals/a/decide", json=body, headers=auth.headers())
        assert ok.status_code == 200 and ok.json()["reason"] == "unknown approval"
    assert w.events == []  # nothing reached the bus without the token


def test_brain_refuses_incidents_without_the_token():
    from brain.main import create_app

    with TestClient(create_app(object())) as client:  # type: ignore[arg-type]
        assert client.post("/incidents", json={}).status_code == 401


def test_missing_or_short_token_fails_loud(monkeypatch):
    monkeypatch.setenv(auth.ENV, "short")
    with pytest.raises(RuntimeError, match="ONCALL_API_TOKEN"):
        auth.headers()
    monkeypatch.delenv(auth.ENV)
    with pytest.raises(RuntimeError, match="ONCALL_API_TOKEN"):
        auth.token()
