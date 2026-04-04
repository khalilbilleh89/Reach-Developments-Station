"""
release_simulation.service

Release Strategy Simulation Engine — deterministic what-if simulation service.

Simulation logic
----------------
1. Load the latest calculated feasibility run for the project.
2. Adjust GDV by price_adjustment_pct.
3. Compute effective development period:
     base_period + phase_delay_months
     then apply release_strategy modifier (+10% / -10% / 0%).
4. Recalculate IRR using the existing IRR engine (reuse, no duplication).
5. Calculate NPV at the platform discount rate (10% p.a.).
6. Derive risk score from IRR delta vs baseline.

Architecture constraints
------------------------
- Deterministic and synchronous — no async workers.
- Read-only — no feasibility runs, phases, or pricing records are mutated.
- Reuses ``app.modules.feasibility.irr_engine.calculate_irr`` and
  ``app.modules.feasibility.irr_engine.build_development_cashflows``.
- No duplicate IRR / cashflow formulas.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.errors import ResourceNotFoundError
from app.modules.feasibility.irr_engine import (
    build_development_cashflows,
    calculate_irr,
)
from app.modules.release_simulation.schemas import (
    SimulateStrategiesRequest,
    SimulateStrategiesResponse,
    SimulateStrategyRequest,
    SimulateStrategyResponse,
    SimulationResult,
    SimulationScenarioInput,
)

# ---------------------------------------------------------------------------
# Platform constants
# ---------------------------------------------------------------------------

# Discount rate used for NPV calculations (10 % p.a.).
_NPV_DISCOUNT_RATE_ANNUAL = 0.10
_NPV_DISCOUNT_RATE_MONTHLY = (1.0 + _NPV_DISCOUNT_RATE_ANNUAL) ** (1.0 / 12.0) - 1.0

# Release strategy absorption modifiers applied to the development period.
_STRATEGY_MODIFIER: dict[str, float] = {
    "hold": 0.10,       # +10 % → slower absorption → longer period
    "accelerate": -0.10,  # −10 % → faster absorption → shorter period
    "maintain": 0.0,    # unchanged
}

# IRR delta thresholds for risk classification (matches PR spec).
_IRR_LOW_RISK_THRESHOLD = 0.02   # > +2 % delta → low risk
# 0 ≤ delta ≤ 2 % → medium risk
# delta < 0       → high risk

# Default fallback assumptions when no feasibility run exists.
_DEFAULT_TOTAL_COST = 1_000_000.0
_DEFAULT_GDV = 1_200_000.0
_DEFAULT_DEV_PERIOD_MONTHS = 24


def _calculate_npv(cashflows: list, monthly_rate: float) -> float:
    """Calculate NPV for a cashflow array at the given monthly discount rate."""
    return sum(cf / (1.0 + monthly_rate) ** t for t, cf in enumerate(cashflows))


def _compute_effective_period(
    base_period: int,
    phase_delay_months: int,
    release_strategy: str,
) -> int:
    """Compute the effective development period after delay and strategy modifier.

    Parameters
    ----------
    base_period:
        Baseline development period in months (from feasibility run).
    phase_delay_months:
        Additional months to add (may be negative for acceleration).
    release_strategy:
        'hold' | 'accelerate' | 'maintain'.

    Returns
    -------
    int
        Effective period, always >= 1.
    """
    modifier = _STRATEGY_MODIFIER.get(release_strategy, 0.0)
    delayed = base_period + phase_delay_months
    adjusted = delayed * (1.0 + modifier)
    return max(1, math.ceil(adjusted))


def _derive_risk_score(irr_delta: Optional[float]) -> str:
    """Return risk classification string based on IRR delta.

    Rules (per PR spec):
      irr_delta > +2%  → 'low'
      0 ≤ delta ≤ 2%  → 'medium'
      delta < 0        → 'high'
      unavailable      → 'medium' (conservative default)
    """
    if irr_delta is None:
        return "medium"
    if irr_delta > _IRR_LOW_RISK_THRESHOLD:
        return "low"
    if irr_delta >= 0.0:
        return "medium"
    return "high"


class ReleaseSimulationRepository:
    """Read-only data access for simulation inputs."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_project(self, project_id: str):
        """Return the Project record or None."""
        from app.modules.projects.models import Project
        return self.db.query(Project).filter(Project.id == project_id).first()

    def get_feasibility_baseline(
        self, project_id: str
    ) -> Tuple[bool, Optional[float], Optional[float], Optional[int], Optional[float], str]:
        """Return (has_run, gdv, total_cost, dev_period_months, irr, currency) from the latest calculated run.

        Fetches the latest calculated FeasibilityRun once, then loads result and
        assumptions by that specific run_id to guarantee all values originate from
        the same run.

        Returns (False, None, None, None, None, DEFAULT_CURRENCY) when no calculated run exists.
        """
        from app.core.constants.currency import DEFAULT_CURRENCY
        from app.modules.feasibility.models import (
            FeasibilityAssumptions,
            FeasibilityResult,
            FeasibilityRun,
        )
        latest_run = (
            self.db.query(FeasibilityRun)
            .filter(FeasibilityRun.project_id == project_id)
            .filter(FeasibilityRun.status == "calculated")
            .order_by(FeasibilityRun.created_at.desc())
            .first()
        )
        if latest_run is None:
            return False, None, None, None, None, DEFAULT_CURRENCY

        run_id = latest_run.id

        feas_result = (
            self.db.query(FeasibilityResult)
            .filter(FeasibilityResult.run_id == run_id)
            .first()
        )
        feas_assumptions = (
            self.db.query(FeasibilityAssumptions)
            .filter(FeasibilityAssumptions.run_id == run_id)
            .first()
        )

        gdv = float(feas_result.gdv) if feas_result is not None and feas_result.gdv is not None else None
        total_cost = float(feas_result.total_cost) if feas_result is not None and feas_result.total_cost is not None else None
        irr = float(feas_result.irr) if feas_result is not None and feas_result.irr is not None else None
        dev_period = (
            int(feas_assumptions.development_period_months)
            if feas_assumptions is not None and feas_assumptions.development_period_months is not None
            else None
        )
        # Currency: prefer result currency, fall back to assumptions, then platform default.
        currency = DEFAULT_CURRENCY
        if feas_result is not None and getattr(feas_result, "currency", None):
            currency = feas_result.currency
        elif feas_assumptions is not None and getattr(feas_assumptions, "currency", None):
            currency = feas_assumptions.currency

        return True, gdv, total_cost, dev_period, irr, currency


class ReleaseSimulationService:
    """Service that runs deterministic, read-only release strategy simulations."""

    def __init__(self, db: Session) -> None:
        self.repo = ReleaseSimulationRepository(db)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def simulate_strategy(
        self, project_id: str, request: SimulateStrategyRequest
    ) -> SimulateStrategyResponse:
        """Run a single release strategy simulation for a project.

        Raises ResourceNotFoundError if the project does not exist.
        All source records are read-only — nothing is mutated.
        """
        project = self.repo.get_project(project_id)
        if project is None:
            raise ResourceNotFoundError(f"Project '{project_id}' not found.")

        has_baseline, baseline_gdv, baseline_total_cost, baseline_dev_period, baseline_irr, currency = (
            self.repo.get_feasibility_baseline(project_id)
        )

        result = self._run_scenario(
            scenario=request.scenario,
            baseline_gdv=baseline_gdv,
            baseline_total_cost=baseline_total_cost,
            baseline_dev_period=baseline_dev_period,
            baseline_irr=baseline_irr,
            currency=currency,
        )

        return SimulateStrategyResponse(
            project_id=project.id,
            project_name=project.name,
            has_feasibility_baseline=has_baseline,
            currency=currency,
            result=result,
        )

    def simulate_strategies(
        self, project_id: str, request: SimulateStrategiesRequest
    ) -> SimulateStrategiesResponse:
        """Run multiple release strategy simulations and return results ranked by IRR.

        Raises ResourceNotFoundError if the project does not exist.
        All source records are read-only — nothing is mutated.
        """
        project = self.repo.get_project(project_id)
        if project is None:
            raise ResourceNotFoundError(f"Project '{project_id}' not found.")

        has_baseline, baseline_gdv, baseline_total_cost, baseline_dev_period, baseline_irr, currency = (
            self.repo.get_feasibility_baseline(project_id)
        )

        results: List[SimulationResult] = [
            self._run_scenario(
                scenario=scenario,
                baseline_gdv=baseline_gdv,
                baseline_total_cost=baseline_total_cost,
                baseline_dev_period=baseline_dev_period,
                baseline_irr=baseline_irr,
                currency=currency,
            )
            for scenario in request.scenarios
        ]

        # Rank by IRR descending (highest IRR = best outcome first).
        results.sort(key=lambda r: r.irr, reverse=True)

        best_label = results[0].label if results else None

        return SimulateStrategiesResponse(
            project_id=project.id,
            project_name=project.name,
            has_feasibility_baseline=has_baseline,
            currency=currency,
            results=results,
            best_scenario_label=best_label,
        )

    # ------------------------------------------------------------------
    # Core simulation logic
    # ------------------------------------------------------------------

    def _run_scenario(
        self,
        scenario: SimulationScenarioInput,
        baseline_gdv: Optional[float],
        baseline_total_cost: Optional[float],
        baseline_dev_period: Optional[int],
        baseline_irr: Optional[float],
        currency: str,
    ) -> SimulationResult:
        """Execute one simulation scenario and return the result.

        Falls back to default assumptions when no feasibility baseline exists.
        """
        # Resolve baseline values (fall back to defaults when missing).
        gdv = baseline_gdv if baseline_gdv is not None else _DEFAULT_GDV
        total_cost = baseline_total_cost if baseline_total_cost is not None else _DEFAULT_TOTAL_COST
        dev_period = baseline_dev_period if baseline_dev_period is not None else _DEFAULT_DEV_PERIOD_MONTHS

        # 1. Adjust GDV by price change.
        simulated_gdv = gdv * (1.0 + scenario.price_adjustment_pct / 100.0)

        # 2. Compute effective development period.
        simulated_dev_period = _compute_effective_period(
            base_period=dev_period,
            phase_delay_months=scenario.phase_delay_months,
            release_strategy=scenario.release_strategy,
        )

        # 3. Recalculate IRR using the existing IRR engine (no duplication).
        # Round once here so that irr_delta = irr − baseline_irr is exact per the contract.
        irr = round(
            calculate_irr(
                total_cost=total_cost,
                gdv=simulated_gdv,
                development_period_months=simulated_dev_period,
            ),
            6,
        )

        # 4. Calculate NPV using platform discount rate.
        cashflows = build_development_cashflows(
            total_cost=total_cost,
            gdv=simulated_gdv,
            development_period_months=simulated_dev_period,
        )
        simulated_npv = _calculate_npv(cashflows, _NPV_DISCOUNT_RATE_MONTHLY)

        # 5. Derive IRR delta and risk score (delta is computed from the same rounded irr).
        irr_delta: Optional[float] = None
        if baseline_irr is not None:
            irr_delta = round(irr - baseline_irr, 6)

        risk_score = _derive_risk_score(irr_delta)
        cashflow_delay = simulated_dev_period - dev_period

        return SimulationResult(
            label=scenario.label,
            price_adjustment_pct=scenario.price_adjustment_pct,
            phase_delay_months=scenario.phase_delay_months,
            release_strategy=scenario.release_strategy,
            simulated_gdv=round(simulated_gdv, 2),
            simulated_dev_period_months=simulated_dev_period,
            irr=irr,
            irr_delta=irr_delta,
            npv=round(simulated_npv, 2),
            cashflow_delay_months=cashflow_delay,
            risk_score=risk_score,
            currency=currency,
            baseline_gdv=round(baseline_gdv, 2) if baseline_gdv is not None else None,
            baseline_irr=baseline_irr,
            baseline_dev_period_months=baseline_dev_period,
            baseline_total_cost=round(baseline_total_cost, 2) if baseline_total_cost is not None else None,
        )
