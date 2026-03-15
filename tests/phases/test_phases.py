"""
Tests for the phases module.

Validates create / list / get / update / delete behaviour and hierarchy enforcement.
Covers both generic endpoints (/phases) and project-scoped endpoints (/projects/{id}/phases).
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


def test_create_phase_with_code_and_description(client: TestClient):
    """POST /api/v1/phases should persist code and description."""
    project_id = _create_project(client)
    response = client.post(
        "/api/v1/phases",
        json={
            "project_id": project_id,
            "name": "Phase Alpha",
            "code": "PH-A",
            "sequence": 1,
            "description": "First development phase.",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["code"] == "PH-A"
    assert data["description"] == "First development phase."


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


def test_create_phase_date_validation(client: TestClient):
    """Phase with end_date before start_date should be rejected."""
    project_id = _create_project(client)
    response = client.post(
        "/api/v1/phases",
        json={
            "project_id": project_id,
            "name": "Phase X",
            "sequence": 1,
            "start_date": "2025-06-01",
            "end_date": "2025-01-01",
        },
    )
    assert response.status_code == 422


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


def test_delete_phase(client: TestClient):
    """DELETE /api/v1/phases/{id} should remove the phase."""
    project_id = _create_project(client)
    create = client.post("/api/v1/phases", json={"project_id": project_id, "name": "Phase 1", "sequence": 1})
    phase_id = create.json()["id"]
    response = client.delete(f"/api/v1/phases/{phase_id}")
    assert response.status_code == 204
    # Verify it's gone
    get_resp = client.get(f"/api/v1/phases/{phase_id}")
    assert get_resp.status_code == 404


def test_delete_phase_not_found(client: TestClient):
    """DELETE /api/v1/phases/{id} with unknown id should return 404."""
    response = client.delete("/api/v1/phases/no-such-phase")
    assert response.status_code == 404


def test_list_phases_by_project_endpoint(client: TestClient):
    """GET /api/v1/projects/{id}/phases should list phases scoped to the project."""
    project_id = _create_project(client)
    client.post("/api/v1/phases", json={"project_id": project_id, "name": "Phase 1", "sequence": 1})
    client.post("/api/v1/phases", json={"project_id": project_id, "name": "Phase 2", "sequence": 2})
    response = client.get(f"/api/v1/projects/{project_id}/phases")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert all(item["project_id"] == project_id for item in data["items"])


def test_list_phases_by_project_not_found(client: TestClient):
    """GET /api/v1/projects/{id}/phases with unknown project should return 404."""
    response = client.get("/api/v1/projects/no-such-project/phases")
    assert response.status_code == 404


def test_create_phase_for_project_endpoint(client: TestClient):
    """POST /api/v1/projects/{id}/phases should create a phase scoped to the project."""
    project_id = _create_project(client)
    response = client.post(
        f"/api/v1/projects/{project_id}/phases",
        json={"name": "Phase Beta", "sequence": 1, "code": "PH-B"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["project_id"] == project_id
    assert data["name"] == "Phase Beta"
    assert data["code"] == "PH-B"


def test_create_phase_for_project_not_found(client: TestClient):
    """POST /api/v1/projects/{id}/phases with unknown project should return 404."""
    response = client.post(
        "/api/v1/projects/no-such-project/phases",
        json={"name": "Phase Beta", "sequence": 1},
    )
    assert response.status_code == 404
