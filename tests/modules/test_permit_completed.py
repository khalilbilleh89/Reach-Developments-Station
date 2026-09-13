"""Completion is durable, audited and no longer overdue work."""

import uuid
from datetime import date
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.projects.batch import positions
from app.modules.projects.models import Project
from tests.modules.conftest import PROJECTS
from tests.modules.test_permit_entry_removal import add


@pytest.mark.parametrize("status", ["issued", "renewed"])
@pytest.mark.parametrize("reason", [None, "", "Done"])
def test_completion_records_optional_reason_and_satisfies_prerequisite(
    admin_client: TestClient, project_id: str, db: Session, status: str, reason: str | None
) -> None:
    permit = add(
        admin_client,
        project_id,
        initial_status=status,
        statutory_sla_days=1,
        status_effective_date="2025-01-01",
    )
    child = add(admin_client, project_id, permit_code="CHILD", prerequisite_permit_id=permit["id"])
    url = f"{PROJECTS}/{project_id}/permits/{permit['id']}"
    body = {"to_status": "completed", "effective_date": "2025-01-02"}
    if reason is not None:
        body["reason"] = reason
    result = admin_client.post(f"{url}/transitions", json=body)
    assert result.status_code == 201, result.text
    assert result.json()["status"] == "completed"
    assert result.json()["sla_overdue"] is False
    assert result.json()["sla_days_remaining"] is None
    history = admin_client.get(f"{url}/status-history").json()
    assert history[-1]["to_status"] == "completed"
    assert history[-1]["reason"] == (reason or None)
    assert (
        admin_client.get(f"{PROJECTS}/{project_id}/permits/{child['id']}").json()[
            "prerequisite_satisfied"
        ]
        is True
    )
    register = admin_client.get(f"{PROJECTS}/{project_id}/permits", params={"status": "completed"})
    assert register.status_code == 200
    assert register.json()["sla_overdue_count"] == 0
    position = positions(
        db, select(Project.id).where(Project.id == uuid.UUID(project_id)), date(2026, 9, 12)
    )[uuid.UUID(project_id)]
    assert not position.overdue
    assert (
        admin_client.post(
            f"{url}/transitions", json={"to_status": "issued", "effective_date": "2025-01-03"}
        ).status_code
        == 409
    )


def test_completion_migration_round_trip_and_history_guard(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    db.rollback()
    command.downgrade(config, "0025_prelaunch_master")
    command.upgrade(config, "head")
    command.check(config)
    add(admin_client, project_id, initial_status="completed")
    db.rollback()
    with pytest.raises(RuntimeError, match="completed permit"):
        command.downgrade(config, "0025_prelaunch_master")
    command.upgrade(config, "head")
