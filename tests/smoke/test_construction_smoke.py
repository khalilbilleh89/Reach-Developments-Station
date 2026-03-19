"""
Smoke test: Construction

Verifies the construction workflow end-to-end:
  Project → Construction Scope → Milestone → Progress Update

Assertions:
  - Scope is attached to project
  - Milestone references the scope
  - Milestone progression is valid
  - Progress update references the milestone
"""

from fastapi.testclient import TestClient


# ── Helpers ──────────────────────────────────────────────────────────────────


def _create_project(client: TestClient, code: str = "SMKC-001") -> str:
    resp = client.post(
        "/api/v1/projects",
        json={"name": "Construction Smoke Project", "code": code},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_scope(client: TestClient, project_id: str, name: str = "Civil Works") -> dict:
    resp = client.post(
        "/api/v1/construction/scopes",
        json={"project_id": project_id, "name": name},
    )
    assert resp.status_code == 201
    return resp.json()


def _create_milestone(client: TestClient, scope_id: str) -> dict:
    resp = client.post(
        "/api/v1/construction/milestones",
        json={
            "scope_id": scope_id,
            "name": "Foundation Complete",
            "sequence": 1,
        },
    )
    assert resp.status_code == 201
    return resp.json()


def _add_progress_update(client: TestClient, milestone_id: str, percent: int) -> dict:
    resp = client.post(
        f"/api/v1/construction/milestones/{milestone_id}/progress-updates",
        json={"progress_percent": percent, "status_note": "On track"},
    )
    assert resp.status_code == 201
    return resp.json()


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_construction_scope_attached_to_project(client: TestClient):
    """Construction scope must reference the project it was created for."""
    project_id = _create_project(client, "SMKC-001")
    scope = _create_scope(client, project_id)

    assert scope["project_id"] == project_id


def test_construction_milestone_references_scope(client: TestClient):
    """Milestone must reference the scope it was created under."""
    project_id = _create_project(client, "SMKC-002")
    scope = _create_scope(client, project_id)
    milestone = _create_milestone(client, scope["id"])

    assert milestone["scope_id"] == scope["id"]


def test_construction_milestone_progression(client: TestClient):
    """Milestone status can be advanced from pending to in_progress to completed."""
    project_id = _create_project(client, "SMKC-003")
    scope = _create_scope(client, project_id)
    milestone = _create_milestone(client, scope["id"])

    assert milestone["status"] == "pending"

    # Advance to in_progress
    in_progress = client.patch(
        f"/api/v1/construction/milestones/{milestone['id']}",
        json={"status": "in_progress"},
    ).json()
    assert in_progress["status"] == "in_progress"

    # Advance to completed
    completed = client.patch(
        f"/api/v1/construction/milestones/{milestone['id']}",
        json={"status": "completed"},
    ).json()
    assert completed["status"] == "completed"


def test_construction_progress_update_references_milestone(client: TestClient):
    """Progress update must reference the milestone it was recorded for."""
    project_id = _create_project(client, "SMKC-004")
    scope = _create_scope(client, project_id)
    milestone = _create_milestone(client, scope["id"])
    update = _add_progress_update(client, milestone["id"], 50)

    assert update["milestone_id"] == milestone["id"]
    assert update["progress_percent"] == 50


def test_construction_full_workflow(client: TestClient):
    """Full workflow: project → scope → milestone → progress update."""
    project_id = _create_project(client, "SMKC-005")
    scope = _create_scope(client, project_id, "MEP Works")
    milestone = _create_milestone(client, scope["id"])
    update = _add_progress_update(client, milestone["id"], 25)

    # Verify the complete chain
    assert scope["project_id"] == project_id
    assert milestone["scope_id"] == scope["id"]
    assert update["milestone_id"] == milestone["id"]

    # Verify progress is retrievable
    updates_resp = client.get(
        f"/api/v1/construction/milestones/{milestone['id']}/progress-updates"
    )
    assert updates_resp.status_code == 200
    updates = updates_resp.json()
    assert updates["total"] >= 1
