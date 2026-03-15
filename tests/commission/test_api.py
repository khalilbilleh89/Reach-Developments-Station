"""
Tests for the Commission module API endpoints.

Validates HTTP behaviour, request/response contracts, and the core
commission calculation rules (marginal and cumulative modes).
"""

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _create_hierarchy(client: TestClient, proj_code: str) -> tuple[str, str]:
    """Create Project → Phase → Building → Floor → Unit; return (project_id, unit_id)."""
    resp = client.post("/api/v1/projects", json={"name": "Comm Project", "code": proj_code})
    assert resp.status_code == 201, resp.text
    project_id = resp.json()["id"]

    resp = client.post(
        "/api/v1/phases",
        json={"project_id": project_id, "name": "Phase 1", "sequence": 1},
    )
    assert resp.status_code == 201, resp.text
    phase_id = resp.json()["id"]

    resp = client.post(
        f"/api/v1/phases/{phase_id}/buildings",
        json={"name": "Block A", "code": f"BLK-{proj_code}"},
    )
    assert resp.status_code == 201, resp.text
    building_id = resp.json()["id"]

    resp = client.post(
        f"/api/v1/buildings/{building_id}/floors",
        json={"name": "Floor 1", "code": "FL-01", "sequence_number": 1},
    )
    assert resp.status_code == 201, resp.text
    floor_id = resp.json()["id"]

    resp = client.post(
        "/api/v1/units",
        json={
            "floor_id": floor_id,
            "unit_number": "101",
            "unit_type": "studio",
            "internal_area": 100.0,
        },
    )
    assert resp.status_code == 201, resp.text
    unit_id = resp.json()["id"]

    return project_id, unit_id


def _create_buyer(client: TestClient, email: str) -> str:
    resp = client.post(
        "/api/v1/sales/buyers",
        json={"full_name": "Test Buyer", "email": email, "phone": "+9620000001"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_contract(
    client: TestClient,
    unit_id: str,
    buyer_id: str,
    contract_number: str,
    contract_price: float = 500_000.0,
) -> str:
    resp = client.post(
        "/api/v1/sales/contracts",
        json={
            "unit_id": unit_id,
            "buyer_id": buyer_id,
            "contract_number": contract_number,
            "contract_date": "2026-03-01",
            "contract_price": contract_price,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_plan(
    client: TestClient,
    project_id: str,
    *,
    pool_percentage: float = 5.0,
    calculation_mode: str = "marginal",
    name: str = "Default Plan",
) -> str:
    resp = client.post(
        "/api/v1/commission/plans",
        json={
            "project_id": project_id,
            "name": name,
            "pool_percentage": pool_percentage,
            "calculation_mode": calculation_mode,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _add_slab(
    client: TestClient,
    plan_id: str,
    *,
    range_from: float,
    range_to: float | None,
    sequence: int,
    sales_rep_pct: float = 60.0,
    team_lead_pct: float = 20.0,
    manager_pct: float = 10.0,
    broker_pct: float = 5.0,
    platform_pct: float = 5.0,
) -> dict:
    payload = {
        "range_from": range_from,
        "range_to": range_to,
        "sequence": sequence,
        "sales_rep_pct": sales_rep_pct,
        "team_lead_pct": team_lead_pct,
        "manager_pct": manager_pct,
        "broker_pct": broker_pct,
        "platform_pct": platform_pct,
    }
    resp = client.post(f"/api/v1/commission/plans/{plan_id}/slabs", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _setup_single_slab_plan(
    client: TestClient,
    project_id: str,
    *,
    pool_percentage: float = 5.0,
    calculation_mode: str = "marginal",
) -> str:
    """Create a plan with one open-ended slab (60/20/10/5/5)."""
    plan_id = _create_plan(
        client,
        project_id,
        pool_percentage=pool_percentage,
        calculation_mode=calculation_mode,
    )
    _add_slab(client, plan_id, range_from=0, range_to=None, sequence=1)
    return plan_id


# ---------------------------------------------------------------------------
# Plan tests
# ---------------------------------------------------------------------------


def test_create_plan(client: TestClient):
    project_id, _ = _create_hierarchy(client, "CP-P1")
    resp = client.post(
        "/api/v1/commission/plans",
        json={
            "project_id": project_id,
            "name": "Test Plan",
            "pool_percentage": 5.0,
            "calculation_mode": "marginal",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["project_id"] == project_id
    assert data["pool_percentage"] == pytest.approx(5.0)
    assert data["calculation_mode"] == "marginal"
    assert data["is_active"] is True


def test_create_plan_invalid_project_returns_404(client: TestClient):
    resp = client.post(
        "/api/v1/commission/plans",
        json={
            "project_id": "no-such-project",
            "name": "Plan",
            "pool_percentage": 5.0,
        },
    )
    assert resp.status_code == 404


def test_create_plan_invalid_pool_percentage_returns_422(client: TestClient):
    project_id, _ = _create_hierarchy(client, "CP-PP")
    resp = client.post(
        "/api/v1/commission/plans",
        json={
            "project_id": project_id,
            "name": "Bad Plan",
            "pool_percentage": 0.0,  # must be > 0
        },
    )
    assert resp.status_code == 422


def test_get_plan(client: TestClient):
    project_id, _ = _create_hierarchy(client, "CP-G1")
    plan_id = _create_plan(client, project_id)
    resp = client.get(f"/api/v1/commission/plans/{plan_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == plan_id


def test_get_plan_not_found(client: TestClient):
    resp = client.get("/api/v1/commission/plans/no-such-plan")
    assert resp.status_code == 404


def test_list_project_plans(client: TestClient):
    project_id, _ = _create_hierarchy(client, "CP-L1")
    _create_plan(client, project_id, name="Plan A")
    _create_plan(client, project_id, name="Plan B")
    resp = client.get(f"/api/v1/commission/projects/{project_id}/plans")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_list_project_plans_invalid_project_returns_404(client: TestClient):
    resp = client.get("/api/v1/commission/projects/no-such-project/plans")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Slab tests
# ---------------------------------------------------------------------------


def test_add_slab(client: TestClient):
    project_id, _ = _create_hierarchy(client, "CS-S1")
    plan_id = _create_plan(client, project_id)
    slab = _add_slab(client, plan_id, range_from=0, range_to=300_000, sequence=1)
    assert slab["commission_plan_id"] == plan_id
    assert slab["range_from"] == pytest.approx(0.0)
    assert slab["range_to"] == pytest.approx(300_000.0)
    assert slab["sequence"] == 1


def test_add_slab_invalid_plan_returns_404(client: TestClient):
    resp = client.post(
        "/api/v1/commission/plans/no-plan/slabs",
        json={
            "range_from": 0,
            "range_to": None,
            "sequence": 1,
            "sales_rep_pct": 60,
            "team_lead_pct": 20,
            "manager_pct": 10,
            "broker_pct": 5,
            "platform_pct": 5,
        },
    )
    assert resp.status_code == 404


def test_add_slab_pct_not_100_returns_422(client: TestClient):
    project_id, _ = _create_hierarchy(client, "CS-S2")
    plan_id = _create_plan(client, project_id)
    resp = client.post(
        f"/api/v1/commission/plans/{plan_id}/slabs",
        json={
            "range_from": 0,
            "range_to": None,
            "sequence": 1,
            "sales_rep_pct": 50,
            "team_lead_pct": 20,
            "manager_pct": 10,
            "broker_pct": 5,
            "platform_pct": 5,  # total = 90, not 100
        },
    )
    assert resp.status_code == 422


def test_add_slab_overlap_returns_422(client: TestClient):
    project_id, _ = _create_hierarchy(client, "CS-S3")
    plan_id = _create_plan(client, project_id)
    _add_slab(client, plan_id, range_from=0, range_to=300_000, sequence=1)
    # Overlapping slab
    resp = client.post(
        f"/api/v1/commission/plans/{plan_id}/slabs",
        json={
            "range_from": 200_000,  # overlaps with [0, 300_000)
            "range_to": None,
            "sequence": 2,
            "sales_rep_pct": 60,
            "team_lead_pct": 20,
            "manager_pct": 10,
            "broker_pct": 5,
            "platform_pct": 5,
        },
    )
    assert resp.status_code == 422


def test_add_slab_duplicate_sequence_returns_422(client: TestClient):
    project_id, _ = _create_hierarchy(client, "CS-S4")
    plan_id = _create_plan(client, project_id)
    _add_slab(client, plan_id, range_from=0, range_to=300_000, sequence=1)
    resp = client.post(
        f"/api/v1/commission/plans/{plan_id}/slabs",
        json={
            "range_from": 300_000,
            "range_to": None,
            "sequence": 1,  # duplicate
            "sales_rep_pct": 60,
            "team_lead_pct": 20,
            "manager_pct": 10,
            "broker_pct": 5,
            "platform_pct": 5,
        },
    )
    assert resp.status_code == 422


def test_list_slabs(client: TestClient):
    project_id, _ = _create_hierarchy(client, "CS-L1")
    plan_id = _create_plan(client, project_id)
    _add_slab(client, plan_id, range_from=0, range_to=300_000, sequence=1)
    _add_slab(
        client,
        plan_id,
        range_from=300_000,
        range_to=None,
        sequence=2,
        sales_rep_pct=50,
        team_lead_pct=25,
        manager_pct=15,
        broker_pct=5,
        platform_pct=5,
    )
    resp = client.get(f"/api/v1/commission/plans/{plan_id}/slabs")
    assert resp.status_code == 200
    slabs = resp.json()
    assert len(slabs) == 2
    assert slabs[0]["sequence"] == 1
    assert slabs[1]["sequence"] == 2


# ---------------------------------------------------------------------------
# Payout calculation tests
# ---------------------------------------------------------------------------


def test_calculate_payout_single_slab_marginal(client: TestClient):
    """Single open-ended slab: pool is fully allocated by party percentages."""
    project_id, unit_id = _create_hierarchy(client, "CP-M1")
    buyer_id = _create_buyer(client, "m1@example.com")
    contract_id = _create_contract(client, unit_id, buyer_id, "CNT-M1", 500_000.0)
    plan_id = _setup_single_slab_plan(client, project_id, pool_percentage=5.0)

    resp = client.post(
        "/api/v1/commission/payouts/calculate",
        json={"sale_contract_id": contract_id, "commission_plan_id": plan_id},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()

    assert data["gross_sale_value"] == pytest.approx(500_000.0)
    assert data["commission_pool_value"] == pytest.approx(25_000.0)  # 5% of 500k
    assert data["calculation_mode"] == "marginal"
    assert data["status"] == "calculated"
    assert data["project_id"] == project_id
    assert len(data["lines"]) == 5  # one per party

    # Verify allocations (60/20/10/5/5 of 25,000)
    lines_by_party = {ln["party_type"]: ln for ln in data["lines"]}
    assert lines_by_party["sales_rep"]["amount"] == pytest.approx(15_000.0, abs=0.01)
    assert lines_by_party["team_lead"]["amount"] == pytest.approx(5_000.0, abs=0.01)
    assert lines_by_party["manager"]["amount"] == pytest.approx(2_500.0, abs=0.01)
    assert lines_by_party["broker"]["amount"] == pytest.approx(1_250.0, abs=0.01)
    assert lines_by_party["platform"]["amount"] == pytest.approx(1_250.0, abs=0.01)

    total_allocated = sum(ln["amount"] for ln in data["lines"])
    assert total_allocated == pytest.approx(25_000.0, abs=0.02)


def test_calculate_payout_two_slabs_marginal(client: TestClient):
    """
    Two-slab marginal: 500k contract, slabs [0,300k) and [300k, ∞).
    commission_pool = 500k * 5% = 25,000
    slab1 covers 300k → 300/500 * 25000 = 15,000
    slab2 covers 200k → 200/500 * 25000 = 10,000
    """
    project_id, unit_id = _create_hierarchy(client, "CP-M2")
    buyer_id = _create_buyer(client, "m2@example.com")
    contract_id = _create_contract(client, unit_id, buyer_id, "CNT-M2", 500_000.0)

    plan_id = _create_plan(client, project_id, pool_percentage=5.0, calculation_mode="marginal")
    _add_slab(
        client, plan_id, range_from=0, range_to=300_000, sequence=1,
        sales_rep_pct=60, team_lead_pct=20, manager_pct=10, broker_pct=5, platform_pct=5,
    )
    _add_slab(
        client, plan_id, range_from=300_000, range_to=None, sequence=2,
        sales_rep_pct=50, team_lead_pct=25, manager_pct=15, broker_pct=5, platform_pct=5,
    )

    resp = client.post(
        "/api/v1/commission/payouts/calculate",
        json={"sale_contract_id": contract_id, "commission_plan_id": plan_id},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()

    assert data["commission_pool_value"] == pytest.approx(25_000.0)
    assert len(data["lines"]) == 10  # 5 parties × 2 slabs

    total_allocated = sum(ln["amount"] for ln in data["lines"])
    assert total_allocated == pytest.approx(25_000.0, abs=0.05)

    # slab 1 commission = 15,000
    slab1_lines = [ln for ln in data["lines"] if ln["value_covered"] == pytest.approx(300_000.0, abs=1)]
    assert len(slab1_lines) == 5
    slab1_total = sum(ln["amount"] for ln in slab1_lines)
    assert slab1_total == pytest.approx(15_000.0, abs=0.05)


def test_calculate_payout_cumulative_mode(client: TestClient):
    """
    Cumulative mode: applicable slab drives the whole pool allocation.
    500k → falls in slab2 [300k, ∞) → full 25k allocated by slab2 percentages.
    """
    project_id, unit_id = _create_hierarchy(client, "CP-C1")
    buyer_id = _create_buyer(client, "c1@example.com")
    contract_id = _create_contract(client, unit_id, buyer_id, "CNT-C1", 500_000.0)

    plan_id = _create_plan(client, project_id, pool_percentage=5.0, calculation_mode="cumulative")
    _add_slab(
        client, plan_id, range_from=0, range_to=300_000, sequence=1,
        sales_rep_pct=60, team_lead_pct=20, manager_pct=10, broker_pct=5, platform_pct=5,
    )
    _add_slab(
        client, plan_id, range_from=300_000, range_to=None, sequence=2,
        sales_rep_pct=50, team_lead_pct=25, manager_pct=15, broker_pct=5, platform_pct=5,
    )

    resp = client.post(
        "/api/v1/commission/payouts/calculate",
        json={"sale_contract_id": contract_id, "commission_plan_id": plan_id},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()

    assert data["calculation_mode"] == "cumulative"
    assert len(data["lines"]) == 5  # whole pool in one slab

    lines_by_party = {ln["party_type"]: ln for ln in data["lines"]}
    assert lines_by_party["sales_rep"]["amount"] == pytest.approx(12_500.0, abs=0.01)
    assert lines_by_party["team_lead"]["amount"] == pytest.approx(6_250.0, abs=0.01)


def test_calculate_payout_contract_not_found_returns_404(client: TestClient):
    project_id, _ = _create_hierarchy(client, "CP-NF")
    plan_id = _setup_single_slab_plan(client, project_id)
    resp = client.post(
        "/api/v1/commission/payouts/calculate",
        json={"sale_contract_id": "no-contract", "commission_plan_id": plan_id},
    )
    assert resp.status_code == 404


def test_calculate_payout_plan_not_found_returns_404(client: TestClient):
    project_id, unit_id = _create_hierarchy(client, "CP-PNF")
    buyer_id = _create_buyer(client, "pnf@example.com")
    contract_id = _create_contract(client, unit_id, buyer_id, "CNT-PNF")
    resp = client.post(
        "/api/v1/commission/payouts/calculate",
        json={"sale_contract_id": contract_id, "commission_plan_id": "no-plan"},
    )
    assert resp.status_code == 404


def test_calculate_payout_inactive_plan_returns_422(client: TestClient):
    project_id, unit_id = _create_hierarchy(client, "CP-IP")
    buyer_id = _create_buyer(client, "ip@example.com")
    contract_id = _create_contract(client, unit_id, buyer_id, "CNT-IP")

    # Create inactive plan
    resp = client.post(
        "/api/v1/commission/plans",
        json={
            "project_id": project_id,
            "name": "Inactive Plan",
            "pool_percentage": 5.0,
            "is_active": False,
        },
    )
    plan_id = resp.json()["id"]
    _add_slab(client, plan_id, range_from=0, range_to=None, sequence=1)

    resp = client.post(
        "/api/v1/commission/payouts/calculate",
        json={"sale_contract_id": contract_id, "commission_plan_id": plan_id},
    )
    assert resp.status_code == 422


def test_calculate_payout_no_slabs_returns_422(client: TestClient):
    project_id, unit_id = _create_hierarchy(client, "CP-NS")
    buyer_id = _create_buyer(client, "ns@example.com")
    contract_id = _create_contract(client, unit_id, buyer_id, "CNT-NS")
    plan_id = _create_plan(client, project_id)  # no slabs added

    resp = client.post(
        "/api/v1/commission/payouts/calculate",
        json={"sale_contract_id": contract_id, "commission_plan_id": plan_id},
    )
    assert resp.status_code == 422


def test_duplicate_payout_returns_409(client: TestClient):
    """Calculating a payout twice for the same contract must fail."""
    project_id, unit_id = _create_hierarchy(client, "CP-D1")
    buyer_id = _create_buyer(client, "d1@example.com")
    contract_id = _create_contract(client, unit_id, buyer_id, "CNT-D1")
    plan_id = _setup_single_slab_plan(client, project_id)

    client.post(
        "/api/v1/commission/payouts/calculate",
        json={"sale_contract_id": contract_id, "commission_plan_id": plan_id},
    )
    resp = client.post(
        "/api/v1/commission/payouts/calculate",
        json={"sale_contract_id": contract_id, "commission_plan_id": plan_id},
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Payout retrieval tests
# ---------------------------------------------------------------------------


def test_get_payout(client: TestClient):
    project_id, unit_id = _create_hierarchy(client, "CP-GR1")
    buyer_id = _create_buyer(client, "gr1@example.com")
    contract_id = _create_contract(client, unit_id, buyer_id, "CNT-GR1")
    plan_id = _setup_single_slab_plan(client, project_id)

    payout = client.post(
        "/api/v1/commission/payouts/calculate",
        json={"sale_contract_id": contract_id, "commission_plan_id": plan_id},
    ).json()

    resp = client.get(f"/api/v1/commission/payouts/{payout['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == payout["id"]


def test_get_payout_not_found(client: TestClient):
    resp = client.get("/api/v1/commission/payouts/no-such-payout")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Approve payout tests
# ---------------------------------------------------------------------------


def test_approve_payout(client: TestClient):
    project_id, unit_id = _create_hierarchy(client, "CP-A1")
    buyer_id = _create_buyer(client, "a1@example.com")
    contract_id = _create_contract(client, unit_id, buyer_id, "CNT-A1")
    plan_id = _setup_single_slab_plan(client, project_id)

    payout = client.post(
        "/api/v1/commission/payouts/calculate",
        json={"sale_contract_id": contract_id, "commission_plan_id": plan_id},
    ).json()

    resp = client.post(f"/api/v1/commission/payouts/{payout['id']}/approve")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"
    assert data["approved_at"] is not None


def test_approve_already_approved_returns_409(client: TestClient):
    project_id, unit_id = _create_hierarchy(client, "CP-A2")
    buyer_id = _create_buyer(client, "a2@example.com")
    contract_id = _create_contract(client, unit_id, buyer_id, "CNT-A2")
    plan_id = _setup_single_slab_plan(client, project_id)

    payout = client.post(
        "/api/v1/commission/payouts/calculate",
        json={"sale_contract_id": contract_id, "commission_plan_id": plan_id},
    ).json()

    client.post(f"/api/v1/commission/payouts/{payout['id']}/approve")
    resp = client.post(f"/api/v1/commission/payouts/{payout['id']}/approve")
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Project list + summary tests
# ---------------------------------------------------------------------------


def test_list_project_payouts(client: TestClient):
    project_id, unit_id = _create_hierarchy(client, "CP-LP1")
    buyer_id = _create_buyer(client, "lp1@example.com")
    contract_id = _create_contract(client, unit_id, buyer_id, "CNT-LP1")
    plan_id = _setup_single_slab_plan(client, project_id)
    client.post(
        "/api/v1/commission/payouts/calculate",
        json={"sale_contract_id": contract_id, "commission_plan_id": plan_id},
    )

    resp = client.get(f"/api/v1/commission/projects/{project_id}/payouts")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    # List items must NOT include per-line detail (no N+1 queries)
    assert "lines" not in data["items"][0]


def test_list_project_payouts_invalid_project_returns_404(client: TestClient):
    resp = client.get("/api/v1/commission/projects/no-project/payouts")
    assert resp.status_code == 404


def test_project_summary_empty(client: TestClient):
    project_id, _ = _create_hierarchy(client, "CP-SUM0")
    resp = client.get(f"/api/v1/commission/projects/{project_id}/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_payouts"] == 0
    assert data["total_commission_pool"] == pytest.approx(0.0)
    assert data["total_gross_value"] == pytest.approx(0.0)


def test_project_summary_with_payouts(client: TestClient):
    project_id, unit_id = _create_hierarchy(client, "CP-SUM1")
    buyer_id = _create_buyer(client, "sum1@example.com")
    contract_id = _create_contract(client, unit_id, buyer_id, "CNT-SUM1", 500_000.0)
    plan_id = _setup_single_slab_plan(client, project_id, pool_percentage=5.0)
    payout = client.post(
        "/api/v1/commission/payouts/calculate",
        json={"sale_contract_id": contract_id, "commission_plan_id": plan_id},
    ).json()
    client.post(f"/api/v1/commission/payouts/{payout['id']}/approve")

    resp = client.get(f"/api/v1/commission/projects/{project_id}/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_payouts"] == 1
    assert data["approved_payouts"] == 1
    assert data["calculated_payouts"] == 0
    assert data["total_gross_value"] == pytest.approx(500_000.0)
    assert data["total_commission_pool"] == pytest.approx(25_000.0)


def test_project_summary_invalid_project_returns_404(client: TestClient):
    resp = client.get("/api/v1/commission/projects/no-project/summary")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PR-015A integrity tests
# ---------------------------------------------------------------------------


def test_calculate_payout_cross_project_plan_returns_422(client: TestClient):
    """Payout calculation must fail when the plan belongs to a different project."""
    # Project A has a unit and a contract
    project_a_id, unit_a_id = _create_hierarchy(client, "CP-XP-A")
    buyer_id = _create_buyer(client, "xpa@example.com")
    contract_id = _create_contract(client, unit_a_id, buyer_id, "CNT-XP-A")

    # Project B has its own commission plan
    project_b_id, _ = _create_hierarchy(client, "CP-XP-B")
    plan_b_id = _setup_single_slab_plan(client, project_b_id)

    # Calculating a payout for a contract from Project A using Project B's plan
    # must be rejected
    resp = client.post(
        "/api/v1/commission/payouts/calculate",
        json={"sale_contract_id": contract_id, "commission_plan_id": plan_b_id},
    )
    assert resp.status_code == 422, resp.text
    assert "project" in resp.json()["detail"].lower()


def test_add_slab_after_approved_payout_returns_409(client: TestClient):
    """Slabs cannot be added to a plan that already has an approved payout."""
    project_id, unit_id = _create_hierarchy(client, "CP-FREEZE")
    buyer_id = _create_buyer(client, "freeze@example.com")
    contract_id = _create_contract(client, unit_id, buyer_id, "CNT-FREEZE")
    plan_id = _setup_single_slab_plan(client, project_id)

    # Calculate and approve a payout
    payout = client.post(
        "/api/v1/commission/payouts/calculate",
        json={"sale_contract_id": contract_id, "commission_plan_id": plan_id},
    ).json()
    resp = client.post(f"/api/v1/commission/payouts/{payout['id']}/approve")
    assert resp.status_code == 200

    # Attempting to add a new slab must now be rejected
    resp = client.post(
        f"/api/v1/commission/plans/{plan_id}/slabs",
        json={
            "range_from": 0,
            "range_to": None,
            "sequence": 99,
            "sales_rep_pct": 60,
            "team_lead_pct": 20,
            "manager_pct": 10,
            "broker_pct": 5,
            "platform_pct": 5,
        },
    )
    assert resp.status_code == 409, resp.text


def test_calculate_payout_slab_not_starting_at_zero_returns_422(client: TestClient):
    """Payout calculation must fail when the first slab does not start at 0."""
    project_id, unit_id = _create_hierarchy(client, "CP-SZ")
    buyer_id = _create_buyer(client, "sz@example.com")
    contract_id = _create_contract(client, unit_id, buyer_id, "CNT-SZ")

    plan_id = _create_plan(client, project_id)
    # First slab starts at 100k, not 0
    _add_slab(client, plan_id, range_from=100_000, range_to=None, sequence=1)

    resp = client.post(
        "/api/v1/commission/payouts/calculate",
        json={"sale_contract_id": contract_id, "commission_plan_id": plan_id},
    )
    assert resp.status_code == 422, resp.text
    assert "range_from" in resp.json()["detail"] or "start at 0" in resp.json()["detail"]


def test_detail_payout_includes_lines(client: TestClient):
    """GET /payouts/{id} (detail endpoint) must include payout lines."""
    project_id, unit_id = _create_hierarchy(client, "CP-DL")
    buyer_id = _create_buyer(client, "dl@example.com")
    contract_id = _create_contract(client, unit_id, buyer_id, "CNT-DL")
    plan_id = _setup_single_slab_plan(client, project_id)

    payout = client.post(
        "/api/v1/commission/payouts/calculate",
        json={"sale_contract_id": contract_id, "commission_plan_id": plan_id},
    ).json()

    resp = client.get(f"/api/v1/commission/payouts/{payout['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert "lines" in data
    assert len(data["lines"]) == 5
    # value_covered (renamed from units_covered) holds the monetary value
    # covered in this slab bracket.  With a single open-ended slab [0, ∞),
    # every line covers the full 500,000 contract value.
    for ln in data["lines"]:
        assert "value_covered" in ln
        assert ln["value_covered"] == pytest.approx(500_000.0)
