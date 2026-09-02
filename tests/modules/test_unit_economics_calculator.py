"""The unit economics arithmetic, tested without a database.

Two things are proved here and nothing else, because nothing else is in the
module: that dividing a pool loses nothing, and that the profit layers subtract
what they say they subtract in the order they say they do.

These are the rules a finance director would argue about, which is exactly why
they are testable without building a project, a unit, a contract and a price
first. A test that needed all of that to check ``100 / 3`` would be a test
nobody runs while changing the arithmetic.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.modules.unit_economics.calculator import (
    AllocationError,
    CostInputs,
    DriverLine,
    allocate,
    portfolio,
    profitability,
)

UNITS = [uuid.UUID(int=index) for index in range(1, 9)]


def drivers(*values: str) -> list[DriverLine]:
    return [
        DriverLine(unit_id=UNITS[index], driver_value=Decimal(value))
        for index, value in enumerate(values)
    ]


def amounts(lines: list) -> list[str]:
    return [str(line.allocated_amount) for line in lines]


class TestDividingAPool:
    """Given one amount and a set of drivers, when the pool is allocated."""

    def test_it_divides_in_proportion_to_the_drivers(self) -> None:
        """The weighted-area case: 50 / 30 / 20 of a hundred."""
        lines = allocate(pool_amount=Decimal("100.00"), drivers=drivers("50", "30", "20"))
        assert amounts(lines) == ["50.00", "30.00", "20.00"]

    def test_revenue_value_divides_the_same_way(self) -> None:
        lines = allocate(pool_amount=Decimal("100.00"), drivers=drivers("200", "300", "500"))
        assert amounts(lines) == ["20.00", "30.00", "50.00"]

    def test_a_custom_driver_is_just_another_denominator(self) -> None:
        lines = allocate(pool_amount=Decimal("100.00"), drivers=drivers("1", "1", "2"))
        assert amounts(lines) == ["25.00", "25.00", "50.00"]

    def test_unit_count_splits_evenly_and_still_reconciles(self) -> None:
        """100 across 3. The case that has no exact answer in two decimals."""
        lines = allocate(pool_amount=Decimal("100.00"), drivers=drivers("1", "1", "1"))
        assert sum(line.allocated_amount for line in lines) == Decimal("100.00")
        assert sorted(amounts(lines)) == ["33.33", "33.33", "33.34"]

    def test_exactly_one_unit_carries_the_residual(self) -> None:
        lines = allocate(pool_amount=Decimal("100.00"), drivers=drivers("1", "1", "1"))
        assert sum(1 for line in lines if line.is_rounding_recipient) == 1

    def test_the_residual_recipient_is_stable_across_recalculation(self) -> None:
        """Same inputs, same allocation. An allocation that moves cannot be re-approved."""
        first = allocate(pool_amount=Decimal("100.00"), drivers=drivers("50", "30", "20"))
        second = allocate(pool_amount=Decimal("100.00"), drivers=drivers("50", "30", "20"))
        assert amounts(first) == amounts(second)
        assert [line.is_rounding_recipient for line in first] == [
            line.is_rounding_recipient for line in second
        ]

    def test_the_residual_goes_to_the_largest_driver(self) -> None:
        lines = allocate(pool_amount=Decimal("100.00"), drivers=drivers("1", "1", "1.0001"))
        recipient = next(line for line in lines if line.is_rounding_recipient)
        assert recipient.driver_value == Decimal("1.0001")

    @pytest.mark.parametrize(
        "pool",
        ["0.01", "0.03", "1000000.01", "999999999.99", "7.77", "123456.78"],
    )
    def test_every_pool_reconciles_exactly(self, pool: str) -> None:
        """Not within a cent. Exactly, at the scale the money column stores."""
        for shape in (("1", "1", "1"), ("7", "11", "13"), ("1", "0", "2"), ("3", "3", "3", "3")):
            lines = allocate(pool_amount=Decimal(pool), drivers=drivers(*shape))
            assert sum(line.allocated_amount for line in lines) == Decimal(pool)

    def test_a_hostile_fraction_still_reconciles(self) -> None:
        """Seven units, a prime pool, and no clean division anywhere in it."""
        lines = allocate(
            pool_amount=Decimal("1000003.33"),
            drivers=drivers("13", "17", "19", "23", "29", "31", "37"),
        )
        assert sum(line.allocated_amount for line in lines) == Decimal("1000003.33")

    def test_a_zero_denominator_is_refused(self) -> None:
        """All-zero drivers cannot divide anything, and zeros would say they did."""
        with pytest.raises(AllocationError) as failure:
            allocate(pool_amount=Decimal("100.00"), drivers=drivers("0", "0"))
        assert "nothing to divide" in str(failure.value)

    def test_an_empty_population_is_refused(self) -> None:
        with pytest.raises(AllocationError):
            allocate(pool_amount=Decimal("100.00"), drivers=[])

    def test_a_zero_driver_takes_nothing_while_others_take_everything(self) -> None:
        lines = allocate(pool_amount=Decimal("90.00"), drivers=drivers("0", "1", "2"))
        assert amounts(lines) == ["0.00", "30.00", "60.00"]

    def test_a_zero_pool_allocates_zero_to_everyone(self) -> None:
        """Finance recording a deliberate nil is not the same as leaving it out."""
        lines = allocate(pool_amount=Decimal("0.00"), drivers=drivers("50", "30", "20"))
        assert amounts(lines) == ["0.00", "0.00", "0.00"]


class TestTheProfitLayers:
    """Given revenue and costs, when the layers are applied in order."""

    def test_the_worked_example(self) -> None:
        """The full appraisal, subtotal by subtotal."""
        result = profitability(
            revenue=Decimal("200000.00"),
            costs=CostInputs(
                direct_cost=Decimal("5000.00"),
                land_cost=Decimal("20000.00"),
                hard_cost=Decimal("80000.00"),
                soft_cost=Decimal("15000.00"),
                variable_selling_cost=Decimal("4000.00"),
                commercial_seller_cost=Decimal("3000.00"),
                allocated_finance_cost=Decimal("8000.00"),
            ),
        )
        assert result.development_cost == Decimal("120000.00")
        assert result.gross_profit == Decimal("80000.00")
        assert result.commercial_cost == Decimal("7000.00")
        assert result.contribution_profit == Decimal("73000.00")
        assert result.finance_cost == Decimal("8000.00")
        assert result.profit_after_finance == Decimal("65000.00")
        assert result.total_cost == Decimal("135000.00")
        assert result.margin_fraction == Decimal("0.325000")
        assert result.return_on_cost_fraction == Decimal("0.481481")

    def test_deal_finance_cost_lands_on_the_finance_layer(self) -> None:
        """A financing subsidy is a finance cost, not a commercial one."""
        result = profitability(
            revenue=Decimal("100000.00"),
            costs=CostInputs(
                land_cost=Decimal("10000.00"),
                commercial_seller_cost=Decimal("2000.00"),
                deal_finance_cost=Decimal("3000.00"),
            ),
        )
        assert result.commercial_cost == Decimal("2000.00")
        assert result.finance_cost == Decimal("3000.00")
        assert result.contribution_profit == Decimal("88000.00")
        assert result.profit_after_finance == Decimal("85000.00")

    def test_a_loss_is_reported_as_a_loss(self) -> None:
        """Revenue 100, cost 120. Nothing is clamped to zero."""
        result = profitability(
            revenue=Decimal("100.00"), costs=CostInputs(hard_cost=Decimal("120.00"))
        )
        assert result.profit_after_finance == Decimal("-20.00")
        assert result.margin_fraction == Decimal("-0.200000")
        assert result.return_on_cost_fraction == Decimal("-0.166667")

    def test_zero_cost_gives_profit_but_no_return_on_cost(self) -> None:
        """There is no such thing as an infinite return, so the answer is nothing."""
        result = profitability(revenue=Decimal("100.00"), costs=CostInputs())
        assert result.profit_after_finance == Decimal("100.00")
        assert result.margin_fraction == Decimal("1.000000")
        assert result.return_on_cost_fraction is None

    def test_zero_revenue_gives_no_margin_rather_than_zero_margin(self) -> None:
        """Undefined and zero are different facts and must not print the same."""
        result = profitability(
            revenue=Decimal("0.00"), costs=CostInputs(hard_cost=Decimal("50.00"))
        )
        assert result.profit_after_finance == Decimal("-50.00")
        assert result.margin_fraction is None
        assert result.gross_margin_fraction is None
        assert result.contribution_margin_fraction is None

    def test_every_subtotal_is_the_sum_of_its_parts(self) -> None:
        result = profitability(
            revenue=Decimal("500000.00"),
            costs=CostInputs(
                direct_cost=Decimal("1111.11"),
                land_cost=Decimal("2222.22"),
                hard_cost=Decimal("3333.33"),
                soft_cost=Decimal("4444.44"),
                variable_selling_cost=Decimal("555.55"),
                commercial_seller_cost=Decimal("666.66"),
                allocated_finance_cost=Decimal("777.77"),
                deal_finance_cost=Decimal("888.88"),
            ),
        )
        assert result.development_cost == Decimal("11111.10")
        assert result.commercial_cost == Decimal("1222.21")
        assert result.finance_cost == Decimal("1666.65")
        assert result.total_cost == Decimal("13999.96")
        assert result.revenue - result.total_cost == result.profit_after_finance, (
            "the layers must not lose money between them"
        )


class TestAddingUnitsUp:
    """Given several units, when a project total is taken."""

    def test_the_project_margin_is_weighted_not_averaged(self) -> None:
        """A big thin unit and a small fat one do not average to the truth."""
        big = profitability(
            revenue=Decimal("1000000.00"), costs=CostInputs(hard_cost=Decimal("950000.00"))
        )
        small = profitability(
            revenue=Decimal("100000.00"), costs=CostInputs(hard_cost=Decimal("50000.00"))
        )
        totals = portfolio([big, small])
        assert totals.revenue_total == Decimal("1100000.00")
        assert totals.profit_total == Decimal("100000.00")
        # Weighted: 100,000 / 1,100,000. The average of 5% and 50% would be 27.5%.
        assert totals.margin_fraction == Decimal("0.090909")

    def test_the_project_return_on_cost_is_weighted_too(self) -> None:
        one = profitability(
            revenue=Decimal("200.00"), costs=CostInputs(hard_cost=Decimal("100.00"))
        )
        two = profitability(
            revenue=Decimal("400.00"), costs=CostInputs(hard_cost=Decimal("100.00"))
        )
        totals = portfolio([one, two])
        assert totals.total_cost_total == Decimal("200.00")
        assert totals.profit_total == Decimal("400.00")
        assert totals.return_on_cost_fraction == Decimal("2.000000")

    def test_an_empty_portfolio_reports_nothing_rather_than_zero_margin(self) -> None:
        totals = portfolio([])
        assert totals.unit_count == 0
        assert totals.revenue_total == Decimal("0.00")
        assert totals.margin_fraction is None
        assert totals.return_on_cost_fraction is None
