"""Plain-language project specification register, separate from construction costs."""

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.construction.models import TechnicalSpecification
from app.modules.construction.permissions import CONSTRUCTION_READER_ROLES
from app.modules.inventory.permissions import visible_phase_ids
from app.modules.projects.permissions import require_project_access, require_project_role
from app.modules.projects.schemas import StrictRequest
from app.modules.projects.service import lock_project

READERS = CONSTRUCTION_READER_ROLES | {"sales_advisor", "sales_operations"}
WRITERS = frozenset({"system_admin", "project_manager", "design_engineering"})


class SpecificationInput(StrictRequest):
    category: Literal[
        "structure",
        "finishes",
        "sanitary",
        "plumbing",
        "water",
        "aluminium",
        "doors",
        "kitchen",
        "electrical",
        "heating_cooling",
        "shared",
        "other",
    ]
    title: str = Field(min_length=1, max_length=200)
    scope: Literal["project", "units"]
    applies_to: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=4000)
    brand_model: str = Field(default="", max_length=300)
    inclusion: Literal["included", "optional", "excluded", "undecided"] = "undecided"
    status: Literal["draft", "confirmed"] = "draft"
    source_reference: str = Field(default="", max_length=500)
    version: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def validate_text(self) -> "SpecificationInput":
        for key in ("title", "applies_to", "description", "brand_model", "source_reference"):
            setattr(self, key, getattr(self, key).strip())
        if not self.title or not self.applies_to or not self.description:
            raise ValueError("Item, applicability and specification must not be blank.")
        if self.status == "confirmed" and (
            not self.source_reference or self.inclusion == "undecided"
        ):
            raise ValueError(
                "Confirmed specifications need a source reference and a decided inclusion status."
            )
        return self


class SpecificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    category: str
    title: str
    scope: str
    applies_to: str
    description: str
    brand_model: str
    inclusion: str
    status: str
    source_reference: str
    version: int
    updated_at: datetime


def authorize(
    session: Session, project_id: uuid.UUID, actor: ActorContext, *, write: bool = False
) -> None:
    require_project_access(session, project_id=project_id, actor=actor)
    require_project_role(actor, WRITERS if write else READERS)
    if visible_phase_ids(session, project_id=project_id, actor=actor) is not None:
        raise PermissionDeniedError(
            "Technical Specifications requires access to the whole project."
        )


def list_specifications(
    session: Session, project_id: uuid.UUID, actor: ActorContext
) -> list[TechnicalSpecification]:
    authorize(session, project_id, actor)
    return list(
        session.scalars(
            select(TechnicalSpecification)
            .where(
                TechnicalSpecification.project_id == project_id,
                TechnicalSpecification.removed_at.is_(None),
            )
            .order_by(
                TechnicalSpecification.category,
                TechnicalSpecification.title,
                TechnicalSpecification.id,
            )
        )
    )


def _row(
    session: Session, project_id: uuid.UUID, specification_id: uuid.UUID
) -> TechnicalSpecification:
    row = session.scalar(
        select(TechnicalSpecification)
        .where(
            TechnicalSpecification.project_id == project_id,
            TechnicalSpecification.id == specification_id,
            TechnicalSpecification.removed_at.is_(None),
        )
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise NotFoundError("Technical specification not found.")
    return row


def save(
    session: Session,
    project_id: uuid.UUID,
    actor: ActorContext,
    payload: SpecificationInput,
    specification_id: uuid.UUID | None = None,
) -> TechnicalSpecification:
    authorize(session, project_id, actor, write=True)
    lock_project(session, project_id)
    authorize(session, project_id, actor, write=True)
    row = _row(session, project_id, specification_id) if specification_id else None
    before = SpecificationRead.model_validate(row).model_dump(mode="json") if row else None
    if row and row.version != payload.version:
        raise ConflictError("This specification changed. Reload it before saving.")
    values = payload.model_dump(exclude={"version"})
    if row:
        for key, value in values.items():
            setattr(row, key, value)
        row.version += 1
        row.updated_at = datetime.now(UTC)
    else:
        row = TechnicalSpecification(project_id=project_id, **values)
        session.add(row)
    session.flush()
    record_event(
        session,
        action="technical_specification.updated" if before else "technical_specification.created",
        entity_type="technical_specification",
        entity_id=row.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        before=before,
        after=SpecificationRead.model_validate(row).model_dump(mode="json"),
    )
    session.commit()
    session.refresh(row)
    return row


def delete(
    session: Session,
    project_id: uuid.UUID,
    actor: ActorContext,
    specification_id: uuid.UUID,
    reason: str,
) -> None:
    authorize(session, project_id, actor, write=True)
    lock_project(session, project_id)
    authorize(session, project_id, actor, write=True)
    if not reason.strip():
        raise ValidationError("A deletion reason is required.")
    row = _row(session, project_id, specification_id)
    before = SpecificationRead.model_validate(row).model_dump(mode="json")
    # Confirmed content remains recoverable evidence; drafts have no dependents.
    if row.status == "confirmed":
        row.removed_at = datetime.now(UTC)
    else:
        session.delete(row)
    record_event(
        session,
        action="technical_specification.deleted",
        entity_type="technical_specification",
        entity_id=row.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        reason=reason.strip(),
        before=before,
    )
    session.commit()
