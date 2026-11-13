import sqlite3
from pathlib import Path

DEFAULT_PATH = "data/oncall.db"

# tables from IMPLEMENTATION.md §5.1; IF NOT EXISTS so every process can call connect()
SCHEMA = """
CREATE TABLE IF NOT EXISTS journal (
  id INTEGER PRIMARY KEY, ts REAL NOT NULL,
  kind TEXT NOT NULL,
  object TEXT NOT NULL,
  field_manager TEXT,
  resource_version TEXT,
  diff_json TEXT NOT NULL,
  inverse_json TEXT NOT NULL,
  by_agent INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS incidents (
  id TEXT PRIMARY KEY, opened_at REAL, onset_at REAL,
  culprit TEXT, victims_json TEXT, pattern TEXT,
  major INTEGER DEFAULT 0, tier TEXT, state TEXT,
  resolved_at REAL, severity_at_open REAL, llm_why TEXT
);
CREATE TABLE IF NOT EXISTS ledger (
  pattern TEXT, action TEXT, target TEXT, source TEXT,
  successes INTEGER DEFAULT 0, failures INTEGER DEFAULT 0, last_failure_at REAL,
  PRIMARY KEY (pattern, action, target, source)
);
CREATE TABLE IF NOT EXISTS receipts (
  id INTEGER PRIMARY KEY, incident_id TEXT, ts REAL, tool TEXT, target TEXT,
  diff_json TEXT, pods_touched_json TEXT, inverse_json TEXT,
  blast_json TEXT, forecast_json TEXT,
  hash_before TEXT, hash_after TEXT, checklist_json TEXT, trust_json TEXT,
  outcome TEXT
);
CREATE TABLE IF NOT EXISTS approvals (
  id TEXT PRIMARY KEY, incident_id TEXT, action_json TEXT,
  created_at REAL, expires_at REAL, state TEXT, decided_by TEXT
);
CREATE TABLE IF NOT EXISTS baselines (
  service TEXT PRIMARY KEY, err_ratio REAL, p95_ms REAL, updated_at REAL
);
"""


# open db in WAL mode so observer, brain, gateway can share it
# shared=True lets watch threads use one connection; caller must hold a lock around writes
def connect(path: str = DEFAULT_PATH, shared: bool = False) -> sqlite3.Connection:
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5, check_same_thread=not shared)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    # DBs from before the LLM "why" column: CREATE IF NOT EXISTS never adds columns
    if "llm_why" not in {r[1] for r in conn.execute("PRAGMA table_info(incidents)")}:
        conn.execute("ALTER TABLE incidents ADD COLUMN llm_why TEXT")
    return conn
