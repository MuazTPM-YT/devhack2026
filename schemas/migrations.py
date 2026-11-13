# versioned, additive schema upgrades for orchestration tables. Never run by connect(): a service in
# shadow/coordinated mode calls require() and fails loud; an operator runs this module (with --backup).
import argparse
import sqlite3
import time
from pathlib import Path

from schemas.db import connect

# v1: workspace, episodes, evidence, tasks, findings, model calls, outbox (handoff §6.1)
V1 = """
CREATE TABLE orchestration_workspaces (
  incident_id TEXT PRIMARY KEY REFERENCES incidents(id),
  phase TEXT NOT NULL,
  revision INTEGER NOT NULL DEFAULT 0,
  scope_revision INTEGER NOT NULL DEFAULT 0,
  plan_revision INTEGER NOT NULL DEFAULT 0,
  created_at REAL NOT NULL,
  deadline_at REAL,
  owner TEXT,
  lease_epoch INTEGER NOT NULL DEFAULT 0,
  requests_limit INTEGER NOT NULL,
  tool_calls_limit INTEGER NOT NULL,
  tool_calls_used INTEGER NOT NULL DEFAULT 0,
  specialists_limit INTEGER NOT NULL,
  specialists_started INTEGER NOT NULL DEFAULT 0,
  last_error TEXT
);
CREATE INDEX workspaces_by_phase ON orchestration_workspaces(phase);
CREATE TABLE signal_episodes (
  episode_id TEXT PRIMARY KEY,
  cluster TEXT NOT NULL, namespace TEXT NOT NULL, service TEXT NOT NULL, symptom TEXT NOT NULL,
  first_breach_at REAL, sustained_at REAL NOT NULL, last_observed_at REAL NOT NULL, recovered_at REAL,
  source_revision INTEGER NOT NULL,
  evidence_json TEXT NOT NULL DEFAULT '[]',
  suppressed INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX episodes_open ON signal_episodes(service, recovered_at);
CREATE TABLE signal_deliveries (
  delivery_id TEXT PRIMARY KEY, received_at REAL NOT NULL, ack_json TEXT NOT NULL
);
CREATE TABLE incident_memberships (
  incident_id TEXT NOT NULL REFERENCES incidents(id),
  episode_id TEXT NOT NULL REFERENCES signal_episodes(episode_id),
  service TEXT NOT NULL, reason TEXT NOT NULL,
  evidence_json TEXT NOT NULL DEFAULT '[]',
  added_revision INTEGER NOT NULL,
  closed INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (incident_id, episode_id)
);
CREATE UNIQUE INDEX one_owner_per_open_episode ON incident_memberships(episode_id) WHERE closed = 0;
CREATE TABLE incident_links (
  incident_a TEXT NOT NULL REFERENCES incidents(id),
  incident_b TEXT NOT NULL REFERENCES incidents(id),
  relation TEXT NOT NULL, reason TEXT NOT NULL,
  supporting_json TEXT NOT NULL DEFAULT '[]', contradicting_json TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'open', revision INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (incident_a, incident_b, relation),
  CHECK (incident_a < incident_b)
);
CREATE TABLE environment_snapshots (
  snapshot_id TEXT PRIMARY KEY,
  cluster TEXT NOT NULL, namespace TEXT NOT NULL, version_hash TEXT NOT NULL, observed_at REAL NOT NULL,
  edges_json TEXT NOT NULL, edges_source TEXT NOT NULL, edges_complete INTEGER NOT NULL,
  versions_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE evidence_snapshots (
  snapshot_id TEXT PRIMARY KEY,
  query_key TEXT NOT NULL, source TEXT NOT NULL,
  source_observed_at REAL, fetched_at REAL NOT NULL, valid_until REAL NOT NULL,
  payload_json TEXT NOT NULL, payload_hash TEXT NOT NULL,
  environment_snapshot_id TEXT REFERENCES environment_snapshots(snapshot_id)
);
CREATE INDEX evidence_by_key ON evidence_snapshots(query_key, valid_until);
CREATE TABLE investigation_tasks (
  task_id TEXT PRIMARY KEY,
  incident_id TEXT NOT NULL REFERENCES incidents(id),
  question_id TEXT NOT NULL, type TEXT NOT NULL, fingerprint TEXT NOT NULL,
  scope_revision INTEGER NOT NULL, plan_revision INTEGER NOT NULL,
  input_json TEXT NOT NULL, allowed_tools_json TEXT NOT NULL,
  state TEXT NOT NULL, deadline_at REAL NOT NULL,
  requests_allocated INTEGER NOT NULL, tool_calls_allocated INTEGER NOT NULL,
  owner TEXT, lease_token INTEGER NOT NULL DEFAULT 0, lease_expires_at REAL,
  attempt INTEGER NOT NULL DEFAULT 0,
  finding_id TEXT, error TEXT,
  created_at REAL NOT NULL, updated_at REAL NOT NULL,
  UNIQUE (incident_id, fingerprint, scope_revision)
);
CREATE INDEX runnable_tasks ON investigation_tasks(state, deadline_at, lease_expires_at);
CREATE TABLE task_evidence (
  run_id TEXT NOT NULL, incident_id TEXT NOT NULL REFERENCES incidents(id),
  evidence_id TEXT NOT NULL, snapshot_id TEXT, delivered_at REAL NOT NULL,
  PRIMARY KEY (run_id, evidence_id)
);
CREATE TABLE investigation_findings (
  finding_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL REFERENCES investigation_tasks(task_id),
  incident_id TEXT NOT NULL REFERENCES incidents(id),
  question_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
  body_json TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE INDEX findings_by_fingerprint ON investigation_findings(fingerprint);
CREATE TABLE model_calls (
  call_id TEXT PRIMARY KEY,
  incident_id TEXT NOT NULL REFERENCES incidents(id),
  task_id TEXT, run_id TEXT NOT NULL, role TEXT NOT NULL,
  state TEXT NOT NULL, reserved_at REAL NOT NULL, finished_at REAL,
  reserved_tokens INTEGER NOT NULL DEFAULT 0, input_tokens INTEGER, output_tokens INTEGER, error TEXT
);
CREATE INDEX calls_by_incident ON model_calls(incident_id, state);
CREATE TABLE delegation_decisions (
  id INTEGER PRIMARY KEY,
  incident_id TEXT NOT NULL REFERENCES incidents(id),
  status TEXT NOT NULL, reason TEXT, question_id TEXT, explanation TEXT NOT NULL, ts REAL NOT NULL
);
CREATE TABLE event_outbox (
  event_id TEXT PRIMARY KEY,
  destination TEXT NOT NULL, event_type TEXT NOT NULL, incident_id TEXT,
  body_json TEXT NOT NULL, incident_revision INTEGER,
  created_at REAL NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, next_attempt_at REAL NOT NULL,
  delivered_at REAL, last_error TEXT
);
CREATE INDEX outbox_due ON event_outbox(destination, delivered_at, next_attempt_at);
CREATE TABLE coordinator_leases (
  name TEXT PRIMARY KEY, owner TEXT NOT NULL, epoch INTEGER NOT NULL, expires_at REAL NOT NULL
);
CREATE TABLE shadow_decisions (
  id INTEGER PRIMARY KEY, delivery_id TEXT NOT NULL, decided_at REAL NOT NULL,
  legacy_incident_id TEXT, decision_json TEXT NOT NULL
);
"""

MIGRATIONS: list[tuple[int, str]] = [(1, V1)]
LATEST = MIGRATIONS[-1][0]


def version(conn: sqlite3.Connection) -> int:
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'").fetchone():
        return 0
    return conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()[0]


# apply every pending version, each in its own immediate transaction; rerun is a no-op
def migrate(conn: sqlite3.Connection, clock=time.time) -> list[int]:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at REAL NOT NULL)")
    conn.commit()
    applied = []
    for number, sql in MIGRATIONS:
        conn.execute("BEGIN IMMEDIATE")
        try:
            if version(conn) >= number:
                conn.rollback()
                continue
            # executescript would commit our transaction first; run statement by statement instead
            for statement in (s.strip() for s in sql.split(";")):
                if statement:
                    conn.execute(statement)
            conn.execute("INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)", (number, clock()))
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        applied.append(number)
    return applied


def require(conn: sqlite3.Connection, needed: int = LATEST) -> None:
    have = version(conn)
    if have < needed:
        raise RuntimeError(f"orchestration schema version {have} < {needed}: back up the database, then run "
                           "uv run python -m schemas.migrations data/oncall.db --backup")


def backup(path: str, clock=time.time) -> Path:
    target = Path(f"{path}.bak-{int(clock())}")
    src, dst = sqlite3.connect(path), sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return target


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="apply orchestration schema migrations")
    parser.add_argument("db")
    parser.add_argument("--backup", action="store_true", help="copy the database first (sqlite backup API)")
    args = parser.parse_args(argv)
    if not Path(args.db).exists():
        raise SystemExit(f"no database at {args.db}")
    if args.backup:
        print(f"backup: {backup(args.db)}")
    conn = connect(args.db)
    try:
        applied = migrate(conn)
        print(f"applied {applied or 'nothing'}; schema version {version(conn)}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
