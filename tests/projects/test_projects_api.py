"""
Tests for the projects module.

Validates create / list / get / update behaviour, new production fields,
uniqueness enforcement, and list filtering.
"""

import pytest
from fastapi.testclient import TestClient


def test_create_project(client: TestClient):
    """POST /api/v1/projects should create and return a project."""
    response = client.post(
        "/api/v1/projects",
        json={"name": "Marina Bay", "code": "MB-001", "status": "pipeline"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Marina Bay"
    assert data["code"] == "MB-001"
    assert data["status"] == "pipeline"
    assert "id" in data


def test_create_project_with_all_fields(client: TestClient):
    """POST /api/v1/projects should persist all production-grade fields."""
    payload = {
        "name": "Sunrise Tower",
        "code": "SRT-001",
        "developer_name": "Reach Developments",
        "location": "Dubai Marina, Dubai, UAE",
        "start_date": "2026-01-01",
        "target_end_date": "2028-12-31",
        "status": "active",
        "description": "Luxury waterfront development.",
    }
    response = client.post("/api/v1/projects", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["developer_name"] == "Reach Developments"
    assert data["location"] == "Dubai Marina, Dubai, UAE"
    assert data["start_date"] == "2026-01-01"
    assert data["target_end_date"] == "2028-12-31"
    assert data["description"] == "Luxury waterfront development."


def test_create_project_date_validation(client: TestClient):
    """POST /api/v1/projects should reject target_end_date before start_date."""
    payload = {
        "name": "Bad Dates",
        "code": "BD-001",
        "start_date": "2028-01-01",
        "target_end_date": "2027-01-01",
    }
    response = client.post("/api/v1/projects", json=payload)
    assert response.status_code == 422


def test_create_project_duplicate_code(client: TestClient):
    """POST /api/v1/projects with duplicate code should return 409."""
    client.post("/api/v1/projects", json={"name": "Marina Bay", "code": "MB-001"})
    response = client.post("/api/v1/projects", json={"name": "Other", "code": "MB-001"})
    assert response.status_code == 409


def test_list_projects(client: TestClient):
    """GET /api/v1/projects should return all projects."""
    client.post("/api/v1/projects", json={"name": "Project A", "code": "PA-001"})
    client.post("/api/v1/projects", json={"name": "Project B", "code": "PB-001"})
    response = client.get("/api/v1/projects")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_list_projects_filter_by_status(client: TestClient):
    """GET /api/v1/projects?status= should filter by status."""
    client.post("/api/v1/projects", json={"name": "Active", "code": "ACT-001", "status": "active"})
    client.post("/api/v1/projects", json={"name": "Pipeline", "code": "PIP-001", "status": "pipeline"})
    response = client.get("/api/v1/projects?status=active")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["status"] == "active"


def test_list_projects_search(client: TestClient):
    """GET /api/v1/projects?search= should filter by name or code."""
    client.post("/api/v1/projects", json={"name": "Marina Bay", "code": "MB-001"})
    client.post("/api/v1/projects", json={"name": "Palm Heights", "code": "PH-001"})
    response = client.get("/api/v1/projects?search=marina")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "Marina Bay"


def test_get_project(client: TestClient):
    """GET /api/v1/projects/{id} should return the project."""
    create = client.post("/api/v1/projects", json={"name": "Marina Bay", "code": "MB-002"})
    project_id = create.json()["id"]
    response = client.get(f"/api/v1/projects/{project_id}")
    assert response.status_code == 200
    assert response.json()["id"] == project_id


def test_get_project_not_found(client: TestClient):
    """GET /api/v1/projects/{id} with unknown id should return 404."""
    response = client.get("/api/v1/projects/does-not-exist")
    assert response.status_code == 404


def test_update_project(client: TestClient):
    """PATCH /api/v1/projects/{id} should update the project."""
    create = client.post("/api/v1/projects", json={"name": "Marina Bay", "code": "MB-003"})
    project_id = create.json()["id"]
    response = client.patch(f"/api/v1/projects/{project_id}", json={"status": "active"})
    assert response.status_code == 200
    assert response.json()["status"] == "active"


def test_update_project_new_fields(client: TestClient):
    """PATCH /api/v1/projects/{id} should update developer_name and dates."""
    create = client.post("/api/v1/projects", json={"name": "Test Project", "code": "TP-001"})
    project_id = create.json()["id"]
    response = client.patch(
        f"/api/v1/projects/{project_id}",
        json={
            "developer_name": "Reach Developments",
            "start_date": "2026-06-01",
            "target_end_date": "2029-06-01",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["developer_name"] == "Reach Developments"
    assert data["start_date"] == "2026-06-01"
    assert data["target_end_date"] == "2029-06-01"


def test_archive_project(client: TestClient):
    """POST /api/v1/projects/{id}/archive should set status to on_hold."""
    create = client.post("/api/v1/projects", json={"name": "Marina Bay", "code": "MB-004", "status": "active"})
    project_id = create.json()["id"]
    response = client.post(f"/api/v1/projects/{project_id}/archive")
    assert response.status_code == 200
    assert response.json()["status"] == "on_hold"


def test_archive_project_already_archived(client: TestClient):
    """POST /api/v1/projects/{id}/archive on already-archived project should return 409."""
    create = client.post("/api/v1/projects", json={"name": "Marina Bay", "code": "MB-005", "status": "on_hold"})
    project_id = create.json()["id"]
    response = client.post(f"/api/v1/projects/{project_id}/archive")
    assert response.status_code == 409


def test_archive_project_not_found(client: TestClient):
    """POST /api/v1/projects/{id}/archive with unknown id should return 404."""
    response = client.post("/api/v1/projects/does-not-exist/archive")
    assert response.status_code == 404



def test_update_project_partial_date_cross_field_validation(client: TestClient):
    """PATCH with only target_end_date earlier than existing start_date should return 422."""
    create = client.post(
        "/api/v1/projects",
        json={"name": "Date Test", "code": "DT-001", "start_date": "2027-01-01"},
    )
    project_id = create.json()["id"]
    # Patch only target_end_date to a date before persisted start_date
    response = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"target_end_date": "2026-01-01"},
    )
    assert response.status_code == 422


def test_update_project_partial_date_valid(client: TestClient):
    """PATCH with only target_end_date after existing start_date should succeed."""
    create = client.post(
        "/api/v1/projects",
        json={"name": "Date Test 2", "code": "DT-002", "start_date": "2027-01-01"},
    )
    project_id = create.json()["id"]
    response = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"target_end_date": "2029-06-01"},
    )
    assert response.status_code == 200
    assert response.json()["target_end_date"] == "2029-06-01"


def test_list_projects_invalid_status_returns_422(client: TestClient):
    """GET /api/v1/projects?status=invalid should return 422 (enum validation)."""
    response = client.get("/api/v1/projects?status=invalid_status")
    assert response.status_code == 422


def test_delete_project_no_dependencies(client: TestClient):
    """DELETE /api/v1/projects/{id} should remove the project and return 204."""
    create = client.post("/api/v1/projects", json={"name": "Delete Me", "code": "DEL-001"})
    project_id = create.json()["id"]
    response = client.delete(f"/api/v1/projects/{project_id}")
    assert response.status_code == 204
    # Confirm it is gone
    get_response = client.get(f"/api/v1/projects/{project_id}")
    assert get_response.status_code == 404


def test_delete_project_not_found(client: TestClient):
    """DELETE /api/v1/projects/{id} with unknown id should return 404."""
    response = client.delete("/api/v1/projects/does-not-exist")
    assert response.status_code == 404


def test_delete_project_with_phases_returns_409(client: TestClient):
    """DELETE /api/v1/projects/{id} should return 409 when the project has phases."""
    create = client.post("/api/v1/projects", json={"name": "Has Phases", "code": "HP-001"})
    project_id = create.json()["id"]
    # Add a phase so the project has dependent phase records
    client.post(
        f"/api/v1/projects/{project_id}/phases",
        json={"name": "Phase 1", "code": "HP-001-P1", "sequence": 1},
    )
    response = client.delete(f"/api/v1/projects/{project_id}")
    assert response.status_code == 409
    assert "dependent phase records" in response.json()["message"]
