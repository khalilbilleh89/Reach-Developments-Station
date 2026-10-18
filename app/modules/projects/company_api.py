"""Company information and bank instructions; no money movement is recorded here."""

import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request, Response
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.modules.access.dependencies import ActiveActor, DbSession
from app.modules.projects import company_document_service as documents
from app.modules.projects import company_service as service
from app.modules.projects.company_models import CompanyBankAccount, ProjectCompany
from app.modules.projects.company_schemas import (
    BankAccountRead,
    BankAccountWrite,
    CompanyDetail,
    CompanyWrite,
    DocumentRead,
    DocumentRemoval,
    DocumentUpdate,
    DocumentUpload,
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


@router.get("/{company_id}/documents", response_model=list[DocumentRead])
def list_company_documents(
    project_id: uuid.UUID, company_id: uuid.UUID, session: DbSession, actor: ActiveActor
) -> list[DocumentRead]:
    service.scope(session, project_id, actor)
    service.company(session, project_id, company_id)
    return documents.list_documents(session, company_id)


@router.post("/{company_id}/documents", response_model=DocumentRead, status_code=201)
async def create_company_document(
    project_id: uuid.UUID,
    company_id: uuid.UUID,
    fields: Annotated[DocumentUpload, Query()],
    request: Request,
    session: DbSession,
    actor: ActiveActor,
) -> DocumentRead:
    await run_in_threadpool(documents.authorize_upload, session, project_id, company_id, actor)
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > documents.MAX_DOCUMENT_BYTES:
            raise HTTPException(
                status_code=413, detail="PDF documents must be no larger than 10 MB."
            )
        data.extend(chunk)
    row = await run_in_threadpool(
        documents.create_locked,
        session,
        project_id,
        company_id,
        actor,
        fields.label,
        fields.filename,
        bytes(data),
    )
    return DocumentRead.model_validate(row)


@router.patch("/{company_id}/documents/{document_id}", response_model=DocumentRead)
def update_company_document(
    project_id: uuid.UUID,
    company_id: uuid.UUID,
    document_id: uuid.UUID,
    body: DocumentUpdate,
    session: DbSession,
    actor: ActiveActor,
) -> DocumentRead:
    service.scope(session, project_id, actor, write=True)
    service.company(session, project_id, company_id)
    row = documents.document(session, company_id, document_id)
    documents.change(session, row, actor, body.expected_version, label=body.label)
    return DocumentRead.model_validate(row)


@router.get("/{company_id}/documents/{document_id}/file")
def download_company_document(
    project_id: uuid.UUID,
    company_id: uuid.UUID,
    document_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
) -> Response:
    service.scope(session, project_id, actor)
    service.company(session, project_id, company_id)
    row = documents.document(session, company_id, document_id)
    return Response(
        content=row.document,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(row.filename, safe='')}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.post("/{company_id}/documents/{document_id}/delete", status_code=204)
def delete_company_document(
    project_id: uuid.UUID,
    company_id: uuid.UUID,
    document_id: uuid.UUID,
    body: DocumentRemoval,
    session: DbSession,
    actor: ActiveActor,
) -> Response:
    service.scope(session, project_id, actor, write=True)
    service.company(session, project_id, company_id)
    documents.change(
        session,
        documents.document(session, company_id, document_id),
        actor,
        body.expected_version,
        reason=body.reason,
    )
    return Response(status_code=204)
