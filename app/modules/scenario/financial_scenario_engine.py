"""
scenario.financial_scenario_engine

Pure financial scenario execution engine for the Scenario Engine layer.

Rules enforced here:
  - No DB access, no HTTP concerns, no side effects.
  - All financial calculations are delegated to the Calculation Engine.
  - No IRR / NPV / cashflow formulas are duplicated here.
  - Scenario override values are merged on top of baseline assumptions before
    delegating to the Calculation Engine.

Architecture notes
------------------
This engine sits in the Scenario Engine layer.  It accepts baseline financial
assumptions and a dict of override values, builds the merged input payload,
delegates to the existing Calculation Engine adapters, and returns a
structured result set suitable for persistence and comparison.

Supported overrides (keys in FinancialScenarioAssumptions)
-----------------------------------------------------------
gdv, total_cost, equity_invested, sellable_area_sqm,
avg_sale_price_per_sqm, development_period_months,
annual_discount_rate, sales_pace_months_override,
pricing_uplift_pct, cost_inflation_pct, debt_ratio
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from app.core.calculation_engine.returns import (
    run_return_calculations,
    build_development_cashflows,
)
from app.core.calculation_engine.types import ReturnInputs, ReturnOutputs
from app.core.constants.currency import DEFAULT_CURRENCY


# ---------------------------------------------------------------------------
# Input structures
# ---------------------------------------------------------------------------


@dataclass
class FinancialScenarioAssumptions:
    """Complete set of baseline financial assumptions for a scenario run.

    All monetary values are in the project currency.

    Attributes
    ----------
    gdv:
        Gross Development Value (total expected sales revenue).
    total_cost:
        Total development cost (construction + soft costs + finance + sales).
    equity_invested:
        Equity portion of project funding.
    sellable_area_sqm:
        Total sellable floor area in square metres.
    avg_sale_price_per_sqm:
        Average achieved sale price per square metre.
    development_period_months:
        Duration of the development period (used for IRR cashflow model).
    annual_discount_rate:
        Annual discount rate for NPV calculation (decimal, e.g. 0.10 = 10%).
    sales_pace_months_override:
        Optional override for the assumed sales period in months (used for
        slower/faster sales sensitivity).  When None, development_period_months
        is used for the sales pace model.
    pricing_uplift_pct:
        Optional percentage uplift applied to GDV (e.g. 0.05 = +5% price
        increase scenario).  Applied before calculation.
    cost_inflation_pct:
        Optional percentage increase applied to total_cost (e.g. 0.10 = +10%
        cost inflation scenario).  Applied before calculation.
    debt_ratio:
        Debt portion of funding as a decimal fraction (e.g. 0.65 = 65% debt).
        When this override is provided, it takes precedence and
        equity_invested is recalculated as total_cost * (1 - debt_ratio),
        even if equity_invested was explicitly set.
    label:
        Human-readable label for this scenario run (e.g. "Base Case",
        "Slower Sales", "Price Uplift").
    notes:
        Optional free-text notes captured with the run.
    """

    gdv: float
    total_cost: float
    equity_invested: float
    sellable_area_sqm: float
    avg_sale_price_per_sqm: float
    development_period_months: int
    annual_discount_rate: float = 0.10
    sales_pace_months_override: Optional[int] = None
    pricing_uplift_pct: Optional[float] = None
    cost_inflation_pct: Optional[float] = None
    debt_ratio: Optional[float] = None
    label: str = "Base Case"
    notes: Optional[str] = None
    currency: str = DEFAULT_CURRENCY  # denomination of all monetary inputs/outputs


@dataclass(frozen=True)
class ScenarioOverrides:
    """Key-value overrides applied on top of baseline assumptions.

    Only fields present in FinancialScenarioAssumptions are valid.
    Unknown keys are ignored to maintain forward compatibility.
    """

    values: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Output structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FinancialScenarioRunResult:
    """Results produced by a single financial scenario run.

    Attributes
    ----------
    label:
        Human-readable scenario label.
    assumptions_used:
        The merged (baseline + overrides) assumptions actually used.
    returns:
        Return and profitability metrics from the Calculation Engine.
    cashflows:
        Monthly cashflow array (equal outflows, lump-sum GDV at end).
    effective_gdv:
        GDV after pricing uplift, if any.
    effective_total_cost:
        Total cost after cost inflation, if any.
    effective_equity_invested:
        Equity invested used for ROE calculation.
    effective_development_period_months:
        Development period after sales pace override, if any.
    """

    label: str
    assumptions_used: Dict[str, Any]
    returns: ReturnOutputs
    cashflows: List[float]
    effective_gdv: float
    effective_total_cost: float
    effective_equity_invested: float
    effective_development_period_months: int
    currency: str = DEFAULT_CURRENCY  # denomination of all monetary outputs


@dataclass(frozen=True)
class FinancialScenarioComparison:
    """Side-by-side comparison of multiple financial scenario runs.

    Attributes
    ----------
    runs:
        All individual run results in the order they were provided.
    baseline_label:
        Label of the baseline (first) run used as the comparison reference.
    deltas:
        List of delta metrics relative to the baseline run (first entry
        has all-zero deltas; subsequent entries show the difference).
    """

    runs: List[FinancialScenarioRunResult]
    baseline_label: str
    deltas: List[Dict[str, float]]


# ---------------------------------------------------------------------------
# Core engine functions
# ---------------------------------------------------------------------------


def _apply_overrides(
    base: FinancialScenarioAssumptions,
    overrides: ScenarioOverrides,
) -> FinancialScenarioAssumptions:
    """Return a new assumptions object with override values merged in.

    Unknown override keys are silently ignored (forward-compatibility).
    """
    valid_fields = {f.name for f in base.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    merged = asdict(base)
    for key, value in overrides.values.items():
        if key in valid_fields:
            merged[key] = value
    return FinancialScenarioAssumptions(**merged)


def _resolve_effective_values(
    assumptions: FinancialScenarioAssumptions,
) -> tuple[float, float, float, int]:
    """Compute effective GDV, cost, equity, and period after scenario modifiers.

    Applies pricing_uplift_pct, cost_inflation_pct, debt_ratio, and
    sales_pace_months_override in a deterministic order.

    Returns
    -------
    (effective_gdv, effective_total_cost, effective_equity, effective_period)
    """
    effective_gdv = assumptions.gdv
    if assumptions.pricing_uplift_pct is not None:
        effective_gdv = assumptions.gdv * (1.0 + assumptions.pricing_uplift_pct)

    effective_cost = assumptions.total_cost
    if assumptions.cost_inflation_pct is not None:
        effective_cost = assumptions.total_cost * (1.0 + assumptions.cost_inflation_pct)

    # Equity: use explicit value unless debt_ratio implies a different split.
    effective_equity = assumptions.equity_invested
    if assumptions.debt_ratio is not None:
        effective_equity = effective_cost * max(0.0, 1.0 - assumptions.debt_ratio)

    effective_period = assumptions.development_period_months
    if assumptions.sales_pace_months_override is not None:
        effective_period = assumptions.sales_pace_months_override

    return effective_gdv, effective_cost, effective_equity, effective_period


def run_financial_scenario(
    baseline: FinancialScenarioAssumptions,
    overrides: Optional[ScenarioOverrides] = None,
) -> FinancialScenarioRunResult:
    """Execute a single financial scenario run.

    Merges overrides onto the baseline assumptions, resolves effective values
    after scenario modifiers (pricing uplift, cost inflation, etc.), then
    delegates all financial calculations to the Calculation Engine.

    Parameters
    ----------
    baseline:
        Baseline financial assumptions for this run.
    overrides:
        Optional overrides applied on top of the baseline.  Fields that exist
        in FinancialScenarioAssumptions are merged; unknown keys are ignored.

    Returns
    -------
    FinancialScenarioRunResult
        Structured result containing return metrics, cashflows, and the
        merged assumptions actually used.
    """
    merged = _apply_overrides(baseline, overrides) if overrides else baseline

    effective_gdv, effective_cost, effective_equity, effective_period = (
        _resolve_effective_values(merged)
    )

    return_inputs = ReturnInputs(
        gdv=effective_gdv,
        total_cost=effective_cost,
        equity_invested=effective_equity,
        sellable_area_sqm=merged.sellable_area_sqm,
        avg_sale_price_per_sqm=merged.avg_sale_price_per_sqm,
        development_period_months=effective_period,
        currency=merged.currency,
    )
    return_outputs = run_return_calculations(
        return_inputs,
        annual_discount_rate=merged.annual_discount_rate,
    )

    cashflows = build_development_cashflows(
        effective_cost,
        effective_gdv,
        effective_period,
    )

    return FinancialScenarioRunResult(
        label=merged.label,
        assumptions_used=asdict(merged),
        returns=return_outputs,
        cashflows=cashflows,
        effective_gdv=effective_gdv,
        effective_total_cost=effective_cost,
        effective_equity_invested=effective_equity,
        effective_development_period_months=effective_period,
        currency=merged.currency,
    )


def _returns_to_dict(r: ReturnOutputs) -> Dict[str, float]:
    """Convert ReturnOutputs to a plain float dict for delta calculation."""
    return {
        "gross_profit": r.gross_profit,
        "developer_margin": r.developer_margin,
        "roi": r.roi,
        "roe": r.roe,
        "irr": r.irr,
        "npv": r.npv,
        "equity_multiple": r.equity_multiple,
        "payback_period_months": r.payback_period_months,
        "break_even_price_per_sqm": r.break_even_price_per_sqm,
        "break_even_sellable_sqm": r.break_even_sellable_sqm,
    }


def compare_financial_scenarios(
    runs: List[FinancialScenarioRunResult],
) -> FinancialScenarioComparison:
    """Build a side-by-side comparison of multiple financial scenario runs.

    The first run is treated as the baseline.  Deltas for each subsequent run
    are expressed as ``alternative − baseline`` for every return metric.

    Parameters
    ----------
    runs:
        Two or more scenario run results.  Must have at least two elements.

    Returns
    -------
    FinancialScenarioComparison
        Runs with deltas relative to the baseline (first run).

    Raises
    ------
    ValueError
        When fewer than two runs are provided.
    """
    if len(runs) < 2:
        raise ValueError("At least two scenario runs are required for comparison.")

    baseline_metrics = _returns_to_dict(runs[0].returns)
    deltas: List[Dict[str, float]] = []

    for run in runs:
        run_metrics = _returns_to_dict(run.returns)
        delta = {k: round(run_metrics[k] - baseline_metrics[k], 8) for k in baseline_metrics}
        deltas.append(delta)

    return FinancialScenarioComparison(
        runs=runs,
        baseline_label=runs[0].label,
        deltas=deltas,
    )
