"""Unit Economics-owned participation in a project denomination correction."""

from __future__ import annotations

import uuid

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.modules.unit_economics.models import AllocationVersion, CurrentCostSettings, UnitCost


def correct_project_base_currency(
    session: Session,
    *,
    project_id: uuid.UUID,
    old_currency_id: uuid.UUID,
    new_currency_id: uuid.UUID,
) -> dict[str, int]:
    """Relabel cost records whose denomination is fixed to the project base."""
    counts: dict[str, int] = {}
    for model in (AllocationVersion, UnitCost):
        result = session.execute(
            update(model)
            .where(model.project_id == project_id, model.currency_id == old_currency_id)
            .values(currency_id=new_currency_id)
        )
        if result.rowcount:
            counts[f"{model.__tablename__}.currency_id"] = result.rowcount
    settings = session.execute(
        update(CurrentCostSettings)
        .where(
            CurrentCostSettings.project_id == project_id,
            CurrentCostSettings.currency_id == old_currency_id,
        )
        .values(currency_id=new_currency_id, revision=CurrentCostSettings.revision + 1)
    )
    if settings.rowcount:
        counts["ue_current_cost_settings.currency_id"] = settings.rowcount
    return counts
