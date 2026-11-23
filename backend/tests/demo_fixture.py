"""The demo tables over in-memory SQLite, for unit tests with no services (docs/demo-wall-handoff.md).

`demo_comparisons`, `demo_feedback` and `projects` are the real models. `comparisons` has JSONB columns
SQLite can't hold, so it is a stand-in with the four columns the in-flight count reads. The advisory lock,
the one-statement snapshot and row-level security need PostgreSQL: tests/integration/test_demo_db.py.
"""
from __future__ import annotations

import uuid

from sqlalchemy import text

from changelens.domain.models import DemoComparison, DemoFeedback, Project

OFF = {"limit": None, "used": 0, "in_flight": 0, "remaining": None,
       "feedback": {"submitted": False, "discount_offered": False}}


def fresh(limit: int = 3) -> dict:
    """The state of an account that has done nothing."""
    return {"limit": limit, "used": 0, "in_flight": 0, "remaining": limit,
            "feedback": {"submitted": False, "discount_offered": False}}


def create_demo_tables(engine) -> None:
    Project.__table__.create(engine)
    DemoComparison.__table__.create(engine)
    DemoFeedback.__table__.create(engine)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE comparisons (id CHAR(32) PRIMARY KEY, tenant_id CHAR(32) NOT NULL, "
                          "project_id CHAR(32) NOT NULL, status VARCHAR(24) NOT NULL)"))


def add_comparison(engine, tenant: uuid.UUID, project: uuid.UUID, status: str) -> uuid.UUID:
    """One stand-in comparison row; returns its ID."""
    comparison = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO comparisons (id, tenant_id, project_id, status) VALUES (:i, :t, :p, :s)"),
                     {"i": comparison.hex, "t": tenant.hex, "p": project.hex, "s": status})
    return comparison
