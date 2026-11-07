"""Inventory-owned, read-only unit selection and physical profile for Leasing."""

import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.modules.inventory import service
from app.modules.inventory.models import Building, Floor, Unit


def unit_relation(project_ids: Select) -> Select:
    return (
        select(
            Unit.id,
            Unit.project_id,
            Unit.unit_reference,
            Building.code.label("building"),
            Floor.code.label("floor"),
            (Unit.is_active & Unit.removed_at.is_(None)).label("is_active"),
        )
        .outerjoin(Floor, Floor.id == Unit.floor_id)
        .join(Building, Building.id == func.coalesce(Unit.building_id, Floor.building_id))
        .where(Unit.project_id.in_(project_ids))
    )


def profile(session: Session, project_id: uuid.UUID, unit_id: uuid.UUID) -> dict:
    unit = session.scalar(select(Unit).where(Unit.project_id == project_id, Unit.id == unit_id))
    if unit is None:
        raise NotFoundError("Unit not found in this project.")
    schedule = service.approved_schedule(session, unit_id=unit.id)
    lines = service.area_lines(session, project_id=project_id, schedule=schedule)
    internal = service.internal_area_type(session, project_id=project_id)
    line = next((line for line in lines if internal and line["area_type_id"] == internal.id), None)
    return {
        "asset_class": unit.asset_class,
        "bedrooms": unit.bedrooms,
        "bathrooms": unit.bathrooms,
        "furnishing": unit.furnishing_specification_code,
        "delivery_status": unit.delivery_status,
        "internal_area": line["raw_area"] if line else None,
        "area_unit": line["unit_of_measure"] if line else None,
    }
