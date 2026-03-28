"""
Tests for the Phasing Optimization Engine (PR-V7-03).

Validates:
  - GET /projects/{id}/phasing-recommendations
      - HTTP contract (200 on valid project, 404 on missing project)
      - Response schema shape — all required fields present
      - High demand + critically low availability → release_more_inventory
      - High demand + moderate availability → maintain_current_release
      - Balanced demand → maintain_current_release
      - Low demand + high availability → delay_further_release
      - Low demand + moderate availability → hold_current_inventory
      - No sold units → insufficient_data
      - No phases → insufficient_data
      - Next phase recommendation: prepare_next_phase when justified
      - Next phase recommendation: not_applicable when no next phase
      - Next phase recommendation: defer_next_phase when low demand
      - Auth requirement (401 when unauthenticated)
      - Source record immutability (no phase mutation)
  - GET /portfolio/phasing-insights
      - HTTP contract (200, auth required)
      - Response schema shape
      - Empty portfolio returns valid null-safe response
      - Per-project cards populated
      - Summary counts accurate
      - Batched query path is deterministic
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Shared hierarchy helpers (adapted from test_pricing_recommendations.py)
# ---------------------------------------------------------------------------


def _create_project(
    client: TestClient, code: str = "PRJ-PH", name: str = "Phasing Opt Project"
) -> str:
    resp = client.post("/api/v1/projects", json={"name": name, "code": code})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_phase(
    client: TestClient, project_id: str, name: str = "Phase 1", sequence: int = 1
) -> str:
    resp = client.post(
        "/api/v1/phases",
        json={"project_id": project_id, "name": name, "sequence": sequence},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_building(client: TestClient, phase_id: str, code: str = "BLK-PH") -> str:
    resp = client.post(
        f"/api/v1/phases/{phase_id}/buildings",
        json={"name": "Block A", "code": code},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_floor(client: TestClient, building_id: str) -> str:
    resp = client.post(
        f"/api/v1/buildings/{building_id}/floors",
        json={"name": "Floor 1", "code": "FL-01", "sequence_number": 1},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_units_in_phase(
    client: TestClient,
    project_id: str,
    num_units: int,
    unit_type: str = "studio",
    phase_name: str = "Phase 1",
    phase_sequence: int = 1,
    building_code: str = "BLK-PH",
) -> tuple:
    """Create phase -> building -> floor -> N units. Returns (phase_id, [unit_ids])."""
    phase_id = _create_phase(client, project_id, phase_name, phase_sequence)
    building_id = _create_building(client, phase_id, building_code)
    floor_id = _create_floor(client, building_id)

    unit_ids = []
    for i in range(1, num_units + 1):
        resp = client.post(
            "/api/v1/units",
            json={
                "floor_id": floor_id,
                "unit_number": str(i),
                "unit_type": unit_type,
                "internal_area": 80.0,
            },
        )
        assert resp.status_code == 201, resp.text
        unit_ids.append(resp.json()["id"])
    return phase_id, unit_ids


def _set_unit_under_contract(client: TestClient, unit_id: str) -> None:
    """Set a unit to under_contract through valid status transitions."""
    r = client.patch(f"/api/v1/units/{unit_id}", json={"status": "reserved"})
    assert r.status_code == 200, f"Failed to reserve unit {unit_id}: {r.text}"
    r = client.patch(f"/api/v1/units/{unit_id}", json={"status": "under_contract"})
    assert r.status_code == 200, f"Failed to set under_contract for {unit_id}: {r.text}"


def _create_buyer(client: TestClient, email: str = "buyer@ph.com") -> str:
    resp = client.post(
        "/api/v1/sales/buyers",
        json={"full_name": "PH Buyer", "email": email, "phone": "+971500000099"},
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


def _create_calculated_feasibility_run(
    client: TestClient,
    project_id: str,
    development_period_months: int = 12,
) -> str:
    """Create a calculated feasibility run; returns run_id.

    Uses development_period_months to drive the planned absorption rate:
    planned_rate = total_units / development_period_months.
    """
    run_resp = client.post(
        "/api/v1/feasibility/runs",
        json={
            "project_id": project_id,
            "scenario_name": "Test Run",
            "scenario_type": "base",
        },
    )
    assert run_resp.status_code == 201, run_resp.text
    run_id = run_resp.json()["id"]

    assumptions_resp = client.post(
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
    assert assumptions_resp.status_code in (200, 201), assumptions_resp.text

    calc_resp = client.post(f"/api/v1/feasibility/runs/{run_id}/calculate")
    assert calc_resp.status_code in (200, 201), calc_resp.text
    return run_id


def _create_approved_baseline(client: TestClient, project_id: str) -> str:
    """Create a tender comparison set and approve it as the project baseline.

    Returns the comparison set ID.
    """
    set_resp = client.post(
        f"/api/v1/projects/{project_id}/tender-comparisons",
        json={
            "title": "Approved Baseline",
            "comparison_stage": "baseline_vs_tender",
        },
    )
    assert set_resp.status_code == 201, set_resp.text
    set_id = set_resp.json()["id"]

    approve_resp = client.post(f"/api/v1/tender-comparisons/{set_id}/approve-baseline")
    assert approve_resp.status_code == 200, approve_resp.text
    return set_id


# ---------------------------------------------------------------------------
# Auth requirement
# ---------------------------------------------------------------------------


def test_phasing_recommendations_requires_auth(unauth_client: TestClient):
    """Endpoint must reject unauthenticated requests with 401/403."""
    resp = unauth_client.get("/api/v1/projects/does-not-matter/phasing-recommendations")
    assert resp.status_code in (401, 403)


def test_portfolio_phasing_insights_requires_auth(unauth_client: TestClient):
    """Portfolio endpoint must reject unauthenticated requests with 401/403."""
    resp = unauth_client.get("/api/v1/portfolio/phasing-insights")
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# 404 on missing project
# ---------------------------------------------------------------------------


def test_phasing_recommendations_404_on_missing_project(client: TestClient):
    """Must return 404 when the project does not exist."""
    resp = client.get("/api/v1/projects/nonexistent-id/phasing-recommendations")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Response schema shape
# ---------------------------------------------------------------------------


def test_phasing_recommendations_response_shape(client: TestClient):
    """Response must include all required top-level fields."""
    proj_id = _create_project(client, "PRJ-PHF", "Phasing Shape Test")
    resp = client.get(f"/api/v1/projects/{proj_id}/phasing-recommendations")
    assert resp.status_code == 200
    data = resp.json()

    required_fields = [
        "project_id",
        "project_name",
        "current_phase_id",
        "current_phase_name",
        "current_phase_recommendation",
        "next_phase_recommendation",
        "release_urgency",
        "confidence",
        "reason",
        "sold_units",
        "available_units",
        "sell_through_pct",
        "absorption_status",
        "has_next_phase",
        "next_phase_id",
        "next_phase_name",
    ]
    for field in required_fields:
        assert field in data, f"Missing field: {field}"

    assert data["project_id"] == proj_id


# ---------------------------------------------------------------------------
# No phases → insufficient_data
# ---------------------------------------------------------------------------


def test_phasing_recommendations_no_phases_returns_insufficient_data(client: TestClient):
    """Project with no phases should return insufficient_data recommendation."""
    proj_id = _create_project(client, "PRJ-PH0", "No Phases Project")
    resp = client.get(f"/api/v1/projects/{proj_id}/phasing-recommendations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["current_phase_recommendation"] == "insufficient_data"
    assert data["absorption_status"] == "no_data"
    assert data["sold_units"] == 0
    assert data["current_phase_id"] is None


# ---------------------------------------------------------------------------
# No sold units → insufficient_data
# ---------------------------------------------------------------------------


def test_phasing_recommendations_no_sold_units_returns_insufficient_data(client: TestClient):
    """Project with units but no contracts should return insufficient_data."""
    proj_id = _create_project(client, "PRJ-PH1", "No Sales Project")
    _create_units_in_phase(client, proj_id, num_units=10, building_code="BLK-PH1")
    resp = client.get(f"/api/v1/projects/{proj_id}/phasing-recommendations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["current_phase_recommendation"] == "insufficient_data"
    assert data["absorption_status"] == "no_data"
    assert data["sold_units"] == 0


# ---------------------------------------------------------------------------
# High demand + critically low availability → release_more_inventory
# ---------------------------------------------------------------------------


def test_high_demand_critically_low_avail_returns_release_more_inventory(client: TestClient):
    """High demand (>60% sell-through) + ≤20% phase availability → release_more_inventory."""
    proj_id = _create_project(client, "PRJ-PH2", "High Demand Low Avail")
    # 10 units, sell 9 (90% sell-through), 1 available (10% availability)
    _phase_id, unit_ids = _create_units_in_phase(
        client, proj_id, num_units=10, building_code="BLK-PH2"
    )
    buyer_id = _create_buyer(client, "buyer-ph2@ph.com")
    for i, uid in enumerate(unit_ids[:9]):
        _set_unit_under_contract(client, uid)
        _create_contract(client, uid, buyer_id, f"CNT-PH2-{i:03d}", contract_date=str(date.today() - timedelta(days=60 - i)))

    resp = client.get(f"/api/v1/projects/{proj_id}/phasing-recommendations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["current_phase_recommendation"] == "release_more_inventory"
    assert data["release_urgency"] == "high"
    assert data["absorption_status"] == "high_demand"
    assert data["sold_units"] == 9


# ---------------------------------------------------------------------------
# High demand + moderate availability → maintain_current_release
# ---------------------------------------------------------------------------


def test_high_demand_moderate_avail_returns_maintain_current_release(client: TestClient):
    """High demand + 20-50% phase availability → maintain_current_release."""
    proj_id = _create_project(client, "PRJ-PH3", "High Demand Moderate Avail")
    # 10 units, sell 7 (70% sell-through → high_demand), 3 available (30% availability)
    _phase_id, unit_ids = _create_units_in_phase(
        client, proj_id, num_units=10, building_code="BLK-PH3"
    )
    buyer_id = _create_buyer(client, "buyer-ph3@ph.com")
    for i, uid in enumerate(unit_ids[:7]):
        _set_unit_under_contract(client, uid)
        _create_contract(client, uid, buyer_id, f"CNT-PH3-{i:03d}", contract_date=str(date.today() - timedelta(days=30 - i)))

    resp = client.get(f"/api/v1/projects/{proj_id}/phasing-recommendations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["current_phase_recommendation"] == "maintain_current_release"
    assert data["absorption_status"] == "high_demand"


# ---------------------------------------------------------------------------
# Balanced demand → maintain_current_release
# ---------------------------------------------------------------------------


def test_balanced_demand_returns_maintain_current_release(client: TestClient):
    """Balanced demand (40-60% sell-through) → maintain_current_release."""
    proj_id = _create_project(client, "PRJ-PH4", "Balanced Demand")
    # 10 units, sell 5 (50% sell-through → balanced)
    _phase_id, unit_ids = _create_units_in_phase(
        client, proj_id, num_units=10, building_code="BLK-PH4"
    )
    buyer_id = _create_buyer(client, "buyer-ph4@ph.com")
    for i, uid in enumerate(unit_ids[:5]):
        _set_unit_under_contract(client, uid)
        _create_contract(client, uid, buyer_id, f"CNT-PH4-{i:03d}", contract_date=str(date.today() - timedelta(days=30 - i)))

    resp = client.get(f"/api/v1/projects/{proj_id}/phasing-recommendations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["current_phase_recommendation"] == "maintain_current_release"
    assert data["absorption_status"] == "balanced"
    assert data["confidence"] == "high"


# ---------------------------------------------------------------------------
# Low demand + high availability → delay_further_release
# ---------------------------------------------------------------------------


def test_low_demand_high_avail_returns_delay_further_release(client: TestClient):
    """Low demand (<40% sell-through) + ≥70% availability → delay_further_release."""
    proj_id = _create_project(client, "PRJ-PH5", "Low Demand High Avail")
    # 10 units, sell 2 (20% sell-through → low_demand), 8 available (80% availability)
    _phase_id, unit_ids = _create_units_in_phase(
        client, proj_id, num_units=10, building_code="BLK-PH5"
    )
    buyer_id = _create_buyer(client, "buyer-ph5@ph.com")
    for i, uid in enumerate(unit_ids[:2]):
        _set_unit_under_contract(client, uid)
        _create_contract(client, uid, buyer_id, f"CNT-PH5-{i:03d}", contract_date=str(date.today() - timedelta(days=30 - i)))

    resp = client.get(f"/api/v1/projects/{proj_id}/phasing-recommendations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["current_phase_recommendation"] == "delay_further_release"
    assert data["absorption_status"] == "low_demand"
    assert data["confidence"] == "high"


# ---------------------------------------------------------------------------
# Low demand + moderate availability → hold_current_inventory
# ---------------------------------------------------------------------------


def test_low_demand_moderate_avail_returns_hold_current_inventory(client: TestClient):
    """Low demand (<40% sell-through) + <70% availability → hold_current_inventory."""
    proj_id = _create_project(client, "PRJ-PH6", "Low Demand Moderate Avail")
    # 10 units, sell 2 (20% sell-through → low_demand), 8 available but set 2 reserved
    # to get availability below 70% — actually just use 10 units, sell 2 (20% ST),
    # and make availability pct between 20-70%: sell 2, leave 8 available = 80% avail.
    # For < 70%, we need to sell fewer and have less availability.
    # 10 units, sell 1 (10% ST → low_demand), 9 available (90% avail) → delay_further_release
    # Let's use: 10 units, sell 2 (20% → low_demand); then reserve 2 to get avail at 60%.
    _phase_id, unit_ids = _create_units_in_phase(
        client, proj_id, num_units=10, building_code="BLK-PH6"
    )
    buyer_id = _create_buyer(client, "buyer-ph6@ph.com")
    # Sell 2 units (20% sell-through = low_demand)
    for i, uid in enumerate(unit_ids[:2]):
        _set_unit_under_contract(client, uid)
        _create_contract(client, uid, buyer_id, f"CNT-PH6-{i:03d}", contract_date=str(date.today() - timedelta(days=30 - i)))
    # Reserve 2 more units to bring available down to 6/10 = 60% (< 70% threshold)
    for uid in unit_ids[2:4]:
        r = client.patch(f"/api/v1/units/{uid}", json={"status": "reserved"})
        assert r.status_code == 200, r.text

    resp = client.get(f"/api/v1/projects/{proj_id}/phasing-recommendations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["current_phase_recommendation"] == "hold_current_inventory"
    assert data["absorption_status"] == "low_demand"


# ---------------------------------------------------------------------------
# Next phase: prepare_next_phase when high demand + critically low inventory
# ---------------------------------------------------------------------------


def test_prepare_next_phase_when_high_demand_and_low_inventory(client: TestClient):
    """High demand + ≤20% phase availability + approved baseline → prepare_next_phase."""
    proj_id = _create_project(client, "PRJ-PH7", "Prepare Next Phase")
    # Phase 1: 10 units, sell 9 (≤20% avail)
    _phase1_id, unit_ids = _create_units_in_phase(
        client, proj_id, num_units=10, phase_name="Phase 1", phase_sequence=1, building_code="BLK-PH7A"
    )
    # Phase 2: create but don't activate
    _phase2_id, _unit_ids2 = _create_units_in_phase(
        client, proj_id, num_units=10, phase_name="Phase 2", phase_sequence=2, building_code="BLK-PH7B"
    )
    # Approved baseline: required to unlock prepare_next_phase
    _create_approved_baseline(client, proj_id)

    buyer_id = _create_buyer(client, "buyer-ph7@ph.com")
    for i, uid in enumerate(unit_ids[:9]):
        _set_unit_under_contract(client, uid)
        _create_contract(
            client, uid, buyer_id, f"CNT-PH7-{i:03d}",
            contract_date=str(date.today() - timedelta(days=60 - i))
        )

    resp = client.get(f"/api/v1/projects/{proj_id}/phasing-recommendations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["next_phase_recommendation"] == "prepare_next_phase"
    assert data["has_next_phase"] is True
    assert data["next_phase_id"] is not None
    assert data["release_urgency"] == "high"


# ---------------------------------------------------------------------------
# Next phase: high demand + critically low inventory WITHOUT approved baseline
# → do_not_open_next_phase (readiness gate)
# ---------------------------------------------------------------------------


def test_high_demand_low_inventory_without_baseline_does_not_prepare_next_phase(
    client: TestClient,
):
    """High demand + ≤20% availability + NO approved baseline → do_not_open_next_phase.

    The readiness gate prevents prepare_next_phase from being emitted when the
    project does not yet have an approved tender baseline.
    """
    proj_id = _create_project(client, "PRJ-PH7B", "High Demand No Baseline")
    # Phase 1: 10 units, sell 9 (high demand, ≤20% availability)
    _phase1_id, unit_ids = _create_units_in_phase(
        client, proj_id, num_units=10, phase_name="Phase 1", phase_sequence=1, building_code="BLK-PH7C"
    )
    # Phase 2 exists but no approved baseline
    _phase2_id, _unit_ids2 = _create_units_in_phase(
        client, proj_id, num_units=10, phase_name="Phase 2", phase_sequence=2, building_code="BLK-PH7D"
    )
    # No _create_approved_baseline call — readiness gate must block prepare_next_phase

    buyer_id = _create_buyer(client, "buyer-ph7b@ph.com")
    for i, uid in enumerate(unit_ids[:9]):
        _set_unit_under_contract(client, uid)
        _create_contract(
            client, uid, buyer_id, f"CNT-PH7B-{i:03d}",
            contract_date=str(date.today() - timedelta(days=60 - i))
        )

    resp = client.get(f"/api/v1/projects/{proj_id}/phasing-recommendations")
    assert resp.status_code == 200
    data = resp.json()
    # Without baseline, must NOT emit prepare_next_phase
    assert data["next_phase_recommendation"] == "do_not_open_next_phase"
    assert data["has_next_phase"] is True
    assert data["release_urgency"] == "high"
    # Reason must explain the readiness block
    assert "baseline" in data["reason"].lower()


# ---------------------------------------------------------------------------
# Next phase: not_applicable when no next phase exists
# ---------------------------------------------------------------------------


def test_next_phase_not_applicable_when_no_next_phase(client: TestClient):
    """When only one phase exists, next_phase_recommendation must be 'not_applicable'."""
    proj_id = _create_project(client, "PRJ-PH8", "Single Phase Project")
    _phase_id, unit_ids = _create_units_in_phase(
        client, proj_id, num_units=10, building_code="BLK-PH8"
    )
    buyer_id = _create_buyer(client, "buyer-ph8@ph.com")
    for i, uid in enumerate(unit_ids[:7]):
        _set_unit_under_contract(client, uid)
        _create_contract(
            client, uid, buyer_id, f"CNT-PH8-{i:03d}",
            contract_date=str(date.today() - timedelta(days=30 - i))
        )

    resp = client.get(f"/api/v1/projects/{proj_id}/phasing-recommendations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["next_phase_recommendation"] == "not_applicable"
    assert data["has_next_phase"] is False
    assert data["next_phase_id"] is None
    assert data["next_phase_name"] is None


# ---------------------------------------------------------------------------
# Next phase: defer_next_phase when low demand
# ---------------------------------------------------------------------------


def test_defer_next_phase_when_low_demand(client: TestClient):
    """Low demand + next phase exists → defer_next_phase."""
    proj_id = _create_project(client, "PRJ-PH9", "Low Demand With Next Phase")
    # Phase 1: low demand (2/10 sold = 20% sell-through)
    _phase1_id, unit_ids = _create_units_in_phase(
        client, proj_id, num_units=10, phase_name="Phase 1", phase_sequence=1, building_code="BLK-PH9A"
    )
    # Phase 2 exists
    _phase2_id, _unit_ids2 = _create_units_in_phase(
        client, proj_id, num_units=10, phase_name="Phase 2", phase_sequence=2, building_code="BLK-PH9B"
    )

    buyer_id = _create_buyer(client, "buyer-ph9@ph.com")
    for i, uid in enumerate(unit_ids[:2]):
        _set_unit_under_contract(client, uid)
        _create_contract(
            client, uid, buyer_id, f"CNT-PH9-{i:03d}",
            contract_date=str(date.today() - timedelta(days=30 - i))
        )

    resp = client.get(f"/api/v1/projects/{proj_id}/phasing-recommendations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["next_phase_recommendation"] == "defer_next_phase"
    assert data["has_next_phase"] is True


# ---------------------------------------------------------------------------
# Recommendation reason is always populated
# ---------------------------------------------------------------------------


def test_recommendation_reason_is_populated(client: TestClient):
    """Reason text must always be a non-empty string."""
    proj_id = _create_project(client, "PRJ-PH10", "Reason Test")
    resp = client.get(f"/api/v1/projects/{proj_id}/phasing-recommendations")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["reason"], str)
    assert len(data["reason"]) > 0


# ---------------------------------------------------------------------------
# sell_through_pct and sold_units are accurate
# ---------------------------------------------------------------------------


def test_sell_through_and_sold_units_are_accurate(client: TestClient):
    """sell_through_pct and sold_units must reflect actual contract records."""
    proj_id = _create_project(client, "PRJ-PH11", "Sell-Through Accuracy")
    _phase_id, unit_ids = _create_units_in_phase(
        client, proj_id, num_units=20, building_code="BLK-PH11"
    )
    buyer_id = _create_buyer(client, "buyer-ph11@ph.com")
    for i, uid in enumerate(unit_ids[:12]):
        _set_unit_under_contract(client, uid)
        _create_contract(
            client, uid, buyer_id, f"CNT-PH11-{i:03d}",
            contract_date=str(date.today() - timedelta(days=30 - (i % 30)))
        )

    resp = client.get(f"/api/v1/projects/{proj_id}/phasing-recommendations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["sold_units"] == 12
    # sell_through_pct = 12/20 * 100 = 60.0 (boundary: > 60 is high demand, so this is balanced)
    assert data["sell_through_pct"] == pytest.approx(60.0)
    assert data["absorption_status"] == "balanced"


# ---------------------------------------------------------------------------
# Absorption vs plan: plan-aware classification
# ---------------------------------------------------------------------------


def test_phasing_uses_absorption_vs_plan_when_feasibility_exists(client: TestClient):
    """When a feasibility plan exists, demand should be classified via absorption_vs_plan_pct."""
    proj_id = _create_project(client, "PRJ-PH12", "Plan-Aware Phasing")
    _phase_id, unit_ids = _create_units_in_phase(
        client, proj_id, num_units=5, building_code="BLK-PH12"
    )
    # Create feasibility run with short period so planned_rate is high
    # planned_rate = 5 units / 2 months = 2.5 units/month
    # actual: 5 contracts over ~30 days → ~5/1 = 5/month → absorption_vs_plan_pct ≈ 200% → high_demand
    _create_calculated_feasibility_run(client, proj_id, development_period_months=2)

    buyer_id = _create_buyer(client, "buyer-ph12@ph.com")
    for i, uid in enumerate(unit_ids):
        _set_unit_under_contract(client, uid)
        _create_contract(
            client, uid, buyer_id, f"CNT-PH12-{i:03d}",
            contract_date=str(date.today() - timedelta(days=30 - i))
        )

    resp = client.get(f"/api/v1/projects/{proj_id}/phasing-recommendations")
    assert resp.status_code == 200
    data = resp.json()
    # 5 contracts / ~1 month ≈ 5/month vs planned 2.5/month → ~200% → high_demand
    assert data["absorption_status"] == "high_demand"


# ---------------------------------------------------------------------------
# current_phase_id and current_phase_name are populated when phases exist
# ---------------------------------------------------------------------------


def test_current_phase_fields_populated(client: TestClient):
    """current_phase_id and current_phase_name must be populated when a phase exists."""
    proj_id = _create_project(client, "PRJ-PH13", "Phase Fields Test")
    _phase_id, unit_ids = _create_units_in_phase(
        client, proj_id, num_units=5, phase_name="Phase Alpha", building_code="BLK-PH13"
    )
    buyer_id = _create_buyer(client, "buyer-ph13@ph.com")
    _set_unit_under_contract(client, unit_ids[0])
    _create_contract(client, unit_ids[0], buyer_id, "CNT-PH13-001")

    resp = client.get(f"/api/v1/projects/{proj_id}/phasing-recommendations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["current_phase_id"] is not None
    assert data["current_phase_name"] == "Phase Alpha"


# ---------------------------------------------------------------------------
# Source immutability
# ---------------------------------------------------------------------------


def test_phasing_recommendations_does_not_mutate_phases(client: TestClient):
    """Fetching phasing recommendations must not alter any phase records."""
    proj_id = _create_project(client, "PRJ-PH14", "Immutability Test")
    phase_id, unit_ids = _create_units_in_phase(
        client, proj_id, num_units=5, building_code="BLK-PH14"
    )

    # Record phase state before recommendation fetch
    before = client.get(f"/api/v1/phases/{phase_id}").json()

    # Fetch recommendations
    client.get(f"/api/v1/projects/{proj_id}/phasing-recommendations")

    # Verify phase is unchanged
    after = client.get(f"/api/v1/phases/{phase_id}").json()
    assert before["status"] == after["status"]
    assert before["name"] == after["name"]
    assert before["sequence"] == after["sequence"]


# ---------------------------------------------------------------------------
# Portfolio endpoint — auth requirement
# ---------------------------------------------------------------------------


def test_portfolio_phasing_insights_shape(client: TestClient):
    """Portfolio endpoint must return all required top-level fields."""
    resp = client.get("/api/v1/portfolio/phasing-insights")
    assert resp.status_code == 200
    data = resp.json()

    assert "summary" in data
    assert "projects" in data
    assert "top_phase_opportunities" in data
    assert "top_release_risks" in data

    summary = data["summary"]
    summary_fields = [
        "total_projects",
        "projects_prepare_next_phase_count",
        "projects_hold_inventory_count",
        "projects_delay_release_count",
        "projects_insufficient_data_count",
    ]
    for field in summary_fields:
        assert field in summary, f"Missing summary field: {field}"


# ---------------------------------------------------------------------------
# Portfolio endpoint — empty portfolio
# ---------------------------------------------------------------------------


def test_portfolio_phasing_insights_empty_portfolio(client: TestClient):
    """Empty portfolio must return valid null-safe response."""
    resp = client.get("/api/v1/portfolio/phasing-insights")
    assert resp.status_code == 200
    data = resp.json()
    assert data["summary"]["total_projects"] == 0
    assert data["projects"] == []
    assert data["top_phase_opportunities"] == []
    assert data["top_release_risks"] == []


# ---------------------------------------------------------------------------
# Portfolio endpoint — per-project cards populated
# ---------------------------------------------------------------------------


def test_portfolio_phasing_insights_project_cards_present(client: TestClient):
    """Every project must appear in the portfolio phasing response."""
    proj1 = _create_project(client, "PRJ-PPH1", "Portfolio Phase Project 1")
    proj2 = _create_project(client, "PRJ-PPH2", "Portfolio Phase Project 2")

    resp = client.get("/api/v1/portfolio/phasing-insights")
    assert resp.status_code == 200
    data = resp.json()

    project_ids = {card["project_id"] for card in data["projects"]}
    assert proj1 in project_ids
    assert proj2 in project_ids
    assert data["summary"]["total_projects"] >= 2


# ---------------------------------------------------------------------------
# Portfolio endpoint — summary counts are correct
# ---------------------------------------------------------------------------


def test_portfolio_phasing_summary_counts(client: TestClient):
    """Summary counts must accurately reflect individual project recommendations."""
    # Project 1: high demand + critically low availability → release_more_inventory (no next phase)
    proj1 = _create_project(client, "PRJ-PPC1", "Count Test HD")
    _phase1_id, unit_ids1 = _create_units_in_phase(
        client, proj1, num_units=10, building_code="BLK-PPC1"
    )
    buyer1 = _create_buyer(client, "buyer-ppc1@ph.com")
    for i, uid in enumerate(unit_ids1[:9]):
        _set_unit_under_contract(client, uid)
        _create_contract(
            client, uid, buyer1, f"CNT-PPC1-{i:03d}",
            contract_date=str(date.today() - timedelta(days=60 - i))
        )

    # Project 2: low demand + high availability → delay_further_release (no next phase)
    proj2 = _create_project(client, "PRJ-PPC2", "Count Test LD")
    _phase2_id, unit_ids2 = _create_units_in_phase(
        client, proj2, num_units=10, building_code="BLK-PPC2"
    )
    buyer2 = _create_buyer(client, "buyer-ppc2@ph.com")
    for i, uid in enumerate(unit_ids2[:2]):
        _set_unit_under_contract(client, uid)
        _create_contract(
            client, uid, buyer2, f"CNT-PPC2-{i:03d}",
            contract_date=str(date.today() - timedelta(days=30 - i))
        )

    resp = client.get("/api/v1/portfolio/phasing-insights")
    assert resp.status_code == 200
    data = resp.json()

    # Find project recommendations in the cards
    cards_by_project = {card["project_id"]: card for card in data["projects"]}

    assert cards_by_project[proj1]["current_phase_recommendation"] == "release_more_inventory"
    assert cards_by_project[proj2]["current_phase_recommendation"] == "delay_further_release"
    assert data["summary"]["projects_delay_release_count"] >= 1
