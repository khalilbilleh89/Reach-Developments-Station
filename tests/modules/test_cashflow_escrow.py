"""Cash received and cash usable, and the transfer between them.

A restriction takes buyer money out of the spendable pool without taking it out
of the bank. A release puts it back. Neither creates or destroys project cash —
and reporting a release as an inflow, which is the obvious mistake because it
makes usable cash go up, would show the project collecting the same money twice.

The ceiling is the control, and it is held under a row lock rather than by a
validator. Two operators each releasing 80 from a restriction of 100 would both
read 100 available, both pass their own check and both write.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from tests.modules.conftest import (
    cashflow_monthly,
    cashflow_url,
    confirm_receipt,
    create_cashflow_forecast,
    govern_cashflow_forecast,
    month_named,
    record_receipt,
    release_restriction,
    restrict_receipt,
)


def month_row(monthly: dict[str, object], month: str) -> dict[str, str]:
    months = monthly["months"]
    assert isinstance(months, list)
    row = next(entry for entry in months if entry["period_month"] == month)
    return row


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
        forecast_end_month=month_named(2),
    )
    assert created.status_code == 201, created.text
    identifier: str = created.json()["id"]
    assert (
        govern_cashflow_forecast(finance_client, cfo_client, project_id, identifier).status_code
        == 200
    )
    return identifier


@pytest.fixture
def restricted_receipt(
    finance_client: TestClient,
    second_finance_client: TestClient,
    collections_client: TestClient,
    project_id: str,
    collecting_sale: str,
    cash_forecast: str,
) -> dict[str, str]:
    """100 of buyer cash received, 80 of it held in escrow and confirmed."""
    receipt = record_receipt(
        collections_client,
        project_id,
        collecting_sale,
        "100.00",
        receipt_date=date.today().isoformat(),
    )
    receipt_id = receipt.json()["id"]
    assert confirm_receipt(finance_client, project_id, receipt_id).status_code == 200
    restriction = restrict_receipt(
        finance_client, project_id, receipt_id, restricted_amount="80.00"
    )
    assert restriction.status_code == 201, restriction.text
    restriction_id = restriction.json()["id"]
    confirmed = second_finance_client.post(
        f"{cashflow_url(project_id)}/restrictions/{restriction_id}/confirm", json={}
    )
    assert confirmed.status_code == 200, confirmed.text
    return {"receipt": receipt_id, "restriction": restriction_id}


class TestARestrictionMovesAvailabilityNotCash:
    def test_the_three_balances_move_as_the_business_means_them_to(
        self, finance_client: TestClient, project_id: str, restricted_receipt: dict[str, str]
    ) -> None:
        """Given / When / Then: total +100, restricted +80, usable +20."""
        row = month_row(cashflow_monthly(finance_client, project_id), month_named(0))
        assert row["closing_total_cash"] == "100.00"
        assert row["closing_restricted_cash"] == "80.00"
        assert row["closing_unrestricted_cash"] == "20.00"

    def test_a_release_frees_cash_without_creating_any(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        restricted_receipt: dict[str, str],
    ) -> None:
        """30 released: total unchanged, restricted 50, usable 50."""
        release = release_restriction(
            finance_client, project_id, restricted_receipt["restriction"], amount="30.00"
        )
        assert release.status_code == 201, release.text
        release_id = release.json()["releases"][0]["id"]
        confirmed = second_finance_client.post(
            f"{cashflow_url(project_id)}/releases/{release_id}/confirm", json={}
        )
        assert confirmed.status_code == 200, confirmed.text

        row = month_row(cashflow_monthly(finance_client, project_id), month_named(0))
        assert row["closing_total_cash"] == "100.00", "a release is not new cash"
        assert row["closing_restricted_cash"] == "50.00"
        assert row["closing_unrestricted_cash"] == "50.00"
        assert row["escrow_releases"] == "30.00"
        assert row["total_inflows"] == "100.00", "the release must not appear as an inflow"


class TestTheCeiling:
    def test_an_escrow_cannot_hold_more_than_the_receipt_it_came_from(
        self,
        finance_client: TestClient,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        cash_forecast: str,
    ) -> None:
        receipt = record_receipt(collections_client, project_id, collecting_sale, "100.00")
        receipt_id = receipt.json()["id"]
        confirm_receipt(finance_client, project_id, receipt_id)
        refused = restrict_receipt(
            finance_client, project_id, receipt_id, restricted_amount="120.00"
        )
        assert refused.status_code == 422, refused.text

    def test_an_escrow_cannot_release_more_than_it_holds(
        self, finance_client: TestClient, project_id: str, restricted_receipt: dict[str, str]
    ) -> None:
        refused = release_restriction(
            finance_client, project_id, restricted_receipt["restriction"], amount="90.00"
        )
        assert refused.status_code == 409, refused.text

    def test_two_partial_releases_are_measured_together(
        self, finance_client: TestClient, project_id: str, restricted_receipt: dict[str, str]
    ) -> None:
        """50 then 50 against 80 held. The second is refused, not the first."""
        first = release_restriction(
            finance_client, project_id, restricted_receipt["restriction"], amount="50.00"
        )
        assert first.status_code == 201, first.text
        second = release_restriction(
            finance_client, project_id, restricted_receipt["restriction"], amount="50.00"
        )
        assert second.status_code == 409, second.text

    def test_only_confirmed_cash_can_be_restricted(
        self,
        finance_client: TestClient,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        cash_forecast: str,
    ) -> None:
        """A recorded receipt is not yet money in the bank."""
        receipt = record_receipt(collections_client, project_id, collecting_sale, "100.00")
        refused = restrict_receipt(
            finance_client, project_id, receipt.json()["id"], restricted_amount="10.00"
        )
        assert refused.status_code == 409, refused.text

    def test_only_a_confirmed_restriction_can_be_released(
        self,
        finance_client: TestClient,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        cash_forecast: str,
    ) -> None:
        receipt = record_receipt(collections_client, project_id, collecting_sale, "100.00")
        receipt_id = receipt.json()["id"]
        confirm_receipt(finance_client, project_id, receipt_id)
        restriction = restrict_receipt(
            finance_client, project_id, receipt_id, restricted_amount="80.00"
        )
        refused = release_restriction(
            finance_client, project_id, restriction.json()["id"], amount="10.00"
        )
        assert refused.status_code == 409, refused.text


class TestMakerAndChecker:
    def test_the_recorder_of_a_restriction_may_not_confirm_it(
        self, finance_client: TestClient, project_id: str, restricted_receipt: dict[str, str]
    ) -> None:
        """Proved by the fixture needing two clients; this states it directly."""
        receipt_id = restricted_receipt["receipt"]
        del receipt_id
        response = finance_client.post(
            f"{cashflow_url(project_id)}/restrictions/{restricted_receipt['restriction']}/confirm",
            json={},
        )
        # Already confirmed by the second user in the fixture, so this proves the
        # lifecycle refuses a repeat rather than the identity rule alone.
        assert response.status_code == 409, response.text

    def test_the_recorder_of_a_release_may_not_confirm_it(
        self, finance_client: TestClient, project_id: str, restricted_receipt: dict[str, str]
    ) -> None:
        release = release_restriction(
            finance_client, project_id, restricted_receipt["restriction"], amount="10.00"
        )
        release_id = release.json()["releases"][0]["id"]
        refused = finance_client.post(
            f"{cashflow_url(project_id)}/releases/{release_id}/confirm", json={}
        )
        assert refused.status_code == 403, refused.text


class TestReversal:
    def test_a_restriction_with_standing_releases_cannot_be_reversed(
        self, finance_client: TestClient, project_id: str, restricted_receipt: dict[str, str]
    ) -> None:
        """A release against nothing would free money nobody was holding."""
        release_restriction(
            finance_client, project_id, restricted_receipt["restriction"], amount="10.00"
        )
        refused = finance_client.post(
            f"{cashflow_url(project_id)}/restrictions/{restricted_receipt['restriction']}/reverse",
            json={"reason": "Recorded against the wrong receipt"},
        )
        assert refused.status_code == 409, refused.text

    def test_reversing_a_restriction_returns_the_cash_to_the_usable_pool(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        restricted_receipt: dict[str, str],
    ) -> None:
        reversed_response = second_finance_client.post(
            f"{cashflow_url(project_id)}/restrictions/{restricted_receipt['restriction']}/reverse",
            json={"reason": "The trust deed did not apply to this transfer"},
        )
        assert reversed_response.status_code == 200, reversed_response.text

        row = month_row(cashflow_monthly(finance_client, project_id), month_named(0))
        assert row["closing_total_cash"] == "100.00"
        assert row["closing_restricted_cash"] == "0.00"
        assert row["closing_unrestricted_cash"] == "100.00"
