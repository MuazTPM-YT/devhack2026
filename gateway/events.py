import json
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from gateway.audit import EventBus
from schemas.models import Event


def create_events_router(bus: EventBus) -> APIRouter:
    router = APIRouter()

    @router.post("/events/publish")
    async def publish(event: Event):
        return await bus.publish(event.model_dump(mode="json"))

    @router.get("/events")
    async def events(request: Request, last_event_id: Annotated[str | None, Header()] = None):
        try:
            after = int(last_event_id or "0")
            if after < 0 or after > len(bus.audit.records):
                raise ValueError
        except ValueError:
            raise HTTPException(400, "Invalid Last-Event-ID") from None

        async def stream():
            async for record in bus.subscribe(after):
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
