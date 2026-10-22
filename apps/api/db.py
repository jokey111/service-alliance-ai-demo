"""Persistence for the interview demo. SQLite locally; PostgreSQL via DATABASE_URL."""
from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


def now() -> datetime:
    return datetime.now(timezone.utc)


load_dotenv(Path(__file__).with_name(".env"), override=False)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/demo.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(32))
    department: Mapped[str] = mapped_column(String(80))


class Reimbursement(Base):
    __tablename__ = "reimbursements"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    amount_yuan: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(40))
    current_step: Mapped[str] = mapped_column(String(120))
    next_action: Mapped[str] = mapped_column(String(200))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    trace_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class Ticket(Base):
    __tablename__ = "tickets"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    conversation_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    assignee_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class RepairRequest(Base):
    __tablename__ = "repair_requests"
    idempotency_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    domain: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    version: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="published")
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class QCReport(Base):
    __tablename__ = "qc_reports"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    findings: Mapped[list] = mapped_column(JSON, default=list)
    reviewer_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    rule_version: Mapped[str] = mapped_column(String(30), default="qc-v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Trace(Base):
    __tablename__ = "traces"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(32), index=True)
    conversation_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


def init_db() -> None:
    if DATABASE_URL.startswith("sqlite"):
        os.makedirs("data", exist_ok=True)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if not db.get(User, "user"):
            db.add_all([
                User(id="user", name="张伟", role="employee", department="产品部"),
                User(id="agent", name="李娜", role="agent", department="共享服务中心"),
                User(id="qc", name="周雯", role="qc", department="服务质量组"),
                User(id="admin", name="陈建国", role="admin", department="系统管理组"),
            ])
            # Persist referenced users before the knowledge lookup triggers autoflush.
            db.flush()
            db.add_all([
                Reimbursement(id="BX-2026-1023", owner_id="user", title="上海出差住宿报销", amount_yuan=1280, status="审批中", current_step="财务复核", next_action="预计由财务复核后进入付款环节"),
                Reimbursement(id="BX-2026-1008", owner_id="user", title="客户拜访交通报销", amount_yuan=186, status="待补充材料", current_step="票据核验", next_action="请补充电子发票原件"),
            ])
        from apps.api.knowledge import seed_documents
        seed_documents(db)
        db.commit()
