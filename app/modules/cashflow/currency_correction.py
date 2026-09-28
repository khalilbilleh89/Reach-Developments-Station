"""Cashflow-owned participation in a project denomination correction."""

from __future__ import annotations

import uuid

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.modules.cashflow.models import (
    CashflowDevelopmentMovement,
    CashflowFinancingMovement,
    CashflowForecastVersion,
)


def correct_project_base_currency(
    session: Session,
    *,
    project_id: uuid.UUID,
    old_currency_id: uuid.UUID,
    new_currency_id: uuid.UUID,
) -> dict[str, int]:
    """Relabel cashflow rows that can only be recorded in the project base currency."""
    counts: dict[str, int] = {}
    for model in (
        CashflowForecastVersion,
        CashflowDevelopmentMovement,
        CashflowFinancingMovement,
    ):
        result = session.execute(
            update(model)
            .where(model.project_id == project_id, model.currency_id == old_currency_id)
            .values(currency_id=new_currency_id)
        )
        if result.rowcount:
            counts[f"{model.__tablename__}.currency_id"] = result.rowcount
    return counts
