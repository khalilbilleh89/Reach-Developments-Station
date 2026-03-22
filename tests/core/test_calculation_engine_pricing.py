"""
Tests for the centralized pricing formula engine.

Validates base price, attached-area pricing, feature premiums, escalation,
discount effects, and sales exception impacts against configurable pricing rules.
"""

import pytest

from app.core.calculation_engine.pricing import (
    apply_discount,
    apply_escalation,
    calculate_attached_area_price,
    calculate_base_unit_price,
    calculate_premium_total,
    run_unit_pricing,
)
from app.core.calculation_engine.types import PricingInputs


# ---------------------------------------------------------------------------
# calculate_base_unit_price
# ---------------------------------------------------------------------------


def test_base_unit_price_standard():
    """Base unit price = internal area × price per sqm."""
    assert calculate_base_unit_price(100.0, 15_000.0) == pytest.approx(1_500_000.0)


def test_base_unit_price_zero_area_returns_zero():
    assert calculate_base_unit_price(0.0, 15_000.0) == 0.0


def test_base_unit_price_negative_area_returns_zero():
    assert calculate_base_unit_price(-50.0, 15_000.0) == 0.0


def test_base_unit_price_zero_rate_returns_zero():
    assert calculate_base_unit_price(100.0, 0.0) == 0.0


def test_base_unit_price_negative_rate_returns_zero():
    assert calculate_base_unit_price(100.0, -1_000.0) == 0.0


def test_base_unit_price_returns_float():
    result = calculate_base_unit_price(100.0, 15_000.0)
    assert isinstance(result, float)


# ---------------------------------------------------------------------------
# calculate_attached_area_price
# ---------------------------------------------------------------------------


def test_attached_area_price_standard():
    """Attached-area price = balcony sqm × discounted rate."""
    assert calculate_attached_area_price(20.0, 5_000.0) == pytest.approx(100_000.0)


def test_attached_area_price_zero_area_returns_zero():
    assert calculate_attached_area_price(0.0, 5_000.0) == 0.0


def test_attached_area_price_negative_area_returns_zero():
    assert calculate_attached_area_price(-5.0, 5_000.0) == 0.0


def test_attached_area_price_zero_rate_returns_zero():
    assert calculate_attached_area_price(20.0, 0.0) == 0.0


# ---------------------------------------------------------------------------
# calculate_premium_total
# ---------------------------------------------------------------------------


def test_premium_total_all_premiums():
    total = calculate_premium_total(
        floor_premium=10_000.0,
        view_premium=20_000.0,
        corner_premium=5_000.0,
        size_adjustment=-3_000.0,
        custom_adjustment=2_000.0,
    )
    assert total == pytest.approx(34_000.0)


def test_premium_total_no_premiums():
    assert calculate_premium_total() == pytest.approx(0.0)


def test_premium_total_negative_adjustment():
    """Negative adjustments reduce the total."""
    total = calculate_premium_total(floor_premium=10_000.0, size_adjustment=-10_000.0)
    assert total == pytest.approx(0.0)


def test_premium_total_only_custom():
    total = calculate_premium_total(custom_adjustment=7_500.0)
    assert total == pytest.approx(7_500.0)


# ---------------------------------------------------------------------------
# apply_escalation
# ---------------------------------------------------------------------------


def test_apply_escalation_five_percent():
    assert apply_escalation(1_000_000.0, 0.05) == pytest.approx(1_050_000.0)


def test_apply_escalation_zero_rate():
    assert apply_escalation(1_000_000.0, 0.0) == pytest.approx(1_000_000.0)


def test_apply_escalation_negative_rate():
    """Negative escalation rate reduces the price."""
    assert apply_escalation(1_000_000.0, -0.10) == pytest.approx(900_000.0)


def test_apply_escalation_large_rate():
    assert apply_escalation(500_000.0, 1.0) == pytest.approx(1_000_000.0)


# ---------------------------------------------------------------------------
# apply_discount
# ---------------------------------------------------------------------------


def test_apply_discount_standard():
    assert apply_discount(1_000_000.0, 50_000.0) == pytest.approx(950_000.0)


def test_apply_discount_zero_discount():
    assert apply_discount(1_000_000.0, 0.0) == pytest.approx(1_000_000.0)


def test_apply_discount_negative_discount_ignored():
    """Negative discount amounts are treated as zero (no effect)."""
    assert apply_discount(1_000_000.0, -50_000.0) == pytest.approx(1_000_000.0)


def test_apply_discount_exceeds_price_clamped_to_zero():
    """Discount larger than price clamps to 0.0."""
    assert apply_discount(100_000.0, 200_000.0) == 0.0


# ---------------------------------------------------------------------------
# run_unit_pricing — composite runner
# ---------------------------------------------------------------------------


def test_run_unit_pricing_base_only():
    inputs = PricingInputs(internal_area_sqm=100.0, base_price_per_sqm=15_000.0)
    outputs = run_unit_pricing(inputs)
    assert outputs.base_unit_price == pytest.approx(1_500_000.0)
    assert outputs.premium_total == pytest.approx(0.0)
    assert outputs.escalated_price == pytest.approx(1_500_000.0)
    assert outputs.final_unit_price == pytest.approx(1_500_000.0)


def test_run_unit_pricing_with_all_premiums():
    inputs = PricingInputs(
        internal_area_sqm=100.0,
        base_price_per_sqm=15_000.0,
        floor_premium=10_000.0,
        view_premium=20_000.0,
        corner_premium=5_000.0,
    )
    outputs = run_unit_pricing(inputs)
    assert outputs.premium_total == pytest.approx(35_000.0)
    assert outputs.pre_escalation_price == pytest.approx(1_535_000.0)


def test_run_unit_pricing_with_attached_area():
    inputs = PricingInputs(
        internal_area_sqm=100.0,
        base_price_per_sqm=15_000.0,
        attached_area_sqm=20.0,
        attached_area_rate_per_sqm=5_000.0,
    )
    outputs = run_unit_pricing(inputs)
    assert outputs.attached_area_price == pytest.approx(100_000.0)
    assert outputs.pre_escalation_price == pytest.approx(1_600_000.0)


def test_run_unit_pricing_escalation_applied():
    inputs = PricingInputs(
        internal_area_sqm=100.0,
        base_price_per_sqm=10_000.0,
        escalation_rate=0.10,
    )
    outputs = run_unit_pricing(inputs)
    assert outputs.escalated_price == pytest.approx(1_100_000.0)
    assert outputs.final_unit_price == pytest.approx(1_100_000.0)


def test_run_unit_pricing_discount_applied():
    inputs = PricingInputs(
        internal_area_sqm=100.0,
        base_price_per_sqm=10_000.0,
        discount_amount=50_000.0,
    )
    outputs = run_unit_pricing(inputs)
    assert outputs.final_unit_price == pytest.approx(950_000.0)


def test_run_unit_pricing_negative_adjustment_reduces_price():
    """A negative size_adjustment reduces the pre-escalation price."""
    inputs = PricingInputs(
        internal_area_sqm=100.0,
        base_price_per_sqm=10_000.0,
        size_adjustment=-50_000.0,
    )
    outputs = run_unit_pricing(inputs)
    assert outputs.pre_escalation_price == pytest.approx(950_000.0)


def test_run_unit_pricing_full_pipeline():
    """Validate the complete pricing pipeline end-to-end."""
    inputs = PricingInputs(
        internal_area_sqm=120.0,
        base_price_per_sqm=12_000.0,
        attached_area_sqm=15.0,
        attached_area_rate_per_sqm=4_000.0,
        floor_premium=15_000.0,
        view_premium=25_000.0,
        escalation_rate=0.05,
        discount_amount=30_000.0,
    )
    outputs = run_unit_pricing(inputs)
    # base = 120 × 12_000 = 1_440_000
    # attached = 15 × 4_000 = 60_000
    # premiums = 15_000 + 25_000 = 40_000
    # pre_esc = 1_540_000
    # escalated = 1_540_000 × 1.05 = 1_617_000
    # final = 1_617_000 − 30_000 = 1_587_000
    assert outputs.base_unit_price == pytest.approx(1_440_000.0)
    assert outputs.attached_area_price == pytest.approx(60_000.0)
    assert outputs.premium_total == pytest.approx(40_000.0)
    assert outputs.pre_escalation_price == pytest.approx(1_540_000.0)
    assert outputs.escalated_price == pytest.approx(1_617_000.0)
    assert outputs.final_unit_price == pytest.approx(1_587_000.0)
