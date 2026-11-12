import json
from collections.abc import AsyncIterator
from typing import Any

import httpx


async def read_events(client: httpx.AsyncClient, base_url: str, after: int = 0) -> AsyncIterator[dict[str, Any]]:
    async with client.stream("GET", f"{base_url}/events", headers={"Last-Event-ID": str(after)},
                             timeout=httpx.Timeout(30, read=45)) as response:
        response.raise_for_status()
        data: list[str] = []
        async for line in response.aiter_lines():
            if line.startswith("data:"):
                data.append(line[5:].lstrip())
            elif not line and data:
                yield json.loads("\n".join(data))
                data.clear()
