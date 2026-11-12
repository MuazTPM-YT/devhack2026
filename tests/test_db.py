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
