"""Read-only public contracts for Commission history references."""

import uuid

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.modules.commissions.models import CommissionAllocation


def agent_has_commission_history(
    session: Session,
    *,
    project_id: uuid.UUID,
    sales_agent_id: uuid.UUID,
) -> bool:
    """Return whether an Agent is referenced by any Commission allocation."""
    return bool(
        session.scalar(
            select(
                exists().where(
                    CommissionAllocation.project_id == project_id,
                    CommissionAllocation.sales_agent_id == sales_agent_id,
                )
            )
        )
    )
