"""
feasibility.service

Application-layer orchestration for feasibility workflows.
Validates domain invariants and coordinates repository and engine calls.
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.modules.feasibility.engines.feasibility_engine import FeasibilityInputs, run_feasibility
from app.core.calculation_engine.registry import (
    calculate_break_even_price_per_sqm,
    calculate_break_even_sellable_sqm,
    calculate_equity_multiple,
    calculate_irr,
)
from app.modules.feasibility.scenario_runner import run_sensitivity_scenarios
from app.modules.feasibility.repository import (
    FeasibilityAssumptionsRepository,
    FeasibilityResultRepository,
    FeasibilityRunRepository,
)
from app.modules.feasibility.schemas import (
    FeasibilityAssumptionsCreate,
    FeasibilityAssumptionsResponse,
    FeasibilityResultResponse,
    FeasibilityRunCreate,
    FeasibilityRunList,
    FeasibilityRunRequest,
    FeasibilityRunResponse,
    FeasibilityRunUpdate,
)
from app.modules.projects.repository import ProjectRepository
from app.modules.scenario.repository import ScenarioRepository
from app.shared.enums.finance import (
    FeasibilityDecision,
    FeasibilityRiskLevel,
    FeasibilityViabilityStatus,
)
from app.core.errors import ResourceNotFoundError, ValidationError

# ---------------------------------------------------------------------------
# Viability thresholds — v1 business policy
#
# These thresholds represent the initial classification policy for the
# Developer Operating System and are subject to future configuration or
# market-specific overrides.  They are not universal finance law.
#
# profit_margin >= 20 %            → VIABLE
# 10 % <= profit_margin < 20 %     → MARGINAL
# profit_margin < 10 %             → NOT_VIABLE
#
# irr >= 25 %                      → LOW risk
# 15 % <= irr < 25 %               → MEDIUM risk
# irr < 15 %                       → HIGH risk
# ---------------------------------------------------------------------------

_VIABLE_MARGIN_THRESHOLD = 0.20
_MARGINAL_MARGIN_THRESHOLD = 0.10
_LOW_RISK_IRR_THRESHOLD = 0.25
_MEDIUM_RISK_IRR_THRESHOLD = 0.15


def _evaluate_viability(profit_margin: float) -> FeasibilityViabilityStatus:
    """Classify project viability from profit margin (v1 policy thresholds)."""
    if profit_margin >= _VIABLE_MARGIN_THRESHOLD:
        return FeasibilityViabilityStatus.VIABLE
    if profit_margin >= _MARGINAL_MARGIN_THRESHOLD:
        return FeasibilityViabilityStatus.MARGINAL
    return FeasibilityViabilityStatus.NOT_VIABLE


def _evaluate_risk_level(irr: float) -> FeasibilityRiskLevel:
    """Classify risk level from annualised IRR (v1 policy thresholds)."""
    if irr >= _LOW_RISK_IRR_THRESHOLD:
        return FeasibilityRiskLevel.LOW
    if irr >= _MEDIUM_RISK_IRR_THRESHOLD:
        return FeasibilityRiskLevel.MEDIUM
    return FeasibilityRiskLevel.HIGH


def _derive_decision(viability: FeasibilityViabilityStatus) -> FeasibilityDecision:
    """Map viability status to a decision recommendation."""
    return FeasibilityDecision(viability.value)


def _compute_payback_period(development_period_months: int, profit_margin: float) -> Optional[float]:
    """Return payback period in years.

    For a standard development project where all costs are incurred over the
    development period and all revenue is received at completion, the payback
    period equals the development period itself.  Returns None for projects
    with no profit (not viable).
    """
    if profit_margin <= 0.0:
        return None
    return development_period_months / 12.0


class FeasibilityService:
    def __init__(self, db: Session) -> None:
        self.run_repo = FeasibilityRunRepository(db)
        self.assumptions_repo = FeasibilityAssumptionsRepository(db)
        self.result_repo = FeasibilityResultRepository(db)
        self.project_repo = ProjectRepository(db)
        self.scenario_repo = ScenarioRepository(db)

    # ------------------------------------------------------------------
    # Internal helpers — shared validation guards
    # ------------------------------------------------------------------

    def _validate_project_if_present(self, project_id: Optional[str]) -> None:
        """Raise 404 if project_id is provided but does not exist."""
        if project_id is not None:
            project = self.project_repo.get_by_id(project_id)
            if not project:
                raise ResourceNotFoundError(
                    f"Project '{project_id}' not found.",
                    details={"project_id": project_id},
                )

    def _require_scenario_if_present(self, scenario_id: Optional[str]) -> None:
        """Raise 404 if scenario_id is provided but does not exist."""
        if scenario_id is not None:
            scenario = self.scenario_repo.get_by_id(scenario_id)
            if not scenario:
                raise ResourceNotFoundError(
                    f"Scenario '{scenario_id}' not found.",
                    details={"scenario_id": scenario_id},
                )

    # ------------------------------------------------------------------
    # Run operations
    # ------------------------------------------------------------------

    def create_feasibility_run(self, data: FeasibilityRunCreate) -> FeasibilityRunResponse:
        self._validate_project_if_present(data.project_id)
        self._require_scenario_if_present(data.scenario_id)
        run = self.run_repo.create(data)
        return FeasibilityRunResponse.model_validate(run)

    def get_feasibility_run(self, run_id: str) -> FeasibilityRunResponse:
        run = self.run_repo.get_by_id(run_id)
        if not run:
            raise ResourceNotFoundError(
                f"Feasibility run '{run_id}' not found.",
                details={"run_id": run_id},
            )
        return FeasibilityRunResponse.model_validate(run)

    def list_feasibility_runs(
        self, project_id: Optional[str] = None, skip: int = 0, limit: int = 100
    ) -> FeasibilityRunList:
        if project_id:
            runs = self.run_repo.list_by_project(project_id, skip=skip, limit=limit)
            total = self.run_repo.count_by_project(project_id)
        else:
            runs = self.run_repo.list_all(skip=skip, limit=limit)
            total = self.run_repo.count_all()
        return FeasibilityRunList(
            items=[FeasibilityRunResponse.model_validate(r) for r in runs],
            total=total,
        )

    def update_feasibility_run(self, run_id: str, data: FeasibilityRunUpdate) -> FeasibilityRunResponse:
        run = self.run_repo.get_by_id(run_id)
        if not run:
            raise ResourceNotFoundError(
                f"Feasibility run '{run_id}' not found.",
                details={"run_id": run_id},
            )
        updated = self.run_repo.update(run, data)
        return FeasibilityRunResponse.model_validate(updated)

    # ------------------------------------------------------------------
    # Assumptions operations
    # ------------------------------------------------------------------

    def update_assumptions(
        self, run_id: str, data: FeasibilityAssumptionsCreate
    ) -> FeasibilityAssumptionsResponse:
        run = self.run_repo.get_by_id(run_id)
        if not run:
            raise ResourceNotFoundError(
                f"Feasibility run '{run_id}' not found.",
                details={"run_id": run_id},
            )
        assumptions = self.assumptions_repo.upsert(run_id, data)
        return FeasibilityAssumptionsResponse.model_validate(assumptions)

    def get_assumptions(self, run_id: str) -> FeasibilityAssumptionsResponse:
        run = self.run_repo.get_by_id(run_id)
        if not run:
            raise ResourceNotFoundError(
                f"Feasibility run '{run_id}' not found.",
                details={"run_id": run_id},
            )
        assumptions = self.assumptions_repo.get_by_run(run_id)
        if not assumptions:
            raise ResourceNotFoundError(
                f"No assumptions found for feasibility run '{run_id}'.",
                details={"run_id": run_id},
            )
        return FeasibilityAssumptionsResponse.model_validate(assumptions)

    # ------------------------------------------------------------------
    # Calculation operations
    # ------------------------------------------------------------------

    def _execute_calculation(
        self, run_id: str, inputs: FeasibilityInputs
    ) -> FeasibilityResultResponse:
        """Execute the feasibility calculation from validated inputs and persist results."""
        outputs = run_feasibility(inputs)

        irr = calculate_irr(
            total_cost=outputs.total_cost,
            gdv=outputs.gdv,
            development_period_months=inputs.development_period_months,
        )
        equity_multiple = calculate_equity_multiple(outputs.gdv, outputs.total_cost)
        break_even_price = calculate_break_even_price_per_sqm(
            outputs.total_cost, inputs.sellable_area_sqm
        )
        break_even_units = calculate_break_even_sellable_sqm(
            outputs.total_cost, inputs.avg_sale_price_per_sqm
        )
        scenario_outputs = run_sensitivity_scenarios(inputs)

        viability = _evaluate_viability(outputs.profit_margin)
        risk = _evaluate_risk_level(irr)
        decision = _derive_decision(viability)
        payback = _compute_payback_period(inputs.development_period_months, outputs.profit_margin)

        result = self.result_repo.create_or_replace(
            run_id=run_id,
            gdv=outputs.gdv,
            construction_cost=outputs.construction_cost,
            soft_cost=outputs.soft_cost,
            finance_cost=outputs.finance_cost,
            sales_cost=outputs.sales_cost,
            total_cost=outputs.total_cost,
            developer_profit=outputs.developer_profit,
            profit_margin=outputs.profit_margin,
            irr_estimate=outputs.irr_estimate,
            irr=irr,
            equity_multiple=equity_multiple,
            break_even_price=break_even_price,
            break_even_units=break_even_units,
            scenario_outputs=scenario_outputs,
            viability_status=viability.value,
            risk_level=risk.value,
            decision=decision.value,
            payback_period=payback,
        )
        return FeasibilityResultResponse.model_validate(result)

    def run_feasibility_calculation(self, run_id: str) -> FeasibilityResultResponse:
        run = self.run_repo.get_by_id(run_id)
        if not run:
            raise ResourceNotFoundError(
                f"Feasibility run '{run_id}' not found.",
                details={"run_id": run_id},
            )
        assumptions = self.assumptions_repo.get_by_run(run_id)
        if not assumptions:
            raise ValidationError(
                f"Assumptions must be set before calculating feasibility run '{run_id}'.",
                details={"run_id": run_id},
            )
        # Validate all required fields are present
        required_fields = [
            "sellable_area_sqm",
            "avg_sale_price_per_sqm",
            "construction_cost_per_sqm",
            "soft_cost_ratio",
            "finance_cost_ratio",
            "sales_cost_ratio",
            "development_period_months",
        ]
        for field in required_fields:
            if getattr(assumptions, field) is None:
                raise ValidationError(
                    f"Assumption field '{field}' is required but missing.",
                    details={"run_id": run_id, "field": field},
                )

        inputs = FeasibilityInputs(
            sellable_area_sqm=float(assumptions.sellable_area_sqm),
            avg_sale_price_per_sqm=float(assumptions.avg_sale_price_per_sqm),
            construction_cost_per_sqm=float(assumptions.construction_cost_per_sqm),
            soft_cost_ratio=float(assumptions.soft_cost_ratio),
            finance_cost_ratio=float(assumptions.finance_cost_ratio),
            sales_cost_ratio=float(assumptions.sales_cost_ratio),
            development_period_months=int(assumptions.development_period_months),
        )
        return self._execute_calculation(run_id, inputs)

    def get_feasibility_result(self, run_id: str) -> FeasibilityResultResponse:
        run = self.run_repo.get_by_id(run_id)
        if not run:
            raise ResourceNotFoundError(
                f"Feasibility run '{run_id}' not found.",
                details={"run_id": run_id},
            )
        result = self.result_repo.get_by_run(run_id)
        if not result:
            raise ResourceNotFoundError(
                f"No result found for feasibility run '{run_id}'. Run the calculation first.",
                details={"run_id": run_id},
            )
        return FeasibilityResultResponse.model_validate(result)

    # ------------------------------------------------------------------
    # Convenience: run feasibility in a single request
    # ------------------------------------------------------------------

    def run_feasibility_for_scenario(self, data: FeasibilityRunRequest) -> FeasibilityResultResponse:
        """Create a run, set assumptions, execute calculation, and return results.

        This is the convenience endpoint that maps to POST /feasibility/run.
        All inline assumptions are required; scenario_id is optional and used
        for lineage tracking only.

        Persistence behaviour: run creation, assumption upsert, and result
        persistence are sequential DB operations, not wrapped in a single
        transaction.  If the calculation step fails after the run and
        assumptions have been persisted, those earlier records will remain.
        The result can then be obtained by retrying POST /feasibility/runs/{id}/calculate
        once the error is resolved.
        """
        # Validate references first so no DB records are created on invalid input.
        self._validate_project_if_present(data.project_id)
        self._require_scenario_if_present(data.scenario_id)

        run_create = FeasibilityRunCreate(
            project_id=data.project_id,
            scenario_id=data.scenario_id,
            scenario_name=data.scenario_name,
            scenario_type=data.scenario_type,
            notes=data.notes,
        )
        run_response = self.create_feasibility_run(run_create)

        assumptions_create = FeasibilityAssumptionsCreate(
            sellable_area_sqm=data.sellable_area_sqm,
            avg_sale_price_per_sqm=data.avg_sale_price_per_sqm,
            construction_cost_per_sqm=data.construction_cost_per_sqm,
            soft_cost_ratio=data.soft_cost_ratio,
            finance_cost_ratio=data.finance_cost_ratio,
            sales_cost_ratio=data.sales_cost_ratio,
            development_period_months=data.development_period_months,
        )
        self.assumptions_repo.upsert(run_response.id, assumptions_create)

        inputs = FeasibilityInputs(
            sellable_area_sqm=data.sellable_area_sqm,
            avg_sale_price_per_sqm=data.avg_sale_price_per_sqm,
            construction_cost_per_sqm=data.construction_cost_per_sqm,
            soft_cost_ratio=data.soft_cost_ratio,
            finance_cost_ratio=data.finance_cost_ratio,
            sales_cost_ratio=data.sales_cost_ratio,
            development_period_months=data.development_period_months,
        )
        return self._execute_calculation(run_response.id, inputs)


