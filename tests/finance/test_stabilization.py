"""
tests/finance/test_stabilization.py

PR-27: Platform Stabilization & Production Hardening

Validates edge-case boundaries identified during the final platform audit:

  1. Authentication enforcement  — all finance endpoints reject unauthenticated
     requests (401) regardless of the specific route.
  2. Zero sales / empty project  — finance summary endpoints return safe zero
     values when a project has no contracts.
  3. Zero receivables             — aging and collection endpoints handle a
     project with no outstanding receivables gracefully.
  4. Empty portfolio              — portfolio-level endpoints return safe zeros
     when no projects or contracts exist at all.
  5. Empty land registry          — the land parcel list endpoint returns an
     empty array rather than raising an error.
  6. On-hold projects             — projects with status=on_hold remain
     accessible through all finance endpoints and return valid data.
"""

import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_project(db_session: Session, code: str, status: str = "active") -> str:
    from app.modules.projects.models import Project

    project = Project(name=f"Stab Project {code}", code=code, status=status)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project.id


def _make_unit(db_session: Session, project_id: str, unit_number: str) -> str:
    from app.modules.buildings.models import Building
    from app.modules.floors.models import Floor
    from app.modules.phases.models import Phase
    from app.modules.units.models import Unit

    phase = Phase(project_id=project_id, name="Phase 1", sequence=1)
    db_session.add(phase)
    db_session.flush()

    building = Building(phase_id=phase.id, name="Block A", code=f"ST-BLK-{unit_number}")
    db_session.add(building)
    db_session.flush()

    floor = Floor(
        building_id=building.id,
        name="Floor 1",
        code="ST-FL-01",
        sequence_number=1,
    )
    db_session.add(floor)
    db_session.flush()

    unit = Unit(
        floor_id=floor.id,
        unit_number=unit_number,
        unit_type="studio",
        internal_area=80.0,
        status="available",
    )
    db_session.add(unit)
    db_session.commit()
    db_session.refresh(unit)
    return unit.id


def _make_contract(
    db_session: Session,
    unit_id: str,
    contract_price: float,
    contract_number: str,
    email: str,
) -> str:
    from app.modules.sales.models import Buyer, SalesContract

    buyer = Buyer(full_name="Stab Buyer", email=email, phone="+9620000099")
    db_session.add(buyer)
    db_session.flush()

    contract = SalesContract(
        unit_id=unit_id,
        buyer_id=buyer.id,
        contract_number=contract_number,
        contract_date=date(2026, 1, 1),
        contract_price=contract_price,
    )
    db_session.add(contract)
    db_session.commit()
    db_session.refresh(contract)
    return contract.id


def _make_installment(
    db_session: Session,
    contract_id: str,
    amount: float,
    installment_number: int,
    due_date: date,
    status: str = "pending",
) -> None:
    from app.modules.sales.models import ContractPaymentSchedule

    line = ContractPaymentSchedule(
        contract_id=contract_id,
        installment_number=installment_number,
        due_date=due_date,
        amount=amount,
        status=status,
    )
    db_session.add(line)
    db_session.commit()


# ---------------------------------------------------------------------------
# 1. Authentication enforcement
# ---------------------------------------------------------------------------


class TestAuthEnforcement:
    """All protected finance endpoints must return 401 without a valid token."""

    def test_portfolio_summary_rejects_unauthenticated(self, unauth_client: TestClient):
        """GET /finance/portfolio/summary must require authentication."""
        response = unauth_client.get("/api/v1/finance/portfolio/summary")
        assert response.status_code in (401, 403)

    def test_treasury_monitoring_rejects_unauthenticated(self, unauth_client: TestClient):
        """GET /finance/treasury/monitoring must require authentication."""
        response = unauth_client.get("/api/v1/finance/treasury/monitoring")
        assert response.status_code in (401, 403)

    def test_project_summary_rejects_unauthenticated(self, unauth_client: TestClient):
        """GET /finance/projects/{id}/summary must require authentication."""
        response = unauth_client.get("/api/v1/finance/projects/any-id/summary")
        assert response.status_code in (401, 403)

    def test_revenue_overview_rejects_unauthenticated(self, unauth_client: TestClient):
        """GET /finance/revenue/overview must require authentication."""
        response = unauth_client.get("/api/v1/finance/revenue/overview")
        assert response.status_code in (401, 403)

    def test_aging_overview_rejects_unauthenticated(self, unauth_client: TestClient):
        """GET /finance/receivables/aging-overview must require authentication."""
        response = unauth_client.get("/api/v1/finance/receivables/aging-overview")
        assert response.status_code in (401, 403)

    def test_collections_alerts_rejects_unauthenticated(self, unauth_client: TestClient):
        """GET /finance/collections/alerts must require authentication."""
        response = unauth_client.get("/api/v1/finance/collections/alerts")
        assert response.status_code in (401, 403)

    def test_cashflow_forecast_rejects_unauthenticated(self, unauth_client: TestClient):
        """GET /finance/cashflow/forecast must require authentication."""
        response = unauth_client.get("/api/v1/finance/cashflow/forecast")
        assert response.status_code in (401, 403)

    def test_projects_endpoint_rejects_unauthenticated(self, unauth_client: TestClient):
        """GET /projects must require authentication."""
        response = unauth_client.get("/api/v1/projects")
        assert response.status_code in (401, 403)

    def test_sales_contracts_endpoint_rejects_unauthenticated(
        self, unauth_client: TestClient
    ):
        """GET /sales/contracts must require authentication."""
        response = unauth_client.get("/api/v1/sales/contracts")
        assert response.status_code in (401, 403)

    def test_land_parcels_endpoint_rejects_unauthenticated(
        self, unauth_client: TestClient
    ):
        """GET /land/parcels must require authentication."""
        response = unauth_client.get("/api/v1/land/parcels")
        assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# 2. Zero sales / empty project
# ---------------------------------------------------------------------------


class TestZeroSalesEdgeCases:
    """Finance endpoints handle projects with no contracts safely."""

    def test_project_summary_zero_contracts(
        self, client: TestClient, db_session: Session
    ):
        """Project with no contracts returns all-zero financial summary."""
        project_id = _make_project(db_session, "STAB-ZS-01")
        resp = client.get(f"/api/v1/finance/projects/{project_id}/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_contract_value"] == 0.0
        assert data["total_collected"] == 0.0
        assert data["total_receivable"] == 0.0
        assert data["collection_ratio"] == 0.0

    def test_project_revenue_summary_zero_contracts(
        self, client: TestClient, db_session: Session
    ):
        """Project with no contracts returns zero revenue recognition summary."""
        project_id = _make_project(db_session, "STAB-ZS-02")
        resp = client.get(f"/api/v1/finance/projects/{project_id}/revenue-summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_recognized_revenue"] == 0.0
        assert data["total_deferred_revenue"] == 0.0

    def test_project_aging_zero_contracts(
        self, client: TestClient, db_session: Session
    ):
        """Project with no contracts returns zero aging totals."""
        project_id = _make_project(db_session, "STAB-ZS-03")
        resp = client.get(f"/api/v1/finance/projects/{project_id}/aging")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_outstanding"] == 0.0

    def test_project_cashflow_forecast_zero_contracts(
        self, client: TestClient, db_session: Session
    ):
        """Project with no contracts returns zero cashflow forecast."""
        project_id = _make_project(db_session, "STAB-ZS-04")
        resp = client.get(f"/api/v1/finance/cashflow/forecast/project/{project_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_expected"] == 0.0
        assert data["monthly_entries"] == []


# ---------------------------------------------------------------------------
# 3. Zero receivables
# ---------------------------------------------------------------------------


class TestZeroReceivablesEdgeCases:
    """Finance endpoints handle projects with all-paid receivables safely."""

    def test_portfolio_aging_no_outstanding(
        self, client: TestClient, db_session: Session
    ):
        """Portfolio aging overview returns zeros when all installments are paid."""
        project_id = _make_project(db_session, "STAB-ZR-01")
        unit_id = _make_unit(db_session, project_id, "ZR-U01")
        contract_id = _make_contract(
            db_session, unit_id, 500_000.0, "ZR-C001", "zr@example.com"
        )
        # All installments paid
        _make_installment(
            db_session,
            contract_id,
            500_000.0,
            1,
            date(2025, 6, 1),
            status="paid",
        )
        resp = client.get("/api/v1/finance/receivables/aging-overview")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_outstanding"] == 0.0

    def test_contract_aging_fully_paid(
        self, client: TestClient, db_session: Session
    ):
        """Contract aging returns zero outstanding when all installments are paid."""
        project_id = _make_project(db_session, "STAB-ZR-02")
        unit_id = _make_unit(db_session, project_id, "ZR-U02")
        contract_id = _make_contract(
            db_session, unit_id, 300_000.0, "ZR-C002", "zr2@example.com"
        )
        _make_installment(
            db_session,
            contract_id,
            300_000.0,
            1,
            date(2025, 5, 1),
            status="paid",
        )
        resp = client.get(f"/api/v1/finance/contracts/{contract_id}/aging")
        assert resp.status_code == 200
        data = resp.json()
        assert data["outstanding_amount"] == 0.0


# ---------------------------------------------------------------------------
# 4. Empty portfolio
# ---------------------------------------------------------------------------


class TestEmptyPortfolioEdgeCases:
    """Portfolio-level endpoints handle an empty system gracefully."""

    def test_portfolio_summary_empty(self, client: TestClient):
        """GET /finance/portfolio/summary with no data returns valid zeros."""
        resp = client.get("/api/v1/finance/portfolio/summary")
        assert resp.status_code == 200
        data = resp.json()
        # portfolio/summary — monetary totals are now grouped dicts (empty when no data)
        assert data["total_revenue_recognized"] == {}
        assert data["total_receivables"] == {}
        assert data["project_summaries"] == []

    def test_revenue_overview_empty(self, client: TestClient):
        """GET /finance/revenue/overview with no data returns valid zeros."""
        resp = client.get("/api/v1/finance/revenue/overview")
        assert resp.status_code == 200
        data = resp.json()
        # Monetary fields are now grouped dicts — empty when no data
        assert data["total_recognized_revenue"] == {}
        assert data["total_deferred_revenue"] == {}

    def test_aging_overview_empty(self, client: TestClient):
        """GET /finance/receivables/aging-overview with no data returns zeros."""
        resp = client.get("/api/v1/finance/receivables/aging-overview")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_outstanding"] == 0.0

    def test_cashflow_forecast_empty(self, client: TestClient):
        """GET /finance/cashflow/forecast with no data returns empty forecast."""
        resp = client.get("/api/v1/finance/cashflow/forecast")
        assert resp.status_code == 200
        data = resp.json()
        # total_expected is now grouped by currency — empty dict when no data
        assert data["total_expected"] == {}
        assert data["monthly_entries"] == []

    def test_collections_alerts_empty(self, client: TestClient):
        """GET /finance/collections/alerts with no data returns empty list."""
        resp = client.get("/api/v1/finance/collections/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0


# ---------------------------------------------------------------------------
# 5. Empty land registry
# ---------------------------------------------------------------------------


class TestEmptyLandRegistry:
    """Land parcel list endpoint handles an empty registry gracefully."""

    def test_land_parcels_empty_returns_empty_list(self, client: TestClient):
        """GET /land/parcels with no parcels must return an empty items list."""
        resp = client.get("/api/v1/land/parcels")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["items"] == []
        assert data["total"] == 0

    def test_land_parcels_filter_by_nonexistent_project_returns_empty(
        self, client: TestClient
    ):
        """Filtering land parcels by a project with no parcels returns empty items."""
        resp = client.get("/api/v1/land/parcels?project_id=nonexistent-id")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["items"] == []


# ---------------------------------------------------------------------------
# 6. On-hold projects
# ---------------------------------------------------------------------------


class TestOnHoldProjects:
    """Projects with status=on_hold remain accessible through finance endpoints."""

    def test_on_hold_project_finance_summary_accessible(
        self, client: TestClient, db_session: Session
    ):
        """Finance summary for an on_hold project must return 200 with zero values."""
        project_id = _make_project(db_session, "STAB-OH-01", status="on_hold")
        resp = client.get(f"/api/v1/finance/projects/{project_id}/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == project_id

    def test_on_hold_project_aging_accessible(
        self, client: TestClient, db_session: Session
    ):
        """Aging endpoint for an on_hold project must return 200."""
        project_id = _make_project(db_session, "STAB-OH-02", status="on_hold")
        resp = client.get(f"/api/v1/finance/projects/{project_id}/aging")
        assert resp.status_code == 200

    def test_on_hold_project_revenue_summary_accessible(
        self, client: TestClient, db_session: Session
    ):
        """Revenue summary for an on_hold project must return 200."""
        project_id = _make_project(db_session, "STAB-OH-03", status="on_hold")
        resp = client.get(f"/api/v1/finance/projects/{project_id}/revenue-summary")
        assert resp.status_code == 200

    def test_on_hold_project_cashflow_forecast_accessible(
        self, client: TestClient, db_session: Session
    ):
        """Cashflow forecast for an on_hold project must return 200."""
        project_id = _make_project(db_session, "STAB-OH-04", status="on_hold")
        resp = client.get(f"/api/v1/finance/cashflow/forecast/project/{project_id}")
        assert resp.status_code == 200

    def test_on_hold_project_included_in_portfolio_summary(
        self, client: TestClient, db_session: Session
    ):
        """On-hold project with a contract must appear in portfolio summary."""
        project_id = _make_project(db_session, "STAB-OH-05", status="on_hold")
        unit_id = _make_unit(db_session, project_id, "OH-U01")
        _make_contract(
            db_session, unit_id, 200_000.0, "OH-C001", "oh5@example.com"
        )
        resp = client.get("/api/v1/finance/portfolio/summary")
        assert resp.status_code == 200
        data = resp.json()
        project_ids = [p["project_id"] for p in data["project_summaries"]]
        assert project_id in project_ids

    def test_pipeline_project_finance_summary_accessible(
        self, client: TestClient, db_session: Session
    ):
        """Finance summary for a pipeline project must return 200."""
        project_id = _make_project(db_session, "STAB-PL-01", status="pipeline")
        resp = client.get(f"/api/v1/finance/projects/{project_id}/summary")
        assert resp.status_code == 200

    def test_completed_project_finance_summary_accessible(
        self, client: TestClient, db_session: Session
    ):
        """Finance summary for a completed project must return 200."""
        project_id = _make_project(db_session, "STAB-CP-01", status="completed")
        resp = client.get(f"/api/v1/finance/projects/{project_id}/summary")
        assert resp.status_code == 200
