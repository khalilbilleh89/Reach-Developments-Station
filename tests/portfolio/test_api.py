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
from sqlalchemy.orm import Session


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
    phase_id = client.post(
        "/api/v1/phases",
        json={"project_id": project_id, "name": "Phase 1", "sequence": 1},
    ).json()["id"]
    building_id = client.post(
        f"/api/v1/phases/{phase_id}/buildings",
        json={"name": "Block A", "code": "BLK-A"},
    ).json()["id"]
    floor_id = client.post(
        f"/api/v1/buildings/{building_id}/floors",
        json={"name": "Floor 1", "code": "FL-01", "sequence_number": 1},
    ).json()["id"]
    unit_id = client.post(
        "/api/v1/units",
        json={
            "floor_id": floor_id,
            "unit_number": "101",
            "unit_type": "studio",
            "internal_area": 100.0,
        },
    ).json()["id"]
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
) -> str:
    resp = client.post(
        "/api/v1/sales/contracts",
        json={
            "unit_id": unit_id,
            "buyer_id": buyer_id,
            "contract_number": contract_number,
            "contract_date": str(date.today()),
            "contract_price": price,
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
    assert summary["contracted_revenue"] == 0.0
    assert summary["collected_cash"] == 0.0
    assert summary["outstanding_balance"] == 0.0

    # Projects list
    assert data["projects"] == []

    # Pipeline section
    pipeline = data["pipeline"]
    assert pipeline["total_scenarios"] == 0
    assert pipeline["total_feasibility_runs"] == 0
    assert pipeline["projects_with_no_feasibility"] == 0

    # Collections section
    collections = data["collections"]
    assert collections["total_receivables"] == 0
    assert collections["overdue_receivables"] == 0
    assert collections["overdue_balance"] == 0.0
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
    assert data["summary"]["contracted_revenue"] == pytest.approx(300000.0, rel=1e-3)
    # Project card should also reflect revenue
    cards = data["projects"]
    assert len(cards) == 1
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


def test_dashboard_risk_flag_schema(client: TestClient, db_session: Session):
    """Risk flags should include all required fields when present."""
    # Seed an overdue receivable directly via ORM to trigger the flag
    from app.modules.receivables.models import Receivable

    rec = Receivable(
        contract_id="fake-contract",
        installment_id="fake-install",
        receivable_number=1,
        due_date=date(2025, 1, 1),
        amount_due=50000.0,
        amount_paid=0.0,
        balance_due=50000.0,
        status="overdue",
        currency="AED",
    )
    db_session.add(rec)
    db_session.commit()

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
