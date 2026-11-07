"""Scoped leasing workflow; no writes to inventory, sales or cash records."""

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.inventory.leasing_sources import profile, unit_relation
from app.modules.leasing.models import LeasingInstruction
from app.modules.leasing.permissions import require_reader, scope
from app.modules.leasing.schemas import (
    ClientChoice,
    Create,
    Detail,
    Instruction,
    ProjectChoice,
    Register,
    Row,
    Source,
    Terms,
    UnitChoice,
    UnitChoices,
    Update,
)
from app.modules.projects.models import Project
from app.modules.projects.permissions import whole_project_ids
from app.modules.sales.leasing_sources import active_buyer, client_relation
from app.modules.settings.service import get_currency


def project_choices(session: Session, actor: ActorContext) -> list[ProjectChoice]:
    require_reader(actor)
    return [
        ProjectChoice(
            id=p.id,
            name=p.name,
            code=p.code,
            currency_code=get_currency(session, p.base_currency_id).code,
        )
        for p in session.scalars(
            select(Project).where(Project.id.in_(whole_project_ids(actor))).order_by(Project.name)
        )
    ]


def unit_choices(
    session: Session, project_id: uuid.UUID, actor: ActorContext, search: str, offset: int
) -> UnitChoices:
    scope(session, project_id, actor)
    units = unit_relation(select(Project.id).where(Project.id == project_id)).subquery()
    query = select(units).where(units.c.is_active)
    if search:
        query = query.where(units.c.unit_reference.icontains(search, autoescape=True))
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    rows = session.execute(
        query.order_by(units.c.unit_reference, units.c.id).offset(offset).limit(50)
    ).mappings()
    return UnitChoices(items=[UnitChoice.model_validate(r) for r in rows], total=total)


def clients(
    session: Session, project_id: uuid.UUID, actor: ActorContext, search: str
) -> list[ClientChoice]:
    scope(session, project_id, actor)
    relation = client_relation(select(Project.id).where(Project.id == project_id)).subquery()
    query = select(relation).where(relation.c.is_active)
    if search:
        query = query.where(
            or_(
                relation.c.display_name.icontains(search, autoescape=True),
                relation.c.client_number.icontains(search, autoescape=True),
            )
        )
    return [
        ClientChoice.model_validate(r)
        for r in session.execute(
            query.order_by(relation.c.display_name, relation.c.id).limit(50)
        ).mappings()
    ]


def source(
    session: Session, project_id: uuid.UUID, unit_id: uuid.UUID, actor: ActorContext
) -> Source:
    project = scope(session, project_id, actor)
    units = unit_relation(select(Project.id).where(Project.id == project_id)).subquery()
    unit = session.execute(select(units).where(units.c.id == unit_id)).mappings().one_or_none()
    if unit is None:
        raise NotFoundError("Unit not found in this project.")
    buyer, reference = active_buyer(session, project_id, unit_id)
    return Source(
        unit=UnitChoice.model_validate(unit),
        project_name=project.name,
        location=project.location or project.city,
        currency_code=get_currency(session, project.base_currency_id).code,
        sale_client=buyer,
        sale_reference=reference,
        **profile(session, project_id, unit_id),
    )


def attention(row: LeasingInstruction, as_at: date) -> list[str]:
    items = []
    if row.status == "closed":
        return items
    if row.owner_client_id is None:
        items.append("Owner not linked")
    if not row.mandate_date or not row.mandate_reference:
        items.append("Instruction to confirm")
    if row.follow_up_date and row.follow_up_date <= as_at:
        items.append("Follow-up due")
    if row.status == "leased" and row.lease_end:
        if row.lease_end < as_at:
            items.append("Lease ended — review")
        elif row.lease_end <= as_at + timedelta(days=60):
            items.append("Expires within 60 days")
    return items


def register(
    session: Session,
    actor: ActorContext,
    project_id: uuid.UUID | None,
    search: str,
    stage: str | None,
    focus: str | None,
    offset: int,
    limit: int,
    as_at: date,
) -> Register:
    require_reader(actor)
    if project_id:
        scope(session, project_id, actor)
    allowed = whole_project_ids(actor)
    units = unit_relation(allowed).subquery()
    owners = client_relation(allowed).subquery()
    base = (
        select(LeasingInstruction, Project.name, units.c.unit_reference, owners.c.display_name)
        .join(Project, Project.id == LeasingInstruction.project_id)
        .join(units, units.c.id == LeasingInstruction.unit_id)
        .outerjoin(owners, owners.c.id == LeasingInstruction.owner_client_id)
        .where(LeasingInstruction.project_id.in_(allowed), LeasingInstruction.is_deleted.is_(False))
    )
    if project_id:
        base = base.where(LeasingInstruction.project_id == project_id)
    if search:
        base = base.where(
            or_(
                units.c.unit_reference.icontains(search, autoescape=True),
                Project.name.icontains(search, autoescape=True),
                owners.c.display_name.icontains(search, autoescape=True),
                LeasingInstruction.tenant_name.icontains(search, autoescape=True),
            )
        )
    # Counts share project/search scope, independent of the selected stage.
    counts_query = base.with_only_columns(
        LeasingInstruction.id,
        LeasingInstruction.status,
        LeasingInstruction.follow_up_date,
        LeasingInstruction.lease_end,
    ).subquery()
    counts = dict(
        session.execute(
            select(counts_query.c.status, func.count()).group_by(counts_query.c.status)
        ).all()
    )
    expiry = (
        (counts_query.c.status == "leased")
        & (counts_query.c.lease_end >= as_at)
        & (counts_query.c.lease_end <= as_at + timedelta(days=60))
    )
    follow_up = (counts_query.c.status != "closed") & (counts_query.c.follow_up_date <= as_at)
    counts["expiring"] = session.scalar(
        select(func.count()).select_from(counts_query).where(expiry)
    )
    counts["follow_up"] = session.scalar(
        select(func.count()).select_from(counts_query).where(follow_up)
    )
    if stage:
        base = base.where(LeasingInstruction.status == stage)
    if focus == "expiring":
        base = base.where(
            LeasingInstruction.status == "leased",
            LeasingInstruction.lease_end >= as_at,
            LeasingInstruction.lease_end <= as_at + timedelta(days=60),
        )
    if focus == "follow_up":
        base = base.where(
            LeasingInstruction.status != "closed", LeasingInstruction.follow_up_date <= as_at
        )
    total = session.scalar(select(func.count()).select_from(base.subquery()))
    rows = session.execute(
        base.order_by(LeasingInstruction.updated_at.desc(), LeasingInstruction.id)
        .offset(offset)
        .limit(limit)
    ).all()
    codes = {row.currency_id: get_currency(session, row.currency_id).code for row, _, _, _ in rows}
    return Register(
        items=[
            Row(
                **Instruction.model_validate(row).model_dump(),
                project_name=name,
                unit_reference=unit,
                owner_name=owner,
                currency_code=codes[row.currency_id],
                attention=attention(row, as_at),
            )
            for row, name, unit, owner in rows
        ],
        total=total,
        counts=counts,
        as_at=as_at,
    )


def get_record(
    session: Session, project_id: uuid.UUID, record_id: uuid.UUID, *, lock: bool = False
) -> LeasingInstruction:
    query = select(LeasingInstruction).where(
        LeasingInstruction.id == record_id,
        LeasingInstruction.project_id == project_id,
        LeasingInstruction.is_deleted.is_(False),
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = session.scalar(query)
    if row is None:
        raise NotFoundError("Leasing instruction not found.")
    return row


def detail(
    session: Session, project_id: uuid.UUID, record_id: uuid.UUID, actor: ActorContext
) -> Detail:
    scope(session, project_id, actor)
    row = get_record(session, project_id, record_id)
    context = source(session, project_id, row.unit_id, actor)
    relation = client_relation(select(Project.id).where(Project.id == project_id)).subquery()
    owner = (
        session.execute(select(relation).where(relation.c.id == row.owner_client_id))
        .mappings()
        .one_or_none()
    )
    return Detail(
        **Instruction.model_validate(row).model_dump(),
        project_name=context.project_name,
        unit_reference=context.unit.unit_reference,
        owner_name=owner["display_name"] if owner else None,
        currency_code=get_currency(session, row.currency_id).code,
        attention=attention(row, datetime.now(UTC).date()),
        source=context,
        owner=owner,
        owner_matches_sale=(row.owner_client_id == context.sale_client.id)
        if context.sale_client
        else None,
    )


def validate(session: Session, project_id: uuid.UUID, values: Terms) -> None:
    if values.owner_client_id:
        relation = client_relation(select(Project.id).where(Project.id == project_id)).subquery()
        if (
            session.scalar(select(relation.c.id).where(relation.c.id == values.owner_client_id))
            is None
        ):
            raise ValidationError("Choose an owner from this project's clients.")
    if values.lease_start and values.lease_end and values.lease_end <= values.lease_start:
        raise ValidationError("Lease end must be after lease start.")
    if values.follow_up_date and not values.next_action:
        raise ValidationError("Describe the action for this follow-up date.")
    if values.status in {"marketing", "negotiating", "leased"} and not (
        values.owner_client_id
        and values.mandate_date
        and values.mandate_reference
        and values.asking_rent_monthly
        and values.asking_rent_monthly > 0
    ):
        raise ValidationError(
            "Link the owner, record the instruction date/reference and enter positive "
            "monthly asking rent before marketing."
        )
    if values.status == "leased" and not (
        values.tenant_name
        and values.lease_start
        and values.lease_end
        and values.agreed_rent_monthly
        and values.agreed_rent_monthly > 0
        and values.agreement_reference
    ):
        raise ValidationError(
            "A leased unit needs the tenant, start/end dates, positive agreed monthly "
            "rent and agreement reference."
        )


def snapshot(row: LeasingInstruction) -> dict:
    return {**Instruction.model_validate(row).model_dump(), "is_deleted": row.is_deleted}


def persist(
    session: Session,
    row: LeasingInstruction,
    actor: ActorContext,
    action: str,
    before: dict | None,
    reason: str | None,
) -> None:
    try:
        session.add(row)
        session.flush()
        record_event(
            session,
            entity_type="leasing_instruction",
            entity_id=row.id,
            action=action,
            actor_user_id=actor.user_id,
            correlation_id=actor.correlation_id,
            before=before,
            after=snapshot(row),
            reason=reason,
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError(
            "This unit already has an open leasing instruction, or a linked source "
            "changed. Refresh and retry."
        ) from exc


def create(session: Session, project_id: uuid.UUID, actor: ActorContext, body: Create) -> Detail:
    project = scope(session, project_id, actor, write=True)
    context = source(session, project_id, body.unit_id, actor)
    if not context.unit.is_active:
        raise ValidationError("Choose an active unit from the project's inventory.")
    values = Terms.model_validate(body.model_dump(exclude={"unit_id"}))
    if "owner_client_id" not in body.model_fields_set and context.sale_client:
        values.owner_client_id = context.sale_client.id
    validate(session, project_id, values)
    row = LeasingInstruction(
        project_id=project_id,
        unit_id=body.unit_id,
        currency_id=project.base_currency_id,
        **values.model_dump(),
    )
    persist(session, row, actor, "create", None, None)
    return detail(session, project_id, row.id, actor)


def change(
    session: Session,
    project_id: uuid.UUID,
    record_id: uuid.UUID,
    actor: ActorContext,
    version: int,
    reason: str,
    body: Update | None = None,
) -> Detail | None:
    scope(session, project_id, actor, write=True)
    row = get_record(session, project_id, record_id, lock=True)
    if row.version != version:
        raise ConflictError("This instruction changed. Reopen it before saving.")
    before = snapshot(row)
    if body:
        validate(session, project_id, body)
        if row.status == "closed" and body.status != "closed":
            raise ValidationError(
                "A closed letting cycle stays in history. Create a new instruction for "
                "the next tenancy."
            )
        for key, value in body.model_dump(exclude={"reason", "expected_version"}).items():
            setattr(row, key, value)
    else:
        row.is_deleted = True
    row.version += 1
    persist(session, row, actor, "update" if body else "delete", before, reason)
    return detail(session, project_id, record_id, actor) if body else None
