"""Cash happens once, and a hand-written forecast is not exempt from it.

The platform already enforces this for buyer receipts: money that arrived leaves
the forward schedule by exactly its amount, or the same cash is reported as both
collected and expected. The figures Finance types into a forecast need the same
treatment and did not have it.

A September line of 1,000,000 is the spend expected *for September, at the moment
the forecast was cut*. Pay 300,000 of it on the 10th and a live report of
September is 300,000 gone and 700,000 to go. Reporting 300,000 actual **and**
1,000,000 forecast claims 1,300,000 on no evidence at all — nobody forecast a
further million after paying the first three hundred thousand — and the error
lands squarely on the funding requirement, which is the number somebody takes to
a bank.

What is *not* touched is the governed figure. The forecast file goes on saying
1,000,000, because that is what was approved and what accuracy has to be measured
against. Only the projection reads the remainder.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.modules.conftest import (
    cashflow_monthly,
    cashflow_url,
    cover_construction_forecast,
    create_cashflow_forecast,
    create_forecast,
    govern_cashflow_forecast,
    govern_forecast,
    month_named,
    pay_construction,
    record_development,
    record_financing,
    set_cashflow_line,
)

ZERO = Decimal("0.00")


def month_row(monthly: dict[str, Any], month: str) -> dict[str, str]:
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


def forecast_taken_last_month(
    finance_client: TestClient,
    project_id: str,
) -> str:
    """A forecast cut at the start of last month, so today is after its cutoff.

    The offset only applies to cash that moved **after** the forecast was
    written — a payment the preparer could already see is inside the figure they
    wrote. Cutting the version a month back puts every transaction these tests
    record on the right side of that line, on any calendar day.
    """
    created = create_cashflow_forecast(
        finance_client,
        project_id,
        as_of_date=month_named(-1),
        forecast_start_month=month_named(-1),
        forecast_end_month=month_named(3),
    )
    assert created.status_code == 201, created.text
    identifier: str = created.json()["id"]
    return identifier


class TestConstructionCashMeetsTheConstructionForecast:
    @pytest.fixture
    def costed_build(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_budget: str,
    ) -> str:
        """A construction forecast in force with 100,000 left on hard cost.

        Sized to sit inside what the suite's certificate authorises, so the
        payments below go through the ordinary route rather than a special one.
        """
        version_id = create_forecast(finance_client, project_id).json()["id"]
        cover_construction_forecast(
            finance_client, project_id, version_id, cost_codes, hard="100000.00"
        )
        governed = govern_forecast(finance_client, cfo_client, project_id, version_id)
        assert governed.status_code == 200, governed.text
        return version_id

    @pytest.fixture
    def scheduled_build(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        costed_build: str,
    ) -> str:
        """100,000 of hard cost, all of it expected in the current month."""
        identifier = forecast_taken_last_month(finance_client, project_id)
        assert (
            set_cashflow_line(
                finance_client,
                project_id,
                identifier,
                period_month=month_named(0),
                source_kind="construction",
                category="construction",
                amount="100000.00",
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
        return identifier

    def test_paying_part_of_it_leaves_the_rest_expected(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        currency_id: str,
        active_contract: str,
        certified_certificate: str,
        scheduled_build: str,
    ) -> None:
        """30,000 paid against 100,000 forecast is 30,000 and 70,000.

        Not 30,000 and 100,000. The month's total construction cash is the
        figure that was forecast, whatever share of it has been paid so far.
        """
        before = month_row(cashflow_monthly(finance_client, project_id), month_named(0))
        assert Decimal(before["construction_forecast_payments"]) == Decimal("100000.00")
        assert Decimal(before["construction_actual_payments"]) == ZERO

        pay_construction(
            finance_client,
            second_finance_client,
            project_id,
            active_contract,
            currency_id,
            certified_certificate,
            amount="30000.00",
        )

        row = month_row(cashflow_monthly(finance_client, project_id), month_named(0))
        assert Decimal(row["construction_actual_payments"]) == Decimal("30000.00")
        assert Decimal(row["construction_forecast_payments"]) == Decimal("70000.00")
        assert Decimal(row["construction_actual_payments"]) + Decimal(
            row["construction_forecast_payments"]
        ) == Decimal("100000.00")

    def test_the_governed_forecast_still_says_what_it_said(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        currency_id: str,
        active_contract: str,
        certified_certificate: str,
        scheduled_build: str,
    ) -> None:
        """The projection reads the remainder. The approved document is untouched."""
        pay_construction(
            finance_client,
            second_finance_client,
            project_id,
            active_contract,
            currency_id,
            certified_certificate,
            amount="30000.00",
        )
        detail = finance_client.get(
            f"{cashflow_url(project_id)}/forecasts/{scheduled_build}"
        ).json()
        line = next(
            row
            for row in detail["lines"]
            if row["source_kind"] == "construction" and row["amount"] != "0.00"
        )
        assert line["amount"] == "100000.00", (
            "a forecast that quietly shrank would not be the one anybody approved"
        )

    def test_spending_more_than_forecast_floors_the_remainder_at_zero(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        currency_id: str,
        active_contract: str,
        certified_certificate: str,
        scheduled_build: str,
    ) -> None:
        """110,000 paid against 100,000 forecast. The overrun is not new expectation.

        A negative remainder would be the forecast quietly growing to absorb an
        overrun, which is the one thing a reader most needs to see.
        """
        for reference, amount in (("PMT-A", "30000.00"), ("PMT-B", "80000.00")):
            pay_construction(
                finance_client,
                second_finance_client,
                project_id,
                active_contract,
                currency_id,
                certified_certificate,
                amount=amount,
                reference=reference,
                invoice_number=f"INV-{reference}",
            )

        row = month_row(cashflow_monthly(finance_client, project_id), month_named(0))
        assert Decimal(row["construction_actual_payments"]) == Decimal("110000.00")
        assert Decimal(row["construction_forecast_payments"]) == ZERO

    def test_the_overrun_is_reported_by_accuracy_instead(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        currency_id: str,
        active_contract: str,
        certified_certificate: str,
        scheduled_build: str,
    ) -> None:
        """Where an overrun belongs: measured against the forecast that was approved."""
        for reference, amount in (("PMT-A", "30000.00"), ("PMT-B", "80000.00")):
            pay_construction(
                finance_client,
                second_finance_client,
                project_id,
                active_contract,
                currency_id,
                certified_certificate,
                amount=amount,
                reference=reference,
                invoice_number=f"INV-{reference}",
            )
        body = finance_client.get(f"{cashflow_url(project_id)}/forecast-accuracy").json()
        row = next(
            entry
            for entry in body["rows"]
            if entry["category_group"] == "construction_outflow"
            and entry["period_month"] == month_named(0)
        )
        variance = row["variance"]
        assert Decimal(variance["forecast_amount"]) == Decimal("100000.00")
        assert Decimal(variance["actual_amount"]) == Decimal("110000.00")
        assert Decimal(variance["variance_amount"]) == Decimal("10000.00")


class TestDevelopmentAndFinancingCashMeetTheirOwnLines:
    @pytest.fixture
    def scheduled_costs(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        flat_construction_forecast: str,
    ) -> str:
        """50,000 of consultants and 400,000 of equity, both expected this month."""
        identifier = forecast_taken_last_month(finance_client, project_id)
        for kind, category, amount, extra in (
            ("development", "consultants", "50000.00", {}),
            ("financing", "equity_contribution", "400000.00", {"flow_direction": "inflow"}),
        ):
            assert (
                set_cashflow_line(
                    finance_client,
                    project_id,
                    identifier,
                    period_month=month_named(0),
                    source_kind=kind,
                    category=category,
                    amount=amount,
                    **extra,
                ).status_code
                == 200
            )
        assert (
            govern_cashflow_forecast(
                finance_client, cfo_client, project_id, identifier, cost_codes=cost_codes
            ).status_code
            == 200
        )
        return identifier

    def test_a_consultant_paid_reduces_the_consultant_forecast(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        currency_id: str,
        scheduled_costs: str,
    ) -> None:
        movement = record_development(
            finance_client, project_id, currency_id, category="consultants", amount="20000.00"
        )
        assert movement.status_code == 201, movement.text
        confirm_movement(second_finance_client, project_id, "development", movement.json()["id"])

        row = month_row(cashflow_monthly(finance_client, project_id), month_named(0))
        assert Decimal(row["development_actual_outflows"]) == Decimal("20000.00")
        assert Decimal(row["development_forecast_outflows"]) == Decimal("30000.00")

    def test_a_different_category_does_not_offset_it(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        currency_id: str,
        scheduled_costs: str,
    ) -> None:
        """Marketing spend is not consultant spend, however convenient the total.

        Cross-offsetting categories would cancel an expectation nobody has met
        and leave the one that was met still standing — the same money wrong in
        two places at once.
        """
        movement = record_development(
            finance_client, project_id, currency_id, category="marketing", amount="20000.00"
        )
        assert movement.status_code == 201, movement.text
        confirm_movement(second_finance_client, project_id, "development", movement.json()["id"])

        row = month_row(cashflow_monthly(finance_client, project_id), month_named(0))
        assert Decimal(row["development_actual_outflows"]) == Decimal("20000.00")
        assert Decimal(row["development_forecast_outflows"]) == Decimal("50000.00")

    def test_equity_received_reduces_the_equity_forecast(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        currency_id: str,
        scheduled_costs: str,
    ) -> None:
        movement = record_financing(finance_client, project_id, currency_id, amount="150000.00")
        assert movement.status_code == 201, movement.text
        confirm_movement(second_finance_client, project_id, "financing", movement.json()["id"])

        row = month_row(cashflow_monthly(finance_client, project_id), month_named(0))
        assert Decimal(row["financing_actual_inflows"]) == Decimal("150000.00")
        assert Decimal(row["financing_forecast_inflows"]) == Decimal("250000.00")

    def test_a_debt_drawdown_does_not_offset_an_equity_forecast(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        currency_id: str,
        scheduled_costs: str,
    ) -> None:
        """Equity and debt are different money with different obligations attached."""
        movement = record_financing(
            finance_client,
            project_id,
            currency_id,
            movement_type="debt_drawdown",
            amount="150000.00",
        )
        assert movement.status_code == 201, movement.text
        confirm_movement(second_finance_client, project_id, "financing", movement.json()["id"])

        row = month_row(cashflow_monthly(finance_client, project_id), month_named(0))
        assert Decimal(row["financing_actual_inflows"]) == Decimal("150000.00")
        assert Decimal(row["financing_forecast_inflows"]) == Decimal("400000.00")


class TestCashBeforeTheCutoffIsAlreadyInTheFigure:
    def test_a_payment_the_preparer_could_see_does_not_offset_twice(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        currency_id: str,
        cost_codes: dict[str, str],
        flat_construction_forecast: str,
    ) -> None:
        """The remaining expectation was stated after it. Subtracting it again halves it.

        This is the mirror of the rule above and matters just as much. A forecast
        written on the 20th already knows about the cash that moved on the 5th;
        the figure is what is left *after* it.
        """
        movement = record_development(
            finance_client, project_id, currency_id, category="consultants", amount="20000.00"
        )
        confirm_movement(second_finance_client, project_id, "development", movement.json()["id"])

        created = create_cashflow_forecast(
            finance_client,
            project_id,
            forecast_start_month=month_named(0),
            forecast_end_month=month_named(3),
        )
        assert created.status_code == 201, created.text
        identifier = created.json()["id"]
        assert (
            set_cashflow_line(
                finance_client,
                project_id,
                identifier,
                period_month=month_named(0),
                source_kind="development",
                category="consultants",
                amount="50000.00",
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
        assert Decimal(row["development_actual_outflows"]) == Decimal("20000.00")
        assert Decimal(row["development_forecast_outflows"]) == Decimal("50000.00"), (
            "the 50,000 was already what was left after the 20,000 went out"
        )
