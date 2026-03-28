"""
Tests for GET /api/v1/projects/{project_id}/lifecycle-summary.

Validates lifecycle stage derivation, readiness flags, and next-step
recommendations for projects at each stage of the development lifecycle.
"""

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_ASSUMPTIONS = {
    "sellable_area_sqm": 1000.0,
    "avg_sale_price_per_sqm": 3000.0,
    "construction_cost_per_sqm": 800.0,
    "soft_cost_ratio": 0.10,
    "finance_cost_ratio": 0.05,
    "sales_cost_ratio": 0.03,
    "development_period_months": 24,
}


def _create_project(client: TestClient, code: str = "LC-001") -> str:
    resp = client.post("/api/v1/projects", json={"name": "Lifecycle Project", "code": code})
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_phase(client: TestClient, project_id: str, sequence: int = 1) -> str:
    resp = client.post(
        "/api/v1/phases",
        json={"project_id": project_id, "name": f"Phase {sequence}", "sequence": sequence},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_scenario(client: TestClient, project_id: str) -> str:
    resp = client.post(
        "/api/v1/scenarios",
        json={"name": "Test Scenario", "project_id": project_id},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_feasibility_run(client: TestClient, project_id: str) -> str:
    """Create a feasibility run in draft status."""
    resp = client.post(
        "/api/v1/feasibility/runs",
        json={"project_id": project_id, "scenario_name": "Base Case"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _add_assumptions(client: TestClient, run_id: str) -> None:
    resp = client.post(
        f"/api/v1/feasibility/runs/{run_id}/assumptions",
        json=_VALID_ASSUMPTIONS,
    )
    assert resp.status_code == 201


def _calculate_feasibility(client: TestClient, run_id: str) -> None:
    resp = client.post(f"/api/v1/feasibility/runs/{run_id}/calculate")
    assert resp.status_code == 200


def _create_construction_record(client: TestClient, project_id: str) -> str:
    resp = client.post(
        f"/api/v1/projects/{project_id}/construction-cost-records",
        json={
            "title": "Foundation Work",
            "amount": 100000.0,
            "cost_category": "hard_cost",
            "cost_source": "estimate",
            "cost_stage": "construction",
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_comparison_set(client: TestClient, project_id: str) -> str:
    resp = client.post(
        f"/api/v1/projects/{project_id}/tender-comparisons",
        json={
            "title": "Baseline vs Tender",
            "comparison_stage": "baseline_vs_tender",
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _approve_baseline(client: TestClient, set_id: str) -> None:
    resp = client.post(f"/api/v1/tender-comparisons/{set_id}/approve-baseline")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_lifecycle_summary_not_found(client: TestClient):
    """GET lifecycle-summary for an unknown project returns 404."""
    resp = client.get("/api/v1/projects/does-not-exist/lifecycle-summary")
    assert resp.status_code == 404


def test_lifecycle_summary_land_defined_stage(client: TestClient):
    """A project with no linked records should be in land_defined stage."""
    project_id = _create_project(client, code="LC-LAND")

    resp = client.get(f"/api/v1/projects/{project_id}/lifecycle-summary")
    assert resp.status_code == 200

    data = resp.json()
    assert data["project_id"] == project_id
    assert data["current_stage"] == "land_defined"
    assert data["has_scenarios"] is False
    assert data["has_feasibility_runs"] is False
    assert data["has_phases"] is False
    assert data["has_construction_records"] is False
    assert data["has_approved_tender_baseline"] is False
    assert data["scenario_count"] == 0
    assert data["feasibility_run_count"] == 0
    assert data["construction_record_count"] == 0
    assert data["next_step_route"] == "/scenarios"
    assert data["blocked_reason"] is None
    assert "last_updated_at" in data


def test_lifecycle_summary_scenario_defined_stage(client: TestClient):
    """A project with a scenario but no feasibility run is in scenario_defined stage."""
    project_id = _create_project(client, code="LC-SCEN")
    _create_scenario(client, project_id)

    resp = client.get(f"/api/v1/projects/{project_id}/lifecycle-summary")
    assert resp.status_code == 200

    data = resp.json()
    assert data["current_stage"] == "scenario_defined"
    assert data["has_scenarios"] is True
    assert data["has_feasibility_runs"] is False
    assert data["scenario_count"] == 1
    assert data["next_step_route"] == "/feasibility"
    assert data["blocked_reason"] is None


def test_lifecycle_summary_feasibility_ready_stage(client: TestClient):
    """A project with a feasibility run (not yet calculated) is in feasibility_ready stage."""
    project_id = _create_project(client, code="LC-FEAS")
    _create_feasibility_run(client, project_id)

    resp = client.get(f"/api/v1/projects/{project_id}/lifecycle-summary")
    assert resp.status_code == 200

    data = resp.json()
    assert data["current_stage"] == "feasibility_ready"
    assert data["has_feasibility_runs"] is True
    assert data["has_calculated_feasibility"] is False
    assert data["feasibility_run_count"] == 1
    assert data["blocked_reason"] is not None


def test_lifecycle_summary_feasibility_calculated_stage(client: TestClient):
    """A project with a calculated feasibility run is in feasibility_calculated stage."""
    project_id = _create_project(client, code="LC-CALC")
    run_id = _create_feasibility_run(client, project_id)
    _add_assumptions(client, run_id)
    _calculate_feasibility(client, run_id)

    resp = client.get(f"/api/v1/projects/{project_id}/lifecycle-summary")
    assert resp.status_code == 200

    data = resp.json()
    assert data["current_stage"] == "feasibility_calculated"
    assert data["has_calculated_feasibility"] is True
    assert data["next_step_route"] is not None


def test_lifecycle_summary_structure_ready_stage(client: TestClient):
    """A project with phases defined is in structure_ready stage."""
    project_id = _create_project(client, code="LC-STRUCT")
    _create_phase(client, project_id)

    resp = client.get(f"/api/v1/projects/{project_id}/lifecycle-summary")
    assert resp.status_code == 200

    data = resp.json()
    assert data["current_stage"] == "structure_ready"
    assert data["has_phases"] is True
    assert data["has_construction_records"] is False
    assert data["next_step_route"] == f"/projects/{project_id}/construction-costs"
    assert data["blocked_reason"] is None


def test_lifecycle_summary_construction_baseline_pending_stage(client: TestClient):
    """A project with construction records but no approved baseline is construction_baseline_pending."""
    project_id = _create_project(client, code="LC-BPEND")
    _create_phase(client, project_id)
    _create_construction_record(client, project_id)

    resp = client.get(f"/api/v1/projects/{project_id}/lifecycle-summary")
    assert resp.status_code == 200

    data = resp.json()
    assert data["current_stage"] == "construction_baseline_pending"
    assert data["has_construction_records"] is True
    assert data["has_approved_tender_baseline"] is False
    assert data["construction_record_count"] == 1
    assert data["next_step_route"] == f"/projects/{project_id}/tender-comparisons"
    assert data["blocked_reason"] is not None


def test_lifecycle_summary_construction_monitored_stage(client: TestClient):
    """A project with an approved baseline is in construction_monitored stage."""
    project_id = _create_project(client, code="LC-MON")
    _create_phase(client, project_id)
    _create_construction_record(client, project_id)
    set_id = _create_comparison_set(client, project_id)
    _approve_baseline(client, set_id)

    resp = client.get(f"/api/v1/projects/{project_id}/lifecycle-summary")
    assert resp.status_code == 200

    data = resp.json()
    assert data["current_stage"] == "construction_monitored"
    assert data["has_approved_tender_baseline"] is True
    assert data["next_step_route"] == f"/projects/{project_id}/construction-costs"
    assert data["blocked_reason"] is None


def test_lifecycle_summary_is_deterministic(client: TestClient):
    """Lifecycle summary returns the same stage on repeated calls."""
    project_id = _create_project(client, code="LC-DET")
    _create_scenario(client, project_id)

    for _ in range(3):
        resp = client.get(f"/api/v1/projects/{project_id}/lifecycle-summary")
        assert resp.status_code == 200
        assert resp.json()["current_stage"] == "scenario_defined"


def test_lifecycle_summary_flags_present_in_response(client: TestClient):
    """Response payload contains all expected fields."""
    project_id = _create_project(client, code="LC-FIELDS")

    resp = client.get(f"/api/v1/projects/{project_id}/lifecycle-summary")
    assert resp.status_code == 200

    data = resp.json()
    expected_fields = {
        "project_id",
        "has_scenarios",
        "has_active_scenario",
        "has_feasibility_runs",
        "has_calculated_feasibility",
        "has_phases",
        "has_construction_records",
        "has_approved_tender_baseline",
        "scenario_count",
        "feasibility_run_count",
        "construction_record_count",
        "current_stage",
        "recommended_next_step",
        "next_step_route",
        "blocked_reason",
        "last_updated_at",
    }
    assert expected_fields.issubset(data.keys())
