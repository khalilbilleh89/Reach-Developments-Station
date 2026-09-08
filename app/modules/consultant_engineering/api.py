"""Project-scoped Consultant Engineer routes."""

# FastAPI validates each public route against its explicit ``response_model``.
# ruff: noqa: ANN201

import uuid

from fastapi import APIRouter, status

from app.modules.access.dependencies import ActiveActor, DbSession
from app.modules.consultant_engineering import schemas, service
from app.modules.consultant_engineering.permissions import ConsultantProject

router = APIRouter(
    prefix="/projects/{project_id}/consultant-engineering", tags=["consultant-engineering"]
)


@router.get("", response_model=schemas.WorkspaceOut)
def read_workspace(project: ConsultantProject, session: DbSession) -> schemas.WorkspaceOut:
    return service.workspace(session, project)


@router.post(
    "/engagements", response_model=schemas.EngagementOut, status_code=status.HTTP_201_CREATED
)
def create_engagement(
    project: ConsultantProject,
    payload: schemas.EngagementCreate,
    session: DbSession,
    actor: ActiveActor,
):
    return service.create_engagement(session, project, actor, payload)


@router.put("/engagements/{engagement_id}", response_model=schemas.EngagementOut)
def update_engagement(
    project: ConsultantProject,
    engagement_id: uuid.UUID,
    payload: schemas.EngagementUpdate,
    session: DbSession,
    actor: ActiveActor,
):
    return service.update_engagement(session, project, actor, engagement_id, payload)


@router.post("/engagements/{engagement_id}/activate", response_model=schemas.EngagementOut)
def activate_engagement(
    project: ConsultantProject, engagement_id: uuid.UUID, session: DbSession, actor: ActiveActor
):
    return service.transition_engagement(session, project, actor, engagement_id, "active")


@router.post("/engagements/{engagement_id}/complete", response_model=schemas.EngagementOut)
def complete_engagement(
    project: ConsultantProject, engagement_id: uuid.UUID, session: DbSession, actor: ActiveActor
):
    return service.transition_engagement(session, project, actor, engagement_id, "completed")


@router.post("/engagements/{engagement_id}/terminate", response_model=schemas.EngagementOut)
def terminate_engagement(
    project: ConsultantProject, engagement_id: uuid.UUID, session: DbSession, actor: ActiveActor
):
    return service.transition_engagement(session, project, actor, engagement_id, "terminated")


@router.post(
    "/engagements/{engagement_id}/disciplines",
    response_model=schemas.DisciplineOut,
    status_code=status.HTTP_201_CREATED,
)
def create_discipline(
    project: ConsultantProject,
    engagement_id: uuid.UUID,
    payload: schemas.DisciplineWrite,
    session: DbSession,
    actor: ActiveActor,
):
    return service.create_discipline(session, project, actor, engagement_id, payload)


@router.put("/disciplines/{discipline_id}", response_model=schemas.DisciplineOut)
def update_discipline(
    project: ConsultantProject,
    discipline_id: uuid.UUID,
    payload: schemas.DisciplineWrite,
    session: DbSession,
    actor: ActiveActor,
):
    return service.update_discipline(session, project, actor, discipline_id, payload)


@router.post(
    "/engagements/{engagement_id}/stages",
    response_model=schemas.StageOut,
    status_code=status.HTTP_201_CREATED,
)
def create_stage(
    project: ConsultantProject,
    engagement_id: uuid.UUID,
    payload: schemas.StageWrite,
    session: DbSession,
    actor: ActiveActor,
):
    return service.create_stage(session, project, actor, engagement_id, payload)


@router.put("/stages/{stage_id}", response_model=schemas.StageOut)
def update_stage(
    project: ConsultantProject,
    stage_id: uuid.UUID,
    payload: schemas.StageUpdate,
    session: DbSession,
    actor: ActiveActor,
):
    return service.update_stage(session, project, actor, stage_id, payload)


@router.post(
    "/engagements/{engagement_id}/deliverables",
    response_model=schemas.DeliverableOut,
    status_code=status.HTTP_201_CREATED,
)
def create_deliverable(
    project: ConsultantProject,
    engagement_id: uuid.UUID,
    payload: schemas.DeliverableWrite,
    session: DbSession,
    actor: ActiveActor,
):
    return service.create_deliverable(session, project, actor, engagement_id, payload)


@router.put("/deliverables/{deliverable_id}", response_model=schemas.DeliverableOut)
def update_deliverable(
    project: ConsultantProject,
    deliverable_id: uuid.UUID,
    payload: schemas.DeliverableUpdate,
    session: DbSession,
    actor: ActiveActor,
):
    return service.update_deliverable(session, project, actor, deliverable_id, payload)
