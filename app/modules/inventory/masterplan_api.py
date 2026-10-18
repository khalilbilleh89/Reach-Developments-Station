"""Drawing and footprint routes. All access includes the whole-project image boundary."""

import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Query, Request, Response
from pydantic import ValidationError as InputError
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.core.errors import ValidationError
from app.modules.access.dependencies import ActiveActor, DbSession
from app.modules.inventory import masterplans as service
from app.modules.inventory.models import Masterplan
from app.modules.inventory.permissions import InventoryProject

router = APIRouter(prefix="/projects/{project_id}/inventory/masterplans", tags=["inventory"])


@router.get("", response_model=list[service.PlanRead])
def list_plans(
    project: InventoryProject, session: DbSession, actor: ActiveActor
) -> list[Masterplan]:
    service.require_scope(session, project.id, actor)
    return list(
        session.scalars(
            select(Masterplan)
            .where(Masterplan.project_id == project.id)
            .order_by(Masterplan.title, Masterplan.id)
        )
    )


@router.post("", response_model=service.PlanRead, status_code=201)
async def create_plan(
    request: Request,
    project: InventoryProject,
    session: DbSession,
    actor: ActiveActor,
    title: Annotated[str, Query(min_length=1, max_length=200)],
    source_reference: Annotated[str, Query(min_length=1, max_length=500)],
    filename: Annotated[str, Query(min_length=1, max_length=1024)],
    kind: str = "plan",
    width_m: str | None = None,
    page_number: Annotated[int, Query(ge=0, le=999)] = 0,
) -> Masterplan:
    service.writable(session, project.id, actor)
    try:
        payload = service.PlanInput(
            title=title, source_reference=source_reference, kind=kind, width_m=width_m
        )
    except InputError as exc:
        raise ValidationError(
            "Check title, drawing reference, view type and measured width."
        ) from exc
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > service.MAX_BYTES:
            raise ValidationError("Drawing must be at most 10 MiB.")
        body.extend(chunk)
    return await run_in_threadpool(
        service.create_plan, session, project.id, actor, payload, filename, page_number, bytes(body)
    )


@router.put("/{plan_id}", response_model=service.PlanRead)
def update_plan(
    plan_id: uuid.UUID,
    payload: service.PlanUpdate,
    project: InventoryProject,
    session: DbSession,
    actor: ActiveActor,
) -> Masterplan:
    return service.update_plan(session, project.id, actor, plan_id, payload)


@router.get("/{plan_id}/preview")
def preview(
    plan_id: uuid.UUID, project: InventoryProject, session: DbSession, actor: ActiveActor
) -> Response:
    service.require_scope(session, project.id, actor)
    return Response(
        service.preview(session, project.id, plan_id),
        media_type="image/png",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/{plan_id}/mappings", response_model=list[service.MappingRead])
def list_mappings(
    plan_id: uuid.UUID, project: InventoryProject, session: DbSession, actor: ActiveActor
) -> list:
    service.require_scope(session, project.id, actor)
    service.get_plan(session, project.id, plan_id)
    return service.mappings(session, project.id, plan_id)


@router.get("/{plan_id}/source")
def source(
    plan_id: uuid.UUID, project: InventoryProject, session: DbSession, actor: ActiveActor
) -> Response:
    service.require_scope(session, project.id, actor)
    filename, data = service.source(session, project.id, plan_id)
    return Response(
        data,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename, safe='')}",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/{plan_id}/mappings", response_model=service.MappingRead, status_code=201)
def create_mapping(
    plan_id: uuid.UUID,
    payload: service.MappingInput,
    project: InventoryProject,
    session: DbSession,
    actor: ActiveActor,
) -> object:
    return service.save_mapping(session, project.id, actor, plan_id, payload)


@router.put("/{plan_id}/mappings/{mapping_id}", response_model=service.MappingRead)
def update_mapping(
    plan_id: uuid.UUID,
    mapping_id: uuid.UUID,
    payload: service.MappingUpdate,
    project: InventoryProject,
    session: DbSession,
    actor: ActiveActor,
) -> object:
    return service.save_mapping(session, project.id, actor, plan_id, payload, mapping_id)


@router.delete("/{plan_id}", status_code=204)
def delete_plan(
    plan_id: uuid.UUID,
    project: InventoryProject,
    session: DbSession,
    actor: ActiveActor,
    version: Annotated[int, Query(ge=1)],
    reason: Annotated[str, Query(min_length=1, max_length=500)],
) -> None:
    service.delete(session, project.id, actor, plan_id, version, reason)


@router.delete("/{plan_id}/mappings/{mapping_id}", status_code=204)
def delete_mapping(
    plan_id: uuid.UUID,
    mapping_id: uuid.UUID,
    project: InventoryProject,
    session: DbSession,
    actor: ActiveActor,
    version: Annotated[int, Query(ge=1)],
    reason: Annotated[str, Query(min_length=1, max_length=500)],
) -> None:
    service.delete(session, project.id, actor, plan_id, version, reason, mapping_id)
