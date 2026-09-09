"""Thin Portfolio route composition; source validation is read-only."""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.core.errors import NotFoundError, ValidationError
from app.modules.access.dependencies import ActiveActor, DbSession
from app.modules.access.models import User
from app.modules.management_actions import batch, permissions, repository, schemas, service
from app.modules.management_actions.models import ManagementAction as Action
from app.modules.management_actions.models import ManagementActionHistory as History
from app.modules.portfolio import action_sources
from app.modules.projects.models import Project

router = APIRouter(prefix="/portfolio/actions", tags=["management-actions"])
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


@router.get("", response_model=schemas.ActionPage)
def list_actions(
    session: DbSession,
    actor: ActiveActor,
    project_id: uuid.UUID | None = None,
    owner_user_id: uuid.UUID | None = None,
    owner: Literal["me"] | None = None,
    status: schemas.Status | None = None,
    due_state: schemas.DueState | None = None,
    source_type: schemas.Source | None = None,
    source_key: str | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> schemas.ActionPage:
    scope = permissions.project_scope(actor, project_id)
    if owner and owner_user_id and owner_user_id != actor.user_id:
        raise ValidationError("Choose My Actions or a specific owner, not both.")
    today = datetime.now(UTC).date()
    ids = repository.filtered(
        scope,
        today,
        owner_user_id=actor.user_id if owner else owner_user_id,
        status=status,
        due=due_state,
        source_type=source_type,
        source_key=source_key,
    )
    return repository.page(session, ids, today, limit=limit, offset=offset)


@router.get("/assignees", response_model=list[schemas.Identity])
def assignees(
    project_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
    limit: Limit = 100,
    offset: Offset = 0,
) -> list[schemas.Identity]:
    permissions.require_writer(actor)
    permissions.require_project(session, actor, project_id)
    return [
        schemas.Identity(user_id=row.id, display_name=row.display_name)
        for row in session.execute(
            permissions.eligible_users(project_id)
            .order_by(User.display_name, User.id)
            .limit(limit)
            .offset(offset)
        )
    ]


@router.get("/owners", response_model=list[schemas.Identity])
def owners(
    session: DbSession,
    actor: ActiveActor,
    project_id: uuid.UUID | None = None,
    limit: Limit = 100,
    offset: Offset = 0,
) -> list[schemas.Identity]:
    """Read-filter values from authorized actions, not a write-support directory."""
    ids = select(Action.owner_user_id).where(
        Action.project_id.in_(permissions.project_scope(actor, project_id))
    )
    return [
        schemas.Identity(user_id=row.id, display_name=row.display_name)
        for row in session.execute(
            select(User.id, User.display_name)
            .where(User.id.in_(ids))
            .order_by(User.display_name, User.id)
            .limit(limit)
            .offset(offset)
        )
    ]


@router.get("/projects")
def projects(
    session: DbSession, actor: ActiveActor, limit: Limit = 100, offset: Offset = 0
) -> dict:
    scope = permissions.project_scope(actor)
    rows = session.execute(
        select(Project.id, Project.code, Project.name)
        .where(Project.id.in_(scope))
        .order_by(Project.code, Project.id)
        .offset(offset)
        .limit(limit)
    )
    return {
        "items": [dict(row._mapping) for row in rows],
        "total": session.scalar(select(func.count()).select_from(scope.subquery())),
    }


@router.get("/summary")
def summary(session: DbSession, actor: ActiveActor, project_id: uuid.UUID | None = None) -> dict:
    if project_id is not None:
        permissions.require_project(session, actor, project_id)
    return batch.summary(
        session, permissions.project_scope(actor, project_id), datetime.now(UTC).date()
    )


def response(session: DbSession, actor: ActiveActor, action_id: uuid.UUID) -> schemas.ActionOut:
    ids = select(Action.id).where(
        Action.id == action_id, Action.project_id.in_(permissions.project_scope(actor))
    )
    rows = repository.records(session, ids, datetime.now(UTC).date(), limit=1, offset=0)
    if not rows:
        raise NotFoundError("Management action not found.")
    return rows[0]


@router.post("", response_model=schemas.ActionOut, status_code=201)
def create_action(
    payload: schemas.Create, session: DbSession, actor: ActiveActor
) -> schemas.ActionOut:
    permissions.require_writer(actor)
    permissions.require_project(session, actor, payload.project_id, lock=True)
    action_sources.validate(
        session,
        permissions.project_scope(actor, payload.project_id),
        datetime.now(UTC).date(),
        payload.source_type,
        payload.source_code,
        payload.source_key,
        payload.source_observation_date,
    )
    action = service.create(session, actor, payload)
    return response(session, actor, action.id)


@router.get("/{action_id}", response_model=schemas.ActionOut)
def detail(action_id: uuid.UUID, session: DbSession, actor: ActiveActor) -> schemas.ActionOut:
    return response(session, actor, action_id)


@router.get("/{action_id}/source")
def source(action_id: uuid.UUID, session: DbSession, actor: ActiveActor) -> dict:
    action = repository.find(session, permissions.project_scope(actor), action_id)
    if action.source_type == "manual":
        return {"state": "manual", "title": "Manual management commitment", "drilldown": None}
    current = action_sources.current_source(
        session,
        permissions.project_scope(actor, action.project_id),
        datetime.now(UTC).date(),
        action.source_type,
        action.source_code,
        action.source_key,
    )
    return current or {
        "state": "unavailable",
        "title": "Source no longer reported or unavailable. Action workflow is unchanged.",
        "drilldown": None,
    }


@router.patch("/{action_id}", response_model=schemas.ActionOut)
def update(
    action_id: uuid.UUID, payload: schemas.Patch, session: DbSession, actor: ActiveActor
) -> schemas.ActionOut:
    service.patch(session, actor, action_id, payload)
    return response(session, actor, action_id)


@router.post("/{action_id}/transitions", response_model=schemas.ActionOut)
def transition(
    action_id: uuid.UUID, payload: schemas.Transition, session: DbSession, actor: ActiveActor
) -> schemas.ActionOut:
    service.transition(session, actor, action_id, payload)
    return response(session, actor, action_id)


@router.get("/{action_id}/history", response_model=schemas.HistoryPage)
def history(
    action_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
    limit: Limit = 20,
    offset: Offset = 0,
) -> schemas.HistoryPage:
    action = repository.find(session, permissions.project_scope(actor), action_id)
    rows = session.execute(
        select(History, User.display_name)
        .join(User, User.id == History.actor_user_id)
        .where(History.action_id == action.id)
        .order_by(History.version)
        .offset(offset)
        .limit(limit)
    )
    return schemas.HistoryPage(
        items=[
            schemas.HistoryOut(
                id=row.id,
                version=row.version,
                actor=schemas.Identity(user_id=row.actor_user_id, display_name=name),
                occurred_at=row.occurred_at,
                event_type=row.event_type,
                reason=row.reason,
                changes=row.changes,
            )
            for row, name in rows
        ],
        total=session.scalar(select(func.count(History.id)).where(History.action_id == action.id)),
        limit=limit,
        offset=offset,
    )
