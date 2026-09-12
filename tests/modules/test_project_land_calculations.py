"""Decimal acquisition and assumption formulas, without invented market facts."""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.modules.projects.land_analytics import cost_breakdown, derive_analytics


def parcel(**changes: object) -> SimpleNamespace:
    values = {
        "purchase_price": Decimal("1000000"),
        "acquisition_fees": Decimal("1000"),
        "acquisition_tax_rate_fraction": Decimal("0.05"),
        "agent_fee_amount": Decimal("20000"),
        "legal_fee_amount": Decimal("5000"),
        "registration_fee_amount": Decimal("3000"),
        "expected_gdv_amount": Decimal("5000000"),
        "land_area": Decimal("2000"),
        "area_unit": "sqm",
    }
    values.update(changes)
    return SimpleNamespace(**values)


def test_acquisition_reconciles_with_purchase_based_percentages() -> None:
    result = cost_breakdown(parcel())
    assert result["acquisition_tax_amount"] == Decimal("50000.00")
    assert result["total_acquisition_fees"] == Decimal("79000.00")
    assert result["total_acquisition_cost"] == Decimal("1079000.00")
    assert result["agent_fee_rate_fraction"] == Decimal("0.020000")
    assert result["legal_fee_rate_fraction"] == Decimal("0.005000")
    assert result["registration_fee_rate_fraction"] == Decimal("0.003000")


def test_land_and_buildable_costs_use_different_areas() -> None:
    result = derive_analytics(parcel(), SimpleNamespace(maximum_gfa=Decimal("4000")), [])
    assert result["purchase_cost_per_sqm"] == Decimal("500.00")
    assert result["purchase_cost_per_buildable_sqm"] == Decimal("250.00")
    assert result["acquisition_cost_per_sqm"] == Decimal("539.50")
    assert result["acquisition_cost_per_buildable_sqm"] == Decimal("269.75")
    assert result["purchase_cost_to_gdv_fraction"] == Decimal("0.200000")
    assert result["acquisition_cost_to_gdv_fraction"] == Decimal("0.215800")


@pytest.mark.parametrize(
    "unknown",
    [
        "purchase_price",
        "acquisition_fees",
        "agent_fee_amount",
        "legal_fee_amount",
        "registration_fee_amount",
        "acquisition_tax_rate_fraction",
    ],
)
def test_missing_cost_is_not_zero(unknown: str) -> None:
    assert cost_breakdown(parcel(**{unknown: None}))["total_acquisition_cost"] is None


def test_zero_or_missing_gdv_buildable_and_purchase_never_divide_by_zero() -> None:
    result = derive_analytics(parcel(expected_gdv_amount=Decimal("0")), None, [])
    assert result["purchase_cost_to_gdv_fraction"] is None
    assert result["purchase_cost_per_buildable_sqm"] is None
    result = derive_analytics(parcel(), SimpleNamespace(maximum_gfa=Decimal("0")), [])
    assert result["acquisition_cost_per_buildable_sqm"] is None
    assert cost_breakdown(parcel(purchase_price=Decimal("0")))["agent_fee_rate_fraction"] is None


def test_sqft_is_converted_before_reporting_per_sqm() -> None:
    result = derive_analytics(parcel(land_area=Decimal("1000"), area_unit="sqft"), None, [])
    assert result["land_area_sqm"] == Decimal("92.90304000")
    assert result["purchase_cost_per_sqm"] == Decimal("10763.91")


def test_market_changes_compound_purchase_not_fees_and_allow_decreases() -> None:
    years = [
        SimpleNamespace(year=2026, change_rate_fraction=Decimal("0.10")),
        SimpleNamespace(year=2027, change_rate_fraction=Decimal("-0.05")),
    ]
    result = derive_analytics(parcel(), None, years)["market_years"]
    assert result[0]["estimated_value"] == Decimal("1100000.00")
    assert result[1]["opening_value"] == result[0]["estimated_value"]
    assert result[1]["estimated_value"] == Decimal("1045000.00")
    years[0].change_rate_fraction = Decimal("0.20")
    assert derive_analytics(parcel(), None, years)["market_years"][1]["estimated_value"] == Decimal(
        "1140000.00"
    )


def test_market_overflow_is_unavailable_not_an_exception() -> None:
    years = [SimpleNamespace(year=2026, change_rate_fraction=Decimal("10"))]
    result = derive_analytics(parcel(purchase_price=Decimal("9999999999999999.99")), None, years)
    assert result["market_years"][0]["estimated_value"] is None
