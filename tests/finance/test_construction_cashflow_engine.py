"""
Tests for the PR-FIN-034 Construction Cashflow Forecast Engine.

Validates:
  - linear spread accuracy across full execution windows
  - partial window truncation (records outside forecast window excluded)
  - cumulative_cost is monotonically non-decreasing
  - execution_probability scales expected_cost correctly
  - committed cost override when include_committed=True and committed_amount > 0
  - committed cost ignored when include_committed=False
  - portfolio totals equal sum of project totals
  - phase-scope forecast produces correct results
  - invalid date window raises ValueError
  - empty cost records return zero-valued period results
  - multi-category cost aggregation within a period
  - single-month execution window
  - cost records entirely outside forecast window contribute nothing
  - partial overlap (record starts before window, ends inside)
  - partial overlap (record starts inside window, ends after)
  - variance_to_plan = expected_cost − planned_cost
  - execution_probability = 0.0 produces zero expected_cost
  - multiple projects in portfolio are sorted deterministically
  - service layer returns correct response schema shapes
  - service layer raises ResourceNotFoundError for unknown project
  - service layer raises ResourceNotFoundError for unknown phase
  - service layer raises ValidationError for inverted date window
  - portfolio service returns empty periods when no cost data
  - API endpoint returns 200 with valid parameters
  - API endpoint returns 422 for inverted date window
  - API endpoint returns 404 for unknown project
  - API endpoint returns 404 for unknown phase
  - execution_probability query parameter is respected
  - include_committed query parameter is respected
  - period_label format is YYYY-MM
  - cost_item_count reflects distinct contributing records
  - cumulative_cost in portfolio equals sum across all project periods
  - planned_total in summary equals sum of period planned_cost
  - expected_total in summary equals sum of period expected_cost
"""

import pytest
from datetime import date
from unittest.mock import MagicMock

from app.core.errors import ResourceNotFoundError, ValidationError
from app.modules.finance.construction_cashflow_engine import (
    ConstructionCostRecord,
    ConstructionForecastAssumptions,
    compute_phase_construction_cashflow,
    compute_portfolio_construction_cashflow,
    compute_project_construction_cashflow,
)
from app.modules.finance.cashflow_service import CashflowForecastService
from app.modules.finance.schemas import ConstructionForecastAssumptionsSchema
from app.modules.phases.models import Phase
from app.modules.projects.models import Project


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _record(
    planned: float,
    committed: float,
    start: date,
    end: date,
    project_id: str = "p-001",
    phase_id: str = "ph-001",
    category: str = "structural",
) -> ConstructionCostRecord:
    return ConstructionCostRecord(
        project_id=project_id,
        phase_id=phase_id,
        cost_category=category,
        planned_amount=planned,
        committed_amount=committed,
        start_date=start,
        end_date=end,
    )


# ---------------------------------------------------------------------------
# Pure engine tests — no DB
# ---------------------------------------------------------------------------


class TestComputeProjectConstructionCashflow:
    """Tests for compute_project_construction_cashflow — pure calculations, no DB."""

    START = date(2026, 1, 1)
    END = date(2026, 12, 31)

    def test_empty_records_returns_zero_periods(self):
        result = compute_project_construction_cashflow("p-001", [], self.START, self.END)
        assert result.scope_type == "project"
        assert result.scope_id == "p-001"
        assert result.summary.planned_total == 0.0
        assert result.summary.expected_total == 0.0
        assert result.summary.variance_to_plan == 0.0
        assert len(result.periods) == 12  # 12 monthly buckets

    def test_all_periods_present_for_window(self):
        result = compute_project_construction_cashflow("p-001", [], self.START, self.END)
        labels = [p.period_label for p in result.periods]
        assert labels[0] == "2026-01"
        assert labels[-1] == "2026-12"
        assert len(labels) == 12

    def test_period_label_format_yyyy_mm(self):
        result = compute_project_construction_cashflow(
            "p-001", [], date(2026, 3, 1), date(2026, 5, 31)
        )
        labels = [p.period_label for p in result.periods]
        assert labels == ["2026-03", "2026-04", "2026-05"]

    def test_linear_spread_accuracy_full_year(self):
        """1,200,000 over 12 months → 100,000 per month."""
        records = [_record(1_200_000.0, 0.0, date(2026, 1, 1), date(2026, 12, 31))]
        result = compute_project_construction_cashflow("p-001", records, self.START, self.END)

        for period in result.periods:
            assert period.planned_cost == pytest.approx(100_000.0)
            assert period.expected_cost == pytest.approx(100_000.0)

        assert result.summary.planned_total == pytest.approx(1_200_000.0)
        assert result.summary.expected_total == pytest.approx(1_200_000.0)

    def test_partial_window_truncation_record_outside_forecast(self):
        """A record ending before the forecast window contributes nothing."""
        records = [_record(600_000.0, 0.0, date(2025, 1, 1), date(2025, 6, 30))]
        result = compute_project_construction_cashflow(
            "p-001", records, date(2026, 1, 1), date(2026, 3, 31)
        )
        assert result.summary.planned_total == 0.0
        assert result.summary.expected_total == 0.0
        for period in result.periods:
            assert period.planned_cost == 0.0
            assert period.cost_item_count == 0

    def test_partial_overlap_record_starts_before_window(self):
        """Record from 2025-11 to 2026-02 in a 2026-01 to 2026-03 window.

        4 months total execution → 100,000 / month.
        Overlap: Jan + Feb = 2 months in window.
        """
        records = [_record(400_000.0, 0.0, date(2025, 11, 1), date(2026, 2, 28))]
        result = compute_project_construction_cashflow(
            "p-001", records, date(2026, 1, 1), date(2026, 3, 31)
        )
        # 4 total months → 100_000 / month; Jan + Feb overlap = 200_000
        jan = next(p for p in result.periods if p.period_label == "2026-01")
        feb = next(p for p in result.periods if p.period_label == "2026-02")
        mar = next(p for p in result.periods if p.period_label == "2026-03")
        assert jan.planned_cost == pytest.approx(100_000.0)
        assert feb.planned_cost == pytest.approx(100_000.0)
        assert mar.planned_cost == pytest.approx(0.0)
        assert result.summary.planned_total == pytest.approx(200_000.0)

    def test_partial_overlap_record_ends_after_window(self):
        """Record from 2026-11 to 2027-02 in a 2026-10 to 2026-12 window.

        4 months total → 250_000 / month. Overlap: Nov + Dec = 2 months.
        """
        records = [_record(1_000_000.0, 0.0, date(2026, 11, 1), date(2027, 2, 28))]
        result = compute_project_construction_cashflow(
            "p-001", records, date(2026, 10, 1), date(2026, 12, 31)
        )
        oct_ = next(p for p in result.periods if p.period_label == "2026-10")
        nov = next(p for p in result.periods if p.period_label == "2026-11")
        dec = next(p for p in result.periods if p.period_label == "2026-12")
        assert oct_.planned_cost == pytest.approx(0.0)
        assert nov.planned_cost == pytest.approx(250_000.0)
        assert dec.planned_cost == pytest.approx(250_000.0)

    def test_execution_probability_scaling(self):
        """execution_probability=0.5 halves the expected_cost."""
        records = [_record(1_200_000.0, 0.0, date(2026, 1, 1), date(2026, 12, 31))]
        assumptions = ConstructionForecastAssumptions(execution_probability=0.5)
        result = compute_project_construction_cashflow(
            "p-001", records, self.START, self.END, assumptions
        )
        for period in result.periods:
            assert period.planned_cost == pytest.approx(100_000.0)
            assert period.expected_cost == pytest.approx(50_000.0)
        assert result.summary.expected_total == pytest.approx(600_000.0)

    def test_execution_probability_zero_produces_zero_expected(self):
        """execution_probability=0.0 produces zero expected_cost in all periods."""
        records = [_record(1_200_000.0, 0.0, date(2026, 1, 1), date(2026, 12, 31))]
        assumptions = ConstructionForecastAssumptions(execution_probability=0.0)
        result = compute_project_construction_cashflow(
            "p-001", records, self.START, self.END, assumptions
        )
        for period in result.periods:
            assert period.expected_cost == pytest.approx(0.0)
        assert result.summary.expected_total == pytest.approx(0.0)

    def test_committed_cost_override_when_include_committed_true(self):
        """When committed_amount > 0 and include_committed=True, expected_cost uses committed."""
        records = [
            _record(1_200_000.0, 600_000.0, date(2026, 1, 1), date(2026, 12, 31))
        ]
        assumptions = ConstructionForecastAssumptions(
            execution_probability=1.0, include_committed=True
        )
        result = compute_project_construction_cashflow(
            "p-001", records, self.START, self.END, assumptions
        )
        for period in result.periods:
            assert period.committed_cost == pytest.approx(50_000.0)
            # expected uses committed (50_000) not planned (100_000)
            assert period.expected_cost == pytest.approx(50_000.0)

    def test_committed_cost_ignored_when_include_committed_false(self):
        """When include_committed=False, expected_cost uses planned regardless."""
        records = [
            _record(1_200_000.0, 600_000.0, date(2026, 1, 1), date(2026, 12, 31))
        ]
        assumptions = ConstructionForecastAssumptions(
            execution_probability=1.0, include_committed=False
        )
        result = compute_project_construction_cashflow(
            "p-001", records, self.START, self.END, assumptions
        )
        for period in result.periods:
            assert period.expected_cost == pytest.approx(100_000.0)

    def test_variance_to_plan_is_expected_minus_planned(self):
        """variance_to_plan == expected_cost − planned_cost for every period."""
        records = [_record(1_200_000.0, 0.0, date(2026, 1, 1), date(2026, 12, 31))]
        assumptions = ConstructionForecastAssumptions(execution_probability=0.8)
        result = compute_project_construction_cashflow(
            "p-001", records, self.START, self.END, assumptions
        )
        for period in result.periods:
            assert period.variance_to_plan == pytest.approx(
                period.expected_cost - period.planned_cost, abs=0.01
            )

    def test_cumulative_cost_is_monotonically_non_decreasing(self):
        """cumulative_cost must never decrease across periods."""
        records = [_record(1_200_000.0, 0.0, date(2026, 1, 1), date(2026, 12, 31))]
        result = compute_project_construction_cashflow("p-001", records, self.START, self.END)
        cumulative = [p.cumulative_cost for p in result.periods]
        for i in range(1, len(cumulative)):
            assert cumulative[i] >= cumulative[i - 1]

    def test_cumulative_cost_final_equals_expected_total(self):
        """The last period's cumulative_cost equals summary.expected_total."""
        records = [_record(1_200_000.0, 0.0, date(2026, 1, 1), date(2026, 12, 31))]
        result = compute_project_construction_cashflow("p-001", records, self.START, self.END)
        assert result.periods[-1].cumulative_cost == pytest.approx(result.summary.expected_total)

    def test_cost_item_count_reflects_contributing_records(self):
        """cost_item_count reflects the number of records contributing to each bucket."""
        records = [
            _record(600_000.0, 0.0, date(2026, 1, 1), date(2026, 6, 30), category="structural"),
            _record(600_000.0, 0.0, date(2026, 1, 1), date(2026, 6, 30), category="finishing"),
        ]
        result = compute_project_construction_cashflow(
            "p-001", records, date(2026, 1, 1), date(2026, 6, 30)
        )
        for period in result.periods:
            assert period.cost_item_count == 2

    def test_multi_category_aggregation_within_period(self):
        """Multiple cost categories sum correctly within the same period."""
        records = [
            _record(600_000.0, 0.0, date(2026, 1, 1), date(2026, 6, 30), category="structural"),
            _record(600_000.0, 0.0, date(2026, 1, 1), date(2026, 6, 30), category="finishing"),
        ]
        result = compute_project_construction_cashflow(
            "p-001", records, date(2026, 1, 1), date(2026, 6, 30)
        )
        # Each record: 600_000 / 6 = 100_000/month. Total = 200_000/month.
        for period in result.periods:
            assert period.planned_cost == pytest.approx(200_000.0)

    def test_single_month_execution_window(self):
        """A record executing in a single month places its full amount in that bucket."""
        records = [_record(300_000.0, 0.0, date(2026, 3, 1), date(2026, 3, 31))]
        result = compute_project_construction_cashflow(
            "p-001", records, date(2026, 1, 1), date(2026, 6, 30)
        )
        mar = next(p for p in result.periods if p.period_label == "2026-03")
        assert mar.planned_cost == pytest.approx(300_000.0)
        assert mar.cost_item_count == 1
        # Other months should have zero cost
        other_months = [p for p in result.periods if p.period_label != "2026-03"]
        for period in other_months:
            assert period.planned_cost == pytest.approx(0.0)

    def test_invalid_date_window_raises_value_error(self):
        """start_date > end_date raises ValueError."""
        with pytest.raises(ValueError, match="start_date"):
            compute_project_construction_cashflow(
                "p-001", [], date(2026, 6, 1), date(2026, 1, 1)
            )

    def test_summary_planned_total_equals_sum_of_period_planned(self):
        """summary.planned_total == sum of all period planned_cost values."""
        records = [_record(1_200_000.0, 0.0, date(2026, 1, 1), date(2026, 12, 31))]
        result = compute_project_construction_cashflow("p-001", records, self.START, self.END)
        assert result.summary.planned_total == pytest.approx(
            sum(p.planned_cost for p in result.periods)
        )

    def test_summary_expected_total_equals_sum_of_period_expected(self):
        """summary.expected_total == sum of all period expected_cost values."""
        records = [_record(1_200_000.0, 0.0, date(2026, 1, 1), date(2026, 12, 31))]
        assumptions = ConstructionForecastAssumptions(execution_probability=0.75)
        result = compute_project_construction_cashflow(
            "p-001", records, self.START, self.END, assumptions
        )
        assert result.summary.expected_total == pytest.approx(
            sum(p.expected_cost for p in result.periods)
        )


class TestComputePhaseConstructionCashflow:
    """Tests for compute_phase_construction_cashflow — pure calculations, no DB."""

    START = date(2026, 1, 1)
    END = date(2026, 6, 30)

    def test_phase_scope_type_and_id(self):
        result = compute_phase_construction_cashflow("ph-001", [], self.START, self.END)
        assert result.scope_type == "phase"
        assert result.scope_id == "ph-001"

    def test_phase_forecast_matches_project_for_same_records(self):
        """Phase and project engines produce identical numbers for the same records."""
        records = [_record(600_000.0, 0.0, date(2026, 1, 1), date(2026, 6, 30))]
        phase_result = compute_phase_construction_cashflow(
            "ph-001", records, self.START, self.END
        )
        project_result = compute_project_construction_cashflow(
            "p-001", records, self.START, self.END
        )
        for pp, pr in zip(phase_result.periods, project_result.periods):
            assert pp.planned_cost == pytest.approx(pr.planned_cost)
            assert pp.expected_cost == pytest.approx(pr.expected_cost)

    def test_phase_invalid_date_window_raises(self):
        with pytest.raises(ValueError, match="start_date"):
            compute_phase_construction_cashflow(
                "ph-001", [], date(2026, 6, 1), date(2026, 1, 1)
            )


class TestComputePortfolioConstructionCashflow:
    """Tests for compute_portfolio_construction_cashflow — pure calculations, no DB."""

    START = date(2026, 1, 1)
    END = date(2026, 6, 30)

    def test_empty_portfolio_returns_zero_periods(self):
        result = compute_portfolio_construction_cashflow({}, self.START, self.END)
        assert result.scope_type == "portfolio"
        assert result.summary.planned_total == 0.0
        assert result.summary.expected_total == 0.0
        assert len(result.project_forecasts) == 0

    def test_portfolio_totals_equal_sum_of_project_totals(self):
        """Portfolio period totals must equal the sum of all project period totals."""
        project_records = {
            "p-001": [_record(600_000.0, 0.0, date(2026, 1, 1), date(2026, 6, 30))],
            "p-002": [_record(1_200_000.0, 0.0, date(2026, 1, 1), date(2026, 6, 30))],
        }
        result = compute_portfolio_construction_cashflow(
            project_records, self.START, self.END
        )
        for period in result.periods:
            label = period.period_label
            project_sum = sum(
                next(p for p in pf.periods if p.period_label == label).planned_cost
                for pf in result.project_forecasts
            )
            assert period.planned_cost == pytest.approx(project_sum)

    def test_portfolio_project_forecasts_sorted_by_project_id(self):
        """Project forecasts must be sorted by project_id for determinism."""
        project_records = {
            "p-003": [_record(100_000.0, 0.0, date(2026, 1, 1), date(2026, 1, 31))],
            "p-001": [_record(200_000.0, 0.0, date(2026, 1, 1), date(2026, 1, 31))],
            "p-002": [_record(300_000.0, 0.0, date(2026, 1, 1), date(2026, 1, 31))],
        }
        result = compute_portfolio_construction_cashflow(
            project_records, self.START, self.END
        )
        ids = [pf.scope_id for pf in result.project_forecasts]
        assert ids == sorted(ids)

    def test_portfolio_invalid_date_window_raises(self):
        with pytest.raises(ValueError, match="start_date"):
            compute_portfolio_construction_cashflow(
                {}, date(2026, 6, 1), date(2026, 1, 1)
            )

    def test_portfolio_cumulative_is_non_decreasing(self):
        project_records = {
            "p-001": [_record(1_200_000.0, 0.0, date(2026, 1, 1), date(2026, 6, 30))],
        }
        result = compute_portfolio_construction_cashflow(
            project_records, self.START, self.END
        )
        cumulative = [p.cumulative_cost for p in result.periods]
        for i in range(1, len(cumulative)):
            assert cumulative[i] >= cumulative[i - 1]

    def test_portfolio_summary_equals_sum_of_periods(self):
        project_records = {
            "p-001": [_record(1_200_000.0, 0.0, date(2026, 1, 1), date(2026, 6, 30))],
            "p-002": [_record(600_000.0, 0.0, date(2026, 3, 1), date(2026, 6, 30))],
        }
        result = compute_portfolio_construction_cashflow(
            project_records, self.START, self.END
        )
        assert result.summary.planned_total == pytest.approx(
            sum(p.planned_cost for p in result.periods)
        )
        assert result.summary.expected_total == pytest.approx(
            sum(p.expected_cost for p in result.periods)
        )


# ---------------------------------------------------------------------------
# Service-layer unit tests — mocked DB
# ---------------------------------------------------------------------------


class TestCashflowServiceConstruction:
    """Service-layer tests using mocked DB sessions."""

    def _make_service(self, project_exists: bool = True, phase_exists: bool = True):
        """Create a CashflowForecastService backed by a mock DB."""
        db = MagicMock()

        mock_project = MagicMock()
        mock_phase = MagicMock()

        project_query = MagicMock()
        project_query.filter.return_value.first.return_value = (
            mock_project if project_exists else None
        )

        phase_query = MagicMock()
        phase_query.filter.return_value.first.return_value = (
            mock_phase if phase_exists else None
        )

        def _query_side_effect(model):
            if model is Project:
                return project_query
            if model is Phase:
                return phase_query
            return MagicMock()

        db.query.side_effect = _query_side_effect
        return CashflowForecastService(db)

    def test_get_project_construction_forecast_returns_correct_schema(self):
        service = self._make_service(project_exists=True)
        result = service.get_project_construction_forecast(
            "p-001", date(2026, 1, 1), date(2026, 6, 30)
        )
        assert result.scope_type == "project"
        assert result.project_id == "p-001"
        assert result.granularity == "monthly"
        assert len(result.periods) == 6

    def test_get_project_construction_forecast_raises_404_for_unknown_project(self):
        service = self._make_service(project_exists=False)
        with pytest.raises(ResourceNotFoundError):
            service.get_project_construction_forecast(
                "missing", date(2026, 1, 1), date(2026, 6, 30)
            )

    def test_get_project_construction_forecast_raises_422_for_inverted_window(self):
        service = self._make_service(project_exists=True)
        with pytest.raises(ValidationError):
            service.get_project_construction_forecast(
                "p-001", date(2026, 6, 1), date(2026, 1, 1)
            )

    def test_get_phase_construction_forecast_returns_correct_schema(self):
        service = self._make_service(phase_exists=True)
        result = service.get_phase_construction_forecast(
            "ph-001", date(2026, 1, 1), date(2026, 3, 31)
        )
        assert result.scope_type == "phase"
        assert result.phase_id == "ph-001"
        assert len(result.periods) == 3

    def test_get_phase_construction_forecast_raises_404_for_unknown_phase(self):
        service = self._make_service(phase_exists=False)
        with pytest.raises(ResourceNotFoundError):
            service.get_phase_construction_forecast(
                "missing", date(2026, 1, 1), date(2026, 3, 31)
            )

    def test_get_phase_construction_forecast_raises_422_for_inverted_window(self):
        service = self._make_service(phase_exists=True)
        with pytest.raises(ValidationError):
            service.get_phase_construction_forecast(
                "ph-001", date(2026, 6, 1), date(2026, 1, 1)
            )

    def test_get_portfolio_construction_forecast_returns_correct_schema(self):
        db = MagicMock()
        service = CashflowForecastService(db)
        result = service.get_portfolio_construction_forecast(
            date(2026, 1, 1), date(2026, 3, 31)
        )
        assert result.scope_type == "portfolio"
        assert len(result.periods) == 3

    def test_get_portfolio_construction_forecast_raises_422_for_inverted_window(self):
        db = MagicMock()
        service = CashflowForecastService(db)
        with pytest.raises(ValidationError):
            service.get_portfolio_construction_forecast(
                date(2026, 6, 1), date(2026, 1, 1)
            )

    def test_assumptions_schema_respected_in_project_forecast(self):
        service = self._make_service(project_exists=True)
        assumptions = ConstructionForecastAssumptionsSchema(
            execution_probability=0.5, spread_method="linear", include_committed=False
        )
        result = service.get_project_construction_forecast(
            "p-001", date(2026, 1, 1), date(2026, 3, 31), assumptions
        )
        assert result.assumptions.execution_probability == pytest.approx(0.5)
        assert result.assumptions.include_committed is False


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


class TestConstructionCashflowAPIEndpoints:
    """API-level tests via the test client."""

    START = "2026-01-01"
    END = "2026-06-30"

    def _url_project(self, project_id: str) -> str:
        return f"/api/v1/finance/projects/{project_id}/construction-cashflow"

    def _url_phase(self, phase_id: str) -> str:
        return f"/api/v1/finance/phases/{phase_id}/construction-cashflow"

    def _url_portfolio(self) -> str:
        return "/api/v1/finance/portfolio/construction-cashflow"

    def test_project_endpoint_returns_200(self, client, db_session):
        project = Project(name="Test Project API CC", code="CCAPI001")
        db_session.add(project)
        db_session.commit()

        resp = client.get(
            self._url_project(project.id),
            params={"start_date": self.START, "end_date": self.END},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["scope_type"] == "project"
        assert body["project_id"] == project.id
        assert body["granularity"] == "monthly"
        assert len(body["periods"]) == 6

    def test_project_endpoint_returns_404_for_unknown_project(self, client):
        resp = client.get(
            self._url_project("nonexistent-project-id"),
            params={"start_date": self.START, "end_date": self.END},
        )
        assert resp.status_code == 404

    def test_project_endpoint_returns_422_for_inverted_window(self, client, db_session):
        project = Project(name="Test Project CC 422", code="CCAPI422")
        db_session.add(project)
        db_session.commit()

        resp = client.get(
            self._url_project(project.id),
            params={"start_date": self.END, "end_date": self.START},
        )
        assert resp.status_code == 422

    def test_phase_endpoint_returns_200(self, client, db_session):
        project = Project(name="Test Phase CC Project", code="CCPH001")
        db_session.add(project)
        db_session.flush()

        phase = Phase(project_id=project.id, name="Phase A", sequence=1)
        db_session.add(phase)
        db_session.commit()

        resp = client.get(
            self._url_phase(phase.id),
            params={"start_date": self.START, "end_date": self.END},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["scope_type"] == "phase"
        assert body["phase_id"] == phase.id

    def test_phase_endpoint_returns_404_for_unknown_phase(self, client):
        resp = client.get(
            self._url_phase("nonexistent-phase-id"),
            params={"start_date": self.START, "end_date": self.END},
        )
        assert resp.status_code == 404

    def test_portfolio_endpoint_returns_200(self, client):
        resp = client.get(
            self._url_portfolio(),
            params={"start_date": self.START, "end_date": self.END},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["scope_type"] == "portfolio"
        assert body["granularity"] == "monthly"
        assert len(body["periods"]) == 6

    def test_portfolio_endpoint_returns_422_for_inverted_window(self, client):
        resp = client.get(
            self._url_portfolio(),
            params={"start_date": self.END, "end_date": self.START},
        )
        assert resp.status_code == 422

    def test_execution_probability_param_propagated(self, client, db_session):
        project = Project(name="Test Project EP", code="CCEP001")
        db_session.add(project)
        db_session.commit()

        resp = client.get(
            self._url_project(project.id),
            params={
                "start_date": self.START,
                "end_date": self.END,
                "execution_probability": "0.5",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["assumptions"]["execution_probability"] == pytest.approx(0.5)

    def test_include_committed_false_param_propagated(self, client, db_session):
        project = Project(name="Test Project IC", code="CCIC001")
        db_session.add(project)
        db_session.commit()

        resp = client.get(
            self._url_project(project.id),
            params={
                "start_date": self.START,
                "end_date": self.END,
                "include_committed": "false",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["assumptions"]["include_committed"] is False

    def test_portfolio_response_contains_summary_fields(self, client):
        resp = client.get(
            self._url_portfolio(),
            params={"start_date": self.START, "end_date": self.END},
        )
        assert resp.status_code == 200
        body = resp.json()
        summary = body["summary"]
        assert "planned_total" in summary
        assert "expected_total" in summary
        assert "variance_to_plan" in summary
