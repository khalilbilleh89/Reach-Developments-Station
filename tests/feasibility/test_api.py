"""
Tests for the feasibility API endpoints.

Validates HTTP behaviour, request/response contracts, and full workflow.
"""

import pytest
from fastapi.testclient import TestClient


def _create_project(client: TestClient, code: str = "PRJ-FAPI") -> str:
    resp = client.post("/api/v1/projects", json={"name": "Feasibility Project", "code": code})
    assert resp.status_code == 201
    return resp.json()["id"]


_VALID_ASSUMPTIONS_PAYLOAD = {
    "sellable_area_sqm": 1000.0,
    "avg_sale_price_per_sqm": 3000.0,
    "construction_cost_per_sqm": 800.0,
    "soft_cost_ratio": 0.10,
    "finance_cost_ratio": 0.05,
    "sales_cost_ratio": 0.03,
    "development_period_months": 24,
}


# ---------------------------------------------------------------------------
# Run creation
# ---------------------------------------------------------------------------

def test_create_run(client: TestClient):
    """POST /api/v1/feasibility/runs should create and return a run."""
    project_id = _create_project(client)
    resp = client.post(
        "/api/v1/feasibility/runs",
        json={"project_id": project_id, "scenario_name": "Base Case", "scenario_type": "base"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["project_id"] == project_id
    assert data["scenario_name"] == "Base Case"
    assert data["scenario_type"] == "base"
    assert "id" in data


def test_create_run_invalid_project(client: TestClient):
    """POST /api/v1/feasibility/runs with non-existent project should return 404."""
    resp = client.post(
        "/api/v1/feasibility/runs",
        json={"project_id": "no-such-project", "scenario_name": "Test"},
    )
    assert resp.status_code == 404


def test_get_run(client: TestClient):
    """GET /api/v1/feasibility/runs/{id} should return the run."""
    project_id = _create_project(client, code="PRJ-FGET")
    run_id = client.post(
        "/api/v1/feasibility/runs",
        json={"project_id": project_id, "scenario_name": "Base"},
    ).json()["id"]
    resp = client.get(f"/api/v1/feasibility/runs/{run_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == run_id


def test_get_run_not_found(client: TestClient):
    """GET /api/v1/feasibility/runs/{id} with unknown id should return 404."""
    resp = client.get("/api/v1/feasibility/runs/no-such-run")
    assert resp.status_code == 404


def test_list_runs_filtered_by_project(client: TestClient):
    """GET /api/v1/feasibility/runs?project_id=... should return matching runs."""
    project_id = _create_project(client, code="PRJ-FLIST")
    client.post(
        "/api/v1/feasibility/runs",
        json={"project_id": project_id, "scenario_name": "Run 1"},
    )
    client.post(
        "/api/v1/feasibility/runs",
        json={"project_id": project_id, "scenario_name": "Run 2"},
    )
    resp = client.get(f"/api/v1/feasibility/runs?project_id={project_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


# ---------------------------------------------------------------------------
# Assumptions
# ---------------------------------------------------------------------------

def test_upsert_assumptions(client: TestClient):
    """POST /api/v1/feasibility/runs/{id}/assumptions should store assumptions."""
    project_id = _create_project(client, code="PRJ-FASM")
    run_id = client.post(
        "/api/v1/feasibility/runs",
        json={"project_id": project_id, "scenario_name": "Base"},
    ).json()["id"]
    resp = client.post(
        f"/api/v1/feasibility/runs/{run_id}/assumptions",
        json=_VALID_ASSUMPTIONS_PAYLOAD,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["run_id"] == run_id
    assert data["sellable_area_sqm"] == pytest.approx(1000.0)
    assert data["avg_sale_price_per_sqm"] == pytest.approx(3000.0)


def test_upsert_assumptions_invalid_run(client: TestClient):
    """POST /api/v1/feasibility/runs/{id}/assumptions with unknown run should return 404."""
    resp = client.post(
        "/api/v1/feasibility/runs/no-such-run/assumptions",
        json=_VALID_ASSUMPTIONS_PAYLOAD,
    )
    assert resp.status_code == 404


def test_get_assumptions(client: TestClient):
    """GET /api/v1/feasibility/runs/{id}/assumptions should return stored assumptions."""
    project_id = _create_project(client, code="PRJ-FGETASM")
    run_id = client.post(
        "/api/v1/feasibility/runs",
        json={"project_id": project_id, "scenario_name": "Base"},
    ).json()["id"]
    client.post(f"/api/v1/feasibility/runs/{run_id}/assumptions", json=_VALID_ASSUMPTIONS_PAYLOAD)
    resp = client.get(f"/api/v1/feasibility/runs/{run_id}/assumptions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["development_period_months"] == 24


def test_get_assumptions_not_set(client: TestClient):
    """GET /api/v1/feasibility/runs/{id}/assumptions with no assumptions should return 404."""
    project_id = _create_project(client, code="PRJ-FNOASM")
    run_id = client.post(
        "/api/v1/feasibility/runs",
        json={"project_id": project_id, "scenario_name": "Base"},
    ).json()["id"]
    resp = client.get(f"/api/v1/feasibility/runs/{run_id}/assumptions")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Calculate and results
# ---------------------------------------------------------------------------

def test_calculate_and_get_results(client: TestClient):
    """Full workflow: create run → set assumptions → calculate → get results."""
    project_id = _create_project(client, code="PRJ-FCALC")
    run_id = client.post(
        "/api/v1/feasibility/runs",
        json={"project_id": project_id, "scenario_name": "Base"},
    ).json()["id"]
    client.post(f"/api/v1/feasibility/runs/{run_id}/assumptions", json=_VALID_ASSUMPTIONS_PAYLOAD)

    calc_resp = client.post(f"/api/v1/feasibility/runs/{run_id}/calculate")
    assert calc_resp.status_code == 200
    calc_data = calc_resp.json()
    assert calc_data["gdv"] == pytest.approx(3_000_000.0)
    assert calc_data["total_cost"] == pytest.approx(1_010_000.0)
    assert calc_data["developer_profit"] == pytest.approx(1_990_000.0)

    results_resp = client.get(f"/api/v1/feasibility/runs/{run_id}/results")
    assert results_resp.status_code == 200
    results_data = results_resp.json()
    assert results_data["run_id"] == run_id
    assert results_data["gdv"] == pytest.approx(3_000_000.0)


def test_calculate_without_assumptions_returns_422(client: TestClient):
    """POST /api/v1/feasibility/runs/{id}/calculate without assumptions should return 422."""
    project_id = _create_project(client, code="PRJ-FCALCNOASM")
    run_id = client.post(
        "/api/v1/feasibility/runs",
        json={"project_id": project_id, "scenario_name": "Base"},
    ).json()["id"]
    resp = client.post(f"/api/v1/feasibility/runs/{run_id}/calculate")
    assert resp.status_code == 422


def test_get_results_before_calculate_returns_404(client: TestClient):
    """GET /api/v1/feasibility/runs/{id}/results before calculation should return 404."""
    project_id = _create_project(client, code="PRJ-FNORES")
    run_id = client.post(
        "/api/v1/feasibility/runs",
        json={"project_id": project_id, "scenario_name": "Base"},
    ).json()["id"]
    resp = client.get(f"/api/v1/feasibility/runs/{run_id}/results")
    assert resp.status_code == 404


def test_scenario_type_preserved(client: TestClient):
    """Scenario type should be stored and returned correctly."""
    project_id = _create_project(client, code="PRJ-FTYPE")
    resp = client.post(
        "/api/v1/feasibility/runs",
        json={"project_id": project_id, "scenario_name": "Upside", "scenario_type": "upside"},
    )
    assert resp.status_code == 201
    assert resp.json()["scenario_type"] == "upside"


def test_result_payload_is_serializable(client: TestClient):
    """Result response should have all required fields with non-null values."""
    project_id = _create_project(client, code="PRJ-FSER")
    run_id = client.post(
        "/api/v1/feasibility/runs",
        json={"project_id": project_id, "scenario_name": "Base"},
    ).json()["id"]
    client.post(f"/api/v1/feasibility/runs/{run_id}/assumptions", json=_VALID_ASSUMPTIONS_PAYLOAD)
    resp = client.post(f"/api/v1/feasibility/runs/{run_id}/calculate")
    data = resp.json()
    required_fields = [
        "id", "run_id", "gdv", "construction_cost", "soft_cost",
        "finance_cost", "sales_cost", "total_cost", "developer_profit",
        "profit_margin", "irr_estimate", "created_at", "updated_at",
    ]
    for field in required_fields:
        assert field in data, f"Missing field: {field}"
        assert data[field] is not None, f"Field is None: {field}"
