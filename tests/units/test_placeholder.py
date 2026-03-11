"""
Tests for the units module.

Validates create / list / get / update behaviour and hierarchy enforcement.
"""

import pytest
from fastapi.testclient import TestClient


def _create_hierarchy(client: TestClient, proj_code: str = "PRJ-UNIT"):
    project_id = client.post("/api/v1/projects", json={"name": "Test Project", "code": proj_code}).json()["id"]
    phase_id = client.post("/api/v1/phases", json={"project_id": project_id, "name": "Phase 1", "sequence": 1}).json()["id"]
    building_id = client.post("/api/v1/buildings", json={"phase_id": phase_id, "name": "Block A", "code": "BLK-A"}).json()["id"]
    floor_id = client.post("/api/v1/floors", json={"building_id": building_id, "level": 1}).json()["id"]
    return floor_id


def test_create_unit(client: TestClient):
    """POST /api/v1/units should create and return a unit."""
    floor_id = _create_hierarchy(client)
    response = client.post(
        "/api/v1/units",
        json={"floor_id": floor_id, "unit_number": "101", "unit_type": "studio", "internal_area": 55.0},
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
        json={"floor_id": "no-such-floor", "unit_number": "101", "unit_type": "studio", "internal_area": 55.0},
    )
    assert response.status_code == 404


def test_create_unit_duplicate_number(client: TestClient):
    """Duplicate unit number on the same floor should return 409."""
    floor_id = _create_hierarchy(client)
    client.post("/api/v1/units", json={"floor_id": floor_id, "unit_number": "101", "unit_type": "studio", "internal_area": 55.0})
    response = client.post("/api/v1/units", json={"floor_id": floor_id, "unit_number": "101", "unit_type": "one_bedroom", "internal_area": 70.0})
    assert response.status_code == 409


def test_list_units_filtered_by_floor(client: TestClient):
    """GET /api/v1/units?floor_id=... should return units for that floor."""
    floor_id = _create_hierarchy(client)
    client.post("/api/v1/units", json={"floor_id": floor_id, "unit_number": "101", "unit_type": "studio", "internal_area": 55.0})
    response = client.get(f"/api/v1/units?floor_id={floor_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1


def test_get_unit(client: TestClient):
    """GET /api/v1/units/{id} should return the unit."""
    floor_id = _create_hierarchy(client)
    create = client.post("/api/v1/units", json={"floor_id": floor_id, "unit_number": "101", "unit_type": "studio", "internal_area": 55.0})
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
    create = client.post("/api/v1/units", json={"floor_id": floor_id, "unit_number": "101", "unit_type": "studio", "internal_area": 55.0})
    unit_id = create.json()["id"]
    response = client.patch(f"/api/v1/units/{unit_id}", json={"status": "reserved", "internal_area": 60.0})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "reserved"
    assert float(data["internal_area"]) == 60.0

