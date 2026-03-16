"""
Tests for the unit qualitative pricing attributes API.

Validates GET and PUT behaviour for /api/v1/units/{unit_id}/pricing-attributes.
"""

from fastapi.testclient import TestClient


def _create_unit(client: TestClient, proj_code: str = "PRJ-PA") -> str:
    """Create the full hierarchy and return a unit ID."""
    project_id = client.post(
        "/api/v1/projects", json={"name": "Test Project", "code": proj_code}
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
        json={"name": "Ground Floor", "code": "FL-01", "sequence_number": 1},
    ).json()["id"]
    unit_id = client.post(
        "/api/v1/units",
        json={
            "floor_id": floor_id,
            "unit_number": "101",
            "unit_type": "studio",
            "internal_area": 55.0,
        },
    ).json()["id"]
    return unit_id


def test_get_pricing_attributes_not_found(client: TestClient):
    """GET /api/v1/units/{id}/pricing-attributes returns 404 when no record exists."""
    unit_id = _create_unit(client, proj_code="PRJ-PA-GET404")
    response = client.get(f"/api/v1/units/{unit_id}/pricing-attributes")
    assert response.status_code == 404


def test_get_pricing_attributes_unit_not_found(client: TestClient):
    """GET /api/v1/units/{id}/pricing-attributes returns 404 for non-existent unit."""
    response = client.get("/api/v1/units/no-such-unit/pricing-attributes")
    assert response.status_code == 404


def test_put_pricing_attributes_creates(client: TestClient):
    """PUT /api/v1/units/{id}/pricing-attributes creates a new record (201)."""
    unit_id = _create_unit(client, proj_code="PRJ-PA-CREATE")
    payload = {
        "view_type": "sea",
        "corner_unit": True,
        "floor_premium_category": "penthouse",
        "orientation": "N",
        "outdoor_area_premium": "terrace",
        "upgrade_flag": True,
        "notes": "Premium penthouse with sea view.",
    }
    response = client.put(
        f"/api/v1/units/{unit_id}/pricing-attributes",
        json=payload,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["unit_id"] == unit_id
    assert data["view_type"] == "sea"
    assert data["corner_unit"] is True
    assert data["floor_premium_category"] == "penthouse"
    assert data["orientation"] == "N"
    assert data["outdoor_area_premium"] == "terrace"
    assert data["upgrade_flag"] is True
    assert data["notes"] == "Premium penthouse with sea view."
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_put_pricing_attributes_updates(client: TestClient):
    """PUT /api/v1/units/{id}/pricing-attributes updates an existing record (200)."""
    unit_id = _create_unit(client, proj_code="PRJ-PA-UPDATE")
    # Create
    client.put(
        f"/api/v1/units/{unit_id}/pricing-attributes",
        json={"view_type": "city", "corner_unit": False},
    )
    # Update
    response = client.put(
        f"/api/v1/units/{unit_id}/pricing-attributes",
        json={"view_type": "sea", "corner_unit": True, "orientation": "S"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["view_type"] == "sea"
    assert data["corner_unit"] is True
    assert data["orientation"] == "S"


def test_get_pricing_attributes_after_create(client: TestClient):
    """GET /api/v1/units/{id}/pricing-attributes returns 200 after PUT."""
    unit_id = _create_unit(client, proj_code="PRJ-PA-GETOK")
    client.put(
        f"/api/v1/units/{unit_id}/pricing-attributes",
        json={"view_type": "park", "floor_premium_category": "standard"},
    )
    response = client.get(f"/api/v1/units/{unit_id}/pricing-attributes")
    assert response.status_code == 200
    data = response.json()
    assert data["unit_id"] == unit_id
    assert data["view_type"] == "park"
    assert data["floor_premium_category"] == "standard"


def test_put_pricing_attributes_invalid_view_type(client: TestClient):
    """PUT /api/v1/units/{id}/pricing-attributes rejects invalid view_type (422)."""
    unit_id = _create_unit(client, proj_code="PRJ-PA-INV")
    response = client.put(
        f"/api/v1/units/{unit_id}/pricing-attributes",
        json={"view_type": "ocean"},
    )
    assert response.status_code == 422


def test_put_pricing_attributes_unit_not_found(client: TestClient):
    """PUT /api/v1/units/{id}/pricing-attributes returns 404 for non-existent unit."""
    response = client.put(
        "/api/v1/units/no-such-unit/pricing-attributes",
        json={"view_type": "sea"},
    )
    assert response.status_code == 404


def test_put_pricing_attributes_all_null(client: TestClient):
    """PUT /api/v1/units/{id}/pricing-attributes accepts all-null payload."""
    unit_id = _create_unit(client, proj_code="PRJ-PA-NULL")
    response = client.put(
        f"/api/v1/units/{unit_id}/pricing-attributes",
        json={},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["view_type"] is None
    assert data["corner_unit"] is None
    assert data["upgrade_flag"] is None
