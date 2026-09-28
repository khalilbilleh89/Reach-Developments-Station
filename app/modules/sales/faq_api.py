"""Commercial FAQ routes, using existing Sales project access."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.modules.access.dependencies import ActiveActor, DbSession
from app.modules.sales import faq
from app.modules.sales.faq_schemas import FaqInput, FaqList, FaqRead, FaqUpdate
from app.modules.sales.permissions import SalesProject

router = APIRouter(prefix="/projects/{project_id}/faqs", tags=["sales"])


@router.get("", response_model=FaqList)
def read_faqs(session: DbSession, actor: ActiveActor, project: SalesProject) -> FaqList:
    return faq.list_faqs(session, project, actor)


@router.post("", response_model=FaqRead, status_code=201)
def create_faq(
    payload: FaqInput, session: DbSession, actor: ActiveActor, project: SalesProject
) -> FaqRead:
    return faq.create(session, project, actor, payload)


@router.put("/{faq_id}", response_model=FaqRead)
def update_faq(
    faq_id: uuid.UUID,
    payload: FaqUpdate,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> FaqRead:
    return faq.update(session, project, actor, faq_id, payload)


@router.delete("/{faq_id}", status_code=204)
def delete_faq(
    faq_id: uuid.UUID,
    version: Annotated[int, Query(ge=1)],
    reason: Annotated[str, Query(min_length=1, max_length=500)],
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> Response:
    faq.delete(session, project, actor, faq_id, version, reason)
    return Response(status_code=204)
