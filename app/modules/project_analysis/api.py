"""GET-only project analysis. Authorization precedes every source query."""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.modules.access.dependencies import ActiveActor, DbSession
from app.modules.project_analysis import feasibility as feasibility_service
from app.modules.project_analysis import schemas, service
from app.modules.project_analysis.permissions import AnalysisProject, require_section

router = APIRouter(prefix="/projects/{project_id}/analysis", tags=["project-analysis"])


@router.get("/feasibility", response_model=feasibility_service.Feasibility)
def feasibility(
    project: AnalysisProject,
    session: DbSession,
    actor: ActiveActor,
    as_of: Annotated[date | None, Query()] = None,
    period_from: Annotated[date | None, Query()] = None,
    period_to: Annotated[date | None, Query()] = None,
    phase_id: Annotated[uuid.UUID | None, Query()] = None,
    building_id: Annotated[uuid.UUID | None, Query()] = None,
) -> feasibility_service.Feasibility:
    require_section(actor, "feasibility")
    context = service.context(
        session, project, as_of, period_from, period_to, phase_id, building_id
    )
    return feasibility_service.read(session, context)


@router.get("/fundamental", response_model=schemas.Fundamental)
def fundamental(
    project: AnalysisProject,
    session: DbSession,
    actor: ActiveActor,
    as_of: Annotated[date | None, Query()] = None,
    period_from: Annotated[date | None, Query()] = None,
    period_to: Annotated[date | None, Query()] = None,
    phase_id: Annotated[uuid.UUID | None, Query()] = None,
    building_id: Annotated[uuid.UUID | None, Query()] = None,
) -> schemas.Fundamental:
    require_section(actor, "fundamental")
    context = service.context(
        session, project, as_of, period_from, period_to, phase_id, building_id
    )
    return service.fundamental(session, project, context)


@router.get("/financial", response_model=schemas.Financial)
def financial(
    project: AnalysisProject,
    session: DbSession,
    actor: ActiveActor,
    as_of: Annotated[date | None, Query()] = None,
    period_from: Annotated[date | None, Query()] = None,
    period_to: Annotated[date | None, Query()] = None,
    phase_id: Annotated[uuid.UUID | None, Query()] = None,
    building_id: Annotated[uuid.UUID | None, Query()] = None,
) -> schemas.Financial:
    require_section(actor, "financial")
    context = service.context(
        session, project, as_of, period_from, period_to, phase_id, building_id
    )
    return service.financial(session, project, context)


@router.get("/technical", response_model=schemas.Technical)
def technical(
    project: AnalysisProject,
    session: DbSession,
    actor: ActiveActor,
    as_of: Annotated[date | None, Query()] = None,
    period_from: Annotated[date | None, Query()] = None,
    period_to: Annotated[date | None, Query()] = None,
    phase_id: Annotated[uuid.UUID | None, Query()] = None,
    building_id: Annotated[uuid.UUID | None, Query()] = None,
) -> schemas.Technical:
    require_section(actor, "technical")
    context = service.context(
        session, project, as_of, period_from, period_to, phase_id, building_id
    )
    return service.technical(session, project, context)
