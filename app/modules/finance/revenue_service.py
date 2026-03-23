"""
finance.revenue_service

Service-layer orchestration for the scenario-based Revenue Recognition Engine.

Responsibilities
----------------
- Validate that the requested scenario exists.
- Retrieve the associated unit-sales data from the database via
  cross-module joins (Scenario → project_id → contracts).
- Build the engine input value object.
- Delegate revenue-schedule calculation to the pure engine.
- Return the structured result.

Supported strategies (DB-backed)
---------------------------------
ON_CONTRACT_SIGNING
    Fully supported.  All required data (contract_date, contract_price) is
    persisted in the sales schema.

ON_UNIT_DELIVERY
    Supported with fallback.  When no delivery date is stored for a contract
    the engine falls back to the contract signing date, preserving the same
    behaviour as ON_CONTRACT_SIGNING for those units.

ON_CONSTRUCTION_PROGRESS
    Not supported via this service.  Construction milestone completion
    percentages are not currently persisted.  Requests using this strategy
    are rejected with a ValidationError.

No direct database mutations are performed here; this is a read-only
service.  All financial calculations are delegated to
:mod:`app.modules.finance.revenue_engine`.
"""

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.core.errors import ResourceNotFoundError, ValidationError
from app.core.logging import get_logger
from app.modules.buildings.models import Building
from app.modules.finance.revenue_engine import generate_revenue_schedule
from app.modules.finance.revenue_models import (
    RecognitionStrategy,
    RevenueScheduleInput,
    RevenueScheduleResult,
    UnitSaleData,
)
from app.modules.floors.models import Floor
from app.modules.phases.models import Phase
from app.modules.sales.models import SalesContract
from app.modules.scenario.models import Scenario
from app.modules.units.models import Unit

_logger = get_logger("reach_developments.finance.revenue_service")


class ScenarioRevenueService:
    """Generates a period-based revenue schedule for a given scenario.

    The service looks up the scenario's associated project and queries all
    sales contracts linked to units within that project hierarchy.  The
    contract data is then passed to the recognition engine using the
    requested strategy.

    Parameters
    ----------
    db:
        Active SQLAlchemy session injected by FastAPI's dependency system.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_revenue_schedule(
        self,
        scenario_id: str,
        strategy: RecognitionStrategy = RecognitionStrategy.ON_CONTRACT_SIGNING,
    ) -> RevenueScheduleResult:
        """Return the revenue schedule for a scenario.

        Parameters
        ----------
        scenario_id:
            The unique identifier of the scenario.
        strategy:
            Recognition strategy to apply.  Defaults to
            ``ON_CONTRACT_SIGNING``.

        Returns
        -------
        RevenueScheduleResult
            Chronologically ordered revenue schedule with per-period totals.

        Raises
        ------
        ResourceNotFoundError
            When the scenario does not exist.
        ValidationError
            When the requested strategy requires data that is not yet
            persisted for the scenario's project.  Specifically,
            ``ON_CONSTRUCTION_PROGRESS`` is rejected because milestone
            completion percentages are not stored in the current schema.
            ``ON_UNIT_DELIVERY`` is accepted and will use the contract
            signing date as a fallback when no delivery date is present.
        """
        scenario = self._require_scenario(scenario_id)
        project_id: Optional[str] = scenario.project_id

        if strategy == RecognitionStrategy.ON_CONSTRUCTION_PROGRESS:
            raise ValidationError(
                "Strategy 'on_construction_progress' is not supported via the "
                "scenario revenue API because construction milestone data is not "
                "currently persisted.  Use 'on_contract_signing' or "
                "'on_unit_delivery' instead.",
                details={"strategy": strategy.value, "scenario_id": scenario_id},
            )

        unit_sales = self._fetch_unit_sales(project_id)

        _logger.info(
            "Generating revenue schedule",
            extra={
                "scenario_id": scenario_id,
                "project_id": project_id,
                "strategy": strategy.value,
                "unit_sales_count": len(unit_sales),
            },
        )

        inputs = RevenueScheduleInput(
            scenario_id=scenario_id,
            unit_sales=unit_sales,
            strategy=strategy,
        )
        return generate_revenue_schedule(inputs)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_scenario(self, scenario_id: str) -> Scenario:
        """Fetch scenario or raise ResourceNotFoundError."""
        scenario = (
            self.db.query(Scenario).filter(Scenario.id == scenario_id).first()
        )
        if not scenario:
            raise ResourceNotFoundError(
                f"Scenario '{scenario_id}' not found.",
                details={"scenario_id": scenario_id},
            )
        return scenario

    def _fetch_unit_sales(self, project_id: Optional[str]) -> list:
        """Return UnitSaleData records for all contracts under the project.

        When ``project_id`` is None (the scenario is not yet linked to a
        project) an empty list is returned rather than raising an error, so
        that the endpoint still returns a valid (empty) schedule.
        """
        if not project_id:
            return []

        rows = (
            self.db.query(
                SalesContract.id,
                SalesContract.contract_price,
                SalesContract.contract_date,
            )
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(Phase.project_id == project_id)
            .all()
        )

        return [
            UnitSaleData(
                contract_id=str(row[0]),
                contract_total=float(row[1]),
                contract_date=row[2] if isinstance(row[2], date) else row[2],
            )
            for row in rows
        ]
