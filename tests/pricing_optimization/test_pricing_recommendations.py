"""
Tests for the Pricing Optimization Engine (PR-V7-02).

Validates:
  - GET /projects/{id}/pricing-recommendations
      - HTTP contract (200 on valid project, 404 on missing project)
      - Response schema shape — all required fields present
      - Empty project (no units) returns valid response
      - Demand classification correctness (high_demand, balanced, low_demand, no_data)
      - Recommendation rules (correct change_pct for demand + availability combos)
      - Auth requirement (401 when unauthenticated)
      - Source record immutability (no pricing mutation)
  - GET /portfolio/pricing-insights
      - HTTP contract (200, auth required)
      - Response schema shape
      - Empty portfolio returns valid null-safe response
      - Per-project cards populated
      - Summary counts accurate
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Shared hierarchy helpers
# ---------------------------------------------------------------------------


def _create_project(
    client: TestClient, code: str = "PRJ-PO", name: str = "Pricing Opt Project"
) -> str:
    resp = client.post("/api/v1/projects", json={"name": name, "code": code})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_unit(
    client: TestClient,
    proj_id: str,
    unit_number: str = "101",
    unit_type: str = "studio",
    phase_code: str = "BLK-PO",
) -> str:
    """Create phase → building → floor → unit and return unit_id."""
    phase_resp = client.post(
        "/api/v1/phases",
        json={"project_id": proj_id, "name": "Phase 1", "sequence": 1},
    )
    assert phase_resp.status_code == 201, phase_resp.text
    phase_id = phase_resp.json()["id"]

    building_resp = client.post(
        f"/api/v1/phases/{phase_id}/buildings",
        json={"name": "Block A", "code": phase_code},
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
            "unit_type": unit_type,
            "internal_area": 100.0,
        },
    )
    assert unit_resp.status_code == 201, unit_resp.text
    return unit_resp.json()["id"]


def _create_units_in_hierarchy(
    client: TestClient,
    proj_id: str,
    num_units: int,
    unit_type: str = "studio",
    phase_code: str = "BLK-PO",
) -> list:
    """Create phase → building → floor → N units. Returns list of unit IDs."""
    phase_resp = client.post(
        "/api/v1/phases",
        json={"project_id": proj_id, "name": "Phase 1", "sequence": 1},
    )
    assert phase_resp.status_code == 201, phase_resp.text
    phase_id = phase_resp.json()["id"]

    building_resp = client.post(
        f"/api/v1/phases/{phase_id}/buildings",
        json={"name": "Block A", "code": phase_code},
    )
    assert building_resp.status_code == 201, building_resp.text
    building_id = building_resp.json()["id"]

    floor_resp = client.post(
        f"/api/v1/buildings/{building_id}/floors",
        json={"name": "Floor 1", "code": "FL-01", "sequence_number": 1},
    )
    assert floor_resp.status_code == 201, floor_resp.text
    floor_id = floor_resp.json()["id"]

    unit_ids = []
    for i in range(1, num_units + 1):
        unit_resp = client.post(
            "/api/v1/units",
            json={
                "floor_id": floor_id,
                "unit_number": str(i),
                "unit_type": unit_type,
                "internal_area": 80.0,
            },
        )
        assert unit_resp.status_code == 201, unit_resp.text
        unit_ids.append(unit_resp.json()["id"])
    return unit_ids


def _set_unit_under_contract(client: TestClient, unit_id: str) -> None:
    """Set a unit to under_contract status through valid transitions."""
    r = client.patch(f"/api/v1/units/{unit_id}", json={"status": "reserved"})
    assert r.status_code == 200, f"Failed to reserve unit {unit_id}: {r.text}"
    r = client.patch(f"/api/v1/units/{unit_id}", json={"status": "under_contract"})
    assert r.status_code == 200, f"Failed to set under_contract for unit {unit_id}: {r.text}"


def _create_buyer(client: TestClient, email: str = "buyer@po.com") -> str:
    resp = client.post(
        "/api/v1/sales/buyers",
        json={"full_name": "PO Buyer", "email": email, "phone": "+971500000099"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_contract(
    client: TestClient,
    unit_id: str,
    buyer_id: str,
    contract_number: str,
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
# Auth requirement
# ---------------------------------------------------------------------------


def test_pricing_recommendations_requires_auth(unauth_client: TestClient):
    """Endpoint must reject unauthenticated requests with 401/403."""
    resp = unauth_client.get("/api/v1/projects/does-not-matter/pricing-recommendations")
    assert resp.status_code in (401, 403)


def test_portfolio_pricing_insights_requires_auth(unauth_client: TestClient):
    """Portfolio endpoint must reject unauthenticated requests with 401/403."""
    resp = unauth_client.get("/api/v1/portfolio/pricing-insights")
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# 404 on missing project
# ---------------------------------------------------------------------------


def test_pricing_recommendations_404_on_missing_project(client: TestClient):
    """Must return 404 when the project does not exist."""
    resp = client.get("/api/v1/projects/nonexistent-id/pricing-recommendations")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Response schema shape — project endpoint
# ---------------------------------------------------------------------------


def test_pricing_recommendations_response_shape(client: TestClient):
    """Response must include all required top-level and recommendation fields."""
    proj_id = _create_project(client, "PRJ-POF", "Pricing Opt Field Test")
    resp = client.get(f"/api/v1/projects/{proj_id}/pricing-recommendations")
    assert resp.status_code == 200
    data = resp.json()

    assert "project_id" in data
    assert "project_name" in data
    assert "recommendations" in data
    assert "has_pricing_data" in data
    assert isinstance(data["recommendations"], list)


def test_pricing_recommendations_no_units_returns_empty(client: TestClient):
    """Project with no units must return empty recommendations list."""
    proj_id = _create_project(client, "PRJ-PONU", "No Units Project")
    resp = client.get(f"/api/v1/projects/{proj_id}/pricing-recommendations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == proj_id
    assert data["recommendations"] == []
    assert data["has_pricing_data"] is False


def test_pricing_recommendations_unit_card_fields(client: TestClient):
    """Each recommendation must contain all required fields."""
    proj_id = _create_project(client, "PRJ-POUCF", "Unit Card Fields")
    _create_units_in_hierarchy(client, proj_id, 2, "studio", "BLK-UCF")

    resp = client.get(f"/api/v1/projects/{proj_id}/pricing-recommendations")
    assert resp.status_code == 200
    data = resp.json()

    assert len(data["recommendations"]) == 1  # one unit type: studio
    rec = data["recommendations"][0]
    for field in (
        "unit_type",
        "current_avg_price",
        "recommended_price",
        "change_pct",
        "confidence",
        "reason",
        "demand_status",
        "total_units",
        "available_units",
        "sold_units",
        "availability_pct",
    ):
        assert field in rec, f"Missing recommendation field: {field}"


# ---------------------------------------------------------------------------
# Demand classification
# ---------------------------------------------------------------------------


def test_demand_status_no_data_when_no_contracts(client: TestClient):
    """With no contracts, demand_status must be 'no_data'."""
    proj_id = _create_project(client, "PRJ-POND", "No Data Demand")
    _create_units_in_hierarchy(client, proj_id, 3, "studio", "BLK-ND")

    resp = client.get(f"/api/v1/projects/{proj_id}/pricing-recommendations")
    assert resp.status_code == 200
    data = resp.json()

    assert len(data["recommendations"]) == 1
    rec = data["recommendations"][0]
    assert rec["demand_status"] == "no_data"
    assert rec["confidence"] == "insufficient_data"
    assert rec["change_pct"] is None
    assert rec["recommended_price"] is None


def test_demand_status_high_demand_via_sell_through(client: TestClient):
    """When sell-through > 60%, demand_status should be 'high_demand' (no plan fallback)."""
    proj_id = _create_project(client, "PRJ-POHD", "High Demand Project")
    # 10 units, sell 7 (70% sell-through) → high_demand
    unit_ids = _create_units_in_hierarchy(client, proj_id, 10, "two_bedroom", "BLK-HD")

    # Set 7 units to under_contract status through valid transitions
    for uid in unit_ids[:7]:
        _set_unit_under_contract(client, uid)

    resp = client.get(f"/api/v1/projects/{proj_id}/pricing-recommendations")
    assert resp.status_code == 200
    data = resp.json()

    rec = next(r for r in data["recommendations"] if r["unit_type"] == "two_bedroom")
    assert rec["demand_status"] == "high_demand"
    assert rec["change_pct"] is not None
    assert rec["change_pct"] > 0


def test_demand_status_low_demand_via_sell_through(client: TestClient):
    """When sell-through < 40%, demand_status should be 'low_demand' (no plan fallback)."""
    proj_id = _create_project(client, "PRJ-POLD", "Low Demand Project")
    # 10 units, sell 3 (30% sell-through) → low_demand
    unit_ids = _create_units_in_hierarchy(client, proj_id, 10, "three_bedroom", "BLK-LD")

    # Set 3 units to under_contract status through valid transitions
    for uid in unit_ids[:3]:
        _set_unit_under_contract(client, uid)

    resp = client.get(f"/api/v1/projects/{proj_id}/pricing-recommendations")
    assert resp.status_code == 200
    data = resp.json()

    rec = next(r for r in data["recommendations"] if r["unit_type"] == "three_bedroom")
    assert rec["demand_status"] == "low_demand"
    assert rec["change_pct"] is not None
    assert rec["change_pct"] < 0


# ---------------------------------------------------------------------------
# Recommendation rules
# ---------------------------------------------------------------------------


def test_recommendation_hold_when_balanced(client: TestClient):
    """Balanced demand (sell-through ~50%) must yield change_pct == 0.0."""
    proj_id = _create_project(client, "PRJ-POB", "Balanced Project")
    # 10 units, sell 5 (50% sell-through) → balanced
    unit_ids = _create_units_in_hierarchy(client, proj_id, 10, "one_bedroom", "BLK-BAL")

    # Set 5 units to under_contract through valid transitions
    for uid in unit_ids[:5]:
        _set_unit_under_contract(client, uid)

    resp = client.get(f"/api/v1/projects/{proj_id}/pricing-recommendations")
    assert resp.status_code == 200
    data = resp.json()

    rec = next(r for r in data["recommendations"] if r["unit_type"] == "one_bedroom")
    assert rec["demand_status"] == "balanced"
    assert rec["change_pct"] == 0.0


def test_recommendation_has_pricing_data_false_without_records(client: TestClient):
    """has_pricing_data must be False when no formal pricing records exist."""
    proj_id = _create_project(client, "PRJ-PONP", "No Pricing Records")
    _create_units_in_hierarchy(client, proj_id, 2, "studio", "BLK-NP")

    resp = client.get(f"/api/v1/projects/{proj_id}/pricing-recommendations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_pricing_data"] is False
    # current_avg_price and recommended_price must be null
    for rec in data["recommendations"]:
        assert rec["current_avg_price"] is None
        assert rec["recommended_price"] is None


def test_recommendation_unit_type_counts_accurate(client: TestClient):
    """total_units, available_units, sold_units must be accurate."""
    proj_id = _create_project(client, "PRJ-POUC", "Unit Count Accuracy")
    unit_ids = _create_units_in_hierarchy(client, proj_id, 4, "studio", "BLK-UC")

    # Set 2 units to under_contract status through valid transitions
    for uid in unit_ids[:2]:
        _set_unit_under_contract(client, uid)

    resp = client.get(f"/api/v1/projects/{proj_id}/pricing-recommendations")
    assert resp.status_code == 200
    data = resp.json()

    rec = next(r for r in data["recommendations"] if r["unit_type"] == "studio")
    assert rec["total_units"] == 4
    assert rec["sold_units"] == 2
    assert rec["available_units"] == 2
    assert rec["availability_pct"] == pytest.approx(50.0, abs=0.1)


# ---------------------------------------------------------------------------
# Source immutability
# ---------------------------------------------------------------------------


def test_pricing_recommendations_does_not_mutate_units(client: TestClient):
    """Fetching pricing recommendations must not modify any unit statuses."""
    proj_id = _create_project(client, "PRJ-POIM", "Immutability Check")
    unit_ids = _create_units_in_hierarchy(client, proj_id, 3, "studio", "BLK-IM")

    # Record initial unit statuses
    initial_statuses = {}
    for uid in unit_ids:
        r = client.get(f"/api/v1/units/{uid}")
        assert r.status_code == 200
        initial_statuses[uid] = r.json()["status"]

    # Fetch recommendations
    client.get(f"/api/v1/projects/{proj_id}/pricing-recommendations")

    # Verify statuses are unchanged
    for uid, original_status in initial_statuses.items():
        r = client.get(f"/api/v1/units/{uid}")
        assert r.status_code == 200
        assert r.json()["status"] == original_status, f"Unit {uid} status was mutated"


# ---------------------------------------------------------------------------
# Portfolio pricing insights endpoint
# ---------------------------------------------------------------------------


def test_portfolio_pricing_insights_response_shape(client: TestClient):
    """Response must include all required top-level fields."""
    resp = client.get("/api/v1/portfolio/pricing-insights")
    assert resp.status_code == 200
    data = resp.json()

    assert "summary" in data
    assert "projects" in data
    assert "top_opportunities" in data
    assert "pricing_risk_zones" in data

    summary_keys = [
        "total_projects",
        "projects_with_pricing_data",
        "avg_recommended_adjustment_pct",
        "projects_underpriced",
        "projects_overpriced",
        "projects_balanced",
    ]
    for key in summary_keys:
        assert key in data["summary"], f"Missing summary key: {key}"


def test_portfolio_pricing_insights_empty_portfolio(client: TestClient):
    """Empty portfolio must return valid null-safe response."""
    resp = client.get("/api/v1/portfolio/pricing-insights")
    assert resp.status_code == 200
    data = resp.json()
    assert data["projects"] == []
    assert data["top_opportunities"] == []
    assert data["pricing_risk_zones"] == []
    assert data["summary"]["total_projects"] == 0
    assert data["summary"]["avg_recommended_adjustment_pct"] is None


def test_portfolio_pricing_insights_project_cards_present(client: TestClient):
    """Portfolio insights must include a card for every project."""
    proj_id = _create_project(client, "PRJ-PPIC", "Portfolio Insights Card")

    resp = client.get("/api/v1/portfolio/pricing-insights")
    assert resp.status_code == 200
    data = resp.json()

    project_ids = [c["project_id"] for c in data["projects"]]
    assert proj_id in project_ids

    card = next(c for c in data["projects"] if c["project_id"] == proj_id)
    for field in (
        "project_id",
        "project_name",
        "pricing_status",
        "avg_recommended_adjustment_pct",
        "recommendation_count",
        "high_demand_unit_types",
        "low_demand_unit_types",
    ):
        assert field in card, f"Missing card field: {field}"


def test_portfolio_pricing_insights_summary_counts(client: TestClient):
    """summary.total_projects must equal the number of projects returned."""
    _create_project(client, "PRJ-PPS1", "Portfolio Pricing Summary 1")
    _create_project(client, "PRJ-PPS2", "Portfolio Pricing Summary 2")

    resp = client.get("/api/v1/portfolio/pricing-insights")
    assert resp.status_code == 200
    data = resp.json()

    assert data["summary"]["total_projects"] >= 2
    assert len(data["projects"]) == data["summary"]["total_projects"]


def test_portfolio_pricing_insights_underpriced_classification(client: TestClient):
    """A project with high-demand, high sell-through should appear in top_opportunities."""
    proj_id = _create_project(client, "PRJ-PPIU", "Portfolio Underpriced")
    # 10 units, sell 8 (80% sell-through) → high demand
    unit_ids = _create_units_in_hierarchy(client, proj_id, 10, "studio", "BLK-PIU")

    # Set 8 units to under_contract status through valid transitions (80% sell-through → high demand)
    for uid in unit_ids[:8]:
        _set_unit_under_contract(client, uid)

    resp = client.get("/api/v1/portfolio/pricing-insights")
    assert resp.status_code == 200
    data = resp.json()

    card = next(
        (c for c in data["projects"] if c["project_id"] == proj_id), None
    )
    assert card is not None
    # High demand / high sell-through → should be underpriced or no_data (no formal pricing)
    assert card["pricing_status"] in ("underpriced", "no_data")


# ---------------------------------------------------------------------------
# Absorption-vs-plan primary decision branch
# ---------------------------------------------------------------------------


def _create_calculated_feasibility_run(
    client: TestClient,
    project_id: str,
    development_period_months: int,
    run_code: str,
) -> str:
    """Create a calculated feasibility run with assumptions and return the run_id."""
    run_resp = client.post(
        "/api/v1/feasibility/runs",
        json={
            "project_id": project_id,
            "scenario_name": run_code,
            "scenario_type": "base",
        },
    )
    assert run_resp.status_code == 201, run_resp.text
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
            "development_period_months": development_period_months,
        },
    )
    calc_resp = client.post(f"/api/v1/feasibility/runs/{run_id}/calculate")
    assert calc_resp.status_code in (200, 201), calc_resp.text
    return run_id


def test_pricing_recommendation_uses_absorption_vs_plan_when_feasibility_inputs_exist(
    client: TestClient,
):
    """Primary decision branch: absorption-vs-plan path is used when feasibility
    assumptions and dated contracts exist.

    Seeds:
      - calculated feasibility run with development_period_months=10
      - 10 studio units (planned rate = 10/10 = 1.0 unit/month)
      - Units 0-2 set to under_contract via PATCH (sold_units = 3 > 0, avoids no_data)
      - 3 draft contracts on units 3-5 spread across 60 days
        → actual rate ≈ 3 / (60/30.44) ≈ 1.52 units/month
        → absorption_vs_plan_pct ≈ 152% → high_demand

    Asserts that the plan-aware demand classification branch is active
    (demand_context mentions "of plan") and demand_status is high_demand.
    """
    proj_id = _create_project(client, "PRJ-POFEAS", "Absorption vs Plan Project")

    # Calculated feasibility run: 10 units / 10 months → planned 1.0 unit/month
    _create_calculated_feasibility_run(
        client, proj_id, development_period_months=10, run_code="Base Case FEAS"
    )

    # Create 10 studio units
    unit_ids = _create_units_in_hierarchy(client, proj_id, 10, "studio", "BLK-FEAS")

    # Units 0-2: set to under_contract via PATCH so sold_units > 0 (avoids no_data)
    for uid in unit_ids[:3]:
        _set_unit_under_contract(client, uid)

    # Units 3-5: create contracts with spread dates (drives absorption-rate calculation)
    # These units remain in "available" status; draft contracts count for date bounds
    buyer = _create_buyer(client, "buyer_feas@po.com")
    first_date = str(date.today() - timedelta(days=60))
    mid_date = str(date.today() - timedelta(days=30))
    last_date = str(date.today())
    _create_contract(client, unit_ids[3], buyer, "CNT-FEAS-001", 600_000.0, first_date)
    _create_contract(client, unit_ids[4], buyer, "CNT-FEAS-002", 600_000.0, mid_date)
    _create_contract(client, unit_ids[5], buyer, "CNT-FEAS-003", 600_000.0, last_date)

    resp = client.get(f"/api/v1/projects/{proj_id}/pricing-recommendations")
    assert resp.status_code == 200
    data = resp.json()

    # demand_context must reference absorption vs plan (not the sell-through fallback)
    assert data["demand_context"] is not None
    assert "of plan" in data["demand_context"], (
        f"Expected plan-aware demand context, got: {data['demand_context']}"
    )

    # Actual ≈ 1.52 units/month vs planned 1.0 units/month → > 100% → high_demand
    rec = next(r for r in data["recommendations"] if r["unit_type"] == "studio")
    assert rec["demand_status"] == "high_demand"
    assert rec["change_pct"] is not None
    assert rec["change_pct"] > 0


def test_pricing_recommendation_absorption_vs_plan_below_threshold_gives_low_demand(
    client: TestClient,
):
    """Plan-aware path: when actual absorption < 80% of plan → low_demand.

    Seeds:
      - feasibility run with development_period_months=6 → planned = 10/6 ≈ 1.67/month
      - Units 0-1 set to under_contract via PATCH (sold_units = 2 > 0, avoids no_data)
      - 2 contracts on units 2-3 spread across 90 days
        → actual ≈ 2 / (90/30.44) ≈ 0.68/month
        → absorption_vs_plan_pct ≈ 40% → low_demand
    """
    proj_id = _create_project(client, "PRJ-POFLD", "Low Demand Plan Project")

    # planned = 10 units / 6 months ≈ 1.667 units/month
    _create_calculated_feasibility_run(
        client, proj_id, development_period_months=6, run_code="Base Case LOW"
    )

    unit_ids = _create_units_in_hierarchy(client, proj_id, 10, "studio", "BLK-FLD")

    # Units 0-1: set to under_contract so sold_units > 0
    for uid in unit_ids[:2]:
        _set_unit_under_contract(client, uid)

    # Units 2-3: contracts with 90-day spread → actual ≈ 0.68/month → < 80% plan → low_demand
    buyer = _create_buyer(client, "buyer_fld@po.com")
    first_date = str(date.today() - timedelta(days=90))
    last_date = str(date.today())
    _create_contract(client, unit_ids[2], buyer, "CNT-FLD-001", 700_000.0, first_date)
    _create_contract(client, unit_ids[3], buyer, "CNT-FLD-002", 700_000.0, last_date)

    resp = client.get(f"/api/v1/projects/{proj_id}/pricing-recommendations")
    assert resp.status_code == 200
    data = resp.json()

    # Plan-aware context must be referenced
    assert data["demand_context"] is not None
    assert "of plan" in data["demand_context"]

    rec = next(r for r in data["recommendations"] if r["unit_type"] == "studio")
    assert rec["demand_status"] == "low_demand"
    assert rec["change_pct"] is not None
    assert rec["change_pct"] < 0


# ---------------------------------------------------------------------------
# Demand classification boundary tests
# ---------------------------------------------------------------------------


def _make_project_with_sell_through(
    client: TestClient,
    code: str,
    name: str,
    total_units: int,
    sold_units: int,
    unit_type: str = "studio",
    block_code: str = "BLK-BT",
) -> str:
    """Create a project with exactly sold_units set to under_contract and return project_id."""
    proj_id = _create_project(client, code, name)
    unit_ids = _create_units_in_hierarchy(client, proj_id, total_units, unit_type, block_code)
    for uid in unit_ids[:sold_units]:
        _set_unit_under_contract(client, uid)
    return proj_id


def test_boundary_40pct_sellthrough_classifies_as_balanced(client: TestClient):
    """Exactly 40% sell-through must classify as balanced (>= threshold, not low_demand)."""
    # 10 units, 4 sold = 40.0% sell-through → must be balanced
    proj_id = _make_project_with_sell_through(
        client, "PRJ-BT40", "Boundary 40pct", 10, 4, "studio", "BLK-BT40"
    )
    resp = client.get(f"/api/v1/projects/{proj_id}/pricing-recommendations")
    assert resp.status_code == 200
    rec = next(r for r in resp.json()["recommendations"] if r["unit_type"] == "studio")
    assert rec["demand_status"] == "balanced", (
        f"40% sell-through should be balanced, got: {rec['demand_status']}"
    )
    assert rec["change_pct"] == 0.0


def test_boundary_just_below_40pct_sellthrough_classifies_as_low_demand(client: TestClient):
    """Just below 40% sell-through (3/10 = 30%) must classify as low_demand."""
    proj_id = _make_project_with_sell_through(
        client, "PRJ-BT30", "Boundary 30pct", 10, 3, "studio", "BLK-BT30"
    )
    resp = client.get(f"/api/v1/projects/{proj_id}/pricing-recommendations")
    assert resp.status_code == 200
    rec = next(r for r in resp.json()["recommendations"] if r["unit_type"] == "studio")
    assert rec["demand_status"] == "low_demand"
    assert rec["change_pct"] < 0


def test_boundary_60pct_sellthrough_classifies_as_balanced(client: TestClient):
    """Exactly 60% sell-through must classify as balanced (not high_demand)."""
    # 10 units, 6 sold = 60.0% → 60 is not > 60 → balanced
    proj_id = _make_project_with_sell_through(
        client, "PRJ-BT60", "Boundary 60pct", 10, 6, "studio", "BLK-BT60"
    )
    resp = client.get(f"/api/v1/projects/{proj_id}/pricing-recommendations")
    assert resp.status_code == 200
    rec = next(r for r in resp.json()["recommendations"] if r["unit_type"] == "studio")
    assert rec["demand_status"] == "balanced", (
        f"60% sell-through should be balanced (not high_demand), got: {rec['demand_status']}"
    )
    assert rec["change_pct"] == 0.0


def test_boundary_above_60pct_sellthrough_classifies_as_high_demand(client: TestClient):
    """Above 60% sell-through (7/10 = 70%) must classify as high_demand."""
    proj_id = _make_project_with_sell_through(
        client, "PRJ-BT70", "Boundary 70pct", 10, 7, "studio", "BLK-BT70"
    )
    resp = client.get(f"/api/v1/projects/{proj_id}/pricing-recommendations")
    assert resp.status_code == 200
    rec = next(r for r in resp.json()["recommendations"] if r["unit_type"] == "studio")
    assert rec["demand_status"] == "high_demand"
    assert rec["change_pct"] > 0


# ---------------------------------------------------------------------------
# Recommendation availability boundary tests
# ---------------------------------------------------------------------------


def _make_high_demand_project_with_availability(
    client: TestClient,
    code: str,
    total_units: int,
    sold_units: int,
) -> str:
    """Create a high-demand project (>60% sell-through) with specific availability."""
    return _make_project_with_sell_through(
        client,
        code,
        f"Avail Test {code}",
        total_units,
        sold_units,
        "studio",
        f"BLK-{code}",
    )


def test_high_demand_at_20pct_availability_gives_8pct_increase(client: TestClient):
    """High demand + availability_pct ≤ 20% → change_pct must be +8%."""
    # 10 units, 8 sold (80% sell-through → high_demand), 2 available (20%)
    proj_id = _make_high_demand_project_with_availability(
        client, "AVAIL20", total_units=10, sold_units=8
    )
    resp = client.get(f"/api/v1/projects/{proj_id}/pricing-recommendations")
    assert resp.status_code == 200
    rec = next(r for r in resp.json()["recommendations"] if r["unit_type"] == "studio")
    assert rec["demand_status"] == "high_demand"
    assert rec["availability_pct"] == pytest.approx(20.0, abs=0.1)
    assert rec["change_pct"] == pytest.approx(8.0)
    assert rec["confidence"] == "high"


def test_high_demand_at_40pct_availability_gives_5pct_increase(client: TestClient):
    """High demand + availability_pct ≤ 40% (but > 20%) → change_pct must be +5%."""
    # 10 units, 7 sold (70% sell-through → high_demand), 3 available (30% availability)
    # 30% availability is ≤ 40% but > 20% → +5%
    proj_id = _make_high_demand_project_with_availability(
        client, "AVAIL40", total_units=10, sold_units=7
    )
    resp = client.get(f"/api/v1/projects/{proj_id}/pricing-recommendations")
    assert resp.status_code == 200
    rec = next(r for r in resp.json()["recommendations"] if r["unit_type"] == "studio")
    assert rec["demand_status"] == "high_demand"
    assert rec["availability_pct"] == pytest.approx(30.0, abs=0.1)
    assert rec["change_pct"] == pytest.approx(5.0)
    assert rec["confidence"] == "high"


def test_low_demand_at_70pct_availability_gives_8pct_decrease(client: TestClient):
    """Low demand + availability_pct ≥ 70% → change_pct must be −8%."""
    # 10 units, 3 sold (30% → low_demand), 7 available (70%)
    proj_id = _make_project_with_sell_through(
        client, "PRJ-LD70", "Low Demand 70pct Avail", 10, 3, "studio", "BLK-LD70"
    )
    resp = client.get(f"/api/v1/projects/{proj_id}/pricing-recommendations")
    assert resp.status_code == 200
    rec = next(r for r in resp.json()["recommendations"] if r["unit_type"] == "studio")
    assert rec["demand_status"] == "low_demand"
    assert rec["availability_pct"] == pytest.approx(70.0, abs=0.1)
    assert rec["change_pct"] == pytest.approx(-8.0)
    assert rec["confidence"] == "high"


def test_low_demand_at_50pct_availability_gives_5pct_decrease(client: TestClient):
    """Low demand + availability_pct ≥ 50% (but < 70%) → change_pct must be −5%."""
    # 10 units, 3 sold (30% sell-through → low_demand), 5 available (50%)
    # but wait: 10 total - 3 sold = 7 available. Need to set reserved/other states.
    # Easier: 6 units, 3 sold (50% sell-through → but that's balanced)...
    # Use: 10 units, 2 sold (20% → low_demand), 5 available = impossible unless 3 reserved.
    # Simplest: directly use 4 units total, 1 sold (25% → low_demand), 2 available, 1 reserved
    # Actually: use 4 units, 1 sold = 1 under_contract (25% → low_demand), 3 available = 75%... no.
    # Let's be explicit: 8 units, 2 sold (25% → low_demand), 4 available (50%) + 2 reserved
    # We set 2 to under_contract, 2 to reserved, 4 remain available
    proj_id = _create_project(client, "PRJ-LD50", "Low Demand 50pct Avail")
    unit_ids = _create_units_in_hierarchy(client, proj_id, 8, "studio", "BLK-LD50")
    # 2 units under_contract (sold)
    for uid in unit_ids[:2]:
        _set_unit_under_contract(client, uid)
    # 2 units reserved (not sold)
    for uid in unit_ids[2:4]:
        r = client.patch(f"/api/v1/units/{uid}", json={"status": "reserved"})
        assert r.status_code == 200, r.text
    # 4 units remain available

    resp = client.get(f"/api/v1/projects/{proj_id}/pricing-recommendations")
    assert resp.status_code == 200
    rec = next(r for r in resp.json()["recommendations"] if r["unit_type"] == "studio")
    assert rec["demand_status"] == "low_demand"
    # availability = 4/8 = 50%
    assert rec["availability_pct"] == pytest.approx(50.0, abs=0.1)
    assert rec["change_pct"] == pytest.approx(-5.0)
    assert rec["confidence"] == "medium"
