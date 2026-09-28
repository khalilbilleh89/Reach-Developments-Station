"""Payment Plans-owned participation in a project denomination correction."""

from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.modules.payment_plans.models import PaymentPlan, PaymentPlanVersion


def correct_project_base_currency(
    session: Session,
    *,
    project_id: uuid.UUID,
    old_currency_id: uuid.UUID,
    new_currency_id: uuid.UUID,
    sale_contract_ids: frozenset[uuid.UUID],
) -> dict[str, int]:
    """Relabel frozen schedules only when their owning sale was corrected."""
    if not sale_contract_ids:
        return {}
    plan_ids = select(PaymentPlan.id).where(
        PaymentPlan.project_id == project_id,
        PaymentPlan.sale_contract_id.in_(sale_contract_ids),
    )
    result = session.execute(
        update(PaymentPlanVersion)
        .where(
            PaymentPlanVersion.project_id == project_id,
            PaymentPlanVersion.payment_plan_id.in_(plan_ids),
            PaymentPlanVersion.currency_id == old_currency_id,
        )
        .values(currency_id=new_currency_id)
    )
    return {"payment_plan_versions.currency_id": result.rowcount} if result.rowcount else {}
