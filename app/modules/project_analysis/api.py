"""GET-only project analysis. Authorization precedes every source query."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query

from app.modules.access.dependencies import ActiveActor, DbSession
from app.modules.project_analysis import feasibility as feasibility_service
from app.modules.project_analysis import report, schemas, service
from app.modules.project_analysis.permissions import AnalysisProject, require_section
from app.modules.project_analysis.report_schemas import AnalyticsReport

router = APIRouter(prefix="/projects/{project_id}/analysis", tags=["project-analysis"])


@router.get("/report", response_model=AnalyticsReport)
def analytics_report(
    project: AnalysisProject,
    session: DbSession,
    actor: ActiveActor,
    period_from: Annotated[date | None, Query()] = None,
    period_to: Annotated[date | None, Query()] = None,
    threshold: Annotated[
        Decimal, Query(ge=0, le=Decimal("999999999999.99"), max_digits=14, decimal_places=2)
    ] = Decimal("400000"),
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
) -> AnalyticsReport:
    require_section(actor, "financial")
    return report.read(session, project, period_from, period_to, threshold, currency)


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
