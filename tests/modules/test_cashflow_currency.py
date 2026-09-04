"""One denomination throughout, and no exchange rate to hide behind.

The MVP has no FX. A movement in another currency is refused at entry rather
than converted, relabelled or quietly excluded — and the third of those is the
worst, because a cash position silently missing a transaction says nothing on
screen about what it left out.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.modules.conftest import (
    SETTINGS,
    cashflow_url,
    create_cashflow_forecast,
    govern_cashflow_forecast,
    month_named,
    record_development,
    record_financing,
)


@pytest.fixture
def foreign_currency_id(admin_client: TestClient) -> str:
    created = admin_client.post(
        f"{SETTINGS}/currencies", json={"code": "EUR", "name": "Euro", "minor_units": 2}
    )
    assert created.status_code in {200, 201, 409}, created.text
    currencies = admin_client.get(f"{SETTINGS}/currencies").json()
    identifier: str = next(row for row in currencies if row["code"] == "EUR")["id"]
    return identifier


@pytest.fixture
def cash_forecast(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    flat_construction_forecast: str,
) -> str:
    created = create_cashflow_forecast(
        finance_client,
        project_id,
        forecast_start_month=month_named(0),
        forecast_end_month=month_named(1),
    )
    identifier: str = created.json()["id"]
    assert (
        govern_cashflow_forecast(finance_client, cfo_client, project_id, identifier).status_code
        == 200
    )
    return identifier


class TestAForeignMovementIsRefusedNotConverted:
    def test_a_development_movement_in_another_currency_is_refused(
        self,
        finance_client: TestClient,
        project_id: str,
        foreign_currency_id: str,
        cash_forecast: str,
    ) -> None:
        refused = record_development(finance_client, project_id, foreign_currency_id)
        assert refused.status_code == 422, refused.text
        assert "exchange rate" in refused.json()["detail"]

    def test_a_financing_movement_in_another_currency_is_refused(
        self,
        finance_client: TestClient,
        project_id: str,
        foreign_currency_id: str,
        cash_forecast: str,
    ) -> None:
        refused = record_financing(finance_client, project_id, foreign_currency_id)
        assert refused.status_code == 422, refused.text

    def test_the_refusal_names_the_project_currency(
        self,
        finance_client: TestClient,
        project_id: str,
        foreign_currency_id: str,
        cash_forecast: str,
    ) -> None:
        """A refusal that does not say what would be accepted is a dead end."""
        refused = record_development(finance_client, project_id, foreign_currency_id)
        assert "accounts in" in refused.json()["detail"]


class TestTheForecastIsDenominated:
    def test_a_forecast_states_the_currency_it_is_in(
        self, finance_client: TestClient, project_id: str, cash_forecast: str
    ) -> None:
        detail = finance_client.get(f"{cashflow_url(project_id)}/forecasts/{cash_forecast}").json()
        assert detail["currency_code"]

    def test_every_report_states_its_currency(
        self, finance_client: TestClient, project_id: str, cash_forecast: str
    ) -> None:
        """A total in no stated currency is a total in no currency at all."""
        for path in ("/summary", "/monthly", "/reconciliation", "/management"):
            body = finance_client.get(f"{cashflow_url(project_id)}{path}").json()
            assert body["basis"]["currency_code"], path

    def test_the_reconciliation_counts_foreign_movements(
        self, finance_client: TestClient, project_id: str, cash_forecast: str
    ) -> None:
        body = finance_client.get(f"{cashflow_url(project_id)}/reconciliation").json()
        check = next(row for row in body["checks"] if row["name"] == "one_denomination_throughout")
        assert check["passed"] is True
        assert check["actual"] == "0"
