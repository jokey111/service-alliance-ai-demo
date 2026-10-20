"""Executable reimbursement status SOP using a real MCP client session."""
from __future__ import annotations

import json
import os
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


MCP_URL = os.getenv("MCP_URL", "http://127.0.0.1:8011/mcp")
SKILL_VERSION = "1.0.0"


def unpack(result: Any) -> dict:
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    for block in result.content:
        content = getattr(block, "text", None)
        if content:
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                continue
    return {"status": "invalid_tool_result"}


async def execute(actor_id: str, reimbursement_id: str | None = None) -> tuple[dict, list[dict]]:
    steps: list[dict] = [{"kind": "skill", "name": "reimbursement-status", "version": SKILL_VERSION}]
    async with streamable_http_client(MCP_URL) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            catalog = await session.list_tools()
            names = [tool.name for tool in catalog.tools]
            steps.append({"kind": "mcp_list_tools", "server": "12345-synthetic-business", "tools": names})
            if "list_my_reimbursements" not in names:
                return {"status": "tool_unavailable"}, steps
            list_result = await session.call_tool("list_my_reimbursements", {"actor_id": actor_id})
            listing = unpack(list_result)
            steps.append({"kind": "mcp_call", "tool": "list_my_reimbursements", "status": listing.get("status"), "item_count": len(listing.get("items", []))})
            if listing.get("status") != "ok":
                return listing, steps
            items = listing.get("items", [])
            if not items:
                return {"status": "no_records", "items": []}, steps
            target = reimbursement_id
            if target is None:
                if len(items) > 1:
                    return {"status": "selection_required", "items": items}, steps
                target = items[0]["id"]
            if target not in {item["id"] for item in items}:
                return {"status": "forbidden_or_missing"}, steps
            detail_result = await session.call_tool("get_reimbursement_detail", {"actor_id": actor_id, "reimbursement_id": target})
            detail = unpack(detail_result)
            steps.append({"kind": "mcp_call", "tool": "get_reimbursement_detail", "status": detail.get("status"), "record_id": target})
            return detail, steps
