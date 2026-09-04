"""Scheduled, forecast and actual customer cash are three different numbers.

Scheduled is what the governing buyer schedules say becomes due. Forecast is
what Finance expects to collect and when. Actual is what collections confirms
arrived. Collapsing any two of them produces a report that looks complete and
answers the wrong question.

The rule this family exists for is the subtlest in the module. A confirmed
receipt is already counted as cash that arrived. If the instalments it will
eventually be applied to also stay in the forward forecast at full value, the
same money is counted twice — once as received and once as expected. The
forecast offsets it; collections' records are not touched.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from tests.modules.conftest import (
    cashflow_monthly,
    cashflow_url,
    confirm_receipt,
    create_cashflow_forecast,
    current_version_id,
    fixed_row,
    govern_cashflow_forecast,
    month_named,
    plans_url,
    record_receipt,
    write_schedule,
)


def total_of(monthly: dict[str, object], field: str) -> Decimal:
    months = monthly["months"]
    assert isinstance(months, list)
    return sum((Decimal(row[field]) for row in months), Decimal("0.00"))


def future_total(monthly: dict[str, object], field: str) -> Decimal:
    months = monthly["months"]
    assert isinstance(months, list)
    return sum(
        (Decimal(row[field]) for row in months if row["basis"] == "forecast"),
        Decimal("0.00"),
    )


@pytest.fixture
def forward_schedule(
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    active_sale: str,
    plan_id: str,
) -> tuple[str, str]:
    """A governing schedule whose instalments are still ahead of the project.

    The suite's standard 20 / 30 / 50 falls due in March, June and September of
    the year under test, which is behind today — and a schedule entirely in the
    past has no forward collection to forecast. This one is three equal thirds in
    the months ahead, which is what makes the forecast series non-empty and the
    unapplied-cash offset observable.
    """
    version_id = current_version_id(collections_client, project_id, plan_id)
    written = write_schedule(
        collections_client,
        project_id,
        plan_id,
        version_id,
        [
            fixed_row(1, "0.340000", month_named(3)),
            fixed_row(2, "0.330000", month_named(6)),
            fixed_row(3, "0.330000", month_named(9)),
        ],
    )
    assert written.status_code == 200, written.text
    base = f"{plans_url(project_id)}/{plan_id}/versions/{version_id}"
    assert collections_client.post(f"{base}/submit", json={}).status_code == 200
    assert cfo_client.post(f"{base}/approve", json={"reason": "Terms reviewed"}).status_code == 200
    assert cfo_client.post(f"{base}/activate", json={}).status_code == 200
    return plan_id, version_id


@pytest.fixture
def cash_forecast(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    cost_codes: dict[str, str],
    flat_construction_forecast: str,
    forward_schedule: tuple[str, str],
) -> str:
    """A forecast in force over a year, built on the sale's governing schedule."""
    created = create_cashflow_forecast(
        finance_client,
        project_id,
        forecast_start_month=month_named(0),
        forecast_end_month=month_named(18),
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


class TestTheThreeSeriesAreSeparate:
    def test_the_governing_schedule_is_frozen_into_the_version(
        self, finance_client: TestClient, project_id: str, cash_forecast: str
    ) -> None:
        """Provenance: the version records which instalments it was built on."""
        detail = finance_client.get(f"{cashflow_url(project_id)}/forecasts/{cash_forecast}").json()
        assert detail["installments_in_snapshot"] > 0
        assert len(detail["customer_schedule"]) == detail["installments_in_snapshot"]
        first = detail["customer_schedule"][0]
        assert first["chosen_forecast_date"] is not None
        assert "amount" in first

    def test_the_snapshot_carries_no_buyer(
        self, finance_client: TestClient, project_id: str, cash_forecast: str
    ) -> None:
        """A cash forecast needs the money and the dates, not who is paying."""
        detail = finance_client.get(f"{cashflow_url(project_id)}/forecasts/{cash_forecast}").json()
        row = detail["customer_schedule"][0]
        assert "buyer" not in row
        assert "client_name" not in row
        assert "party" not in row

    def test_scheduled_due_is_reported_in_every_month_it_falls(
        self, finance_client: TestClient, project_id: str, cash_forecast: str
    ) -> None:
        monthly = cashflow_monthly(finance_client, project_id)
        assert total_of(monthly, "customer_scheduled_due") > Decimal("0.00")


class TestCashArrivesOnce:
    def test_confirmed_unapplied_cash_counts_as_actual_and_leaves_the_forecast(
        self,
        finance_client: TestClient,
        collections_client: TestClient,
        project_id: str,
        active_sale: str,
        cash_forecast: str,
    ) -> None:
        """Given / When / Then: 80 arrives unapplied; the forward forecast drops by 80.

        Not 80 *somewhere* — exactly 80, taken off the earliest expected
        instalments first. Leaving it in would have the project collect the same
        money twice: once in the month it arrived and again in the month the
        instalment it will be filed against falls due.
        """
        before = future_total(
            cashflow_monthly(finance_client, project_id), "customer_forecast_receipts"
        )

        receipt = record_receipt(
            collections_client,
            project_id,
            active_sale,
            "80.00",
            receipt_date=date.today().isoformat(),
        )
        assert receipt.status_code == 201, receipt.text
        assert confirm_receipt(finance_client, project_id, receipt.json()["id"]).status_code == 200

        monthly = cashflow_monthly(finance_client, project_id)
        assert total_of(monthly, "customer_actual_receipts") == Decimal("80.00")
        after = future_total(monthly, "customer_forecast_receipts")
        assert before - after == Decimal("80.00"), (
            "confirmed unapplied cash must leave the forward forecast exactly once"
        )

    def test_collections_records_are_not_touched_by_the_offset(
        self,
        finance_client: TestClient,
        collections_client: TestClient,
        project_id: str,
        active_sale: str,
        cash_forecast: str,
    ) -> None:
        """The operator's filing backlog is theirs; a forecast may not clear it."""
        from tests.modules.conftest import collections_url

        receipt = record_receipt(collections_client, project_id, active_sale, "80.00")
        receipt_id = receipt.json()["id"]
        confirm_receipt(finance_client, project_id, receipt_id)
        cashflow_monthly(finance_client, project_id)

        detail = collections_client.get(f"{collections_url(project_id)}/receipts/{receipt_id}")
        assert detail.status_code == 200, detail.text
        assert detail.json()["allocations"] == []

    def test_the_scheduled_series_is_not_reduced_by_cash_received(
        self,
        finance_client: TestClient,
        collections_client: TestClient,
        project_id: str,
        active_sale: str,
        cash_forecast: str,
    ) -> None:
        """Scheduled due is a contractual fact and a receipt does not change it."""
        before = total_of(cashflow_monthly(finance_client, project_id), "customer_scheduled_due")
        receipt = record_receipt(collections_client, project_id, active_sale, "80.00")
        confirm_receipt(finance_client, project_id, receipt.json()["id"])
        after = total_of(cashflow_monthly(finance_client, project_id), "customer_scheduled_due")
        assert before == after
