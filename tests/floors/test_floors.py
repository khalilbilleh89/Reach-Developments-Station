"""
Tests for the floors module.

Validates create / list / get / update / delete behaviour and hierarchy enforcement.
"""

import pytest
from fastapi.testclient import TestClient


def _create_hierarchy(client: TestClient, proj_code: str = "PRJ-FLR"):
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
    return building_id


def _floor_payload(**overrides) -> dict:
    base = {"name": "Ground Floor", "code": "FL-00", "sequence_number": 1}
    base.update(overrides)
    return base


def test_create_floor(client: TestClient):
    """POST /api/v1/buildings/{building_id}/floors should create and return a floor."""
    building_id = _create_hierarchy(client)
    response = client.post(
        f"/api/v1/buildings/{building_id}/floors", json=_floor_payload()
    )
    assert response.status_code == 201
    data = response.json()
    assert data["building_id"] == building_id
    assert data["name"] == "Ground Floor"
    assert data["code"] == "FL-00"
    assert data["sequence_number"] == 1
    assert data["status"] == "planned"


def test_create_floor_invalid_building(client: TestClient):
    """POST /api/v1/buildings/{building_id}/floors with non-existent building_id should return 404."""
    response = client.post(
        "/api/v1/buildings/no-such-building/floors", json=_floor_payload()
    )
    assert response.status_code == 404


def test_create_floor_duplicate_code(client: TestClient):
    """Duplicate floor code within the same building should return 409."""
    building_id = _create_hierarchy(client)
    client.post(
        f"/api/v1/buildings/{building_id}/floors",
        json=_floor_payload(code="FL-00", sequence_number=1),
    )
    response = client.post(
        f"/api/v1/buildings/{building_id}/floors",
        json=_floor_payload(code="FL-00", sequence_number=2),
    )
    assert response.status_code == 409


def test_create_floor_duplicate_sequence(client: TestClient):
    """Duplicate sequence_number within the same building should return 409."""
    building_id = _create_hierarchy(client)
    client.post(
        f"/api/v1/buildings/{building_id}/floors",
        json=_floor_payload(code="FL-00", sequence_number=1),
    )
    response = client.post(
        f"/api/v1/buildings/{building_id}/floors",
        json=_floor_payload(code="FL-01", sequence_number=1),
    )
    assert response.status_code == 409


def test_list_floors_by_building(client: TestClient):
    """GET /api/v1/buildings/{building_id}/floors should return floors for that building."""
    building_id = _create_hierarchy(client)
    client.post(f"/api/v1/buildings/{building_id}/floors", json=_floor_payload())
    response = client.get(f"/api/v1/buildings/{building_id}/floors")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1


def test_list_floors_building_not_found(client: TestClient):
    """GET /api/v1/buildings/{building_id}/floors with unknown building_id should return 404."""
    response = client.get("/api/v1/buildings/no-such-building/floors")
    assert response.status_code == 404


def test_get_floor(client: TestClient):
    """GET /api/v1/floors/{floor_id} should return the floor."""
    building_id = _create_hierarchy(client)
    create = client.post(
        f"/api/v1/buildings/{building_id}/floors", json=_floor_payload()
    )
    floor_id = create.json()["id"]
    response = client.get(f"/api/v1/floors/{floor_id}")
    assert response.status_code == 200
    assert response.json()["id"] == floor_id


def test_get_floor_not_found(client: TestClient):
    """GET /api/v1/floors/{id} with unknown id should return 404."""
    response = client.get("/api/v1/floors/no-such-floor")
    assert response.status_code == 404


def test_update_floor(client: TestClient):
    """PATCH /api/v1/floors/{id} should update the floor."""
    building_id = _create_hierarchy(client)
    create = client.post(
        f"/api/v1/buildings/{building_id}/floors", json=_floor_payload()
    )
    floor_id = create.json()["id"]
    response = client.patch(
        f"/api/v1/floors/{floor_id}", json={"status": "active", "name": "Lobby Floor"}
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Lobby Floor"
    assert response.json()["status"] == "active"


def test_delete_floor(client: TestClient):
    """DELETE /api/v1/floors/{id} should remove the floor."""
    building_id = _create_hierarchy(client)
    create = client.post(
        f"/api/v1/buildings/{building_id}/floors", json=_floor_payload()
    )
    floor_id = create.json()["id"]
    response = client.delete(f"/api/v1/floors/{floor_id}")
    assert response.status_code == 204
    get_resp = client.get(f"/api/v1/floors/{floor_id}")
    assert get_resp.status_code == 404


def test_floor_schema_fields(client: TestClient):
    """FloorResponse should include all required fields."""
    building_id = _create_hierarchy(client)
    payload = _floor_payload(level_number=0, description="Ground level")
    create = client.post(f"/api/v1/buildings/{building_id}/floors", json=payload)
    data = create.json()
    assert "id" in data
    assert "building_id" in data
    assert "name" in data
    assert "code" in data
    assert "sequence_number" in data
    assert "level_number" in data
    assert "status" in data
    assert "description" in data
    assert "created_at" in data
    assert "updated_at" in data
    assert data["description"] == "Ground level"
    assert data["level_number"] == 0


def test_floor_on_hold_status(client: TestClient):
    """FloorStatus should support on_hold."""
    building_id = _create_hierarchy(client)
    create = client.post(
        f"/api/v1/buildings/{building_id}/floors", json=_floor_payload(status="on_hold")
    )
    assert create.status_code == 201
    assert create.json()["status"] == "on_hold"


def test_list_floors_legacy_endpoint(client: TestClient):
    """GET /api/v1/floors?building_id=... backward-compatible alias should still work."""
    building_id = _create_hierarchy(client, proj_code="PRJ-FLR-LEG")
    client.post(f"/api/v1/buildings/{building_id}/floors", json=_floor_payload())
    response = client.get(f"/api/v1/floors?building_id={building_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
