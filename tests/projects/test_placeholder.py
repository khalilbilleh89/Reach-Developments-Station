"""
Tests for the projects module.

Validates create / list / get / update behaviour and uniqueness enforcement.
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

