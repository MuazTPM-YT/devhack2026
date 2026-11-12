from typing import get_args

import pytest

from gateway import policy, trust
from schemas import config
from schemas.db import connect
from schemas.models import Tool

POLICY = config.load("policy")
SERVICES = config.load("services")["services"]
FREE = {"incident": 0, "hour": 0, "in_flight": 0}


def act(tool="rollback_deploy", target="payment"):
    return {"tool": tool, "target": target}


@pytest.mark.parametrize("action,outcome,reason", [
    (act(tool="delete_namespace"), "refused", "not allowed"),
    (act(target="no-such-svc"), "refused", "unknown service"),
    (act(target="kafka"), "escalated", "protected"),
    (act(target="valkey-cart"), "escalated", "protected"),
])
def test_tool_and_target_gates(action, outcome, reason):
    passed, got, why = policy.check(action, SERVICES, POLICY, FREE)
    assert (passed, got) == (False, outcome) and reason in why


def test_non_actable_service_refused():
    services = {**SERVICES, "quote": {"kind": "stateless", "critical": False}}
    assert policy.check(act(target="quote"), services, POLICY, FREE)[:2] == (False, "refused")


# protected wins over actable: a mis-edited services.yaml must still escalate
def test_protected_beats_actable_flag():
    services = {**SERVICES, "kafka": {"kind": "stateful", "protected": True, "actable": True}}
    assert policy.check(act(target="kafka"), services, POLICY, FREE)[:2] == (False, "escalated")


@pytest.mark.parametrize("used,ok,outcome", [
    ({"incident": 2, "hour": 2, "in_flight": 0}, True, ""),
    ({"incident": 3, "hour": 0, "in_flight": 0}, False, "escalated"),
    ({"incident": 0, "hour": 3, "in_flight": 0}, False, "escalated"),
    ({"incident": 0, "hour": 0, "in_flight": 1}, False, "refused"),
    ({"incident": 3, "hour": 0, "in_flight": 1}, False, "escalated"),
])
def test_budget_boundaries(used, ok, outcome):
    assert policy.check(act(), SERVICES, POLICY, used)[:2] == (ok, outcome)


def test_every_actable_service_and_tool_passes_when_budget_free():
    for name, svc in SERVICES.items():
        if svc.get("actable") and not svc.get("protected"):
            for tool in POLICY["tools"]:
                assert policy.check(act(tool, name), SERVICES, POLICY, FREE)[0], (tool, name)


def test_policy_tools_match_schema_tools():
    assert set(POLICY["tools"]) == set(get_args(Tool))


def test_config_invariants():
    for name, svc in SERVICES.items():
        assert not (svc.get("protected") and svc.get("actable")), name
    assert POLICY["budgets"]["max_in_flight"] == 1
    assert POLICY["tools"]["raise_limit"]["auto_eligible"] is False
    assert POLICY["tools"]["scale"]["min"] >= 1 and POLICY["tools"]["scale"]["max"] <= 3
    assert POLICY["approval"]["approvers_env"] == "ONCALL_APPROVER_IDS"


@pytest.mark.parametrize("tool,kind,auto", [
    ("rollback_deploy", "stateless", True),
    ("restart_service", "stateless", True),
    ("restart_service", "stateful", False),
    ("raise_limit", "stateless", False),
])
def test_tool_auto_eligibility(tool, kind, auto):
    assert trust.eligible(POLICY["tools"][tool], kind) is auto


def test_usage_counts_incident_hour_and_in_flight(tmp_path):
    conn = connect(str(tmp_path / "db.sqlite"))
    rows = [("i1", 1000, "success"), ("i1", 4000, "pending"), ("i2", 4500, "undone"), ("i3", 100, "pending")]
    conn.executemany("INSERT INTO receipts (incident_id, ts, outcome) VALUES (?, ?, ?)", rows)
    assert policy.usage(conn, "i1", now=5000) == {"incident": 2, "hour": 2, "in_flight": 2}
    assert policy.usage(conn, "none", now=10_000) == {"incident": 0, "hour": 0, "in_flight": 2}
