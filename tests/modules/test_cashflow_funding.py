"""How much cash must be raised, and by when.

A funding requirement is the number a developer takes to a bank, and it is worth
being exact about what question it answers: *given what is in the account today,
how far below zero does the next N days take us?*

Three things that question contains, each of which the arithmetic this family
guards used to get wrong.

**The money already in the bank.** A window that nets expected inflows against
expected outflows and calls the shortfall a requirement tells a project sitting
on ten million that it needs to raise five. Nobody would raise it — but the
number appears on a board pack, and the board asks why.

**Time inside the window.** Cash is not fungible across dates. A payment on day
ten funded by a receipt on day twenty leaves the window closing level and the
company unable to pay on day ten.

**Restricted cash is not cash.** Escrowed buyer money is on the balance sheet
and cannot pay a contractor, so it never opens a window.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.modules.conftest import (
    cashflow_summary,
    cashflow_url,
    confirm_receipt,
    contract_basis,
    cover_construction_forecast,
    create_cashflow_forecast,
    create_forecast,
    current_version_id,
    fixed_row,
    govern_cashflow_forecast,
    govern_forecast,
    month_named,
    plans_url,
    record_receipt,
    restrict_receipt,
    set_cashflow_line,
    write_schedule,
)

ZERO = Decimal("0.00")

#: What the construction forecast these tests pin has left to spend. Large
#: enough to push a window below zero, round enough to read the trough off.
BUILD_COST = Decimal("5000000.00")


def window(summary: dict[str, Any], days: int) -> dict[str, str]:
    row = next(
        (entry for entry in summary["funding_windows"] if entry["days"] == days),
        None,
    )
    assert row is not None, f"the summary must answer for {days} days"
    return row


@pytest.fixture
def build_cost(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    cost_codes: dict[str, str],
    active_budget: str,
) -> str:
    """A construction forecast in force with 5,000,000 left on hard cost.

    Large enough that a window can be pushed below zero by scheduling it, and
    round enough that the trough can be read without a calculator.
    """
    version_id = create_forecast(finance_client, project_id).json()["id"]
    cover_construction_forecast(
        finance_client, project_id, version_id, cost_codes, hard=str(BUILD_COST)
    )
    governed = govern_forecast(finance_client, cfo_client, project_id, version_id)
    assert governed.status_code == 200, governed.text
    return version_id


@pytest.fixture
def instalment_on_day_twenty(
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    active_sale: str,
    plan_id: str,
) -> Decimal:
    """The whole buyer schedule on one instalment, twenty days from today.

    Returned as its amount rather than asserted against a copied figure, so the
    window's arithmetic is stated against the contract this project actually has.
    """
    version_id = current_version_id(collections_client, project_id, plan_id)
    due = (date.today() + timedelta(days=20)).isoformat()
    written = write_schedule(
        collections_client,
        project_id,
        plan_id,
        version_id,
        [fixed_row(1, "1.000000", due)],
    )
    assert written.status_code == 200, written.text
    base = f"{plans_url(project_id)}/{plan_id}/versions/{version_id}"
    assert collections_client.post(f"{base}/submit", json={}).status_code == 200
    assert cfo_client.post(f"{base}/approve", json={"reason": "Terms reviewed"}).status_code == 200
    assert cfo_client.post(f"{base}/activate", json={}).status_code == 200
    return Decimal(contract_basis(collections_client, project_id, plan_id)["payable"])


def governed_cash_forecast(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    cost_codes: dict[str, str],
    *,
    opening_unrestricted_cash: str,
    opening_restricted_cash: str = "0.00",
    construction_this_month: str = "0.00",
) -> str:
    """A forecast in force from this month, with one construction figure in it.

    The rest of the pinned build cost is scheduled five months out, beyond every
    window this family asks about. A cashflow forecast has to account for all of
    it — that is what governance insists on — and leaving the balance inside the
    window would put a second number in the answer.
    """
    created = create_cashflow_forecast(
        finance_client,
        project_id,
        opening_unrestricted_cash=opening_unrestricted_cash,
        opening_restricted_cash=opening_restricted_cash,
        forecast_start_month=month_named(0),
        forecast_end_month=month_named(6),
    )
    assert created.status_code == 201, created.text
    identifier: str = created.json()["id"]
    for month, amount in (
        (month_named(0), construction_this_month),
        (month_named(5), str(BUILD_COST - Decimal(construction_this_month))),
    ):
        assert (
            set_cashflow_line(
                finance_client,
                project_id,
                identifier,
                period_month=month,
                source_kind="construction",
                category="construction",
                amount=amount,
                construction_cost_code_id=cost_codes["hard"],
            ).status_code
            == 200
        )
    activated = govern_cashflow_forecast(
        finance_client, cfo_client, project_id, identifier, cost_codes=cost_codes
    )
    assert activated.status_code == 200, activated.text
    return identifier


class TestAWindowOpensOnTheCashAlreadyHeld:
    def test_a_project_that_can_pay_from_its_own_balance_needs_nothing(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        build_cost: str,
    ) -> None:
        """Ten million held, five million to pay: the requirement is nothing.

        The failure this replaces reported five million, which is an instruction
        to raise debt against money the company already has — and somebody would
        have paid arrangement fees for it.
        """
        governed_cash_forecast(
            finance_client,
            cfo_client,
            project_id,
            cost_codes,
            opening_unrestricted_cash="10000000.00",
            construction_this_month="5000000.00",
        )
        thirty = window(cashflow_summary(finance_client, project_id), 30)
        assert Decimal(thirty["opening_unrestricted_cash"]) == Decimal("10000000.00")
        assert Decimal(thirty["outflows"]) == Decimal("5000000.00")
        assert Decimal(thirty["minimum_projected_unrestricted_cash"]) == Decimal("5000000.00")
        assert Decimal(thirty["funding_requirement"]) == ZERO

    def test_escrowed_cash_does_not_open_a_window(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        cfo_client: TestClient,
        collections_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        build_cost: str,
        collecting_sale: str,
    ) -> None:
        """Restricted money is on the balance sheet and cannot pay a contractor."""
        governed_cash_forecast(
            finance_client,
            cfo_client,
            project_id,
            cost_codes,
            opening_unrestricted_cash="1000000.00",
            construction_this_month="0.00",
        )
        receipt = record_receipt(
            collections_client,
            project_id,
            collecting_sale,
            "10000.00",
            receipt_date=date.today().isoformat(),
        )
        receipt_id = receipt.json()["id"]
        assert confirm_receipt(finance_client, project_id, receipt_id).status_code == 200
        before = Decimal(
            window(cashflow_summary(finance_client, project_id), 30)["opening_unrestricted_cash"]
        )
        assert before == Decimal("1010000.00"), "confirmed buyer cash is spendable"

        restricted = restrict_receipt(
            finance_client, project_id, receipt_id, restricted_amount="4000.00"
        )
        assert restricted.status_code == 201, restricted.text
        confirmed = second_finance_client.post(
            f"{cashflow_url(project_id)}/restrictions/{restricted.json()['id']}/confirm", json={}
        )
        assert confirmed.status_code == 200, confirmed.text

        after = window(cashflow_summary(finance_client, project_id), 30)
        assert Decimal(after["opening_unrestricted_cash"]) == before - Decimal("4000.00")


class TestTheTroughIsWhatHasToBeFunded:
    """A window that closes in credit can still be short in the middle of it.

    Cash is not fungible across dates. The amounts here are derived from the
    contract this project actually has rather than copied in, so the shape holds
    whatever the sale is worth: the outflow lands early and is half an instalment
    larger than the cash on hand, and the instalment arrives on day twenty.
    """

    def test_a_window_that_closes_in_credit_can_still_need_funding(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        build_cost: str,
        instalment_on_day_twenty: Decimal,
    ) -> None:
        """The closing position is the one number that cannot see the trough."""
        opening = Decimal("1000000.00")
        half = (instalment_on_day_twenty / 2).quantize(Decimal("0.01"))
        governed_cash_forecast(
            finance_client,
            cfo_client,
            project_id,
            cost_codes,
            opening_unrestricted_cash=str(opening),
            construction_this_month=str(opening + half),
        )
        thirty = window(cashflow_summary(finance_client, project_id), 30)

        assert Decimal(thirty["opening_unrestricted_cash"]) == opening
        assert Decimal(thirty["usable_inflows"]) == instalment_on_day_twenty
        assert Decimal(thirty["outflows"]) == opening + half
        assert Decimal(thirty["minimum_projected_unrestricted_cash"]) == -half
        assert Decimal(thirty["closing_projected_unrestricted_cash"]) == (
            instalment_on_day_twenty - half
        ), "the window ends in credit"
        assert Decimal(thirty["funding_requirement"]) == half, (
            "and still needs funding, because of where it goes in between"
        )

    def test_the_requirement_is_not_read_off_the_closing_position(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        build_cost: str,
        instalment_on_day_twenty: Decimal,
    ) -> None:
        """Stated on its own, because the two agreed before this and should not."""
        opening = Decimal("1000000.00")
        half = (instalment_on_day_twenty / 2).quantize(Decimal("0.01"))
        governed_cash_forecast(
            finance_client,
            cfo_client,
            project_id,
            cost_codes,
            opening_unrestricted_cash=str(opening),
            construction_this_month=str(opening + half),
        )
        thirty = window(cashflow_summary(finance_client, project_id), 30)
        closing = Decimal(thirty["closing_projected_unrestricted_cash"])
        assert closing > ZERO
        assert Decimal(thirty["funding_requirement"]) > ZERO
        assert Decimal(thirty["funding_requirement"]) != max(ZERO, -closing)


class TestTheWindowSeesTheMonthItStartsIn:
    def test_a_forecast_for_this_month_is_inside_the_next_thirty_days(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        build_cost: str,
    ) -> None:
        """The month has begun. What it expects to spend has not been spent.

        A window that only counted rows dated strictly after today missed every
        month-grained forecast for the month the report was taken in — which is
        the one month a thirty-day window is guaranteed to overlap.
        """
        governed_cash_forecast(
            finance_client,
            cfo_client,
            project_id,
            cost_codes,
            opening_unrestricted_cash="0.00",
            construction_this_month="750000.00",
        )
        thirty = window(cashflow_summary(finance_client, project_id), 30)
        assert Decimal(thirty["outflows"]) == Decimal("750000.00")
        assert Decimal(thirty["funding_requirement"]) == Decimal("750000.00")

    def test_every_window_answers_from_the_same_opening_balance(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        build_cost: str,
    ) -> None:
        """Thirty, sixty and ninety days all start from today's bank balance."""
        governed_cash_forecast(
            finance_client,
            cfo_client,
            project_id,
            cost_codes,
            opening_unrestricted_cash="250000.00",
            construction_this_month="0.00",
        )
        summary = cashflow_summary(finance_client, project_id)
        for days in (30, 60, 90):
            row = window(summary, days)
            assert Decimal(row["opening_unrestricted_cash"]) == Decimal("250000.00")
            assert row["from_date"] == date.today().isoformat()
            assert row["to_date"] == (date.today() + timedelta(days=days)).isoformat()
