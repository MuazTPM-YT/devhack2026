import fcntl
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from gateway.audit import AuditLog, EventBus
from schemas.models import Event


_active_bus: EventBus | None = None
AUDIT_PATH = "data/audit.jsonl"  # tests point this at a temp dir (tests/conftest.py)


def active_bus() -> EventBus:
    if _active_bus is None:
        raise RuntimeError("Event router not started; enter the gateway lifespan first")
    return _active_bus


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _active_bus
    if _active_bus is not None:
        raise RuntimeError("Event router already active; use one gateway application per worker")
    bus = getattr(app.state, "event_bus", None)
    lock = None
    if bus is None:
        path = Path(getattr(app.state, "audit_path", AUDIT_PATH))
        lock = writer_lock(path)
        bus = EventBus(AuditLog(path))
    _active_bus = bus
    app.state.event_bus = bus
    try:
        yield
    finally:
        _active_bus = None
        if lock is not None:
            lock.close()  # closing the file drops the flock


# one writer per audit log, across processes. Live 2026-11-14: an old gateway kept running after a restart, both
# appended (two seq 95, chain broken) and the old one expired an approval nobody saw. The kernel drops the lock
# when the holder dies, kill -9 included
def writer_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(f"{path}.lock", "a")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise RuntimeError(f"another gateway is writing {path}; stop it first (scripts/demo.sh down)") from None
    return handle


# a Discord-bound event names its sender (payload "source"); the bus lives in the gateway, the only process
# that knows rehearsal mode, so it adds the mode for every sender. Recorded in the audit chain too
def stamp(event: dict[str, Any]) -> dict[str, Any]:
    src = event.get("payload", {}).get("source")
    if isinstance(src, dict):
        src["mode"] = "rehearsal" if os.environ.get("ONCALL_REHEARSAL") == "1" else "live"
    return event


async def publish(event: Event | dict[str, Any]) -> dict[str, Any]:
    validated = Event.model_validate(event)
    return await active_bus().publish(stamp(validated.model_dump(mode="json")))


def create_events_router(bus: EventBus | None = None) -> APIRouter:
    router = APIRouter(lifespan=lifespan if bus is None else None)

    def selected_bus() -> EventBus:
        return bus if bus is not None else active_bus()

    @router.post("/events/publish")
    async def publish_event(event: Event):
        return await selected_bus().publish(stamp(event.model_dump(mode="json")))

    @router.get("/events")
    async def events(request: Request, last_event_id: Annotated[str | None, Header()] = None):
        try:
            after = int(last_event_id or "0")
            if after < 0 or after > len(selected_bus().audit.records):
                raise ValueError
        except ValueError:
            raise HTTPException(400, "Invalid Last-Event-ID") from None

        async def stream():
            async for record in selected_bus().subscribe(after):
                if await request.is_disconnected():
                    break
                if record is None:
                    yield ": heartbeat\n\n"
                else:
                    yield (f"id: {record['seq']}\nevent: {record['event']['type']}\n"
                           f"data: {json.dumps(record)}\n\n")

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    return router


router = create_events_router()
