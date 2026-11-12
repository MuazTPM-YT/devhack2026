import pytest

from schemas.models import ActionRequest, Evidence, EvidenceBundle, Incident


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
