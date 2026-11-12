# the six tools over MCP (IMPLEMENTATION.md §6.4.1). Each is a thin call into the checklist.
from collections.abc import Callable
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

TOOLS = ["rollback_deploy", "revert_config", "restart_service", "scale", "raise_limit", "enable_degraded_mode"]


# target is a Literal of actable services, so a wrong target fails MCP schema validation before the checklist
def build_mcp(submit: Callable[[dict], Any], actable: list[str]) -> FastMCP:
    mcp = FastMCP("oncall-gateway", stateless_http=True, json_response=True, streamable_http_path="/mcp")
    ActableService = Literal[tuple(actable)]  # type: ignore[valid-type]

    def make(tool: str):
        async def call(incident_id: str, target: ActableService, pattern: str, evidence_ids: list[str],  # type: ignore[valid-type]
                       prediction: dict | None = None, journal_entry: int | None = None,
                       params: dict | None = None) -> dict:
            decision = await submit({"incident_id": incident_id, "tool": tool, "target": target, "pattern": pattern,
                                     "evidence_ids": evidence_ids, "prediction": prediction,
                                     "journal_entry": journal_entry, "params": params or {}})
            return decision.model_dump(mode="json")

        call.__name__ = tool
        return call

    for tool in TOOLS:
        mcp.tool(name=tool, description=f"{tool.replace('_', ' ')} through the safety checklist")(make(tool))
    return mcp
