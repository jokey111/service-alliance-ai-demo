"""Deterministic regression cases for product-critical behavior."""
from __future__ import annotations

from sqlalchemy import select

from apps.api.db import Reimbursement, SessionLocal
from apps.api.knowledge import search


def run_cases(route_fn) -> list[dict]:
    cases = [
        ("E01", "本人报销进度", "我的报销进度到哪了？", "reimbursement-status"),
        ("E02", "否定查询意图", "先别查报销，只告诉我申请流程", "knowledge"),
        ("E03", "请假知识", "年假怎么申请？", "knowledge"),
        ("E04", "安全知识", "收到钓鱼邮件怎么办？", "knowledge"),
        ("E05", "人工转接", "我要转人工客服", "handoff"),
        ("E06", "能力边界", "帮我订一张电影票", "fallback"),
    ]
    results = [{"id": case_id, "name": name, "expected": expected,
                "observed": route_fn(query, None), "passed": route_fn(query, None) == expected}
               for case_id, name, query, expected in cases]
    with SessionLocal() as db:
        active = search(db, "报销旧版指引")
        results.append({"id": "E07", "name": "过期知识过滤", "expected": "不引用 KB-FIN-BX-OLD",
                        "observed": [doc.id for doc in active],
                        "passed": all(doc.id != "KB-FIN-BX-OLD" for doc in active)})
        leave = search(db, "年假怎么申请")
        results.append({"id": "E08", "name": "跨业务知识召回", "expected": "KB-HR-001",
                        "observed": [doc.id for doc in leave],
                        "passed": bool(leave) and leave[0].id == "KB-HR-001"})
        owned = db.scalars(select(Reimbursement).where(Reimbursement.owner_id == "user")).all()
        results.append({"id": "E09", "name": "本人单据可见", "expected": "2 张本人单据",
                        "observed": len(owned), "passed": len(owned) == 2})
        other = db.scalars(select(Reimbursement).where(Reimbursement.owner_id == "agent")).all()
        results.append({"id": "E10", "name": "坐席不能冒充本人取员工单据", "expected": "0 张员工单据",
                        "observed": len(other), "passed": len(other) == 0})
    return results
