import json
import os
import threading
import time
from pathlib import Path
from typing import Any

_lock = threading.Lock()


# append one fault record, fsync so the bench never reads a half line
def record(path: Path, kind: str, target: str | None = None, **extra: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {"ts": time.time(), "type": kind}
    if target is not None:
        entry["target"] = target
    entry.update(extra)
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as stream:
            stream.write(json.dumps(entry, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    return entry


def read_all(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
