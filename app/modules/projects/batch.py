"""Current permit predicates and complete land acquisition components."""

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.modules.projects.models import LandParcel, Permit
from app.modules.projects.service import _SATISFYING_STATUSES, _sla_overdue_clause


@dataclass
class DevelopmentPosition:
    permit_count: int = 0
    blockers: list[tuple[uuid.UUID, str]] = field(default_factory=list)
    overdue: list[tuple[uuid.UUID, str]] = field(default_factory=list)
    land_count: int = 0
    land_total: Decimal = Decimal(0)
    land_incomplete: bool = False


def positions(
    session: Session, project_ids: Select, as_of: date
) -> dict[uuid.UUID, DevelopmentPosition]:
    result: dict[uuid.UUID, DevelopmentPosition] = {}
    for permit, overdue in session.execute(
        select(Permit, _sla_overdue_clause(as_of)).where(Permit.project_id.in_(project_ids))
    ):
        target = result.setdefault(permit.project_id, DevelopmentPosition())
        target.permit_count += 1
        unresolved = permit.status not in _SATISFYING_STATUSES | {"withdrawn"}
        if unresolved and permit.is_blocking:
            target.blockers.append((permit.id, permit.permit_type_code))
        elif unresolved and overdue:
            target.overdue.append((permit.id, permit.permit_type_code))
    for parcel in session.scalars(
        select(LandParcel).where(
            LandParcel.project_id.in_(project_ids), LandParcel.is_active.is_(True)
        )
    ):
        target = result.setdefault(parcel.project_id, DevelopmentPosition())
        target.land_count += 1
        if parcel.purchase_price is None or parcel.acquisition_fees is None:
            target.land_incomplete = True
        else:
            target.land_total += parcel.purchase_price + parcel.acquisition_fees
    return result
