"""
Tests for GET /api/v1/projects/{project_id}/summary.

Validates:
- summary counts phases correctly by status
- summary handles no phases
- summary returns correct timeline (earliest start, latest end)
- 404 for unknown project
"""

import pytest
from fastapi.testclient import TestClient


def _create_project(client: TestClient, code: str = "SUM-001") -> str:
    resp = client.post("/api/v1/projects", json={"name": "Summary Project", "code": code})
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_phase(
    client: TestClient,
    project_id: str,
    sequence: int,
    status: str = "planned",
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    payload: dict = {"project_id": project_id, "name": f"Phase {sequence}", "sequence": sequence, "status": status}
    if start_date:
        payload["start_date"] = start_date
    if end_date:
        payload["end_date"] = end_date
    resp = client.post("/api/v1/phases", json=payload)
    assert resp.status_code == 201
    return resp.json()


def test_summary_no_phases(client: TestClient):
    """Summary for a project with no phases should return all zeros and null dates."""
    project_id = _create_project(client)
    resp = client.get(f"/api/v1/projects/{project_id}/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == project_id
    assert data["total_phases"] == 0
    assert data["active_phases"] == 0
    assert data["planned_phases"] == 0
    assert data["completed_phases"] == 0
    assert data["earliest_start_date"] is None
    assert data["latest_target_completion"] is None


def test_summary_counts_phases_by_status(client: TestClient):
    """Summary counts planned, active and completed phases correctly."""
    project_id = _create_project(client, code="SUM-002")
    _create_phase(client, project_id, 1, status="planned")
    _create_phase(client, project_id, 2, status="active")
    _create_phase(client, project_id, 3, status="active")
    _create_phase(client, project_id, 4, status="completed")

    resp = client.get(f"/api/v1/projects/{project_id}/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_phases"] == 4
    assert data["planned_phases"] == 1
    assert data["active_phases"] == 2
    assert data["completed_phases"] == 1


def test_summary_returns_correct_timeline(client: TestClient):
    """Summary returns earliest start_date and latest end_date across phases."""
    project_id = _create_project(client, code="SUM-003")
    _create_phase(client, project_id, 1, start_date="2026-01-01", end_date="2026-06-30")
    _create_phase(client, project_id, 2, start_date="2025-07-01", end_date="2027-12-31")
    _create_phase(client, project_id, 3, start_date="2026-03-01")

    resp = client.get(f"/api/v1/projects/{project_id}/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["earliest_start_date"] == "2025-07-01"
    assert data["latest_target_completion"] == "2027-12-31"


def test_summary_timeline_null_when_no_dates(client: TestClient):
    """Summary returns null dates when phases have no date fields set."""
    project_id = _create_project(client, code="SUM-004")
    _create_phase(client, project_id, 1)
    _create_phase(client, project_id, 2)

    resp = client.get(f"/api/v1/projects/{project_id}/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["earliest_start_date"] is None
    assert data["latest_target_completion"] is None


def test_summary_not_found(client: TestClient):
    """GET /api/v1/projects/{id}/summary with unknown id should return 404."""
    resp = client.get("/api/v1/projects/does-not-exist/summary")
    assert resp.status_code == 404


def test_summary_schema_fields(client: TestClient):
    """Summary response contains all required schema fields."""
    project_id = _create_project(client, code="SUM-005")
    resp = client.get(f"/api/v1/projects/{project_id}/summary")
    assert resp.status_code == 200
    data = resp.json()
    required_fields = {
        "project_id",
        "total_phases",
        "active_phases",
        "planned_phases",
        "completed_phases",
        "earliest_start_date",
        "latest_target_completion",
    }
    assert required_fields.issubset(data.keys())
