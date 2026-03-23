"""
Tests for the Construction Schedule API endpoints.

Validates:
- POST /construction/dependencies — create dependency
- GET  /construction/scopes/{scope_id}/dependencies — list dependencies
- GET  /construction/dependencies/{dependency_id} — get dependency
- DELETE /construction/dependencies/{dependency_id} — delete dependency

- GET  /construction/scopes/{scope_id}/schedule — compute schedule
- POST /construction/scopes/{scope_id}/schedule/recompute — recompute schedule
- GET  /construction/scopes/{scope_id}/critical-path — critical path summary

- Validates 404 / 409 / 422 error responses
- Validates critical path response shape
- Validates duration_days field on milestone create/response
"""

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _create_project(client: TestClient, code: str = "SCHED-001") -> str:
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
    duration_days: int | None = None,
) -> dict:
    body: dict = {"scope_id": scope_id, "name": name, "sequence": sequence}
    if duration_days is not None:
        body["duration_days"] = duration_days
    resp = client.post("/api/v1/construction/milestones", json=body)
    assert resp.status_code == 201
    return resp.json()


def _create_dependency(
    client: TestClient,
    predecessor_id: str,
    successor_id: str,
    lag_days: int = 0,
) -> dict:
    resp = client.post(
        "/api/v1/construction/dependencies",
        json={
            "predecessor_id": predecessor_id,
            "successor_id": successor_id,
            "lag_days": lag_days,
        },
    )
    return resp.json() if resp.status_code == 201 else resp


# ---------------------------------------------------------------------------
# duration_days on milestones
# ---------------------------------------------------------------------------


def test_milestone_create_with_duration_days(client: TestClient) -> None:
    project_id = _create_project(client, "DUR-001")
    scope = _create_scope(client, project_id)
    m = _create_milestone(client, scope["id"], duration_days=14)
    assert m["duration_days"] == 14


def test_milestone_create_without_duration_days_returns_null(client: TestClient) -> None:
    project_id = _create_project(client, "DUR-002")
    scope = _create_scope(client, project_id)
    m = _create_milestone(client, scope["id"])
    assert m["duration_days"] is None


def test_milestone_update_duration_days(client: TestClient) -> None:
    project_id = _create_project(client, "DUR-003")
    scope = _create_scope(client, project_id)
    m = _create_milestone(client, scope["id"])
    resp = client.patch(
        f"/api/v1/construction/milestones/{m['id']}",
        json={"duration_days": 7},
    )
    assert resp.status_code == 200
    assert resp.json()["duration_days"] == 7


def test_milestone_duration_days_negative_rejected(client: TestClient) -> None:
    project_id = _create_project(client, "DUR-004")
    scope = _create_scope(client, project_id)
    resp = client.post(
        "/api/v1/construction/milestones",
        json={"scope_id": scope["id"], "name": "M1", "sequence": 1, "duration_days": -1},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Dependency create
# ---------------------------------------------------------------------------


def test_create_dependency_success(client: TestClient) -> None:
    project_id = _create_project(client, "DEP-001")
    scope = _create_scope(client, project_id)
    m1 = _create_milestone(client, scope["id"], sequence=1, name="M1", duration_days=5)
    m2 = _create_milestone(client, scope["id"], sequence=2, name="M2", duration_days=5)

    resp = client.post(
        "/api/v1/construction/dependencies",
        json={"predecessor_id": m1["id"], "successor_id": m2["id"]},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["predecessor_id"] == m1["id"]
    assert data["successor_id"] == m2["id"]
    assert data["lag_days"] == 0
    assert "id" in data


def test_create_dependency_with_lag(client: TestClient) -> None:
    project_id = _create_project(client, "DEP-002")
    scope = _create_scope(client, project_id)
    m1 = _create_milestone(client, scope["id"], sequence=1, name="M1", duration_days=5)
    m2 = _create_milestone(client, scope["id"], sequence=2, name="M2", duration_days=5)

    resp = client.post(
        "/api/v1/construction/dependencies",
        json={"predecessor_id": m1["id"], "successor_id": m2["id"], "lag_days": 3},
    )
    assert resp.status_code == 201
    assert resp.json()["lag_days"] == 3


def test_create_dependency_self_reference_rejected(client: TestClient) -> None:
    project_id = _create_project(client, "DEP-003")
    scope = _create_scope(client, project_id)
    m = _create_milestone(client, scope["id"], sequence=1, name="M1")

    resp = client.post(
        "/api/v1/construction/dependencies",
        json={"predecessor_id": m["id"], "successor_id": m["id"]},
    )
    assert resp.status_code == 422


def test_create_dependency_invalid_lag_rejected(client: TestClient) -> None:
    project_id = _create_project(client, "DEP-004")
    scope = _create_scope(client, project_id)
    m1 = _create_milestone(client, scope["id"], sequence=1, name="M1")
    m2 = _create_milestone(client, scope["id"], sequence=2, name="M2")

    resp = client.post(
        "/api/v1/construction/dependencies",
        json={"predecessor_id": m1["id"], "successor_id": m2["id"], "lag_days": -1},
    )
    assert resp.status_code == 422


def test_create_dependency_missing_predecessor_returns_404(client: TestClient) -> None:
    project_id = _create_project(client, "DEP-005")
    scope = _create_scope(client, project_id)
    m2 = _create_milestone(client, scope["id"], sequence=2, name="M2")

    resp = client.post(
        "/api/v1/construction/dependencies",
        json={"predecessor_id": "non-existent", "successor_id": m2["id"]},
    )
    assert resp.status_code == 404


def test_create_dependency_missing_successor_returns_404(client: TestClient) -> None:
    project_id = _create_project(client, "DEP-006")
    scope = _create_scope(client, project_id)
    m1 = _create_milestone(client, scope["id"], sequence=1, name="M1")

    resp = client.post(
        "/api/v1/construction/dependencies",
        json={"predecessor_id": m1["id"], "successor_id": "non-existent"},
    )
    assert resp.status_code == 404


def test_create_duplicate_dependency_returns_409(client: TestClient) -> None:
    project_id = _create_project(client, "DEP-007")
    scope = _create_scope(client, project_id)
    m1 = _create_milestone(client, scope["id"], sequence=1, name="M1")
    m2 = _create_milestone(client, scope["id"], sequence=2, name="M2")

    client.post(
        "/api/v1/construction/dependencies",
        json={"predecessor_id": m1["id"], "successor_id": m2["id"]},
    )
    resp = client.post(
        "/api/v1/construction/dependencies",
        json={"predecessor_id": m1["id"], "successor_id": m2["id"]},
    )
    assert resp.status_code == 409


def test_create_circular_dependency_returns_409(client: TestClient) -> None:
    """A → B then B → A should be rejected."""
    project_id = _create_project(client, "DEP-008")
    scope = _create_scope(client, project_id)
    m1 = _create_milestone(client, scope["id"], sequence=1, name="M1", duration_days=5)
    m2 = _create_milestone(client, scope["id"], sequence=2, name="M2", duration_days=5)

    resp1 = client.post(
        "/api/v1/construction/dependencies",
        json={"predecessor_id": m1["id"], "successor_id": m2["id"]},
    )
    assert resp1.status_code == 201

    resp2 = client.post(
        "/api/v1/construction/dependencies",
        json={"predecessor_id": m2["id"], "successor_id": m1["id"]},
    )
    assert resp2.status_code == 409


# ---------------------------------------------------------------------------
# Dependency list / get / delete
# ---------------------------------------------------------------------------


def test_list_scope_dependencies(client: TestClient) -> None:
    project_id = _create_project(client, "LIST-001")
    scope = _create_scope(client, project_id)
    m1 = _create_milestone(client, scope["id"], sequence=1, name="M1")
    m2 = _create_milestone(client, scope["id"], sequence=2, name="M2")
    m3 = _create_milestone(client, scope["id"], sequence=3, name="M3")

    client.post(
        "/api/v1/construction/dependencies",
        json={"predecessor_id": m1["id"], "successor_id": m2["id"]},
    )
    client.post(
        "/api/v1/construction/dependencies",
        json={"predecessor_id": m2["id"], "successor_id": m3["id"]},
    )

    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/dependencies")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_list_scope_dependencies_invalid_scope_returns_404(client: TestClient) -> None:
    resp = client.get("/api/v1/construction/scopes/non-existent/dependencies")
    assert resp.status_code == 404


def test_list_scope_dependencies_empty_scope(client: TestClient) -> None:
    project_id = _create_project(client, "LIST-002")
    scope = _create_scope(client, project_id)
    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/dependencies")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_get_dependency_by_id(client: TestClient) -> None:
    project_id = _create_project(client, "GET-DEP-001")
    scope = _create_scope(client, project_id)
    m1 = _create_milestone(client, scope["id"], sequence=1, name="M1")
    m2 = _create_milestone(client, scope["id"], sequence=2, name="M2")
    create_resp = client.post(
        "/api/v1/construction/dependencies",
        json={"predecessor_id": m1["id"], "successor_id": m2["id"]},
    )
    dep_id = create_resp.json()["id"]

    resp = client.get(f"/api/v1/construction/dependencies/{dep_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == dep_id


def test_get_dependency_not_found(client: TestClient) -> None:
    resp = client.get("/api/v1/construction/dependencies/non-existent")
    assert resp.status_code == 404


def test_delete_dependency(client: TestClient) -> None:
    project_id = _create_project(client, "DEL-DEP-001")
    scope = _create_scope(client, project_id)
    m1 = _create_milestone(client, scope["id"], sequence=1, name="M1")
    m2 = _create_milestone(client, scope["id"], sequence=2, name="M2")
    create_resp = client.post(
        "/api/v1/construction/dependencies",
        json={"predecessor_id": m1["id"], "successor_id": m2["id"]},
    )
    dep_id = create_resp.json()["id"]

    del_resp = client.delete(f"/api/v1/construction/dependencies/{dep_id}")
    assert del_resp.status_code == 204

    get_resp = client.get(f"/api/v1/construction/dependencies/{dep_id}")
    assert get_resp.status_code == 404


def test_delete_dependency_not_found(client: TestClient) -> None:
    resp = client.delete("/api/v1/construction/dependencies/non-existent")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Schedule endpoints
# ---------------------------------------------------------------------------


def test_get_schedule_empty_scope(client: TestClient) -> None:
    """Scope with no milestones returns zero project duration."""
    project_id = _create_project(client, "SCHED-002")
    scope = _create_scope(client, project_id)
    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/schedule")
    assert resp.status_code == 200
    data = resp.json()
    assert data["scope_id"] == scope["id"]
    assert data["project_duration"] == 0
    assert data["phases"] == []
    assert data["critical_path"] == []


def test_get_schedule_single_milestone(client: TestClient) -> None:
    project_id = _create_project(client, "SCHED-003")
    scope = _create_scope(client, project_id)
    m = _create_milestone(client, scope["id"], sequence=1, name="M1", duration_days=10)

    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/schedule")
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_duration"] == 10
    assert len(data["phases"]) == 1
    phase = data["phases"][0]
    assert phase["milestone_id"] == m["id"]
    assert phase["earliest_start"] == 0
    assert phase["earliest_finish"] == 10
    assert phase["is_critical"] is True
    assert data["critical_path"] == [m["id"]]


def test_get_schedule_linear_chain(client: TestClient) -> None:
    project_id = _create_project(client, "SCHED-004")
    scope = _create_scope(client, project_id)
    m1 = _create_milestone(client, scope["id"], sequence=1, name="M1", duration_days=10)
    m2 = _create_milestone(client, scope["id"], sequence=2, name="M2", duration_days=5)

    client.post(
        "/api/v1/construction/dependencies",
        json={"predecessor_id": m1["id"], "successor_id": m2["id"]},
    )

    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/schedule")
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_duration"] == 15

    phases_by_id = {p["milestone_id"]: p for p in data["phases"]}
    assert phases_by_id[m1["id"]]["earliest_start"] == 0
    assert phases_by_id[m2["id"]]["earliest_start"] == 10


def test_get_schedule_with_lag(client: TestClient) -> None:
    project_id = _create_project(client, "SCHED-005")
    scope = _create_scope(client, project_id)
    m1 = _create_milestone(client, scope["id"], sequence=1, name="M1", duration_days=10)
    m2 = _create_milestone(client, scope["id"], sequence=2, name="M2", duration_days=5)

    client.post(
        "/api/v1/construction/dependencies",
        json={"predecessor_id": m1["id"], "successor_id": m2["id"], "lag_days": 3},
    )

    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/schedule")
    assert resp.status_code == 200
    data = resp.json()
    phases_by_id = {p["milestone_id"]: p for p in data["phases"]}
    assert phases_by_id[m2["id"]]["earliest_start"] == 13


def test_recompute_schedule_endpoint(client: TestClient) -> None:
    project_id = _create_project(client, "SCHED-006")
    scope = _create_scope(client, project_id)
    m = _create_milestone(client, scope["id"], sequence=1, name="M1", duration_days=7)

    resp = client.post(f"/api/v1/construction/scopes/{scope['id']}/schedule/recompute")
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_duration"] == 7


def test_get_schedule_invalid_scope_returns_404(client: TestClient) -> None:
    resp = client.get("/api/v1/construction/scopes/non-existent/schedule")
    assert resp.status_code == 404


def test_recompute_schedule_invalid_scope_returns_404(client: TestClient) -> None:
    resp = client.post("/api/v1/construction/scopes/non-existent/schedule/recompute")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Critical path endpoint
# ---------------------------------------------------------------------------


def test_get_critical_path_empty_scope(client: TestClient) -> None:
    project_id = _create_project(client, "CP-001")
    scope = _create_scope(client, project_id)
    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/critical-path")
    assert resp.status_code == 200
    data = resp.json()
    assert data["scope_id"] == scope["id"]
    assert data["project_duration"] == 0
    assert data["total_phases"] == 0
    assert data["critical_phases"] == 0
    assert data["critical_path_milestone_ids"] == []
    assert data["critical_path_milestone_names"] == []


def test_get_critical_path_linear_chain(client: TestClient) -> None:
    project_id = _create_project(client, "CP-002")
    scope = _create_scope(client, project_id)
    m1 = _create_milestone(client, scope["id"], sequence=1, name="Foundation", duration_days=10)
    m2 = _create_milestone(client, scope["id"], sequence=2, name="Structure", duration_days=15)

    client.post(
        "/api/v1/construction/dependencies",
        json={"predecessor_id": m1["id"], "successor_id": m2["id"]},
    )

    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/critical-path")
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_duration"] == 25
    assert data["total_phases"] == 2
    assert data["critical_phases"] == 2
    assert m1["id"] in data["critical_path_milestone_ids"]
    assert m2["id"] in data["critical_path_milestone_ids"]
    assert "Foundation" in data["critical_path_milestone_names"]
    assert "Structure" in data["critical_path_milestone_names"]


def test_get_critical_path_parallel_phases(client: TestClient) -> None:
    """
    A(10) ─┐
            ├─ C(5)
    B(15) ─┘

    Critical path: B → C
    """
    project_id = _create_project(client, "CP-003")
    scope = _create_scope(client, project_id)
    a = _create_milestone(client, scope["id"], sequence=1, name="A", duration_days=10)
    b = _create_milestone(client, scope["id"], sequence=2, name="B", duration_days=15)
    c = _create_milestone(client, scope["id"], sequence=3, name="C", duration_days=5)

    client.post(
        "/api/v1/construction/dependencies",
        json={"predecessor_id": a["id"], "successor_id": c["id"]},
    )
    client.post(
        "/api/v1/construction/dependencies",
        json={"predecessor_id": b["id"], "successor_id": c["id"]},
    )

    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/critical-path")
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_duration"] == 20
    assert data["critical_phases"] == 2
    assert a["id"] not in data["critical_path_milestone_ids"]
    assert b["id"] in data["critical_path_milestone_ids"]
    assert c["id"] in data["critical_path_milestone_ids"]


def test_get_critical_path_invalid_scope_returns_404(client: TestClient) -> None:
    resp = client.get("/api/v1/construction/scopes/non-existent/critical-path")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Milestone dependency cascade on delete
# ---------------------------------------------------------------------------


def test_deleting_milestone_cascades_its_dependencies(client: TestClient) -> None:
    project_id = _create_project(client, "CASCADE-001")
    scope = _create_scope(client, project_id)
    m1 = _create_milestone(client, scope["id"], sequence=1, name="M1", duration_days=5)
    m2 = _create_milestone(client, scope["id"], sequence=2, name="M2", duration_days=5)
    m3 = _create_milestone(client, scope["id"], sequence=3, name="M3", duration_days=5)

    create_resp = client.post(
        "/api/v1/construction/dependencies",
        json={"predecessor_id": m1["id"], "successor_id": m2["id"]},
    )
    assert create_resp.status_code == 201
    dep_id = create_resp.json()["id"]

    client.delete(f"/api/v1/construction/milestones/{m1['id']}")

    get_resp = client.get(f"/api/v1/construction/dependencies/{dep_id}")
    assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# Schedule response shape validation
# ---------------------------------------------------------------------------


def test_schedule_phase_row_has_all_expected_fields(client: TestClient) -> None:
    project_id = _create_project(client, "SHAPE-001")
    scope = _create_scope(client, project_id)
    _create_milestone(client, scope["id"], sequence=1, name="M1", duration_days=5)

    resp = client.get(f"/api/v1/construction/scopes/{scope['id']}/schedule")
    assert resp.status_code == 200
    row = resp.json()["phases"][0]

    expected_fields = {
        "milestone_id",
        "milestone_name",
        "duration_days",
        "earliest_start",
        "earliest_finish",
        "latest_start",
        "latest_finish",
        "total_float",
        "is_critical",
        "delay_days",
    }
    assert expected_fields.issubset(set(row.keys()))
