"""
tests.core.test_currency_enforcement

PR-CURRENCY-003 — Validates runtime currency enforcement introduced by this PR:

1. Calculation engine contracts carry explicit currency context
2. Feasibility engine accepts and propagates currency
3. Financial scenario engine accepts and propagates currency
4. Release simulation response includes currency
5. Finance summary response includes project base_currency
6. Sales service installment generation uses contract currency
7. Receivable generation rejects mismatched installment currencies
8. Portfolio schemas no longer hardcode AED in field descriptions
"""

import pytest
from fastapi.testclient import TestClient

from app.core.constants.currency import DEFAULT_CURRENCY, CURRENCY_JOD, CURRENCY_USD


# ---------------------------------------------------------------------------
# A. Calculation engine contract currency propagation
# ---------------------------------------------------------------------------


class TestCalculationContractCurrency:
    """Calculation engine input/output dataclasses carry currency."""

    def test_pricing_inputs_has_currency_field(self):
        from app.core.calculation_engine.types import PricingInputs

        inp = PricingInputs(
            internal_area_sqm=100.0,
            base_price_per_sqm=1000.0,
            currency=CURRENCY_JOD,
        )
        assert inp.currency == CURRENCY_JOD

    def test_pricing_inputs_defaults_to_platform_default(self):
        from app.core.calculation_engine.types import PricingInputs

        inp = PricingInputs(internal_area_sqm=100.0, base_price_per_sqm=1000.0)
        assert inp.currency == DEFAULT_CURRENCY

    def test_pricing_outputs_propagates_currency(self):
        from app.core.calculation_engine.pricing import run_unit_pricing
        from app.core.calculation_engine.types import PricingInputs

        inputs = PricingInputs(
            internal_area_sqm=80.0,
            base_price_per_sqm=500.0,
            currency=CURRENCY_USD,
        )
        outputs = run_unit_pricing(inputs)
        assert outputs.currency == CURRENCY_USD

    def test_return_inputs_has_currency_field(self):
        from app.core.calculation_engine.types import ReturnInputs

        inp = ReturnInputs(
            gdv=10_000_000.0,
            total_cost=7_000_000.0,
            equity_invested=2_000_000.0,
            sellable_area_sqm=5_000.0,
            avg_sale_price_per_sqm=2_000.0,
            development_period_months=24,
            currency=CURRENCY_JOD,
        )
        assert inp.currency == CURRENCY_JOD

    def test_return_outputs_propagates_currency(self):
        from app.core.calculation_engine.returns import run_return_calculations
        from app.core.calculation_engine.types import ReturnInputs

        inputs = ReturnInputs(
            gdv=10_000_000.0,
            total_cost=7_000_000.0,
            equity_invested=2_000_000.0,
            sellable_area_sqm=5_000.0,
            avg_sale_price_per_sqm=2_000.0,
            development_period_months=24,
            currency=CURRENCY_JOD,
        )
        outputs = run_return_calculations(inputs)
        assert outputs.currency == CURRENCY_JOD

    def test_cashflow_inputs_has_currency_field(self):
        from app.core.calculation_engine.types import CashflowInputs

        inp = CashflowInputs(
            monthly_inflows=[100.0, 200.0],
            monthly_outflows=[50.0, 60.0],
            currency=CURRENCY_USD,
        )
        assert inp.currency == CURRENCY_USD

    def test_cashflow_outputs_propagates_currency(self):
        from app.core.calculation_engine.cashflow import run_cashflow_analysis
        from app.core.calculation_engine.types import CashflowInputs

        inputs = CashflowInputs(
            monthly_inflows=[100.0, 200.0],
            monthly_outflows=[50.0, 60.0],
            currency=CURRENCY_USD,
        )
        outputs = run_cashflow_analysis(inputs)
        assert outputs.currency == CURRENCY_USD

    def test_land_inputs_has_currency_field(self):
        from app.core.calculation_engine.types import LandInputs

        inp = LandInputs(
            land_area_sqm=10_000.0,
            acquisition_price=5_000_000.0,
            buildable_area_sqm=8_000.0,
            sellable_area_sqm=6_000.0,
            gdv=12_000_000.0,
            total_development_cost=6_000_000.0,
            developer_margin_target=0.20,
            currency=CURRENCY_JOD,
        )
        assert inp.currency == CURRENCY_JOD

    def test_land_outputs_propagates_currency(self):
        from app.core.calculation_engine.land import run_land_calculations
        from app.core.calculation_engine.types import LandInputs

        inputs = LandInputs(
            land_area_sqm=10_000.0,
            acquisition_price=5_000_000.0,
            buildable_area_sqm=8_000.0,
            sellable_area_sqm=6_000.0,
            gdv=12_000_000.0,
            total_development_cost=6_000_000.0,
            developer_margin_target=0.20,
            currency=CURRENCY_JOD,
        )
        outputs = run_land_calculations(inputs)
        assert outputs.currency == CURRENCY_JOD


# ---------------------------------------------------------------------------
# B. Feasibility engine contract currency propagation
# ---------------------------------------------------------------------------


class TestFeasibilityEngineCurrency:
    """FeasibilityInputs and FeasibilityOutputs carry explicit currency."""

    def test_feasibility_inputs_default_currency(self):
        from app.modules.feasibility.engines.feasibility_engine import FeasibilityInputs

        inp = FeasibilityInputs(
            sellable_area_sqm=5_000.0,
            avg_sale_price_per_sqm=1_500.0,
            construction_cost_per_sqm=600.0,
            soft_cost_ratio=0.05,
            finance_cost_ratio=0.03,
            sales_cost_ratio=0.02,
            development_period_months=24,
        )
        assert inp.currency == DEFAULT_CURRENCY

    def test_feasibility_inputs_explicit_currency(self):
        from app.modules.feasibility.engines.feasibility_engine import FeasibilityInputs

        inp = FeasibilityInputs(
            sellable_area_sqm=5_000.0,
            avg_sale_price_per_sqm=1_500.0,
            construction_cost_per_sqm=600.0,
            soft_cost_ratio=0.05,
            finance_cost_ratio=0.03,
            sales_cost_ratio=0.02,
            development_period_months=24,
            currency=CURRENCY_USD,
        )
        assert inp.currency == CURRENCY_USD

    def test_feasibility_outputs_propagates_currency(self):
        from app.modules.feasibility.engines.feasibility_engine import (
            FeasibilityInputs,
            run_feasibility,
        )

        inp = FeasibilityInputs(
            sellable_area_sqm=5_000.0,
            avg_sale_price_per_sqm=1_500.0,
            construction_cost_per_sqm=600.0,
            soft_cost_ratio=0.05,
            finance_cost_ratio=0.03,
            sales_cost_ratio=0.02,
            development_period_months=24,
            currency=CURRENCY_JOD,
        )
        outputs = run_feasibility(inp)
        assert outputs.currency == CURRENCY_JOD

    def test_feasibility_outputs_unchanged_numeric_results(self):
        """Numeric results must not change when currency field is added."""
        from app.modules.feasibility.engines.feasibility_engine import (
            FeasibilityInputs,
            run_feasibility,
        )

        inp = FeasibilityInputs(
            sellable_area_sqm=5_000.0,
            avg_sale_price_per_sqm=1_500.0,
            construction_cost_per_sqm=600.0,
            soft_cost_ratio=0.05,
            finance_cost_ratio=0.03,
            sales_cost_ratio=0.02,
            development_period_months=24,
        )
        outputs = run_feasibility(inp)
        assert outputs.gdv == pytest.approx(7_500_000.0)
        assert outputs.construction_cost == pytest.approx(3_000_000.0)


# ---------------------------------------------------------------------------
# C. Financial scenario engine currency propagation
# ---------------------------------------------------------------------------


class TestFinancialScenarioEngineCurrency:
    """FinancialScenarioAssumptions and FinancialScenarioRunResult carry currency."""

    def _base_assumptions(self, **kwargs):
        from app.modules.scenario.financial_scenario_engine import FinancialScenarioAssumptions

        defaults = dict(
            gdv=10_000_000.0,
            total_cost=7_000_000.0,
            equity_invested=2_450_000.0,
            sellable_area_sqm=5_000.0,
            avg_sale_price_per_sqm=2_000.0,
            development_period_months=24,
        )
        defaults.update(kwargs)
        return FinancialScenarioAssumptions(**defaults)

    def test_assumptions_default_currency(self):
        a = self._base_assumptions()
        assert a.currency == DEFAULT_CURRENCY

    def test_assumptions_explicit_currency(self):
        a = self._base_assumptions(currency=CURRENCY_JOD)
        assert a.currency == CURRENCY_JOD

    def test_result_propagates_currency(self):
        from app.modules.scenario.financial_scenario_engine import (
            ScenarioOverrides,
            run_financial_scenario,
        )

        assumptions = self._base_assumptions(currency=CURRENCY_USD)
        result = run_financial_scenario(assumptions, ScenarioOverrides(values={}))
        assert result.currency == CURRENCY_USD

    def test_result_default_currency_when_not_specified(self):
        from app.modules.scenario.financial_scenario_engine import (
            ScenarioOverrides,
            run_financial_scenario,
        )

        assumptions = self._base_assumptions()
        result = run_financial_scenario(assumptions, ScenarioOverrides(values={}))
        assert result.currency == DEFAULT_CURRENCY

    def test_numeric_results_unchanged_by_currency_field(self):
        """Adding currency must not alter any numeric calculation outputs."""
        from app.modules.scenario.financial_scenario_engine import (
            ScenarioOverrides,
            run_financial_scenario,
        )

        base = self._base_assumptions(gdv=10_000_000.0, total_cost=7_000_000.0)
        result = run_financial_scenario(base, ScenarioOverrides(values={}))
        assert abs(result.returns.gross_profit - 3_000_000.0) < 1.0


# ---------------------------------------------------------------------------
# D. Release simulation response includes currency
# ---------------------------------------------------------------------------


class TestReleaseSimulationCurrency:
    def test_simulate_strategy_response_includes_currency(self, client: TestClient):
        """POST /projects/{id}/simulate-strategy must return currency in response."""
        project = client.post(
            "/api/v1/projects",
            json={"name": "Sim Project", "code": "SIM-001", "base_currency": "JOD"},
        ).json()
        project_id = project["id"]

        response = client.post(
            f"/api/v1/projects/{project_id}/simulate-strategy",
            json={"scenario": {"price_adjustment_pct": 0.0}},
        )
        assert response.status_code == 200
        data = response.json()
        assert "currency" in data
        assert isinstance(data["currency"], str)
        assert len(data["currency"]) == 3

    def test_simulate_strategy_result_includes_currency(self, client: TestClient):
        """Each SimulationResult in the response must include currency."""
        project = client.post(
            "/api/v1/projects",
            json={"name": "Sim2 Project", "code": "SIM-002"},
        ).json()
        project_id = project["id"]

        response = client.post(
            f"/api/v1/projects/{project_id}/simulate-strategy",
            json={"scenario": {"price_adjustment_pct": 5.0, "release_strategy": "hold"}},
        )
        assert response.status_code == 200
        result = response.json()["result"]
        assert "currency" in result

    def test_simulate_strategies_response_includes_currency(self, client: TestClient):
        """POST /projects/{id}/simulate-strategies must return currency in response."""
        project = client.post(
            "/api/v1/projects",
            json={"name": "MultiSim Project", "code": "SIM-003"},
        ).json()
        project_id = project["id"]

        response = client.post(
            f"/api/v1/projects/{project_id}/simulate-strategies",
            json={
                "scenarios": [
                    {"price_adjustment_pct": 0.0, "release_strategy": "maintain"},
                    {"price_adjustment_pct": 5.0, "release_strategy": "hold"},
                ]
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "currency" in data
        for r in data["results"]:
            assert "currency" in r


# ---------------------------------------------------------------------------
# E. Finance summary response includes project base_currency
# ---------------------------------------------------------------------------


class TestFinanceSummaryCurrency:
    def test_project_finance_summary_includes_currency(self, client: TestClient):
        """GET /finance/projects/{id}/summary must include currency in response."""
        project = client.post(
            "/api/v1/projects",
            json={"name": "Finance Proj", "code": "FIN-001", "base_currency": "USD"},
        ).json()
        project_id = project["id"]

        response = client.get(f"/api/v1/finance/projects/{project_id}/summary")
        assert response.status_code == 200
        data = response.json()
        assert "currency" in data
        assert data["currency"] == "USD"

    def test_project_finance_summary_currency_defaults_to_base_currency(self, client: TestClient):
        """Finance summary currency must match the project's base_currency."""
        project = client.post(
            "/api/v1/projects",
            json={"name": "Finance AED", "code": "FIN-002"},
        ).json()
        project_id = project["id"]

        response = client.get(f"/api/v1/finance/projects/{project_id}/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["currency"] == DEFAULT_CURRENCY


# ---------------------------------------------------------------------------
# F. Sales service: installment currency inherits from contract
# ---------------------------------------------------------------------------


class TestSalesInstallmentCurrencyInheritance:
    """_build_installment_items must use contract currency, not hardcoded 'AED'."""

    def test_installment_currency_matches_contract_currency(self):
        """When contract has currency='JOD', generated installments must be 'JOD'."""
        import datetime
        from unittest.mock import MagicMock

        from app.modules.sales.service import _build_installment_items

        mock_contract = MagicMock()
        mock_contract.id = "contract-test-123"
        mock_contract.contract_price = 500_000.0
        mock_contract.contract_date = datetime.date.today()
        mock_contract.currency = CURRENCY_JOD

        items = _build_installment_items(mock_contract)
        assert len(items) > 0
        for item in items:
            assert item.currency == CURRENCY_JOD, (
                f"Expected installment currency={CURRENCY_JOD!r}, got {item.currency!r}"
            )

    def test_installment_currency_defaults_to_platform_default_when_no_contract_currency(self):
        """When contract has no currency attribute, installments use DEFAULT_CURRENCY."""
        import datetime
        from unittest.mock import MagicMock

        from app.modules.sales.service import _build_installment_items

        mock_contract = MagicMock(spec=[])
        mock_contract.id = "contract-test-456"
        mock_contract.contract_price = 200_000.0
        mock_contract.contract_date = datetime.date.today()

        items = _build_installment_items(mock_contract)
        assert len(items) > 0
        for item in items:
            assert item.currency == DEFAULT_CURRENCY


# ---------------------------------------------------------------------------
# G. Receivable generation: currency mismatch is rejected
# ---------------------------------------------------------------------------


class TestReceivableCurrencyEnforcement:
    """generate_for_contract must reject mismatched installment currencies."""

    def test_receivables_service_rejects_mismatched_currency(self, db_session):
        """ReceivableService.generate_for_contract raises 422 when installment
        currency differs from contract currency."""
        import datetime
        from fastapi import HTTPException
        from unittest.mock import MagicMock, patch

        from app.modules.receivables.service import ReceivableService

        contract_currency = CURRENCY_JOD
        installment_currency = CURRENCY_USD  # intentionally different

        mock_contract = MagicMock()
        mock_contract.id = "ctr-mismatch"
        mock_contract.currency = contract_currency

        mock_installment = MagicMock()
        mock_installment.installment_number = 1
        mock_installment.currency = installment_currency
        mock_installment.due_amount = 50_000.0
        mock_installment.due_date = datetime.date.today()
        mock_installment.template_id = None

        service = ReceivableService(db_session)
        with patch.object(service, "_require_contract", return_value=mock_contract):
            with patch.object(db_session, "query") as mock_query:
                mock_query.return_value.filter.return_value.order_by.return_value.all.return_value = (
                    [mock_installment]
                )
                with pytest.raises(HTTPException) as exc_info:
                    service.generate_for_contract("ctr-mismatch")
        assert exc_info.value.status_code == 422
        assert "currency mismatch" in exc_info.value.detail.lower()

    def test_receivables_service_proceeds_same_currency(self, db_session):
        """ReceivableService.generate_for_contract does not raise currency error when currencies match."""
        import datetime
        from fastapi import HTTPException
        from unittest.mock import MagicMock, patch

        from app.modules.receivables.service import ReceivableService

        shared_currency = CURRENCY_JOD

        mock_contract = MagicMock()
        mock_contract.id = "ctr-match"
        mock_contract.currency = shared_currency

        mock_installment = MagicMock()
        mock_installment.installment_number = 1
        mock_installment.currency = shared_currency
        mock_installment.due_amount = 50_000.0
        mock_installment.due_date = datetime.date.today()
        mock_installment.template_id = None
        mock_installment.id = "inst-001"

        service = ReceivableService(db_session)
        with patch.object(service, "_require_contract", return_value=mock_contract):
            with patch.object(db_session, "query") as mock_query:
                mock_query.return_value.filter.return_value.order_by.return_value.all.return_value = (
                    [mock_installment]
                )
                mock_query.return_value.filter.return_value.all.return_value = []
                try:
                    service.generate_for_contract("ctr-match")
                except HTTPException as exc:
                    assert "currency mismatch" not in exc.detail.lower(), (
                        f"Unexpected currency mismatch error: {exc.detail}"
                    )


# ---------------------------------------------------------------------------
# H. Feasibility run API: currency flows through convenience endpoint
# ---------------------------------------------------------------------------


class TestFeasibilityRunCurrencyFlow:
    def test_feasibility_run_request_accepts_currency(self, client: TestClient):
        """POST /feasibility/run with currency must persist that currency on result."""
        response = client.post(
            "/api/v1/feasibility/run",
            json={
                "scenario_name": "Currency Flow Test",
                "sellable_area_sqm": 5000.0,
                "avg_sale_price_per_sqm": 1500.0,
                "construction_cost_per_sqm": 600.0,
                "soft_cost_ratio": 0.05,
                "finance_cost_ratio": 0.03,
                "sales_cost_ratio": 0.02,
                "development_period_months": 24,
                "currency": "JOD",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "currency" in data
        assert data["currency"] == "JOD"

    def test_feasibility_run_request_defaults_currency(self, client: TestClient):
        """POST /feasibility/run without currency must default to DEFAULT_CURRENCY."""
        response = client.post(
            "/api/v1/feasibility/run",
            json={
                "scenario_name": "Default Currency Test",
                "sellable_area_sqm": 5000.0,
                "avg_sale_price_per_sqm": 1500.0,
                "construction_cost_per_sqm": 600.0,
                "soft_cost_ratio": 0.05,
                "finance_cost_ratio": 0.03,
                "sales_cost_ratio": 0.02,
                "development_period_months": 24,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "currency" in data
        assert data["currency"] == DEFAULT_CURRENCY


# ---------------------------------------------------------------------------
# I. Scenario financial run: currency flows through API
# ---------------------------------------------------------------------------


class TestScenarioFinancialRunCurrency:
    def test_financial_scenario_run_persists_currency(self, client: TestClient):
        """POST /scenarios/{id}/financial-runs with currency must persist it."""
        scenario = client.post(
            "/api/v1/scenarios",
            json={"name": "Currency Scenario"},
        ).json()
        scenario_id = scenario["id"]

        response = client.post(
            f"/api/v1/scenarios/{scenario_id}/financial-runs",
            json={
                "assumptions": {
                    "gdv": 10_000_000.0,
                    "total_cost": 7_000_000.0,
                    "equity_invested": 2_000_000.0,
                    "sellable_area_sqm": 5_000.0,
                    "avg_sale_price_per_sqm": 2_000.0,
                    "development_period_months": 24,
                    "currency": "USD",
                }
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "currency" in data
        assert data["currency"] == "USD"

    def test_financial_scenario_run_defaults_currency(self, client: TestClient):
        """POST /scenarios/{id}/financial-runs without currency defaults to platform default."""
        scenario = client.post(
            "/api/v1/scenarios",
            json={"name": "Default Currency Scenario"},
        ).json()
        scenario_id = scenario["id"]

        response = client.post(
            f"/api/v1/scenarios/{scenario_id}/financial-runs",
            json={
                "assumptions": {
                    "gdv": 10_000_000.0,
                    "total_cost": 7_000_000.0,
                    "equity_invested": 2_000_000.0,
                    "sellable_area_sqm": 5_000.0,
                    "avg_sale_price_per_sqm": 2_000.0,
                    "development_period_months": 24,
                }
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "currency" in data
        assert data["currency"] == DEFAULT_CURRENCY
