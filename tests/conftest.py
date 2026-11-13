import os

import pytest

# processes share ONCALL_API_TOKEN; tests use a fixed fake one
os.environ.setdefault("ONCALL_API_TOKEN", "test-token-0123456789")
# the judge plane has its own secret (chaos :7004)
os.environ.setdefault("CHAOS_JUDGE_TOKEN", "judge-token-0123456789")

from schemas.models import ActionRequest, Evidence, EvidenceBundle, Incident


# a test gateway app must never append to the live data/audit.jsonl (it did, until the writer lock refused it)
@pytest.fixture(autouse=True)
def private_audit_log(monkeypatch, tmp_path):
    monkeypatch.setattr("gateway.events.AUDIT_PATH", str(tmp_path / "audit.jsonl"))


# agent services drop the judge token when they start; give every test a fresh one
@pytest.fixture(autouse=True)
def judge_token(monkeypatch):
    monkeypatch.setenv("CHAOS_JUDGE_TOKEN", "judge-token-0123456789")


@pytest.fixture
def bundle():
    return EvidenceBundle(
        incident=Incident(id="inc-1", opened_at=10, onset_at=9, unhealthy=["payment"],
                          culprit="payment", severity=3),
        changes=[Evidence(id="journal:41", kind="journal", summary="image changed", ts=8)],
        metrics=[Evidence(id="query:err_ratio:service=payment", kind="query",
                          summary="payment errors", value=0.4, ts=10)],
    )


@pytest.fixture
def action():
    return ActionRequest(incident_id="inc-1", tool="rollback_deploy", target="payment",
                         pattern="recent_change", evidence_ids=["journal:41"], journal_entry=41)
