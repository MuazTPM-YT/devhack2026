import asyncio
import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Any

from brain.redact import redact_value


def canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def verify(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    previous = ""
    if not path.exists():
        return records
    for expected, line in enumerate(path.read_text().splitlines(), 1):
        try:
            record = json.loads(line)
            digest = record.pop("hash")
            if record["seq"] != expected or record["prev_hash"] != previous:
                raise ValueError
            if hashlib.sha256(canonical(record)).hexdigest() != digest:
                raise ValueError
            record["hash"] = digest
        except (ValueError, KeyError, TypeError):
            raise ValueError(f"Audit chain broken at seq {expected}") from None
        records.append(record)
        previous = digest
    return records


class AuditLog:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self.records = verify(path)

    def append(self, event: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            body = {"seq": len(self.records) + 1, "ts": time.time(),
                    "event": redact_value(event),
                    "prev_hash": self.records[-1]["hash"] if self.records else ""}
            body["hash"] = hashlib.sha256(canonical(body)).hexdigest()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a") as stream:
                stream.write(json.dumps(body, sort_keys=True) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            self.records.append(body)
            return body


class EventBus:
    def __init__(self, audit: AuditLog, queue_size: int = 256):
        self.audit, self.queue_size = audit, queue_size
        self.lock = asyncio.Lock()
        self.subscribers: set[asyncio.Queue] = set()

    async def publish(self, event: dict[str, Any]) -> dict[str, Any]:
        async with self.lock:
            record = self.audit.append(event)
            for queue in tuple(self.subscribers):
                if queue.full():
                    self.subscribers.discard(queue)
                    while not queue.empty():
                        queue.get_nowait()
                    queue.put_nowait(None)
                else:
                    queue.put_nowait(record)
            return record

    async def subscribe(self, after: int):
        queue: asyncio.Queue = asyncio.Queue(self.queue_size)
        async with self.lock:
            replay = [r for r in self.audit.records if r["seq"] > after]
            self.subscribers.add(queue)
        try:
            for record in replay:
                yield record
            while True:
                try:
                    record = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    yield None
                    continue
                if record is None:
                    return
                yield record
        finally:
            self.subscribers.discard(queue)
