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

import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.cashflow import calculator, service
from app.modules.projects.models import Project
from tests.modules.conftest import (
    cashflow_summary,
    cashflow_url,
    create_cashflow_forecast,
    govern_cashflow_forecast,
    month_named,
    record_financing,
    set_cashflow_line,
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
        cost_codes: dict[str, str],
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
            govern_cashflow_forecast(
                finance_client, cfo_client, project_id, identifier, cost_codes=cost_codes
            ).status_code
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


class TestTheReturnIsOnTheSameCashAsTheBridge:
    """One rule decides what is actual and what is forecast. Returns does not get a second.

    A return computed on a wider set of rows than the cash bridge is a return on
    a different project, and the two numbers sit on one screen. The version this
    class guards swept every equity row in the register regardless of basis, so
    a contribution that was forecast and then actually received counted twice in
    the IRR while counting once in the bridge — and the disagreement was largest
    on the figure a board reads first.
    """

    @pytest.fixture
    def equity_forecast(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        flat_construction_forecast: str,
    ) -> str:
        """A forecast in force whose only financing is equity, so the two are comparable.

        The bridge reports financing by direction rather than by type, so a
        project carrying debt as well would make "the bridge's equity cash" a
        figure no response states. Here the two are the same rows.
        """
        created = create_cashflow_forecast(
            finance_client,
            project_id,
            forecast_start_month=month_named(0),
            forecast_end_month=month_named(6),
        )
        assert created.status_code == 201, created.text
        identifier: str = created.json()["id"]
        assert (
            set_cashflow_line(
                finance_client,
                project_id,
                identifier,
                period_month=month_named(2),
                source_kind="financing",
                category="equity_contribution",
                amount="400000.00",
                flow_direction="inflow",
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

    def test_equity_received_is_counted_once_not_twice(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        currency_id: str,
        equity_forecast: str,
    ) -> None:
        """500,000 contributed and 400,000 still forecast. Contributed is 900,000.

        Not 1,300,000, which is what counting the actual against a forecast
        series nobody filtered produces — and not 500,000 either: the money
        expected in two months' time is part of what the investor will have put
        in, and an IRR that ignored it would understate the outlay.
        """
        movement = record_financing(finance_client, project_id, currency_id, amount="500000.00")
        assert movement.status_code == 201, movement.text
        confirmed = second_finance_client.post(
            f"{cashflow_url(project_id)}/financing-movements/{movement.json()['id']}/confirm",
            json={},
        )
        assert confirmed.status_code == 200, confirmed.text

        returns = cashflow_summary(finance_client, project_id)["returns"]
        assert Decimal(returns["equity_contributed"]) == Decimal("900000.00")
        assert Decimal(returns["equity_net"]) == Decimal("-900000.00")

    def test_the_irr_series_is_the_bridge_s_equity_cash_with_the_sign_turned_round(
        self,
        db: Session,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        currency_id: str,
        equity_forecast: str,
    ) -> None:
        """Month by month, the series an IRR is computed on against the bridge itself.

        The claim an IRR makes is unverifiable from its own output — it is one
        number derived from a series nobody can see — so the series is compared
        here to the months the bridge published. Anything that changed one and
        not the other would show up as a month that disagrees.
        """
        movement = record_financing(finance_client, project_id, currency_id, amount="500000.00")
        assert (
            second_finance_client.post(
                f"{cashflow_url(project_id)}/financing-movements/{movement.json()['id']}/confirm",
                json={},
            ).status_code
            == 200
        )

        project = db.get(Project, uuid.UUID(project_id))
        assert project is not None
        as_of = date.today()
        version = service.active_forecast(db, project_id=project.id)
        rows = service.collect_source_rows(db, project=project, version=version, as_of=as_of)
        positions = service.monthly_positions(db, project=project, version=version, as_of=as_of)
        flows = service.equity_flows_for(positions, rows, as_of=as_of)

        assert len(flows) == len(positions)
        for position, flow in zip(positions, flows, strict=True):
            bridge_equity = (
                position.financing_actual_inflows
                + position.financing_forecast_inflows
                - position.financing_actual_outflows
                - position.financing_forecast_outflows
            )
            assert flow == -bridge_equity, (
                f"{position.period_month}: the bridge reports {bridge_equity} of equity "
                f"cash and the IRR was given {flow}"
            )
        assert sum(flows) == Decimal("-900000.00")

    def test_the_return_is_stated_over_the_months_the_bridge_covers(
        self,
        finance_client: TestClient,
        project_id: str,
        equity_forecast: str,
    ) -> None:
        """The equity a return is computed on is the equity the bridge published.

        Stated as its own assertion because the range is part of the answer: a
        return computed over a horizon the response does not name is a number
        the reader cannot check.
        """
        summary = cashflow_summary(finance_client, project_id)
        assert summary["basis"]["from_month"] == month_named(0)
        assert summary["basis"]["to_month"] == month_named(6)
        assert Decimal(summary["returns"]["equity_contributed"]) == Decimal("400000.00")
        assert Decimal(summary["returns"]["equity_distributed"]) == Decimal("0.00")
