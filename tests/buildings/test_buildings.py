"""
Tests for the buildings module.

Validates create / list / get / update / delete behaviour and hierarchy enforcement.
"""

import pytest
from fastapi.testclient import TestClient


def _create_project(client: TestClient, code: str = "PRJ-BLD") -> str:
    resp = client.post("/api/v1/projects", json={"name": "Test Project", "code": code})
    return resp.json()["id"]


def _create_phase(client: TestClient, project_id: str, sequence: int = 1) -> str:
    resp = client.post("/api/v1/phases", json={"project_id": project_id, "name": "Phase 1", "sequence": sequence})
    return resp.json()["id"]


def test_create_building(client: TestClient):
    """POST /api/v1/phases/{phase_id}/buildings should create and return a building."""
    project_id = _create_project(client)
    phase_id = _create_phase(client, project_id)
    response = client.post(
        f"/api/v1/phases/{phase_id}/buildings",
        json={"name": "Block A", "code": "BLK-A"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["phase_id"] == phase_id
    assert data["code"] == "BLK-A"


def test_create_building_invalid_phase(client: TestClient):
    """POST /api/v1/phases/{phase_id}/buildings with non-existent phase_id should return 404."""
    response = client.post(
        "/api/v1/phases/no-such-phase/buildings",
        json={"name": "Block A", "code": "BLK-A"},
    )
    assert response.status_code == 404


def test_create_building_duplicate_code_in_phase(client: TestClient):
    """Duplicate building code within the same phase should return 409."""
    project_id = _create_project(client)
    phase_id = _create_phase(client, project_id)
    client.post(f"/api/v1/phases/{phase_id}/buildings", json={"name": "Block A", "code": "BLK-A"})
    response = client.post(f"/api/v1/phases/{phase_id}/buildings", json={"name": "Block A2", "code": "BLK-A"})
    assert response.status_code == 409


def test_list_buildings_by_phase(client: TestClient):
    """GET /api/v1/phases/{phase_id}/buildings should return buildings for that phase."""
    project_id = _create_project(client)
    phase_id = _create_phase(client, project_id)
    client.post(f"/api/v1/phases/{phase_id}/buildings", json={"name": "Block A", "code": "BLK-A"})
    response = client.get(f"/api/v1/phases/{phase_id}/buildings")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1


def test_list_buildings_phase_not_found(client: TestClient):
    """GET /api/v1/phases/{phase_id}/buildings with unknown phase_id should return 404."""
    response = client.get("/api/v1/phases/no-such-phase/buildings")
    assert response.status_code == 404


def test_get_building_not_found(client: TestClient):
    """GET /api/v1/buildings/{id} with unknown id should return 404."""
    response = client.get("/api/v1/buildings/no-such-building")
    assert response.status_code == 404


def test_update_building(client: TestClient):
    """PATCH /api/v1/buildings/{id} should update the building."""
    project_id = _create_project(client)
    phase_id = _create_phase(client, project_id)
    create = client.post(f"/api/v1/phases/{phase_id}/buildings", json={"name": "Block A", "code": "BLK-A"})
    building_id = create.json()["id"]
    response = client.patch(f"/api/v1/buildings/{building_id}", json={"status": "under_construction"})
    assert response.status_code == 200
    assert response.json()["status"] == "under_construction"


def test_delete_building(client: TestClient):
    """DELETE /api/v1/buildings/{id} should remove the building."""
    project_id = _create_project(client)
    phase_id = _create_phase(client, project_id)
    create = client.post(f"/api/v1/phases/{phase_id}/buildings", json={"name": "Block A", "code": "BLK-A"})
    building_id = create.json()["id"]
    response = client.delete(f"/api/v1/buildings/{building_id}")
    assert response.status_code == 204
    get_resp = client.get(f"/api/v1/buildings/{building_id}")
    assert get_resp.status_code == 404


# ── Tests for GET /api/v1/buildings (flat list endpoint) ─────────────────────


def test_list_buildings_flat_returns_all(client: TestClient):
    """GET /api/v1/buildings without filters should return all buildings."""
    project_id = _create_project(client)
    phase_id = _create_phase(client, project_id)
    client.post(f"/api/v1/phases/{phase_id}/buildings", json={"name": "Block A", "code": "BLK-A"})
    client.post(f"/api/v1/phases/{phase_id}/buildings", json={"name": "Block B", "code": "BLK-B"})

    response = client.get("/api/v1/buildings")

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    codes = {b["code"] for b in data["items"]}
    assert "BLK-A" in codes
    assert "BLK-B" in codes


def test_list_buildings_flat_filtered_by_phase(client: TestClient):
    """GET /api/v1/buildings?phase_id= should return only buildings in that phase."""
    project_id = _create_project(client, code="PRJ-BLD-FILTER")
    phase_a_id = _create_phase(client, project_id, sequence=1)
    phase_b_id = _create_phase(client, project_id, sequence=2)

    client.post(f"/api/v1/phases/{phase_a_id}/buildings", json={"name": "Block A1", "code": "A1"})
    client.post(f"/api/v1/phases/{phase_b_id}/buildings", json={"name": "Block B1", "code": "B1"})

    response = client.get(f"/api/v1/buildings?phase_id={phase_a_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["code"] == "A1"
    assert data["items"][0]["phase_id"] == phase_a_id


def test_list_buildings_flat_pagination(client: TestClient):
    """GET /api/v1/buildings supports skip and limit pagination."""
    project_id = _create_project(client, code="PRJ-BLD-PAGE")
    phase_id = _create_phase(client, project_id)
    for i in range(3):
        client.post(f"/api/v1/phases/{phase_id}/buildings", json={"name": f"Block {i}", "code": f"BLK-{i}"})

    response_limit = client.get("/api/v1/buildings?limit=2")
    assert response_limit.status_code == 200
    limited = response_limit.json()
    assert len(limited["items"]) == 2
    assert limited["total"] == 3

    response_skip = client.get("/api/v1/buildings?skip=2&limit=10")
    assert response_skip.status_code == 200
    skipped = response_skip.json()
    assert len(skipped["items"]) == 1
