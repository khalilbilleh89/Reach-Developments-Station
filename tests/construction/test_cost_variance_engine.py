"""
Tests for the Contractor Cost Variance Analytics Engine.

PR-CONSTR-047 — Contractor Cost Variance Analytics Engine

Validates:
- zero variance case (actual == planned)
- positive variance (cost overrun)
- negative variance (under budget)
- large cost overrun (single package)
- mixed contractor packages (some overrun, some under, some uncosted)
- empty input
- no assessed packages (all missing cost fields)
- single assessed package
- cost_overrun_rate calculation
- average_cost_variance_pct calculation
- max_cost_overrun_pct calculation
- total_cost_variance calculation
- packages with zero planned_cost excluded from percentage calculations
- integration with contractor scorecard engine
"""

from decimal import Decimal

import pytest

from app.modules.construction.cost_variance_engine import (
    ContractorCostVarianceResult,
    PackageCostInput,
    compute_cost_variance,
)


# ---------------------------------------------------------------------------
# Helper factory
# ---------------------------------------------------------------------------


def _pkg(
    pid: str = "P1",
    planned: str | None = None,
    actual: str | None = None,
) -> PackageCostInput:
    return PackageCostInput(
        package_id=pid,
        planned_cost=Decimal(planned) if planned is not None else None,
        actual_cost=Decimal(actual) if actual is not None else None,
    )


# ---------------------------------------------------------------------------
# Empty / no-data cases
# ---------------------------------------------------------------------------


def test_empty_input_returns_zero_result() -> None:
    result = compute_cost_variance([])
    assert result.assessed_packages == 0
    assert result.total_planned_cost == Decimal("0.00")
    assert result.total_actual_cost == Decimal("0.00")
    assert result.total_cost_variance == Decimal("0.00")
    assert result.average_cost_variance_pct is None
    assert result.max_cost_overrun_pct is None
    assert result.cost_overrun_rate is None


def test_no_assessed_packages_all_missing_cost_fields() -> None:
    """Packages without both cost fields do not contribute."""
    pkgs = [
        _pkg("P1"),  # no cost fields
        _pkg("P2", planned="10000"),  # only planned
        _pkg("P3", actual="12000"),  # only actual
    ]
    result = compute_cost_variance(pkgs)
    assert result.assessed_packages == 0
    assert result.cost_overrun_rate is None
    assert result.average_cost_variance_pct is None


# ---------------------------------------------------------------------------
# Zero variance (actual == planned)
# ---------------------------------------------------------------------------


def test_zero_variance_case() -> None:
    """When actual == planned, cost_variance == 0 and no overrun."""
    pkgs = [
        _pkg("P1", planned="50000", actual="50000"),
        _pkg("P2", planned="30000", actual="30000"),
    ]
    result = compute_cost_variance(pkgs)
    assert result.assessed_packages == 2
    assert result.total_planned_cost == Decimal("80000")
    assert result.total_actual_cost == Decimal("80000")
    assert result.total_cost_variance == Decimal("0")
    assert result.average_cost_variance_pct == 0.0
    assert result.max_cost_overrun_pct is None
    assert result.cost_overrun_rate == 0.0


# ---------------------------------------------------------------------------
# Positive variance (cost overrun)
# ---------------------------------------------------------------------------


def test_single_package_overrun() -> None:
    """Single package with actual > planned."""
    pkgs = [_pkg("P1", planned="100000", actual="118000")]
    result = compute_cost_variance(pkgs)
    assert result.assessed_packages == 1
    assert result.total_cost_variance == Decimal("18000")
    # (118000 - 100000) / 100000 * 100 = 18.0
    assert result.average_cost_variance_pct == 18.0
    assert result.max_cost_overrun_pct == 18.0
    assert result.cost_overrun_rate == 1.0


def test_positive_variance_multiple_packages() -> None:
    """Multiple packages all over budget."""
    pkgs = [
        _pkg("P1", planned="100000", actual="125000"),  # +25%
        _pkg("P2", planned="200000", actual="210000"),  # +5%
    ]
    result = compute_cost_variance(pkgs)
    assert result.assessed_packages == 2
    assert result.total_planned_cost == Decimal("300000")
    assert result.total_actual_cost == Decimal("335000")
    assert result.total_cost_variance == Decimal("35000")
    # avg = (25 + 5) / 2 = 15.0
    assert result.average_cost_variance_pct == 15.0
    assert result.max_cost_overrun_pct == 25.0
    assert result.cost_overrun_rate == 1.0


# ---------------------------------------------------------------------------
# Negative variance (under budget)
# ---------------------------------------------------------------------------


def test_negative_variance_under_budget() -> None:
    """Actual < planned means the contractor came in under budget."""
    pkgs = [_pkg("P1", planned="100000", actual="95000")]
    result = compute_cost_variance(pkgs)
    assert result.assessed_packages == 1
    assert result.total_cost_variance == Decimal("-5000")
    # (-5000 / 100000) * 100 = -5.0
    assert result.average_cost_variance_pct == -5.0
    assert result.max_cost_overrun_pct is None  # no overrun packages
    assert result.cost_overrun_rate == 0.0


# ---------------------------------------------------------------------------
# Large cost overrun
# ---------------------------------------------------------------------------


def test_large_cost_overrun() -> None:
    """Single package with a very large overrun."""
    pkgs = [_pkg("P1", planned="50000", actual="90000")]
    result = compute_cost_variance(pkgs)
    assert result.assessed_packages == 1
    assert result.total_cost_variance == Decimal("40000")
    # (40000 / 50000) * 100 = 80.0
    assert result.average_cost_variance_pct == 80.0
    assert result.max_cost_overrun_pct == 80.0
    assert result.cost_overrun_rate == 1.0


# ---------------------------------------------------------------------------
# Mixed packages
# ---------------------------------------------------------------------------


def test_mixed_packages_some_overrun_some_under_some_uncosted() -> None:
    """Mix of over-budget, under-budget, and uncosted packages."""
    pkgs = [
        _pkg("P1", planned="100000", actual="120000"),  # +20%
        _pkg("P2", planned="100000", actual="90000"),   # -10%
        _pkg("P3"),  # no costs — excluded
        _pkg("P4", planned="100000", actual="100000"),  # 0%
        _pkg("P5", planned="200000", actual="250000"),  # +25%
    ]
    result = compute_cost_variance(pkgs)
    assert result.assessed_packages == 4  # P3 excluded
    assert result.total_planned_cost == Decimal("500000")
    assert result.total_actual_cost == Decimal("560000")
    assert result.total_cost_variance == Decimal("60000")
    # variances: +20, -10, 0, +25 → avg = 35/4 = 8.75
    assert result.average_cost_variance_pct == 8.75
    # max overrun from over-budget packages: P1=20%, P5=25%
    assert result.max_cost_overrun_pct == 25.0
    # 2 over budget out of 4 assessed
    assert result.cost_overrun_rate == 0.5


def test_cost_overrun_rate_partial() -> None:
    """cost_overrun_rate: 1 of 3 packages over budget."""
    pkgs = [
        _pkg("P1", planned="100000", actual="105000"),  # overrun
        _pkg("P2", planned="100000", actual="100000"),  # on-budget
        _pkg("P3", planned="100000", actual="95000"),   # under
    ]
    result = compute_cost_variance(pkgs)
    assert result.assessed_packages == 3
    assert result.cost_overrun_rate == pytest.approx(1 / 3)


def test_average_cost_variance_pct_rounded_to_two_decimal_places() -> None:
    """average_cost_variance_pct is rounded to 2 decimal places."""
    # 10/3 % = 3.333... → rounds to 3.33
    pkgs = [
        _pkg("P1", planned="300000", actual="310000"),  # +3.333...%
        _pkg("P2", planned="300000", actual="310000"),  # +3.333...%
        _pkg("P3", planned="300000", actual="310000"),  # +3.333...%
    ]
    result = compute_cost_variance(pkgs)
    assert result.average_cost_variance_pct == pytest.approx(3.33, abs=0.005)
    # Explicitly check it is rounded to at most 2 decimal places
    assert result.average_cost_variance_pct is not None
    assert round(result.average_cost_variance_pct, 2) == result.average_cost_variance_pct


# ---------------------------------------------------------------------------
# Zero planned_cost edge case
# ---------------------------------------------------------------------------


def test_zero_planned_cost_excluded_from_pct() -> None:
    """Packages with planned_cost == 0 are excluded from % calculations."""
    pkgs = [
        _pkg("P1", planned="0", actual="10000"),   # excluded from % (zero planned)
        _pkg("P2", planned="100000", actual="110000"),  # +10%
    ]
    result = compute_cost_variance(pkgs)
    assert result.assessed_packages == 2
    # total variance includes both: 10000 + 10000 = 20000
    assert result.total_cost_variance == Decimal("20000")
    # only P2 contributes to %
    assert result.average_cost_variance_pct == 10.0
    assert result.max_cost_overrun_pct == 10.0


# ---------------------------------------------------------------------------
# Single package
# ---------------------------------------------------------------------------


def test_single_assessed_package_on_budget() -> None:
    pkgs = [_pkg("P1", planned="75000", actual="75000")]
    result = compute_cost_variance(pkgs)
    assert result.assessed_packages == 1
    assert result.cost_overrun_rate == 0.0
    assert result.average_cost_variance_pct == 0.0
    assert result.max_cost_overrun_pct is None


# ---------------------------------------------------------------------------
# Integration: compute_cost_variance feeds ContractorScorecard
# ---------------------------------------------------------------------------


def test_cost_variance_integrates_with_scorecard() -> None:
    """Verify cost variance fields are propagated to ContractorScorecard."""
    from app.modules.construction.contractor_scorecard_engine import (
        ContractorScorecardInput,
        PackageScorecardData,
        compute_contractor_scorecard,
    )

    packages = [
        PackageScorecardData(
            package_id="P1",
            status="completed",
            planned_value=Decimal("100000"),
            awarded_value=Decimal("118000"),
        ),
        PackageScorecardData(
            package_id="P2",
            status="completed",
            planned_value=Decimal("200000"),
            awarded_value=Decimal("200000"),
        ),
    ]
    inp = ContractorScorecardInput(
        contractor_id="CTR-1",
        contractor_name="Test Contractor",
        milestones=[],
        packages=packages,
        risk_signal_count=0,
    )
    sc = compute_contractor_scorecard(inp)

    assert sc.total_cost_variance == Decimal("18000")
    # avg: (18% + 0%) / 2 = 9.0
    assert sc.average_cost_variance_pct == 9.0
    # only P1 is over budget: 18%
    assert sc.max_cost_overrun_pct == 18.0
    # 1 of 2 packages over budget
    assert sc.cost_overrun_rate == 0.5


def test_scorecard_no_packages_has_none_cost_variance() -> None:
    """Scorecard with no packages produces None cost variance fields."""
    from app.modules.construction.contractor_scorecard_engine import (
        ContractorScorecardInput,
        compute_contractor_scorecard,
    )

    inp = ContractorScorecardInput(
        contractor_id="CTR-2",
        contractor_name="No Package Corp",
        milestones=[],
        packages=[],
        risk_signal_count=0,
    )
    sc = compute_contractor_scorecard(inp)

    assert sc.total_cost_variance is None
    assert sc.average_cost_variance_pct is None
    assert sc.max_cost_overrun_pct is None
    assert sc.cost_overrun_rate is None
