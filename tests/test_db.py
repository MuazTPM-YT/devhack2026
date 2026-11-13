import tempfile
import unittest
from pathlib import Path

from schemas.db import connect


class DbTest(unittest.TestCase):
    def test_wal_and_tables(self):
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "sub" / "oncall.db")
            conn = connect(path)
            self.assertEqual(conn.execute("PRAGMA journal_mode").fetchone()[0], "wal")
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertEqual(tables, {"journal", "incidents", "ledger", "receipts", "approvals", "baselines"})
            conn.close()
            connect(path).close()  # second open must not fail on existing tables


if __name__ == "__main__":
    unittest.main()


# DBs made before the LLM "why" column must gain it on open, keeping their rows
def test_old_incidents_table_gains_why_column(tmp_path):
    import sqlite3
    path = str(tmp_path / "old.db")
    old = sqlite3.connect(path)
    old.execute("CREATE TABLE incidents (id TEXT PRIMARY KEY, opened_at REAL, onset_at REAL, culprit TEXT, "
                "victims_json TEXT, pattern TEXT, major INTEGER DEFAULT 0, tier TEXT, state TEXT, "
                "resolved_at REAL, severity_at_open REAL)")
    old.execute("INSERT INTO incidents (id) VALUES ('inc-old')")
    old.commit()
    old.close()
    conn = connect(path)
    assert conn.execute("SELECT id, llm_why FROM incidents").fetchone()[:] == ("inc-old", None)
    connect(path).close()  # second open must not try to add it again
