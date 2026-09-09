"""The one action migration changes no source tables and protects history."""

import uuid
from datetime import UTC, datetime

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_engine
from tests.conftest import alembic_config
from tests.factories import make_user
from tests.modules.conftest import grant_access
from tests.modules.test_commissions_review import snapshot


def test_action_migration_roundtrip_constraints_and_history(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    owner = make_user(db, email="migration-action-owner@example.com", roles=("project_manager",))
    grant_access(admin_client, project_id, owner)
    before = snapshot(db, ("management_actions", "management_action_history", "alembic_version"))
    reply = admin_client.post(
        "/api/v1/portfolio/actions",
        json={
            "project_id": project_id,
            "title": "Governed history",
            "owner_user_id": str(owner.id),
            "due_date": str(datetime.now(UTC).date()),
        },
    )
    assert reply.status_code == 201, reply.text
    identifier = uuid.UUID(reply.json()["id"])
    for assignment in (
        "status = 'invented'",
        "version = 0",
        "title = ' '",
        "owner_user_id = NULL",
        "source_type = 'engine'",
    ):
        with pytest.raises(SQLAlchemyError), db.begin_nested():
            db.execute(
                text(f"UPDATE management_actions SET {assignment} WHERE id = :id"),
                {"id": identifier},
            )
    for statement in (
        "UPDATE management_action_history SET reason = 'rewrite'",
        "DELETE FROM management_action_history",
    ):
        with pytest.raises(SQLAlchemyError, match="append-only"), db.begin_nested():
            db.execute(text(statement))
    assert (
        snapshot(db, ("management_actions", "management_action_history", "alembic_version"))
        == before
    )
    db.rollback()
    command.downgrade(alembic_config(), "0017_consultant_commissions")
    assert "management_actions" not in inspect(get_engine()).get_table_names()
    assert snapshot(db, ("alembic_version",)) == before
    db.rollback()
    command.upgrade(alembic_config(), "head")
    command.check(alembic_config())
    assert {"management_actions", "management_action_history"} <= set(
        inspect(get_engine()).get_table_names()
    )
    assert (
        snapshot(db, ("management_actions", "management_action_history", "alembic_version"))
        == before
    )
