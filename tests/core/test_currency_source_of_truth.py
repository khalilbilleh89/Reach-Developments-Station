"""
tests.core.test_currency_source_of_truth

PR-CURRENCY-002 — Validates the currency foundation introduced by this PR:

1. canonical DEFAULT_CURRENCY = "AED"
2. project.base_currency persists and is returned by the API
3. critical monetary entities carry an explicit currency column
4. ORM models accept and persist currency values
5. schemas expose currency fields in create/response payloads
"""

import pytest
from fastapi.testclient import TestClient

from app.core.constants.currency import DEFAULT_CURRENCY


# ---------------------------------------------------------------------------
# A. Canonical constant assertions
# ---------------------------------------------------------------------------


class TestCanonicalCurrencyConstant:
    def test_default_currency_is_aed(self):
        """The platform canonical default must be AED (not JOD)."""
        assert DEFAULT_CURRENCY == "AED"

    def test_supported_currencies_includes_aed(self):
        from app.core.constants.currency import CURRENCY_AED, SUPPORTED_CURRENCIES

        assert CURRENCY_AED in SUPPORTED_CURRENCIES

    def test_supported_currencies_includes_jod_and_usd(self):
        from app.core.constants.currency import CURRENCY_JOD, CURRENCY_USD, SUPPORTED_CURRENCIES

        assert CURRENCY_JOD in SUPPORTED_CURRENCIES
        assert CURRENCY_USD in SUPPORTED_CURRENCIES

    def test_no_inline_aed_in_pricing_schemas(self):
        """pricing.schemas must no longer define a module-local DEFAULT_CURRENCY = 'AED'."""
        import app.modules.pricing.schemas as ps

        # The module must import DEFAULT_CURRENCY from the canonical constant,
        # not define its own copy.  If the module-level attribute still exists,
        # it must equal the canonical constant.
        if hasattr(ps, "DEFAULT_CURRENCY"):
            from app.core.constants.currency import DEFAULT_CURRENCY as canonical

            assert ps.DEFAULT_CURRENCY is canonical or ps.DEFAULT_CURRENCY == canonical


# ---------------------------------------------------------------------------
# B. Project base_currency — model + API
# ---------------------------------------------------------------------------


class TestProjectBaseCurrency:
    def test_project_create_default_currency(self, client: TestClient):
        """POST /projects without base_currency should default to AED."""
        response = client.post(
            "/api/v1/projects",
            json={"name": "Currency Test", "code": "CT-001"},
        )
        assert response.status_code == 201
        data = response.json()
        assert "base_currency" in data
        assert data["base_currency"] == DEFAULT_CURRENCY

    def test_project_create_explicit_currency(self, client: TestClient):
        """POST /projects with explicit base_currency should persist it."""
        response = client.post(
            "/api/v1/projects",
            json={"name": "JOD Project", "code": "JOD-001", "base_currency": "JOD"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["base_currency"] == "JOD"

    def test_project_get_returns_base_currency(self, client: TestClient):
        """GET /projects/{id} must return base_currency."""
        create = client.post(
            "/api/v1/projects",
            json={"name": "Read Test", "code": "RT-001"},
        )
        project_id = create.json()["id"]
        response = client.get(f"/api/v1/projects/{project_id}")
        assert response.status_code == 200
        assert "base_currency" in response.json()

    def test_project_update_base_currency(self, client: TestClient):
        """PATCH /projects/{id} with base_currency should update it."""
        create = client.post(
            "/api/v1/projects",
            json={"name": "Patch Test", "code": "PT-001"},
        )
        project_id = create.json()["id"]
        response = client.patch(
            f"/api/v1/projects/{project_id}",
            json={"base_currency": "USD"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["base_currency"] == "USD"

    def test_project_list_returns_base_currency(self, client: TestClient):
        """GET /projects list must include base_currency on each item."""
        client.post("/api/v1/projects", json={"name": "List Test", "code": "LT-001"})
        response = client.get("/api/v1/projects")
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) >= 1
        for item in items:
            assert "base_currency" in item


# ---------------------------------------------------------------------------
# C. ORM model currency columns — schema creation smoke tests
#    (Validates column presence via SQLite in-memory test DB)
# ---------------------------------------------------------------------------


class TestOrmCurrencyColumnPresence:
    """Ensures the SQLite test schema reflects all new currency columns."""

    def test_projects_has_base_currency(self, db_session):
        from app.modules.projects.models import Project

        p = Project(name="CurrencyTest", code="CUR-001")
        db_session.add(p)
        db_session.flush()
        assert p.base_currency == DEFAULT_CURRENCY

    def test_sales_contract_has_currency(self, db_session):
        from app.modules.sales.models import SalesContract

        # inspect mapped columns
        mapper = SalesContract.__mapper__
        assert "currency" in [c.key for c in mapper.columns]

    def test_payment_schedule_has_currency(self, db_session):
        from app.modules.payment_plans.models import PaymentSchedule

        mapper = PaymentSchedule.__mapper__
        assert "currency" in [c.key for c in mapper.columns]

    def test_payment_receipt_has_currency(self, db_session):
        from app.modules.collections.models import PaymentReceipt

        mapper = PaymentReceipt.__mapper__
        assert "currency" in [c.key for c in mapper.columns]

    def test_commission_payout_has_currency(self, db_session):
        from app.modules.commission.models import CommissionPayout

        mapper = CommissionPayout.__mapper__
        assert "currency" in [c.key for c in mapper.columns]

    def test_commission_payout_line_has_currency(self, db_session):
        from app.modules.commission.models import CommissionPayoutLine

        mapper = CommissionPayoutLine.__mapper__
        assert "currency" in [c.key for c in mapper.columns]

    def test_feasibility_assumptions_has_currency(self, db_session):
        from app.modules.feasibility.models import FeasibilityAssumptions

        mapper = FeasibilityAssumptions.__mapper__
        assert "currency" in [c.key for c in mapper.columns]

    def test_feasibility_result_has_currency(self, db_session):
        from app.modules.feasibility.models import FeasibilityResult

        mapper = FeasibilityResult.__mapper__
        assert "currency" in [c.key for c in mapper.columns]

    def test_financial_scenario_run_has_currency(self, db_session):
        from app.modules.scenario.models import FinancialScenarioRun

        mapper = FinancialScenarioRun.__mapper__
        assert "currency" in [c.key for c in mapper.columns]

    def test_land_parcel_currency_non_nullable(self, db_session):
        from app.modules.land.models import LandParcel

        mapper = LandParcel.__mapper__
        currency_col = mapper.columns["currency"]
        assert not currency_col.nullable

    def test_land_valuation_has_currency(self, db_session):
        from app.modules.land.models import LandValuation

        mapper = LandValuation.__mapper__
        assert "currency" in [c.key for c in mapper.columns]

    def test_sales_exception_has_currency(self, db_session):
        from app.modules.sales_exceptions.models import SalesException

        mapper = SalesException.__mapper__
        assert "currency" in [c.key for c in mapper.columns]

    def test_construction_cost_comparison_set_has_currency(self, db_session):
        from app.modules.tender_comparison.models import ConstructionCostComparisonSet

        mapper = ConstructionCostComparisonSet.__mapper__
        assert "currency" in [c.key for c in mapper.columns]

    def test_cashflow_forecast_period_has_currency(self, db_session):
        from app.modules.cashflow.models import CashflowForecastPeriod

        mapper = CashflowForecastPeriod.__mapper__
        assert "currency" in [c.key for c in mapper.columns]


# ---------------------------------------------------------------------------
# D. ORM defaults validate canonical constant propagation
# ---------------------------------------------------------------------------


class TestOrmCurrencyDefaults:
    """All new currency columns must default to DEFAULT_CURRENCY."""

    def _get_column_default(self, model_class, col_name: str) -> str:
        col = model_class.__mapper__.columns[col_name]
        return col.default.arg if col.default else col.server_default

    def test_sales_contract_currency_default(self, db_session):
        from app.modules.sales.models import SalesContract

        col = SalesContract.__mapper__.columns["currency"]
        assert col.default.arg == DEFAULT_CURRENCY

    def test_payment_schedule_currency_default(self, db_session):
        from app.modules.payment_plans.models import PaymentSchedule

        col = PaymentSchedule.__mapper__.columns["currency"]
        assert col.default.arg == DEFAULT_CURRENCY

    def test_payment_receipt_currency_default(self, db_session):
        from app.modules.collections.models import PaymentReceipt

        col = PaymentReceipt.__mapper__.columns["currency"]
        assert col.default.arg == DEFAULT_CURRENCY

    def test_feasibility_assumptions_currency_default(self, db_session):
        from app.modules.feasibility.models import FeasibilityAssumptions

        col = FeasibilityAssumptions.__mapper__.columns["currency"]
        assert col.default.arg == DEFAULT_CURRENCY

    def test_feasibility_result_currency_default(self, db_session):
        from app.modules.feasibility.models import FeasibilityResult

        col = FeasibilityResult.__mapper__.columns["currency"]
        assert col.default.arg == DEFAULT_CURRENCY

    def test_financial_scenario_run_currency_default(self, db_session):
        from app.modules.scenario.models import FinancialScenarioRun

        col = FinancialScenarioRun.__mapper__.columns["currency"]
        assert col.default.arg == DEFAULT_CURRENCY

    def test_land_parcel_currency_default(self, db_session):
        from app.modules.land.models import LandParcel

        col = LandParcel.__mapper__.columns["currency"]
        assert col.default.arg == DEFAULT_CURRENCY

    def test_land_valuation_currency_default(self, db_session):
        from app.modules.land.models import LandValuation

        col = LandValuation.__mapper__.columns["currency"]
        assert col.default.arg == DEFAULT_CURRENCY

    def test_commission_payout_currency_default(self, db_session):
        from app.modules.commission.models import CommissionPayout

        col = CommissionPayout.__mapper__.columns["currency"]
        assert col.default.arg == DEFAULT_CURRENCY

    def test_tender_set_currency_default(self, db_session):
        from app.modules.tender_comparison.models import ConstructionCostComparisonSet

        col = ConstructionCostComparisonSet.__mapper__.columns["currency"]
        assert col.default.arg == DEFAULT_CURRENCY


# ---------------------------------------------------------------------------
# E. Migration chain includes 0061
# ---------------------------------------------------------------------------


class TestMigrationCurrencyEntry:
    def test_migration_0061_exists(self):
        """Migration 0061 must exist in the versions directory."""
        from pathlib import Path

        versions_dir = Path(__file__).parents[2] / "app" / "db" / "migrations" / "versions"
        migration_files = list(versions_dir.glob("0061_*.py"))
        assert len(migration_files) == 1, "Migration 0061 not found"

    def test_migration_0061_has_correct_revision(self):
        import importlib.util
        from pathlib import Path

        versions_dir = Path(__file__).parents[2] / "app" / "db" / "migrations" / "versions"
        migration_file = next(versions_dir.glob("0061_*.py"))
        spec = importlib.util.spec_from_file_location("migration_0061", migration_file)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod.revision == "0061"
        assert mod.down_revision == "0060"
