"""Project-scoped Consultant Engineer routes."""

# FastAPI validates each public route against its explicit ``response_model``.
# ruff: noqa: ANN201

import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.modules.access.dependencies import ActiveActor, ActorContext, DbSession
from app.modules.cashflow import permissions as cash_permissions
from app.modules.cashflow import schemas as cash_schemas
from app.modules.consultant_engineering import payments, schemas, service
from app.modules.consultant_engineering.permissions import ConsultantProject
from app.modules.projects.models import Project

router = APIRouter(
    prefix="/projects/{project_id}/consultant-engineering", tags=["consultant-engineering"]
)


def financial_project(project: ConsultantProject, actor: ActiveActor) -> Project:
    cash_permissions.require_cashflow_reader(actor)
    return project


FinancialProject = Annotated[Project, Depends(financial_project)]


@router.get("/payments", response_model=schemas.PaymentsWorkspaceOut)
def payment_workspace(project: FinancialProject, session: DbSession, actor: ActiveActor):
    return payments.workspace(session, project, actor)


@router.post("/stages/{stage_id}/payments", response_model=schemas.StagePaymentOut, status_code=201)
def create_stage_payment(
    project: FinancialProject,
    stage_id: uuid.UUID,
    payload: schemas.StagePaymentCreate,
    session: DbSession,
    actor: ActiveActor,
):
    row = payments.create_payment(session, project, actor, stage_id, payload)
    session.commit()
    return payments.payment_out(session, project, actor, row)


@router.patch("/payments/{payment_id}", response_model=schemas.StagePaymentOut)
def update_stage_payment(
    project: FinancialProject,
    payment_id: uuid.UUID,
    payload: cash_schemas.PreLaunchExpenseUpdate,
    session: DbSession,
    actor: ActiveActor,
):
    row = payments.change_payment(session, project, actor, payment_id, payload)
    session.commit()
    return payments.payment_out(session, project, actor, row)


@router.post("/payments/{payment_id}/confirm", response_model=schemas.StagePaymentOut)
def confirm_stage_payment(
    project: FinancialProject,
    payment_id: uuid.UUID,
    payload: cash_schemas.PreLaunchExpenseConfirm,
    session: DbSession,
    actor: ActiveActor,
):
    row = payments.confirm_payment(session, project, actor, payment_id, payload)
    session.commit()
    return payments.payment_out(session, project, actor, row)


@router.post("/payments/{payment_id}/remove", response_model=schemas.StagePaymentOut)
def remove_stage_payment(
    project: FinancialProject,
    payment_id: uuid.UUID,
    payload: cash_schemas.PreLaunchExpenseRemove,
    session: DbSession,
    actor: ActiveActor,
):
    row = payments.remove_payment(session, project, actor, payment_id, payload)
    session.commit()
    return payments.payment_out(session, project, actor, row)


@router.post("/payments/{payment_id}/reverse", response_model=schemas.StagePaymentOut)
def reverse_stage_payment(
    project: FinancialProject,
    payment_id: uuid.UUID,
    payload: cash_schemas.ReasonRequest,
    session: DbSession,
    actor: ActiveActor,
):
    row = payments.reverse_payment(session, project, actor, payment_id, payload.reason)
    session.commit()
    return payments.payment_out(session, project, actor, row)


def _save_proof(
    session: Session,
    project: Project,
    actor: ActorContext,
    payment_id: uuid.UUID,
    filename: str,
    data: bytes,
) -> schemas.PaymentProofOut:
    row = payments.create_proof(session, project, actor, payment_id, filename, data)
    session.commit()
    return schemas.PaymentProofOut.model_validate(row)


@router.post(
    "/payments/{payment_id}/proofs", response_model=schemas.PaymentProofOut, status_code=201
)
async def create_payment_proof(
    project: FinancialProject,
    payment_id: uuid.UUID,
    request: Request,
    session: DbSession,
    actor: ActiveActor,
    filename: Annotated[str, Query(min_length=1, max_length=255)],
):
    await run_in_threadpool(payments.authorize_upload, session, project, actor, payment_id)
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > payments.MAX_PROOF_BYTES:
            raise HTTPException(
                status_code=413, detail="Payment PDF proof must be no larger than 10 MB."
            )
        data.extend(chunk)
    return await run_in_threadpool(
        _save_proof, session, project, actor, payment_id, filename, bytes(data)
    )


@router.get("/payments/{payment_id}/proofs/{proof_id}/file")
def download_payment_proof(
    project: FinancialProject, payment_id: uuid.UUID, proof_id: uuid.UUID, session: DbSession
):
    row = payments.proof(session, project, payment_id, proof_id)
    return Response(
        content=row.document,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(row.filename, safe='')}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.post("/payments/{payment_id}/proofs/{proof_id}/delete", status_code=204)
def delete_payment_proof(
    project: FinancialProject,
    payment_id: uuid.UUID,
    proof_id: uuid.UUID,
    payload: cash_schemas.ReasonRequest,
    session: DbSession,
    actor: ActiveActor,
):
    payments.delete_proof(session, project, actor, payment_id, proof_id, payload.reason)
    session.commit()
    return Response(status_code=204)


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


@router.post("/engagements/{engagement_id}/delete", status_code=204)
def delete_draft_engagement(
    project: ConsultantProject,
    engagement_id: uuid.UUID,
    payload: schemas.EngagementRemoval,
    session: DbSession,
    actor: ActiveActor,
):
    service.delete_engagement(session, project, actor, engagement_id, payload)
    return Response(status_code=204)


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


@router.post("/engagements/{engagement_id}/reopen", response_model=schemas.EngagementOut)
def reopen_engagement(
    project: ConsultantProject,
    engagement_id: uuid.UUID,
    payload: schemas.EngagementReopen,
    session: DbSession,
    actor: ActiveActor,
):
    return service.reopen_engagement(session, project, actor, engagement_id, payload)


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
