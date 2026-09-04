"""How wrong the last forecast was, month by month and group by group.

No blended accuracy score. Customer collections running 20% ahead and
construction running 20% behind would average into a project on plan, and the
two facts a reader needs are the two the average destroys.

The rate is null where nothing was forecast. A percentage against zero is
undefined, and "we forecast nothing and spent 40,000" is a complete sentence
without one.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.modules.cashflow import calculator
from tests.modules.conftest import (
    cashflow_url,
    create_cashflow_forecast,
    govern_cashflow_forecast,
    month_named,
)


class TestTheVarianceArithmetic:
    def test_more_spent_than_forecast_is_a_positive_variance(self) -> None:
        """Given / When / Then: forecast 100, actual 120, variance +20 and +20%."""
        variance = calculator.forecast_variance(
            forecast_amount=Decimal("100.00"), actual_amount=Decimal("120.00")
        )
        assert variance.variance_amount == Decimal("20.00")
        assert variance.variance_rate == Decimal("0.200000")

    def test_less_spent_than_forecast_is_negative(self) -> None:
        variance = calculator.forecast_variance(
            forecast_amount=Decimal("100.00"), actual_amount=Decimal("80.00")
        )
        assert variance.variance_amount == Decimal("-20.00")
        assert variance.variance_rate == Decimal("-0.200000")

    def test_a_zero_forecast_keeps_the_amount_and_drops_the_rate(self) -> None:
        """A percentage against nothing is undefined; the amount is not."""
        variance = calculator.forecast_variance(
            forecast_amount=Decimal("0.00"), actual_amount=Decimal("40.00")
        )
        assert variance.variance_amount == Decimal("40.00")
        assert variance.variance_rate is None

    def test_an_exact_forecast_reports_zero_rather_than_nothing(self) -> None:
        variance = calculator.forecast_variance(
            forecast_amount=Decimal("100.00"), actual_amount=Decimal("100.00")
        )
        assert variance.variance_amount == Decimal("0.00")
        assert variance.variance_rate == Decimal("0.000000")


@pytest.fixture
def governed_forecast(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    cost_codes: dict[str, str],
    flat_construction_forecast: str,
) -> str:
    """A forecast taken last month, so there is something to measure it against.

    Accuracy compares a *prior* forecast to what has happened since. A version
    taken this morning has no finished month behind it and nothing to be right or
    wrong about, and a report that answered anyway would be measuring a forecast
    against the hours since it was written.
    """
    created = create_cashflow_forecast(
        finance_client,
        project_id,
        as_of_date=month_named(-1),
        forecast_start_month=month_named(-1),
        forecast_end_month=month_named(3),
    )
    identifier: str = created.json()["id"]
    assert (
        govern_cashflow_forecast(
            finance_client, cfo_client, project_id, identifier, cost_codes=cost_codes
        ).status_code
        == 200
    )
    return identifier


class TestTheReport:
    def test_it_states_which_forecast_it_measured(
        self, finance_client: TestClient, project_id: str, governed_forecast: str
    ) -> None:
        body = finance_client.get(f"{cashflow_url(project_id)}/forecast-accuracy").json()
        assert body["basis"]["forecast_version_number"] == 1
        assert body["basis"]["forecast_as_of_date"]

    def test_it_reports_groups_rather_than_one_score(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        currency_id: str,
        governed_forecast: str,
    ) -> None:
        """Customer ahead and construction behind must not cancel out."""
        from tests.modules.conftest import record_development

        movement = record_development(finance_client, project_id, currency_id)
        second_finance_client.post(
            f"{cashflow_url(project_id)}/development-movements/{movement.json()['id']}/confirm",
            json={},
        )
        body = finance_client.get(f"{cashflow_url(project_id)}/forecast-accuracy").json()
        assert "score" not in body
        groups = {row["category_group"] for row in body["rows"]}
        assert "development_outflow" in groups

    def test_an_unforecast_actual_is_reported_with_a_null_rate(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        currency_id: str,
        governed_forecast: str,
    ) -> None:
        """Nothing was forecast for consultants, and 50,000 was spent."""
        from tests.modules.conftest import record_development

        movement = record_development(
            finance_client,
            project_id,
            currency_id,
            movement_date=date.today().isoformat(),
        )
        second_finance_client.post(
            f"{cashflow_url(project_id)}/development-movements/{movement.json()['id']}/confirm",
            json={},
        )
        body = finance_client.get(f"{cashflow_url(project_id)}/forecast-accuracy").json()
        row = next(
            row
            for row in body["rows"]
            if row["category_group"] == "development_outflow"
            and row["period_month"] == month_named(0)
        )
        assert row["variance"]["forecast_amount"] == "0.00"
        assert row["variance"]["actual_amount"] == "50000.00"
        assert row["variance"]["variance_amount"] == "50000.00"
        assert row["variance"]["variance_rate"] is None

    def test_a_month_that_has_not_finished_is_not_measured_beyond_today(
        self, finance_client: TestClient, project_id: str, governed_forecast: str
    ) -> None:
        """Calling a project behind plan because the month is still running."""
        body = finance_client.get(f"{cashflow_url(project_id)}/forecast-accuracy").json()
        current = month_named(0)
        assert all(row["period_month"] <= current for row in body["rows"])
