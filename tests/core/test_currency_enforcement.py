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


# ---------------------------------------------------------------------------
# J. PR-CURRENCY-008 — final leak closure
# ---------------------------------------------------------------------------


class TestPricingServiceNoCurrencyLiteral:
    """Pricing service and repository must use DEFAULT_CURRENCY constant, not inline literals."""

    def test_pricing_repository_record_change_default_uses_constant(self):
        """PricingHistoryRepository.record_change must default currency to DEFAULT_CURRENCY."""
        import inspect

        from app.modules.pricing.repository import PricingHistoryRepository

        sig = inspect.signature(PricingHistoryRepository.record_change)
        currency_param = sig.parameters.get("currency")
        assert currency_param is not None
        assert currency_param.default == DEFAULT_CURRENCY, (
            f"Expected DEFAULT_CURRENCY ({DEFAULT_CURRENCY!r}), "
            f"got {currency_param.default!r} — do not use inline ISO literals"
        )

    def test_portfolio_service_cost_variance_uses_constant(self, db_session):
        """Portfolio service must fall back to DEFAULT_CURRENCY when project currency
        is absent from the currency map — not to a raw 'AED' literal."""
        from unittest.mock import MagicMock, patch

        from app.modules.portfolio.service import PortfolioService

        service = PortfolioService(db_session)

        pid = "proj-fallback-test"
        mock_project = MagicMock()
        mock_project.id = pid
        mock_project.name = "Test Project"

        with (
            patch.object(service.repo, "list_projects", return_value=[]),
            patch.object(service.repo, "list_projects_with_active_comparison_sets",
                         return_value=[mock_project]),
            patch.object(service.repo, "get_variance_totals_by_project",
                         return_value={pid: (__import__("decimal").Decimal("1000000"),
                                             __import__("decimal").Decimal("900000"),
                                             __import__("decimal").Decimal("-100000"))}),
            patch.object(service.repo, "get_active_set_count_by_project",
                         return_value={pid: 1}),
            patch.object(service.repo, "get_latest_comparison_stage_by_project",
                         return_value={pid: "tender"}),
            # Deliberately exclude pid from the currency map to trigger the fallback
            patch.object(service.repo, "get_currency_by_project_comparison_sets",
                         return_value={}),
            patch.object(service.repo, "get_portfolio_variance_totals_grouped",
                         return_value={}),
        ):
            result = service.get_cost_variance()

            assert len(result.projects) == 1
            card = result.projects[0]
            assert card.currency == DEFAULT_CURRENCY, (
                f"Expected DEFAULT_CURRENCY ({DEFAULT_CURRENCY!r}), got {card.currency!r}"
            )


class TestCommissionPayoutCurrencyPropagation:
    """CommissionPayout and payout lines must inherit contract currency."""

    def test_commission_payout_inherits_contract_currency(self, client: TestClient):
        """Calculating a payout for a JOD-denominated contract must produce a
        JOD-denominated payout record with JOD-denominated payout lines."""
        # Build hierarchy
        proj_resp = client.post(
            "/api/v1/projects",
            json={"name": "Comm Currency Project", "code": "CCP-008", "base_currency": "JOD"},
        )
        assert proj_resp.status_code == 201, proj_resp.text
        project_id = proj_resp.json()["id"]

        phase_resp = client.post(
            "/api/v1/phases",
            json={"project_id": project_id, "name": "Phase 1", "sequence": 1},
        )
        assert phase_resp.status_code == 201
        phase_id = phase_resp.json()["id"]

        bldg_resp = client.post(
            f"/api/v1/phases/{phase_id}/buildings",
            json={"name": "Block A", "code": "BLK-CCP008"},
        )
        assert bldg_resp.status_code == 201
        building_id = bldg_resp.json()["id"]

        floor_resp = client.post(
            f"/api/v1/buildings/{building_id}/floors",
            json={"name": "Floor 1", "code": "FL-01", "sequence_number": 1},
        )
        assert floor_resp.status_code == 201
        floor_id = floor_resp.json()["id"]

        unit_resp = client.post(
            "/api/v1/units",
            json={
                "floor_id": floor_id,
                "unit_number": "201",
                "unit_type": "studio",
                "internal_area": 90.0,
            },
        )
        assert unit_resp.status_code == 201
        unit_id = unit_resp.json()["id"]

        buyer_resp = client.post(
            "/api/v1/sales/buyers",
            json={"full_name": "JOD Buyer", "email": "jod.buyer@test.com", "phone": "+9621111111"},
        )
        assert buyer_resp.status_code == 201
        buyer_id = buyer_resp.json()["id"]

        # Create JOD-denominated contract
        contract_resp = client.post(
            "/api/v1/sales/contracts",
            json={
                "unit_id": unit_id,
                "buyer_id": buyer_id,
                "contract_number": "CCP-JOD-001",
                "contract_date": "2026-01-01",
                "contract_price": 200_000.0,
                "currency": "JOD",
            },
        )
        assert contract_resp.status_code == 201, contract_resp.text
        contract_id = contract_resp.json()["id"]

        # Create commission plan and slab
        plan_resp = client.post(
            "/api/v1/commission/plans",
            json={
                "project_id": project_id,
                "name": "JOD Plan",
                "pool_percentage": 5.0,
                "calculation_mode": "marginal",
            },
        )
        assert plan_resp.status_code == 201, plan_resp.text
        plan_id = plan_resp.json()["id"]

        slab_resp = client.post(
            f"/api/v1/commission/plans/{plan_id}/slabs",
            json={
                "range_from": 0,
                "range_to": None,
                "sequence": 1,
                "sales_rep_pct": 60.0,
                "team_lead_pct": 20.0,
                "manager_pct": 10.0,
                "broker_pct": 5.0,
                "platform_pct": 5.0,
            },
        )
        assert slab_resp.status_code == 201, slab_resp.text

        # Calculate payout
        payout_resp = client.post(
            "/api/v1/commission/payouts/calculate",
            json={
                "sale_contract_id": contract_id,
                "commission_plan_id": plan_id,
            },
        )
        assert payout_resp.status_code == 201, payout_resp.text
        payout_data = payout_resp.json()

        assert payout_data["currency"] == "JOD", (
            f"Payout must inherit contract currency 'JOD', got {payout_data['currency']!r}"
        )
        lines = payout_data.get("lines", [])
        assert len(lines) > 0, "Expected at least one payout line"
        for line in lines:
            assert line["currency"] == "JOD", (
                f"Payout line must inherit contract currency 'JOD', got {line['currency']!r}"
            )


class TestPaymentPlanResponseCurrency:
    """PaymentPlanResponse and PaymentScheduleListResponse must include denomination."""

    def test_payment_plan_response_has_currency_field(self):
        """PaymentPlanResponse schema must declare a currency field."""
        from app.modules.payment_plans.schemas import PaymentPlanResponse

        fields = PaymentPlanResponse.model_fields
        assert "currency" in fields, (
            "PaymentPlanResponse must include a 'currency' field for denomination safety"
        )

    def test_payment_schedule_list_response_has_currency_field(self):
        """PaymentScheduleListResponse schema must declare a currency field."""
        from app.modules.payment_plans.schemas import PaymentScheduleListResponse

        fields = PaymentScheduleListResponse.model_fields
        assert "currency" in fields, (
            "PaymentScheduleListResponse must include a 'currency' field for denomination safety"
        )

    def test_payment_plan_response_currency_defaults_to_platform_default(self):
        """PaymentPlanResponse.currency must default to DEFAULT_CURRENCY."""
        from datetime import datetime, timezone

        from app.modules.payment_plans.schemas import PaymentPlanResponse

        response = PaymentPlanResponse(
            id="plan-001",
            contract_id="ctr-001",
            plan_name="Test Plan",
            plan_type="standard_installments",
            installments=[],
            total_installments=0,
            total_due=0.0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        assert response.currency == DEFAULT_CURRENCY

    def test_payment_plan_api_response_includes_currency(self, client: TestClient):
        """POST /payment-plans/contracts/{id}/plan must return currency in response."""
        # Build a minimal hierarchy
        proj_resp = client.post(
            "/api/v1/projects",
            json={"name": "Plan Currency Project", "code": "PCP-008"},
        )
        assert proj_resp.status_code == 201
        project_id = proj_resp.json()["id"]

        phase_resp = client.post(
            "/api/v1/phases",
            json={"project_id": project_id, "name": "Phase 1", "sequence": 1},
        )
        assert phase_resp.status_code == 201
        phase_id = phase_resp.json()["id"]

        bldg_resp = client.post(
            f"/api/v1/phases/{phase_id}/buildings",
            json={"name": "Block A", "code": "BLK-PCP008"},
        )
        assert bldg_resp.status_code == 201
        building_id = bldg_resp.json()["id"]

        floor_resp = client.post(
            f"/api/v1/buildings/{building_id}/floors",
            json={"name": "Floor 1", "code": "FL-01", "sequence_number": 1},
        )
        assert floor_resp.status_code == 201
        floor_id = floor_resp.json()["id"]

        unit_resp = client.post(
            "/api/v1/units",
            json={
                "floor_id": floor_id,
                "unit_number": "301",
                "unit_type": "studio",
                "internal_area": 60.0,
            },
        )
        assert unit_resp.status_code == 201
        unit_id = unit_resp.json()["id"]

        buyer_resp = client.post(
            "/api/v1/sales/buyers",
            json={
                "full_name": "Plan Buyer",
                "email": "plan.buyer@test.com",
                "phone": "+9622222222",
            },
        )
        assert buyer_resp.status_code == 201
        buyer_id = buyer_resp.json()["id"]

        contract_resp = client.post(
            "/api/v1/sales/contracts",
            json={
                "unit_id": unit_id,
                "buyer_id": buyer_id,
                "contract_number": "PCP-AED-001",
                "contract_date": "2026-01-01",
                "contract_price": 300_000.0,
            },
        )
        assert contract_resp.status_code == 201, contract_resp.text
        contract_id = contract_resp.json()["id"]

        plan_resp = client.post(
            "/api/v1/payment-plans",
            json={
                "contract_id": contract_id,
                "plan_name": "Quarterly Plan",
                "number_of_installments": 4,
                "start_date": "2026-02-01",
            },
        )
        assert plan_resp.status_code == 201, plan_resp.text
        plan_data = plan_resp.json()
        assert "currency" in plan_data, (
            "Payment plan response must include 'currency' field"
        )
        assert plan_data["currency"] == DEFAULT_CURRENCY

    def test_jod_contract_payment_plan_preserves_jod_denomination(self, client: TestClient):
        """Creating a payment plan for a JOD contract must produce JOD schedule rows
        and a JOD-denominated plan response — not fall back to the platform default."""
        proj_resp = client.post(
            "/api/v1/projects",
            json={"name": "JOD Plan Project", "code": "JPP-008A", "base_currency": "JOD"},
        )
        assert proj_resp.status_code == 201, proj_resp.text
        project_id = proj_resp.json()["id"]

        phase_resp = client.post(
            "/api/v1/phases",
            json={"project_id": project_id, "name": "Phase 1", "sequence": 1},
        )
        assert phase_resp.status_code == 201
        phase_id = phase_resp.json()["id"]

        bldg_resp = client.post(
            f"/api/v1/phases/{phase_id}/buildings",
            json={"name": "Block A", "code": "BLK-JPP008A"},
        )
        assert bldg_resp.status_code == 201
        building_id = bldg_resp.json()["id"]

        floor_resp = client.post(
            f"/api/v1/buildings/{building_id}/floors",
            json={"name": "Floor 1", "code": "FL-01", "sequence_number": 1},
        )
        assert floor_resp.status_code == 201
        floor_id = floor_resp.json()["id"]

        unit_resp = client.post(
            "/api/v1/units",
            json={
                "floor_id": floor_id,
                "unit_number": "401",
                "unit_type": "studio",
                "internal_area": 75.0,
            },
        )
        assert unit_resp.status_code == 201
        unit_id = unit_resp.json()["id"]

        buyer_resp = client.post(
            "/api/v1/sales/buyers",
            json={"full_name": "JOD Plan Buyer", "email": "jod.plan@test.com", "phone": "+9623333333"},
        )
        assert buyer_resp.status_code == 201
        buyer_id = buyer_resp.json()["id"]

        contract_resp = client.post(
            "/api/v1/sales/contracts",
            json={
                "unit_id": unit_id,
                "buyer_id": buyer_id,
                "contract_number": "JPP-JOD-001",
                "contract_date": "2026-01-01",
                "contract_price": 250_000.0,
                "currency": "JOD",
            },
        )
        assert contract_resp.status_code == 201, contract_resp.text
        contract_id = contract_resp.json()["id"]

        plan_resp = client.post(
            "/api/v1/payment-plans",
            json={
                "contract_id": contract_id,
                "plan_name": "JOD Quarterly Plan",
                "number_of_installments": 4,
                "start_date": "2026-02-01",
            },
        )
        assert plan_resp.status_code == 201, plan_resp.text
        plan_data = plan_resp.json()

        # Plan-level response must carry JOD denomination
        assert plan_data["currency"] == CURRENCY_JOD, (
            f"Payment plan response must use contract currency 'JOD', "
            f"got {plan_data['currency']!r}"
        )

        # Every persisted schedule row must also be JOD
        for installment in plan_data["installments"]:
            assert installment["currency"] == CURRENCY_JOD, (
                f"Installment {installment['installment_number']} must carry "
                f"contract currency 'JOD', got {installment['currency']!r}"
            )

    def test_jod_contract_schedule_list_response_preserves_jod_denomination(self, client: TestClient):
        """GET schedule list for a JOD contract must return currency='JOD' at the
        list-response level — sourced from the parent contract, not items[0]."""
        proj_resp = client.post(
            "/api/v1/projects",
            json={"name": "JOD Schedule List Project", "code": "JSL-008A", "base_currency": "JOD"},
        )
        assert proj_resp.status_code == 201
        project_id = proj_resp.json()["id"]

        phase_resp = client.post(
            "/api/v1/phases",
            json={"project_id": project_id, "name": "Phase 1", "sequence": 1},
        )
        assert phase_resp.status_code == 201
        phase_id = phase_resp.json()["id"]

        bldg_resp = client.post(
            f"/api/v1/phases/{phase_id}/buildings",
            json={"name": "Block A", "code": "BLK-JSL008A"},
        )
        assert bldg_resp.status_code == 201
        building_id = bldg_resp.json()["id"]

        floor_resp = client.post(
            f"/api/v1/buildings/{building_id}/floors",
            json={"name": "Floor 1", "code": "FL-01", "sequence_number": 1},
        )
        assert floor_resp.status_code == 201
        floor_id = floor_resp.json()["id"]

        unit_resp = client.post(
            "/api/v1/units",
            json={
                "floor_id": floor_id,
                "unit_number": "501",
                "unit_type": "studio",
                "internal_area": 100.0,
            },
        )
        assert unit_resp.status_code == 201
        unit_id = unit_resp.json()["id"]

        buyer_resp = client.post(
            "/api/v1/sales/buyers",
            json={"full_name": "JOD Schedule Buyer", "email": "jod.schedule@test.com", "phone": "+9624444444"},
        )
        assert buyer_resp.status_code == 201
        buyer_id = buyer_resp.json()["id"]

        contract_resp = client.post(
            "/api/v1/sales/contracts",
            json={
                "unit_id": unit_id,
                "buyer_id": buyer_id,
                "contract_number": "JSL-JOD-001",
                "contract_date": "2026-01-01",
                "contract_price": 180_000.0,
                "currency": "JOD",
            },
        )
        assert contract_resp.status_code == 201, contract_resp.text
        contract_id = contract_resp.json()["id"]

        # Create payment plan and assert it succeeded
        plan_resp = client.post(
            "/api/v1/payment-plans",
            json={
                "contract_id": contract_id,
                "plan_name": "JOD Schedule Plan",
                "number_of_installments": 3,
                "start_date": "2026-03-01",
            },
        )
        assert plan_resp.status_code == 201, plan_resp.text
        plan_data = plan_resp.json()
        assert len(plan_data["installments"]) == 3, "Expected 3 installments"
        for inst in plan_data["installments"]:
            assert inst["currency"] == CURRENCY_JOD, (
                f"Installment {inst['installment_number']} must carry JOD, "
                f"got {inst['currency']!r}"
            )

        # Fetch the schedule list — must preserve JOD at the list level
        schedule_resp = client.get(f"/api/v1/payment-plans/contracts/{contract_id}/schedule")
        assert schedule_resp.status_code == 200, schedule_resp.text
        schedule_data = schedule_resp.json()

        assert schedule_data["currency"] == CURRENCY_JOD, (
            f"Schedule list response must use contract currency 'JOD', "
            f"got {schedule_data['currency']!r}"
        )

    def test_build_list_response_mismatch_guard_raises_500(self):
        """_build_list_response must raise HTTP 500 if any persisted row carries
        a currency different from the contract denomination passed in."""
        import datetime
        from unittest.mock import MagicMock

        import pytest
        from fastapi import HTTPException

        from app.modules.payment_plans.service import PaymentPlanService

        now = datetime.datetime.now(datetime.timezone.utc)
        today = datetime.date.today()

        good_row = MagicMock()
        good_row.id = "row-001"
        good_row.contract_id = "ctr-guard"
        good_row.template_id = None
        good_row.installment_number = 1
        good_row.due_date = today
        good_row.due_amount = 50_000.0
        good_row.currency = CURRENCY_JOD
        good_row.status = "pending"
        good_row.notes = None
        good_row.created_at = now
        good_row.updated_at = now

        bad_row = MagicMock()
        bad_row.id = "row-002"
        bad_row.contract_id = "ctr-guard"
        bad_row.template_id = None
        bad_row.installment_number = 2
        bad_row.due_date = today
        bad_row.due_amount = 50_000.0
        bad_row.currency = DEFAULT_CURRENCY  # wrong — default instead of JOD
        bad_row.status = "pending"
        bad_row.notes = None
        bad_row.created_at = now
        bad_row.updated_at = now

        with pytest.raises(HTTPException) as exc_info:
            PaymentPlanService._build_list_response(
                "ctr-guard", [good_row, bad_row], CURRENCY_JOD
            )
        assert exc_info.value.status_code == 500
        assert "currency mismatch" in exc_info.value.detail.lower()

    def test_build_plan_response_mismatch_guard_raises_500(self):
        """_build_plan_response must raise HTTP 500 if any persisted row carries
        a currency different from the contract denomination passed in."""
        import datetime
        from unittest.mock import MagicMock

        import pytest
        from fastapi import HTTPException

        from app.modules.payment_plans.service import PaymentPlanService

        now = datetime.datetime.now(datetime.timezone.utc)
        today = datetime.date.today()

        def _make_row(idx: int, currency: str) -> MagicMock:
            row = MagicMock()
            row.id = f"row-{idx:03d}"
            row.contract_id = "ctr-guard2"
            row.template_id = "tmpl-001"
            row.installment_number = idx
            row.due_date = today
            row.due_amount = 30_000.0
            row.currency = currency
            row.status = "pending"
            row.notes = None
            row.created_at = now
            row.updated_at = now
            return row

        rows = [_make_row(1, CURRENCY_JOD), _make_row(2, DEFAULT_CURRENCY)]

        with pytest.raises(HTTPException) as exc_info:
            PaymentPlanService._build_plan_response(
                "Test Plan", "standard_installments", rows, CURRENCY_JOD
            )
        assert exc_info.value.status_code == 500
        assert "currency mismatch" in exc_info.value.detail.lower()
