"""Cash this module owns, and the second person who says it moved.

Recording is not paying. A recorded movement is Finance preparing a
disbursement; a confirmed one is money that has left, and the person who
confirms it is never the person who recorded it — compared by identifier,
because one user holding Finance and Approver / CFO is one pair of eyes.

The category set has no construction entry, deliberately. Construction cash
belongs to PR-MVP-09 and is read from there; a category here that could hold one
would let the same disbursement be recorded twice with nothing to detect it, and
the project would report a build that cost double.
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
    cashflow_url,
    create_cashflow_forecast,
    govern_cashflow_forecast,
    month_named,
    record_development,
)


def outflow_in(monthly: dict[str, object], month: str) -> Decimal:
    months = monthly["months"]
    assert isinstance(months, list)
    row = next((entry for entry in months if entry["period_month"] == month), None)
    return Decimal(row["development_actual_outflows"]) if row else Decimal("0.00")


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
        forecast_start_month=month_named(-2),
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


class TestRecordingIsNotPaying:
    def test_a_recorded_movement_is_not_yet_cash(
        self,
        finance_client: TestClient,
        project_id: str,
        currency_id: str,
        cash_forecast: str,
    ) -> None:
        """Given / When / Then: 50,000 recorded, and the cash position does not move."""
        recorded = record_development(finance_client, project_id, currency_id)
        assert recorded.status_code == 201, recorded.text
        assert recorded.json()["status"] == "recorded"
        assert recorded.json()["counts_as_cash"] is False
        assert outflow_in(cashflow_monthly(finance_client, project_id), month_named(0)) == Decimal(
            "0.00"
        )

    def test_confirmation_by_a_second_person_makes_it_cash(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        currency_id: str,
        cash_forecast: str,
    ) -> None:
        movement_id = record_development(finance_client, project_id, currency_id).json()["id"]
        confirmed = second_finance_client.post(
            f"{cashflow_url(project_id)}/development-movements/{movement_id}/confirm",
            json={},
        )
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["counts_as_cash"] is True
        assert outflow_in(cashflow_monthly(finance_client, project_id), month_named(0)) == Decimal(
            "50000.00"
        )

    def test_the_recorder_may_not_confirm_their_own_movement(
        self,
        finance_client: TestClient,
        project_id: str,
        currency_id: str,
        cash_forecast: str,
    ) -> None:
        """A role check would let one user holding two roles pay themselves."""
        movement_id = record_development(finance_client, project_id, currency_id).json()["id"]
        refused = finance_client.post(
            f"{cashflow_url(project_id)}/development-movements/{movement_id}/confirm",
            json={},
        )
        assert refused.status_code == 403, refused.text

    def test_a_movement_cannot_be_dated_in_the_future(
        self,
        finance_client: TestClient,
        project_id: str,
        currency_id: str,
        cash_forecast: str,
    ) -> None:
        """A movement is a record of something that happened."""
        refused = record_development(
            finance_client,
            project_id,
            currency_id,
            movement_date=(date.today() + timedelta(days=1)).isoformat(),
        )
        assert refused.status_code == 422, refused.text


class TestConstructionCashIsNotRecordedHere:
    def test_there_is_no_construction_category(
        self,
        finance_client: TestClient,
        project_id: str,
        currency_id: str,
        cash_forecast: str,
    ) -> None:
        """The escape hatch that would let one payment be counted twice."""
        refused = record_development(
            finance_client, project_id, currency_id, category="construction"
        )
        assert refused.status_code == 422, refused.text

    def test_the_open_api_schema_lists_the_closed_set(self) -> None:
        from app.main import create_app

        schema = create_app().openapi()
        categories = schema["components"]["schemas"]["DevelopmentMovementCreate"]["properties"][
            "category"
        ]["enum"]
        assert "construction" not in categories
        assert "consultants" in categories


class TestReversal:
    def test_a_reversal_removes_it_from_the_current_position(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        currency_id: str,
        cash_forecast: str,
    ) -> None:
        movement_id = record_development(finance_client, project_id, currency_id).json()["id"]
        second_finance_client.post(
            f"{cashflow_url(project_id)}/development-movements/{movement_id}/confirm",
            json={},
        )
        reversed_response = second_finance_client.post(
            f"{cashflow_url(project_id)}/development-movements/{movement_id}/reverse",
            json={"reason": "Paid against the wrong project"},
        )
        assert reversed_response.status_code == 200, reversed_response.text
        assert outflow_in(cashflow_monthly(finance_client, project_id), month_named(0)) == Decimal(
            "0.00"
        )

    def test_a_position_taken_before_the_reversal_still_carries_it(
        self,
        db: Session,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        currency_id: str,
        cash_forecast: str,
    ) -> None:
        """History is not rewritten by a decision taken after it.

        Confirmed a fortnight ago, reversed today. A position taken five days ago
        still carries it, because it was standing then; today's position does
        not, because it is not standing now. The two answers differ on purpose.
        """
        spent_on = date.today() - timedelta(days=20)
        movement = record_development(
            finance_client, project_id, currency_id, movement_date=spent_on.isoformat()
        )
        movement_id = movement.json()["id"]
        second_finance_client.post(
            f"{cashflow_url(project_id)}/development-movements/{movement_id}/confirm",
            json={},
        )
        backdate(
            db,
            table="cashflow_development_movements",
            row_id=movement_id,
            confirmed_at=at(date.today() - timedelta(days=14)),
        )
        second_finance_client.post(
            f"{cashflow_url(project_id)}/development-movements/{movement_id}/reverse",
            json={"reason": "Duplicate"},
        )

        month = spent_on.replace(day=1).isoformat()
        earlier = cashflow_monthly(
            finance_client,
            project_id,
            as_of=(date.today() - timedelta(days=5)).isoformat(),
        )
        assert outflow_in(earlier, month) == Decimal("50000.00")
        assert outflow_in(cashflow_monthly(finance_client, project_id), month) == Decimal("0.00")
