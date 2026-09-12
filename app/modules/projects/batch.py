"""Current permit predicates and complete land acquisition components."""

import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.modules.projects.land_analytics import cost_breakdown
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
    deadlines: list[tuple[uuid.UUID, str, date, str, bool]] = field(default_factory=list)
    undated_permits: int = 0


@dataclass(frozen=True)
class PermitFact:
    project_id: uuid.UUID
    source_id: uuid.UUID
    label: str
    status: str
    blocking: bool
    due_date: date | None


def reporting_permits(session: Session, scope: Select) -> list[PermitFact]:
    """Freeze status even after issue; no inference from absence in an Outlook."""
    return [
        PermitFact(
            p.project_id,
            p.id,
            p.permit_code,
            p.status,
            p.is_blocking,
            p.status_effective_date + timedelta(days=p.statutory_sla_days)
            if p.statutory_sla_days is not None
            else None,
        )
        for p in session.scalars(
            select(Permit)
            .where(Permit.project_id.in_(scope), Permit.deleted_at.is_(None))
            .order_by(Permit.project_id, Permit.id)
        )
    ]


def positions(
    session: Session, project_ids: Select, as_of: date, *, risk_only: bool = False
) -> dict[uuid.UUID, DevelopmentPosition]:
    result: dict[uuid.UUID, DevelopmentPosition] = {}
    for permit, overdue in session.execute(
        select(Permit, _sla_overdue_clause(as_of)).where(
            Permit.project_id.in_(project_ids), Permit.deleted_at.is_(None)
        )
    ):
        target = result.setdefault(permit.project_id, DevelopmentPosition())
        target.permit_count += 1
        unresolved = permit.status not in _SATISFYING_STATUSES | {"withdrawn"}
        if unresolved:
            if permit.statutory_sla_days is None:
                target.undated_permits += 1
            else:
                target.deadlines.append(
                    (
                        permit.id,
                        permit.permit_code,
                        permit.status_effective_date + timedelta(days=permit.statutory_sla_days),
                        permit.status,
                        permit.is_blocking,
                    )
                )
        if unresolved and permit.is_blocking:
            target.blockers.append((permit.id, permit.permit_type_code))
        elif unresolved and overdue:
            target.overdue.append((permit.id, permit.permit_type_code))
    if risk_only:
        return result
    for parcel in session.scalars(
        select(LandParcel).where(
            LandParcel.project_id.in_(project_ids), LandParcel.is_active.is_(True)
        )
    ):
        target = result.setdefault(parcel.project_id, DevelopmentPosition())
        target.land_count += 1
        cost = cost_breakdown(parcel)["total_acquisition_cost"]
        if cost is None:
            target.land_incomplete = True
        else:
            target.land_total += cost
    return result
