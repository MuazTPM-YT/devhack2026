import json
import os

import httpx
import pytest
from mcp import types
from mcp.shared.memory import create_connected_server_and_client_session

from akira_mcp import report, settings, watch
from akira_mcp.__main__ import main
from akira_mcp.server import CAP, build_server, out
from schemas import auth

APPROVAL = {"id": "a1", "incident_id": "inc-1", "state": "pending", "past_expiry": False,
            "action": {"tool": "rollback_deploy", "target": "payment"}}
WRITE_TOOLS = {"decide_approval", "acknowledge_page", "clear_receipt", "create_chaos", "draw_random_chaos",
               "reset_shop", "stop_chaos"}


def rec(seq, kind, incident="inc-1", ts=100.0, **payload):
    return {"seq": seq, "ts": ts, "event": {"type": kind, "incident_id": incident, "payload": payload}}


class Backend:
    """Fake gateway/observer/notifier/chaos: routes by (method, path); every request is kept."""

    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.routes: dict[tuple[str, str], object] = {
            ("GET", "/health"): {"ok": True},
            ("GET", "/health/now"): {"ts": 1.0, "severity": 3, "prometheus_ok": True, "services": {
                "payment": {"err_ratio": 0.4, "unhealthy": True, "breaching": True},
                "cart": {"err_ratio": 0.0, "unhealthy": False, "breaching": False}}},
            ("GET", "/approvals"): [APPROVAL],
            ("POST", "/approvals/a1/decide"): {"decision": "executed", "receipt_id": 3},
            ("POST", "/pages/inc-1/ack"): {"result": "acknowledged", "message_updated": True},
            ("GET", "/incidents"): [{"id": "inc-1"}],
        }

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        found = self.routes.get((request.method, request.url.path))
        if found is None:
            return httpx.Response(404, json={"detail": "not here"})
        if callable(found):
            return found(request)
        return httpx.Response(200, json=found)

    def sent(self, method, path):
        return [r for r in self.requests if r.method == method and r.url.path == path]


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("AKIRA_MCP_TOOLSETS", "read")  # recorded, so server() changes are undone
    monkeypatch.setenv("ONCALL_APPROVER_IDS", "123,456")
    monkeypatch.setenv("AKIRA_OPERATOR_ID", "123")
    return monkeypatch


def server(backend, toolsets="read"):
    os.environ["AKIRA_MCP_TOOLSETS"] = toolsets
    return build_server(settings.load(), httpx.AsyncClient(transport=httpx.MockTransport(backend)))


def accept(confirm=True):
    async def answer(context, params):
        answer.asked.append(params.message)
        return types.ElicitResult(action="accept", content={"confirm": confirm})
    answer.asked = []
    return answer


async def call(srv, name, args=None, elicit=None):
    async with create_connected_server_and_client_session(srv, elicitation_callback=elicit) as client:
        result = await client.call_tool(name, args or {})
    text = result.content[0].text if result.content else ""
    return result, (result.structuredContent if not result.isError else text)


# ---- settings: each write group needs its own secret, and the judge's is dropped otherwise ------------

def test_read_only_by_default_and_judge_token_dropped(env):
    s = settings.load()
    assert s.toolsets == {"read"} and s.operator_id is None and s.api_token
    assert auth.JUDGE_ENV not in os.environ


@pytest.mark.parametrize("change, error", [
    ({"AKIRA_MCP_TOOLSETS": "read,root"}, "unknown toolset"),
    ({"AKIRA_MCP_TOOLSETS": "chaos", auth.JUDGE_ENV: None}, "CHAOS_JUDGE_TOKEN"),
    ({"AKIRA_MCP_TOOLSETS": "approvals", "AKIRA_OPERATOR_ID": None}, "AKIRA_OPERATOR_ID"),
    ({"AKIRA_MCP_TOOLSETS": "approvals", "AKIRA_OPERATOR_ID": "rehearsal-harness"}, "digits only"),
    ({"AKIRA_MCP_TOOLSETS": "approvals", "AKIRA_OPERATOR_ID": "999"}, "not in ONCALL_APPROVER_IDS"),
    ({"AKIRA_MCP_TOOLSETS": "approvals", "ONCALL_APPROVER_IDS": None}, "ONCALL_APPROVER_IDS"),
    ({"AKIRA_MCP_TOOLSETS": "approvals", auth.ENV: None}, "ONCALL_API_TOKEN"),
    ({"GATEWAY_URL": "file:///etc/passwd"}, "GATEWAY_URL"),
])
def test_missing_or_bad_setting_fails_loud(env, change, error):
    for k, v in change.items():
        env.delenv(k, raising=False) if v is None else env.setenv(k, v)
    with pytest.raises(settings.SettingsError, match=error):
        settings.load()


def test_main_exits_2_with_the_reason_on_stderr(env, capsys):
    env.setenv("AKIRA_MCP_TOOLSETS", "chaos")
    env.delenv(auth.JUDGE_ENV)
    assert main(["serve"]) == 2
    assert "CHAOS_JUDGE_TOKEN" in capsys.readouterr().err


# ---- tool surface ------------------------------------------------------------------------------------

async def test_default_server_has_no_write_tools(env):
    tools = {t.name: t for t in await server(Backend()).list_tools()}
    assert not set(tools) & WRITE_TOOLS and "watch_events" in tools and "get_recent_changes" in tools
    assert all(t.annotations.readOnlyHint for t in tools.values())


async def test_journal_tool_needs_the_api_token(env):
    env.delenv(auth.ENV)
    assert "get_recent_changes" not in {t.name for t in await server(Backend()).list_tools()}


async def test_write_tools_are_marked_and_never_take_an_identity(env):
    tools = {t.name: t for t in await server(Backend(), "read,chaos,approvals").list_tools()}
    assert WRITE_TOOLS <= set(tools)
    assert tools["create_chaos"].annotations.destructiveHint and not tools["stop_chaos"].annotations.destructiveHint
    for name in WRITE_TOOLS:
        props = tools[name].inputSchema.get("properties", {})
        assert not {"decided_by", "by", "ctx", "origin"} & set(props), name
    assert tools["decide_approval"].inputSchema["properties"]["decision"]["enum"] == ["approved", "rejected"]


# ---- read tools ----------------------------------------------------------------------------------------

async def test_service_health_can_show_only_the_unhealthy(env):
    _, body = await call(server(Backend()), "get_service_health", {"only_unhealthy": True})
    assert list(body["services"]) == ["payment"] and body["severity"] == 3


async def test_list_incidents_passes_filters(env):
    b = Backend()
    _, body = await call(server(b), "list_incidents", {"unfinished": True, "limit": 5})
    assert body == {"incidents": [{"id": "inc-1"}]}
    assert dict(b.sent("GET", "/incidents")[0].url.params) == {"limit": "5", "unfinished": "true"}


async def test_service_down_is_a_readable_tool_error(env):
    def down(request):
        raise httpx.ConnectError("refused")
    result, text = await call(server(down), "list_pending_approvals")
    assert result.isError and "cannot reach http://127.0.0.1:7003/approvals" in text


async def test_incident_timeline_is_one_line_per_event(env):
    b = Backend()
    b.routes[("GET", "/incidents/inc-1")] = {
        "incident": {"id": "inc-1"}, "approvals": [], "receipts": [], "similar": [], "events_total": 2,
        "events": [rec(1, "incident_opened", unhealthy=["payment"], severity=4), rec(2, "approval_decided",
                                                                                     decision="approved")]}
    _, body = await call(server(b), "get_incident", {"incident_id": "inc-1"})
    assert "events" not in body
    assert [e["text"] for e in body["timeline"]] == ["incident opened · payment · severity 4", "approval approved"]


async def test_watch_starts_from_now_and_returns_the_next_cursor(env, monkeypatch):
    monkeypatch.setattr("akira_mcp.server.POLL_S", 0)
    b = Backend()
    pages = iter([{"records": [], "last_seq": 7, "next_after": 7},
                  {"records": [rec(8, "verify_tick", severity=1), rec(9, "incident_resolved", card={"text": "FIXED"})],
                   "last_seq": 9, "next_after": 9}])

    def log(request):
        if request.url.params["limit"] == "1":
            return httpx.Response(200, json={"records": [], "last_seq": 7, "next_after": 7})
        return httpx.Response(200, json=next(pages))

    b.routes[("GET", "/events/log")] = log
    _, body = await call(server(b), "watch_events", {"wait_s": 5, "types": ["incident_resolved"]})
    assert [e["seq"] for e in body["events"]] == [9] and body["next_seq"] == 9 and not body["timed_out"]
    assert [r.url.params["after"] for r in b.sent("GET", "/events/log")] == ["0", "7", "7"]


async def test_watch_times_out_empty(env, monkeypatch):
    monkeypatch.setattr("akira_mcp.server.POLL_S", 0)
    b = Backend()
    b.routes[("GET", "/events/log")] = {"records": [], "last_seq": 3, "next_after": 3}
    _, body = await call(server(b), "watch_events", {"after_seq": 3, "wait_s": 0})
    assert body["timed_out"] and body["events"] == [] and body["next_seq"] == 3


def test_big_results_are_cut_and_secrets_redacted():
    cut = out({"rows": ["a plain log line " * 6] * (CAP // 50)})
    assert cut["truncated"] and len(cut["preview"]) == CAP
    assert "hunter2" not in json.dumps(out({"line": "password=hunter2"}))


async def test_runbooks_read_from_the_repo_config(env):
    _, body = await call(server(Backend()), "get_runbooks", {"runbook_id": "RB-01"})
    assert [b["id"] for b in body["runbooks"]] == ["RB-01"] and body["runbooks"][0]["steps"]


# ---- approvals: confirmed by a human, always as the configured operator ------------------------------

async def test_approve_after_dialog_acts_as_the_operator(env):
    b, ask = Backend(), accept()
    _, body = await call(server(b, "approvals"), "decide_approval",
                         {"approval_id": "a1", "decision": "approved"}, elicit=ask)
    assert body["gateway"]["decision"] == "executed" and body["confirmed_by"] == "confirmed in dialog"
    assert "rollback_deploy on payment" in ask.asked[0]
    sent = b.sent("POST", "/approvals/a1/decide")[0]
    assert json.loads(sent.content) == {"decision": "approved", "decided_by": "123", "via": "akira-mcp"}
    assert sent.headers[auth.HEADER] == auth.token()


@pytest.mark.parametrize("answer", [accept(confirm=False), None])
async def test_declined_dialog_changes_nothing(env, answer):
    async def decline(context, params):
        return types.ElicitResult(action="decline")
    b = Backend()
    result, text = await call(server(b, "approvals"), "decide_approval",
                              {"approval_id": "a1", "decision": "approved"}, elicit=answer or decline)
    assert result.isError and "nothing was done" in text and not b.sent("POST", "/approvals/a1/decide")


async def test_client_without_dialogs_relies_on_its_permission_prompt(env):
    b = Backend()
    _, body = await call(server(b, "approvals"), "decide_approval", {"approval_id": "a1", "decision": "rejected"})
    assert body["confirmed_by"] == "client permission prompt" and b.sent("POST", "/approvals/a1/decide")


async def test_only_pending_approvals_can_be_decided(env):
    b = Backend()
    result, text = await call(server(b, "approvals"), "decide_approval",
                              {"approval_id": "gone", "decision": "approved"}, elicit=accept())
    assert result.isError and "not pending" in text and not b.requests[1:]


async def test_acknowledge_goes_to_the_notifier_as_the_operator(env):
    b = Backend()
    _, body = await call(server(b, "approvals"), "acknowledge_page", {"incident_id": "inc-1"}, elicit=accept())
    sent = b.sent("POST", "/pages/inc-1/ack")[0]
    assert sent.url.port == 7005 and json.loads(sent.content) == {"by": "123", "via": "akira-mcp"}
    assert body["notifier"]["message_updated"]


# ---- chaos: through the panel with the judge token, marked as ours ----------------------------------

async def test_create_chaos_previews_confirms_then_starts(env):
    b, ask = Backend(), accept()
    b.routes[("POST", "/chaos/experiments/preview")] = {
        "ok": True, "problems": [], "journeys": ["checkout"],
        "changes": [{"place": "configmap/flagd-config flags[paymentFailure].defaultVariant", "after": "50%"}]}
    b.routes[("POST", "/chaos/experiments")] = {"id": "exp-1", "status": "active", "origin": "akira-mcp"}
    _, body = await call(server(b, "chaos"), "create_chaos",
                         {"target": "payment", "capability": "flag:paymentFailure", "choice": "50%"}, elicit=ask)
    assert body["started"] and body["experiment"]["id"] == "exp-1"
    assert "paymentFailure" in ask.asked[0] and "checkout" in ask.asked[0]
    sent = b.sent("POST", "/chaos/experiments")[0]
    assert json.loads(sent.content)["origin"] == "akira-mcp" and sent.headers["Idempotency-Key"].startswith("akira-")
    assert sent.headers[auth.JUDGE_HEADER] == auth.token(auth.JUDGE_ENV) and auth.HEADER not in sent.headers


async def test_refused_preview_never_starts(env):
    b = Backend()
    b.routes[("POST", "/chaos/experiments/preview")] = {"ok": False, "problems": ["payment is not watched"]}
    result, text = await call(server(b, "chaos"), "create_chaos",
                              {"target": "payment", "capability": "scale_zero", "choice": "0"}, elicit=accept())
    assert result.isError and "not watched" in text and not b.sent("POST", "/chaos/experiments")


async def test_rejected_start_is_returned_not_raised(env):
    b = Backend()
    b.routes[("POST", "/chaos/experiments/preview")] = {"ok": True, "changes": []}
    b.routes[("POST", "/chaos/experiments")] = lambda r: httpx.Response(409, json={"id": "exp-2", "status": "rejected",
                                                                                    "error": "one at a time"})
    _, body = await call(server(b, "chaos"), "create_chaos",
                         {"target": "payment", "capability": "image", "choice": "payment:v2-bad"}, elicit=accept())
    assert body == {"experiment": {"id": "exp-2", "status": "rejected", "error": "one at a time"}, "started": False}


async def test_draw_is_blind_and_marked(env):
    b = Backend()
    b.routes[("POST", "/chaos/experiments/draw")] = {"id": "exp-3", "hidden": True}
    _, body = await call(server(b, "chaos"), "draw_random_chaos", {}, elicit=accept())
    assert body["experiment"]["hidden"]
    assert json.loads(b.sent("POST", "/chaos/experiments/draw")[0].content)["origin"] == "akira-mcp"


async def test_reset_returns_the_panel_answer(env):
    b = Backend()
    b.routes[("POST", "/chaos/reset")] = {"type": "reset", "restored": ["payment"], "healthy": True}
    _, body = await call(server(b, "chaos"), "reset_shop", {}, elicit=accept())
    assert body["reset"]["healthy"] is True


# ---- report and watch CLI ---------------------------------------------------------------------------

def test_report_times_each_stage_from_onset():
    detail = {
        "incident": {"id": "inc-1", "onset_at": 100.0, "culprit": "payment", "victims": ["checkout"], "state": "resolved"},
        "events": [rec(1, "incident_opened", ts=130.0), rec(2, "diagnosis_ready", ts=160.5, pattern="recent_change"),
                   rec(3, "action_executed", ts=200.0), rec(4, "incident_resolved", ts=290.0, card={"text": "FIXED"})],
        "events_total": 4, "approvals": [{"id": "a1", "state": "approved", "decided_by": "123",
                                          "action": {"tool": "rollback_deploy", "target": "payment"}}],
        "receipts": [{"id": 3, "receipt": {"tool": "rollback_deploy", "target": "payment", "outcome": "success",
                                           "prediction_held": True, "harm_clean": True}, "card": {"text": "FIXED"}}],
        "similar": []}
    r = report.incident_report(detail)
    assert r["outcome"] == "incident_resolved" and r["card"] == "FIXED" and r["notes"] == []
    assert r["seconds_from_onset"] == {"detect": 30.0, "diagnose": 60.5, "act": 100.0, "finish": 190.0}
    assert r["diagnosis"] == {"pattern": "recent_change"} and r["approvals"][0]["decided_by"] == "123"


def test_report_flags_a_fix_that_did_nothing():
    r = report.incident_report({"incident": {"id": "i", "opened_at": 10.0},
                                "events": [rec(1, "incident_resolved", ts=20.0)], "events_total": 1})
    assert r["actions"] == [] and "fixed nothing" in r["notes"][0]


def test_watch_prints_one_line_per_event_and_reports_outages(monkeypatch):
    lines = []
    events = [rec(5, "incident_opened", incident="inc-2", unhealthy=["cart"]), rec(6, "approval_decided",
                                                                                  decision="approved")]

    def stream(after):
        assert after == 4
        yield from events
        raise httpx.ReadTimeout("gone")

    monkeypatch.setattr(watch.shell, "stream_events", stream)
    assert watch.run("http://gw", after=4, incident="inc-1", out=lines.append, forever=False) == 1
    assert lines[0] == "watching http://gw/events after seq 4 for inc-1"
    assert lines[1].startswith("#6 ") and "approval approved" in lines[1]
    assert lines[2] == "event stream lost (ReadTimeout); retrying every 5 s" and len(lines) == 3
