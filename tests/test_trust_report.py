import pytest

from bench.trust_report import summarize_ledger
from gateway import trust
from schemas.db import connect


def test_ledger_report_reads_actual_separate_counts_and_failure_reset(tmp_path):
    path = tmp_path / "ledger with spaces.db"
    db = connect(str(path))
    try:
        key = ("recent_change", "rollback_deploy", "payment")
        for _ in range(28):
            trust.record(db, *key, "rehearsal", True, 1)
        assert not summarize_ledger(path)["rows"][0]["statistical_threshold_met"]
        trust.record(db, *key, "real", True, 2)
        report = summarize_ledger(path)
        row = report["rows"][0]
        assert row["statistical_threshold_met"]
        assert row["rehearsal"] == (28, 0)
        assert row["real"] == (1, 0)
        assert row["lower_bound"] == 0.9019
        assert report["authorization_evaluated"] is False
        trust.record(db, *key, "real", False, 3)
        assert summarize_ledger(path)["rows"][0]["lower_bound"] == 0
    finally:
        db.close()
    before = path.read_bytes()
    summarize_ledger(path)
    assert path.read_bytes() == before


def test_missing_database_is_not_created(tmp_path):
    path = tmp_path / "absent.db"
    with pytest.raises(ValueError, match="not found"):
        summarize_ledger(path)
    assert not path.exists()


@pytest.mark.parametrize("confidence,bar", [(0, 0.9), (1, 0.9), (0.95, -1), (0.95, 1)])
def test_invalid_thresholds_fail_before_database_access(tmp_path, confidence, bar):
    with pytest.raises(ValueError, match="between 0 and 1"):
        summarize_ledger(tmp_path / "absent.db", confidence, bar)
