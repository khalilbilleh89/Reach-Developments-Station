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

from datetime import date, timedelta
from decimal import Decimal
from itertools import pairwise

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.modules.conftest import (
    at,
    backdate,
    cashflow_monthly,
    cashflow_summary,
    cashflow_url,
    confirm_receipt,
    contract_basis,
    create_cashflow_forecast,
    current_version_id,
    fixed_row,
    govern_cashflow_forecast,
    month_named,
    pay_construction,
    plans_url,
    record_development,
    record_financing,
    record_receipt,
    refund_buyer,
    restrict_receipt,
    set_cashflow_line,
    write_schedule,
)


def month_row(monthly: dict[str, object], month: str) -> dict[str, str]:
    months = monthly["months"]
    assert isinstance(months, list)
    row = next((entry for entry in months if entry["period_month"] == month), None)
    assert row is not None, f"{month} is missing from a series that must have no gaps"
    return row


def next_month_start(month: date) -> date:
    if month.month == 12:
        return date(month.year + 1, 1, 1)
    return date(month.year, month.month + 1, 1)


def end_of_this_month() -> str:
    """The last day of the month today falls in.

    Chosen so a test about "later this month" holds on every calendar day: the
    first of a month is always before its last, whatever today happens to be.
    """
    first = date.today().replace(day=1)
    return (next_month_start(first) - timedelta(days=1)).isoformat()


def one_instalment_due(
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    plan_id: str,
    *,
    due: str,
) -> Decimal:
    """Put the whole buyer schedule on one instalment and govern it.

    Returns what that instalment is worth, so an assertion is stated against the
    contract this project has rather than a figure copied into the test.
    """
    version_id = current_version_id(collections_client, project_id, plan_id)
    written = write_schedule(
        collections_client, project_id, plan_id, version_id, [fixed_row(1, "1.000000", due)]
    )
    assert written.status_code == 200, written.text
    base = f"{plans_url(project_id)}/{plan_id}/versions/{version_id}"
    assert collections_client.post(f"{base}/submit", json={}).status_code == 200
    assert cfo_client.post(f"{base}/approve", json={"reason": "Terms reviewed"}).status_code == 200
    assert cfo_client.post(f"{base}/activate", json={}).status_code == 200
    return Decimal(contract_basis(collections_client, project_id, plan_id)["payable"])


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
    cost_codes: dict[str, str],
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
    activated = govern_cashflow_forecast(
        finance_client, cfo_client, project_id, identifier, cost_codes=cost_codes
    )
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
        assert row["basis"] == "actual_and_forecast", (
            "the month a report is taken in is part spent and part expected"
        )
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

    def test_a_month_states_which_of_the_three_bases_it_is_on(
        self, finance_client: TestClient, project_id: str, opening_forecast: str
    ) -> None:
        """Never colour alone. A reader who cannot see two shades still needs to know.

        Three words, because there are three cases. A closed month is settled, a
        future month is expectation, and the month a report was taken in is
        both — and calling that one "actual" presents a part month as a finished
        one to the reader least able to tell the difference.
        """
        months = cashflow_monthly(finance_client, project_id)["months"]
        assert month_row({"months": months}, month_named(0))["basis"] == "actual_and_forecast"
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


class TestTheCurrentMonthIsPartActualAndPartForecast:
    """A part-spent month is not a finished one.

    The error this class exists for is quiet. A month the report is taken inside
    has real transactions in it, so reporting it on actuals alone produces a real
    number made of real cash — and drops every payment still due before the month
    ends. On the third of the month that understates collections by four weeks,
    and the project reads as short of cash for a reason that evaporates on the
    first of the next month.
    """

    def test_this_months_construction_forecast_survives_the_month_beginning(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_construction_forecast: str,
    ) -> None:
        """A month-grained line for this month is the rest of this month.

        It is the preparer's statement of what is still to be paid, written while
        the month was running. Zeroing it the moment the month starts deletes the
        whole figure on the first of the month.
        """
        created = create_cashflow_forecast(
            finance_client,
            project_id,
            forecast_start_month=month_named(0),
            forecast_end_month=month_named(3),
        )
        identifier = created.json()["id"]
        assert (
            set_cashflow_line(
                finance_client,
                project_id,
                identifier,
                period_month=month_named(0),
                source_kind="construction",
                category="construction",
                amount="1000000.00",
                construction_cost_code_id=cost_codes["hard"],
            ).status_code
            == 200
        )
        assert (
            govern_cashflow_forecast(
                finance_client, cfo_client, project_id, identifier, cost_codes=cost_codes
            ).status_code
            == 200
        )
        row = month_row(cashflow_monthly(finance_client, project_id), month_named(0))
        assert row["construction_forecast_payments"] == "1000000.00"
        assert row["total_outflows"] == "1000000.00"

    def test_an_instalment_due_later_this_month_is_still_forecast_cash(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        collections_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        flat_construction_forecast: str,
        active_sale: str,
        plan_id: str,
    ) -> None:
        """Read as at the first of the month, with the money due on the last of it.

        Dated rows answer on their own date, not on their month. Asking whether
        the *month* has begun deletes an instalment due on the 28th from a report
        taken on the 1st, and most of the month's collections with it.
        """
        payable = one_instalment_due(
            collections_client, cfo_client, project_id, plan_id, due=end_of_this_month()
        )
        identifier = create_cashflow_forecast(
            finance_client,
            project_id,
            forecast_start_month=month_named(0),
            forecast_end_month=month_named(3),
        ).json()["id"]
        assert (
            govern_cashflow_forecast(
                finance_client, cfo_client, project_id, identifier, cost_codes=cost_codes
            ).status_code
            == 200
        )

        monthly = cashflow_monthly(finance_client, project_id, as_of=month_named(0))
        row = month_row(monthly, month_named(0))
        assert row["basis"] == "actual_and_forecast"
        assert Decimal(row["customer_forecast_receipts"]) == payable
        assert Decimal(row["total_inflows"]) == payable

    def test_cash_that_arrived_is_not_forecast_again_in_the_same_month(
        self,
        db: Session,
        finance_client: TestClient,
        cfo_client: TestClient,
        collections_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        flat_construction_forecast: str,
        active_sale: str,
        plan_id: str,
    ) -> None:
        """Both series in one month, and the same money in only one of them.

        A hybrid month is only safe if nothing is counted twice. Cash that has
        arrived is actual; the instalment it will eventually be applied to leaves
        the forward forecast by exactly that amount, so the month's customer
        total is the instalment — not the instalment plus the cash.
        """
        opening = month_named(0)
        payable = one_instalment_due(
            collections_client, cfo_client, project_id, plan_id, due=end_of_this_month()
        )
        receipt = record_receipt(
            collections_client, project_id, active_sale, "5000.00", receipt_date=opening
        )
        receipt_id = receipt.json()["id"]
        confirm_receipt(finance_client, project_id, receipt_id)
        backdate(db, table="collection_receipts", row_id=receipt_id, confirmed_at=at(opening))

        identifier = create_cashflow_forecast(
            finance_client,
            project_id,
            forecast_start_month=opening,
            forecast_end_month=month_named(3),
        ).json()["id"]
        assert (
            govern_cashflow_forecast(
                finance_client, cfo_client, project_id, identifier, cost_codes=cost_codes
            ).status_code
            == 200
        )

        row = month_row(cashflow_monthly(finance_client, project_id, as_of=opening), opening)
        assert Decimal(row["customer_actual_receipts"]) == Decimal("5000.00")
        assert Decimal(row["customer_forecast_receipts"]) == payable - Decimal("5000.00")
        assert Decimal(row["total_inflows"]) == payable, (
            "the cash that arrived is inside the instalment, not on top of it"
        )


class TestTheOpeningBalanceAnchorsTheSeries:
    """An opening balance is a statement about one moment, not a starting point.

    The transactions of the months before it are not additional to it — they are
    what produced it. Replaying them through it counts each of them twice, and
    the error grows with how much history a project has, so the oldest and most
    valuable projects report the worst numbers.
    """

    def test_the_bridge_opens_in_the_month_the_balance_is_stated_for(
        self, finance_client: TestClient, project_id: str, opening_forecast: str
    ) -> None:
        monthly = cashflow_monthly(finance_client, project_id)
        months = monthly["months"]
        assert isinstance(months, list)
        assert months[0]["period_month"] == month_named(0)
        assert months[0]["opening_total_cash"] == "1200.00"

    def test_a_transaction_before_the_anchor_is_not_replayed_through_it(
        self,
        finance_client: TestClient,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        opening_forecast: str,
    ) -> None:
        """It is already inside the opening balance. Running it again would double it."""
        receipt = record_receipt(
            collections_client,
            project_id,
            collecting_sale,
            "9000.00",
            receipt_date=month_named(-2),
        )
        confirm_receipt(finance_client, project_id, receipt.json()["id"])

        monthly = cashflow_monthly(finance_client, project_id)
        months = monthly["months"]
        assert isinstance(months, list)
        assert months[0]["period_month"] == month_named(0)
        assert months[0]["opening_total_cash"] == "1200.00"
        assert all(row["period_month"] >= month_named(0) for row in months)

    def test_the_pre_opening_transaction_is_still_in_the_drilldown(
        self,
        finance_client: TestClient,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        opening_forecast: str,
    ) -> None:
        """Excluded from the bridge is not the same as hidden."""
        receipt = record_receipt(
            collections_client,
            project_id,
            collecting_sale,
            "9000.00",
            receipt_date=month_named(-2),
        )
        confirm_receipt(finance_client, project_id, receipt.json()["id"])
        drilldown = finance_client.get(
            f"{cashflow_url(project_id)}/drilldown", params={"period_month": month_named(-2)}
        )
        assert drilldown.status_code == 200, drilldown.text
        assert drilldown.json()["total"] == "9000.00"

    def test_asking_for_a_month_before_the_anchor_says_why_it_cannot(
        self, finance_client: TestClient, project_id: str, opening_forecast: str
    ) -> None:
        """A refusal a preparer can act on, not an empty chart or a wrong one."""
        refused = finance_client.get(
            f"{cashflow_url(project_id)}/monthly", params={"from_month": month_named(-3)}
        )
        assert refused.status_code == 422, refused.text
        detail = refused.json()["detail"].lower()
        assert "opening balance" in detail
        assert "drill-down" in detail
