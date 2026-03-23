"""
Tests for the Construction Progress & Variance API endpoints.

PR-CONSTR-041 — Construction Progress Tracking & Schedule Variance

Validates:
- POST /construction/milestones/{id}/progress — update milestone progress
- GET  /construction/scopes/{id}/progress    — scope progress overview
- GET  /construction/scopes/{id}/variance    — schedule variance

Error cases:
- 404 on unknown milestone / scope
- 422 on invalid progress payloads
"""

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _create_project(client: TestClient, code: str = "PV-001") -> str:
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
    client: TestClient,
    scope_id: str,
    sequence: int = 1,
    name: str = "Foundation",
    duration_days: int | None = 10,
) -> dict:
    body: dict = {"scope_id": scope_id, "name": name, "sequence": sequence}
    if duration_days is not None:
        body["duration_days"] = duration_days
    resp = client.post("/api/v1/construction/milestones", json=body)
    assert resp.status_code == 201
    return resp.json()


def _post_progress(
    client: TestClient,
    milestone_id: str,
    payload: dict,
) -> dict:
    resp = client.post(
        f"/api/v1/construction/milestones/{milestone_id}/progress",
        json=payload,
    )
    return resp


# ---------------------------------------------------------------------------
# POST /construction/milestones/{id}/progress
# ---------------------------------------------------------------------------


def test_update_progress_basic(client: TestClient) -> None:
    project_id = _create_project(client, "PV-010")
    scope = _create_scope(client, project_id)
    m = _create_milestone(client, scope["id"])

    resp = _post_progress(client, m["id"], {
        "progress_percent": 50.0,
        "actual_start_day": 2,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["progress_percent"] == 50.0
    assert data["actual_start_day"] == 2
    assert data["actual_finish_day"] is None
    assert data["last_progress_update_at"] is not None


def test_update_progress_to_complete(client: TestClient) -> None:
    project_id = _create_project(client, "PV-011")
    scope = _create_scope(client, project_id)
    m = _create_milestone(client, scope["id"])

    resp = _post_progress(client, m["id"], {
        "progress_percent": 100.0,
        "actual_start_day": 0,
        "actual_finish_day": 10,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["progress_percent"] == 100.0
    assert data["actual_start_day"] == 0
    assert data["actual_finish_day"] == 10


def test_update_progress_zero_percent_allowed(client: TestClient) -> None:
    project_id = _create_project(client, "PV-012")
    scope = _create_scope(client, project_id)
    m = _create_milestone(client, scope["id"])

    resp = _post_progress(client, m["id"], {"progress_percent": 0.0})
    assert resp.status_code == 200
    assert resp.json()["progress_percent"] == 0.0


def test_update_progress_idempotent_overwrite(client: TestClient) -> None:
    project_id = _create_project(client, "PV-013")
    scope = _create_scope(client, project_id)
    m = _create_milestone(client, scope["id"])

    _post_progress(client, m["id"], {"progress_percent": 30.0, "actual_start_day": 1})
    resp = _post_progress(client, m["id"], {"progress_percent": 70.0, "actual_start_day": 1})
    assert resp.status_code == 200
    assert resp.json()["progress_percent"] == 70.0


def test_update_progress_milestone_not_found(client: TestClient) -> None:
    resp = _post_progress(client, "non-existent-id", {"progress_percent": 0.0})
    assert resp.status_code == 404


def test_update_progress_over_100_rejected(client: TestClient) -> None:
    project_id = _create_project(client, "PV-014")
    scope = _create_scope(client, project_id)
    m = _create_milestone(client, scope["id"])

    resp = _post_progress(client, m["id"], {"progress_percent": 101.0})
    assert resp.status_code == 422


def test_update_progress_negative_rejected(client: TestClient) -> None:
    project_id = _create_project(client, "PV-015")
    scope = _create_scope(client, project_id)
    m = _create_milestone(client, scope["id"])

    resp = _post_progress(client, m["id"], {"progress_percent": -1.0})
    assert resp.status_code == 422


def test_update_progress_requires_actual_start_when_percent_gt_0(client: TestClient) -> None:
    project_id = _create_project(client, "PV-016")
    scope = _create_scope(client, project_id)
    m = _create_milestone(client, scope["id"])

    resp = _post_progress(client, m["id"], {"progress_percent": 50.0})
    assert resp.status_code == 422


def test_update_progress_finish_requires_100_percent(client: TestClient) -> None:
    project_id = _create_project(client, "PV-017")
    scope = _create_scope(client, project_id)
    m = _create_milestone(client, scope["id"])

    resp = _post_progress(client, m["id"], {
        "progress_percent": 80.0,
        "actual_start_day": 0,
        "actual_finish_day": 8,
    })
    assert resp.status_code == 422


def test_update_progress_finish_before_start_rejected(client: TestClient) -> None:
    project_id = _create_project(client, "PV-018")
    scope = _create_scope(client, project_id)
    m = _create_milestone(client, scope["id"])

    resp = _post_progress(client, m["id"], {
        "progress_percent": 100.0,
        "actual_start_day": 10,
        "actual_finish_day": 5,
    })
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /construction/scopes/{id}/progress
# ---------------------------------------------------------------------------


def test_scope_progress_empty_scope(client: TestClient) -> None:
    project_id = _create_project(client, "PV-020")
    scope = _create_scope(client, project_id)

    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/progress")
    assert resp.status_code == 200
    data = resp.json()
    assert data["scope_id"] == scope["id"]
    assert data["total_milestones"] == 0
    assert data["started_milestones"] == 0
    assert data["completed_milestones"] == 0
    assert data["overall_completion_percent"] == 0.0
    assert data["milestones"] == []


def test_scope_progress_no_progress_recorded(client: TestClient) -> None:
    project_id = _create_project(client, "PV-021")
    scope = _create_scope(client, project_id)
    _create_milestone(client, scope["id"], sequence=1)
    _create_milestone(client, scope["id"], sequence=2, name="Framing")

    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/progress")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_milestones"] == 2
    assert data["started_milestones"] == 0
    assert data["completed_milestones"] == 0
    assert data["overall_completion_percent"] == 0.0


def test_scope_progress_partial(client: TestClient) -> None:
    project_id = _create_project(client, "PV-022")
    scope = _create_scope(client, project_id)
    m1 = _create_milestone(client, scope["id"], sequence=1, name="M1")
    m2 = _create_milestone(client, scope["id"], sequence=2, name="M2")

    _post_progress(client, m1["id"], {"progress_percent": 50.0, "actual_start_day": 0})

    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/progress")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_milestones"] == 2
    assert data["started_milestones"] == 1
    assert data["completed_milestones"] == 0
    assert data["overall_completion_percent"] == 25.0  # (50 + 0) / 2


def test_scope_progress_all_completed(client: TestClient) -> None:
    project_id = _create_project(client, "PV-023")
    scope = _create_scope(client, project_id)
    m1 = _create_milestone(client, scope["id"], sequence=1, name="M1")
    m2 = _create_milestone(client, scope["id"], sequence=2, name="M2")

    for m in [m1, m2]:
        _post_progress(client, m["id"], {
            "progress_percent": 100.0,
            "actual_start_day": 0,
            "actual_finish_day": 10,
        })

    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/progress")
    assert resp.status_code == 200
    data = resp.json()
    assert data["completed_milestones"] == 2
    assert data["overall_completion_percent"] == 100.0


def test_scope_progress_response_shape(client: TestClient) -> None:
    project_id = _create_project(client, "PV-024")
    scope = _create_scope(client, project_id)
    m = _create_milestone(client, scope["id"])
    _post_progress(client, m["id"], {"progress_percent": 40.0, "actual_start_day": 1})

    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/progress")
    assert resp.status_code == 200
    data = resp.json()
    row = data["milestones"][0]
    assert "milestone_id" in row
    assert "milestone_name" in row
    assert "sequence" in row
    assert "progress_percent" in row
    assert "actual_start_day" in row
    assert "actual_finish_day" in row
    assert "last_progress_update_at" in row


def test_scope_progress_scope_not_found(client: TestClient) -> None:
    resp = client.get("/api/v1/construction/scopes/no-such-scope/progress")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /construction/scopes/{id}/variance
# ---------------------------------------------------------------------------


def test_scope_variance_empty_scope(client: TestClient) -> None:
    project_id = _create_project(client, "PV-030")
    scope = _create_scope(client, project_id)

    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/variance")
    assert resp.status_code == 200
    data = resp.json()
    assert data["scope_id"] == scope["id"]
    assert data["project_delay_days"] == 0
    assert data["critical_path_shift"] is False
    assert data["affected_milestones"] == []
    assert data["milestones"] == []


def test_scope_variance_no_progress_all_not_started(client: TestClient) -> None:
    project_id = _create_project(client, "PV-031")
    scope = _create_scope(client, project_id)
    _create_milestone(client, scope["id"], sequence=1, name="M1", duration_days=10)
    _create_milestone(client, scope["id"], sequence=2, name="M2", duration_days=5)

    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/variance")
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_delay_days"] == 0
    assert all(r["milestone_status"] == "not_started" for r in data["milestones"])


def test_scope_variance_on_time_start(client: TestClient) -> None:
    project_id = _create_project(client, "PV-032")
    scope = _create_scope(client, project_id)
    m = _create_milestone(client, scope["id"], sequence=1, duration_days=10)

    # Start on day 0 (CPM planned start = 0)
    _post_progress(client, m["id"], {"progress_percent": 30.0, "actual_start_day": 0})

    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/variance")
    assert resp.status_code == 200
    data = resp.json()
    row = data["milestones"][0]
    assert row["schedule_variance_days"] == 0
    assert row["milestone_status"] == "in_progress"
    assert data["project_delay_days"] == 0


def test_scope_variance_delayed_milestone(client: TestClient) -> None:
    project_id = _create_project(client, "PV-033")
    scope = _create_scope(client, project_id)
    m = _create_milestone(client, scope["id"], sequence=1, duration_days=10)

    # Start 5 days late (CPM planned start = 0)
    _post_progress(client, m["id"], {"progress_percent": 20.0, "actual_start_day": 5})

    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/variance")
    assert resp.status_code == 200
    data = resp.json()
    row = data["milestones"][0]
    assert row["schedule_variance_days"] == 5
    assert row["milestone_status"] == "delayed"
    assert data["project_delay_days"] == 5
    assert data["critical_path_shift"] is True


def test_scope_variance_completed_milestone(client: TestClient) -> None:
    project_id = _create_project(client, "PV-034")
    scope = _create_scope(client, project_id)
    m = _create_milestone(client, scope["id"], sequence=1, duration_days=10)

    _post_progress(client, m["id"], {
        "progress_percent": 100.0,
        "actual_start_day": 0,
        "actual_finish_day": 10,
    })

    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/variance")
    assert resp.status_code == 200
    data = resp.json()
    row = data["milestones"][0]
    assert row["milestone_status"] == "completed"
    assert row["completion_variance_days"] == 0


def test_scope_variance_response_shape(client: TestClient) -> None:
    project_id = _create_project(client, "PV-035")
    scope = _create_scope(client, project_id)
    _create_milestone(client, scope["id"], sequence=1)

    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/variance")
    assert resp.status_code == 200
    data = resp.json()
    assert "scope_id" in data
    assert "project_delay_days" in data
    assert "critical_path_shift" in data
    assert "affected_milestones" in data
    assert "milestones" in data
    row = data["milestones"][0]
    assert "milestone_id" in row
    assert "milestone_name" in row
    assert "planned_start" in row
    assert "planned_finish" in row
    assert "schedule_variance_days" in row
    assert "completion_variance_days" in row
    assert "milestone_status" in row
    assert "is_critical" in row
    assert "risk_exposed" in row


def test_scope_variance_scope_not_found(client: TestClient) -> None:
    resp = client.get("/api/v1/construction/scopes/no-such-scope/variance")
    assert resp.status_code == 404


def test_scope_variance_delay_propagation_to_downstream(client: TestClient) -> None:
    """A delayed first milestone should mark subsequent linked milestones as risk-exposed."""
    project_id = _create_project(client, "PV-036")
    scope = _create_scope(client, project_id)
    m1 = _create_milestone(client, scope["id"], sequence=1, name="M1", duration_days=10)
    m2 = _create_milestone(client, scope["id"], sequence=2, name="M2", duration_days=10)

    # Create dependency M1 → M2
    client.post(
        "/api/v1/construction/dependencies",
        json={"predecessor_id": m1["id"], "successor_id": m2["id"]},
    )

    # Delay M1 (CPM planned start=0, actual start=3)
    _post_progress(client, m1["id"], {"progress_percent": 20.0, "actual_start_day": 3})

    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/variance")
    assert resp.status_code == 200
    data = resp.json()

    rows = {r["milestone_id"]: r for r in data["milestones"]}
    assert rows[m1["id"]]["milestone_status"] == "delayed"
    assert rows[m2["id"]]["risk_exposed"] is True
    assert m2["id"] in data["affected_milestones"]
    assert data["project_delay_days"] == 3
