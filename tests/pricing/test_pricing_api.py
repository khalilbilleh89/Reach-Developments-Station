"""
Tests for the pricing API endpoints.

Validates HTTP behaviour, request/response contracts, and full workflow.
"""

import pytest
from fastapi.testclient import TestClient


def _create_hierarchy(client: TestClient, proj_code: str = "PRJ-PAPI") -> tuple[str, str]:
    """Create a full project hierarchy and return (project_id, unit_id)."""
    project_id = client.post("/api/v1/projects", json={"name": "Pricing Project", "code": proj_code}).json()["id"]
    phase_id = client.post("/api/v1/phases", json={"project_id": project_id, "name": "Phase 1", "sequence": 1}).json()["id"]
    building_id = client.post("/api/v1/buildings", json={"phase_id": phase_id, "name": "Block A", "code": "BLK-A"}).json()["id"]
    floor_id = client.post("/api/v1/floors", json={"building_id": building_id, "level": 1}).json()["id"]
    unit_id = client.post(
        "/api/v1/units",
        json={"floor_id": floor_id, "unit_number": "101", "unit_type": "studio", "internal_area": 100.0},
    ).json()["id"]
    return project_id, unit_id


_VALID_ATTRS_PAYLOAD = {
    "base_price_per_sqm": 5000.0,
    "floor_premium": 10000.0,
    "view_premium": 15000.0,
    "corner_premium": 5000.0,
    "size_adjustment": 2000.0,
    "custom_adjustment": -1000.0,
}


# ---------------------------------------------------------------------------
# Pricing attributes endpoints
# ---------------------------------------------------------------------------

def test_set_unit_pricing_attributes(client: TestClient):
    """POST /api/v1/pricing/unit/{id}/attributes should store pricing attributes."""
    _, unit_id = _create_hierarchy(client)
    resp = client.post(f"/api/v1/pricing/unit/{unit_id}/attributes", json=_VALID_ATTRS_PAYLOAD)
    assert resp.status_code == 201
    data = resp.json()
    assert data["unit_id"] == unit_id
    assert data["base_price_per_sqm"] == pytest.approx(5000.0)
    assert data["floor_premium"] == pytest.approx(10000.0)


def test_set_unit_pricing_attributes_invalid_unit(client: TestClient):
    """POST attributes with non-existent unit_id should return 404."""
    resp = client.post("/api/v1/pricing/unit/no-such-unit/attributes", json=_VALID_ATTRS_PAYLOAD)
    assert resp.status_code == 404


def test_get_unit_pricing_attributes(client: TestClient):
    """GET /api/v1/pricing/unit/{id}/attributes should return stored attributes."""
    _, unit_id = _create_hierarchy(client, "PRJ-GATTR")
    client.post(f"/api/v1/pricing/unit/{unit_id}/attributes", json=_VALID_ATTRS_PAYLOAD)
    resp = client.get(f"/api/v1/pricing/unit/{unit_id}/attributes")
    assert resp.status_code == 200
    data = resp.json()
    assert data["unit_id"] == unit_id
    assert data["view_premium"] == pytest.approx(15000.0)


def test_get_unit_pricing_attributes_not_set(client: TestClient):
    """GET attributes when not set should return 404."""
    _, unit_id = _create_hierarchy(client, "PRJ-NOATTR")
    resp = client.get(f"/api/v1/pricing/unit/{unit_id}/attributes")
    assert resp.status_code == 404


def test_upsert_pricing_attributes_replaces(client: TestClient):
    """POST attributes twice should replace the existing attributes."""
    _, unit_id = _create_hierarchy(client, "PRJ-UPS")
    client.post(f"/api/v1/pricing/unit/{unit_id}/attributes", json=_VALID_ATTRS_PAYLOAD)
    updated = {**_VALID_ATTRS_PAYLOAD, "base_price_per_sqm": 6000.0}
    resp = client.post(f"/api/v1/pricing/unit/{unit_id}/attributes", json=updated)
    assert resp.status_code == 201
    assert resp.json()["base_price_per_sqm"] == pytest.approx(6000.0)


# ---------------------------------------------------------------------------
# Price calculation endpoints
# ---------------------------------------------------------------------------

def test_get_unit_price(client: TestClient):
    """GET /api/v1/pricing/unit/{id} should return the calculated price."""
    _, unit_id = _create_hierarchy(client, "PRJ-GUPRC")
    client.post(f"/api/v1/pricing/unit/{unit_id}/attributes", json=_VALID_ATTRS_PAYLOAD)
    resp = client.get(f"/api/v1/pricing/unit/{unit_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["unit_id"] == unit_id
    assert data["unit_area"] == pytest.approx(100.0)
    assert data["base_unit_price"] == pytest.approx(500_000.0)
    assert data["premium_total"] == pytest.approx(31_000.0)
    assert data["final_unit_price"] == pytest.approx(531_000.0)


def test_calculate_unit_price(client: TestClient):
    """POST /api/v1/pricing/unit/{id}/calculate should return the calculated price."""
    _, unit_id = _create_hierarchy(client, "PRJ-CALC")
    client.post(f"/api/v1/pricing/unit/{unit_id}/attributes", json=_VALID_ATTRS_PAYLOAD)
    resp = client.post(f"/api/v1/pricing/unit/{unit_id}/calculate")
    assert resp.status_code == 200
    data = resp.json()
    assert data["unit_id"] == unit_id
    assert data["final_unit_price"] == pytest.approx(531_000.0)


def test_get_unit_price_no_attributes_returns_422(client: TestClient):
    """GET unit price without pricing attributes should return 422."""
    _, unit_id = _create_hierarchy(client, "PRJ-NOATCALC")
    resp = client.get(f"/api/v1/pricing/unit/{unit_id}")
    assert resp.status_code == 422


def test_calculate_unit_price_no_attributes_returns_422(client: TestClient):
    """POST calculate without attributes should return 422."""
    _, unit_id = _create_hierarchy(client, "PRJ-NOCALC")
    resp = client.post(f"/api/v1/pricing/unit/{unit_id}/calculate")
    assert resp.status_code == 422


def test_get_unit_price_not_found(client: TestClient):
    """GET price for non-existent unit should return 404."""
    resp = client.get("/api/v1/pricing/unit/no-such-unit")
    assert resp.status_code == 404


def test_calculate_unit_price_not_found(client: TestClient):
    """POST calculate for non-existent unit should return 404."""
    resp = client.post("/api/v1/pricing/unit/no-such-unit/calculate")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Project pricing summary
# ---------------------------------------------------------------------------

def test_get_project_price_summary(client: TestClient):
    """GET /api/v1/pricing/project/{id} should return a project pricing summary."""
    project_id, unit_id = _create_hierarchy(client, "PRJ-PSUM")
    client.post(
        f"/api/v1/pricing/unit/{unit_id}/attributes",
        json={
            "base_price_per_sqm": 5000.0,
            "floor_premium": 0.0,
            "view_premium": 0.0,
            "corner_premium": 0.0,
            "size_adjustment": 0.0,
            "custom_adjustment": 0.0,
        },
    )
    resp = client.get(f"/api/v1/pricing/project/{project_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == project_id
    assert data["total_units_priced"] == 1
    assert data["total_value"] == pytest.approx(500_000.0)
    assert len(data["items"]) == 1


def test_get_project_price_summary_no_units_priced(client: TestClient):
    """GET project summary with no priced units returns zero totals."""
    project_id, _ = _create_hierarchy(client, "PRJ-PSUMEMPTY")
    resp = client.get(f"/api/v1/pricing/project/{project_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_units_priced"] == 0
    assert data["total_value"] == pytest.approx(0.0)
    assert data["items"] == []


def test_get_project_price_summary_not_found(client: TestClient):
    """GET project summary for non-existent project should return 404."""
    resp = client.get("/api/v1/pricing/project/no-such-project")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Response structure validation
# ---------------------------------------------------------------------------

def test_unit_price_response_structure(client: TestClient):
    """Unit price response must contain all required fields."""
    _, unit_id = _create_hierarchy(client, "PRJ-STRUCT")
    client.post(f"/api/v1/pricing/unit/{unit_id}/attributes", json=_VALID_ATTRS_PAYLOAD)
    resp = client.get(f"/api/v1/pricing/unit/{unit_id}")
    data = resp.json()
    required_fields = ["unit_id", "unit_area", "base_unit_price", "premium_total", "final_unit_price"]
    for field in required_fields:
        assert field in data, f"Missing field: {field}"
        assert data[field] is not None, f"Field is None: {field}"


def test_pricing_attributes_response_structure(client: TestClient):
    """Pricing attributes response must contain all required fields."""
    _, unit_id = _create_hierarchy(client, "PRJ-ATSTR")
    resp = client.post(f"/api/v1/pricing/unit/{unit_id}/attributes", json=_VALID_ATTRS_PAYLOAD)
    data = resp.json()
    required_fields = [
        "id", "unit_id", "base_price_per_sqm", "floor_premium", "view_premium",
        "corner_premium", "size_adjustment", "custom_adjustment", "created_at", "updated_at",
    ]
    for field in required_fields:
        assert field in data, f"Missing field: {field}"


def test_price_calculation_is_deterministic(client: TestClient):
    """Repeated price calculation calls must return the same result."""
    _, unit_id = _create_hierarchy(client, "PRJ-DET")
    client.post(f"/api/v1/pricing/unit/{unit_id}/attributes", json=_VALID_ATTRS_PAYLOAD)
    resp1 = client.post(f"/api/v1/pricing/unit/{unit_id}/calculate")
    resp2 = client.post(f"/api/v1/pricing/unit/{unit_id}/calculate")
    assert resp1.json()["final_unit_price"] == resp2.json()["final_unit_price"]
