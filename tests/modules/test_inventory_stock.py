"""Stock presents approved physical evidence without inventing missing areas."""

from decimal import Decimal

from fastapi.testclient import TestClient

from app.modules.inventory.physical import component_measurements
from tests.modules.conftest import approve_areas, inventory_url


def test_stock_components_keep_zero_unknown_and_duplicate_distinct() -> None:
    line = {
        "physical_component": "internal",
        "raw_area": Decimal("95.123456"),
        "unit_of_measure": "sqm",
    }
    result = component_measurements(
        [
            line,
            {"physical_component": "balcony", "raw_area": Decimal("0"), "unit_of_measure": "sqm"},
        ]
    )
    assert result["internal"]["area"] == Decimal("95.123456")
    assert result["balcony"]["area"] == Decimal("0")
    assert result["roof_garden"] == {"area": None, "unit": None}
    assert component_measurements([line, line])["internal"] == {"area": None, "unit": None}


def test_stock_register_exposes_approved_component_areas(
    admin_client: TestClient, project_id: str, unit_id: str, area_types: dict[str, str]
) -> None:
    approve_areas(admin_client, project_id, unit_id, area_types, internal="101.25")
    result = admin_client.get(f"{inventory_url(project_id)}/units")
    assert result.status_code == 200, result.text
    unit = next(row for row in result.json()["units"] if row["id"] == unit_id)
    assert Decimal(unit["physical_components"]["internal"]["area"]) == Decimal("101.25")
    assert "bathrooms" in unit and "view_class_code" in unit and "orientation_code" in unit
