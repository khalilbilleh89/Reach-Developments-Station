"""
Tests for the units module.

Validates create / list / get / update / delete behaviour and hierarchy enforcement.
"""

import pytest
from fastapi.testclient import TestClient


def _create_hierarchy(client: TestClient, proj_code: str = "PRJ-UNIT"):
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
    return floor_id


def test_create_unit(client: TestClient):
    """POST /api/v1/units should create and return a unit."""
    floor_id = _create_hierarchy(client)
    response = client.post(
        "/api/v1/units",
        json={
            "floor_id": floor_id,
            "unit_number": "101",
            "unit_type": "studio",
            "internal_area": 55.0,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["floor_id"] == floor_id
    assert data["unit_number"] == "101"
    assert data["status"] == "available"


def test_create_unit_invalid_floor(client: TestClient):
    """POST /api/v1/units with non-existent floor_id should return 404."""
    response = client.post(
        "/api/v1/units",
        json={
            "floor_id": "no-such-floor",
            "unit_number": "101",
            "unit_type": "studio",
            "internal_area": 55.0,
        },
    )
    assert response.status_code == 404


def test_create_unit_duplicate_number(client: TestClient):
    """Duplicate unit number on the same floor should return 409."""
    floor_id = _create_hierarchy(client)
    client.post(
        "/api/v1/units",
        json={
            "floor_id": floor_id,
            "unit_number": "101",
            "unit_type": "studio",
            "internal_area": 55.0,
        },
    )
    response = client.post(
        "/api/v1/units",
        json={
            "floor_id": floor_id,
            "unit_number": "101",
            "unit_type": "one_bedroom",
            "internal_area": 70.0,
        },
    )
    assert response.status_code == 409


def test_list_units_filtered_by_floor(client: TestClient):
    """GET /api/v1/units?floor_id=... should return units for that floor."""
    floor_id = _create_hierarchy(client)
    client.post(
        "/api/v1/units",
        json={
            "floor_id": floor_id,
            "unit_number": "101",
            "unit_type": "studio",
            "internal_area": 55.0,
        },
    )
    response = client.get(f"/api/v1/units?floor_id={floor_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1


def test_get_unit(client: TestClient):
    """GET /api/v1/units/{id} should return the unit."""
    floor_id = _create_hierarchy(client)
    create = client.post(
        "/api/v1/units",
        json={
            "floor_id": floor_id,
            "unit_number": "101",
            "unit_type": "studio",
            "internal_area": 55.0,
        },
    )
    unit_id = create.json()["id"]
    response = client.get(f"/api/v1/units/{unit_id}")
    assert response.status_code == 200
    assert response.json()["id"] == unit_id


def test_get_unit_not_found(client: TestClient):
    """GET /api/v1/units/{id} with unknown id should return 404."""
    response = client.get("/api/v1/units/no-such-unit")
    assert response.status_code == 404


def test_update_unit(client: TestClient):
    """PATCH /api/v1/units/{id} should update the unit."""
    floor_id = _create_hierarchy(client)
    create = client.post(
        "/api/v1/units",
        json={
            "floor_id": floor_id,
            "unit_number": "101",
            "unit_type": "studio",
            "internal_area": 55.0,
        },
    )
    unit_id = create.json()["id"]
    response = client.patch(
        f"/api/v1/units/{unit_id}", json={"status": "reserved", "internal_area": 60.0}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "reserved"
    assert float(data["internal_area"]) == 60.0


def test_delete_unit(client: TestClient):
    """DELETE /api/v1/units/{id} should remove the unit."""
    floor_id = _create_hierarchy(client, proj_code="PRJ-DEL")
    create = client.post(
        "/api/v1/units",
        json={
            "floor_id": floor_id,
            "unit_number": "201",
            "unit_type": "one_bedroom",
            "internal_area": 70.0,
        },
    )
    assert create.status_code == 201
    unit_id = create.json()["id"]
    delete_response = client.delete(f"/api/v1/units/{unit_id}")
    assert delete_response.status_code == 204
    get_response = client.get(f"/api/v1/units/{unit_id}")
    assert get_response.status_code == 404


def test_delete_unit_not_found(client: TestClient):
    """DELETE /api/v1/units/{id} with unknown id should return 404."""
    response = client.delete("/api/v1/units/no-such-unit")
    assert response.status_code == 404


def test_create_unit_floor_scoped(client: TestClient):
    """POST /api/v1/floors/{floor_id}/units should create a unit using floor from URL."""
    floor_id = _create_hierarchy(client, proj_code="PRJ-FS")
    response = client.post(
        f"/api/v1/floors/{floor_id}/units",
        json={
            "unit_number": "301",
            "unit_type": "two_bedroom",
            "internal_area": 90.0,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["floor_id"] == floor_id
    assert data["unit_number"] == "301"


def test_create_unit_with_apartment_attributes(client: TestClient):
    """POST /api/v1/units with apartment attributes should persist and return them."""
    floor_id = _create_hierarchy(client, proj_code="PRJ-APT1")
    response = client.post(
        "/api/v1/units",
        json={
            "floor_id": floor_id,
            "unit_number": "A101",
            "unit_type": "two_bedroom",
            "internal_area": 90.0,
            "bedrooms": 2,
            "bathrooms": 2,
            "floor_level": "1",
            "livable_area": 85.0,
            "balcony_area": 10.0,
            "has_roof_garden": False,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["bedrooms"] == 2
    assert data["bathrooms"] == 2
    assert data["floor_level"] == "1"
    assert float(data["livable_area"]) == 85.0
    assert float(data["balcony_area"]) == 10.0
    assert data["has_roof_garden"] is False


def test_create_unit_with_roof_garden(client: TestClient):
    """POST /api/v1/units with has_roof_garden=True and roof_garden_area should succeed."""
    floor_id = _create_hierarchy(client, proj_code="PRJ-RG1")
    response = client.post(
        "/api/v1/units",
        json={
            "floor_id": floor_id,
            "unit_number": "B201",
            "unit_type": "penthouse",
            "internal_area": 150.0,
            "has_roof_garden": True,
            "roof_garden_area": 40.0,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["has_roof_garden"] is True
    assert float(data["roof_garden_area"]) == 40.0


def test_create_unit_roof_garden_false_with_area_rejected(client: TestClient):
    """POST with has_roof_garden=False and roof_garden_area > 0 should return 422."""
    floor_id = _create_hierarchy(client, proj_code="PRJ-RG2")
    response = client.post(
        "/api/v1/units",
        json={
            "floor_id": floor_id,
            "unit_number": "C301",
            "unit_type": "studio",
            "internal_area": 55.0,
            "has_roof_garden": False,
            "roof_garden_area": 20.0,
        },
    )
    assert response.status_code == 422


def test_update_unit_apartment_attributes(client: TestClient):
    """PATCH /api/v1/units/{id} should update apartment attributes."""
    floor_id = _create_hierarchy(client, proj_code="PRJ-UPD2")
    create = client.post(
        "/api/v1/units",
        json={
            "floor_id": floor_id,
            "unit_number": "D401",
            "unit_type": "one_bedroom",
            "internal_area": 70.0,
        },
    )
    assert create.status_code == 201
    unit_id = create.json()["id"]

    response = client.patch(
        f"/api/v1/units/{unit_id}",
        json={
            "bedrooms": 1,
            "bathrooms": 1,
            "floor_level": "4",
            "livable_area": 65.0,
            "has_roof_garden": False,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["bedrooms"] == 1
    assert data["bathrooms"] == 1
    assert data["floor_level"] == "4"
    assert float(data["livable_area"]) == 65.0
    assert data["has_roof_garden"] is False


def test_existing_unit_without_apartment_attributes_still_valid(client: TestClient):
    """Units created without new fields should return null for those fields."""
    floor_id = _create_hierarchy(client, proj_code="PRJ-OLD1")
    create = client.post(
        "/api/v1/units",
        json={
            "floor_id": floor_id,
            "unit_number": "E501",
            "unit_type": "studio",
            "internal_area": 50.0,
        },
    )
    assert create.status_code == 201
    unit_id = create.json()["id"]

    response = client.get(f"/api/v1/units/{unit_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["bedrooms"] is None
    assert data["bathrooms"] is None
    assert data["floor_level"] is None
    assert data["livable_area"] is None
    assert data["has_roof_garden"] is None


def test_list_units_floor_scoped(client: TestClient):
    """GET /api/v1/floors/{floor_id}/units should list units for that floor."""
    floor_id = _create_hierarchy(client, proj_code="PRJ-LSF")
    create = client.post(
        f"/api/v1/floors/{floor_id}/units",
        json={
            "unit_number": "401",
            "unit_type": "studio",
            "internal_area": 50.0,
        },
    )
    assert create.status_code == 201
    response = client.get(f"/api/v1/floors/{floor_id}/units")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["unit_number"] == "401"
