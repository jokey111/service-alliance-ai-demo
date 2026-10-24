"""Direct and conversation-based human handoff create one visible ticket."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api import db as demo_db
from apps.api import main


class HandoffTest(unittest.TestCase):
    def test_direct_handoff_and_repeat_from_same_conversation(self) -> None:
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        demo_db.Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        user = demo_db.User(id="user", name="张伟", role="employee", department="测试部门")
        other = demo_db.User(id="other", name="王明", role="employee", department="测试部门")
        with session_factory() as session:
            session.add_all([user, other])
            session.commit()

        with patch.object(main, "SessionLocal", session_factory):
            direct = main.handoff(main.HandoffRequest(), user)
            with session_factory() as session:
                ticket = session.get(demo_db.Ticket, direct["id"])
                self.assertEqual(ticket.status, "pending")
                self.assertIn("员工直接请求人工服务", ticket.description)
                conversation_id = ticket.conversation_id
                self.assertEqual(session.get(demo_db.Conversation, conversation_id).status, "handoff")

            repeated = main.handoff(main.HandoffRequest(conversation_id=conversation_id), user)
            self.assertEqual(repeated["id"], direct["id"])
            with session_factory() as session:
                self.assertEqual(len(session.scalars(select(demo_db.Ticket)).all()), 1)

            with self.assertRaises(HTTPException) as error:
                main.handoff(main.HandoffRequest(conversation_id=conversation_id), other)
            self.assertEqual(error.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
