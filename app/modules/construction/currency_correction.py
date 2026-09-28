"""Construction-owned participation in a project denomination correction."""

from __future__ import annotations

import uuid

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.modules.construction.models import BudgetVersion, Contract, ForecastVersion, Payment


def correct_project_base_currency(
    session: Session,
    *,
    project_id: uuid.UUID,
    old_currency_id: uuid.UUID,
    new_currency_id: uuid.UUID,
) -> dict[str, int]:
    """Relabel records whose services require the project or contract base denomination."""
    counts: dict[str, int] = {}
    for model in (BudgetVersion, Contract, ForecastVersion, Payment):
        result = session.execute(
            update(model)
            .where(model.project_id == project_id, model.currency_id == old_currency_id)
            .values(currency_id=new_currency_id)
        )
        if result.rowcount:
            counts[f"{model.__tablename__}.currency_id"] = result.rowcount
    return counts
