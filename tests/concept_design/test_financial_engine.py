"""
Tests for the Concept Design Financial Engine.

Validates pure GDV estimation logic — no database or HTTP layer involved.

PR-CONCEPT-062
"""

import pytest

from app.modules.concept_design.financial_engine import (
    ConceptFinancialMetrics,
    estimate_concept_financials,
)


# ---------------------------------------------------------------------------
# GDV calculation — primary path (price_per_sqm)
# ---------------------------------------------------------------------------


def test_gdv_primary_path_area_based():
    result = estimate_concept_financials(
        sellable_area=7400.0,
        unit_count=92,
        price_per_sqm=2500.0,
    )
    assert result.estimated_gdv == pytest.approx(7400.0 * 2500.0)


def test_gdv_primary_path_revenue_per_sqm_is_price():
    """When computed via area, revenue_per_sqm == price_per_sqm."""
    result = estimate_concept_financials(
        sellable_area=5000.0,
        unit_count=50,
        price_per_sqm=3000.0,
    )
    assert result.estimated_revenue_per_sqm == pytest.approx(3000.0)


def test_gdv_primary_path_revenue_per_unit():
    result = estimate_concept_financials(
        sellable_area=5000.0,
        unit_count=50,
        price_per_sqm=3000.0,
    )
    # GDV = 15_000_000; revenue per unit = 15_000_000 / 50 = 300_000
    assert result.estimated_revenue_per_unit == pytest.approx(300_000.0)


# ---------------------------------------------------------------------------
# GDV calculation — fallback path (price_per_unit)
# ---------------------------------------------------------------------------


def test_gdv_fallback_unit_based():
    result = estimate_concept_financials(
        sellable_area=None,
        unit_count=88,
        price_per_unit=250_000.0,
    )
    assert result.estimated_gdv == pytest.approx(88 * 250_000.0)


def test_gdv_fallback_used_when_sellable_area_none():
    """If sellable_area is None, fall back to unit-based GDV."""
    result = estimate_concept_financials(
        sellable_area=None,
        unit_count=100,
        price_per_sqm=2000.0,
        price_per_unit=300_000.0,
    )
    # Primary path requires non-None sellable_area; falls back to unit path
    assert result.estimated_gdv == pytest.approx(100 * 300_000.0)


def test_gdv_fallback_unit_revenue_per_sqm_none_when_no_area():
    """revenue_per_sqm is None when sellable_area is absent."""
    result = estimate_concept_financials(
        sellable_area=None,
        unit_count=50,
        price_per_unit=200_000.0,
    )
    assert result.estimated_revenue_per_sqm is None
    assert result.estimated_revenue_per_unit == pytest.approx(200_000.0)


# ---------------------------------------------------------------------------
# Primary path preferred over fallback
# ---------------------------------------------------------------------------


def test_primary_path_preferred_when_both_prices_given():
    """When both prices are given and sellable_area is present, primary wins."""
    result = estimate_concept_financials(
        sellable_area=8000.0,
        unit_count=80,
        price_per_sqm=2500.0,
        price_per_unit=200_000.0,
    )
    # Primary: 8000 * 2500 = 20_000_000
    # Fallback: 80 * 200_000 = 16_000_000
    assert result.estimated_gdv == pytest.approx(20_000_000.0)


# ---------------------------------------------------------------------------
# Null / zero handling
# ---------------------------------------------------------------------------


def test_no_pricing_returns_all_none():
    result = estimate_concept_financials(
        sellable_area=7400.0,
        unit_count=92,
    )
    assert result.estimated_gdv is None
    assert result.estimated_revenue_per_sqm is None
    assert result.estimated_revenue_per_unit is None


def test_zero_unit_count_fallback_returns_none():
    """When unit_count is 0, unit-based fallback is not applicable."""
    result = estimate_concept_financials(
        sellable_area=None,
        unit_count=0,
        price_per_unit=300_000.0,
    )
    assert result.estimated_gdv is None


def test_zero_price_per_sqm_treated_as_no_pricing():
    """price_per_sqm <= 0 should not be used for GDV estimation."""
    result = estimate_concept_financials(
        sellable_area=5000.0,
        unit_count=50,
        price_per_sqm=0.0,
    )
    assert result.estimated_gdv is None


def test_zero_price_per_unit_treated_as_no_pricing():
    result = estimate_concept_financials(
        sellable_area=None,
        unit_count=50,
        price_per_unit=0.0,
    )
    assert result.estimated_gdv is None


def test_zero_sellable_area_falls_back_to_unit_path():
    """sellable_area == 0 should not be used; fall back to unit path."""
    result = estimate_concept_financials(
        sellable_area=0.0,
        unit_count=50,
        price_per_sqm=2000.0,
        price_per_unit=300_000.0,
    )
    # Primary skipped (area == 0), fallback used
    assert result.estimated_gdv == pytest.approx(50 * 300_000.0)


# ---------------------------------------------------------------------------
# Revenue metrics with None GDV
# ---------------------------------------------------------------------------


def test_revenue_per_sqm_is_none_when_gdv_is_none():
    result = estimate_concept_financials(
        sellable_area=5000.0,
        unit_count=50,
    )
    assert result.estimated_revenue_per_sqm is None


def test_revenue_per_unit_is_none_when_gdv_is_none():
    result = estimate_concept_financials(
        sellable_area=5000.0,
        unit_count=50,
    )
    assert result.estimated_revenue_per_unit is None


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------


def test_returns_concept_financial_metrics_dataclass():
    result = estimate_concept_financials(
        sellable_area=5000.0,
        unit_count=50,
        price_per_sqm=3000.0,
    )
    assert isinstance(result, ConceptFinancialMetrics)


# ---------------------------------------------------------------------------
# Non-finite input handling — PR-CONCEPT-062A
# ---------------------------------------------------------------------------


def test_inf_price_per_sqm_treated_as_absent():
    """inf price_per_sqm must not produce inf GDV."""
    result = estimate_concept_financials(
        sellable_area=5000.0,
        unit_count=50,
        price_per_sqm=float("inf"),
    )
    assert result.estimated_gdv is None


def test_nan_price_per_sqm_treated_as_absent():
    """nan price_per_sqm must not produce nan GDV."""
    result = estimate_concept_financials(
        sellable_area=5000.0,
        unit_count=50,
        price_per_sqm=float("nan"),
    )
    assert result.estimated_gdv is None


def test_inf_price_per_unit_treated_as_absent():
    """inf price_per_unit must not produce inf GDV."""
    result = estimate_concept_financials(
        sellable_area=None,
        unit_count=50,
        price_per_unit=float("inf"),
    )
    assert result.estimated_gdv is None


def test_nan_price_per_unit_treated_as_absent():
    """nan price_per_unit must not produce nan GDV."""
    result = estimate_concept_financials(
        sellable_area=None,
        unit_count=50,
        price_per_unit=float("nan"),
    )
    assert result.estimated_gdv is None


def test_non_finite_input_falls_back_to_other_price():
    """If price_per_sqm is inf but price_per_unit is valid, use fallback path."""
    result = estimate_concept_financials(
        sellable_area=5000.0,
        unit_count=50,
        price_per_sqm=float("inf"),
        price_per_unit=300_000.0,
    )
    # Primary path rejected (inf); fallback to unit-based
    assert result.estimated_gdv == pytest.approx(50 * 300_000.0)


# ---------------------------------------------------------------------------
# Comparison engine integration — GDV fields passed through
# ---------------------------------------------------------------------------


def test_comparison_engine_propagates_gdv_fields():
    """Confirm financial fields flow from engine input to comparison row."""
    from app.modules.concept_design.comparison_engine import (
        ConceptOptionComparisonInput,
        compute_concept_comparison,
    )

    opts = [
        ConceptOptionComparisonInput(
            concept_option_id="opt-A",
            name="Option A",
            status="draft",
            unit_count=92,
            sellable_area=7400.0,
            efficiency_ratio=0.75,
            average_unit_area=80.0,
            building_count=2,
            floor_count=10,
            estimated_gdv=18_200_000.0,
            estimated_revenue_per_sqm=2459.46,
            estimated_revenue_per_unit=197_826.09,
        ),
        ConceptOptionComparisonInput(
            concept_option_id="opt-B",
            name="Option B",
            status="draft",
            unit_count=88,
            sellable_area=7200.0,
            efficiency_ratio=0.72,
            average_unit_area=81.8,
            building_count=2,
            floor_count=10,
            estimated_gdv=19_500_000.0,
            estimated_revenue_per_sqm=2708.33,
            estimated_revenue_per_unit=221_590.91,
        ),
    ]

    result = compute_concept_comparison(opts, comparison_basis="project")

    assert result.best_gdv_option_id == "opt-B"

    rows = {r.concept_option_id: r for r in result.rows}
    assert rows["opt-B"].is_best_gdv is True
    assert rows["opt-A"].is_best_gdv is False
    assert rows["opt-B"].gdv_delta_vs_best == pytest.approx(0.0)
    assert rows["opt-A"].gdv_delta_vs_best == pytest.approx(18_200_000.0 - 19_500_000.0)


def test_comparison_engine_no_gdv_when_all_none():
    """best_gdv_option_id is None when no options have GDV data."""
    from app.modules.concept_design.comparison_engine import (
        ConceptOptionComparisonInput,
        compute_concept_comparison,
    )

    opts = [
        ConceptOptionComparisonInput(
            concept_option_id="opt-1",
            name="Option 1",
            status="draft",
            unit_count=100,
            sellable_area=9000.0,
            efficiency_ratio=0.75,
            average_unit_area=90.0,
            building_count=None,
            floor_count=None,
        ),
    ]

    result = compute_concept_comparison(opts, comparison_basis="scenario")
    assert result.best_gdv_option_id is None
    assert result.rows[0].is_best_gdv is False
    assert result.rows[0].gdv_delta_vs_best is None
