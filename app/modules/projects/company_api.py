"""Company information and bank instructions; no money movement is recorded here."""

import uuid

from fastapi import APIRouter, Response
from sqlalchemy import select

from app.modules.access.dependencies import ActiveActor, DbSession
from app.modules.projects import company_service as service
from app.modules.projects.company_models import CompanyBankAccount, ProjectCompany
from app.modules.projects.company_schemas import (
    BankAccountRead,
    BankAccountWrite,
    CompanyDetail,
    CompanyWrite,
    RemovalRequest,
)

router = APIRouter(prefix="/projects/{project_id}/companies", tags=["companies"])


@router.get("", response_model=list[CompanyDetail])
def list_companies(
    project_id: uuid.UUID, session: DbSession, actor: ActiveActor
) -> list[CompanyDetail]:
    service.scope(session, project_id, actor)
    rows = session.scalars(
        select(ProjectCompany)
        .where(ProjectCompany.project_id == project_id, ProjectCompany.is_deleted.is_(False))
        .order_by(ProjectCompany.created_at, ProjectCompany.id)
    ).all()
    return [service.detail(session, row) for row in rows]


@router.post("", response_model=CompanyDetail, status_code=201)
def create_company(
    project_id: uuid.UUID, body: CompanyWrite, session: DbSession, actor: ActiveActor
) -> CompanyDetail:
    service.scope(session, project_id, actor, write=True)
    row = ProjectCompany(project_id=project_id)
    service.save(session, row, body.model_dump(), actor, creating=True)
    return service.detail(session, row)


@router.patch("/{company_id}", response_model=CompanyDetail)
def update_company(
    project_id: uuid.UUID,
    company_id: uuid.UUID,
    body: CompanyWrite,
    session: DbSession,
    actor: ActiveActor,
) -> CompanyDetail:
    service.scope(session, project_id, actor, write=True)
    row = service.company(session, project_id, company_id)
    service.save(session, row, body.model_dump(exclude_unset=True), actor, creating=False)
    return service.detail(session, row)


@router.post("/{company_id}/delete", status_code=204)
def delete_company(
    project_id: uuid.UUID,
    company_id: uuid.UUID,
    body: RemovalRequest,
    session: DbSession,
    actor: ActiveActor,
) -> Response:
    service.scope(session, project_id, actor, write=True)
    service.remove(session, service.company(session, project_id, company_id), actor, body.reason)
    return Response(status_code=204)


@router.post("/{company_id}/bank-accounts", response_model=BankAccountRead, status_code=201)
def create_bank_account(
    project_id: uuid.UUID,
    company_id: uuid.UUID,
    body: BankAccountWrite,
    session: DbSession,
    actor: ActiveActor,
) -> BankAccountRead:
    service.scope(session, project_id, actor, write=True)
    service.company(session, project_id, company_id)
    row = CompanyBankAccount(company_id=company_id)
    service.save(session, row, body.model_dump(), actor, creating=True)
    return BankAccountRead.model_validate(row)


@router.patch("/{company_id}/bank-accounts/{account_id}", response_model=BankAccountRead)
def update_bank_account(
    project_id: uuid.UUID,
    company_id: uuid.UUID,
    account_id: uuid.UUID,
    body: BankAccountWrite,
    session: DbSession,
    actor: ActiveActor,
) -> BankAccountRead:
    service.scope(session, project_id, actor, write=True)
    service.company(session, project_id, company_id)
    row = service.account(session, company_id, account_id)
    service.save(session, row, body.model_dump(exclude_unset=True), actor, creating=False)
    return BankAccountRead.model_validate(row)


@router.post("/{company_id}/bank-accounts/{account_id}/delete", status_code=204)
def delete_bank_account(
    project_id: uuid.UUID,
    company_id: uuid.UUID,
    account_id: uuid.UUID,
    body: RemovalRequest,
    session: DbSession,
    actor: ActiveActor,
) -> Response:
    service.scope(session, project_id, actor, write=True)
    service.company(session, project_id, company_id)
    service.remove(session, service.account(session, company_id, account_id), actor, body.reason)
    return Response(status_code=204)
