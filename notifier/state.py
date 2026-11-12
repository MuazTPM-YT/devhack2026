import json
import sqlite3
from pathlib import Path
from typing import Any

from brain.redact import redact_value


class NotifierState:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS notifier_state (key TEXT PRIMARY KEY, body TEXT)")

    def connect(self):
        return sqlite3.connect(self.path)

    def get(self, key: str, default: Any = None) -> Any:
        with self.connect() as db:
            row = db.execute("SELECT body FROM notifier_state WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set(self, key: str, value: Any):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO notifier_state VALUES (?, ?)", (key, json.dumps(redact_value(value))))

    def approvals(self) -> dict[str, Any]:
        with self.connect() as db:
            rows = db.execute("SELECT key, body FROM notifier_state WHERE key LIKE 'approval:%'").fetchall()
        return {key.removeprefix("approval:"): json.loads(body) for key, body in rows}
