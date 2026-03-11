"""
Tests for the phases module.

Validates create / list / get / update behaviour and hierarchy enforcement.
"""

import pytest
from fastapi.testclient import TestClient


def _create_project(client: TestClient, code: str = "PRJ-001") -> str:
    resp = client.post("/api/v1/projects", json={"name": "Test Project", "code": code})
    return resp.json()["id"]


def test_create_phase(client: TestClient):
    """POST /api/v1/phases should create and return a phase."""
    project_id = _create_project(client)
    response = client.post(
        "/api/v1/phases",
        json={"project_id": project_id, "name": "Phase 1", "sequence": 1},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["project_id"] == project_id
    assert data["sequence"] == 1


def test_create_phase_invalid_project(client: TestClient):
    """POST /api/v1/phases with non-existent project_id should return 404."""
    response = client.post(
        "/api/v1/phases",
        json={"project_id": "no-such-project", "name": "Phase 1", "sequence": 1},
    )
    assert response.status_code == 404


def test_create_phase_duplicate_sequence(client: TestClient):
    """Duplicate sequence within the same project should return 409."""
    project_id = _create_project(client)
    client.post("/api/v1/phases", json={"project_id": project_id, "name": "Phase 1", "sequence": 1})
    response = client.post(
        "/api/v1/phases",
        json={"project_id": project_id, "name": "Phase 1 dup", "sequence": 1},
    )
    assert response.status_code == 409


def test_list_phases_filtered_by_project(client: TestClient):
    """GET /api/v1/phases?project_id=... should return only phases for that project."""
    p1 = _create_project(client, code="P1")
    p2 = _create_project(client, code="P2")
    client.post("/api/v1/phases", json={"project_id": p1, "name": "Phase 1", "sequence": 1})
    client.post("/api/v1/phases", json={"project_id": p2, "name": "Phase A", "sequence": 1})
    response = client.get(f"/api/v1/phases?project_id={p1}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["project_id"] == p1


def test_get_phase_not_found(client: TestClient):
    """GET /api/v1/phases/{id} with unknown id should return 404."""
    response = client.get("/api/v1/phases/no-such-phase")
    assert response.status_code == 404


def test_update_phase(client: TestClient):
    """PATCH /api/v1/phases/{id} should update the phase."""
    project_id = _create_project(client)
    create = client.post("/api/v1/phases", json={"project_id": project_id, "name": "Phase 1", "sequence": 1})
    phase_id = create.json()["id"]
    response = client.patch(f"/api/v1/phases/{phase_id}", json={"status": "active"})
    assert response.status_code == 200
    assert response.json()["status"] == "active"
