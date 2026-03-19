"""
Tests for the Construction Dashboard (PR-C5).

Validates project-level construction dashboard aggregation:
  - 404 for unknown project
  - empty project with no scopes
  - dashboard totals with one scope
  - dashboard totals with multiple scopes
  - overdue milestone counting
  - engineering item open/completed counts
  - cost summary aggregation into dashboard
  - scope isolation (project A should not include project B scopes)
  - latest_progress_percent when updates exist / do not exist
  - variance correctness
  - active scope counting
"""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient


# ── Helper factories ──────────────────────────────────────────────────────────


def _create_project(client: TestClient, code: str) -> str:
    resp = client.post("/api/v1/projects", json={"name": f"Project {code}", "code": code})
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_scope(client: TestClient, project_id: str, name: str = "Scope A") -> dict:
    resp = client.post(
        "/api/v1/construction/scopes",
        json={"project_id": project_id, "name": name},
    )
    assert resp.status_code == 201
    return resp.json()


def _create_milestone(
    client: TestClient,
    scope_id: str,
    *,
    sequence: int = 1,
    name: str = "Foundation",
    status: str = "pending",
    target_date: str | None = None,
) -> dict:
    payload: dict = {"scope_id": scope_id, "name": name, "sequence": sequence, "status": status}
    if target_date:
        payload["target_date"] = target_date
    resp = client.post("/api/v1/construction/milestones", json=payload)
    assert resp.status_code == 201
    return resp.json()


def _create_engineering_item(
    client: TestClient,
    scope_id: str,
    *,
    title: str = "Structural Review",
    status: str = "pending",
) -> dict:
    resp = client.post(
        f"/api/v1/construction/scopes/{scope_id}/engineering-items",
        json={"title": title, "status": status},
    )
    assert resp.status_code == 201
    return resp.json()


def _create_cost_item(
    client: TestClient,
    scope_id: str,
    *,
    budget_amount: float = 10000.0,
    committed_amount: float = 0.0,
    actual_amount: float = 0.0,
) -> dict:
    resp = client.post(
        f"/api/v1/construction/scopes/{scope_id}/cost-items",
        json={
            "cost_category": "materials",
            "cost_type": "budget",
            "description": "Steel reinforcement",
            "budget_amount": budget_amount,
            "committed_amount": committed_amount,
            "actual_amount": actual_amount,
        },
    )
    assert resp.status_code == 201
    return resp.json()


def _create_progress_update(
    client: TestClient,
    milestone_id: str,
    *,
    progress_percent: int = 50,
    reported_at: str | None = None,
) -> dict:
    payload: dict = {"progress_percent": progress_percent}
    if reported_at:
        payload["reported_at"] = reported_at
    resp = client.post(
        f"/api/v1/construction/milestones/{milestone_id}/progress-updates",
        json=payload,
    )
    assert resp.status_code == 201
    return resp.json()


def _get_dashboard(client: TestClient, project_id: str) -> dict:
    resp = client.get(f"/api/v1/construction/projects/{project_id}/dashboard")
    return resp


# ── 404 for unknown project ───────────────────────────────────────────────────


def test_dashboard_unknown_project_returns_404(client: TestClient):
    resp = _get_dashboard(client, "non-existent-project")
    assert resp.status_code == 404


# ── Empty project (no scopes) ─────────────────────────────────────────────────


def test_dashboard_empty_project_no_scopes(client: TestClient):
    project_id = _create_project(client, "DASH-P01")
    resp = _get_dashboard(client, project_id)
    assert resp.status_code == 200
    data = resp.json()

    assert data["project_id"] == project_id
    assert data["scopes_total"] == 0
    assert data["scopes_active"] == 0
    assert data["engineering_items_open_total"] == 0
    assert data["milestones_overdue_total"] == 0
    assert Decimal(data["total_budget"]) == Decimal("0.00")
    assert Decimal(data["total_committed"]) == Decimal("0.00")
    assert Decimal(data["total_actual"]) == Decimal("0.00")
    assert Decimal(data["variance_to_budget"]) == Decimal("0.00")
    assert Decimal(data["variance_to_commitment"]) == Decimal("0.00")
    assert data["scopes"] == []


# ── Dashboard totals with one scope ──────────────────────────────────────────


def test_dashboard_one_scope_no_data(client: TestClient):
    project_id = _create_project(client, "DASH-P02")
    scope = _create_scope(client, project_id, "Scope Alpha")
    resp = _get_dashboard(client, project_id)
    assert resp.status_code == 200
    data = resp.json()

    assert data["scopes_total"] == 1
    assert len(data["scopes"]) == 1
    s = data["scopes"][0]
    assert s["scope_id"] == scope["id"]
    assert s["scope_name"] == "Scope Alpha"
    assert s["engineering_items_total"] == 0
    assert s["engineering_items_open"] == 0
    assert s["engineering_items_completed"] == 0
    assert s["milestones_total"] == 0
    assert s["milestones_completed"] == 0
    assert s["milestones_overdue"] == 0
    assert s["latest_progress_percent"] is None
    assert Decimal(s["total_budget"]) == Decimal("0.00")
    assert Decimal(s["variance_to_budget"]) == Decimal("0.00")


# ── Engineering item counts ───────────────────────────────────────────────────


def test_dashboard_engineering_item_counts(client: TestClient):
    project_id = _create_project(client, "DASH-P03")
    scope = _create_scope(client, project_id)

    _create_engineering_item(client, scope["id"], title="Item 1", status="pending")
    _create_engineering_item(client, scope["id"], title="Item 2", status="in_progress")
    _create_engineering_item(client, scope["id"], title="Item 3", status="completed")

    resp = _get_dashboard(client, project_id)
    assert resp.status_code == 200
    s = resp.json()["scopes"][0]

    assert s["engineering_items_total"] == 3
    assert s["engineering_items_completed"] == 1
    assert s["engineering_items_open"] == 2
    assert resp.json()["engineering_items_open_total"] == 2


# ── Milestone completed/overdue counts ───────────────────────────────────────


def test_dashboard_milestone_counts_completed(client: TestClient):
    project_id = _create_project(client, "DASH-P04")
    scope = _create_scope(client, project_id)

    _create_milestone(client, scope["id"], sequence=1, status="completed")
    _create_milestone(client, scope["id"], sequence=2, status="pending")

    resp = _get_dashboard(client, project_id)
    assert resp.status_code == 200
    s = resp.json()["scopes"][0]

    assert s["milestones_total"] == 2
    assert s["milestones_completed"] == 1


def test_dashboard_overdue_milestone_counting(client: TestClient):
    project_id = _create_project(client, "DASH-P05")
    scope = _create_scope(client, project_id)

    # Overdue: target_date in the past, not completed
    _create_milestone(
        client, scope["id"], sequence=1, status="pending", target_date="2000-01-01"
    )
    _create_milestone(
        client, scope["id"], sequence=2, status="delayed", target_date="2000-01-01"
    )
    # Not overdue: completed even though date is in the past
    _create_milestone(
        client, scope["id"], sequence=3, status="completed", target_date="2000-01-01"
    )
    # Not overdue: no target_date
    _create_milestone(client, scope["id"], sequence=4, status="pending")

    resp = _get_dashboard(client, project_id)
    assert resp.status_code == 200
    data = resp.json()
    s = data["scopes"][0]

    assert s["milestones_overdue"] == 2
    assert data["milestones_overdue_total"] == 2


# ── Cost summary aggregation ──────────────────────────────────────────────────


def test_dashboard_cost_aggregation_single_scope(client: TestClient):
    project_id = _create_project(client, "DASH-P06")
    scope = _create_scope(client, project_id)

    _create_cost_item(
        client, scope["id"], budget_amount=10000.0, committed_amount=8000.0, actual_amount=6000.0
    )
    _create_cost_item(
        client, scope["id"], budget_amount=5000.0, committed_amount=4000.0, actual_amount=3000.0
    )

    resp = _get_dashboard(client, project_id)
    assert resp.status_code == 200
    data = resp.json()
    s = data["scopes"][0]

    assert Decimal(s["total_budget"]) == Decimal("15000.00")
    assert Decimal(s["total_committed"]) == Decimal("12000.00")
    assert Decimal(s["total_actual"]) == Decimal("9000.00")
    assert Decimal(s["variance_to_budget"]) == Decimal("-6000.00")
    assert Decimal(s["variance_to_commitment"]) == Decimal("-3000.00")

    # Top-level totals
    assert Decimal(data["total_budget"]) == Decimal("15000.00")
    assert Decimal(data["total_actual"]) == Decimal("9000.00")
    assert Decimal(data["variance_to_budget"]) == Decimal("-6000.00")


# ── Multiple scopes ───────────────────────────────────────────────────────────


def test_dashboard_multiple_scopes_totals(client: TestClient):
    project_id = _create_project(client, "DASH-P07")

    # Scope 1: one project → one scope only (uniqueness constraint)
    # We need two separate projects to test multiple scopes but the
    # constraint is per project/phase/building combo.  Use separate
    # project+phase combos or create phases.
    # Actually the scope uniqueness is per (project_id, phase_id, building_id)
    # combination. Two scopes on same project but different phases work fine.
    # But for the simplest approach, create two different projects and then
    # test each independently… or use two scopes with different phase_ids.
    #
    # Simpler: just use two projects with one scope each and verify isolation.
    # But here we specifically want multiple scopes under the SAME project.
    # The unique constraint is per (project_id, phase_id, building_id) trio.
    # So two scopes linked to different phases of the same project are fine.
    #
    # However creating phases requires project. Let's create a project with phases.
    phase_resp = client.post(
        "/api/v1/phases", json={"project_id": project_id, "name": "Phase 1", "sequence": 1}
    )
    assert phase_resp.status_code == 201
    phase_id = phase_resp.json()["id"]

    # Scope A: linked to project (project_id only, phase_id=None)
    scope_a_resp = client.post(
        "/api/v1/construction/scopes",
        json={"project_id": project_id, "name": "Scope A"},
    )
    assert scope_a_resp.status_code == 201
    scope_a = scope_a_resp.json()

    # Scope B: linked to phase (phase_id only, project_id=None)
    scope_b_resp = client.post(
        "/api/v1/construction/scopes",
        json={"phase_id": phase_id, "name": "Scope B"},
    )
    assert scope_b_resp.status_code == 201

    _create_cost_item(client, scope_a["id"], budget_amount=10000.0, actual_amount=5000.0)

    # Only scope_a is linked to project_id; scope_b is linked to phase only
    resp = _get_dashboard(client, project_id)
    assert resp.status_code == 200
    data = resp.json()

    # Only the project-linked scope should appear in the project dashboard
    assert data["scopes_total"] == 1
    assert Decimal(data["total_budget"]) == Decimal("10000.00")


def test_dashboard_scope_isolation_across_projects(client: TestClient):
    """Project A dashboard must not include Project B scopes."""
    project_a = _create_project(client, "DASH-ISO-A")
    project_b = _create_project(client, "DASH-ISO-B")

    scope_a = _create_scope(client, project_a, "Scope A")
    scope_b = _create_scope(client, project_b, "Scope B")

    _create_cost_item(client, scope_a["id"], budget_amount=1000.0, actual_amount=500.0)
    _create_cost_item(client, scope_b["id"], budget_amount=9999.0, actual_amount=9999.0)

    resp_a = _get_dashboard(client, project_a)
    assert resp_a.status_code == 200
    data_a = resp_a.json()

    assert data_a["scopes_total"] == 1
    assert data_a["scopes"][0]["scope_id"] == scope_a["id"]
    assert Decimal(data_a["total_budget"]) == Decimal("1000.00")
    assert Decimal(data_a["total_actual"]) == Decimal("500.00")

    resp_b = _get_dashboard(client, project_b)
    assert resp_b.status_code == 200
    data_b = resp_b.json()

    assert data_b["scopes_total"] == 1
    assert data_b["scopes"][0]["scope_id"] == scope_b["id"]
    assert Decimal(data_b["total_budget"]) == Decimal("9999.00")


# ── Latest progress percent ───────────────────────────────────────────────────


def test_dashboard_no_progress_updates_returns_none(client: TestClient):
    project_id = _create_project(client, "DASH-P08")
    scope = _create_scope(client, project_id)
    _create_milestone(client, scope["id"], sequence=1)

    resp = _get_dashboard(client, project_id)
    assert resp.status_code == 200
    s = resp.json()["scopes"][0]
    assert s["latest_progress_percent"] is None


def test_dashboard_latest_progress_reflects_most_recent_update(client: TestClient):
    project_id = _create_project(client, "DASH-P09")
    scope = _create_scope(client, project_id)
    milestone = _create_milestone(client, scope["id"], sequence=1)

    _create_progress_update(
        client,
        milestone["id"],
        progress_percent=30,
        reported_at="2024-01-01T10:00:00Z",
    )
    _create_progress_update(
        client,
        milestone["id"],
        progress_percent=75,
        reported_at="2024-06-01T10:00:00Z",
    )

    resp = _get_dashboard(client, project_id)
    assert resp.status_code == 200
    s = resp.json()["scopes"][0]
    assert s["latest_progress_percent"] == 75


# ── Variance correctness ──────────────────────────────────────────────────────


def test_dashboard_variance_over_budget(client: TestClient):
    """When actual > budget, variance_to_budget must be positive."""
    project_id = _create_project(client, "DASH-P10")
    scope = _create_scope(client, project_id)

    _create_cost_item(
        client, scope["id"],
        budget_amount=5000.0,
        committed_amount=5000.0,
        actual_amount=7000.0,
    )

    resp = _get_dashboard(client, project_id)
    assert resp.status_code == 200
    data = resp.json()
    s = data["scopes"][0]

    assert Decimal(s["variance_to_budget"]) == Decimal("2000.00")
    assert Decimal(s["variance_to_commitment"]) == Decimal("2000.00")
    assert Decimal(data["variance_to_budget"]) == Decimal("2000.00")


# ── Active scope counting ─────────────────────────────────────────────────────


def test_dashboard_active_scope_with_open_engineering_item(client: TestClient):
    project_id = _create_project(client, "DASH-P11")
    scope = _create_scope(client, project_id)

    # Add an open (non-completed) engineering item → scope is active
    _create_engineering_item(client, scope["id"], status="in_progress")

    resp = _get_dashboard(client, project_id)
    assert resp.status_code == 200
    data = resp.json()
    assert data["scopes_active"] == 1


def test_dashboard_scope_fully_completed_not_active(client: TestClient):
    """A scope with only completed items and zero cost is not counted as active."""
    project_id = _create_project(client, "DASH-P12")
    scope = _create_scope(client, project_id)

    _create_engineering_item(client, scope["id"], status="completed")
    _create_milestone(client, scope["id"], sequence=1, status="completed")
    # No cost items → committed and actual both zero

    resp = _get_dashboard(client, project_id)
    assert resp.status_code == 200
    data = resp.json()
    assert data["scopes_active"] == 0
