"""
Tests for the Absorption Metrics API endpoint (PR-V7-01).

Validates:
  - Endpoint HTTP contract (200 on valid project, 404 on missing project)
  - Response schema shape — all required fields present
  - Null-safe response for projects with no units
  - Absorption rate calculation from contract dates
  - Planned absorption rate derived from feasibility assumptions
  - IRR recalculation using actual contracted revenue
  - Revenue realized percentage
  - Auth requirement (401 when unauthenticated)
  - Source record immutability
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Shared hierarchy helpers (reused from test_api.py pattern)
# ---------------------------------------------------------------------------


def _create_project(
    client: TestClient, code: str = "PRJ-AM", name: str = "Absorption Metrics Project"
) -> str:
    resp = client.post("/api/v1/projects", json={"name": name, "code": code})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_unit(
    client: TestClient,
    proj_code: str = "PRJ-AM",
    unit_number: str = "101",
    proj_name: str = "Absorption Metrics Project",
) -> tuple[str, str]:
    """Create full hierarchy and return (project_id, unit_id)."""
    project_id = _create_project(client, proj_code, proj_name)
    phase_resp = client.post(
        "/api/v1/phases",
        json={"project_id": project_id, "name": "Phase 1", "sequence": 1},
    )
    assert phase_resp.status_code == 201, phase_resp.text
    phase_id = phase_resp.json()["id"]

    building_resp = client.post(
        f"/api/v1/phases/{phase_id}/buildings",
        json={"name": "Block A", "code": "BLK-A"},
    )
    assert building_resp.status_code == 201, building_resp.text
    building_id = building_resp.json()["id"]

    floor_resp = client.post(
        f"/api/v1/buildings/{building_id}/floors",
        json={"name": "Floor 1", "code": "FL-01", "sequence_number": 1},
    )
    assert floor_resp.status_code == 201, floor_resp.text
    floor_id = floor_resp.json()["id"]

    unit_resp = client.post(
        "/api/v1/units",
        json={
            "floor_id": floor_id,
            "unit_number": unit_number,
            "unit_type": "studio",
            "internal_area": 100.0,
        },
    )
    assert unit_resp.status_code == 201, unit_resp.text
    unit_id = unit_resp.json()["id"]
    return project_id, unit_id


def _create_buyer(client: TestClient, email: str = "buyer@am.com") -> str:
    resp = client.post(
        "/api/v1/sales/buyers",
        json={"full_name": "AM Buyer", "email": email, "phone": "+971500000088"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_contract(
    client: TestClient,
    unit_id: str,
    buyer_id: str,
    contract_number: str = "CNT-AM-001",
    price: float = 500_000.0,
    contract_date: str | None = None,
) -> str:
    payload = {
        "unit_id": unit_id,
        "buyer_id": buyer_id,
        "contract_number": contract_number,
        "contract_date": contract_date or str(date.today()),
        "contract_price": price,
    }
    resp = client.post("/api/v1/sales/contracts", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# 404 — missing project
# ---------------------------------------------------------------------------


def test_absorption_metrics_404_for_missing_project(client: TestClient):
    """GET /projects/{id}/absorption-metrics → 404 when project absent."""
    resp = client.get("/api/v1/projects/nonexistent-project-id/absorption-metrics")
    assert resp.status_code == 404
    assert "not found" in resp.json()["message"].lower()


# ---------------------------------------------------------------------------
# 401 — unauthenticated request
# ---------------------------------------------------------------------------


def test_absorption_metrics_requires_authentication(unauth_client: TestClient):
    """Endpoint must reject unauthenticated requests with 401/403."""
    resp = unauth_client.get("/api/v1/projects/some-id/absorption-metrics")
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Null-safe: project with no units
# ---------------------------------------------------------------------------


def test_absorption_metrics_no_units_returns_null_safe_response(client: TestClient):
    """Project with no units must return null-safe response (no error)."""
    project_id = _create_project(client, "PRJ-AMNOU", "AM No-Units Project")
    resp = client.get(f"/api/v1/projects/{project_id}/absorption-metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_units"] == 0
    assert data["sold_units"] == 0
    assert data["absorption_rate_per_month"] is None
    assert data["planned_absorption_rate_per_month"] is None
    assert data["revenue_timing_note"] is not None


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------


def test_absorption_metrics_response_shape(client: TestClient):
    """Response must include all required fields."""
    project_id = _create_project(client, "PRJ-AMSHP", "AM Shape Project")
    resp = client.get(f"/api/v1/projects/{project_id}/absorption-metrics")
    assert resp.status_code == 200
    data = resp.json()

    required_keys = [
        "project_id",
        "project_name",
        "project_code",
        "total_units",
        "sold_units",
        "reserved_units",
        "available_units",
        "absorption_rate_per_month",
        "planned_absorption_rate_per_month",
        "absorption_vs_plan_pct",
        "avg_selling_time_days",
        "contracted_revenue",
        "projected_revenue",
        "revenue_realized_pct",
        "planned_irr",
        "actual_irr_estimate",
        "irr_delta",
        "cashflow_delay_months",
        "revenue_timing_note",
    ]
    for key in required_keys:
        assert key in data, f"Missing key: {key}"

    assert data["project_id"] == project_id
    assert data["project_code"] == "PRJ-AMSHP"


# ---------------------------------------------------------------------------
# Absorption rate calculation from contract dates
# ---------------------------------------------------------------------------


def test_absorption_rate_calculated_from_contract_dates(client: TestClient, db_session):
    """Absorption rate is derived from first/last contract dates when >= 2 contracts."""
    from app.modules.units.models import Unit as UnitModel

    project_id = _create_project(client, "PRJ-AMRATE", "AM Rate Project")
    phase_resp = client.post(
        "/api/v1/phases",
        json={"project_id": project_id, "name": "Phase 1", "sequence": 1},
    )
    phase_id = phase_resp.json()["id"]
    building_resp = client.post(
        f"/api/v1/phases/{phase_id}/buildings",
        json={"name": "Block A", "code": "BLK-R"},
    )
    building_id = building_resp.json()["id"]
    floor_resp = client.post(
        f"/api/v1/buildings/{building_id}/floors",
        json={"name": "Floor 1", "code": "FL-R1", "sequence_number": 1},
    )
    floor_id = floor_resp.json()["id"]

    unit_ids = []
    for i in range(1, 4):
        u = client.post(
            "/api/v1/units",
            json={"floor_id": floor_id, "unit_number": str(i), "unit_type": "studio", "internal_area": 80.0},
        )
        unit_ids.append(u.json()["id"])

    buyer_id = _create_buyer(client, "buyer@amrate.com")

    # First contract: 60 days ago, second: today → 2 contracts over ~2 months
    first_date = str(date.today() - timedelta(days=61))
    second_date = str(date.today())
    _create_contract(client, unit_ids[0], buyer_id, "CNT-AMR-001", 400_000.0, first_date)
    buyer2_id = _create_buyer(client, "buyer2@amrate.com")
    _create_contract(client, unit_ids[1], buyer2_id, "CNT-AMR-002", 400_000.0, second_date)

    resp = client.get(f"/api/v1/projects/{project_id}/absorption-metrics")
    assert resp.status_code == 200
    data = resp.json()
    # Rate should be calculable (2 non-cancelled contracts with different dates)
    assert data["absorption_rate_per_month"] is not None
    assert data["absorption_rate_per_month"] > 0
    assert data["avg_selling_time_days"] is not None


def test_absorption_rate_null_when_fewer_than_2_contracts(client: TestClient):
    """Absorption rate must be null when project has fewer than 2 contracts."""
    project_id, unit_id = _create_unit(client, "PRJ-AM1CNT", "101", "AM One-Contract Project")
    buyer_id = _create_buyer(client, "buyer@am1cnt.com")
    _create_contract(client, unit_id, buyer_id, "CNT-AM1-001", 300_000.0)

    resp = client.get(f"/api/v1/projects/{project_id}/absorption-metrics")
    assert resp.status_code == 200
    data = resp.json()
    # Only 1 contract: absorption_rate and avg_selling_time must be null
    assert data["absorption_rate_per_month"] is None
    assert data["avg_selling_time_days"] is None


# ---------------------------------------------------------------------------
# Planned absorption rate from feasibility assumptions
# ---------------------------------------------------------------------------


def test_planned_absorption_rate_from_feasibility_run(client: TestClient):
    """Planned absorption rate is derived from feasibility assumptions when available."""
    project_id = _create_project(client, "PRJ-AMPLAN", "AM Plan Project")

    # Create a feasibility run with assumptions and calculate it
    run_resp = client.post(
        "/api/v1/feasibility/runs",
        json={"project_id": project_id, "scenario_name": "Base Case", "scenario_type": "base"},
    )
    assert run_resp.status_code == 201, run_resp.text
    run_id = run_resp.json()["id"]

    # Set assumptions: 10 units, 24 months development period → planned 10/24 ≈ 0.4167 units/month
    client.post(
        f"/api/v1/feasibility/runs/{run_id}/assumptions",
        json={
            "sellable_area_sqm": 1000.0,
            "avg_sale_price_per_sqm": 3000.0,
            "construction_cost_per_sqm": 800.0,
            "soft_cost_ratio": 0.10,
            "finance_cost_ratio": 0.05,
            "sales_cost_ratio": 0.02,
            "development_period_months": 24,
        },
    )
    # Calculate the run so it has a result
    client.post(f"/api/v1/feasibility/runs/{run_id}/calculate")

    # Create inventory matching total_units = 10
    phase_resp = client.post(
        "/api/v1/phases",
        json={"project_id": project_id, "name": "Phase 1", "sequence": 1},
    )
    phase_id = phase_resp.json()["id"]
    building_resp = client.post(
        f"/api/v1/phases/{phase_id}/buildings", json={"name": "Block A", "code": "BLK-P"}
    )
    building_id = building_resp.json()["id"]
    floor_resp = client.post(
        f"/api/v1/buildings/{building_id}/floors",
        json={"name": "Floor 1", "code": "FL-P1", "sequence_number": 1},
    )
    floor_id = floor_resp.json()["id"]
    for i in range(1, 11):
        client.post(
            "/api/v1/units",
            json={"floor_id": floor_id, "unit_number": str(i), "unit_type": "studio", "internal_area": 100.0},
        )

    resp = client.get(f"/api/v1/projects/{project_id}/absorption-metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["planned_absorption_rate_per_month"] is not None
    # 10 units / 24 months ≈ 0.4167
    assert abs(data["planned_absorption_rate_per_month"] - 10.0 / 24.0) < 0.01


# ---------------------------------------------------------------------------
# IRR recalculation using actual contracted revenue
# ---------------------------------------------------------------------------


def test_irr_recalculation_with_actuals(client: TestClient, db_session):
    """actual_irr_estimate should be computed when feasibility data is available."""
    from app.modules.units.models import Unit as UnitModel

    project_id = _create_project(client, "PRJ-AMIRR", "AM IRR Project")

    # Create feasibility run and calculate
    run_resp = client.post(
        "/api/v1/feasibility/runs",
        json={"project_id": project_id, "scenario_name": "Base Case", "scenario_type": "base"},
    )
    run_id = run_resp.json()["id"]
    client.post(
        f"/api/v1/feasibility/runs/{run_id}/assumptions",
        json={
            "sellable_area_sqm": 500.0,
            "avg_sale_price_per_sqm": 4000.0,
            "construction_cost_per_sqm": 1000.0,
            "soft_cost_ratio": 0.10,
            "finance_cost_ratio": 0.05,
            "sales_cost_ratio": 0.02,
            "development_period_months": 18,
        },
    )
    calc_resp = client.post(f"/api/v1/feasibility/runs/{run_id}/calculate")
    assert calc_resp.status_code in (200, 201), calc_resp.text

    # Create one unit and sell it
    phase_resp = client.post(
        "/api/v1/phases",
        json={"project_id": project_id, "name": "Phase 1", "sequence": 1},
    )
    phase_id = phase_resp.json()["id"]
    building_resp = client.post(
        f"/api/v1/phases/{phase_id}/buildings", json={"name": "Block A", "code": "BLK-I"}
    )
    building_id = building_resp.json()["id"]
    floor_resp = client.post(
        f"/api/v1/buildings/{building_id}/floors",
        json={"name": "Floor 1", "code": "FL-I1", "sequence_number": 1},
    )
    floor_id = floor_resp.json()["id"]
    unit_resp = client.post(
        "/api/v1/units",
        json={"floor_id": floor_id, "unit_number": "1", "unit_type": "studio", "internal_area": 100.0},
    )
    unit_id = unit_resp.json()["id"]
    buyer_id = _create_buyer(client, "buyer@amirr.com")
    _create_contract(client, unit_id, buyer_id, "CNT-AMIRR-001", 500_000.0)

    resp = client.get(f"/api/v1/projects/{project_id}/absorption-metrics")
    assert resp.status_code == 200
    data = resp.json()

    # With a calculated feasibility run, planned_irr should be present
    assert data["planned_irr"] is not None
    # actual_irr_estimate should be computed using contracted_revenue as GDV
    assert data["actual_irr_estimate"] is not None
    # irr_delta = actual - planned
    if data["irr_delta"] is not None:
        assert abs(data["irr_delta"] - (data["actual_irr_estimate"] - data["planned_irr"])) < 1e-4


# ---------------------------------------------------------------------------
# Revenue realized percentage
# ---------------------------------------------------------------------------


def test_revenue_realized_pct_with_feasibility_result(client: TestClient):
    """revenue_realized_pct should equal contracted_revenue / projected_revenue * 100."""
    project_id = _create_project(client, "PRJ-AMREV", "AM Revenue Project")

    run_resp = client.post(
        "/api/v1/feasibility/runs",
        json={"project_id": project_id, "scenario_name": "Base Case", "scenario_type": "base"},
    )
    run_id = run_resp.json()["id"]
    client.post(
        f"/api/v1/feasibility/runs/{run_id}/assumptions",
        json={
            "sellable_area_sqm": 1000.0,
            "avg_sale_price_per_sqm": 3000.0,
            "construction_cost_per_sqm": 800.0,
            "soft_cost_ratio": 0.10,
            "finance_cost_ratio": 0.05,
            "sales_cost_ratio": 0.02,
            "development_period_months": 24,
        },
    )
    client.post(f"/api/v1/feasibility/runs/{run_id}/calculate")

    # Create one unit and sell it at a known price
    phase_resp = client.post(
        "/api/v1/phases",
        json={"project_id": project_id, "name": "Phase 1", "sequence": 1},
    )
    phase_id = phase_resp.json()["id"]
    building_resp = client.post(
        f"/api/v1/phases/{phase_id}/buildings", json={"name": "Block A", "code": "BLK-RV"}
    )
    building_id = building_resp.json()["id"]
    floor_resp = client.post(
        f"/api/v1/buildings/{building_id}/floors",
        json={"name": "Floor 1", "code": "FL-RV1", "sequence_number": 1},
    )
    floor_id = floor_resp.json()["id"]
    unit_resp = client.post(
        "/api/v1/units",
        json={"floor_id": floor_id, "unit_number": "1", "unit_type": "studio", "internal_area": 100.0},
    )
    unit_id = unit_resp.json()["id"]
    buyer_id = _create_buyer(client, "buyer@amrev.com")
    _create_contract(client, unit_id, buyer_id, "CNT-AMRV-001", 1_500_000.0)

    resp = client.get(f"/api/v1/projects/{project_id}/absorption-metrics")
    assert resp.status_code == 200
    data = resp.json()

    assert data["contracted_revenue"] == pytest.approx(1_500_000.0, abs=0.01)
    assert data["projected_revenue"] is not None
    assert data["revenue_realized_pct"] is not None
    # Check it matches contracted/projected * 100
    expected_pct = (data["contracted_revenue"] / data["projected_revenue"]) * 100
    assert data["revenue_realized_pct"] == pytest.approx(expected_pct, abs=0.1)


# ---------------------------------------------------------------------------
# Source record immutability
# ---------------------------------------------------------------------------


def test_absorption_metrics_does_not_mutate_source_records(client: TestClient):
    """Fetching absorption metrics must not alter any project or unit records."""
    project_id, unit_id = _create_unit(client, "PRJ-AMMUT", "101", "AM Immutable Project")

    unit_before = client.get(f"/api/v1/units/{unit_id}").json()
    resp = client.get(f"/api/v1/projects/{project_id}/absorption-metrics")
    assert resp.status_code == 200
    unit_after = client.get(f"/api/v1/units/{unit_id}").json()
    assert unit_before["status"] == unit_after["status"]
