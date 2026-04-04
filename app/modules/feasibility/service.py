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
    calculate_profit_per_sqm,
    calculate_equity_multiple,
    calculate_irr,
)
from app.modules.feasibility.scenario_runner import run_sensitivity_scenarios
from app.modules.feasibility.repository import (
    FeasibilityAssumptionsRepository,
    FeasibilityResultRepository,
    FeasibilityRunRepository,
)
from app.modules.concept_design.repository import ConceptOptionRepository
from app.modules.feasibility.schemas import (
    FeasibilityAssumptionsCreate,
    FeasibilityAssumptionsResponse,
    FeasibilityAssumptionsUpdate,
    FeasibilityConstructionCostContextResponse,
    FeasibilityLineageResponse,
    FeasibilityResultResponse,
    FeasibilityRunCreate,
    FeasibilityRunList,
    FeasibilityRunRequest,
    FeasibilityRunResponse,
    FeasibilityRunUpdate,
)
from app.modules.projects.repository import ProjectRepository
from app.modules.scenario.repository import ScenarioRepository
from app.modules.construction_costs.repository import ConstructionCostRecordRepository
from app.shared.enums.finance import (
    FeasibilityDecision,
    FeasibilityRiskLevel,
    FeasibilityViabilityStatus,
)
from app.core.errors import ResourceNotFoundError, ValidationError, ConflictError
from app.core.logging import get_logger

_logger = get_logger("reach_developments.feasibility")

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
        self.concept_option_repo = ConceptOptionRepository(db)
        self.construction_cost_repo = ConstructionCostRecordRepository(db)

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
        _logger.info("Feasibility run created: id=%s", run.id)
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
        self,
        project_id: Optional[str] = None,
        scenario_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> FeasibilityRunList:
        if project_id and scenario_id:
            runs = self.run_repo.list_by_project_and_scenario(project_id, scenario_id, skip=skip, limit=limit)
            total = self.run_repo.count_by_project_and_scenario(project_id, scenario_id)
        elif project_id:
            runs = self.run_repo.list_by_project(project_id, skip=skip, limit=limit)
            total = self.run_repo.count_by_project(project_id)
        elif scenario_id:
            runs = self.run_repo.list_by_scenario(scenario_id, skip=skip, limit=limit)
            total = self.run_repo.count_by_scenario(scenario_id)
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
        if "project_id" in data.model_fields_set:
            self._validate_project_if_present(data.project_id)
        updated = self.run_repo.update(run, data)
        return FeasibilityRunResponse.model_validate(updated)

    def delete_feasibility_run(self, run_id: str) -> None:
        """Delete a feasibility run and its owned assumptions and result via cascade.

        Raises ConflictError (409) if any concept options were reverse-seeded from
        this run, to preserve lineage integrity.
        """
        run = self.run_repo.get_by_id(run_id)
        if not run:
            raise ResourceNotFoundError(
                f"Feasibility run '{run_id}' not found.",
                details={"run_id": run_id},
            )
        referencing = self.concept_option_repo.list_by_source_feasibility_run_id(run_id)
        if referencing:
            raise ConflictError(
                "Cannot delete feasibility run because concept options were reverse-seeded from it.",
                details={"run_id": run_id, "referencing_concept_option_count": len(referencing)},
            )
        self.run_repo.delete(run)
        _logger.info("Feasibility run deleted: id=%s", run_id)

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
        # Advance lifecycle: draft → assumptions_defined (or keep assumptions_defined
        # if already at that state; do not regress from 'calculated').
        if run.status == "draft":
            self.run_repo.set_status(run, "assumptions_defined")
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

    def patch_assumptions(
        self, run_id: str, data: FeasibilityAssumptionsUpdate
    ) -> FeasibilityAssumptionsResponse:
        run = self.run_repo.get_by_id(run_id)
        if not run:
            raise ResourceNotFoundError(
                f"Feasibility run '{run_id}' not found.",
                details={"run_id": run_id},
            )
        assumptions = self.assumptions_repo.get_by_run(run_id)
        if not assumptions:
            raise ResourceNotFoundError(
                f"No assumptions found for feasibility run '{run_id}'. "
                "Use POST to create assumptions before patching.",
                details={"run_id": run_id},
            )
        updated = self.assumptions_repo.update_partial(assumptions, data)
        # Advance lifecycle if still in draft (patch also counts as defining assumptions).
        if run.status == "draft":
            self.run_repo.set_status(run, "assumptions_defined")
        return FeasibilityAssumptionsResponse.model_validate(updated)

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
        profit_per_sqm = calculate_profit_per_sqm(
            outputs.developer_profit, inputs.sellable_area_sqm
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
            currency=outputs.currency,
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
            profit_per_sqm=profit_per_sqm,
        )
        _logger.info(
            "Feasibility calculation complete: run_id=%s viability=%s risk=%s",
            run_id,
            viability.value,
            risk.value,
        )
        # Advance lifecycle to 'calculated' — no re-fetch needed.
        self.run_repo.set_status_by_id(run_id, "calculated")
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
            currency=assumptions.currency,
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
            currency=data.currency,
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
            currency=data.currency,
        )
        return self._execute_calculation(run_response.id, inputs)

    # ------------------------------------------------------------------
    # Seeded creation from concept option — PR-CONCEPT-063
    # ------------------------------------------------------------------

    def get_run_for_reverse_seed(self, run_id: str) -> FeasibilityRunResponse:
        """Return a feasibility run validated for reverse-seeding into a concept.

        Raises ResourceNotFoundError (404) if the run does not exist.

        This method forms the approved module boundary for the concept design
        service to read feasibility run data.  The concept service must not
        access FeasibilityRun DB tables directly.
        """
        run = self.run_repo.get_by_id(run_id)
        if not run:
            raise ResourceNotFoundError(
                f"Feasibility run '{run_id}' not found.",
                details={"run_id": run_id},
            )
        return FeasibilityRunResponse.model_validate(run)

    def create_seeded_run(
        self,
        *,
        source_concept_option_id: str,
        scenario_id: Optional[str],
        scenario_name: str,
        sellable_area_sqm: Optional[float],
        avg_sale_price_per_sqm: Optional[float] = None,
        construction_cost_per_sqm: Optional[float] = None,
        soft_cost_ratio: float = 0.10,
        finance_cost_ratio: float = 0.05,
        sales_cost_ratio: float = 0.03,
        development_period_months: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> FeasibilityRunResponse:
        """Create a feasibility run seeded from a concept option.

        This method is called by the concept design service through the
        approved module boundary.  It creates a FeasibilityRun with
        source_concept_option_id and seed_source_type='concept_option'
        lineage fields, then persists the seeded assumptions when all
        required financial parameters are available.

        Assumptions are only persisted when *both* conditions hold:
          1. sellable_area_sqm is not None (concept has computable area).
          2. avg_sale_price_per_sqm, construction_cost_per_sqm, and
             development_period_months are all supplied.

        When either condition is missing the run is still created, but
        without an assumptions record.  The caller can supply assumptions
        later via the existing FeasibilityAssumptions endpoint.

        The caller (ConceptDesignService) is responsible for validating the
        concept option state before invoking this method.

        Parameters
        ----------
        source_concept_option_id:
            ID of the concept option being used as the seed source.
        scenario_id:
            Scenario to associate with the run (inherited from concept option).
        scenario_name:
            Name for the new feasibility run.
        sellable_area_sqm:
            Seeded from the concept engine's computed sellable area.
            May be None if the concept has no unit mix lines with sellable area.
        avg_sale_price_per_sqm:
            Optional financial assumption.  Required for assumption seeding.
        construction_cost_per_sqm:
            Optional financial assumption.  Required for assumption seeding.
        soft_cost_ratio, finance_cost_ratio, sales_cost_ratio:
            Cost ratios.  Default to standard platform values when not supplied.
        development_period_months:
            Optional development timeline.  Required for assumption seeding.
        notes:
            Optional free-text notes.

        Returns
        -------
        FeasibilityRunResponse
            The newly created feasibility run with lineage metadata.
        """
        self._require_scenario_if_present(scenario_id)

        run_create = FeasibilityRunCreate(
            scenario_id=scenario_id,
            scenario_name=scenario_name,
            notes=notes,
            source_concept_option_id=source_concept_option_id,
            seed_source_type="concept_option",
        )
        run = self.run_repo.create(run_create)

        # This condition is intentionally expressed here (and mirrored in
        # ConceptDesignService.seed_feasibility_from_concept_option) rather
        # than extracted into a shared utility.  The two checks operate on
        # different inputs (local method params vs. request payload fields)
        # and live in separate modules that must not import each other in the
        # reverse direction.  Keeping them independent preserves the module
        # boundary while remaining easy to read in isolation.
        can_seed_assumptions = (
            sellable_area_sqm is not None
            and avg_sale_price_per_sqm is not None
            and construction_cost_per_sqm is not None
            and development_period_months is not None
        )
        if can_seed_assumptions:
            assumptions_create = FeasibilityAssumptionsCreate(
                sellable_area_sqm=sellable_area_sqm,
                avg_sale_price_per_sqm=avg_sale_price_per_sqm,
                construction_cost_per_sqm=construction_cost_per_sqm,
                soft_cost_ratio=soft_cost_ratio,
                finance_cost_ratio=finance_cost_ratio,
                sales_cost_ratio=sales_cost_ratio,
                development_period_months=development_period_months,
                notes=notes,
            )
            self.assumptions_repo.upsert(run.id, assumptions_create)
            # Advance lifecycle: seeded run with full assumptions is ready for calculation.
            self.run_repo.set_status(run, "assumptions_defined")

        _logger.info(
            "Seeded feasibility run created: id=%s source_concept_option_id=%s",
            run.id,
            source_concept_option_id,
        )
        return FeasibilityRunResponse.model_validate(run)


    # ---------------------------------------------------------------------------
    # Lifecycle Lineage — PR-CONCEPT-065
    # ---------------------------------------------------------------------------

    def get_feasibility_run_lineage(self, run_id: str) -> FeasibilityLineageResponse:
        """Return a lifecycle traceability summary for a feasibility run.

        Composes lineage from canonical fields:
        - upstream: source_concept_option_id (set when run was seeded from a concept)
        - downstream: all concept options reverse-seeded from this run

        Raises ResourceNotFoundError (HTTP 404) if the run does not exist.
        """
        run = self.run_repo.get_by_id(run_id)
        if run is None:
            raise ResourceNotFoundError(f"FeasibilityRun '{run_id}' not found.")

        # Import here to avoid circular dependency — concept_design imports
        # FeasibilityService; FeasibilityService must not import ConceptDesignService
        # at module level.
        from app.modules.concept_design.repository import ConceptOptionRepository

        concept_repo = ConceptOptionRepository(self.run_repo.db)
        reverse_seeded = concept_repo.list_by_source_feasibility_run_id(run_id)

        _logger.info(
            "Lineage retrieved for feasibility run: run_id=%s "
            "reverse_seeded_concepts=%d",
            run_id,
            len(reverse_seeded),
        )

        return FeasibilityLineageResponse(
            record_id=run_id,
            source_concept_option_id=run.source_concept_option_id,
            reverse_seeded_concept_options=[c.id for c in reverse_seeded],
            project_id=run.project_id,
        )

    # ---------------------------------------------------------------------------
    # Construction cost context — PR-V6-10
    # ---------------------------------------------------------------------------

    def get_construction_cost_context(
        self, run_id: str
    ) -> FeasibilityConstructionCostContextResponse:
        """Return a read-only construction cost context for a feasibility run.

        Compares recorded project construction cost totals against the
        feasibility-side assumed construction cost.  Variance fields are only
        populated when *both* sides are available.  All fields are null-safe;
        the ``note`` field always explains the comparison state.

        Raises ResourceNotFoundError (HTTP 404) if the feasibility run does not
        exist.  Missing project linkage, missing cost records, or missing
        assumptions are handled with explicit notes — they are not errors.

        This method is read-only.  It does not mutate feasibility or
        construction records.
        """
        from decimal import Decimal

        run = self.run_repo.get_by_id(run_id)
        if run is None:
            raise ResourceNotFoundError(
                f"Feasibility run '{run_id}' not found.",
                details={"run_id": run_id},
            )

        project_id: Optional[str] = run.project_id

        # --- No linked project ---
        if project_id is None:
            _logger.info(
                "Construction cost context: run_id=%s has no linked project", run_id
            )
            return FeasibilityConstructionCostContextResponse(
                feasibility_run_id=run_id,
                project_id=None,
                has_cost_records=False,
                active_record_count=0,
                recorded_construction_cost_total=None,
                by_category=None,
                by_stage=None,
                assumed_construction_cost=None,
                variance_amount=None,
                variance_pct=None,
                note="No project linked to this feasibility run. Assign a project to enable construction cost context.",
            )

        # --- Fetch recorded construction cost summary ---
        active_count, grand_total, by_category, by_stage = (
            self.construction_cost_repo.get_aggregate_summary(project_id)
        )
        has_cost_records = active_count > 0

        # --- Fetch feasibility-side assumed construction cost ---
        # Compute assumed_construction_cost in Decimal to avoid float multiplication
        # artifacts (e.g. 800.0 * 1000.0 is exact, but irrational ratios are not).
        # Convert to float only at the response boundary.
        assumptions = self.assumptions_repo.get_by_run(run_id)
        assumed_decimal: Optional[Decimal] = None
        if (
            assumptions is not None
            and assumptions.construction_cost_per_sqm is not None
            and assumptions.sellable_area_sqm is not None
        ):
            assumed_decimal = (
                Decimal(str(assumptions.construction_cost_per_sqm))
                * Decimal(str(assumptions.sellable_area_sqm))
            )

        # --- Determine note and variance ---
        variance_amount: Optional[Decimal] = None
        variance_pct: Optional[float] = None
        note: str

        if not has_cost_records and assumed_decimal is None:
            note = "No construction cost records and no feasibility assumptions defined yet."
        elif not has_cost_records:
            note = "No construction cost records for this project yet."
        elif assumed_decimal is None:
            note = (
                "Construction cost records exist but the feasibility-side cost basis "
                "is unavailable (assumptions not yet defined)."
            )
        else:
            # Both sides available — compute transparent variance entirely in Decimal.
            # No float round-trip: assumed_decimal comes directly from Numeric DB columns
            # via Decimal(str(...)), so variance_amount is clean.
            variance_amount = grand_total - assumed_decimal
            if assumed_decimal != Decimal("0"):
                variance_pct = float(variance_amount / assumed_decimal)
            else:
                variance_pct = None
            note = (
                "Variance shown: recorded construction cost total vs. "
                "feasibility-side assumed construction cost "
                "(construction_cost_per_sqm × sellable_area_sqm)."
            )

        _logger.info(
            "Construction cost context retrieved: run_id=%s project_id=%s "
            "active_record_count=%d has_cost_records=%s assumed_cost=%s",
            run_id,
            project_id,
            active_count,
            has_cost_records,
            assumed_decimal,
        )

        return FeasibilityConstructionCostContextResponse(
            feasibility_run_id=run_id,
            project_id=project_id,
            has_cost_records=has_cost_records,
            active_record_count=active_count,
            recorded_construction_cost_total=grand_total if has_cost_records else None,
            by_category=by_category if has_cost_records else None,
            by_stage=by_stage if has_cost_records else None,
            assumed_construction_cost=float(assumed_decimal) if assumed_decimal is not None else None,
            variance_amount=variance_amount,
            variance_pct=variance_pct,
            note=note,
        )
