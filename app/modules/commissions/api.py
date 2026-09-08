"""Project commission distribution routes."""

# FastAPI validates each public route against its explicit ``response_model``.
# ruff: noqa: ANN201

import uuid

from fastapi import APIRouter, status

from app.modules.access.dependencies import ActiveActor, DbSession
from app.modules.commissions import schemas, service
from app.modules.commissions.permissions import CommissionProject

router = APIRouter(prefix="/projects/{project_id}/commissions", tags=["commissions"])


@router.get("", response_model=list[schemas.GrantOut])
def list_grants(project: CommissionProject, session: DbSession):
    return service.list_grants(session, project)


@router.get("/eligible-sales", response_model=list[schemas.EligibleSaleOut])
def eligible_sales(project: CommissionProject, session: DbSession):
    return service.eligible_sales(session, project)


@router.post("", response_model=schemas.GrantOut, status_code=status.HTTP_201_CREATED)
def create_grant(
    project: CommissionProject, payload: schemas.GrantCreate, session: DbSession, actor: ActiveActor
):
    return service.create(session, project, actor, payload)


@router.get("/{commission_id}", response_model=schemas.GrantOut)
def read_grant(project: CommissionProject, commission_id: uuid.UUID, session: DbSession):
    return service.out(session, service._get(session, project, commission_id))


@router.put("/{commission_id}", response_model=schemas.GrantOut)
def update_grant(
    project: CommissionProject,
    commission_id: uuid.UUID,
    payload: schemas.GrantUpdate,
    session: DbSession,
    actor: ActiveActor,
):
    return service.update(session, project, actor, commission_id, payload)


@router.post("/{commission_id}/allocations", response_model=schemas.GrantOut)
def add_allocation(
    project: CommissionProject,
    commission_id: uuid.UUID,
    payload: schemas.AllocationWrite,
    session: DbSession,
    actor: ActiveActor,
):
    return service.add_allocation(session, project, actor, commission_id, payload)


@router.put("/{commission_id}/allocations/{allocation_id}", response_model=schemas.GrantOut)
def update_allocation(
    project: CommissionProject,
    commission_id: uuid.UUID,
    allocation_id: uuid.UUID,
    payload: schemas.AllocationUpdate,
    session: DbSession,
    actor: ActiveActor,
):
    return service.update_allocation(session, project, actor, commission_id, allocation_id, payload)


@router.delete("/{commission_id}/allocations/{allocation_id}", response_model=schemas.GrantOut)
def remove_allocation(
    project: CommissionProject,
    commission_id: uuid.UUID,
    allocation_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
):
    return service.remove_allocation(session, project, actor, commission_id, allocation_id)


@router.post("/{commission_id}/release", response_model=schemas.GrantOut)
def release(
    project: CommissionProject, commission_id: uuid.UUID, session: DbSession, actor: ActiveActor
):
    return service.release(session, project, actor, commission_id)


@router.post("/{commission_id}/reverse", response_model=schemas.GrantOut)
def reverse(
    project: CommissionProject,
    commission_id: uuid.UUID,
    payload: schemas.ReasonRequest,
    session: DbSession,
    actor: ActiveActor,
):
    return service.reverse(session, project, actor, commission_id, payload.reason)
