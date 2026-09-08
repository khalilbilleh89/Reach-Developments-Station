"""GET-only project analysis. Authorization precedes every source query."""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.modules.access.dependencies import ActiveActor, DbSession
from app.modules.project_analysis import schemas, service
from app.modules.project_analysis.permissions import AnalysisProject, require_section

router = APIRouter(prefix="/projects/{project_id}/analysis", tags=["project-analysis"])


def read_context(
    project: AnalysisProject,
    session: DbSession,
    as_of: Annotated[date | None, Query()] = None,
    period_from: Annotated[date | None, Query()] = None,
    period_to: Annotated[date | None, Query()] = None,
    phase_id: Annotated[uuid.UUID | None, Query()] = None,
    building_id: Annotated[uuid.UUID | None, Query()] = None,
) -> schemas.Context:
    return service.context(session, project, as_of, period_from, period_to, phase_id, building_id)


ReadContext = Annotated[schemas.Context, Depends(read_context)]


@router.get("/fundamental", response_model=schemas.Fundamental)
def fundamental(
    project: AnalysisProject, session: DbSession, actor: ActiveActor, context: ReadContext
) -> schemas.Fundamental:
    require_section(actor, "fundamental")
    return service.fundamental(session, project, context)


@router.get("/financial", response_model=schemas.Financial)
def financial(
    project: AnalysisProject, session: DbSession, actor: ActiveActor, context: ReadContext
) -> schemas.Financial:
    require_section(actor, "financial")
    return service.financial(session, project, context)


@router.get("/technical", response_model=schemas.Technical)
def technical(
    project: AnalysisProject, session: DbSession, actor: ActiveActor, context: ReadContext
) -> schemas.Technical:
    require_section(actor, "technical")
    return service.technical(session, project, context)
