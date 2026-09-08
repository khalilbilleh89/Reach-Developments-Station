"""Locked, audited consultant-design operations."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.consultant_engineering import models, schemas
from app.modules.consultant_engineering.permissions import require_editor
from app.modules.projects.models import Project
from app.modules.projects.service import lock_project


def _audit(
    session: Session,
    actor: ActorContext,
    action: str,
    entity: object,
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    record_event(
        session,
        action=action,
        entity_type=type(entity).__name__,
        entity_id=entity.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        before=before,
        after={**(after or {}), "project_id": entity.project_id},
    )


def _get[T](session: Session, cls: type[T], project: Project, identifier: uuid.UUID) -> T:
    row = session.scalar(
        select(cls)
        .where(cls.id == identifier, cls.project_id == project.id)
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise NotFoundError("Consultant design record not found.")
    return row


def workspace(session: Session, project: Project) -> schemas.WorkspaceOut:
    engagements = list(
        session.scalars(
            select(models.ConsultantEngagement)
            .where(models.ConsultantEngagement.project_id == project.id)
            .order_by(models.ConsultantEngagement.created_at.desc())
        )
    )
    disciplines = list(
        session.scalars(
            select(models.ConsultantDiscipline)
            .where(models.ConsultantDiscipline.project_id == project.id)
            .order_by(models.ConsultantDiscipline.name)
        )
    )
    stages = list(
        session.scalars(
            select(models.ConsultantDesignStage)
            .where(models.ConsultantDesignStage.project_id == project.id)
            .order_by(models.ConsultantDesignStage.sequence)
        )
    )
    deliverables = list(
        session.scalars(
            select(models.ConsultantDeliverable)
            .where(models.ConsultantDeliverable.project_id == project.id)
            .order_by(
                models.ConsultantDeliverable.due_date.nulls_last(),
                models.ConsultantDeliverable.created_at,
            )
        )
    )
    active = next((row for row in engagements if row.status == "active"), None)
    current = next(
        (row for row in stages if row.status in {"in_progress", "on_hold"}),
        next((row for row in stages if row.status == "not_started"), None),
    )
    return schemas.WorkspaceOut(
        active_engagement=active,
        engagements=engagements,
        disciplines=disciplines,
        stages=stages,
        deliverables=deliverables,
        total_disciplines=len(disciplines),
        completed_disciplines=sum(row.status == "completed" for row in disciplines),
        current_design_stage=current,
        completed_stages=sum(row.status == "completed" for row in stages),
        total_stages=len(stages),
        outstanding_deliverables=sum(
            row.status not in {"accepted", "superseded", "cancelled"} for row in deliverables
        ),
        accepted_deliverables=sum(row.status == "accepted" for row in deliverables),
    )


def create_engagement(
    session: Session, project: Project, actor: ActorContext, payload: schemas.EngagementCreate
) -> models.ConsultantEngagement:
    require_editor(actor)
    lock_project(session, project.id)
    values = payload.model_dump()
    values["consultant_name"] = values["consultant_name"].strip()
    values["agreement_reference"] = values["agreement_reference"].strip()
    if (
        values["planned_start_date"]
        and values["planned_completion_date"]
        and values["planned_completion_date"] < values["planned_start_date"]
    ):
        raise ValidationError("Planned completion cannot precede planned start.")
    row = models.ConsultantEngagement(
        project_id=project.id, created_by_user_id=actor.user_id, **values
    )
    session.add(row)
    session.flush()
    _audit(session, actor, "consultant.engagement_created", row, after=values)
    session.commit()
    session.refresh(row)
    return row


def update_engagement(
    session: Session,
    project: Project,
    actor: ActorContext,
    identifier: uuid.UUID,
    payload: schemas.EngagementUpdate,
) -> models.ConsultantEngagement:
    require_editor(actor)
    lock_project(session, project.id)
    row = _get(session, models.ConsultantEngagement, project, identifier)
    if row.status != "draft":
        raise ConflictError("Only a draft engagement may be edited.")
    if row.updated_at != payload.expected_updated_at:
        raise ConflictError("Engagement changed. Reload before saving.")
    values = payload.model_dump(exclude={"expected_updated_at"})
    before = {key: getattr(row, key) for key in values}
    for key, value in values.items():
        setattr(row, key, value.strip() if isinstance(value, str) else value)
    session.flush()
    _audit(session, actor, "consultant.engagement_updated", row, before, values)
    session.commit()
    session.refresh(row)
    return row


def transition_engagement(
    session: Session, project: Project, actor: ActorContext, identifier: uuid.UUID, target: str
) -> models.ConsultantEngagement:
    require_editor(actor)
    lock_project(session, project.id)
    row = _get(session, models.ConsultantEngagement, project, identifier)
    allowed = {("draft", "active"), ("active", "completed"), ("active", "terminated")}
    if (row.status, target) not in allowed:
        raise ConflictError("That consultant agreement transition is not allowed.")
    before = row.status
    row.status = target
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError(
            "This project already has an active main consultant agreement."
        ) from exc
    _audit(
        session,
        actor,
        f"consultant.engagement_{target}",
        row,
        {"status": before},
        {"status": target},
    )
    session.commit()
    session.refresh(row)
    return row


def create_discipline(
    session: Session,
    project: Project,
    actor: ActorContext,
    engagement_id: uuid.UUID,
    payload: schemas.DisciplineWrite,
) -> models.ConsultantDiscipline:
    require_editor(actor)
    lock_project(session, project.id)
    _get(session, models.ConsultantEngagement, project, engagement_id)
    name = payload.name.strip()
    row = models.ConsultantDiscipline(
        project_id=project.id,
        engagement_id=engagement_id,
        normalized_name=name.casefold(),
        **payload.model_dump(exclude={"name"}),
        name=name,
    )
    session.add(row)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError("That discipline already exists in this engagement.") from exc
    _audit(session, actor, "consultant.discipline_created", row, after=payload.model_dump())
    session.commit()
    session.refresh(row)
    return row


def update_discipline(
    session: Session,
    project: Project,
    actor: ActorContext,
    identifier: uuid.UUID,
    payload: schemas.DisciplineWrite,
) -> models.ConsultantDiscipline:
    require_editor(actor)
    lock_project(session, project.id)
    row = _get(session, models.ConsultantDiscipline, project, identifier)
    before = {key: getattr(row, key) for key in type(payload).model_fields}
    for key, value in payload.model_dump().items():
        setattr(row, key, value.strip() if isinstance(value, str) else value)
    row.normalized_name = row.name.casefold()
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError("That discipline already exists in this engagement.") from exc
    _audit(session, actor, "consultant.discipline_updated", row, before, payload.model_dump())
    session.commit()
    session.refresh(row)
    return row


def create_stage(
    session: Session,
    project: Project,
    actor: ActorContext,
    engagement_id: uuid.UUID,
    payload: schemas.StageWrite,
) -> models.ConsultantDesignStage:
    require_editor(actor)
    lock_project(session, project.id)
    _get(session, models.ConsultantEngagement, project, engagement_id)
    _validate_stage(payload.status, payload.actual_completion_date)
    sequence = (
        session.scalar(
            select(func.max(models.ConsultantDesignStage.sequence)).where(
                models.ConsultantDesignStage.engagement_id == engagement_id
            )
        )
        or 0
    ) + 1
    row = models.ConsultantDesignStage(
        project_id=project.id,
        engagement_id=engagement_id,
        sequence=sequence,
        **payload.model_dump(),
    )
    session.add(row)
    session.flush()
    _audit(
        session,
        actor,
        "consultant.stage_created",
        row,
        after={**payload.model_dump(), "sequence": sequence},
    )
    session.commit()
    session.refresh(row)
    return row


def _validate_stage(status: str, actual: date | None) -> None:
    if status == "completed" and actual is None:
        raise ValidationError("A completed design stage requires its actual completion date.")


def update_stage(
    session: Session,
    project: Project,
    actor: ActorContext,
    identifier: uuid.UUID,
    payload: schemas.StageUpdate,
) -> models.ConsultantDesignStage:
    require_editor(actor)
    lock_project(session, project.id)
    row = _get(session, models.ConsultantDesignStage, project, identifier)
    _validate_stage(payload.status, payload.actual_completion_date)
    rows = list(
        session.scalars(
            select(models.ConsultantDesignStage)
            .where(models.ConsultantDesignStage.engagement_id == row.engagement_id)
            .order_by(models.ConsultantDesignStage.sequence)
            .execution_options(populate_existing=True)
        )
    )
    if (
        row.updated_at != payload.expected_updated_at
        or [item.id for item in rows] != payload.expected_order
    ):
        raise ConflictError("Design stages changed. Reload before saving.")
    target = payload.sequence
    if target > len(rows):
        raise ValidationError("Stage sequence must be a position in this engagement.")
    before = {"sequence": row.sequence, "status": row.status, "name": row.name}
    old = row.sequence
    if target != old:
        row.sequence = len(rows) + 1
        session.flush()
        affected = (
            [item for item in rows if target <= item.sequence < old][::-1]
            if target < old
            else [item for item in rows if old < item.sequence <= target]
        )
        for item in affected:
            item.sequence += 1 if target < old else -1
            session.flush()
        row.sequence = target
    for key, value in payload.model_dump(
        exclude={"sequence", "expected_updated_at", "expected_order"}
    ).items():
        setattr(row, key, value)
    session.flush()
    _audit(
        session,
        actor,
        "consultant.stage_updated",
        row,
        before,
        {"sequence": target, "status": row.status, "name": row.name},
    )
    session.commit()
    session.refresh(row)
    return row


def create_deliverable(
    session: Session,
    project: Project,
    actor: ActorContext,
    engagement_id: uuid.UUID,
    payload: schemas.DeliverableWrite,
) -> models.ConsultantDeliverable:
    require_editor(actor)
    lock_project(session, project.id)
    _get(session, models.ConsultantEngagement, project, engagement_id)
    _validate_deliverable(session, project, engagement_id, payload)
    row = models.ConsultantDeliverable(
        project_id=project.id, engagement_id=engagement_id, **payload.model_dump()
    )
    session.add(row)
    session.flush()
    _audit(session, actor, "consultant.deliverable_created", row, after=payload.model_dump())
    session.commit()
    session.refresh(row)
    return row


def _validate_deliverable(
    session: Session, project: Project, engagement_id: uuid.UUID, payload: schemas.DeliverableWrite
) -> None:
    stage = _get(session, models.ConsultantDesignStage, project, payload.stage_id)
    if stage.engagement_id != engagement_id:
        raise ValidationError("The design stage belongs to another engagement.")
    if payload.discipline_id:
        discipline = _get(session, models.ConsultantDiscipline, project, payload.discipline_id)
        if discipline.engagement_id != engagement_id:
            raise ValidationError("The discipline belongs to another engagement.")
    if payload.status in {"submitted", "accepted"} and payload.submitted_date is None:
        raise ValidationError("Submitted work requires its submitted date.")
    if payload.status == "accepted" and payload.accepted_date is None:
        raise ValidationError("Accepted work requires its accepted date.")


def update_deliverable(
    session: Session,
    project: Project,
    actor: ActorContext,
    identifier: uuid.UUID,
    payload: schemas.DeliverableUpdate,
) -> models.ConsultantDeliverable:
    require_editor(actor)
    lock_project(session, project.id)
    row = _get(session, models.ConsultantDeliverable, project, identifier)
    if row.status in {"accepted", "superseded", "cancelled"}:
        raise ConflictError("Historical deliverables are immutable; supersede with a new record.")
    if row.updated_at != payload.expected_updated_at:
        raise ConflictError("Deliverable changed. Reload before saving.")
    _validate_deliverable(session, project, row.engagement_id, payload)
    values = payload.model_dump(exclude={"expected_updated_at"})
    before = {key: getattr(row, key) for key in values}
    for key, value in values.items():
        setattr(row, key, value)
    session.flush()
    _audit(session, actor, f"consultant.deliverable_{row.status}", row, before, values)
    session.commit()
    session.refresh(row)
    return row
