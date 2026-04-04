"""
Tests for the Portfolio Intelligence API.

Validates:
  - Dashboard endpoint response shape and HTTP contract
  - Summary totals from seeded records
  - Project card generation
  - Null-safe handling when source data is absent (empty portfolio)
  - Risk flag derivation
  - No mutation of source records during dashboard retrieval
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Hierarchy helpers (shared with other test modules by convention)
# ---------------------------------------------------------------------------

def _create_project(client: TestClient, code: str = "PRJ-PORT", name: str = "Portfolio Project") -> str:
    resp = client.post("/api/v1/projects", json={"name": name, "code": code})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_unit(client: TestClient, proj_code: str = "PRJ-PORT") -> tuple[str, str]:
    """Create full hierarchy and return (project_id, unit_id)."""
    project_id = _create_project(client, proj_code, f"Project {proj_code}")
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
            "unit_number": "101",
            "unit_type": "studio",
            "internal_area": 100.0,
        },
    )
    assert unit_resp.status_code == 201, unit_resp.text
    unit_id = unit_resp.json()["id"]
    return project_id, unit_id


def _create_buyer(client: TestClient, email: str = "buyer@example.com") -> str:
    resp = client.post(
        "/api/v1/sales/buyers",
        json={"full_name": "Test Buyer", "email": email, "phone": "+971500000001"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_contract(
    client: TestClient,
    unit_id: str,
    buyer_id: str,
    contract_number: str = "CNT-001",
    price: float = 500000.0,
    currency: str = "AED",
) -> str:
    resp = client.post(
        "/api/v1/sales/contracts",
        json={
            "unit_id": unit_id,
            "buyer_id": buyer_id,
            "contract_number": contract_number,
            "contract_date": str(date.today()),
            "contract_price": price,
            "currency": currency,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Dashboard endpoint — empty portfolio
# ---------------------------------------------------------------------------


def test_dashboard_returns_200_on_empty_portfolio(client: TestClient):
    """GET /api/v1/portfolio/dashboard should succeed even with no data."""
    resp = client.get("/api/v1/portfolio/dashboard")
    assert resp.status_code == 200


def test_dashboard_empty_portfolio_schema(client: TestClient):
    """Empty portfolio should return correct schema with zero-value defaults."""
    resp = client.get("/api/v1/portfolio/dashboard")
    assert resp.status_code == 200
    data = resp.json()

    # Top-level keys
    assert "summary" in data
    assert "projects" in data
    assert "pipeline" in data
    assert "collections" in data
    assert "risk_flags" in data

    # Summary section
    summary = data["summary"]
    assert summary["total_projects"] == 0
    assert summary["active_projects"] == 0
    assert summary["total_units"] == 0
    assert summary["available_units"] == 0
    assert summary["reserved_units"] == 0
    assert summary["under_contract_units"] == 0
    assert summary["registered_units"] == 0
    assert summary["contracted_revenue"] == {}
    assert summary["collected_cash"] == {}
    assert summary["outstanding_balance"] == {}

    # Projects list
    assert data["projects"] == []

    # Pipeline section
    pipeline = data["pipeline"]
    assert pipeline["total_scenarios"] == 0
    assert pipeline["approved_scenarios"] == 0
    assert pipeline["total_feasibility_runs"] == 0
    assert pipeline["calculated_feasibility_runs"] == 0
    assert pipeline["projects_with_no_feasibility"] == 0

    # Collections section
    collections = data["collections"]
    assert collections["total_receivables"] == 0
    assert collections["overdue_receivables"] == 0
    assert collections["overdue_balance"] == {}
    assert collections["collection_rate_pct"] is None

    # Risk flags — empty when no data
    assert data["risk_flags"] == []


# ---------------------------------------------------------------------------
# Dashboard endpoint — authentication
# ---------------------------------------------------------------------------


def test_dashboard_requires_authentication(unauth_client: TestClient):
    """GET /api/v1/portfolio/dashboard without auth should return 401 or 403."""
    resp = unauth_client.get("/api/v1/portfolio/dashboard")
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Dashboard endpoint — project counts
# ---------------------------------------------------------------------------


def test_dashboard_summary_project_counts(client: TestClient):
    """Summary should reflect correct project counts."""
    _create_project(client, "PRJ-A", "Alpha")
    _create_project(client, "PRJ-B", "Beta")

    resp = client.get("/api/v1/portfolio/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["summary"]["total_projects"] == 2


def test_dashboard_projects_list_has_card_per_project(client: TestClient):
    """Each project should produce one project card."""
    _create_project(client, "PRJ-C1", "Card One")
    _create_project(client, "PRJ-C2", "Card Two")

    resp = client.get("/api/v1/portfolio/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["projects"]) == 2


def test_dashboard_project_card_schema(client: TestClient):
    """Project card should contain all required fields."""
    project_id, unit_id = _create_unit(client, "PRJ-CARD")

    resp = client.get("/api/v1/portfolio/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["projects"]) == 1

    card = data["projects"][0]
    assert "project_id" in card
    assert "project_name" in card
    assert "project_code" in card
    assert "status" in card
    assert "currency" in card
    assert "total_units" in card
    assert "available_units" in card
    assert "reserved_units" in card
    assert "under_contract_units" in card
    assert "registered_units" in card
    assert "contracted_revenue" in card
    assert "collected_cash" in card
    assert "outstanding_balance" in card
    assert "sell_through_pct" in card
    assert "health_badge" in card


# ---------------------------------------------------------------------------
# Dashboard endpoint — unit inventory counts
# ---------------------------------------------------------------------------


def test_dashboard_unit_counts_reflect_inventory(client: TestClient):
    """Summary unit counts should match inventory seeded."""
    project_id, unit_id = _create_unit(client, "PRJ-UNIT")

    resp = client.get("/api/v1/portfolio/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    summary = data["summary"]
    assert summary["total_units"] == 1
    assert summary["available_units"] == 1  # default unit status is 'available'


def test_dashboard_project_card_unit_counts(client: TestClient):
    """Project card unit counts should match inventory for the project."""
    project_id, unit_id = _create_unit(client, "PRJ-UCARD")

    resp = client.get("/api/v1/portfolio/dashboard")
    assert resp.status_code == 200
    cards = resp.json()["projects"]
    assert len(cards) == 1
    card = cards[0]
    assert card["total_units"] == 1
    assert card["available_units"] == 1


# ---------------------------------------------------------------------------
# Dashboard endpoint — contracted revenue
# ---------------------------------------------------------------------------


def test_dashboard_contracted_revenue_reflects_contracts(client: TestClient):
    """contracted_revenue should sum active contract prices."""
    project_id, unit_id = _create_unit(client, "PRJ-REV")
    buyer_id = _create_buyer(client, "buyer-rev@example.com")
    _create_contract(client, unit_id, buyer_id, "CNT-REV-001", price=300000.0)

    resp = client.get("/api/v1/portfolio/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["summary"]["contracted_revenue"] == {"AED": pytest.approx(300000.0, rel=1e-3)}
    # Project card should also reflect revenue (project-scoped, scalar with currency field)
    cards = data["projects"]
    assert len(cards) == 1
    assert cards[0]["currency"] == "AED"
    assert cards[0]["contracted_revenue"] == pytest.approx(300000.0, rel=1e-3)


# ---------------------------------------------------------------------------
# Dashboard endpoint — pipeline section
# ---------------------------------------------------------------------------


def test_dashboard_pipeline_counts_feasibility_runs(client: TestClient):
    """Pipeline section should count feasibility runs."""
    project_id = _create_project(client, "PRJ-PIPE", "Pipeline Project")
    resp_run = client.post(
        "/api/v1/feasibility/runs",
        json={"project_id": project_id, "scenario_name": "Base Case", "scenario_type": "base"},
    )
    assert resp_run.status_code == 201

    resp = client.get("/api/v1/portfolio/dashboard")
    assert resp.status_code == 200
    pipeline = resp.json()["pipeline"]
    assert pipeline["total_feasibility_runs"] == 1


def test_dashboard_pipeline_projects_with_no_feasibility(client: TestClient):
    """projects_with_no_feasibility should count projects without any feasibility run."""
    _create_project(client, "PRJ-NOFEAS", "No Feasibility")

    resp = client.get("/api/v1/portfolio/dashboard")
    assert resp.status_code == 200
    pipeline = resp.json()["pipeline"]
    assert pipeline["projects_with_no_feasibility"] == 1


def test_dashboard_pipeline_project_with_feasibility_not_counted(client: TestClient):
    """A project with at least one feasibility run should not count as missing feasibility."""
    project_id = _create_project(client, "PRJ-HASFEAS", "Has Feasibility")
    client.post(
        "/api/v1/feasibility/runs",
        json={"project_id": project_id, "scenario_name": "Base", "scenario_type": "base"},
    )

    resp = client.get("/api/v1/portfolio/dashboard")
    assert resp.status_code == 200
    pipeline = resp.json()["pipeline"]
    assert pipeline["projects_with_no_feasibility"] == 0


# ---------------------------------------------------------------------------
# Dashboard endpoint — risk flags
# ---------------------------------------------------------------------------


def test_dashboard_no_risk_flags_on_empty_portfolio(client: TestClient):
    """No risk flags should be emitted on an empty portfolio."""
    resp = client.get("/api/v1/portfolio/dashboard")
    assert resp.status_code == 200
    assert resp.json()["risk_flags"] == []


def test_dashboard_risk_flag_schema(client: TestClient):
    """Risk flags should include all required fields when present.

    Creates a proper relational receivable via the full API stack (project →
    unit → buyer → contract → payment plan with past due date → generate
    receivables).  With a past start_date the receivable is immediately
    derived as overdue, triggering the overdue_receivables risk flag.
    """
    project_id, unit_id = _create_unit(client, "PRJ-RISK")
    buyer_id = _create_buyer(client, "risk-buyer@example.com")
    contract_id = _create_contract(client, unit_id, buyer_id, "CNT-RISK-001", price=100000.0)

    # Create a payment plan with a start date well in the past so the
    # installment due_date is overdue when receivables are generated.
    plan_resp = client.post(
        "/api/v1/payment-plans",
        json={
            "contract_id": contract_id,
            "plan_name": "Overdue Test Plan",
            "number_of_installments": 1,
            "start_date": "2024-01-01",
        },
    )
    assert plan_resp.status_code == 201, plan_resp.text

    # Generate receivables — the single installment due 2024-01-01 will be overdue.
    gen_resp = client.post(f"/api/v1/contracts/{contract_id}/receivables/generate")
    assert gen_resp.status_code == 201, gen_resp.text
    assert gen_resp.json()["generated"] >= 1

    resp = client.get("/api/v1/portfolio/dashboard")
    assert resp.status_code == 200
    flags = resp.json()["risk_flags"]
    assert len(flags) >= 1

    overdue_flag = next((f for f in flags if f["flag_type"] == "overdue_receivables"), None)
    assert overdue_flag is not None
    assert "severity" in overdue_flag
    assert "description" in overdue_flag
    assert overdue_flag["severity"] in ("warning", "critical")


# ---------------------------------------------------------------------------
# Null-safety: project card when no units exist
# ---------------------------------------------------------------------------


def test_dashboard_project_card_sell_through_none_when_no_units(client: TestClient):
    """sell_through_pct and health_badge should be None when project has no units."""
    _create_project(client, "PRJ-EMPTY", "Empty Project")

    resp = client.get("/api/v1/portfolio/dashboard")
    assert resp.status_code == 200
    cards = resp.json()["projects"]
    assert len(cards) == 1
    card = cards[0]
    assert card["sell_through_pct"] is None
    assert card["health_badge"] is None


# ---------------------------------------------------------------------------
# Source record immutability
# ---------------------------------------------------------------------------


def test_dashboard_does_not_mutate_projects(client: TestClient):
    """Dashboard retrieval must not change project data."""
    project_id = _create_project(client, "PRJ-MUT", "Immutable Project")

    # Fetch project state before
    before = client.get(f"/api/v1/projects/{project_id}").json()

    # Call dashboard
    resp = client.get("/api/v1/portfolio/dashboard")
    assert resp.status_code == 200

    # Fetch project state after
    after = client.get(f"/api/v1/projects/{project_id}").json()

    assert before["name"] == after["name"]
    assert before["status"] == after["status"]
    assert before["code"] == after["code"]


# ---------------------------------------------------------------------------
# Collection rate — aggregation guard: mixed-currency yields None
# ---------------------------------------------------------------------------


def _generate_receivables_for_contract(client: TestClient, contract_id: str) -> None:
    """Create a single-installment payment plan (future date) and generate receivables."""
    from datetime import timedelta

    future_date = (date.today() + timedelta(days=30)).isoformat()
    plan_resp = client.post(
        "/api/v1/payment-plans",
        json={
            "contract_id": contract_id,
            "plan_name": "Test Plan",
            "number_of_installments": 1,
            "start_date": future_date,
        },
    )
    assert plan_resp.status_code == 201, plan_resp.text
    gen_resp = client.post(f"/api/v1/contracts/{contract_id}/receivables/generate")
    assert gen_resp.status_code == 201, gen_resp.text


def test_collection_rate_single_currency_is_computed(client: TestClient):
    """collection_rate_pct is computed when all receivables share a single currency.

    Creates two contracts (both AED) each with a generated receivable so that
    amount_paid == 0 and balance_due > 0 across a single-currency portfolio.
    The rate must be 0 % (nothing collected yet) and definitely not None.
    """
    proj1_id, unit1_id = _create_unit(client, "PRJ-COL1")
    buyer1_id = _create_buyer(client, "col1@example.com")
    contract1_id = _create_contract(
        client, unit1_id, buyer1_id, "CNT-COL1-001", price=100_000.0, currency="AED"
    )
    _generate_receivables_for_contract(client, contract1_id)

    proj2_id, unit2_id = _create_unit(client, "PRJ-COL2")
    buyer2_id = _create_buyer(client, "col2@example.com")
    contract2_id = _create_contract(
        client, unit2_id, buyer2_id, "CNT-COL2-001", price=200_000.0, currency="AED"
    )
    _generate_receivables_for_contract(client, contract2_id)

    resp = client.get("/api/v1/portfolio/dashboard")
    assert resp.status_code == 200
    collection_rate_pct = resp.json()["collections"]["collection_rate_pct"]
    # Rate is computable (0.0 % because nothing has been paid yet)
    assert collection_rate_pct is not None
    assert collection_rate_pct == pytest.approx(0.0, abs=1e-2)


def test_collection_rate_mixed_currency_is_none(client: TestClient):
    """collection_rate_pct is None when receivables span multiple currencies.

    Creates one AED receivable and one JOD receivable.  Summing their amounts
    without FX conversion is invalid, so the collection rate must be None.
    """
    proj1_id, unit1_id = _create_unit(client, "PRJ-MCA")
    buyer1_id = _create_buyer(client, "mca1@example.com")
    contract1_id = _create_contract(
        client, unit1_id, buyer1_id, "CNT-MCA-001", price=100_000.0, currency="AED"
    )
    _generate_receivables_for_contract(client, contract1_id)

    proj2_id, unit2_id = _create_unit(client, "PRJ-MCB")
    buyer2_id = _create_buyer(client, "mca2@example.com")
    contract2_id = _create_contract(
        client, unit2_id, buyer2_id, "CNT-MCB-001", price=50_000.0, currency="JOD"
    )
    _generate_receivables_for_contract(client, contract2_id)

    resp = client.get("/api/v1/portfolio/dashboard")
    assert resp.status_code == 200
    collection_rate_pct = resp.json()["collections"]["collection_rate_pct"]
    # Mixed-currency: rate must not be computed
    assert collection_rate_pct is None
