"""Marketing routes; scope is checked before reading any project record."""

import uuid
from typing import Literal

from fastapi import APIRouter, Query, Response

from app.modules.access.dependencies import ActiveActor, DbSession
from app.modules.inventory.service import marketing_unit_references
from app.modules.marketing import service
from app.modules.marketing.models import MarketIndicator, RentalScenario
from app.modules.marketing.permissions import scope
from app.modules.marketing.schemas import (
    Bio,
    Branding,
    ContentRead,
    ContentWrite,
    IndicatorRead,
    IndicatorWrite,
    Removal,
    ScenarioRead,
    ScenarioWrite,
    UnitRegister,
)

router = APIRouter(prefix="/projects/{project_id}/marketing", tags=["marketing"])


class BioWrite(ContentWrite):
    data: Bio


class BrandWrite(ContentWrite):
    data: Branding


@router.get("/content/{kind}", response_model=ContentRead)
def read_content(
    project_id: uuid.UUID, kind: Literal["bio", "branding"], session: DbSession, actor: ActiveActor
) -> ContentRead:
    scope(session, project_id, actor)
    return service.read_content(session, project_id, kind)


@router.put("/content/bio", response_model=ContentRead)
def create_bio(
    project_id: uuid.UUID, body: BioWrite, session: DbSession, actor: ActiveActor
) -> ContentRead:
    scope(session, project_id, actor, write=True)
    return service.save_content(session, project_id, "bio", body.data, body.expected_version, actor)


@router.put("/content/branding", response_model=ContentRead)
def create_branding(
    project_id: uuid.UUID, body: BrandWrite, session: DbSession, actor: ActiveActor
) -> ContentRead:
    scope(session, project_id, actor, write=True)
    return service.save_content(
        session, project_id, "branding", body.data, body.expected_version, actor
    )


@router.post("/content/{kind}/delete", status_code=204)
def delete_content(
    project_id: uuid.UUID,
    kind: Literal["bio", "branding"],
    body: Removal,
    session: DbSession,
    actor: ActiveActor,
) -> Response:
    scope(session, project_id, actor, write=True)
    service.remove(session, service.current_content(session, project_id, kind), body, actor)
    return Response(status_code=204)


@router.get("/scenarios", response_model=list[ScenarioRead])
def scenarios(project_id: uuid.UUID, session: DbSession, actor: ActiveActor) -> list[ScenarioRead]:
    scope(session, project_id, actor)
    rows = service.list_scenarios(session, project_id)
    names = marketing_unit_references(
        session, project_id=project_id, unit_ids=[r.unit_id for r in rows if r.unit_id]
    )
    return [
        ScenarioRead.model_validate(row).model_copy(
            update={"unit_reference": names.get(row.unit_id)}
        )
        for row in rows
    ]


@router.post("/scenarios", response_model=ScenarioRead, status_code=201)
def create_scenario(
    project_id: uuid.UUID, body: ScenarioWrite, session: DbSession, actor: ActiveActor
) -> RentalScenario:
    project = scope(session, project_id, actor, write=True)
    return service.save_scenario(session, project, body, actor)


@router.put("/scenarios/{record_id}", response_model=ScenarioRead)
def update_scenario(
    project_id: uuid.UUID,
    record_id: uuid.UUID,
    body: ScenarioWrite,
    session: DbSession,
    actor: ActiveActor,
) -> RentalScenario:
    project = scope(session, project_id, actor, write=True)
    return service.save_scenario(session, project, body, actor, record_id)


@router.post("/scenarios/{record_id}/delete", status_code=204)
def delete_scenario(
    project_id: uuid.UUID,
    record_id: uuid.UUID,
    body: Removal,
    session: DbSession,
    actor: ActiveActor,
) -> Response:
    scope(session, project_id, actor, write=True)
    service.remove(
        session, service.get_record(session, project_id, record_id, RentalScenario), body, actor
    )
    return Response(status_code=204)


@router.get("/indicators", response_model=list[IndicatorRead])
def indicators(
    project_id: uuid.UUID, session: DbSession, actor: ActiveActor
) -> list[MarketIndicator]:
    scope(session, project_id, actor)
    return service.list_indicators(session, project_id)


@router.post("/indicators", response_model=IndicatorRead, status_code=201)
def create_indicator(
    project_id: uuid.UUID, body: IndicatorWrite, session: DbSession, actor: ActiveActor
) -> MarketIndicator:
    scope(session, project_id, actor, write=True)
    return service.save_indicator(session, project_id, body, actor)


@router.put("/indicators/{record_id}", response_model=IndicatorRead)
def update_indicator(
    project_id: uuid.UUID,
    record_id: uuid.UUID,
    body: IndicatorWrite,
    session: DbSession,
    actor: ActiveActor,
) -> MarketIndicator:
    scope(session, project_id, actor, write=True)
    return service.save_indicator(session, project_id, body, actor, record_id)


@router.post("/indicators/{record_id}/delete", status_code=204)
def delete_indicator(
    project_id: uuid.UUID,
    record_id: uuid.UUID,
    body: Removal,
    session: DbSession,
    actor: ActiveActor,
) -> Response:
    scope(session, project_id, actor, write=True)
    service.remove(
        session, service.get_record(session, project_id, record_id, MarketIndicator), body, actor
    )
    return Response(status_code=204)


@router.get("/units", response_model=UnitRegister)
def units(
    project_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
    search: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> UnitRegister:
    project = scope(session, project_id, actor)
    return service.projections(session, project, actor, search=search, limit=limit, offset=offset)
