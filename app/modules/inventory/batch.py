"""Inventory-owned eligible population, scoped in SQL before loading."""

import uuid
from dataclasses import dataclass

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.modules.inventory.models import Unit
from app.modules.inventory.service import analysis_eligible


@dataclass(frozen=True)
class InventoryPosition:
    eligible_ids: frozenset[uuid.UUID]
    available_units: int
    total_units: int


def positions(session: Session, project_ids: Select) -> dict[uuid.UUID, InventoryPosition]:
    """Sub-assets are a different owner table and never enter this population."""
    eligible: dict[uuid.UUID, set[uuid.UUID]] = {}
    available: dict[uuid.UUID, int] = {}
    total: dict[uuid.UUID, int] = {}
    for unit in session.scalars(select(Unit).where(Unit.project_id.in_(project_ids))):
        total[unit.project_id] = total.get(unit.project_id, 0) + 1
        if analysis_eligible(unit):
            eligible.setdefault(unit.project_id, set()).add(unit.id)
        if unit.is_active and unit.commercial_status == "available":
            available[unit.project_id] = available.get(unit.project_id, 0) + 1
    return {
        pid: InventoryPosition(frozenset(eligible.get(pid, set())), available.get(pid, 0), count)
        for pid, count in total.items()
    }
