import sqlite3

import pytest

from schemas import migrations
from schemas.db import connect


def tables(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_connect_never_migrates(tmp_path):
    conn = connect(str(tmp_path / "x.db"))
    assert migrations.version(conn) == 0
    assert "orchestration_workspaces" not in tables(conn)


def test_empty_db_upgrades_and_rerun_is_noop(tmp_path):
    conn = connect(str(tmp_path / "x.db"))
    assert migrations.migrate(conn, clock=lambda: 5.0) == [1, 2]
    assert migrations.version(conn) == migrations.LATEST
    assert {"orchestration_workspaces", "signal_episodes", "investigation_tasks", "event_outbox",
            "model_calls", "task_evidence", "coordinator_leases"} <= tables(conn)
    assert migrations.migrate(conn) == []
    migrations.require(conn)


def test_legacy_db_keeps_rows_and_reads(tmp_path):
    path = str(tmp_path / "old.db")
    old = connect(path)
    old.execute("INSERT INTO incidents (id, opened_at, onset_at, state) VALUES ('inc-1', 1, 1, 'resolved')")
    old.execute("INSERT INTO receipts (incident_id, tool, target, outcome) VALUES ('inc-1', 'scale', 'cart', 'success')")
    old.commit()
    old.close()
    conn = connect(path)
    migrations.migrate(conn)
    assert conn.execute("SELECT state FROM incidents WHERE id='inc-1'").fetchone()[0] == "resolved"
    assert conn.execute("SELECT outcome FROM receipts").fetchone()[0] == "success"
    # legacy tables have no foreign keys: deleting an old incident still works with FKs on
    conn.execute("DELETE FROM incidents WHERE id='inc-1'")


def test_foreign_keys_enforced_on_new_tables(tmp_path):
    conn = connect(str(tmp_path / "x.db"))
    migrations.migrate(conn)
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO orchestration_workspaces (incident_id, phase, created_at, requests_limit, "
                     "tool_calls_limit, specialists_limit) VALUES ('no-such-incident', 'queued', 1, 9, 24, 2)")


def test_require_fails_loud_when_behind(tmp_path):
    conn = connect(str(tmp_path / "x.db"))
    with pytest.raises(RuntimeError, match="schemas.migrations"):
        migrations.require(conn)


def test_failed_migration_rolls_back(tmp_path, monkeypatch):
    conn = connect(str(tmp_path / "x.db"))
    monkeypatch.setattr(migrations, "MIGRATIONS", [(1, migrations.V1 + "; CREATE TABLE broken (")])
    with pytest.raises(sqlite3.OperationalError):
        migrations.migrate(conn)
    assert migrations.version(conn) == 0
    assert "orchestration_workspaces" not in tables(conn)


def test_cli_backs_up_first(tmp_path, capsys):
    path = tmp_path / "live.db"
    seed = connect(str(path))
    seed.execute("INSERT INTO incidents (id, opened_at, onset_at, state) VALUES ('inc-9', 1, 1, 'open')")
    seed.commit()
    seed.close()
    migrations.main([str(path), "--backup"])
    backups = list(tmp_path.glob("live.db.bak-*"))
    assert len(backups) == 1
    copy = sqlite3.connect(backups[0])
    assert copy.execute("SELECT id FROM incidents").fetchone()[0] == "inc-9"
    assert "orchestration_workspaces" not in {r[0] for r in copy.execute("SELECT name FROM sqlite_master")}
    assert "schema version 2" in capsys.readouterr().out


def test_cli_refuses_missing_db(tmp_path):
    with pytest.raises(SystemExit, match="no database"):
        migrations.main([str(tmp_path / "nope.db")])
