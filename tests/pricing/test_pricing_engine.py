"""
Tests for the pricing calculation engine.

Validates that all formula functions produce deterministic and correct outputs.
"""

import pytest

from app.modules.pricing.engines.pricing_engine import (
    PricingInputs,
    PricingOutputs,
    calculate_adjustments,
    calculate_base_price,
    calculate_corner_premium,
    calculate_final_price,
    calculate_floor_premium,
    calculate_view_premium,
    run_pricing,
)


# ---------------------------------------------------------------------------
# Individual formula unit tests
# ---------------------------------------------------------------------------

def test_calculate_base_price():
    assert calculate_base_price(100.0, 5000.0) == pytest.approx(500_000.0)


def test_calculate_base_price_zero_area():
    assert calculate_base_price(0.0, 5000.0) == pytest.approx(0.0)


def test_calculate_floor_premium():
    assert calculate_floor_premium(10_000.0) == pytest.approx(10_000.0)


def test_calculate_view_premium():
    assert calculate_view_premium(15_000.0) == pytest.approx(15_000.0)


def test_calculate_corner_premium():
    assert calculate_corner_premium(5_000.0) == pytest.approx(5_000.0)


def test_calculate_adjustments():
    assert calculate_adjustments(2_000.0, -1_000.0) == pytest.approx(1_000.0)


def test_calculate_adjustments_zero():
    assert calculate_adjustments(0.0, 0.0) == pytest.approx(0.0)


def test_calculate_final_price():
    assert calculate_final_price(500_000.0, 30_000.0) == pytest.approx(530_000.0)


def test_calculate_final_price_zero_premium():
    assert calculate_final_price(500_000.0, 0.0) == pytest.approx(500_000.0)


# ---------------------------------------------------------------------------
# End-to-end engine tests
# ---------------------------------------------------------------------------

_STANDARD_INPUTS = PricingInputs(
    unit_area=100.0,
    base_price_per_sqm=5000.0,
    floor_premium=10_000.0,
    view_premium=15_000.0,
    corner_premium=5_000.0,
    size_adjustment=2_000.0,
    custom_adjustment=-1_000.0,
)


def test_run_pricing_base_unit_price():
    outputs = run_pricing(_STANDARD_INPUTS)
    assert outputs.base_unit_price == pytest.approx(500_000.0)


def test_run_pricing_premium_total():
    outputs = run_pricing(_STANDARD_INPUTS)
    # 10_000 + 15_000 + 5_000 + 2_000 + (-1_000) = 31_000
    assert outputs.premium_total == pytest.approx(31_000.0)


def test_run_pricing_final_unit_price():
    outputs = run_pricing(_STANDARD_INPUTS)
    assert outputs.final_unit_price == pytest.approx(531_000.0)


def test_run_pricing_zero_premiums():
    inputs = PricingInputs(
        unit_area=80.0,
        base_price_per_sqm=4000.0,
        floor_premium=0.0,
        view_premium=0.0,
        corner_premium=0.0,
        size_adjustment=0.0,
        custom_adjustment=0.0,
    )
    outputs = run_pricing(inputs)
    assert outputs.base_unit_price == pytest.approx(320_000.0)
    assert outputs.premium_total == pytest.approx(0.0)
    assert outputs.final_unit_price == pytest.approx(320_000.0)


def test_run_pricing_negative_custom_adjustment():
    inputs = PricingInputs(
        unit_area=100.0,
        base_price_per_sqm=5000.0,
        floor_premium=0.0,
        view_premium=0.0,
        corner_premium=0.0,
        size_adjustment=0.0,
        custom_adjustment=-10_000.0,
    )
    outputs = run_pricing(inputs)
    assert outputs.premium_total == pytest.approx(-10_000.0)
    assert outputs.final_unit_price == pytest.approx(490_000.0)


def test_run_pricing_returns_dataclass():
    outputs = run_pricing(_STANDARD_INPUTS)
    assert isinstance(outputs, PricingOutputs)


def test_run_pricing_is_deterministic():
    outputs1 = run_pricing(_STANDARD_INPUTS)
    outputs2 = run_pricing(_STANDARD_INPUTS)
    assert outputs1 == outputs2
