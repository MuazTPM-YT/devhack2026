# brain -> gateway over MCP (IMPLEMENTATION.md §6.4.1): the brain can only ask; the gateway decides.
import json
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from schemas.models import ActionRequest, GatewayDecision


async def call_tool(gateway_url: str, action: ActionRequest, http: httpx.AsyncClient | None = None) -> GatewayDecision:
    args: dict[str, Any] = action.model_dump(mode="json", exclude={"tool"})
    async with streamable_http_client(f"{gateway_url}/mcp", http_client=http) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(action.tool, args)
    if result.isError:
        text = " ".join(getattr(c, "text", "") for c in result.content)
        return GatewayDecision(decision="refused", failed_step="schema", reason=text[:300] or "tool error")
    data = result.structuredContent
    if data is None:
        data = json.loads(result.content[0].text)  # type: ignore[union-attr]
    return GatewayDecision.model_validate(data.get("result", data))
