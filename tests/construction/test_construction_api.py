"""
Tests for the construction module API.

Validates scopes and milestones CRUD, link validation, uniqueness enforcement,
and cascade behaviour.
"""

import pytest
from fastapi.testclient import TestClient


# ── Helper factories ─────────────────────────────────────────────────────────

def _create_project(client: TestClient, code: str = "PRJ-001") -> str:
    resp = client.post("/api/v1/projects", json={"name": f"Project {code}", "code": code})
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_scope(client: TestClient, project_id: str, name: str = "Civil Works") -> dict:
    resp = client.post(
        "/api/v1/construction/scopes",
        json={"project_id": project_id, "name": name},
    )
    assert resp.status_code == 201
    return resp.json()


def _create_milestone(client: TestClient, scope_id: str, sequence: int = 1, name: str = "Foundation") -> dict:
    resp = client.post(
        "/api/v1/construction/milestones",
        json={"scope_id": scope_id, "name": name, "sequence": sequence},
    )
    assert resp.status_code == 201
    return resp.json()


# ── Scope creation ───────────────────────────────────────────────────────────

def test_create_scope_with_project(client: TestClient):
    project_id = _create_project(client, "PRJ-001")
    resp = client.post(
        "/api/v1/construction/scopes",
        json={"project_id": project_id, "name": "Civil Works", "status": "planned"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["project_id"] == project_id
    assert data["name"] == "Civil Works"
    assert data["status"] == "planned"
    assert "id" in data


def test_create_scope_requires_at_least_one_link(client: TestClient):
    resp = client.post(
        "/api/v1/construction/scopes",
        json={"name": "Orphan Scope"},
    )
    assert resp.status_code == 422


def test_create_scope_duplicate_link_returns_409(client: TestClient):
    project_id = _create_project(client, "PRJ-002")
    client.post("/api/v1/construction/scopes", json={"project_id": project_id, "name": "Scope A"})
    resp = client.post("/api/v1/construction/scopes", json={"project_id": project_id, "name": "Scope B"})
    assert resp.status_code == 409


def test_create_scope_invalid_project_returns_404(client: TestClient):
    resp = client.post(
        "/api/v1/construction/scopes",
        json={"project_id": "non-existent", "name": "Scope"},
    )
    assert resp.status_code == 404


def test_create_scope_with_dates(client: TestClient):
    project_id = _create_project(client, "PRJ-003")
    resp = client.post(
        "/api/v1/construction/scopes",
        json={
            "project_id": project_id,
            "name": "Scoped with Dates",
            "start_date": "2026-01-01",
            "target_end_date": "2027-06-30",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["start_date"] == "2026-01-01"
    assert data["target_end_date"] == "2027-06-30"


# ── Scope listing ────────────────────────────────────────────────────────────

def test_list_scopes(client: TestClient):
    project_id = _create_project(client, "PRJ-004")
    _create_scope(client, project_id, "Scope A")
    resp = client.get("/api/v1/construction/scopes")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1


def test_list_scopes_filter_by_project(client: TestClient):
    p1 = _create_project(client, "PRJ-005")
    p2 = _create_project(client, "PRJ-006")
    _create_scope(client, p1, "Scope P1")
    _create_scope(client, p2, "Scope P2")
    resp = client.get(f"/api/v1/construction/scopes?project_id={p1}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["project_id"] == p1


# ── Scope get / update / delete ──────────────────────────────────────────────

def test_get_scope(client: TestClient):
    project_id = _create_project(client, "PRJ-007")
    scope = _create_scope(client, project_id)
    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == scope["id"]


def test_get_scope_not_found(client: TestClient):
    resp = client.get("/api/v1/construction/scopes/does-not-exist")
    assert resp.status_code == 404


def test_update_scope(client: TestClient):
    project_id = _create_project(client, "PRJ-008")
    scope = _create_scope(client, project_id)
    resp = client.patch(
        f"/api/v1/construction/scopes/{scope['id']}",
        json={"status": "in_progress"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"


def test_delete_scope(client: TestClient):
    project_id = _create_project(client, "PRJ-009")
    scope = _create_scope(client, project_id)
    resp = client.delete(f"/api/v1/construction/scopes/{scope['id']}")
    assert resp.status_code == 204
    # Confirm gone
    assert client.get(f"/api/v1/construction/scopes/{scope['id']}").status_code == 404


def test_delete_scope_not_found(client: TestClient):
    resp = client.delete("/api/v1/construction/scopes/does-not-exist")
    assert resp.status_code == 404


# ── Milestone creation ───────────────────────────────────────────────────────

def test_create_milestone(client: TestClient):
    project_id = _create_project(client, "PRJ-010")
    scope = _create_scope(client, project_id)
    resp = client.post(
        "/api/v1/construction/milestones",
        json={"scope_id": scope["id"], "name": "Foundation", "sequence": 1},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["scope_id"] == scope["id"]
    assert data["name"] == "Foundation"
    assert data["sequence"] == 1
    assert data["status"] == "pending"
    assert "id" in data


def test_create_milestone_invalid_scope_returns_404(client: TestClient):
    resp = client.post(
        "/api/v1/construction/milestones",
        json={"scope_id": "non-existent", "name": "Foundation", "sequence": 1},
    )
    assert resp.status_code == 404


def test_create_milestone_duplicate_sequence_returns_409(client: TestClient):
    project_id = _create_project(client, "PRJ-011")
    scope = _create_scope(client, project_id)
    _create_milestone(client, scope["id"], sequence=1)
    resp = client.post(
        "/api/v1/construction/milestones",
        json={"scope_id": scope["id"], "name": "Duplicate", "sequence": 1},
    )
    assert resp.status_code == 409


def test_create_milestone_with_dates(client: TestClient):
    project_id = _create_project(client, "PRJ-012")
    scope = _create_scope(client, project_id)
    resp = client.post(
        "/api/v1/construction/milestones",
        json={
            "scope_id": scope["id"],
            "name": "Roof",
            "sequence": 2,
            "target_date": "2026-06-01",
            "completion_date": "2026-06-15",
            "notes": "Ahead of schedule.",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["target_date"] == "2026-06-01"
    assert data["completion_date"] == "2026-06-15"
    assert data["notes"] == "Ahead of schedule."


# ── Milestone listing ────────────────────────────────────────────────────────

def test_list_milestones(client: TestClient):
    project_id = _create_project(client, "PRJ-013")
    scope = _create_scope(client, project_id)
    _create_milestone(client, scope["id"], sequence=1, name="Foundation")
    _create_milestone(client, scope["id"], sequence=2, name="Structure")
    resp = client.get("/api/v1/construction/milestones")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


def test_list_milestones_filter_by_scope(client: TestClient):
    p1 = _create_project(client, "PRJ-014")
    p2 = _create_project(client, "PRJ-015")
    s1 = _create_scope(client, p1)
    s2 = _create_scope(client, p2)
    _create_milestone(client, s1["id"], sequence=1, name="M1")
    _create_milestone(client, s2["id"], sequence=1, name="M2")
    resp = client.get(f"/api/v1/construction/milestones?scope_id={s1['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["scope_id"] == s1["id"]


def test_list_milestones_ordered_by_sequence(client: TestClient):
    project_id = _create_project(client, "PRJ-016")
    scope = _create_scope(client, project_id)
    _create_milestone(client, scope["id"], sequence=3, name="Finishing")
    _create_milestone(client, scope["id"], sequence=1, name="Foundation")
    _create_milestone(client, scope["id"], sequence=2, name="Structure")
    resp = client.get(f"/api/v1/construction/milestones?scope_id={scope['id']}")
    assert resp.status_code == 200
    sequences = [item["sequence"] for item in resp.json()["items"]]
    assert sequences == [1, 2, 3]


# ── Milestone get / update / delete ─────────────────────────────────────────

def test_get_milestone(client: TestClient):
    project_id = _create_project(client, "PRJ-017")
    scope = _create_scope(client, project_id)
    m = _create_milestone(client, scope["id"])
    resp = client.get(f"/api/v1/construction/milestones/{m['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == m["id"]


def test_get_milestone_not_found(client: TestClient):
    resp = client.get("/api/v1/construction/milestones/does-not-exist")
    assert resp.status_code == 404


def test_update_milestone_status(client: TestClient):
    project_id = _create_project(client, "PRJ-018")
    scope = _create_scope(client, project_id)
    m = _create_milestone(client, scope["id"])
    resp = client.patch(
        f"/api/v1/construction/milestones/{m['id']}",
        json={"status": "completed", "completion_date": "2026-04-01"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["completion_date"] == "2026-04-01"


def test_update_milestone_sequence_conflict_returns_409(client: TestClient):
    project_id = _create_project(client, "PRJ-019")
    scope = _create_scope(client, project_id)
    m1 = _create_milestone(client, scope["id"], sequence=1)
    m2 = _create_milestone(client, scope["id"], sequence=2, name="Structure")
    resp = client.patch(f"/api/v1/construction/milestones/{m2['id']}", json={"sequence": 1})
    assert resp.status_code == 409


def test_delete_milestone(client: TestClient):
    project_id = _create_project(client, "PRJ-020")
    scope = _create_scope(client, project_id)
    m = _create_milestone(client, scope["id"])
    resp = client.delete(f"/api/v1/construction/milestones/{m['id']}")
    assert resp.status_code == 204
    assert client.get(f"/api/v1/construction/milestones/{m['id']}").status_code == 404


def test_delete_milestone_not_found(client: TestClient):
    resp = client.delete("/api/v1/construction/milestones/does-not-exist")
    assert resp.status_code == 404


# ── Cascade delete ───────────────────────────────────────────────────────────

def test_delete_scope_cascades_milestones(client: TestClient):
    project_id = _create_project(client, "PRJ-021")
    scope = _create_scope(client, project_id)
    m = _create_milestone(client, scope["id"])
    client.delete(f"/api/v1/construction/scopes/{scope['id']}")
    # Milestone should be gone too (cascade)
    resp = client.get(f"/api/v1/construction/milestones/{m['id']}")
    assert resp.status_code == 404
