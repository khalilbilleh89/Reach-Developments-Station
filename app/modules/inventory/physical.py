"""Physical unit facts: gross measurements, descriptive features and document links.

These annotations are not pricing inputs or substitutes for release approvals.
Measurements remain in the existing immutable approved area schedules.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.inventory import service
from app.modules.inventory.models import Unit, UnitDocument, UnitFeature
from app.modules.inventory.permissions import require_operational_project, require_unit
from app.modules.projects.service import lock_project

COMPONENTS = ("internal", "balcony", "roof_garden", "front_garden", "terrace", "porches")


def gross_measurement(lines: list[dict[str, Any]]) -> dict[str, Any]:
    """Sum the six explicit components, never factors or attached assets.

    Missing measurements are unknown, not zero. An operator records zero for
    an absent component. Refuse to add mixed measurement units or duplicate
    components from legacy/replaced types on the same revision.
    """
    measured = [line for line in lines if line.get("physical_component") in COMPONENTS]
    missing = [
        key for key in COMPONENTS if not any(line["physical_component"] == key for line in measured)
    ]
    units = {line["unit_of_measure"] for line in measured}
    duplicate = len(measured) != len({line["physical_component"] for line in measured})
    reason = (
        "Record all six components; use zero where an area does not apply."
        if missing
        else "Components use different measurement units."
        if len(units) != 1
        else "A component is recorded more than once."
        if duplicate
        else None
    )
    net_lines = [line for line in measured if line["physical_component"] in ("internal", "balcony")]
    net_units = {line["unit_of_measure"] for line in net_lines}
    net_complete = (
        len(net_lines) == 2
        and {line["physical_component"] for line in net_lines} == {"internal", "balcony"}
        and len(net_units) == 1
    )
    return {
        "net_area": sum((line["raw_area"] for line in net_lines), Decimal("0"))
        if net_complete
        else None,
        "net_area_unit": next(iter(net_units)) if len(net_units) == 1 else None,
        "gross_area": None
        if reason
        else sum((line["raw_area"] for line in measured), Decimal("0")),
        "gross_area_unit": next(iter(units)) if len(units) == 1 else None,
        "gross_area_reason": reason,
        "gross_missing_components": missing,
    }


def features(session: Session, unit: Unit) -> list[UnitFeature]:
    return list(
        session.scalars(
            select(UnitFeature)
            .where(UnitFeature.unit_id == unit.id, UnitFeature.project_id == unit.project_id)
            .order_by(UnitFeature.created_at, UnitFeature.id)
        )
    )


def documents(session: Session, unit: Unit) -> list[UnitDocument]:
    return list(
        session.scalars(
            select(UnitDocument)
            .where(UnitDocument.unit_id == unit.id, UnitDocument.project_id == unit.project_id)
            .order_by(UnitDocument.created_at, UnitDocument.id)
        )
    )


def _lock_record(session: Session, unit: Unit, actor: ActorContext) -> Unit:
    project = lock_project(session, unit.project_id)
    require_operational_project(project)
    service.lock_unit(session, project_id=unit.project_id, unit_id=unit.id)
    # A unit may have moved phase while the request waited for the lock.
    return require_unit(session, project=project, unit_id=unit.id, actor=actor)


def add_feature(session: Session, *, unit: Unit, actor: ActorContext, label: str) -> UnitFeature:
    unit = _lock_record(session, unit, actor)
    if any(
        row.is_active and row.label.casefold() == label.casefold()
        for row in features(session, unit)
    ):
        raise ConflictError("That feature is already recorded on this unit.")
    row = UnitFeature(
        project_id=unit.project_id,
        unit_id=unit.id,
        label=label,
        is_active=True,
        created_by_user_id=actor.user_id,
    )
    session.add(row)
    session.flush()
    record_event(
        session,
        action="unit_feature.created",
        entity_type="unit_feature",
        entity_id=row.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        after={"unit_id": str(unit.id), "label": label, "is_active": True},
    )
    session.commit()
    session.refresh(row)
    return row


def retire_feature(
    session: Session, *, unit: Unit, actor: ActorContext, feature_id: uuid.UUID
) -> UnitFeature:
    unit = _lock_record(session, unit, actor)
    row = session.scalars(
        select(UnitFeature)
        .where(
            UnitFeature.id == feature_id,
            UnitFeature.unit_id == unit.id,
            UnitFeature.project_id == unit.project_id,
        )
        .execution_options(populate_existing=True)
    ).first()
    if row is None:
        raise NotFoundError("Feature not found.")
    if not row.is_active:
        raise ConflictError("That feature is already retired.")
    row.is_active = False
    record_event(
        session,
        action="unit_feature.retired",
        entity_type="unit_feature",
        entity_id=row.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        before={"label": row.label, "is_active": True},
        after={"label": row.label, "is_active": False},
    )
    session.commit()
    session.refresh(row)
    return row


def add_document(
    session: Session, *, unit: Unit, actor: ActorContext, title: str, url: str, revision: str | None
) -> UnitDocument:
    unit = _lock_record(session, unit, actor)
    row = UnitDocument(
        project_id=unit.project_id,
        unit_id=unit.id,
        title=title,
        url=url,
        revision=revision,
        is_active=True,
        created_by_user_id=actor.user_id,
    )
    session.add(row)
    session.flush()
    record_event(
        session,
        action="unit_document.created",
        entity_type="unit_document",
        entity_id=row.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        after={"unit_id": str(unit.id), "title": title, "url": url, "revision": revision},
    )
    session.commit()
    session.refresh(row)
    return row


def retire_document(
    session: Session, *, unit: Unit, actor: ActorContext, document_id: uuid.UUID
) -> UnitDocument:
    unit = _lock_record(session, unit, actor)
    row = session.scalars(
        select(UnitDocument)
        .where(
            UnitDocument.id == document_id,
            UnitDocument.unit_id == unit.id,
            UnitDocument.project_id == unit.project_id,
        )
        .execution_options(populate_existing=True)
    ).first()
    if row is None:
        raise NotFoundError("Document not found.")
    if not row.is_active:
        raise ConflictError("That document is already retired.")
    row.is_active = False
    record_event(
        session,
        action="unit_document.retired",
        entity_type="unit_document",
        entity_id=row.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        before={"title": row.title, "url": row.url, "is_active": True},
        after={"title": row.title, "url": row.url, "is_active": False},
    )
    session.commit()
    session.refresh(row)
    return row
