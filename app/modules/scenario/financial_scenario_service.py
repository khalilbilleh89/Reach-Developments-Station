"""
scenario.financial_scenario_service

Application-layer orchestration for Financial Scenario Modeling.

Responsibilities
----------------
- Validate that the parent scenario exists.
- Build FinancialScenarioAssumptions from the request payload.
- Apply optional override values on top of baseline assumptions.
- Delegate all financial calculations to the Financial Scenario Engine
  (which in turn calls the Calculation Engine).
- Persist the run result as a FinancialScenarioRun record.
- Provide list, get, and delete operations for runs.
- Provide a comparison workflow that fetches runs and delegates to
  the engine comparison function.

Architecture rules
------------------
- No financial formula duplication — all calculations are in the engine.
- No direct DB manipulation for calculated values; the engine produces
  results, the service stores them.
- Sales, pricing, and project execution records are never mutated here.
- Cross-layer access goes through this service only, not direct DB queries
  in routers or UI components.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.errors import ResourceNotFoundError, ValidationError
from app.core.logging import get_logger
from app.modules.scenario.financial_scenario_engine import (
    FinancialScenarioAssumptions,
    FinancialScenarioRunResult,
    ScenarioOverrides,
    compare_financial_scenarios,
    run_financial_scenario,
)
from app.modules.scenario.models import FinancialScenarioRun, Scenario
from app.modules.scenario.schemas import (
    FinancialScenarioCompareRequest,
    FinancialScenarioCompareResponse,
    FinancialScenarioRunCreate,
    FinancialScenarioRunDelta,
    FinancialScenarioRunList,
    FinancialScenarioRunResponse,
)

_logger = get_logger("reach_developments.scenario.financial")


class FinancialScenarioService:
    """Orchestrates financial scenario run lifecycle for a parent scenario."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_scenario(self, scenario_id: str) -> Scenario:
        scenario = self.db.query(Scenario).filter(Scenario.id == scenario_id).first()
        if not scenario:
            raise ResourceNotFoundError(
                f"Scenario '{scenario_id}' not found.",
                details={"scenario_id": scenario_id},
            )
        return scenario

    def _require_run(self, run_id: str) -> FinancialScenarioRun:
        run = (
            self.db.query(FinancialScenarioRun)
            .filter(FinancialScenarioRun.id == run_id)
            .first()
        )
        if not run:
            raise ResourceNotFoundError(
                f"FinancialScenarioRun '{run_id}' not found.",
                details={"run_id": run_id},
            )
        return run

    def _build_assumptions(
        self, payload: FinancialScenarioRunCreate
    ) -> FinancialScenarioAssumptions:
        """Convert the Pydantic request schema to the engine dataclass."""
        a = payload.assumptions
        return FinancialScenarioAssumptions(
            gdv=a.gdv,
            total_cost=a.total_cost,
            equity_invested=a.equity_invested,
            sellable_area_sqm=a.sellable_area_sqm,
            avg_sale_price_per_sqm=a.avg_sale_price_per_sqm,
            development_period_months=a.development_period_months,
            annual_discount_rate=a.annual_discount_rate,
            sales_pace_months_override=a.sales_pace_months_override,
            pricing_uplift_pct=a.pricing_uplift_pct,
            cost_inflation_pct=a.cost_inflation_pct,
            debt_ratio=a.debt_ratio,
            label=a.label,
            notes=a.notes,
        )

    def _result_to_json(self, result: FinancialScenarioRunResult) -> Dict[str, Any]:
        """Serialise engine result to a plain dict for JSON storage."""
        return {
            "label": result.label,
            "effective_gdv": result.effective_gdv,
            "effective_total_cost": result.effective_total_cost,
            "effective_equity_invested": result.effective_equity_invested,
            "effective_development_period_months": result.effective_development_period_months,
            "returns": {
                "gross_profit": result.returns.gross_profit,
                "developer_margin": result.returns.developer_margin,
                "roi": result.returns.roi,
                "roe": result.returns.roe,
                "irr": result.returns.irr,
                "npv": result.returns.npv,
                "equity_multiple": result.returns.equity_multiple,
                "payback_period_months": result.returns.payback_period_months,
                "break_even_price_per_sqm": result.returns.break_even_price_per_sqm,
                "break_even_sellable_sqm": result.returns.break_even_sellable_sqm,
            },
            "cashflows": result.cashflows,
        }

    def _persist_run(
        self,
        scenario_id: str,
        result: FinancialScenarioRunResult,
        is_baseline: bool,
        notes: Optional[str],
    ) -> FinancialScenarioRun:
        """Persist the engine result as a FinancialScenarioRun record."""
        run = FinancialScenarioRun(
            scenario_id=scenario_id,
            label=result.label,
            notes=notes,
            is_baseline=is_baseline,
            assumptions_json=result.assumptions_used,
            results_json=self._result_to_json(result),
            irr=result.returns.irr,
            npv=result.returns.npv,
            roi=result.returns.roi,
            developer_margin=result.returns.developer_margin,
            gross_profit=result.returns.gross_profit,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_run(
        self,
        scenario_id: str,
        payload: FinancialScenarioRunCreate,
    ) -> FinancialScenarioRunResponse:
        """Create and execute a financial scenario run.

        Steps:
        1. Validate parent scenario exists.
        2. Build assumptions from payload.
        3. Apply optional overrides.
        4. Execute the scenario via the Financial Scenario Engine.
        5. Persist and return the run.
        """
        self._require_scenario(scenario_id)

        assumptions = self._build_assumptions(payload)
        overrides = ScenarioOverrides(values=payload.overrides or {})
        result = run_financial_scenario(assumptions, overrides)

        run = self._persist_run(
            scenario_id=scenario_id,
            result=result,
            is_baseline=payload.is_baseline,
            notes=payload.assumptions.notes,
        )
        _logger.info(
            "FinancialScenarioRun created: id=%s scenario_id=%s label=%r irr=%.4f",
            run.id,
            scenario_id,
            run.label,
            run.irr or 0.0,
        )
        return FinancialScenarioRunResponse.model_validate(run)

    def get_run(self, scenario_id: str, run_id: str) -> FinancialScenarioRunResponse:
        """Fetch a specific financial scenario run by ID."""
        self._require_scenario(scenario_id)
        run = self._require_run(run_id)
        if run.scenario_id != scenario_id:
            raise ResourceNotFoundError(
                f"Run '{run_id}' does not belong to scenario '{scenario_id}'.",
                details={"run_id": run_id, "scenario_id": scenario_id},
            )
        return FinancialScenarioRunResponse.model_validate(run)

    def list_runs(
        self, scenario_id: str, skip: int = 0, limit: int = 100
    ) -> FinancialScenarioRunList:
        """List all financial scenario runs for a parent scenario."""
        self._require_scenario(scenario_id)
        runs = (
            self.db.query(FinancialScenarioRun)
            .filter(FinancialScenarioRun.scenario_id == scenario_id)
            .order_by(FinancialScenarioRun.created_at)
            .offset(skip)
            .limit(limit)
            .all()
        )
        total = (
            self.db.query(FinancialScenarioRun)
            .filter(FinancialScenarioRun.scenario_id == scenario_id)
            .count()
        )
        return FinancialScenarioRunList(
            items=[FinancialScenarioRunResponse.model_validate(r) for r in runs],
            total=total,
        )

    def delete_run(self, scenario_id: str, run_id: str) -> None:
        """Delete a financial scenario run."""
        self._require_scenario(scenario_id)
        run = self._require_run(run_id)
        if run.scenario_id != scenario_id:
            raise ResourceNotFoundError(
                f"Run '{run_id}' does not belong to scenario '{scenario_id}'.",
                details={"run_id": run_id, "scenario_id": scenario_id},
            )
        self.db.delete(run)
        self.db.commit()
        _logger.info("FinancialScenarioRun deleted: id=%s", run_id)

    def compare_runs(
        self,
        request: FinancialScenarioCompareRequest,
    ) -> FinancialScenarioCompareResponse:
        """Compare multiple financial scenario runs side-by-side.

        The first run in request.run_ids is treated as the baseline.
        Deltas for all subsequent runs are expressed as
        ``alternative − baseline`` for each return metric.

        Raises ResourceNotFoundError if any run ID is not found.
        Raises ValidationError if fewer than two valid run IDs are supplied.
        """
        if len(request.run_ids) < 2:
            raise ValidationError(
                "At least two run IDs are required for comparison.",
                details={"run_ids": request.run_ids},
            )

        runs: List[FinancialScenarioRun] = (
            self.db.query(FinancialScenarioRun)
            .filter(FinancialScenarioRun.id.in_(request.run_ids))
            .all()
        )
        found_ids = {r.id for r in runs}
        missing = [rid for rid in request.run_ids if rid not in found_ids]
        if missing:
            raise ResourceNotFoundError(
                f"FinancialScenarioRuns not found: {missing}",
                details={"missing_ids": missing},
            )

        # Maintain request order.
        runs_by_id = {r.id: r for r in runs}
        ordered_runs = [runs_by_id[rid] for rid in request.run_ids]

        # Reconstruct engine results from stored JSON for delta calculation.
        engine_results = _runs_to_engine_results(ordered_runs)
        comparison = compare_financial_scenarios(engine_results)

        run_responses = [
            FinancialScenarioRunResponse.model_validate(r) for r in ordered_runs
        ]
        deltas = _build_delta_responses(request.run_ids, comparison.deltas, engine_results)

        return FinancialScenarioCompareResponse(
            baseline_run_id=request.run_ids[0],
            baseline_label=ordered_runs[0].label,
            runs=run_responses,
            deltas=deltas,
        )


# ---------------------------------------------------------------------------
# Module-level helpers (not part of the public class API)
# ---------------------------------------------------------------------------


def _runs_to_engine_results(
    runs: List[FinancialScenarioRun],
) -> List[FinancialScenarioRunResult]:
    """Reconstruct minimal engine result objects from stored run JSON.

    Only the return metrics needed for comparison delta calculation are
    reconstructed; cashflows are included as stored.
    """
    from app.core.calculation_engine.types import ReturnOutputs

    results: List[FinancialScenarioRunResult] = []
    for run in runs:
        rj = (run.results_json or {}).get("returns", {})
        returns = ReturnOutputs(
            gross_profit=rj.get("gross_profit", 0.0),
            developer_margin=rj.get("developer_margin", 0.0),
            roi=rj.get("roi", 0.0),
            roe=rj.get("roe", 0.0),
            irr=rj.get("irr", 0.0),
            npv=rj.get("npv", 0.0),
            equity_multiple=rj.get("equity_multiple", 0.0),
            payback_period_months=rj.get("payback_period_months", 0.0),
            break_even_price_per_sqm=rj.get("break_even_price_per_sqm", 0.0),
            break_even_sellable_sqm=rj.get("break_even_sellable_sqm", 0.0),
        )
        results.append(
            FinancialScenarioRunResult(
                label=run.label,
                assumptions_used=run.assumptions_json or {},
                returns=returns,
                cashflows=(run.results_json or {}).get("cashflows", []),
                effective_gdv=(run.results_json or {}).get("effective_gdv", 0.0),
                effective_total_cost=(run.results_json or {}).get("effective_total_cost", 0.0),
                effective_equity_invested=(run.results_json or {}).get(
                    "effective_equity_invested", 0.0
                ),
                effective_development_period_months=(run.results_json or {}).get(
                    "effective_development_period_months", 0
                ),
            )
        )
    return results


def _build_delta_responses(
    run_ids: List[str],
    deltas: List[Dict[str, float]],
    engine_results: List[FinancialScenarioRunResult],
) -> List[FinancialScenarioRunDelta]:
    return [
        FinancialScenarioRunDelta(
            run_id=rid,
            label=er.label,
            gross_profit_delta=delta.get("gross_profit", 0.0),
            developer_margin_delta=delta.get("developer_margin", 0.0),
            roi_delta=delta.get("roi", 0.0),
            roe_delta=delta.get("roe", 0.0),
            irr_delta=delta.get("irr", 0.0),
            npv_delta=delta.get("npv", 0.0),
            equity_multiple_delta=delta.get("equity_multiple", 0.0),
            payback_period_months_delta=delta.get("payback_period_months", 0.0),
        )
        for rid, delta, er in zip(run_ids, deltas, engine_results)
    ]
