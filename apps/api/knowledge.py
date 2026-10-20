"""Small, versioned synthetic knowledge set with effective-date filtering.

This MVP uses transparent lexical retrieval. It is not a vector index or a
claim that any real employer policy has been imported.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.db import KnowledgeDocument, now


DOCS = [
    ("KB-FIN-BX-001", "报销审核", "报销办理指引", ["报销", "发票", "票据", "费用"],
     "演示流程：填写费用类型与事由，上传有效票据后提交审批。若单据处于“待补充材料”，请先查看具体单据的下一步提示。实际适用标准以所在单位正式制度为准。"),
    ("KB-IT-001", "IT", "IT 报修办理指引", ["it", "电脑", "网络", "报修", "故障", "设备"],
     "演示流程：描述设备、故障和地点，核对预览后确认提交。系统返回 IT 工单号后才表示报修成功；故障紧急时请同时联系本单位 IT 服务台。"),
    ("KB-HR-001", "HR", "请假申请指引", ["请假", "休假", "年假", "病假"],
     "演示流程：选择假期类型、填写起止时间与事由，再由有权限的审批人处理。余额、证明材料和提前申请时间应以本单位正式人事制度为准。"),
    ("KB-WL-001", "WeLink", "协作账号问题指引", ["welink", "账号", "登录", "协作"],
     "演示流程：先确认账号所属组织与登录方式；如仍无法登录，联系本单位账号管理员核验身份。不要在客服对话中发送密码或一次性验证码。"),
    ("KB-TRAVEL-001", "差旅", "差旅申请指引", ["差旅", "出差", "订票", "住宿"],
     "演示流程：先填写出差事由、目的地与日期并完成审批，再办理行程预订。预算与住宿标准以当前已发布的差旅制度为准。"),
    ("KB-SUPPLY-001", "供应", "供应协同指引", ["供应", "供应商", "供货"],
     "演示流程：记录需求、供应对象与交付时间，提交给对应业务负责人确认。合同、价格与付款条款必须以正式采购文件为准。"),
    ("KB-PROCURE-001", "采购", "采购申请指引", ["采购", "买设备", "申购"],
     "演示流程：填写物品、用途、预算和需求时间，提交审批后由采购人员按正式流程处理。该演示不会实际下单。"),
    ("KB-GOV-001", "政务", "政务服务咨询指引", ["政务", "办事", "证明", "窗口"],
     "演示流程：先确认事项名称、办理地区与申请人类型，再查阅当地官方办事指南。办理条件和时限须以相应政务平台最新公告为准。"),
    ("KB-SEC-001", "信息安全", "信息安全事件上报指引", ["信息安全", "钓鱼", "泄露", "安全事件"],
     "演示流程：如怀疑账号受损或信息泄露，停止继续操作并联系本单位安全团队。不要在对话中粘贴密码、密钥或客户敏感数据。"),
]


def seed_documents(db: Session) -> None:
    effective = datetime(2025, 1, 1, tzinfo=timezone.utc)
    for doc_id, domain, title, keywords, body in DOCS:
        if not db.get(KnowledgeDocument, doc_id):
            db.add(KnowledgeDocument(id=doc_id, domain=domain, title=title, body=body,
                                     keywords=keywords, version="demo-v1", status="published",
                                     effective_at=effective))
    if not db.get(KnowledgeDocument, "KB-FIN-BX-OLD"):
        db.add(KnowledgeDocument(id="KB-FIN-BX-OLD", domain="报销审核", title="旧版报销指引（已过期）",
                                 body="旧版测试条目，不得用于现行回答。", keywords=["报销"],
                                 version="demo-v0", status="retired", effective_at=effective,
                                 expires_at=datetime(2026, 1, 1, tzinfo=timezone.utc)))


def active_documents(db: Session) -> list[KnowledgeDocument]:
    current = now()
    return db.scalars(select(KnowledgeDocument).where(
        KnowledgeDocument.status == "published",
        KnowledgeDocument.effective_at <= current,
        (KnowledgeDocument.expires_at.is_(None) | (KnowledgeDocument.expires_at > current)),
    )).all()


def search(db: Session, query: str, limit: int = 3) -> list[KnowledgeDocument]:
    words = query.lower()
    scored = []
    for doc in active_documents(db):
        score = sum(3 + min(len(keyword), 4) for keyword in doc.keywords if keyword.lower() in words)
        if doc.title.lower() in words:
            score += 5
        if score:
            scored.append((score, doc))
    scored.sort(key=lambda row: (-row[0], row[1].id))
    return [doc for _, doc in scored[:limit]]


def citation(doc: KnowledgeDocument) -> dict:
    return {"id": doc.id, "title": doc.title, "version": doc.version,
            "domain": doc.domain, "effective_at": doc.effective_at.isoformat()}
