"""Commissions-owned participation in a project denomination correction."""

from __future__ import annotations

import uuid

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.modules.commissions.models import CommissionGrant


def correct_project_base_currency(
    session: Session,
    *,
    project_id: uuid.UUID,
    old_currency_id: uuid.UUID,
    new_currency_id: uuid.UUID,
    sale_contract_ids: frozenset[uuid.UUID],
) -> dict[str, int]:
    """Relabel grants only when the sale from which they were copied was corrected."""
    if not sale_contract_ids:
        return {}
    result = session.execute(
        update(CommissionGrant)
        .where(
            CommissionGrant.project_id == project_id,
            CommissionGrant.sale_contract_id.in_(sale_contract_ids),
            CommissionGrant.currency_id == old_currency_id,
        )
        .values(currency_id=new_currency_id)
    )
    return {"commission_grants.currency_id": result.rowcount} if result.rowcount else {}
