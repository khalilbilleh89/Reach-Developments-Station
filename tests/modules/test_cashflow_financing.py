"""Equity and debt cash, and the sign that flips between two readers.

The project and the investor see the same transaction from opposite sides. An
equity contribution is cash the project received and cash the investor paid out.
Reporting the project's direction into an IRR gives the right magnitude with the
wrong sign, which is the single easiest way to present a loss as a return — so
the transformation is proved here explicitly rather than left to be read out of
the calculator.

The other boundary this family holds is what counts as financing cash at all. A
facility signed is not a drawdown and a guarantee issued is not cash posted;
instruments that never moved money have no row here and appear in no position.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.modules.conftest import (
    cashflow_monthly,
    cashflow_summary,
    cashflow_url,
    create_cashflow_forecast,
    govern_cashflow_forecast,
    month_named,
    record_financing,
)


def confirm(client: TestClient, project_id: str, movement_id: str) -> None:
    response = client.post(
        f"{cashflow_url(project_id)}/financing-movements/{movement_id}/confirm", json={}
    )
    assert response.status_code == 200, response.text


def month_row(monthly: dict[str, object], month: str) -> dict[str, str]:
    months = monthly["months"]
    assert isinstance(months, list)
    return next(entry for entry in months if entry["period_month"] == month)


@pytest.fixture
def cash_forecast(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    cost_codes: dict[str, str],
    flat_construction_forecast: str,
) -> str:
    created = create_cashflow_forecast(
        finance_client,
        project_id,
        forecast_start_month=month_named(-1),
        forecast_end_month=month_named(2),
    )
    assert created.status_code == 201, created.text
    identifier: str = created.json()["id"]
    assert (
        govern_cashflow_forecast(
            finance_client, cfo_client, project_id, identifier, cost_codes=cost_codes
        ).status_code
        == 200
    )
    return identifier


class TestDirectionFollowsFromType:
    def test_an_equity_contribution_is_cash_in(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        currency_id: str,
        cash_forecast: str,
    ) -> None:
        movement = record_financing(finance_client, project_id, currency_id, amount="1000000.00")
        assert movement.status_code == 201, movement.text
        assert movement.json()["flow_direction"] == "inflow"
        confirm(second_finance_client, project_id, movement.json()["id"])

        row = month_row(cashflow_monthly(finance_client, project_id), month_named(0))
        assert row["financing_actual_inflows"] == "1000000.00"
        assert row["total_inflows"] == "1000000.00"

    def test_an_equity_distribution_is_cash_out(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        currency_id: str,
        cash_forecast: str,
    ) -> None:
        movement = record_financing(
            finance_client,
            project_id,
            currency_id,
            movement_type="equity_distribution",
            amount="1400000.00",
        )
        assert movement.json()["flow_direction"] == "outflow"
        confirm(second_finance_client, project_id, movement.json()["id"])

        row = month_row(cashflow_monthly(finance_client, project_id), month_named(0))
        assert row["financing_actual_outflows"] == "1400000.00"

    def test_every_financing_type_carries_a_fixed_direction(self) -> None:
        """A direction on a form is a direction somebody can get wrong."""
        from app.modules.cashflow.models import (
            FINANCING_INFLOW_TYPES,
            FINANCING_OUTFLOW_TYPES,
        )

        assert "equity_contribution" in FINANCING_INFLOW_TYPES
        assert "debt_drawdown" in FINANCING_INFLOW_TYPES
        assert "equity_distribution" in FINANCING_OUTFLOW_TYPES
        assert "interest_payment" in FINANCING_OUTFLOW_TYPES
        assert not set(FINANCING_INFLOW_TYPES) & set(FINANCING_OUTFLOW_TYPES)


class TestTheInvestorSeesTheOppositeSign:
    def test_a_contribution_is_negative_equity_cashflow(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        currency_id: str,
        cash_forecast: str,
    ) -> None:
        """Given / When / Then: project +1,000,000, investor -1,000,000."""
        movement = record_financing(finance_client, project_id, currency_id, amount="1000000.00")
        confirm(second_finance_client, project_id, movement.json()["id"])

        returns = cashflow_summary(finance_client, project_id)["returns"]
        assert returns["equity_contributed"] == "1000000.00"
        assert returns["equity_net"] == "-1000000.00"
        assert returns["equity_irr_basis"] == "equity_investor_sign_convention"

    def test_a_distribution_is_positive_equity_cashflow(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        currency_id: str,
        cash_forecast: str,
    ) -> None:
        """Project -1,400,000 out; the investor received it."""
        contribution = record_financing(
            finance_client, project_id, currency_id, amount="1000000.00"
        )
        confirm(second_finance_client, project_id, contribution.json()["id"])
        distribution = record_financing(
            finance_client,
            project_id,
            currency_id,
            movement_type="equity_distribution",
            amount="1400000.00",
        )
        confirm(second_finance_client, project_id, distribution.json()["id"])

        returns = cashflow_summary(finance_client, project_id)["returns"]
        assert returns["equity_contributed"] == "1000000.00"
        assert returns["equity_distributed"] == "1400000.00"
        assert returns["equity_net"] == "400000.00"


class TestIrrRefusesRatherThanGuesses:
    def test_with_no_investment_there_is_no_return_to_state(
        self, finance_client: TestClient, project_id: str, cash_forecast: str
    ) -> None:
        """Never 0%, never 999%, never NaN. Each is a number for a board pack."""
        returns = cashflow_summary(finance_client, project_id)["returns"]
        assert returns["equity_irr_per_period"] is None
        assert returns["equity_irr_unavailable_reason"] == "no_negative_equity_cashflow"

    def test_with_no_distribution_the_reason_says_so(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        currency_id: str,
        cash_forecast: str,
    ) -> None:
        movement = record_financing(finance_client, project_id, currency_id, amount="1000000.00")
        confirm(second_finance_client, project_id, movement.json()["id"])
        returns = cashflow_summary(finance_client, project_id)["returns"]
        assert returns["equity_irr_per_period"] is None
        assert returns["equity_irr_unavailable_reason"] == "no_positive_equity_cashflow"

    def test_irr_never_appears_without_absolute_figures_beside_it(
        self, finance_client: TestClient, project_id: str, cash_forecast: str
    ) -> None:
        """A percentage with no cash behind it is a number nobody can check."""
        returns = cashflow_summary(finance_client, project_id)["returns"]
        for field in (
            "net_present_value",
            "net_project_cashflow",
            "equity_contributed",
            "equity_distributed",
            "equity_net",
        ):
            assert field in returns


class TestOnlyCashIsRecorded:
    def test_a_movement_in_another_currency_is_refused(
        self,
        finance_client: TestClient,
        admin_client: TestClient,
        project_id: str,
        cash_forecast: str,
    ) -> None:
        """No exchange rate exists in this MVP, so converting would invent the amount."""
        from tests.modules.conftest import SETTINGS

        other = admin_client.post(
            f"{SETTINGS}/currencies",
            json={"code": "EUR", "name": "Euro", "minor_units": 2},
        )
        assert other.status_code in {200, 201, 409}, other.text
        currencies = admin_client.get(f"{SETTINGS}/currencies").json()
        euro = next(row for row in currencies if row["code"] == "EUR")

        refused = record_financing(finance_client, project_id, euro["id"])
        assert refused.status_code == 422, refused.text

    def test_a_negative_amount_is_refused(
        self,
        finance_client: TestClient,
        project_id: str,
        currency_id: str,
        cash_forecast: str,
    ) -> None:
        """Direction is a column, not a sign somebody buries in an amount."""
        refused = record_financing(finance_client, project_id, currency_id, amount="-1000.00")
        assert refused.status_code == 422, refused.text
