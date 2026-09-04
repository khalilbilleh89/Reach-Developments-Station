"""Structural checks, each answered on its own. No health score.

A single blended number would let a failed escrow ceiling and a passing currency
check average into "mostly fine", and nobody would know which half was which.
Every check names what it compared, what it expected and what it found.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from tests.modules.conftest import (
    cashflow_url,
    confirm_receipt,
    create_cashflow_forecast,
    govern_cashflow_forecast,
    month_named,
    record_receipt,
    restrict_receipt,
)


def checks_of(client: TestClient, project_id: str) -> dict[str, dict[str, object]]:
    response = client.get(f"{cashflow_url(project_id)}/reconciliation")
    assert response.status_code == 200, response.text
    body = response.json()
    return {check["name"]: check for check in body["checks"]}


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
        opening_unrestricted_cash="1000.00",
        opening_restricted_cash="200.00",
        forecast_start_month=month_named(0),
        forecast_end_month=month_named(2),
    )
    assert created.status_code == 201, created.text
    identifier: str = created.json()["id"]
    assert (
        govern_cashflow_forecast(finance_client, cfo_client, project_id, identifier).status_code
        == 200
    )
    return identifier


class TestEveryCheckIsAnsweredSeparately:
    def test_there_is_no_health_score(
        self, finance_client: TestClient, project_id: str, cash_forecast: str
    ) -> None:
        response = finance_client.get(f"{cashflow_url(project_id)}/reconciliation")
        body = response.json()
        assert "score" not in body
        assert "health" not in body
        assert isinstance(body["checks"], list)
        assert body["failed_count"] == 0

    def test_each_check_names_what_it_compared(
        self, finance_client: TestClient, project_id: str, cash_forecast: str
    ) -> None:
        for check in checks_of(finance_client, project_id).values():
            assert check["name"]
            assert check["detail"], f"{check['name']} says nothing about what it means"
            assert "passed" in check

    def test_the_response_states_its_basis(
        self, finance_client: TestClient, project_id: str, cash_forecast: str
    ) -> None:
        body = finance_client.get(f"{cashflow_url(project_id)}/reconciliation").json()
        assert body["basis"]["project_id"]
        assert body["basis"]["as_of_date"]
        assert body["basis"]["forecast_version_number"] == 1


class TestTheChecksThatMatter:
    def test_the_monthly_bridge_is_checked_in_every_month(
        self, finance_client: TestClient, project_id: str, cash_forecast: str
    ) -> None:
        """Opening plus inflows less outflows is closing, per month, exactly."""
        names = checks_of(finance_client, project_id)
        bridges = [name for name in names if name.startswith("bridge_")]
        assert len(bridges) >= 3
        assert all(names[name]["passed"] for name in bridges)

    def test_the_usable_split_is_checked_in_every_month(
        self, finance_client: TestClient, project_id: str, cash_forecast: str
    ) -> None:
        names = checks_of(finance_client, project_id)
        splits = [name for name in names if name.startswith("usable_split_")]
        assert splits
        assert all(names[name]["passed"] for name in splits)

    def test_each_month_opens_where_the_last_closed(
        self, finance_client: TestClient, project_id: str, cash_forecast: str
    ) -> None:
        names = checks_of(finance_client, project_id)
        carries = [name for name in names if name.startswith("carry_")]
        assert carries
        assert all(names[name]["passed"] for name in carries)

    def test_the_construction_schedule_is_reconciled(
        self, finance_client: TestClient, project_id: str, cash_forecast: str
    ) -> None:
        names = checks_of(finance_client, project_id)
        assert any(name.startswith("construction_schedule_") for name in names)

    def test_a_restriction_is_checked_against_its_receipt(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        cash_forecast: str,
    ) -> None:
        receipt = record_receipt(
            collections_client,
            project_id,
            collecting_sale,
            "100.00",
            receipt_date=date.today().isoformat(),
        )
        receipt_id = receipt.json()["id"]
        confirm_receipt(finance_client, project_id, receipt_id)
        restriction = restrict_receipt(
            finance_client, project_id, receipt_id, restricted_amount="80.00"
        )
        restriction_id = restriction.json()["id"]
        second_finance_client.post(
            f"{cashflow_url(project_id)}/restrictions/{restriction_id}/confirm", json={}
        )

        names = checks_of(finance_client, project_id)
        within = names[f"restriction_within_receipt_{restriction_id}"]
        assert within["passed"] is True
        assert within["expected"] == "100.00"
        assert within["actual"] == "80.00"

        releases = names[f"releases_within_restriction_{restriction_id}"]
        assert releases["passed"] is True
        assert releases["expected"] == "80.00"

    def test_one_denomination_throughout(
        self, finance_client: TestClient, project_id: str, cash_forecast: str
    ) -> None:
        """A movement in another currency would be silently missing otherwise."""
        names = checks_of(finance_client, project_id)
        assert names["one_denomination_throughout"]["passed"] is True

    def test_the_maker_checker_rule_is_re_proved_on_the_rows(
        self, finance_client: TestClient, project_id: str, cash_forecast: str
    ) -> None:
        """The database refuses it; this proves none slipped past an older schema."""
        names = checks_of(finance_client, project_id)
        for label in ("development", "financing", "release"):
            assert names[f"{label}_maker_is_not_checker"]["passed"] is True

    def test_the_customer_snapshot_completeness_is_reported(
        self, finance_client: TestClient, project_id: str, cash_forecast: str
    ) -> None:
        """An instalment with no date of any kind is counted, never dropped quietly."""
        names = checks_of(finance_client, project_id)
        assert "customer_schedule_snapshot_complete" in names

    def test_a_stale_construction_source_is_reported_as_a_failure(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        cash_forecast: str,
    ) -> None:
        """The forecast in force is pinned to a construction version behind the one active."""
        from tests.modules.conftest import (
            cover_construction_forecast,
            create_forecast,
            govern_forecast,
        )

        second_id = create_forecast(
            finance_client, project_id, change_reason="Revised build"
        ).json()["id"]
        cover_construction_forecast(finance_client, project_id, second_id, cost_codes, hard="0.00")
        assert govern_forecast(finance_client, cfo_client, project_id, second_id).status_code == 200

        names = checks_of(finance_client, project_id)
        assert names["construction_source_current"]["passed"] is False
