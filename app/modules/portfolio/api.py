"""Four GET routes. Authorization precedes every source query."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.core.errors import NotFoundError, ValidationError
from app.modules.access.dependencies import ActiveActor, DbSession
from app.modules.portfolio import (
    outlook,
    outlook_schemas,
    permissions,
    risk_projection,
    schemas,
    service,
)
from app.modules.projects.models import Project

router = APIRouter(prefix="/portfolio", tags=["portfolio"])
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


@router.get("/outlook", response_model=outlook_schemas.Outlook)
def forward_outlook(
    session: DbSession,
    actor: ActiveActor,
    horizon_days: int = 90,
    project_id: uuid.UUID | None = None,
    item_type: outlook_schemas.Kind | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> outlook_schemas.Outlook:
    scope = permissions.authorized_projects(actor)
    if horizon_days not in {30, 60, 90}:
        raise ValidationError("Outlook horizon must be 30, 60 or 90 days.")
    if project_id:
        scope = scope.where(Project.id == project_id)
    return outlook.page(
        session,
        scope,
        datetime.now(UTC).date(),
        horizon_days=horizon_days,
        limit=limit,
        offset=offset,
        item_type=item_type,
    )


@router.get("/overview", response_model=schemas.Overview)
def overview(session: DbSession, actor: ActiveActor) -> schemas.Overview:
    scope = permissions.authorized_projects(actor)
    today = datetime.now(UTC).date()
    return service.overview(service.summaries(session, scope, today), today)


@router.get("/projects", response_model=schemas.ProjectPage)
def projects(
    session: DbSession, actor: ActiveActor, limit: Limit = 20, offset: Offset = 0
) -> schemas.ProjectPage:
    scope = permissions.authorized_projects(actor)
    total = session.scalar(select(func.count()).select_from(scope.subquery()))
    page = scope.order_by(Project.code, Project.id).offset(offset).limit(limit)
    today = datetime.now(UTC).date()
    return schemas.ProjectPage(
        as_of=today,
        items=service.summaries(session, page, today),
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/risks", response_model=schemas.RiskPage)
def risks(
    session: DbSession, actor: ActiveActor, limit: Limit = 20, offset: Offset = 0
) -> schemas.RiskPage:
    scope = permissions.authorized_projects(actor)
    today = datetime.now(UTC).date()
    return risk_projection.page(session, scope, today, limit=limit, offset=offset)


@router.get("/projects/{project_id}", response_model=schemas.ProjectSummary)
def project_detail(
    project_id: uuid.UUID, session: DbSession, actor: ActiveActor
) -> schemas.ProjectSummary:
    scope = permissions.authorized_projects(actor).where(Project.id == project_id)
    rows = service.summaries(session, scope, datetime.now(UTC).date())
    if not rows:
        raise NotFoundError("Portfolio project not found.")
    return rows[0]
