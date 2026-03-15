"""
Tests for the floors module.

Validates create / list / get / update behaviour and hierarchy enforcement.
"""

import pytest
from fastapi.testclient import TestClient


def _create_hierarchy(client: TestClient, proj_code: str = "PRJ-FLR"):
    project_id = client.post("/api/v1/projects", json={"name": "Test Project", "code": proj_code}).json()["id"]
    phase_id = client.post("/api/v1/phases", json={"project_id": project_id, "name": "Phase 1", "sequence": 1}).json()["id"]
    building_id = client.post(f"/api/v1/phases/{phase_id}/buildings", json={"name": "Block A", "code": "BLK-A"}).json()["id"]
    return building_id


def test_create_floor(client: TestClient):
    """POST /api/v1/floors should create and return a floor."""
    building_id = _create_hierarchy(client)
    response = client.post("/api/v1/floors", json={"building_id": building_id, "level": 1})
    assert response.status_code == 201
    data = response.json()
    assert data["building_id"] == building_id
    assert data["level"] == 1


def test_create_floor_invalid_building(client: TestClient):
    """POST /api/v1/floors with non-existent building_id should return 404."""
    response = client.post("/api/v1/floors", json={"building_id": "no-such-building", "level": 1})
    assert response.status_code == 404


def test_create_floor_duplicate_level(client: TestClient):
    """Duplicate floor level within the same building should return 409."""
    building_id = _create_hierarchy(client)
    client.post("/api/v1/floors", json={"building_id": building_id, "level": 1})
    response = client.post("/api/v1/floors", json={"building_id": building_id, "level": 1})
    assert response.status_code == 409


def test_list_floors_filtered_by_building(client: TestClient):
    """GET /api/v1/floors?building_id=... should return floors for that building."""
    building_id = _create_hierarchy(client)
    client.post("/api/v1/floors", json={"building_id": building_id, "level": 1})
    response = client.get(f"/api/v1/floors?building_id={building_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1


def test_get_floor_not_found(client: TestClient):
    """GET /api/v1/floors/{id} with unknown id should return 404."""
    response = client.get("/api/v1/floors/no-such-floor")
    assert response.status_code == 404


def test_update_floor(client: TestClient):
    """PATCH /api/v1/floors/{id} should update the floor."""
    building_id = _create_hierarchy(client)
    create = client.post("/api/v1/floors", json={"building_id": building_id, "level": 1})
    floor_id = create.json()["id"]
    response = client.patch(f"/api/v1/floors/{floor_id}", json={"status": "active", "name": "Ground Floor"})
    assert response.status_code == 200
    assert response.json()["name"] == "Ground Floor"
    assert response.json()["status"] == "active"
