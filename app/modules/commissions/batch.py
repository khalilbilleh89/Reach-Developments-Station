"""Released commissions are operational information, never paid cash."""

import uuid
from decimal import Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.modules.commissions.models import CommissionGrant


def released(session: Session, project_ids: Select) -> dict[uuid.UUID, dict[uuid.UUID, Decimal]]:
    result: dict[uuid.UUID, dict[uuid.UUID, Decimal]] = {}
    for pid, currency, amount in session.execute(
        select(
            CommissionGrant.project_id,
            CommissionGrant.currency_id,
            func.sum(CommissionGrant.commission_total),
        )
        .where(CommissionGrant.project_id.in_(project_ids), CommissionGrant.status == "released")
        .group_by(CommissionGrant.project_id, CommissionGrant.currency_id)
    ):
        result.setdefault(pid, {})[currency] = amount
    return result
