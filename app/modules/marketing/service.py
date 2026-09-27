"""Project-locked marketing edits and read-only composition over inventory/pricing."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.inventory import service as inventory
from app.modules.inventory.permissions import require_unit
from app.modules.inventory.physical import gross_measurement
from app.modules.marketing.calculations import calculate
from app.modules.marketing.models import MarketIndicator, MarketingContent, RentalScenario
from app.modules.marketing.schemas import (
    Bio,
    Branding,
    ContentRead,
    IndicatorWrite,
    Removal,
    ScenarioWrite,
    UnitRegister,
    UnitResult,
    UnitScenario,
)
from app.modules.pricing.service import active_price
from app.modules.projects.models import Project
from app.modules.settings.service import get_currency

Record = MarketingContent | RentalScenario | MarketIndicator


def snapshot(row: Record) -> dict:
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def commit_record(
    session: Session,
    row: Record,
    actor: ActorContext,
    before: dict | None,
    *,
    reason: str | None = None,
) -> None:
    session.add(row)
    session.flush()
    record_event(
        session,
        action="delete" if reason else "update" if before else "create",
        entity_type=row.__tablename__,
        entity_id=row.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        before=before,
        after=snapshot(row),
        reason=reason,
    )
    session.commit()


def current_content(session: Session, project_id: uuid.UUID, kind: str) -> MarketingContent | None:
    return session.scalars(
        select(MarketingContent)
        .where(
            MarketingContent.project_id == project_id,
            MarketingContent.kind == kind,
            MarketingContent.is_deleted.is_(False),
        )
        .execution_options(populate_existing=True)
    ).first()


def read_content(session: Session, project_id: uuid.UUID, kind: str) -> ContentRead:
    row = current_content(session, project_id, kind)
    model = Bio if kind == "bio" else Branding
    return ContentRead(
        version=row.version if row else 0, data=model.model_validate(row.data) if row else model()
    )


def version_check(row: Record | None, expected: int) -> None:
    if expected != (row.version if row else 0):
        raise ConflictError(
            "This record changed. Reload before saving; your entries have been kept."
        )


def save_content(
    session: Session,
    project_id: uuid.UUID,
    kind: str,
    data: Bio | Branding,
    expected: int,
    actor: ActorContext,
) -> ContentRead:
    row = current_content(session, project_id, kind)
    version_check(row, expected)
    before = snapshot(row) if row else None
    if row is None:
        last_version = (
            session.scalar(
                select(func.max(MarketingContent.version)).where(
                    MarketingContent.project_id == project_id, MarketingContent.kind == kind
                )
            )
            or 0
        )
        row = MarketingContent(project_id=project_id, kind=kind, version=last_version + 1)
    else:
        row.version += 1
    row.data = data.model_dump(mode="json")
    commit_record(session, row, actor, before)
    return read_content(session, project_id, kind)


def get_record(
    session: Session,
    project_id: uuid.UUID,
    record_id: uuid.UUID,
    model: type[RentalScenario] | type[MarketIndicator],
) -> RentalScenario | MarketIndicator:
    row = session.scalars(
        select(model)
        .where(model.id == record_id, model.project_id == project_id, model.is_deleted.is_(False))
        .execution_options(populate_existing=True)
    ).first()
    if row is None:
        raise NotFoundError("Marketing record not found.")
    return row


def save_scenario(
    session: Session,
    project: Project,
    body: ScenarioWrite,
    actor: ActorContext,
    record_id: uuid.UUID | None = None,
) -> RentalScenario:
    row = get_record(session, project.id, record_id, RentalScenario) if record_id else None
    version_check(row, body.expected_version)
    if body.unit_id:
        require_unit(session, project=project, unit_id=body.unit_id, actor=actor)
    currency = get_currency(session, body.currency_id)
    if not currency.is_active:
        raise ValidationError("Choose an active currency.")
    duplicate = session.scalars(
        select(RentalScenario).where(
            RentalScenario.project_id == project.id,
            RentalScenario.unit_id == body.unit_id,
            RentalScenario.mode == body.mode,
            RentalScenario.is_deleted.is_(False),
        )
    ).first()
    if duplicate is not None and (row is None or row.id != duplicate.id):
        raise ConflictError(
            "This rental mode already has assumptions for this scope. Edit that record."
        )
    before = snapshot(row) if row else None
    row = row or RentalScenario(project_id=project.id, version=0)
    for key, value in body.model_dump(exclude={"expected_version"}).items():
        setattr(row, key, value)
    row.version += 1
    commit_record(session, row, actor, before)
    return row


def save_indicator(
    session: Session,
    project_id: uuid.UUID,
    body: IndicatorWrite,
    actor: ActorContext,
    record_id: uuid.UUID | None = None,
) -> MarketIndicator:
    row = get_record(session, project_id, record_id, MarketIndicator) if record_id else None
    version_check(row, body.expected_version)
    before = snapshot(row) if row else None
    row = row or MarketIndicator(project_id=project_id, version=0)
    for key, value in body.model_dump(exclude={"expected_version"}).items():
        setattr(row, key, value)
    row.version += 1
    commit_record(session, row, actor, before)
    return row


def remove(session: Session, row: Record | None, body: Removal, actor: ActorContext) -> None:
    if row is None:
        raise NotFoundError("Marketing record not found.")
    version_check(row, body.expected_version)
    before = snapshot(row)
    row.is_deleted = True
    row.version += 1
    commit_record(session, row, actor, before, reason=body.reason)


def list_scenarios(session: Session, project_id: uuid.UUID) -> list[RentalScenario]:
    return list(
        session.scalars(
            select(RentalScenario)
            .where(RentalScenario.project_id == project_id, RentalScenario.is_deleted.is_(False))
            .order_by(RentalScenario.mode, RentalScenario.created_at)
        )
    )


def list_indicators(session: Session, project_id: uuid.UUID) -> list[MarketIndicator]:
    return list(
        session.scalars(
            select(MarketIndicator)
            .where(MarketIndicator.project_id == project_id, MarketIndicator.is_deleted.is_(False))
            .order_by(MarketIndicator.name, MarketIndicator.as_of.desc())
        )
    )


def projections(
    session: Session,
    project: Project,
    actor: ActorContext,
    *,
    search: str | None,
    limit: int,
    offset: int,
) -> UnitRegister:
    filters = {
        "search": search,
        "phase_id": None,
        "building_id": None,
        "floor_id": None,
        "commercial_status": None,
        "unit_type_code": None,
        "asset_class": None,
        "is_active": None,
    }
    units = inventory.list_units(
        session, project=project, actor=actor, limit=limit, offset=offset, **filters
    )
    total = inventory.unit_register_totals(session, project=project, actor=actor, **filters)[
        "total"
    ]
    settings = {(row.unit_id, row.mode): row for row in list_scenarios(session, project.id)}
    results = []
    for unit in units:
        schedule = inventory.approved_schedule(session, unit_id=unit.id)
        areas = gross_measurement(
            inventory.area_lines(session, project_id=project.id, schedule=schedule)
        )
        price = active_price(session, unit_id=unit.id)
        modes = []
        for mode in ("long_term", "short_term"):
            s = settings.get((unit.id, mode)) or settings.get((None, mode))
            result = UnitScenario(mode=mode)
            if s is None:
                result.unavailable = "Add project or unit rental assumptions."
            else:
                result.scenario_id = s.id
                result.source_scope = "Unit override" if s.unit_id else "Project default"
                result.currency_id = s.currency_id
                result.area_sqm = areas[f"{s.area_basis}_area"]
                result.price = (
                    s.price_override
                    if s.price_override is not None
                    else price.reference_price_ex_tax
                    if price
                    else None
                )
                result.price_basis = (
                    "Assumed purchase price"
                    if s.price_override is not None
                    else "Current asking price, excluding tax"
                )
                if (
                    result.area_sqm is None
                    or result.area_sqm <= 0
                    or areas[f"{s.area_basis}_area_unit"] not in {"sqm", "m2", "m²"}
                ):
                    result.unavailable = "An approved, positive area in m² is required."
                elif result.price is None or result.price <= 0:
                    result.unavailable = (
                        "No positive current asking price; enter a unit purchase price assumption."
                    )
                elif s.price_override is None and price.currency_id != s.currency_id:
                    result.unavailable = (
                        "Price and rental assumptions use different currencies; "
                        "no FX conversion is applied."
                    )
                else:
                    inputs = ScenarioWrite.model_validate(
                        {
                            key: getattr(s, key)
                            for key in ScenarioWrite.model_fields
                            if key != "expected_version"
                        }
                    )
                    result.projection = calculate(inputs, result.area_sqm, result.price)
            modes.append(result)
        results.append(UnitResult(unit_id=unit.id, reference=unit.unit_reference, scenarios=modes))
    return UnitRegister(total=total, units=results)
