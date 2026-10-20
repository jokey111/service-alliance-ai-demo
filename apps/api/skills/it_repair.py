"""Executable IT repair submission skill. Confirmation is enforced by API before entry."""
from __future__ import annotations

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from apps.api.skills.reimbursement_status import MCP_URL, unpack


async def execute(actor_id: str, device: str, issue: str, location: str, key: str) -> tuple[dict, list[dict]]:
    steps = [{"kind": "skill", "name": "it-repair-request", "version": "1.0.0"}]
    async with streamable_http_client(MCP_URL) as (reader, writer, _):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            names = [tool.name for tool in (await session.list_tools()).tools]
            steps.append({"kind": "mcp_list_tools", "server": "12345-synthetic-business", "tools": names})
            if "create_it_repair_ticket" not in names:
                return {"status": "tool_unavailable"}, steps
            result = unpack(await session.call_tool("create_it_repair_ticket", {
                "actor_id": actor_id, "device": device, "issue": issue, "location": location,
                "idempotency_key": key,
            }))
            steps.append({"kind": "mcp_call", "tool": "create_it_repair_ticket", "status": result.get("status"),
                          "record_id": result.get("ticket_id"), "duplicate": result.get("duplicate")})
            return result, steps
