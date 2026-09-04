"""What existed at a cutoff, and what is standing today.

Two columns answer two different questions, and collapsing them is silent.

The **confirmation timestamp** decides whether a transaction existed when a
forecast was taken. A receipt dated 31 August and confirmed on 5 September was
not cash Finance knew about on 31 August, however early its business date.

The **business date** decides which month it belongs to. Once a later forecast
picks that receipt up, it belongs to August — the month the money actually
arrived — and not to September.

And a reversal is not a deletion. A forecast approved with a transaction inside
it goes on saying what it said; only the current position drops it.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.modules.conftest import (
    at,
    backdate,
    cashflow_monthly,
    collections_url,
    confirm_receipt,
    create_cashflow_forecast,
    govern_cashflow_forecast,
    month_named,
    record_receipt,
    refund_buyer,
)


def days_ago(count: int) -> date:
    return date.today() - timedelta(days=count)


def month_of(day: date) -> str:
    return day.replace(day=1).isoformat()


def customer_cash(monthly: dict[str, object], month: str) -> Decimal:
    months = monthly["months"]
    assert isinstance(months, list)
    row = next((entry for entry in months if entry["period_month"] == month), None)
    return Decimal(row["customer_actual_receipts"]) if row else Decimal("0.00")


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
        forecast_start_month=month_named(-3),
        forecast_end_month=month_named(3),
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


class TestConfirmationDecidesExistenceAndTheDateDecidesTheMonth:
    def test_a_receipt_confirmed_after_the_cutoff_is_not_in_that_position(
        self,
        db: Session,
        finance_client: TestClient,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        cash_forecast: str,
    ) -> None:
        """Given / When / Then: dated ten days ago, confirmed two days ago.

        A position taken as at five days ago cannot contain it: on that date
        nobody had confirmed the transfer. Filtering on the business date would
        put it inside a cash position that was correct when it was taken, and
        re-reading that position later would show cash the company did not yet
        have.
        """
        receipt = record_receipt(
            collections_client,
            project_id,
            collecting_sale,
            "400.00",
            receipt_date=days_ago(10).isoformat(),
        )
        receipt_id = receipt.json()["id"]
        assert confirm_receipt(finance_client, project_id, receipt_id).status_code == 200
        backdate(
            db,
            table="collection_receipts",
            row_id=receipt_id,
            confirmed_at=at(days_ago(2)),
        )

        earlier = cashflow_monthly(finance_client, project_id, as_of=days_ago(5).isoformat())
        assert customer_cash(earlier, month_of(days_ago(10))) == Decimal("0.00")

    def test_a_later_position_places_it_in_the_month_it_arrived(
        self,
        db: Session,
        finance_client: TestClient,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        cash_forecast: str,
    ) -> None:
        """Once it exists, it belongs to the month of the transfer, not the signature."""
        receipt = record_receipt(
            collections_client,
            project_id,
            collecting_sale,
            "400.00",
            receipt_date=days_ago(10).isoformat(),
        )
        receipt_id = receipt.json()["id"]
        confirm_receipt(finance_client, project_id, receipt_id)
        backdate(
            db,
            table="collection_receipts",
            row_id=receipt_id,
            confirmed_at=at(days_ago(2)),
        )

        now = cashflow_monthly(finance_client, project_id)
        assert customer_cash(now, month_of(days_ago(10))) == Decimal("400.00")

    def test_a_position_cannot_be_taken_as_at_a_future_date(
        self, finance_client: TestClient, project_id: str, cash_forecast: str
    ) -> None:
        """It would have to invent transactions, or their absence, as fact."""
        from tests.modules.conftest import cashflow_url

        refused = finance_client.get(
            f"{cashflow_url(project_id)}/monthly",
            params={"as_of": (date.today() + timedelta(days=1)).isoformat()},
        )
        assert refused.status_code == 422, refused.text


class TestAReversalDoesNotRewriteHistory:
    def test_a_receipt_reversed_later_stays_in_the_earlier_position(
        self,
        db: Session,
        finance_client: TestClient,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        cash_forecast: str,
    ) -> None:
        """Confirmed ten days ago, reversed today. A position as at five days ago keeps it."""
        receipt = record_receipt(
            collections_client,
            project_id,
            collecting_sale,
            "400.00",
            receipt_date=days_ago(12).isoformat(),
        )
        receipt_id = receipt.json()["id"]
        confirm_receipt(finance_client, project_id, receipt_id)
        backdate(
            db,
            table="collection_receipts",
            row_id=receipt_id,
            confirmed_at=at(days_ago(10)),
        )
        reversed_response = finance_client.post(
            f"{collections_url(project_id)}/receipts/{receipt_id}/reverse",
            json={"reason": "Bank returned the transfer"},
        )
        assert reversed_response.status_code == 200, reversed_response.text

        earlier = cashflow_monthly(finance_client, project_id, as_of=days_ago(5).isoformat())
        assert customer_cash(earlier, month_of(days_ago(12))) == Decimal("400.00")

    def test_the_current_position_drops_it_the_moment_it_is_reversed(
        self,
        db: Session,
        finance_client: TestClient,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        cash_forecast: str,
    ) -> None:
        """The two answers differ on purpose, and this is the pair that proves it."""
        receipt = record_receipt(
            collections_client,
            project_id,
            collecting_sale,
            "400.00",
            receipt_date=days_ago(12).isoformat(),
        )
        receipt_id = receipt.json()["id"]
        confirm_receipt(finance_client, project_id, receipt_id)
        backdate(
            db,
            table="collection_receipts",
            row_id=receipt_id,
            confirmed_at=at(days_ago(10)),
        )
        finance_client.post(
            f"{collections_url(project_id)}/receipts/{receipt_id}/reverse",
            json={"reason": "Bank returned the transfer"},
        )

        now = cashflow_monthly(finance_client, project_id)
        assert customer_cash(now, month_of(days_ago(12))) == Decimal("0.00")


class TestARefundIsCashOutAndNeverANegativeReceipt:
    def test_receipts_and_refunds_are_reported_separately(
        self,
        finance_client: TestClient,
        collections_client: TestClient,
        sales_ops_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        collecting_sale: str,
        cash_forecast: str,
    ) -> None:
        """100 in and 30 out is two transactions. Never one figure of 70.

        "We received a hundred and refunded thirty" is the sentence a buyer and
        an auditor both ask about, and a stored net answers neither of them.
        """
        today = date.today().isoformat()
        receipt = record_receipt(
            collections_client, project_id, collecting_sale, "100.00", receipt_date=today
        )
        confirm_receipt(finance_client, project_id, receipt.json()["id"])
        refund_buyer(
            sales_ops_client,
            cfo_client,
            collections_client,
            finance_client,
            project_id,
            collecting_sale,
            amount="30.00",
            refund_date=today,
        )

        months = cashflow_monthly(finance_client, project_id)["months"]
        row = next(entry for entry in months if entry["period_month"] == month_named(0))
        assert row["customer_actual_receipts"] == "100.00"
        assert row["customer_refunds"] == "30.00"
        assert row["net_cashflow"] == "70.00", "the net is derived, never stored"
