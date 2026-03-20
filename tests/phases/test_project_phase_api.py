"""
Tests for the project lifecycle phase API endpoints.

Validates:
  - GET  /api/v1/projects/{id}/lifecycle
  - POST /api/v1/phases/{id}/advance
  - POST /api/v1/phases/{id}/reopen
  - PATCH /api/v1/phases/{id} with phase_type field
"""

import pytest
from fastapi.testclient import TestClient


def _create_project(client: TestClient, code: str = "API-001") -> str:
    resp = client.post("/api/v1/projects", json={"name": "API Test Project", "code": code})
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_phase(
    client: TestClient,
    project_id: str,
    name: str,
    sequence: int,
    phase_type: str | None = None,
    status: str = "planned",
) -> dict:
    payload: dict = {"name": name, "sequence": sequence, "status": status}
    if phase_type:
        payload["phase_type"] = phase_type
    resp = client.post(f"/api/v1/projects/{project_id}/phases", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── GET /projects/{id}/lifecycle ────────────────────────────────────────────

def test_lifecycle_endpoint_returns_200_for_existing_project(client: TestClient):
    """GET /api/v1/projects/{id}/lifecycle must return 200 with lifecycle data."""
    project_id = _create_project(client, "API-LC-001")
    _create_phase(client, project_id, "Concept", 1, phase_type="concept")

    resp = client.get(f"/api/v1/projects/{project_id}/lifecycle")
    assert resp.status_code == 200
    data = resp.json()
    assert "project_id" in data
    assert "phases" in data
    assert "current_phase_type" in data
    assert "current_sequence" in data
    assert data["project_id"] == project_id


def test_lifecycle_endpoint_returns_404_for_missing_project(client: TestClient):
    """GET /api/v1/projects/{id}/lifecycle must return 404 for unknown project."""
    resp = client.get("/api/v1/projects/no-such-project/lifecycle")
    assert resp.status_code == 404


def test_lifecycle_endpoint_empty_project(client: TestClient):
    """GET lifecycle on a project with no phases must return empty phases list."""
    project_id = _create_project(client, "API-LC-002")
    resp = client.get(f"/api/v1/projects/{project_id}/lifecycle")
    assert resp.status_code == 200
    data = resp.json()
    assert data["phases"] == []
    assert data["current_phase_type"] is None
    assert data["current_sequence"] is None


def test_lifecycle_response_includes_is_current_field(client: TestClient):
    """Each phase item in the lifecycle response must include is_current field."""
    project_id = _create_project(client, "API-LC-003")
    _create_phase(client, project_id, "Concept", 1, phase_type="concept", status="active")

    resp = client.get(f"/api/v1/projects/{project_id}/lifecycle")
    assert resp.status_code == 200
    phases = resp.json()["phases"]
    assert len(phases) == 1
    assert "is_current" in phases[0]
    assert phases[0]["is_current"] is True


# ── POST /phases/{id}/advance ───────────────────────────────────────────────

def test_advance_endpoint_returns_200(client: TestClient):
    """POST /api/v1/phases/{id}/advance must return 200 with updated phase."""
    project_id = _create_project(client, "API-ADV-001")
    phase = _create_phase(client, project_id, "Concept", 1, phase_type="concept", status="active")

    resp = client.post(f"/api/v1/phases/{phase['id']}/advance")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == phase["id"]
    assert data["status"] == "completed"


def test_advance_endpoint_returns_404_for_missing_phase(client: TestClient):
    """POST /api/v1/phases/{id}/advance must return 404 for unknown phase."""
    resp = client.post("/api/v1/phases/no-such-phase/advance")
    assert resp.status_code == 404


def test_advance_endpoint_returns_422_for_planned_phase(client: TestClient):
    """POST /api/v1/phases/{id}/advance must return 422 for a planned phase."""
    project_id = _create_project(client, "API-ADV-002")
    phase = _create_phase(client, project_id, "Concept", 1, phase_type="concept")

    resp = client.post(f"/api/v1/phases/{phase['id']}/advance")
    assert resp.status_code == 422


def test_advance_activates_next_phase(client: TestClient):
    """POST /phases/{id}/advance must activate the next phase in sequence."""
    project_id = _create_project(client, "API-ADV-003")
    phase1 = _create_phase(client, project_id, "Concept", 1, phase_type="concept", status="active")
    phase2 = _create_phase(client, project_id, "Design", 2, phase_type="design")

    client.post(f"/api/v1/phases/{phase1['id']}/advance")

    get_resp = client.get(f"/api/v1/phases/{phase2['id']}")
    assert get_resp.json()["status"] == "active"


def test_advance_does_not_affect_other_phases_beyond_next(client: TestClient):
    """POST /phases/{id}/advance must not affect phases beyond the immediate next."""
    project_id = _create_project(client, "API-ADV-004")
    phase1 = _create_phase(client, project_id, "Concept", 1, phase_type="concept", status="active")
    _create_phase(client, project_id, "Design", 2, phase_type="design")
    phase3 = _create_phase(client, project_id, "Approvals", 3, phase_type="approvals")

    client.post(f"/api/v1/phases/{phase1['id']}/advance")

    get_resp = client.get(f"/api/v1/phases/{phase3['id']}")
    assert get_resp.json()["status"] == "planned"


# ── POST /phases/{id}/reopen ────────────────────────────────────────────────

def test_reopen_endpoint_returns_200(client: TestClient):
    """POST /api/v1/phases/{id}/reopen must return 200 with active status."""
    project_id = _create_project(client, "API-RO-001")
    phase = _create_phase(client, project_id, "Concept", 1, phase_type="concept", status="completed")

    resp = client.post(f"/api/v1/phases/{phase['id']}/reopen")
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


def test_reopen_endpoint_returns_404_for_missing_phase(client: TestClient):
    """POST /api/v1/phases/{id}/reopen must return 404 for unknown phase."""
    resp = client.post("/api/v1/phases/no-such-phase/reopen")
    assert resp.status_code == 404


def test_reopen_planned_phase_returns_422(client: TestClient):
    """POST /api/v1/phases/{id}/reopen on a planned phase must return 422."""
    project_id = _create_project(client, "API-RO-002")
    phase = _create_phase(client, project_id, "Concept", 1)

    resp = client.post(f"/api/v1/phases/{phase['id']}/reopen")
    assert resp.status_code == 422


def test_reopen_active_phase_returns_422(client: TestClient):
    """POST /api/v1/phases/{id}/reopen on an active phase must return 422."""
    project_id = _create_project(client, "API-RO-003")
    phase = _create_phase(client, project_id, "Concept", 1, status="active")

    resp = client.post(f"/api/v1/phases/{phase['id']}/reopen")
    assert resp.status_code == 422


# ── PATCH with phase_type ────────────────────────────────────────────────────

def test_patch_can_set_phase_type(client: TestClient):
    """PATCH /api/v1/phases/{id} must allow setting phase_type."""
    project_id = _create_project(client, "API-PT-001")
    phase = _create_phase(client, project_id, "Phase A", 1)
    assert phase["phase_type"] is None

    resp = client.patch(f"/api/v1/phases/{phase['id']}", json={"phase_type": "construction"})
    assert resp.status_code == 200
    assert resp.json()["phase_type"] == "construction"


def test_patch_can_update_phase_type(client: TestClient):
    """PATCH must allow updating an existing phase_type."""
    project_id = _create_project(client, "API-PT-002")
    phase = _create_phase(client, project_id, "Concept Phase", 1, phase_type="concept")

    resp = client.patch(f"/api/v1/phases/{phase['id']}", json={"phase_type": "design"})
    assert resp.status_code == 200
    assert resp.json()["phase_type"] == "design"


def test_patch_invalid_phase_type_rejected(client: TestClient):
    """PATCH with an invalid phase_type must be rejected with 422."""
    project_id = _create_project(client, "API-PT-003")
    phase = _create_phase(client, project_id, "Phase X", 1)

    resp = client.patch(f"/api/v1/phases/{phase['id']}", json={"phase_type": "invalid_type"})
    assert resp.status_code == 422
