"""
Tests for the Construction Cost Tracking API.

PR-CONSTR-042 — Construction Cost Tracking & Budget Variance

Validates:
- POST /construction/milestones/{id}/cost — update milestone cost
- GET  /construction/scopes/{id}/cost    — scope milestone cost overview

Error cases:
- 404 on unknown milestone / scope
- 422 on invalid cost payloads (negative costs, missing fields)
"""

from decimal import Decimal

import httpx
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _create_project(client: TestClient, code: str = "CA-001") -> str:
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


def _post_cost(
    client: TestClient,
    milestone_id: str,
    payload: dict,
) -> "httpx.Response":
    return client.post(
        f"/api/v1/construction/milestones/{milestone_id}/cost",
        json=payload,
    )


def _get_scope_cost(client: TestClient, scope_id: str) -> "httpx.Response":
    return client.get(f"/api/v1/construction/scopes/{scope_id}/cost")


# ---------------------------------------------------------------------------
# POST /construction/milestones/{id}/cost
# ---------------------------------------------------------------------------


def test_update_planned_cost(client: TestClient) -> None:
    project_id = _create_project(client, "CA-010")
    scope = _create_scope(client, project_id)
    m = _create_milestone(client, scope["id"])

    resp = _post_cost(client, m["id"], {"planned_cost": 50000.00})
    assert resp.status_code == 200
    data = resp.json()
    assert Decimal(data["planned_cost"]) == Decimal("50000.00")
    assert data["actual_cost"] is None
    assert data["cost_last_updated_at"] is not None


def test_update_actual_cost(client: TestClient) -> None:
    project_id = _create_project(client, "CA-011")
    scope = _create_scope(client, project_id)
    m = _create_milestone(client, scope["id"])

    resp = _post_cost(client, m["id"], {"actual_cost": 55000.00})
    assert resp.status_code == 200
    data = resp.json()
    assert data["planned_cost"] is None
    assert Decimal(data["actual_cost"]) == Decimal("55000.00")
    assert data["cost_last_updated_at"] is not None


def test_update_both_costs(client: TestClient) -> None:
    project_id = _create_project(client, "CA-012")
    scope = _create_scope(client, project_id)
    m = _create_milestone(client, scope["id"])

    resp = _post_cost(client, m["id"], {"planned_cost": 40000.00, "actual_cost": 45000.00})
    assert resp.status_code == 200
    data = resp.json()
    assert Decimal(data["planned_cost"]) == Decimal("40000.00")
    assert Decimal(data["actual_cost"]) == Decimal("45000.00")
    assert data["cost_last_updated_at"] is not None


def test_update_cost_overwrites_previous(client: TestClient) -> None:
    project_id = _create_project(client, "CA-013")
    scope = _create_scope(client, project_id)
    m = _create_milestone(client, scope["id"])

    _post_cost(client, m["id"], {"planned_cost": 10000.00})
    resp = _post_cost(client, m["id"], {"planned_cost": 20000.00, "actual_cost": 18000.00})
    assert resp.status_code == 200
    data = resp.json()
    assert Decimal(data["planned_cost"]) == Decimal("20000.00")
    assert Decimal(data["actual_cost"]) == Decimal("18000.00")


def test_update_cost_milestone_not_found(client: TestClient) -> None:
    resp = _post_cost(client, "nonexistent-id", {"planned_cost": 1000.00})
    assert resp.status_code == 404


def test_update_cost_no_fields_422(client: TestClient) -> None:
    project_id = _create_project(client, "CA-014")
    scope = _create_scope(client, project_id)
    m = _create_milestone(client, scope["id"])

    resp = _post_cost(client, m["id"], {})
    assert resp.status_code == 422


def test_update_cost_negative_planned_422(client: TestClient) -> None:
    project_id = _create_project(client, "CA-015")
    scope = _create_scope(client, project_id)
    m = _create_milestone(client, scope["id"])

    resp = _post_cost(client, m["id"], {"planned_cost": -100.00})
    assert resp.status_code == 422


def test_update_cost_negative_actual_422(client: TestClient) -> None:
    project_id = _create_project(client, "CA-016")
    scope = _create_scope(client, project_id)
    m = _create_milestone(client, scope["id"])

    resp = _post_cost(client, m["id"], {"actual_cost": -500.00})
    assert resp.status_code == 422


def test_update_cost_zero_is_valid(client: TestClient) -> None:
    project_id = _create_project(client, "CA-017")
    scope = _create_scope(client, project_id)
    m = _create_milestone(client, scope["id"])

    resp = _post_cost(client, m["id"], {"planned_cost": 0.00, "actual_cost": 0.00})
    assert resp.status_code == 200
    data = resp.json()
    assert Decimal(data["planned_cost"]) == Decimal("0.00")
    assert Decimal(data["actual_cost"]) == Decimal("0.00")


# ---------------------------------------------------------------------------
# GET /construction/scopes/{id}/cost
# ---------------------------------------------------------------------------


def test_get_scope_cost_empty_milestones(client: TestClient) -> None:
    project_id = _create_project(client, "CA-020")
    scope = _create_scope(client, project_id)

    resp = _get_scope_cost(client, scope["id"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["scope_id"] == scope["id"]
    assert Decimal(data["project_budget"]) == Decimal("0.00")
    assert Decimal(data["project_actual_cost"]) == Decimal("0.00")
    assert Decimal(data["project_cost_variance"]) == Decimal("0.00")
    assert data["project_overrun_percent"] is None
    assert data["milestones"] == []


def test_get_scope_cost_single_milestone_on_budget(client: TestClient) -> None:
    project_id = _create_project(client, "CA-021")
    scope = _create_scope(client, project_id)
    m = _create_milestone(client, scope["id"])
    _post_cost(client, m["id"], {"planned_cost": 10000.00, "actual_cost": 10000.00})

    resp = _get_scope_cost(client, scope["id"])
    assert resp.status_code == 200
    data = resp.json()
    assert Decimal(data["project_budget"]) == Decimal("10000.00")
    assert Decimal(data["project_actual_cost"]) == Decimal("10000.00")
    assert Decimal(data["project_cost_variance"]) == Decimal("0.00")
    assert Decimal(data["project_overrun_percent"]) == Decimal("0.00")


def test_get_scope_cost_overrun(client: TestClient) -> None:
    project_id = _create_project(client, "CA-022")
    scope = _create_scope(client, project_id)
    m1 = _create_milestone(client, scope["id"], sequence=1, name="M1")
    m2 = _create_milestone(client, scope["id"], sequence=2, name="M2")
    _post_cost(client, m1["id"], {"planned_cost": 20000.00, "actual_cost": 25000.00})
    _post_cost(client, m2["id"], {"planned_cost": 10000.00, "actual_cost": 10000.00})

    resp = _get_scope_cost(client, scope["id"])
    assert resp.status_code == 200
    data = resp.json()
    assert Decimal(data["project_budget"]) == Decimal("30000.00")
    assert Decimal(data["project_actual_cost"]) == Decimal("35000.00")
    assert Decimal(data["project_cost_variance"]) == Decimal("5000.00")
    assert Decimal(data["project_overrun_percent"]) == Decimal("16.67")


def test_get_scope_cost_under_budget(client: TestClient) -> None:
    project_id = _create_project(client, "CA-023")
    scope = _create_scope(client, project_id)
    m = _create_milestone(client, scope["id"])
    _post_cost(client, m["id"], {"planned_cost": 10000.00, "actual_cost": 8000.00})

    resp = _get_scope_cost(client, scope["id"])
    assert resp.status_code == 200
    data = resp.json()
    assert Decimal(data["project_cost_variance"]) == Decimal("-2000.00")
    assert Decimal(data["project_overrun_percent"]) == Decimal("-20.00")


def test_get_scope_cost_milestone_rows_contain_variance(client: TestClient) -> None:
    project_id = _create_project(client, "CA-024")
    scope = _create_scope(client, project_id)
    m = _create_milestone(client, scope["id"], name="Structure")
    _post_cost(client, m["id"], {"planned_cost": 15000.00, "actual_cost": 18000.00})

    resp = _get_scope_cost(client, scope["id"])
    assert resp.status_code == 200
    data = resp.json()
    rows = data["milestones"]
    assert len(rows) == 1
    row = rows[0]
    assert row["milestone_id"] == m["id"]
    assert row["milestone_name"] == "Structure"
    assert Decimal(row["planned_cost"]) == Decimal("15000.00")
    assert Decimal(row["actual_cost"]) == Decimal("18000.00")
    assert Decimal(row["cost_variance"]) == Decimal("3000.00")
    assert Decimal(row["cost_variance_percent"]) == Decimal("20.00")
    assert row["cost_last_updated_at"] is not None


def test_get_scope_cost_milestone_with_only_planned(client: TestClient) -> None:
    project_id = _create_project(client, "CA-025")
    scope = _create_scope(client, project_id)
    m = _create_milestone(client, scope["id"])
    _post_cost(client, m["id"], {"planned_cost": 5000.00})

    resp = _get_scope_cost(client, scope["id"])
    assert resp.status_code == 200
    data = resp.json()
    row = data["milestones"][0]
    assert Decimal(row["planned_cost"]) == Decimal("5000.00")
    assert row["actual_cost"] is None
    assert row["cost_variance"] is None
    assert row["cost_variance_percent"] is None


def test_get_scope_cost_milestone_no_costs(client: TestClient) -> None:
    project_id = _create_project(client, "CA-026")
    scope = _create_scope(client, project_id)
    _create_milestone(client, scope["id"])

    resp = _get_scope_cost(client, scope["id"])
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["milestones"]) == 1
    row = data["milestones"][0]
    assert row["planned_cost"] is None
    assert row["actual_cost"] is None
    assert row["cost_variance"] is None


def test_get_scope_cost_not_found(client: TestClient) -> None:
    resp = _get_scope_cost(client, "nonexistent-scope-id")
    assert resp.status_code == 404


def test_get_scope_cost_multiple_milestones_aggregate(client: TestClient) -> None:
    project_id = _create_project(client, "CA-027")
    scope = _create_scope(client, project_id)
    m1 = _create_milestone(client, scope["id"], sequence=1, name="Phase1")
    m2 = _create_milestone(client, scope["id"], sequence=2, name="Phase2")
    m3 = _create_milestone(client, scope["id"], sequence=3, name="Phase3")

    _post_cost(client, m1["id"], {"planned_cost": 10000.00, "actual_cost": 11000.00})
    _post_cost(client, m2["id"], {"planned_cost": 20000.00, "actual_cost": 18000.00})
    # m3 has no cost set

    resp = _get_scope_cost(client, scope["id"])
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["milestones"]) == 3
    assert Decimal(data["project_budget"]) == Decimal("30000.00")
    assert Decimal(data["project_actual_cost"]) == Decimal("29000.00")
    assert Decimal(data["project_cost_variance"]) == Decimal("-1000.00")


def test_cost_fields_appear_in_milestone_response(client: TestClient) -> None:
    """Verify new cost fields are included in the standard milestone response."""
    project_id = _create_project(client, "CA-030")
    scope = _create_scope(client, project_id)
    m = _create_milestone(client, scope["id"])

    # Initially all null
    get_resp = client.get(f"/api/v1/construction/milestones/{m['id']}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert "planned_cost" in data
    assert "actual_cost" in data
    assert "cost_last_updated_at" in data
    assert data["planned_cost"] is None
    assert data["actual_cost"] is None

    # After update, costs are present
    _post_cost(client, m["id"], {"planned_cost": 9999.99, "actual_cost": 9999.99})
    get_resp2 = client.get(f"/api/v1/construction/milestones/{m['id']}")
    data2 = get_resp2.json()
    assert Decimal(data2["planned_cost"]) == Decimal("9999.99")
    assert Decimal(data2["actual_cost"]) == Decimal("9999.99")
    assert data2["cost_last_updated_at"] is not None
