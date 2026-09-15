"""Exact physical totals independent of database fixtures."""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.modules.inventory.physical import COMPONENTS, gross_measurement
from app.modules.sales import service as sales_service


def lines(values: tuple[str, ...]) -> list[dict]:
    return [
        {"physical_component": component, "raw_area": Decimal(value), "unit_of_measure": "sqm"}
        for component, value in zip(COMPONENTS, values, strict=True)
    ]


def test_net_and_gross_follow_owner_formulas_without_weights() -> None:
    result = gross_measurement(lines(("75.3", "12.5", "20", "8", "4.2", "0")))
    assert result["net_area"] == Decimal("87.8")
    assert result["gross_area"] == Decimal("120.0")
    assert result["net_area_unit"] == result["gross_area_unit"] == "sqm"


def test_an_outdoor_component_absent_from_the_schedule_adds_no_area() -> None:
    """An outdoor component the approved schedule does not list is not unknown.

    It is a component the unit does not have, so gross equals net rather than
    refusing a total. Only the internal area is required; it is what gross and
    net are both built from, and without it neither can be stated.
    """
    result = gross_measurement(lines(("75.3", "12.5", "20", "8", "4.2", "0"))[:2])
    assert result["net_area"] == Decimal("87.8")
    assert result["gross_area"] == Decimal("87.8")
    assert result["gross_missing_components"] == []
    assert result["gross_area_reason"] is None


def test_gross_is_still_refused_when_the_internal_area_is_the_missing_one() -> None:
    """The one component whose absence is genuinely unknown, not zero."""
    result = gross_measurement(lines(("75.3", "12.5", "20", "8", "4.2", "0"))[1:])
    assert result["net_area"] is None
    assert result["gross_area"] is None
    assert result["gross_missing_components"] == ["internal"]
    assert result["gross_area_reason"] == (
        "Record the internal area to calculate net and gross area."
    )


def test_missing_mixed_or_duplicate_net_measurements_are_not_zero() -> None:
    measured = lines(("75.3", "0", "0", "0", "0", "0"))
    assert gross_measurement(measured)["net_area"] == Decimal("75.3")
    assert gross_measurement(measured[1:])["net_area"] is None
    assert gross_measurement([*measured, measured[0]])["net_area"] is None
    measured[1]["unit_of_measure"] = "sqft"
    assert gross_measurement(measured)["net_area"] is None
    assert gross_measurement(measured)["gross_area"] is None


def test_explicit_zero_totals_are_valid_measurements() -> None:
    result = gross_measurement(lines(("0", "0", "0", "0", "0", "0")))
    assert result["net_area"] == result["gross_area"] == Decimal("0")


@pytest.mark.parametrize("gross,expected", [("100", "2500.00"), ("120", "2083.33"), ("0", None)])
def test_sale_rate_is_unit_price_divided_by_gross(
    gross: str, expected: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sales_service.inventory_service, "approved_schedule", lambda *a, **k: True)
    monkeypatch.setattr(
        sales_service.inventory_service,
        "area_lines",
        lambda *a, **k: lines((gross, "0", "0", "0", "0", "0")),
    )
    sale = SimpleNamespace(
        unit_id=None, project_id=None, net_contract_price_ex_tax=Decimal("250000")
    )
    result = sales_service.sale_gross_price(None, sale=sale)
    assert result["price_per_gross_area"] == (Decimal(expected) if expected else None)
    assert result["gross_area_unit"] == "sqm"
