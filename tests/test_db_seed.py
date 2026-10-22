"""Seed data must satisfy foreign keys on first startup and on restart."""
from __future__ import annotations

import sqlite3
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api import db as demo_db


class SeedDatabaseTest(unittest.TestCase):
    def test_seed_respects_foreign_keys_and_is_idempotent(self) -> None:
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection: sqlite3.Connection, _record: object) -> None:
            connection.execute("PRAGMA foreign_keys=ON")

        session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        with (
            patch.object(demo_db, "engine", engine),
            patch.object(demo_db, "SessionLocal", session_factory),
            patch.object(demo_db, "DATABASE_URL", "sqlite://"),
        ):
            demo_db.init_db()
            demo_db.init_db()

        with session_factory() as session:
            self.assertIsNotNone(session.get(demo_db.User, "user"))
            self.assertEqual(
                session.get(demo_db.Reimbursement, "BX-2026-1023").owner_id,
                "user",
            )
            self.assertEqual(session.query(demo_db.Reimbursement).count(), 2)


if __name__ == "__main__":
    unittest.main()
