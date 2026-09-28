"""Collections-owned participation in a project denomination correction."""

from __future__ import annotations

import uuid

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.modules.collections.models import CollectionReceipt, CollectionRefund


def correct_project_base_currency(
    session: Session,
    *,
    project_id: uuid.UUID,
    old_currency_id: uuid.UUID,
    new_currency_id: uuid.UUID,
    sale_contract_ids: frozenset[uuid.UUID],
) -> dict[str, int]:
    """Relabel cash records only when their owning sale denomination was corrected."""
    if not sale_contract_ids:
        return {}
    counts: dict[str, int] = {}
    for model in (CollectionReceipt, CollectionRefund):
        result = session.execute(
            update(model)
            .where(
                model.project_id == project_id,
                model.sale_contract_id.in_(sale_contract_ids),
                model.currency_id == old_currency_id,
            )
            .values(currency_id=new_currency_id)
        )
        if result.rowcount:
            counts[f"{model.__tablename__}.currency_id"] = result.rowcount
    return counts
