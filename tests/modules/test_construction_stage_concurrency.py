"""Real competing transactions for the physical checklist's shared project lock."""

import threading
import uuid
from collections.abc import Callable
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.modules.access.models import User
from app.modules.construction import stages
from app.modules.construction.models import ConstructionStage, UnitStageEvent
from app.modules.projects.service import lock_project
from tests.modules.conftest import construction_url
from tests.modules.test_construction_concurrency import _actor, _project, _race


@pytest.mark.parametrize("operation", ["create", "reorder", "edit", "completion"])
def test_project_lock_serializes_checklist_writers(
    db: Session,
    manager_member_client: TestClient,
    manager: User,
    project_id: str,
    unit_id: str,
    operation: str,
) -> None:
    root = construction_url(project_id)
    for name in ("A", "B", "C"):
        assert manager_member_client.post(f"{root}/stages", json={"name": name}).status_code == 201
    rows = manager_member_client.get(f"{root}/stages").json()
    stage_id = uuid.UUID(rows[0]["id"])
    project_uuid = uuid.UUID(project_id)
    actor = _actor(manager)
    ready, release = threading.Event(), threading.Event()
    expected = {"expected_name": "A", "expected_planned_date": None, "expected_sequence": 1}

    def writer(first: bool) -> Callable[[Session], str]:
        def run(session: Session) -> str:
            project = _project(session, project_uuid)
            # Deliberately preload the stale identity map as well as the request.
            session.scalars(
                select(ConstructionStage).where(ConstructionStage.project_id == project_uuid)
            ).all()
            if first:
                lock_project(session, project_uuid)
                ready.set()
                assert release.wait(timeout=20)
            if operation == "create":
                stages.create_stage(session, project, actor, "D" if first else "E", None)
            elif operation == "completion":
                stages.record_completion(
                    session,
                    project,
                    actor,
                    uuid.UUID(unit_id),
                    stage_id,
                    date(2026, 8, 1),
                    "Inspection",
                    0,
                )
            else:
                change = (
                    {
                        "sequence": 3 if first else 2,
                        "expected_order": [uuid.UUID(row["id"]) for row in rows],
                    }
                    if operation == "reorder"
                    else {"name": "Updated" if first else "Stale"}
                )
                stages.update_stage(session, project, actor, stage_id, {**expected, **change})
            return "saved"

        return run

    won, second = _race(writer(True), writer(False), ready, release)
    assert won == ["saved"], won
    if operation == "create":
        assert second == ["saved"], second
    else:
        assert len(second) == 1 and isinstance(second[0], ConflictError), second
    db.expire_all()
    current = stages.list_stages(db, _project(db, project_uuid))
    assert [row.sequence for row in current] == list(range(1, len(current) + 1))
    if operation == "create":
        assert [row.name for row in current] == ["A", "B", "C", "D", "E"]
    elif operation == "reorder":
        assert [row.name for row in current] == ["B", "C", "A"]
    elif operation == "edit":
        assert current[0].name == "Updated"
    else:
        events = list(db.scalars(select(UnitStageEvent).where(UnitStageEvent.stage_id == stage_id)))
        assert len(events) == 1
        assert events[0].sequence == 1
        assert events[0].completed_date == date(2026, 8, 1)
