"""NPV and IRR: the arithmetic, and the basis each of them is stated on.

The formulas are eight lines and they are tested here against cases whose
answers can be verified by hand. That is deliberate: a dependency computing them
in binary floating point would give an answer that disagrees with the ledger it
is quoting, and nobody would be able to say by how much.

The basis matters as much as the number. A project NPV and a levered one differ
by every financing flow, and a figure labelled only "NPV" invites the reader to
assume whichever they were expecting.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.modules.cashflow import calculator
from tests.modules.conftest import (
    cashflow_summary,
    create_cashflow_forecast,
    govern_cashflow_forecast,
    month_named,
)


class TestNetPresentValue:
    def test_a_series_that_discounts_to_exactly_zero(self) -> None:
        """Given / When / Then: -100, +55, +60.50 at 10% a period is 0.00.

        Verifiable without a calculator: 55 / 1.1 is 50 and 60.50 / 1.21 is 50,
        so the two discounted receipts exactly repay the 100. An answer of
        0.00000001 would mean the arithmetic had gone through a float.
        """
        npv = calculator.net_present_value(
            net_flows=[Decimal("-100.00"), Decimal("55.00"), Decimal("60.50")],
            rate_per_period=Decimal("0.10"),
        )
        assert npv == Decimal("0.00")

    def test_the_first_period_is_undiscounted(self) -> None:
        """t = 0 is the first forecast period, so nothing is discounted twice."""
        npv = calculator.net_present_value(
            net_flows=[Decimal("100.00")], rate_per_period=Decimal("0.10")
        )
        assert npv == Decimal("100.00")

    def test_a_zero_rate_is_the_plain_sum(self) -> None:
        npv = calculator.net_present_value(
            net_flows=[Decimal("-100.00"), Decimal("30.00"), Decimal("90.00")],
            rate_per_period=Decimal("0.00"),
        )
        assert npv == Decimal("20.00")

    def test_a_rate_that_divides_by_zero_is_refused(self) -> None:
        with pytest.raises(ValueError, match="divides by zero"):
            calculator.net_present_value(net_flows=[Decimal("1.00")], rate_per_period=Decimal("-1"))


class TestInternalRateOfReturn:
    def test_a_conventional_series_returns_its_periodic_rate(self) -> None:
        """-100 then +110 is 10% a period, and nothing about that is approximate."""
        result = calculator.internal_rate_of_return(
            equity_flows=[Decimal("-100.00"), Decimal("110.00")]
        )
        assert result.unavailable_reason is None
        assert result.rate_per_period == Decimal("0.100000")

    def test_a_longer_conventional_series_solves_too(self) -> None:
        """-100, +60, +60 is a shade over 13% a period."""
        result = calculator.internal_rate_of_return(
            equity_flows=[Decimal("-100.00"), Decimal("60.00"), Decimal("60.00")]
        )
        assert result.unavailable_reason is None
        assert result.rate_per_period is not None
        assert Decimal("0.13") < result.rate_per_period < Decimal("0.14")

    def test_all_positive_has_no_investment_to_return_on(self) -> None:
        result = calculator.internal_rate_of_return(
            equity_flows=[Decimal("100.00"), Decimal("110.00")]
        )
        assert result.rate_per_period is None
        assert result.unavailable_reason == calculator.IRR_NO_INVESTMENT

    def test_all_negative_has_no_return(self) -> None:
        result = calculator.internal_rate_of_return(
            equity_flows=[Decimal("-100.00"), Decimal("-110.00")]
        )
        assert result.rate_per_period is None
        assert result.unavailable_reason == calculator.IRR_NO_RETURN

    def test_two_sign_changes_are_refused_rather_than_answered(self) -> None:
        """Several rates satisfy the equation and none of them is *the* return."""
        result = calculator.internal_rate_of_return(
            equity_flows=[Decimal("-100.00"), Decimal("300.00"), Decimal("-250.00")]
        )
        assert result.rate_per_period is None
        assert result.unavailable_reason == calculator.IRR_AMBIGUOUS

    def test_it_never_answers_zero_or_a_nonsense_number(self) -> None:
        """The three values somebody would otherwise put in a board pack."""
        for flows in (
            [Decimal("100.00")],
            [Decimal("-100.00")],
            [Decimal("0.00"), Decimal("0.00")],
        ):
            result = calculator.internal_rate_of_return(equity_flows=flows)
            assert result.rate_per_period is None
            assert result.unavailable_reason is not None


class TestTheBasisIsStated:
    @pytest.fixture
    def cash_forecast(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        flat_construction_forecast: str,
    ) -> str:
        created = create_cashflow_forecast(
            finance_client,
            project_id,
            discount_rate_per_period="0.010000",
            forecast_start_month=month_named(0),
            forecast_end_month=month_named(6),
        )
        assert created.status_code == 201, created.text
        identifier: str = created.json()["id"]
        assert (
            govern_cashflow_forecast(finance_client, cfo_client, project_id, identifier).status_code
            == 200
        )
        return identifier

    def test_the_response_names_what_the_npv_was_computed_on(
        self, finance_client: TestClient, project_id: str, cash_forecast: str
    ) -> None:
        """ "NPV" alone lets the reader assume whichever basis they expected."""
        returns = cashflow_summary(finance_client, project_id)["returns"]
        assert returns["npv_basis"] == "project_operating_and_development"
        assert returns["equity_irr_basis"] == "equity_investor_sign_convention"

    def test_the_forecast_rate_is_the_one_used(
        self, finance_client: TestClient, project_id: str, cash_forecast: str
    ) -> None:
        """Per period, and no annual figure is converted behind the reader's back."""
        returns = cashflow_summary(finance_client, project_id)["returns"]
        assert returns["discount_rate_per_period"] == "0.010000"

    def test_financing_cash_is_absent_from_the_project_npv(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        currency_id: str,
        cash_forecast: str,
    ) -> None:
        """Equity is how a project was funded, not what it earned.

        Including it would make a project look better the more expensively it
        was financed, which is the wrong direction for every decision an NPV is
        used to take.
        """
        from tests.modules.conftest import cashflow_url, record_financing

        before = cashflow_summary(finance_client, project_id)["returns"]
        movement = record_financing(finance_client, project_id, currency_id, amount="1000000.00")
        confirmed = second_finance_client.post(
            f"{cashflow_url(project_id)}/financing-movements/{movement.json()['id']}/confirm",
            json={},
        )
        assert confirmed.status_code == 200, confirmed.text

        after = cashflow_summary(finance_client, project_id)["returns"]
        assert after["net_present_value"] == before["net_present_value"]
        assert after["net_project_cashflow"] == before["net_project_cashflow"]
        assert after["equity_contributed"] == "1000000.00"
