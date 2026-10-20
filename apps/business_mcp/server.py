"""Separate MCP server backed by synthetic business records.

The actor_id is supplied by the trusted API service over a private network.
Never expose this server directly to the public internet.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from sqlalchemy import select

from apps.api.db import QCReport, Reimbursement, RepairRequest, SessionLocal, Ticket, now
from uuid import uuid4

mcp = FastMCP("12345-synthetic-business", host="0.0.0.0", port=8011, stateless_http=True)


def reimbursement_dict(item: Reimbursement, detail: bool = False) -> dict:
    result = {
        "id": item.id,
        "title": item.title,
        "amount_yuan": item.amount_yuan,
        "status": item.status,
        "updated_at": item.updated_at.isoformat(),
    }
    if detail:
        result.update(current_step=item.current_step, next_action=item.next_action)
    return result


@mcp.tool(description="列出当前登录员工本人可查看的报销单；owner_id 必须由可信 API 服务端注入。")
def list_my_reimbursements(actor_id: str) -> dict:
    with SessionLocal() as db:
        items = db.scalars(select(Reimbursement).where(Reimbursement.owner_id == actor_id)).all()
        return {"status": "ok", "items": [reimbursement_dict(item) for item in items]}


@mcp.tool(description="查询指定报销单详情；必须再次校验它属于当前员工。")
def get_reimbursement_detail(actor_id: str, reimbursement_id: str) -> dict:
    with SessionLocal() as db:
        item = db.get(Reimbursement, reimbursement_id)
        if item is None or item.owner_id != actor_id:
            return {"status": "forbidden_or_missing", "message": "无权查看该单据或单据不存在"}
        return {"status": "ok", "item": reimbursement_dict(item, detail=True)}


@mcp.tool(description="查询工单时间线。员工只能查询本人工单；坐席或质检角色的扩展授权由 API 层处理。")
def get_my_ticket(actor_id: str, ticket_id: str) -> dict:
    with SessionLocal() as db:
        ticket = db.get(Ticket, ticket_id)
        if ticket is None or ticket.owner_id != actor_id:
            return {"status": "forbidden_or_missing"}
        return {"status": "ok", "ticket": {"id": ticket.id, "title": ticket.title, "status": ticket.status, "resolution": ticket.resolution}}


@mcp.tool(description="员工确认后提交 IT 报修；idempotency_key 由 API 生成，重复调用返回同一工单。仅供内网 API 调用。")
def create_it_repair_ticket(actor_id: str, device: str, issue: str, location: str, idempotency_key: str) -> dict:
    if not all(value.strip() for value in (device, issue, location, idempotency_key)):
        return {"status": "invalid_input"}
    with SessionLocal.begin() as db:
        prior = db.get(RepairRequest, idempotency_key)
        if prior:
            if prior.owner_id != actor_id:
                return {"status": "forbidden_or_missing"}
            return {"status": "ok", "ticket_id": prior.ticket_id, "duplicate": True}
        ticket = Ticket(id=f"IT-{now().strftime('%Y%m%d')}-{uuid4().hex[:5].upper()}", owner_id=actor_id,
                        title=f"{device}故障报修", description=f"设备：{device}\n故障：{issue}\n地点：{location}", category="IT报修")
        db.add(ticket)
        db.add(RepairRequest(idempotency_key=idempotency_key, owner_id=actor_id, ticket_id=ticket.id))
        return {"status": "ok", "ticket_id": ticket.id, "duplicate": False}


@mcp.tool(description="只读汇总某类合成工单状态与质检复核状态；由质检 API 调用。")
def query_qc_metrics(category: str) -> dict:
    with SessionLocal() as db:
        tickets = db.scalars(select(Ticket).where(Ticket.category == category)).all() if category != "全部" else db.scalars(select(Ticket)).all()
        ids = [item.id for item in tickets]
        reports = db.scalars(select(QCReport).where(QCReport.ticket_id.in_(ids))).all() if ids else []
        return {"status": "ok", "category": category, "ticket_count": len(tickets),
                "ticket_status": {state: sum(item.status == state for item in tickets) for state in ("pending", "processing", "resolved", "closed")},
                "report_count": len(reports),
                "review_status": {state: sum(item.status == state for item in reports) for state in ("draft", "confirmed", "rejected", "needs_evidence")}}


@mcp.tool(description="只读返回最多五条质检抽样证据，不给出自动合格判定。")
def get_qc_evidence(category: str, limit: int = 5) -> dict:
    with SessionLocal() as db:
        tickets = db.scalars(select(Ticket).where(Ticket.category == category).order_by(Ticket.created_at.desc()).limit(min(max(limit, 1), 5))).all() if category != "全部" else db.scalars(select(Ticket).order_by(Ticket.created_at.desc()).limit(min(max(limit, 1), 5))).all()
        records = []
        for ticket in tickets:
            report = db.scalars(select(QCReport).where(QCReport.ticket_id == ticket.id)).first()
            records.append({"ticket_id": ticket.id, "category": ticket.category, "status": ticket.status,
                            "resolution": ticket.resolution, "qc_report_id": report.id if report else None,
                            "qc_status": report.status if report else None})
        return {"status": "ok", "records": records}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
