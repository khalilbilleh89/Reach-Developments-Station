"""
finance.revenue_router

FastAPI router for the scenario-based Revenue Recognition Engine.

Router prefix: /finance/revenue
Full prefix:   /api/v1/finance/revenue/...

Endpoints
---------
  GET  /api/v1/finance/revenue/{scenario_id}
       Return the revenue schedule for a development scenario.

Authentication
--------------
All endpoints inherit the bearer-token authentication requirement from
the router-level dependency (get_current_user_payload).

Architecture note
-----------------
This router is registered in app/main.py with prefix /api/v1 *after*
the main finance router so that the static path
/api/v1/finance/revenue/overview (owned by the finance router) continues
to take priority over the dynamic /{scenario_id} path.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.security import get_current_user_payload
from app.modules.finance.revenue_models import RecognitionStrategy
from app.modules.finance.revenue_service import ScenarioRevenueService
from app.modules.finance.schemas import ScenarioRevenueScheduleResponse

router = APIRouter(
    prefix="/finance/revenue",
    tags=["Finance"],
    dependencies=[Depends(get_current_user_payload)],
)


# ---------------------------------------------------------------------------
# Dependency factories
# ---------------------------------------------------------------------------


def _get_scenario_revenue_service(
    db: Session = Depends(get_db),
) -> ScenarioRevenueService:
    return ScenarioRevenueService(db)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/{scenario_id}",
    response_model=ScenarioRevenueScheduleResponse,
    summary="Get revenue schedule for a scenario",
)
def get_scenario_revenue_schedule(
    scenario_id: str,
    service: Annotated[ScenarioRevenueService, Depends(_get_scenario_revenue_service)],
    strategy: RecognitionStrategy = Query(
        default=RecognitionStrategy.ON_CONTRACT_SIGNING,
        description=(
            "Revenue recognition strategy to apply.  "
            "Supported values: on_contract_signing (default), "
            "on_construction_progress, on_unit_delivery."
        ),
    ),
) -> ScenarioRevenueScheduleResponse:
    """Return the period-based revenue schedule for a development scenario.

    The schedule lists the revenue recognized in each calendar month
    according to the selected recognition strategy.

    Recognition strategies
    ----------------------
    - **on_contract_signing** *(default)*: revenue recognized in the month
      the sales contract was signed.
    - **on_construction_progress**: revenue distributed across periods
      proportional to construction milestone completion percentages.
    - **on_unit_delivery**: revenue recognized in the month the unit is
      delivered to the buyer.

    Response example
    ----------------
    ```json
    {
      "scenario_id": "abc-123",
      "strategy": "on_contract_signing",
      "revenue_schedule": [
        {"period": "2026-01", "revenue": 2000000},
        {"period": "2026-02", "revenue": 3500000}
      ],
      "total_revenue": 5500000
    }
    ```

    Raises HTTP 404 when the scenario does not exist.
    """
    result = service.get_revenue_schedule(
        scenario_id=scenario_id,
        strategy=strategy,
    )
    return ScenarioRevenueScheduleResponse(
        scenario_id=result.scenario_id,
        strategy=result.strategy,
        revenue_schedule=[
            {"period": e.period, "revenue": e.revenue}
            for e in result.revenue_schedule
        ],
        total_revenue=result.total_revenue,
    )
