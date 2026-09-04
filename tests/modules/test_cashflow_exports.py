"""The export is the screen's own response, rendered.

A dashboard saying 5,420,000 and a CSV saying 5,419,999 is a failed control
however small the gap, and the only way to be certain they agree is for them to
be the same list. These tests read both and compare them cell by cell.
"""

from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.modules.cashflow.read import DRILLDOWN_CSV_COLUMNS, MONTHLY_CSV_COLUMNS
from tests.modules.conftest import (
    cashflow_monthly,
    cashflow_url,
    confirm_receipt,
    create_cashflow_forecast,
    govern_cashflow_forecast,
    month_named,
    record_receipt,
)


def rows_of(body: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(body)))


@pytest.fixture
def project_with_cash(
    finance_client: TestClient,
    cfo_client: TestClient,
    collections_client: TestClient,
    project_id: str,
    cost_codes: dict[str, str],
    collecting_sale: str,
    flat_construction_forecast: str,
) -> str:
    created = create_cashflow_forecast(
        finance_client,
        project_id,
        opening_unrestricted_cash="1000.00",
        forecast_start_month=month_named(0),
        forecast_end_month=month_named(2),
    )
    identifier: str = created.json()["id"]
    assert (
        govern_cashflow_forecast(
            finance_client, cfo_client, project_id, identifier, cost_codes=cost_codes
        ).status_code
        == 200
    )
    receipt = record_receipt(
        collections_client,
        project_id,
        collecting_sale,
        "500.00",
        receipt_date=date.today().isoformat(),
    )
    confirm_receipt(finance_client, project_id, receipt.json()["id"])
    return identifier


class TestTheMonthlyExportMatchesTheScreen:
    def test_every_month_and_every_column_agrees(
        self, finance_client: TestClient, project_id: str, project_with_cash: str
    ) -> None:
        """Given / When / Then: cell for cell, not total for total.

        Comparing only the totals would pass while two months had compensating
        errors, which is the failure mode a reconciliation is supposed to catch
        rather than reproduce.
        """
        monthly = cashflow_monthly(finance_client, project_id)
        export = finance_client.get(f"{cashflow_url(project_id)}/monthly.csv")
        assert export.status_code == 200, export.text
        assert export.headers["content-type"].startswith("text/csv")

        exported = rows_of(export.text)
        assert len(exported) == len(monthly["months"])
        labels = dict(MONTHLY_CSV_COLUMNS)
        for screen, row in zip(monthly["months"], exported, strict=True):
            for field, label in labels.items():
                assert row[label] == str(screen[field]), (
                    f"{screen['period_month']} {field}: screen {screen[field]}, export {row[label]}"
                )

    def test_the_export_carries_a_filename(
        self, finance_client: TestClient, project_id: str, project_with_cash: str
    ) -> None:
        export = finance_client.get(f"{cashflow_url(project_id)}/monthly.csv")
        assert "attachment" in export.headers["content-disposition"]
        assert ".csv" in export.headers["content-disposition"]

    def test_the_same_filters_produce_the_same_rows(
        self, finance_client: TestClient, project_id: str, project_with_cash: str
    ) -> None:
        params = {"from_month": month_named(0), "to_month": month_named(1)}
        monthly = cashflow_monthly(finance_client, project_id, **params)
        export = finance_client.get(f"{cashflow_url(project_id)}/monthly.csv", params=params)
        assert len(rows_of(export.text)) == len(monthly["months"]) == 2


class TestTheDrilldownExportMatchesTheScreen:
    def test_every_row_agrees(
        self, finance_client: TestClient, project_id: str, project_with_cash: str
    ) -> None:
        screen = finance_client.get(f"{cashflow_url(project_id)}/drilldown").json()
        export = finance_client.get(f"{cashflow_url(project_id)}/drilldown.csv")
        assert export.status_code == 200, export.text

        exported = rows_of(export.text)
        assert len(exported) == len(screen["rows"])
        labels = dict(DRILLDOWN_CSV_COLUMNS)
        for row, exported_row in zip(screen["rows"], exported, strict=True):
            for field, label in labels.items():
                assert exported_row[label] == str(row[field])

    def test_the_total_equals_the_rows_it_lists(
        self, finance_client: TestClient, project_id: str, project_with_cash: str
    ) -> None:
        """A total that is not the sum of what is printed under it is not a total."""
        screen = finance_client.get(
            f"{cashflow_url(project_id)}/drilldown",
            params={"source_type": "collection_receipt"},
        ).json()
        summed = sum((Decimal(row["amount"]) for row in screen["rows"]), Decimal("0.00"))
        assert Decimal(screen["total"]) == summed

    def test_a_filtered_drilldown_names_the_transactions_behind_a_figure(
        self, finance_client: TestClient, project_id: str, project_with_cash: str
    ) -> None:
        screen = finance_client.get(
            f"{cashflow_url(project_id)}/drilldown",
            params={"source_type": "collection_receipt"},
        ).json()
        assert screen["rows"], "the receipt that made the figure must be reachable"
        row = screen["rows"][0]
        assert row["source_type"] == "collection_receipt"
        assert row["source_id"]
        assert row["display_reference"]
        assert row["amount"] == "500.00"
