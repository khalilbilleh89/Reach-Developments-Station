"""The monthly bridge, and the two balances it keeps apart.

Opening plus inflows less outflows is closing, and next month opens where this
one closed. Nothing is stored: a running balance column is a number that can
disagree with the transactions beneath it, and the first time it does nobody
knows which is wrong.

The second bridge is the one a total cash balance cannot answer. Received and
usable are different numbers, and a developer paying a contractor out of
escrowed buyer money has a problem no total will show.
"""

from __future__ import annotations

from datetime import date
from itertools import pairwise

import pytest
from fastapi.testclient import TestClient

from tests.modules.conftest import (
    cashflow_monthly,
    cashflow_summary,
    cashflow_url,
    confirm_receipt,
    create_cashflow_forecast,
    govern_cashflow_forecast,
    month_named,
    pay_construction,
    record_development,
    record_financing,
    record_receipt,
    refund_buyer,
    restrict_receipt,
)


def month_row(monthly: dict[str, object], month: str) -> dict[str, str]:
    months = monthly["months"]
    assert isinstance(months, list)
    row = next((entry for entry in months if entry["period_month"] == month), None)
    assert row is not None, f"{month} is missing from a series that must have no gaps"
    return row


def confirm_movement(client: TestClient, project_id: str, kind: str, movement_id: str) -> None:
    response = client.post(
        f"{cashflow_url(project_id)}/{kind}-movements/{movement_id}/confirm", json={}
    )
    assert response.status_code == 200, response.text


@pytest.fixture
def opening_forecast(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    flat_construction_forecast: str,
) -> str:
    """A forecast in force, opening at 1,000 usable and 200 restricted.

    In force rather than draft, because the opening balance is a property of the
    governed statement: with no forecast activated the project has never said
    where its cash history begins, and the bridge honestly opens at zero. Pinned
    to a construction forecast with nothing left to spend, so the months carry
    the transactions this family is about and not a build schedule.
    """
    created = create_cashflow_forecast(
        finance_client,
        project_id,
        opening_unrestricted_cash="1000.00",
        opening_restricted_cash="200.00",
        forecast_start_month=month_named(0),
        forecast_end_month=month_named(3),
    )
    assert created.status_code == 201, created.text
    identifier: str = created.json()["id"]
    activated = govern_cashflow_forecast(finance_client, cfo_client, project_id, identifier)
    assert activated.status_code == 200, activated.text
    return identifier


class TestTheBridge:
    def test_a_month_of_real_transactions_closes_where_the_arithmetic_says(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        collections_client: TestClient,
        sales_ops_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        currency_id: str,
        active_contract: str,
        certified_certificate: str,
        collecting_sale: str,
        opening_forecast: str,
    ) -> None:
        """Given / When / Then: five real movements, one exact closing balance.

        Opening usable 1,000. In: a 500 buyer receipt and 300 of equity. Out: 700
        of construction cash, 200 of consultants and a 50 refund. The month moves
        usable cash by -150 and closes at 850, and every figure is a transaction
        somebody confirmed rather than a number typed into a forecast.
        """
        today = date.today().isoformat()
        receipt = record_receipt(
            collections_client, project_id, collecting_sale, "500.00", receipt_date=today
        )
        assert receipt.status_code == 201, receipt.text
        assert confirm_receipt(finance_client, project_id, receipt.json()["id"]).status_code == 200

        equity = record_financing(
            finance_client, project_id, currency_id, amount="300.00", movement_date=today
        )
        assert equity.status_code == 201, equity.text
        confirm_movement(second_finance_client, project_id, "financing", equity.json()["id"])

        pay_construction(
            finance_client,
            second_finance_client,
            project_id,
            active_contract,
            currency_id,
            certified_certificate,
            amount="700.00",
            payment_date=today,
        )

        consultants = record_development(
            finance_client, project_id, currency_id, amount="200.00", movement_date=today
        )
        assert consultants.status_code == 201, consultants.text
        confirm_movement(second_finance_client, project_id, "development", consultants.json()["id"])

        refund_buyer(
            sales_ops_client,
            cfo_client,
            collections_client,
            finance_client,
            project_id,
            collecting_sale,
            amount="50.00",
            refund_date=today,
        )

        row = month_row(cashflow_monthly(finance_client, project_id), month_named(0))
        assert row["basis"] == "actual"
        assert row["opening_total_cash"] == "1200.00"
        assert row["customer_actual_receipts"] == "500.00"
        assert row["financing_actual_inflows"] == "300.00"
        assert row["construction_actual_payments"] == "700.00"
        assert row["development_actual_outflows"] == "200.00"
        assert row["customer_refunds"] == "50.00"
        assert row["total_inflows"] == "800.00"
        assert row["total_outflows"] == "950.00"
        assert row["net_cashflow"] == "-150.00"
        assert row["closing_total_cash"] == "1050.00"
        assert row["opening_unrestricted_cash"] == "1000.00"
        assert row["closing_unrestricted_cash"] == "850.00"

    def test_every_month_appears_even_when_nothing_happened(
        self, finance_client: TestClient, project_id: str, opening_forecast: str
    ) -> None:
        """A quiet quarter that vanished would make a chart lie about elapsed time."""
        monthly = cashflow_monthly(finance_client, project_id)
        months = [row["period_month"] for row in monthly["months"]]
        assert months == sorted(months)
        for offset in range(0, 4):
            assert month_named(offset) in months

    def test_a_month_opens_exactly_where_the_last_one_closed(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        currency_id: str,
        opening_forecast: str,
    ) -> None:
        movement = record_development(finance_client, project_id, currency_id, amount="150.00")
        confirm_movement(second_finance_client, project_id, "development", movement.json()["id"])
        months = cashflow_monthly(finance_client, project_id)["months"]
        for earlier, later in pairwise(months):
            assert later["opening_total_cash"] == earlier["closing_total_cash"], (
                f"{later['period_month']} does not open where {earlier['period_month']} closed"
            )

    def test_a_month_is_labelled_actual_or_forecast_in_words(
        self, finance_client: TestClient, project_id: str, opening_forecast: str
    ) -> None:
        """Never colour alone. A reader who cannot see two shades still needs to know."""
        months = cashflow_monthly(finance_client, project_id)["months"]
        assert month_row({"months": months}, month_named(0))["basis"] == "actual"
        assert month_row({"months": months}, month_named(2))["basis"] == "forecast"


class TestRestrictedAndUsableAreDifferentNumbers:
    def test_restricting_part_of_a_receipt_leaves_total_cash_alone(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        opening_forecast: str,
    ) -> None:
        """100 arrives, 80 is held back. Total +100, restricted +80, usable +20."""
        today = date.today().isoformat()
        receipt = record_receipt(
            collections_client, project_id, collecting_sale, "100.00", receipt_date=today
        )
        receipt_id = receipt.json()["id"]
        confirm_receipt(finance_client, project_id, receipt_id)

        restriction = restrict_receipt(
            finance_client, project_id, receipt_id, restricted_amount="80.00"
        )
        assert restriction.status_code == 201, restriction.text
        confirmed = second_finance_client.post(
            f"{cashflow_url(project_id)}/restrictions/{restriction.json()['id']}/confirm",
            json={},
        )
        assert confirmed.status_code == 200, confirmed.text

        row = month_row(cashflow_monthly(finance_client, project_id), month_named(0))
        assert row["closing_total_cash"] == "1300.00"
        assert row["newly_restricted_customer_cash"] == "80.00"
        assert row["closing_restricted_cash"] == "280.00"
        assert row["closing_unrestricted_cash"] == "1020.00"

    def test_the_summary_reports_all_three_balances(
        self, finance_client: TestClient, project_id: str, opening_forecast: str
    ) -> None:
        """Nobody should have to subtract two numbers to learn what they can spend."""
        summary = cashflow_summary(finance_client, project_id)
        position = summary["position"]
        assert position["total_cash"] == "1200.00"
        assert position["restricted_cash"] == "200.00"
        assert position["unrestricted_cash"] == "1000.00"


class TestFundingIsMeasuredOnUsableCash:
    def test_a_project_short_of_usable_cash_reports_a_gap(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        currency_id: str,
        opening_forecast: str,
    ) -> None:
        """1,000 usable, 1,400 spent. The gap is 400 however healthy the escrow."""
        movement = record_development(finance_client, project_id, currency_id, amount="1400.00")
        confirm_movement(second_finance_client, project_id, "development", movement.json()["id"])
        row = month_row(cashflow_monthly(finance_client, project_id), month_named(0))
        assert row["closing_unrestricted_cash"] == "-400.00"
        assert row["funding_gap"] == "400.00"
        assert row["closing_restricted_cash"] == "200.00"

    def test_the_peak_deficit_names_the_month_and_both_numbers(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        currency_id: str,
        opening_forecast: str,
    ) -> None:
        movement = record_development(finance_client, project_id, currency_id, amount="1750.00")
        confirm_movement(second_finance_client, project_id, "development", movement.json()["id"])
        peak = cashflow_summary(finance_client, project_id)["peak_deficit"]
        assert peak["minimum_unrestricted_cash"] == "-750.00"
        assert peak["peak_funding_deficit"] == "750.00"
        assert peak["peak_deficit_month"] == month_named(0)

    def test_a_project_that_never_runs_short_names_no_month(
        self, finance_client: TestClient, project_id: str, opening_forecast: str
    ) -> None:
        """Naming the least comfortable month anyway would read as a warning."""
        peak = cashflow_summary(finance_client, project_id)["peak_deficit"]
        assert peak["peak_funding_deficit"] == "0.00"
        assert peak["peak_deficit_month"] is None
