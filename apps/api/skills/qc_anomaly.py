"""Read-only QC analysis agent: plan, query metrics, sample evidence, draft limits."""
from __future__ import annotations

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from apps.api.skills.reimbursement_status import MCP_URL, unpack


async def execute(category: str) -> tuple[dict, list[dict]]:
    steps = [{"kind": "plan", "agent": "qc-anomaly-report", "category": category,
              "actions": ["query_qc_metrics", "get_qc_evidence"], "max_tool_calls": 2}]
    async with streamable_http_client(MCP_URL) as (reader, writer, _):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            names = {tool.name for tool in (await session.list_tools()).tools}
            steps.append({"kind": "mcp_list_tools", "server": "12345-synthetic-business", "tools": sorted(names)})
            if not {"query_qc_metrics", "get_qc_evidence"}.issubset(names):
                return {"status": "tool_unavailable"}, steps
            metrics = unpack(await session.call_tool("query_qc_metrics", {"category": category}))
            steps.append({"kind": "mcp_call", "tool": "query_qc_metrics", "status": metrics.get("status")})
            if metrics.get("status") != "ok":
                return metrics, steps
            evidence = unpack(await session.call_tool("get_qc_evidence", {"category": category, "limit": 5}))
            steps.append({"kind": "mcp_call", "tool": "get_qc_evidence", "status": evidence.get("status"),
                          "record_count": len(evidence.get("records", []))})
            if evidence.get("status") != "ok":
                return evidence, steps
            return {"status": "ok", "metrics": metrics, "evidence": evidence.get("records", [])}, steps
