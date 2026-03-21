"""
Tests for the formal per-unit pricing record API.

Validates the GET/PUT /api/v1/units/{unit_id}/pricing endpoints,
service business logic, and data consistency rules.
"""

import pytest
from fastapi.testclient import TestClient


def _create_hierarchy(client: TestClient, proj_code: str = "PRJ-UPR") -> tuple[str, str]:
    """Create a full project hierarchy and return (project_id, unit_id)."""
    project_id = client.post(
        "/api/v1/projects",
        json={"name": "Pricing Record Project", "code": proj_code},
    ).json()["id"]
    phase_id = client.post(
        "/api/v1/phases",
        json={"project_id": project_id, "name": "Phase 1", "sequence": 1},
    ).json()["id"]
    building_id = client.post(
        f"/api/v1/phases/{phase_id}/buildings",
        json={"name": "Block A", "code": "BLK-A"},
    ).json()["id"]
    floor_id = client.post(
        f"/api/v1/buildings/{building_id}/floors",
        json={"name": "Floor 1", "code": "FL-01", "sequence_number": 1},
    ).json()["id"]
    unit_id = client.post(
        "/api/v1/units",
        json={"floor_id": floor_id, "unit_number": "101", "unit_type": "studio", "internal_area": 85.0},
    ).json()["id"]
    return project_id, unit_id


_VALID_PRICING_PAYLOAD = {
    "base_price": 500_000.0,
    "manual_adjustment": 25_000.0,
    "currency": "AED",
    "pricing_status": "draft",
    "notes": "Initial pricing for unit 101",
}


# ---------------------------------------------------------------------------
# GET /api/v1/units/{unit_id}/pricing
# ---------------------------------------------------------------------------

def test_get_unit_pricing_not_set_returns_404(client: TestClient):
    """GET pricing for a unit with no record should return 404."""
    _, unit_id = _create_hierarchy(client, "PRJ-GNONE")
    resp = client.get(f"/api/v1/units/{unit_id}/pricing")
    assert resp.status_code == 404


def test_get_unit_pricing_invalid_unit_returns_404(client: TestClient):
    """GET pricing for a non-existent unit should return 404."""
    resp = client.get("/api/v1/units/no-such-unit/pricing")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/v1/units/{unit_id}/pricing
# ---------------------------------------------------------------------------

def test_create_pricing_record(client: TestClient):
    """PUT pricing with a valid payload should create a pricing record."""
    _, unit_id = _create_hierarchy(client, "PRJ-CREAT")
    resp = client.put(f"/api/v1/units/{unit_id}/pricing", json=_VALID_PRICING_PAYLOAD)
    assert resp.status_code == 200
    data = resp.json()
    assert data["unit_id"] == unit_id
    assert data["base_price"] == pytest.approx(500_000.0)
    assert data["manual_adjustment"] == pytest.approx(25_000.0)
    assert data["final_price"] == pytest.approx(525_000.0)
    assert data["currency"] == "AED"
    assert data["pricing_status"] == "draft"
    assert data["notes"] == "Initial pricing for unit 101"


def test_put_unit_pricing_invalid_unit_returns_404(client: TestClient):
    """PUT pricing for a non-existent unit should return 404."""
    resp = client.put("/api/v1/units/no-such-unit/pricing", json=_VALID_PRICING_PAYLOAD)
    assert resp.status_code == 404


def test_update_pricing_record(client: TestClient):
    """PUT pricing twice should update the existing record (upsert)."""
    _, unit_id = _create_hierarchy(client, "PRJ-UPDATE")
    client.put(f"/api/v1/units/{unit_id}/pricing", json=_VALID_PRICING_PAYLOAD)
    updated_payload = {**_VALID_PRICING_PAYLOAD, "base_price": 600_000.0, "pricing_status": "reviewed"}
    resp = client.put(f"/api/v1/units/{unit_id}/pricing", json=updated_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["base_price"] == pytest.approx(600_000.0)
    assert data["final_price"] == pytest.approx(625_000.0)
    assert data["pricing_status"] == "reviewed"


def test_one_pricing_record_per_unit(client: TestClient):
    """Multiple PUTs to the same unit must result in exactly one pricing record."""
    _, unit_id = _create_hierarchy(client, "PRJ-ONEPER")
    client.put(f"/api/v1/units/{unit_id}/pricing", json=_VALID_PRICING_PAYLOAD)
    client.put(f"/api/v1/units/{unit_id}/pricing", json={**_VALID_PRICING_PAYLOAD, "base_price": 550_000.0})
    # GET must return a single record with the latest values
    resp = client.get(f"/api/v1/units/{unit_id}/pricing")
    assert resp.status_code == 200
    assert resp.json()["base_price"] == pytest.approx(550_000.0)


# ---------------------------------------------------------------------------
# final_price calculation
# ---------------------------------------------------------------------------

def test_final_price_equals_base_plus_adjustment(client: TestClient):
    """final_price must equal base_price + manual_adjustment."""
    _, unit_id = _create_hierarchy(client, "PRJ-CALC")
    payload = {"base_price": 300_000.0, "manual_adjustment": -15_000.0, "currency": "AED"}
    resp = client.put(f"/api/v1/units/{unit_id}/pricing", json=payload)
    assert resp.status_code == 200
    assert resp.json()["final_price"] == pytest.approx(285_000.0)


def test_final_price_zero_adjustment(client: TestClient):
    """final_price equals base_price when manual_adjustment is zero."""
    _, unit_id = _create_hierarchy(client, "PRJ-ZEROADJ")
    payload = {"base_price": 400_000.0, "currency": "AED"}
    resp = client.put(f"/api/v1/units/{unit_id}/pricing", json=payload)
    assert resp.status_code == 200
    assert resp.json()["final_price"] == pytest.approx(400_000.0)


def test_negative_final_price_rejected(client: TestClient):
    """PUT that would result in a negative final_price should return 422."""
    _, unit_id = _create_hierarchy(client, "PRJ-NEGPRC")
    payload = {
        "base_price": 100_000.0,
        "manual_adjustment": -200_000.0,
        "currency": "AED",
    }
    resp = client.put(f"/api/v1/units/{unit_id}/pricing", json=payload)
    assert resp.status_code == 422


def test_approved_status_persisted(client: TestClient):
    """Pricing status 'approved' must be stored and retrieved correctly via the approval endpoint."""
    _, unit_id = _create_hierarchy(client, "PRJ-APPRD")
    # Create a draft record first, then approve via the dedicated endpoint.
    record = client.put(f"/api/v1/units/{unit_id}/pricing", json=_VALID_PRICING_PAYLOAD).json()
    approve_resp = client.post(
        f"/api/v1/pricing/{record['id']}/approve",
        json={"approved_by": "manager@example.com"},
    )
    assert approve_resp.status_code == 200
    get_resp = client.get(f"/api/v1/units/{unit_id}/pricing")
    assert get_resp.json()["pricing_status"] == "approved"


def test_invalid_pricing_status_rejected(client: TestClient):
    """PUT with an invalid pricing_status should return 422."""
    _, unit_id = _create_hierarchy(client, "PRJ-BADST")
    payload = {**_VALID_PRICING_PAYLOAD, "pricing_status": "pending"}
    resp = client.put(f"/api/v1/units/{unit_id}/pricing", json=payload)
    assert resp.status_code == 422


def test_negative_base_price_rejected(client: TestClient):
    """PUT with a negative base_price should return 422."""
    _, unit_id = _create_hierarchy(client, "PRJ-NEGBASE")
    payload = {**_VALID_PRICING_PAYLOAD, "base_price": -1000.0}
    resp = client.put(f"/api/v1/units/{unit_id}/pricing", json=payload)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Response structure
# ---------------------------------------------------------------------------

def test_response_structure(client: TestClient):
    """Pricing response must contain all required fields."""
    _, unit_id = _create_hierarchy(client, "PRJ-STRUCT")
    client.put(f"/api/v1/units/{unit_id}/pricing", json=_VALID_PRICING_PAYLOAD)
    resp = client.get(f"/api/v1/units/{unit_id}/pricing")
    assert resp.status_code == 200
    data = resp.json()
    required_fields = [
        "id", "unit_id", "base_price", "manual_adjustment", "final_price",
        "currency", "pricing_status", "notes", "created_at", "updated_at",
    ]
    for field in required_fields:
        assert field in data, f"Missing field: {field}"


def test_pricing_does_not_alter_unit_inventory(client: TestClient):
    """Setting a pricing record must not change any unit inventory fields."""
    _, unit_id = _create_hierarchy(client, "PRJ-NOALT")
    unit_before = client.get(f"/api/v1/units/{unit_id}").json()
    client.put(f"/api/v1/units/{unit_id}/pricing", json=_VALID_PRICING_PAYLOAD)
    unit_after = client.get(f"/api/v1/units/{unit_id}").json()
    for field in ["unit_number", "unit_type", "status", "internal_area"]:
        assert unit_before[field] == unit_after[field], f"Field mutated: {field}"
