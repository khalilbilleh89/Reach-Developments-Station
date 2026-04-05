"""
tests.core.test_currency_governance

PR-CURRENCY-005 — Validates currency governance layer:

1. is_supported_currency() helper
2. EUR added to SUPPORTED_CURRENCIES
3. GET /system/currencies endpoint
4. Base currency lock guard (reject change after financial records exist)
5. Admin currency audit API — clean state and detected issues
"""

import pytest
from fastapi.testclient import TestClient

from app.core.constants.currency import (
    CURRENCY_EUR,
    DEFAULT_CURRENCY,
    SUPPORTED_CURRENCIES,
    is_supported_currency,
)


# ---------------------------------------------------------------------------
# A. Currency constants — EUR and helper
# ---------------------------------------------------------------------------


class TestCurrencyConstants:
    def test_eur_in_supported_currencies(self):
        """EUR must be included in SUPPORTED_CURRENCIES."""
        assert "EUR" in SUPPORTED_CURRENCIES

    def test_currency_eur_constant_value(self):
        """CURRENCY_EUR must equal 'EUR'."""
        assert CURRENCY_EUR == "EUR"

    def test_is_supported_currency_valid_codes(self):
        """is_supported_currency returns True for all supported codes."""
        for code in SUPPORTED_CURRENCIES:
            assert is_supported_currency(code), f"Expected {code!r} to be supported"

    def test_is_supported_currency_invalid_codes(self):
        """is_supported_currency returns False for unsupported codes."""
        assert not is_supported_currency("GBP")
        assert not is_supported_currency("CHF")
        assert not is_supported_currency("")
        assert not is_supported_currency("aed")  # case-sensitive

    def test_is_supported_currency_returns_bool(self):
        assert isinstance(is_supported_currency("AED"), bool)
        assert isinstance(is_supported_currency("XYZ"), bool)


# ---------------------------------------------------------------------------
# B. GET /system/currencies endpoint
# ---------------------------------------------------------------------------


class TestSystemCurrenciesEndpoint:
    def test_returns_200(self, client: TestClient):
        response = client.get("/api/v1/system/currencies")
        assert response.status_code == 200

    def test_default_currency_is_aed(self, client: TestClient):
        data = client.get("/api/v1/system/currencies").json()
        assert data["default_currency"] == DEFAULT_CURRENCY

    def test_supported_currencies_includes_all_codes(self, client: TestClient):
        data = client.get("/api/v1/system/currencies").json()
        assert "supported_currencies" in data
        returned = data["supported_currencies"]
        for code in ["AED", "JOD", "USD", "EUR"]:
            assert code in returned, f"Expected {code!r} in supported_currencies"

    def test_supported_currencies_matches_backend_constant(self, client: TestClient):
        data = client.get("/api/v1/system/currencies").json()
        assert sorted(data["supported_currencies"]) == sorted(SUPPORTED_CURRENCIES)

    def test_response_has_required_keys(self, client: TestClient):
        data = client.get("/api/v1/system/currencies").json()
        assert "default_currency" in data
        assert "supported_currencies" in data

    def test_requires_authentication(self, unauth_client: TestClient):
        response = unauth_client.get("/api/v1/system/currencies")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# C. Base currency lock guard
# ---------------------------------------------------------------------------


class TestBaseCurrencyLockGuard:
    """PATCH /projects/{id} must reject base_currency changes once financial
    records exist for the project."""

    def _create_project(self, client: TestClient, code: str, base_currency: str = "AED") -> str:
        resp = client.post(
            "/api/v1/projects",
            json={"name": f"Project {code}", "code": code, "base_currency": base_currency},
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    def test_can_change_currency_without_financial_records(self, client: TestClient):
        """PATCH base_currency must succeed when no financial records exist."""
        project_id = self._create_project(client, "LOCK-001")
        resp = client.patch(
            f"/api/v1/projects/{project_id}",
            json={"base_currency": "USD"},
        )
        assert resp.status_code == 200
        assert resp.json()["base_currency"] == "USD"

    def test_can_change_currency_to_same_value(self, client: TestClient, db_session):
        """PATCH base_currency to the same value must always succeed (no-op)."""
        project_id = self._create_project(client, "LOCK-SAME")
        # Add a scenario to trigger the lock
        from app.modules.scenario.models import Scenario

        scenario = Scenario(
            project_id=project_id,
            name="Test Scenario",
            is_active=True,
            status="draft",
        )
        db_session.add(scenario)
        db_session.commit()

        # Patching to the same currency should succeed
        resp = client.patch(
            f"/api/v1/projects/{project_id}",
            json={"base_currency": "AED"},  # same as default
        )
        assert resp.status_code == 200

    def test_lock_triggered_by_scenario(self, client: TestClient, db_session):
        """PATCH base_currency must be rejected when a scenario exists."""
        from app.modules.scenario.models import Scenario

        project_id = self._create_project(client, "LOCK-002")
        scenario = Scenario(
            project_id=project_id,
            name="Blocking Scenario",
            is_active=True,
            status="draft",
        )
        db_session.add(scenario)
        db_session.commit()

        resp = client.patch(
            f"/api/v1/projects/{project_id}",
            json={"base_currency": "USD"},
        )
        assert resp.status_code == 400

    def test_lock_triggered_by_feasibility_run(self, client: TestClient, db_session):
        """PATCH base_currency must be rejected when a feasibility run exists."""
        from app.modules.feasibility.models import FeasibilityRun

        project_id = self._create_project(client, "LOCK-003")
        run = FeasibilityRun(
            project_id=project_id,
            scenario_name="Test Run",
        )
        db_session.add(run)
        db_session.commit()

        resp = client.patch(
            f"/api/v1/projects/{project_id}",
            json={"base_currency": "JOD"},
        )
        assert resp.status_code == 400

    def test_lock_triggered_by_construction_cost_record(self, client: TestClient, db_session):
        """PATCH base_currency must be rejected when a construction cost record exists."""
        from app.modules.construction_costs.models import ConstructionCostRecord

        project_id = self._create_project(client, "LOCK-004")
        record = ConstructionCostRecord(
            project_id=project_id,
            title="Test Cost",
            amount=100000.0,
            currency="AED",
        )
        db_session.add(record)
        db_session.commit()

        resp = client.patch(
            f"/api/v1/projects/{project_id}",
            json={"base_currency": "USD"},
        )
        assert resp.status_code == 400

    def test_non_currency_patch_unaffected(self, client: TestClient, db_session):
        """PATCH of non-currency fields must succeed even with financial records."""
        from app.modules.scenario.models import Scenario

        project_id = self._create_project(client, "LOCK-005")
        scenario = Scenario(
            project_id=project_id,
            name="Blocking Scenario 2",
            is_active=True,
            status="draft",
        )
        db_session.add(scenario)
        db_session.commit()

        resp = client.patch(
            f"/api/v1/projects/{project_id}",
            json={"description": "Updated description"},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# D. Admin currency audit endpoint
# ---------------------------------------------------------------------------


class TestAdminCurrencyAuditEndpoint:
    def test_returns_200(self, client: TestClient):
        response = client.get("/api/v1/admin/currency-audit")
        assert response.status_code == 200

    def test_clean_state_has_no_issues(self, client: TestClient):
        """With no data, audit must return zero issues."""
        data = client.get("/api/v1/admin/currency-audit").json()
        assert data["total_issues"] == 0
        assert data["issues"] == []
        assert data["counts_by_type"] == {}

    def test_response_has_required_keys(self, client: TestClient):
        data = client.get("/api/v1/admin/currency-audit").json()
        assert "total_issues" in data
        assert "counts_by_type" in data
        assert "issues" in data

    def test_requires_authentication(self, unauth_client: TestClient):
        response = unauth_client.get("/api/v1/admin/currency-audit")
        assert response.status_code == 401

    def test_detects_mismatch(self, client: TestClient, db_session):
        """Audit must detect a construction cost record with mismatched currency."""
        from app.modules.construction_costs.models import ConstructionCostRecord
        from app.modules.projects.models import Project

        project = Project(name="Audit Project", code="AUDIT-001", base_currency="AED")
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)

        # Add a construction cost record with a different currency
        record = ConstructionCostRecord(
            project_id=project.id,
            title="Mismatch Record",
            amount=50000.0,
            currency="USD",  # differs from project.base_currency = "AED"
        )
        db_session.add(record)
        db_session.commit()

        data = client.get("/api/v1/admin/currency-audit").json()
        assert data["total_issues"] >= 1
        types = [i["type"] for i in data["issues"]]
        assert "mismatch" in types

    def test_detects_suspicious_default(self, client: TestClient, db_session):
        """Audit must detect suspicious default when project uses non-default currency."""
        from app.modules.construction_costs.models import ConstructionCostRecord
        from app.modules.projects.models import Project

        project = Project(name="JOD Project", code="AUDIT-002", base_currency="JOD")
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)

        # Record carries DEFAULT_CURRENCY ("AED") but project.base_currency is "JOD"
        record = ConstructionCostRecord(
            project_id=project.id,
            title="Suspicious Record",
            amount=25000.0,
            currency="AED",  # platform default but project expects JOD
        )
        db_session.add(record)
        db_session.commit()

        data = client.get("/api/v1/admin/currency-audit").json()
        assert data["total_issues"] >= 1
        types = [i["type"] for i in data["issues"]]
        assert "suspicious_default" in types

    def test_issue_shape(self, client: TestClient, db_session):
        """Each issue dict must have the expected fields."""
        from app.modules.construction_costs.models import ConstructionCostRecord
        from app.modules.projects.models import Project

        project = Project(name="Shape Project", code="AUDIT-003", base_currency="AED")
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)

        record = ConstructionCostRecord(
            project_id=project.id,
            title="Shape Test",
            amount=10000.0,
            currency="EUR",
        )
        db_session.add(record)
        db_session.commit()

        data = client.get("/api/v1/admin/currency-audit").json()
        assert data["total_issues"] >= 1
        issue = data["issues"][0]
        for field in ("type", "project_id", "project_currency", "record_type", "record_id", "currency"):
            assert field in issue, f"Expected field {field!r} in issue"

    def test_no_issues_for_matching_currency(self, client: TestClient, db_session):
        """Audit must NOT flag records whose currency matches project.base_currency."""
        from app.modules.construction_costs.models import ConstructionCostRecord
        from app.modules.projects.models import Project

        project = Project(name="Clean Project", code="AUDIT-004", base_currency="AED")
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)

        record = ConstructionCostRecord(
            project_id=project.id,
            title="Clean Record",
            amount=10000.0,
            currency="AED",  # matches project.base_currency
        )
        db_session.add(record)
        db_session.commit()

        data = client.get("/api/v1/admin/currency-audit").json()
        assert data["total_issues"] == 0


# ---------------------------------------------------------------------------
# E. scan_currency_integrity unit test
# ---------------------------------------------------------------------------


class TestScanCurrencyIntegrityUnit:
    def test_returns_list(self, db_session):
        """scan_currency_integrity must return a list (empty when no data)."""
        from app.modules.admin.currency_audit_service import scan_currency_integrity

        result = scan_currency_integrity(db_session)
        assert isinstance(result, list)
        assert result == []

    def test_mismatch_detection_unit(self, db_session):
        """Unit test: scan detects mismatch directly without going through HTTP."""
        from app.modules.admin.currency_audit_service import scan_currency_integrity
        from app.modules.construction_costs.models import ConstructionCostRecord
        from app.modules.projects.models import Project

        project = Project(name="Unit Test Project", code="UNIT-001", base_currency="AED")
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)

        record = ConstructionCostRecord(
            project_id=project.id,
            title="Unit Mismatch",
            amount=5000.0,
            currency="JOD",
        )
        db_session.add(record)
        db_session.commit()

        issues = scan_currency_integrity(db_session)
        assert len(issues) == 1
        assert issues[0]["type"] == "mismatch"
        assert issues[0]["project_id"] == project.id
        assert issues[0]["currency"] == "JOD"
        assert issues[0]["project_currency"] == "AED"
        assert issues[0]["record_type"] == "construction_cost_record"
