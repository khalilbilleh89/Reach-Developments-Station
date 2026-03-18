"""
Tests for Construction Progress Update lifecycle.

Validates:
  • progress update CRUD lifecycle (create, list, get, delete)
  • progress_percent validation (0–100 inclusive)
  • optional fields (status_note, reported_by, reported_at)
  • milestone isolation (updates do not bleed across milestones)
  • cascade delete from milestone
  • cascade delete from scope (via milestone)
  • 404 for unknown milestone / update IDs
"""

from fastapi.testclient import TestClient


# ── Helper factories ─────────────────────────────────────────────────────────


def _create_project(client: TestClient, code: str = "PU-001") -> str:
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


def _create_milestone(
    client: TestClient, scope_id: str, sequence: int = 1, name: str = "Foundation"
) -> dict:
    resp = client.post(
        "/api/v1/construction/milestones",
        json={"scope_id": scope_id, "name": name, "sequence": sequence},
    )
    assert resp.status_code == 201
    return resp.json()


def _create_progress_update(
    client: TestClient,
    milestone_id: str,
    progress_percent: int = 25,
    **kwargs,
) -> dict:
    payload = {"progress_percent": progress_percent, **kwargs}
    resp = client.post(
        f"/api/v1/construction/milestones/{milestone_id}/progress-updates",
        json=payload,
    )
    assert resp.status_code == 201
    return resp.json()


# ── CRUD lifecycle ───────────────────────────────────────────────────────────


def test_create_progress_update_minimal(client: TestClient):
    """Create a progress update with only the required field."""
    project_id = _create_project(client, "PU-010")
    scope = _create_scope(client, project_id)
    milestone = _create_milestone(client, scope["id"])

    update = _create_progress_update(client, milestone["id"], progress_percent=40)
    assert update["milestone_id"] == milestone["id"]
    assert update["progress_percent"] == 40
    assert update["status_note"] is None
    assert update["reported_by"] is None
    assert "reported_at" in update
    assert "id" in update


def test_create_progress_update_all_fields(client: TestClient):
    """Create a progress update with all optional fields populated."""
    project_id = _create_project(client, "PU-011")
    scope = _create_scope(client, project_id)
    milestone = _create_milestone(client, scope["id"])

    update = _create_progress_update(
        client,
        milestone["id"],
        progress_percent=75,
        status_note="Concrete pour completed on grid A.",
        reported_by="site_engineer@example.com",
        reported_at="2026-03-15T09:00:00+00:00",
    )
    assert update["progress_percent"] == 75
    assert update["status_note"] == "Concrete pour completed on grid A."
    assert update["reported_by"] == "site_engineer@example.com"
    assert "2026-03-15" in update["reported_at"]


def test_list_progress_updates(client: TestClient):
    """List returns all updates for the milestone in reported_at order."""
    project_id = _create_project(client, "PU-020")
    scope = _create_scope(client, project_id)
    milestone = _create_milestone(client, scope["id"])

    _create_progress_update(client, milestone["id"], progress_percent=10)
    _create_progress_update(client, milestone["id"], progress_percent=50)
    _create_progress_update(client, milestone["id"], progress_percent=90)

    resp = client.get(f"/api/v1/construction/milestones/{milestone['id']}/progress-updates")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3


def test_get_progress_update_by_id(client: TestClient):
    """GET by ID returns the correct record."""
    project_id = _create_project(client, "PU-030")
    scope = _create_scope(client, project_id)
    milestone = _create_milestone(client, scope["id"])

    created = _create_progress_update(client, milestone["id"], progress_percent=60)

    resp = client.get(f"/api/v1/construction/progress-updates/{created['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == created["id"]
    assert data["progress_percent"] == 60


def test_delete_progress_update(client: TestClient):
    """Delete removes the update; subsequent GET returns 404."""
    project_id = _create_project(client, "PU-040")
    scope = _create_scope(client, project_id)
    milestone = _create_milestone(client, scope["id"])

    update = _create_progress_update(client, milestone["id"], progress_percent=30)

    del_resp = client.delete(f"/api/v1/construction/progress-updates/{update['id']}")
    assert del_resp.status_code == 204

    get_resp = client.get(f"/api/v1/construction/progress-updates/{update['id']}")
    assert get_resp.status_code == 404


# ── Validation ───────────────────────────────────────────────────────────────


def test_progress_percent_zero_accepted(client: TestClient):
    """0 is a valid progress_percent value."""
    project_id = _create_project(client, "PU-050")
    scope = _create_scope(client, project_id)
    milestone = _create_milestone(client, scope["id"])

    update = _create_progress_update(client, milestone["id"], progress_percent=0)
    assert update["progress_percent"] == 0


def test_progress_percent_100_accepted(client: TestClient):
    """100 is a valid progress_percent value."""
    project_id = _create_project(client, "PU-051")
    scope = _create_scope(client, project_id)
    milestone = _create_milestone(client, scope["id"])

    update = _create_progress_update(client, milestone["id"], progress_percent=100)
    assert update["progress_percent"] == 100


def test_progress_percent_below_zero_rejected(client: TestClient):
    """progress_percent < 0 must be rejected with 422."""
    project_id = _create_project(client, "PU-052")
    scope = _create_scope(client, project_id)
    milestone = _create_milestone(client, scope["id"])

    resp = client.post(
        f"/api/v1/construction/milestones/{milestone['id']}/progress-updates",
        json={"progress_percent": -1},
    )
    assert resp.status_code == 422


def test_progress_percent_above_100_rejected(client: TestClient):
    """progress_percent > 100 must be rejected with 422."""
    project_id = _create_project(client, "PU-053")
    scope = _create_scope(client, project_id)
    milestone = _create_milestone(client, scope["id"])

    resp = client.post(
        f"/api/v1/construction/milestones/{milestone['id']}/progress-updates",
        json={"progress_percent": 101},
    )
    assert resp.status_code == 422


def test_create_progress_update_unknown_milestone_returns_404(client: TestClient):
    """Creating a progress update for a non-existent milestone returns 404."""
    resp = client.post(
        "/api/v1/construction/milestones/non-existent/progress-updates",
        json={"progress_percent": 50},
    )
    assert resp.status_code == 404


def test_list_progress_updates_unknown_milestone_returns_404(client: TestClient):
    """Listing updates for a non-existent milestone returns 404."""
    resp = client.get("/api/v1/construction/milestones/non-existent/progress-updates")
    assert resp.status_code == 404


def test_get_progress_update_not_found(client: TestClient):
    """GET for a non-existent update ID returns 404."""
    resp = client.get("/api/v1/construction/progress-updates/does-not-exist")
    assert resp.status_code == 404


def test_delete_progress_update_not_found(client: TestClient):
    """DELETE for a non-existent update ID returns 404."""
    resp = client.delete("/api/v1/construction/progress-updates/does-not-exist")
    assert resp.status_code == 404


# ── Isolation ────────────────────────────────────────────────────────────────


def test_progress_updates_isolated_per_milestone(client: TestClient):
    """Updates created for milestone A must not appear in milestone B."""
    project_id = _create_project(client, "PU-060")
    scope = _create_scope(client, project_id)
    m1 = _create_milestone(client, scope["id"], sequence=1, name="Milestone 1")
    m2 = _create_milestone(client, scope["id"], sequence=2, name="Milestone 2")

    _create_progress_update(client, m1["id"], progress_percent=20)
    _create_progress_update(client, m2["id"], progress_percent=80)

    resp_m1 = client.get(f"/api/v1/construction/milestones/{m1['id']}/progress-updates")
    assert resp_m1.json()["total"] == 1
    assert resp_m1.json()["items"][0]["milestone_id"] == m1["id"]

    resp_m2 = client.get(f"/api/v1/construction/milestones/{m2['id']}/progress-updates")
    assert resp_m2.json()["total"] == 1
    assert resp_m2.json()["items"][0]["milestone_id"] == m2["id"]


# ── Cascade delete ───────────────────────────────────────────────────────────


def test_cascade_delete_milestone_removes_progress_updates(client: TestClient):
    """Deleting a milestone must cascade-delete its progress updates."""
    project_id = _create_project(client, "PU-070")
    scope = _create_scope(client, project_id)
    milestone = _create_milestone(client, scope["id"])
    update = _create_progress_update(client, milestone["id"], progress_percent=55)

    del_resp = client.delete(f"/api/v1/construction/milestones/{milestone['id']}")
    assert del_resp.status_code == 204

    get_resp = client.get(f"/api/v1/construction/progress-updates/{update['id']}")
    assert get_resp.status_code == 404


def test_cascade_delete_scope_removes_progress_updates(client: TestClient):
    """Deleting a scope must cascade to milestones and their progress updates."""
    project_id = _create_project(client, "PU-071")
    scope = _create_scope(client, project_id)
    milestone = _create_milestone(client, scope["id"])
    update = _create_progress_update(client, milestone["id"], progress_percent=70)

    del_resp = client.delete(f"/api/v1/construction/scopes/{scope['id']}")
    assert del_resp.status_code == 204

    get_resp = client.get(f"/api/v1/construction/progress-updates/{update['id']}")
    assert get_resp.status_code == 404
