# brain -> gateway over MCP (IMPLEMENTATION.md §6.4.1): the brain can only ask; the gateway decides.
import contextlib
import json
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client

from schemas import auth
from schemas.models import ActionRequest, GatewayDecision


async def call_tool(gateway_url: str, action: ActionRequest, http: httpx.AsyncClient | None = None) -> GatewayDecision:
    args: dict[str, Any] = action.model_dump(mode="json", exclude={"tool"})
    async with contextlib.AsyncExitStack() as stack:
        client = http or await stack.enter_async_context(create_mcp_http_client(headers=auth.headers()))
        read, write, _ = await stack.enter_async_context(streamable_http_client(f"{gateway_url}/mcp",
                                                                                http_client=client))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        result = await session.call_tool(action.tool, args)
    if result.isError:
        text = " ".join(getattr(c, "text", "") for c in result.content)
        return GatewayDecision(decision="refused", failed_step="schema", reason=text[:300] or "tool error")
    data = result.structuredContent
    if data is None:
        data = json.loads(result.content[0].text)  # type: ignore[union-attr]
    return GatewayDecision.model_validate(data.get("result", data))
