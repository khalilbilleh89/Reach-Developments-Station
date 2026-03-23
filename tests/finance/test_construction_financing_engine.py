"""
Tests for the PR-FIN-036 Construction Financing & Draw Schedule Engine.

Validates:
  - debt / equity allocation correctness with default 60/40 split
  - debt + equity equals financed_cost per period (residual approach)
  - cumulative_debt and cumulative_equity are monotonically non-decreasing
  - financing_start_offset defers financing by N periods
  - financing_probability scales period costs before allocation
  - empty cashflow periods return zero-valued summary
  - zero execution cost periods produce zero debt and equity draws
  - custom debt/equity ratios produce correct allocations
  - portfolio totals equal sum of project totals
  - phase-scope produces correct scope_type
  - summary debt_to_cost_ratio equals total_debt / total_cost
  - summary equity_to_cost_ratio equals total_equity / total_cost
  - zero total_cost produces zero ratios (no division by zero)
  - cumulative values at final period equal summary totals
  - service layer integrates cashflow engine and financing engine
  - service layer raises ResourceNotFoundError for unknown project
  - service layer raises ResourceNotFoundError for unknown phase
  - service layer raises ValidationError for inverted date window
  - schema rejects loan_draw_method != pro_rata with 422
  - schema rejects equity_injection_method != pro_rata with 422
  - schema rejects debt_ratio + equity_ratio != 1.0 with 422
  - API endpoint returns 200 with valid parameters
  - API endpoint returns 422 for inverted date window (deterministic)
  - API endpoint returns 404 for unknown project
  - API endpoint returns 404 for unknown phase
  - debt_ratio query parameter is respected
  - period_label format is YYYY-MM
  - portfolio API endpoint returns 200 with valid parameters
  - portfolio project_results is list
"""

import pytest
from datetime import date
from unittest.mock import MagicMock

from pydantic import ValidationError as PydanticValidationError

from app.core.errors import ResourceNotFoundError, ValidationError
from app.modules.finance.construction_cashflow_engine import ConstructionCashflowPeriodResult
from app.modules.finance.construction_financing_engine import (
    ConstructionFinancingAssumptions,
    compute_phase_construction_financing,
    compute_portfolio_construction_financing,
    compute_project_construction_financing,
)
from app.modules.finance.cashflow_service import CashflowForecastService
from app.modules.finance.schemas import (
    ConstructionFinancingAssumptionsSchema,
)
from app.modules.phases.models import Phase
from app.modules.projects.models import Project


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _period(
    label: str,
    planned: float,
    committed: float,
    expected: float,
    cumulative: float = 0.0,
    count: int = 1,
) -> ConstructionCashflowPeriodResult:
    return ConstructionCashflowPeriodResult(
        period_label=label,
        planned_cost=planned,
        committed_cost=committed,
        expected_cost=expected,
        variance_to_plan=round(expected - planned, 2),
        cumulative_cost=cumulative,
        cost_item_count=count,
    )


def _build_periods(monthly_expected: float, months: int = 12) -> list:
    """Build a list of cashflow period results with uniform expected cost."""
    periods = []
    cumulative = 0.0
    start = date(2026, 1, 1)
    for i in range(months):
        year = start.year + (start.month + i - 1) // 12
        month = (start.month + i - 1) % 12 + 1
        label = f"{year:04d}-{month:02d}"
        cumulative = round(cumulative + monthly_expected, 2)
        periods.append(
            _period(label, monthly_expected, 0.0, monthly_expected, cumulative)
        )
    return periods


# ---------------------------------------------------------------------------
# Pure engine tests — no DB
# ---------------------------------------------------------------------------


class TestComputeProjectConstructionFinancing:
    """Tests for compute_project_construction_financing — pure calculations, no DB."""

    def test_empty_periods_returns_zero_summary(self):
        result = compute_project_construction_financing("p-001", [])
        assert result.scope_type == "project"
        assert result.scope_id == "p-001"
        assert result.summary.total_cost == 0.0
        assert result.summary.total_debt == 0.0
        assert result.summary.total_equity == 0.0
        assert result.summary.debt_to_cost_ratio == 0.0
        assert result.summary.equity_to_cost_ratio == 0.0
        assert result.periods == []

    def test_default_60_40_split(self):
        """Default 60/40 split: 1,000 per month × 12 months → 600 debt, 400 equity per month."""
        periods = _build_periods(1_000.0, 12)
        result = compute_project_construction_financing("p-001", periods)

        for p in result.periods:
            assert p.debt_draw == pytest.approx(600.0)
            assert p.equity_contribution == pytest.approx(400.0)
            assert p.period_cost == pytest.approx(1_000.0)

    def test_debt_plus_equity_equals_financed_cost(self):
        """debt_draw + equity_contribution must equal financed_cost for every period."""
        periods = _build_periods(1_500.0, 6)
        result = compute_project_construction_financing("p-001", periods)

        for p in result.periods:
            assert p.debt_draw + p.equity_contribution == pytest.approx(p.period_cost)

    def test_summary_totals_are_sums_of_periods(self):
        periods = _build_periods(1_000.0, 6)
        result = compute_project_construction_financing("p-001", periods)

        expected_total_debt = sum(p.debt_draw for p in result.periods)
        expected_total_equity = sum(p.equity_contribution for p in result.periods)
        expected_total_cost = sum(p.period_cost for p in result.periods)

        assert result.summary.total_debt == pytest.approx(expected_total_debt)
        assert result.summary.total_equity == pytest.approx(expected_total_equity)
        assert result.summary.total_cost == pytest.approx(expected_total_cost)

    def test_cumulative_debt_monotonically_non_decreasing(self):
        periods = _build_periods(1_000.0, 6)
        result = compute_project_construction_financing("p-001", periods)

        prev_cumulative = 0.0
        for p in result.periods:
            assert p.cumulative_debt >= prev_cumulative
            prev_cumulative = p.cumulative_debt

    def test_cumulative_equity_monotonically_non_decreasing(self):
        periods = _build_periods(1_000.0, 6)
        result = compute_project_construction_financing("p-001", periods)

        prev_cumulative = 0.0
        for p in result.periods:
            assert p.cumulative_equity >= prev_cumulative
            prev_cumulative = p.cumulative_equity

    def test_final_cumulative_debt_equals_summary_total_debt(self):
        periods = _build_periods(1_000.0, 6)
        result = compute_project_construction_financing("p-001", periods)

        assert result.periods[-1].cumulative_debt == pytest.approx(result.summary.total_debt)
        assert result.periods[-1].cumulative_equity == pytest.approx(result.summary.total_equity)

    def test_custom_debt_ratio_70_30(self):
        assumptions = ConstructionFinancingAssumptions(debt_ratio=0.70, equity_ratio=0.30)
        periods = _build_periods(1_000.0, 3)
        result = compute_project_construction_financing("p-001", periods, assumptions)

        for p in result.periods:
            assert p.debt_draw == pytest.approx(700.0)
            assert p.equity_contribution == pytest.approx(300.0)

    def test_100_percent_debt_ratio(self):
        """100% debt: all cost is debt, equity is zero."""
        assumptions = ConstructionFinancingAssumptions(debt_ratio=1.0, equity_ratio=0.0)
        periods = _build_periods(2_000.0, 3)
        result = compute_project_construction_financing("p-001", periods, assumptions)

        for p in result.periods:
            assert p.debt_draw == pytest.approx(2_000.0)
            assert p.equity_contribution == pytest.approx(0.0)

    def test_zero_financing_probability_yields_zero_draws(self):
        """financing_probability=0.0 → no debt or equity drawn."""
        assumptions = ConstructionFinancingAssumptions(financing_probability=0.0)
        periods = _build_periods(1_000.0, 3)
        result = compute_project_construction_financing("p-001", periods, assumptions)

        for p in result.periods:
            assert p.debt_draw == 0.0
            assert p.equity_contribution == 0.0

    def test_financing_probability_scales_draws(self):
        """50% financing probability → half the normal debt/equity amounts."""
        assumptions = ConstructionFinancingAssumptions(financing_probability=0.5)
        periods = _build_periods(1_000.0, 3)
        result = compute_project_construction_financing("p-001", periods, assumptions)

        for p in result.periods:
            assert p.debt_draw == pytest.approx(300.0)  # 1000 × 0.5 × 0.60
            assert p.equity_contribution == pytest.approx(200.0)  # 1000 × 0.5 × 0.40

    def test_financing_start_offset_defers_financing(self):
        """With offset=2, first 2 periods have zero draws."""
        assumptions = ConstructionFinancingAssumptions(financing_start_offset=2)
        periods = _build_periods(1_000.0, 5)
        result = compute_project_construction_financing("p-001", periods, assumptions)

        # First 2 periods: zero draws
        assert result.periods[0].debt_draw == 0.0
        assert result.periods[0].equity_contribution == 0.0
        assert result.periods[1].debt_draw == 0.0
        assert result.periods[1].equity_contribution == 0.0

        # Periods from offset onward: normal draws
        for p in result.periods[2:]:
            assert p.debt_draw == pytest.approx(600.0)
            assert p.equity_contribution == pytest.approx(400.0)

    def test_financing_start_offset_preserves_period_cost(self):
        """period_cost is always the expected_cost regardless of offset."""
        assumptions = ConstructionFinancingAssumptions(financing_start_offset=1)
        periods = _build_periods(1_000.0, 3)
        result = compute_project_construction_financing("p-001", periods, assumptions)

        for p in result.periods:
            assert p.period_cost == pytest.approx(1_000.0)

    def test_zero_expected_cost_periods_produce_zero_draws(self):
        """Periods with expected_cost=0 produce zero debt and equity draws."""
        p1 = _period("2026-01", 0.0, 0.0, 0.0, 0.0, 0)
        p2 = _period("2026-02", 1_000.0, 0.0, 1_000.0, 1_000.0)
        result = compute_project_construction_financing("p-001", [p1, p2])

        assert result.periods[0].debt_draw == 0.0
        assert result.periods[0].equity_contribution == 0.0
        assert result.periods[1].debt_draw == pytest.approx(600.0)

    def test_debt_to_cost_ratio_in_summary(self):
        periods = _build_periods(1_000.0, 3)
        result = compute_project_construction_financing("p-001", periods)

        assert result.summary.debt_to_cost_ratio == pytest.approx(0.6, abs=1e-4)
        assert result.summary.equity_to_cost_ratio == pytest.approx(0.4, abs=1e-4)

    def test_zero_total_cost_produces_zero_ratios(self):
        """No division by zero when total_cost is zero."""
        result = compute_project_construction_financing("p-001", [])
        assert result.summary.debt_to_cost_ratio == 0.0
        assert result.summary.equity_to_cost_ratio == 0.0

    def test_period_label_format_yyyy_mm(self):
        periods = [
            _period("2026-01", 500.0, 0.0, 500.0),
            _period("2026-02", 500.0, 0.0, 500.0),
        ]
        result = compute_project_construction_financing("p-001", periods)
        labels = [p.period_label for p in result.periods]
        assert labels == ["2026-01", "2026-02"]


class TestComputePhaseConstructionFinancing:
    """Tests for compute_phase_construction_financing."""

    def test_scope_type_is_phase(self):
        periods = _build_periods(1_000.0, 3)
        result = compute_phase_construction_financing("ph-001", periods)
        assert result.scope_type == "phase"
        assert result.scope_id == "ph-001"

    def test_phase_debt_equity_correctness(self):
        periods = _build_periods(2_000.0, 3)
        result = compute_phase_construction_financing("ph-001", periods)

        assert result.summary.total_debt == pytest.approx(2_000.0 * 3 * 0.6)
        assert result.summary.total_equity == pytest.approx(2_000.0 * 3 * 0.4)


class TestComputePortfolioConstructionFinancing:
    """Tests for compute_portfolio_construction_financing."""

    def test_empty_portfolio_returns_empty_result(self):
        result = compute_portfolio_construction_financing({})
        assert result.scope_type == "portfolio"
        assert result.summary.total_cost == 0.0
        assert result.summary.total_debt == 0.0
        assert result.summary.total_equity == 0.0
        assert result.periods == []
        assert result.project_results == []

    def test_portfolio_totals_equal_sum_of_projects(self):
        """Portfolio debt/equity totals must equal the sum of per-project totals."""
        p1_periods = _build_periods(1_000.0, 3)
        p2_periods = _build_periods(2_000.0, 3)

        result = compute_portfolio_construction_financing(
            {"p-001": p1_periods, "p-002": p2_periods}
        )

        project_debt_total = sum(pr.summary.total_debt for pr in result.project_results)
        project_equity_total = sum(pr.summary.total_equity for pr in result.project_results)

        assert result.summary.total_debt == pytest.approx(project_debt_total)
        assert result.summary.total_equity == pytest.approx(project_equity_total)

    def test_portfolio_projects_sorted_deterministically(self):
        """Projects must be processed in sorted order by project_id."""
        p1_periods = _build_periods(1_000.0, 2)
        p2_periods = _build_periods(2_000.0, 2)

        result = compute_portfolio_construction_financing(
            {"p-002": p2_periods, "p-001": p1_periods}
        )

        ids = [pr.scope_id for pr in result.project_results]
        assert ids == sorted(ids)

    def test_portfolio_period_labels_sorted(self):
        """Portfolio periods should be in sorted label order."""
        p1_periods = _build_periods(500.0, 3)
        result = compute_portfolio_construction_financing({"p-001": p1_periods})

        labels = [p.period_label for p in result.periods]
        assert labels == sorted(labels)

    def test_portfolio_cumulative_final_equals_summary_total(self):
        p1_periods = _build_periods(1_000.0, 4)
        result = compute_portfolio_construction_financing({"p-001": p1_periods})

        assert result.periods[-1].cumulative_debt == pytest.approx(result.summary.total_debt)
        assert result.periods[-1].cumulative_equity == pytest.approx(result.summary.total_equity)

    def test_single_project_portfolio_matches_project_result(self):
        """Portfolio with one project should match the standalone project result."""
        periods = _build_periods(1_000.0, 3)
        portfolio_result = compute_portfolio_construction_financing({"p-001": periods})
        project_result = compute_project_construction_financing("p-001", periods)

        assert portfolio_result.summary.total_debt == pytest.approx(
            project_result.summary.total_debt
        )
        assert portfolio_result.summary.total_equity == pytest.approx(
            project_result.summary.total_equity
        )


# ---------------------------------------------------------------------------
# Service layer tests
# ---------------------------------------------------------------------------


class TestCashflowServiceConstructionFinancing:
    """Tests for CashflowForecastService construction financing methods."""

    def _make_service(self) -> CashflowForecastService:
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        service = CashflowForecastService(db)
        return service

    def _make_service_with_project(self, project_id: str = "p-001") -> CashflowForecastService:
        db = MagicMock()
        mock_project = MagicMock(spec=Project)
        mock_project.id = project_id

        def _query_side_effect(model):
            mock = MagicMock()
            if model is Project:
                mock.filter.return_value.first.return_value = mock_project
            else:
                mock.filter.return_value.first.return_value = None
            return mock

        db.query.side_effect = _query_side_effect
        return CashflowForecastService(db)

    def _make_service_with_phase(self, phase_id: str = "ph-001") -> CashflowForecastService:
        db = MagicMock()
        mock_phase = MagicMock(spec=Phase)
        mock_phase.id = phase_id

        def _query_side_effect(model):
            mock = MagicMock()
            if model is Phase:
                mock.filter.return_value.first.return_value = mock_phase
            else:
                mock.filter.return_value.first.return_value = None
            return mock

        db.query.side_effect = _query_side_effect
        return CashflowForecastService(db)

    def test_project_financing_raises_not_found_for_unknown_project(self):
        service = self._make_service()
        with pytest.raises(ResourceNotFoundError):
            service.compute_project_construction_financing(
                "unknown", date(2026, 1, 1), date(2026, 12, 31)
            )

    def test_phase_financing_raises_not_found_for_unknown_phase(self):
        service = self._make_service()
        # Correct test: unknown phase raises ResourceNotFoundError
        with pytest.raises(ResourceNotFoundError):
            service.compute_phase_construction_financing(
                "unknown", date(2026, 1, 1), date(2026, 12, 31)
            )

    def test_project_financing_raises_validation_error_for_inverted_dates(self):
        service = self._make_service_with_project()
        with pytest.raises(ValidationError):
            service.compute_project_construction_financing(
                "p-001", date(2026, 12, 31), date(2026, 1, 1)
            )

    def test_phase_financing_raises_validation_error_for_inverted_dates(self):
        service = self._make_service_with_phase()
        with pytest.raises(ValidationError):
            service.compute_phase_construction_financing(
                "ph-001", date(2026, 12, 31), date(2026, 1, 1)
            )

    def test_project_financing_returns_correct_schema_shape(self):
        service = self._make_service_with_project()
        response = service.compute_project_construction_financing(
            "p-001", date(2026, 1, 1), date(2026, 3, 31)
        )
        assert response.scope_type == "project"
        assert response.project_id == "p-001"
        assert hasattr(response, "summary")
        assert hasattr(response, "periods")
        assert hasattr(response, "assumptions")

    def test_phase_financing_returns_correct_schema_shape(self):
        service = self._make_service_with_phase()
        response = service.compute_phase_construction_financing(
            "ph-001", date(2026, 1, 1), date(2026, 3, 31)
        )
        assert response.scope_type == "phase"
        assert response.phase_id == "ph-001"
        assert hasattr(response, "summary")
        assert hasattr(response, "periods")

    def test_portfolio_financing_returns_correct_schema_shape(self):
        service = self._make_service()
        response = service.compute_portfolio_construction_financing(
            date(2026, 1, 1), date(2026, 3, 31)
        )
        assert response.scope_type == "portfolio"
        assert hasattr(response, "summary")
        assert hasattr(response, "periods")
        assert isinstance(response.project_results, list)

    def test_portfolio_financing_raises_validation_error_for_inverted_dates(self):
        service = self._make_service()
        with pytest.raises(ValidationError):
            service.compute_portfolio_construction_financing(
                date(2026, 12, 31), date(2026, 1, 1)
            )

    def test_project_financing_assumptions_are_reflected_in_response(self):
        """Custom assumptions should be reflected in the response assumptions field."""
        service = self._make_service_with_project()
        financing_schema = ConstructionFinancingAssumptionsSchema(
            debt_ratio=0.70, equity_ratio=0.30
        )
        response = service.compute_project_construction_financing(
            "p-001",
            date(2026, 1, 1),
            date(2026, 3, 31),
            financing_assumptions_schema=financing_schema,
        )
        assert response.assumptions.debt_ratio == pytest.approx(0.70)
        assert response.assumptions.equity_ratio == pytest.approx(0.30)

    def test_project_summary_fields_are_non_negative(self):
        service = self._make_service_with_project()
        response = service.compute_project_construction_financing(
            "p-001", date(2026, 1, 1), date(2026, 6, 30)
        )
        assert response.summary.total_cost >= 0.0
        assert response.summary.total_debt >= 0.0
        assert response.summary.total_equity >= 0.0
        assert response.summary.debt_to_cost_ratio >= 0.0
        assert response.summary.equity_to_cost_ratio >= 0.0


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------


class TestConstructionFinancingAssumptionsSchema:
    """Tests for ConstructionFinancingAssumptionsSchema validators."""

    def test_default_schema_is_valid(self):
        schema = ConstructionFinancingAssumptionsSchema()
        assert schema.debt_ratio == pytest.approx(0.60)
        assert schema.equity_ratio == pytest.approx(0.40)
        assert schema.loan_draw_method == "pro_rata"
        assert schema.equity_injection_method == "pro_rata"

    def test_ratios_must_sum_to_one(self):
        with pytest.raises(PydanticValidationError):
            ConstructionFinancingAssumptionsSchema(debt_ratio=0.60, equity_ratio=0.20)

    def test_overfunded_ratios_rejected(self):
        with pytest.raises(PydanticValidationError):
            ConstructionFinancingAssumptionsSchema(debt_ratio=0.70, equity_ratio=0.50)

    def test_custom_valid_ratios_accepted(self):
        schema = ConstructionFinancingAssumptionsSchema(debt_ratio=0.70, equity_ratio=0.30)
        assert schema.debt_ratio == pytest.approx(0.70)
        assert schema.equity_ratio == pytest.approx(0.30)

    def test_unsupported_loan_draw_method_rejected(self):
        with pytest.raises(PydanticValidationError):
            ConstructionFinancingAssumptionsSchema(loan_draw_method="front_loaded")

    def test_unsupported_loan_draw_method_back_loaded_rejected(self):
        with pytest.raises(PydanticValidationError):
            ConstructionFinancingAssumptionsSchema(loan_draw_method="back_loaded")

    def test_unsupported_equity_injection_method_upfront_rejected(self):
        with pytest.raises(PydanticValidationError):
            ConstructionFinancingAssumptionsSchema(
                equity_injection_method="upfront",
            )

    def test_unsupported_equity_injection_method_on_demand_rejected(self):
        with pytest.raises(PydanticValidationError):
            ConstructionFinancingAssumptionsSchema(
                equity_injection_method="on_demand",
            )

    def test_unknown_loan_draw_method_rejected(self):
        with pytest.raises(PydanticValidationError):
            ConstructionFinancingAssumptionsSchema(loan_draw_method="unknown_method")

    def test_100_pct_debt_accepted(self):
        schema = ConstructionFinancingAssumptionsSchema(debt_ratio=1.0, equity_ratio=0.0)
        assert schema.debt_ratio == pytest.approx(1.0)

    def test_100_pct_equity_accepted(self):
        schema = ConstructionFinancingAssumptionsSchema(debt_ratio=0.0, equity_ratio=1.0)
        assert schema.equity_ratio == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


class TestConstructionFinancingAPI:
    """API endpoint tests using the shared conftest `client` fixture.

    The `client` fixture (from tests/conftest.py) injects an in-memory SQLite
    DB and overrides the auth dependency, so tests run deterministically without
    a real login flow.
    """

    BASE = "/api/v1/finance"

    def test_project_financing_endpoint_returns_422_for_inverted_dates(self, client):
        """Inverted date window must always return 422 (_validate_date_window runs first)."""
        resp = client.get(
            f"{self.BASE}/projects/some-id/construction-financing",
            params={"start_date": "2026-12-31", "end_date": "2026-01-01"},
        )
        assert resp.status_code == 422

    def test_project_financing_endpoint_returns_404_for_unknown_project(self, client):
        resp = client.get(
            f"{self.BASE}/projects/nonexistent-project-xyz/construction-financing",
            params={"start_date": "2026-01-01", "end_date": "2026-12-31"},
        )
        assert resp.status_code == 404

    def test_phase_financing_endpoint_returns_404_for_unknown_phase(self, client):
        resp = client.get(
            f"{self.BASE}/phases/nonexistent-phase-xyz/construction-financing",
            params={"start_date": "2026-01-01", "end_date": "2026-12-31"},
        )
        assert resp.status_code == 404

    def test_portfolio_financing_endpoint_returns_200(self, client):
        resp = client.get(
            f"{self.BASE}/portfolio/construction-financing",
            params={"start_date": "2026-01-01", "end_date": "2026-03-31"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["scope_type"] == "portfolio"
        assert "summary" in data
        assert "periods" in data
        assert "project_results" in data

    def test_portfolio_financing_returns_422_for_inverted_dates(self, client):
        resp = client.get(
            f"{self.BASE}/portfolio/construction-financing",
            params={"start_date": "2026-12-31", "end_date": "2026-01-01"},
        )
        assert resp.status_code == 422

    def test_portfolio_financing_debt_ratio_query_param(self, client):
        resp = client.get(
            f"{self.BASE}/portfolio/construction-financing",
            params={
                "start_date": "2026-01-01",
                "end_date": "2026-03-31",
                "debt_ratio": 0.80,
                "equity_ratio": 0.20,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["assumptions"]["debt_ratio"] == pytest.approx(0.80)
        assert data["assumptions"]["equity_ratio"] == pytest.approx(0.20)

    def test_portfolio_financing_summary_fields_non_negative(self, client):
        resp = client.get(
            f"{self.BASE}/portfolio/construction-financing",
            params={"start_date": "2026-01-01", "end_date": "2026-06-30"},
        )
        assert resp.status_code == 200
        summary = resp.json()["summary"]
        assert summary["total_cost"] >= 0.0
        assert summary["total_debt"] >= 0.0
        assert summary["total_equity"] >= 0.0
        assert summary["debt_to_cost_ratio"] >= 0.0
        assert summary["equity_to_cost_ratio"] >= 0.0

    def test_unsupported_loan_draw_method_returns_422(self, client):
        """front_loaded is a declared enum value but not yet implemented; must return 422."""
        resp = client.get(
            f"{self.BASE}/portfolio/construction-financing",
            params={
                "start_date": "2026-01-01",
                "end_date": "2026-03-31",
                "loan_draw_method": "front_loaded",
            },
        )
        assert resp.status_code == 422

    def test_unsupported_equity_injection_method_returns_422(self, client):
        """upfront is a declared enum value but not yet implemented; must return 422."""
        resp = client.get(
            f"{self.BASE}/portfolio/construction-financing",
            params={
                "start_date": "2026-01-01",
                "end_date": "2026-03-31",
                "equity_injection_method": "upfront",
            },
        )
        assert resp.status_code == 422

    def test_mismatched_ratios_returns_422(self, client):
        """debt_ratio + equity_ratio != 1.0 must return 422."""
        resp = client.get(
            f"{self.BASE}/portfolio/construction-financing",
            params={
                "start_date": "2026-01-01",
                "end_date": "2026-03-31",
                "debt_ratio": 0.60,
                "equity_ratio": 0.20,
            },
        )
        assert resp.status_code == 422

