"""Physical progress: no certification, money or delivery-state side effects."""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.construction.models import ConstructionStage, UnitStageEvent
from app.modules.construction.permissions import (
    require_construction_technical,
    require_whole_project_scope,
)
from app.modules.inventory.permissions import require_unit
from app.modules.projects.models import Project
from app.modules.projects.permissions import require_project_access, require_project_role
from app.modules.projects.service import lock_project


def list_stages(session: Session, project: Project) -> list[ConstructionStage]:
    return list(
        session.scalars(
            select(ConstructionStage)
            .where(ConstructionStage.project_id == project.id)
            .order_by(ConstructionStage.sequence)
        )
    )


def create_stage(
    session: Session, project: Project, actor: ActorContext, name: str, planned_date: date | None
) -> ConstructionStage:
    require_project_role(actor, frozenset({"project_manager"}))
    lock_project(session, project.id)
    require_project_access(session, project_id=project.id, actor=actor)
    require_whole_project_scope(session, project_id=project.id, actor=actor)
    name = name.strip()
    if not name:
        raise ValidationError("Stage name is required.")
    if session.scalar(
        select(ConstructionStage.id).where(
            ConstructionStage.project_id == project.id,
            func.lower(ConstructionStage.name) == name.lower(),
        )
    ):
        raise ConflictError("A stage with this name already exists.")
    sequence = (
        session.scalar(
            select(func.max(ConstructionStage.sequence)).where(
                ConstructionStage.project_id == project.id
            )
        )
        or 0
    )
    stage = ConstructionStage(
        project_id=project.id, name=name, sequence=sequence + 1, planned_date=planned_date
    )
    session.add(stage)
    session.flush()
    record_event(
        session,
        action="construction.stage_created",
        entity_type="construction_stage",
        entity_id=stage.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        after={"project_id": project.id, **_configuration(stage)},
    )
    session.commit()
    session.refresh(stage)
    return stage


def _configuration(stage: ConstructionStage) -> dict:
    return {"name": stage.name, "planned_date": stage.planned_date, "sequence": stage.sequence}


def update_stage(
    session: Session,
    project: Project,
    actor: ActorContext,
    stage_id: uuid.UUID,
    changes: dict,
) -> ConstructionStage:
    """Compare the operator's snapshot behind the shared project lock.

    Reordering changes presentation only. Each flush obeys the immediate unique
    constraint: park above N, move into the vacant slot, then place the target.
    """
    require_project_role(actor, frozenset({"project_manager"}))
    lock_project(session, project.id)
    require_project_access(session, project_id=project.id, actor=actor)
    require_whole_project_scope(session, project_id=project.id, actor=actor)
    rows = list(
        session.scalars(
            select(ConstructionStage)
            .where(ConstructionStage.project_id == project.id)
            .order_by(ConstructionStage.sequence)
            .execution_options(populate_existing=True)
        )
    )
    stage = next((row for row in rows if row.id == stage_id), None)
    if stage is None:
        raise NotFoundError("Stage not found.")
    before = _configuration(stage)
    if any(before[key] != changes[f"expected_{key}"] for key in before):
        raise ConflictError("Stage configuration changed. Reload before saving.")
    name = changes.get("name", stage.name)
    if name is None or not name.strip():
        raise ValidationError("Stage name is required.")
    name = name.strip()
    if any(row.id != stage.id and row.name.lower() == name.lower() for row in rows):
        raise ConflictError("A stage with this name already exists.")
    target = changes.get("sequence", stage.sequence)
    if target is None or not 1 <= target <= len(rows):
        raise ValidationError("Stage sequence must be a position in the checklist.")
    order_before = [row.id for row in rows]
    if "sequence" in changes:
        if changes.get("expected_order") is None:
            raise ValidationError("The current checklist order is required when moving a stage.")
        if changes["expected_order"] != order_before:
            raise ConflictError("Checklist order changed. Reload before moving a stage.")
    old_sequence = stage.sequence
    if target != old_sequence:
        stage.sequence = max(row.sequence for row in rows) + 1
        session.flush()
        affected = (
            [row for row in rows if target <= row.sequence < old_sequence][::-1]
            if target < old_sequence
            else [row for row in rows if old_sequence < row.sequence <= target]
        )
        for row in affected:
            row.sequence += 1 if target < old_sequence else -1
            session.flush()
        stage.sequence = target
    stage.name = name
    if "planned_date" in changes:
        stage.planned_date = changes["planned_date"]
    session.flush()
    after = _configuration(stage)
    if before != after:
        record_event(
            session,
            action="construction.stage_updated",
            entity_type="construction_stage",
            entity_id=stage.id,
            actor_user_id=actor.user_id,
            correlation_id=actor.correlation_id,
            before={**before, "order": order_before},
            after={
                **after,
                "order": [row.id for row in sorted(rows, key=lambda row: row.sequence)],
            },
        )
    session.commit()
    session.refresh(stage)
    return stage


def unit_progress(
    session: Session, project: Project, actor: ActorContext, unit_id: uuid.UUID
) -> dict:
    unit = require_unit(session, project=project, actor=actor, unit_id=unit_id)
    events = list(
        session.scalars(
            select(UnitStageEvent)
            .where(UnitStageEvent.project_id == project.id, UnitStageEvent.unit_id == unit.id)
            .order_by(UnitStageEvent.sequence.desc())
        )
    )
    rows = []
    for stage in list_stages(session, project):
        history = [event for event in events if event.stage_id == stage.id]
        completed = history[0].completed_date if history else None
        rows.append(
            {
                "id": stage.id,
                "name": stage.name,
                "sequence": stage.sequence,
                "planned_date": stage.planned_date,
                "completed_date": completed,
                "revision": history[0].sequence if history else 0,
                "status": "complete" if completed else "pending",
                "history": history,
            }
        )
    return {
        "unit_id": unit.id,
        "delivery_status": unit.delivery_status,
        "completed_count": sum(row["status"] == "complete" for row in rows),
        "stage_count": len(rows),
        "stages": rows,
    }


def record_completion(
    session: Session,
    project: Project,
    actor: ActorContext,
    unit_id: uuid.UUID,
    stage_id: uuid.UUID,
    completed_date: date | None,
    reason: str,
    expected_revision: int,
) -> None:
    require_construction_technical(actor)
    lock_project(session, project.id)
    require_project_access(session, project_id=project.id, actor=actor)
    require_unit(session, project=project, actor=actor, unit_id=unit_id)
    stage = session.scalar(
        select(ConstructionStage).where(
            ConstructionStage.id == stage_id, ConstructionStage.project_id == project.id
        )
    )
    if stage is None:
        raise NotFoundError("Stage not found.")
    if completed_date and completed_date > datetime.now(UTC).date():
        raise ValidationError("Completion date cannot be in the future.")
    if not reason.strip():
        raise ValidationError("A reason or completion note is required.")
    latest = session.scalar(
        select(UnitStageEvent)
        .where(
            UnitStageEvent.project_id == project.id,
            UnitStageEvent.unit_id == unit_id,
            UnitStageEvent.stage_id == stage_id,
        )
        .order_by(UnitStageEvent.sequence.desc())
        .limit(1)
    )
    revision = latest.sequence if latest else 0
    if revision != expected_revision:
        raise ConflictError("This stage changed. Reload the unit before recording progress.")
    if (latest.completed_date if latest else None) == completed_date:
        raise ConflictError("This completion date is already recorded.")
    event = UnitStageEvent(
        project_id=project.id,
        unit_id=unit_id,
        stage_id=stage.id,
        sequence=revision + 1,
        completed_date=completed_date,
        reason=reason.strip(),
        actor_user_id=actor.user_id,
    )
    session.add(event)
    session.flush()
    record_event(
        session,
        action="construction.stage_progress",
        entity_type="unit_stage_event",
        entity_id=event.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        reason=reason.strip(),
        before={"completed_date": latest.completed_date if latest else None},
        after={"unit_id": unit_id, "stage_id": stage.id, "completed_date": completed_date},
    )
    session.commit()
