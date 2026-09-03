"""The construction arithmetic, proved on exact decimals.

No database and no fixtures: every figure here is reproducible from its inputs,
which is the property the calculator exists to have. If one of these fails, a
certificate somebody signed says a different number from the one the system
would derive for it today.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.construction import calculator

D = Decimal


class TestRetention:
    def test_retention_is_exact_at_ten_percent(self) -> None:
        """Given / When / Then: 200,000 at 10% withholds exactly 20,000."""
        assert calculator.retention_held(
            current_work_ex_tax=D("200000.00"), retention_rate_fraction=D("0.100000")
        ) == D("20000.00")

    def test_retention_rounds_half_up_once(self) -> None:
        """A rate that lands between cents rounds once, at the money scale."""
        assert calculator.retention_held(
            current_work_ex_tax=D("333.33"), retention_rate_fraction=D("0.075000")
        ) == D("25.00")

    def test_no_retention_rate_withholds_nothing(self) -> None:
        assert calculator.retention_held(
            current_work_ex_tax=D("100000.00"), retention_rate_fraction=D("0.000000")
        ) == D("0.00")


class TestCertificateNetDue:
    """The worked example from the module's own specification, end to end."""

    def test_the_money_regression(self) -> None:
        """Given a 200,000 valuation with 10% retention, 30,000 tax, 20,000
        advance recovery and 5,000 other deductions, when the certificate is
        laid out, then net due is exactly 185,000."""
        amounts = calculator.certificate_amounts(
            current_work_ex_tax=D("200000.00"),
            retention_rate_fraction=D("0.100000"),
            retention_release=D("0.00"),
            advance_recovery=D("20000.00"),
            other_deductions=D("5000.00"),
            tax=D("30000.00"),
        )
        assert amounts.retention_held == D("20000.00")
        assert amounts.net_due == D("185000.00")

    def test_retention_release_adds_back(self) -> None:
        """A release is money returning to the vendor, so it raises net due."""
        amounts = calculator.certificate_amounts(
            current_work_ex_tax=D("100000.00"),
            retention_rate_fraction=D("0.100000"),
            retention_release=D("15000.00"),
            advance_recovery=D("0.00"),
            other_deductions=D("0.00"),
            tax=D("0.00"),
        )
        assert amounts.retention_held == D("10000.00")
        assert amounts.net_due == D("105000.00")

    def test_deductions_can_drive_net_due_negative(self) -> None:
        """The calculator reports it; the service is what refuses to certify it.

        Keeping the refusal in the service and the arithmetic here is deliberate:
        a calculator that clamped at zero would hide the fact that the inputs do
        not make a payment certificate.
        """
        amounts = calculator.certificate_amounts(
            current_work_ex_tax=D("10000.00"),
            retention_rate_fraction=D("0.100000"),
            retention_release=D("0.00"),
            advance_recovery=D("9000.00"),
            other_deductions=D("2000.00"),
            tax=D("0.00"),
        )
        assert amounts.net_due == D("-2000.00")

    def test_one_cent_survives(self) -> None:
        amounts = calculator.certificate_amounts(
            current_work_ex_tax=D("0.01"),
            retention_rate_fraction=D("0.000000"),
            retention_release=D("0.00"),
            advance_recovery=D("0.00"),
            other_deductions=D("0.00"),
            tax=D("0.00"),
        )
        assert amounts.net_due == D("0.01")

    def test_a_very_large_valuation_is_exact(self) -> None:
        """Nine figures and two decimals, with no float anywhere near it."""
        amounts = calculator.certificate_amounts(
            current_work_ex_tax=D("987654321.99"),
            retention_rate_fraction=D("0.050000"),
            retention_release=D("0.00"),
            advance_recovery=D("0.00"),
            other_deductions=D("0.00"),
            tax=D("0.00"),
        )
        assert amounts.retention_held == D("49382716.10")
        assert amounts.net_due == D("938271605.89")


class TestCommitment:
    def test_a_positive_variation_raises_the_commitment(self) -> None:
        assert calculator.revised_commitment(
            original_amount=D("800000.00"), approved_variation_delta=D("100000.00")
        ) == D("900000.00")

    def test_a_negative_variation_lowers_it(self) -> None:
        """An omission is a signed line, not a separate kind of record."""
        assert calculator.revised_commitment(
            original_amount=D("800000.00"), approved_variation_delta=D("-40000.00")
        ) == D("760000.00")

    def test_headroom_counts_contingency_as_available(self) -> None:
        """An approved reserve is money the business has already authorised."""
        assert calculator.headroom(
            approved_budget=D("1000000.00"),
            contingency=D("100000.00"),
            committed=D("900000.00"),
        ) == D("200000.00")

    def test_headroom_goes_negative_rather_than_clamping(self) -> None:
        """A cost code that is over its authorisation says so.

        Clamping at zero would report "no room left" for a code that is 250,000
        beyond its budget, which is the same sentence as one that is exactly at
        it — and only one of those is a problem.
        """
        assert calculator.headroom(
            approved_budget=D("1000000.00"), contingency=D("0.00"), committed=D("1250000.00")
        ) == D("-250000.00")


class TestEstimateAtCompletion:
    def test_eac_is_certified_plus_what_is_left(self) -> None:
        assert calculator.estimate_at_completion(
            certified_to_date=D("200000.00"), forecast_remaining=D("650000.00")
        ) == D("850000.00")

    def test_positive_variance_is_over_budget(self) -> None:
        """The sign convention, stated once and asserted here.

        A screen that inverted this would tell a reader a project running
        150,000 over is running 150,000 under.
        """
        assert calculator.variance_at_completion(
            estimate_at_completion=D("1150000.00"), control_budget=D("1000000.00")
        ) == D("150000.00")

    def test_negative_variance_is_under_budget(self) -> None:
        assert calculator.variance_at_completion(
            estimate_at_completion=D("850000.00"), control_budget=D("1000000.00")
        ) == D("-150000.00")


class TestCostCodePosition:
    def test_forecast_below_commitment_is_flagged_not_corrected(self) -> None:
        """Given a forecast of 850,000 against a commitment of 900,000, when the
        position is assembled, then the estimate stays at 850,000 and the gap is
        reported.

        Raising the estimate to the commitment would be the system overruling
        Finance's judgement, and it would hide the question of which of the two
        is wrong.
        """
        position = calculator.cost_code_position(
            approved_budget=D("1000000.00"),
            contingency=D("0.00"),
            revised_commitment_amount=D("900000.00"),
            certified_to_date=D("200000.00"),
            forecast_remaining=D("650000.00"),
        )
        assert position.estimate_at_completion == D("850000.00")
        assert position.forecast_below_commitment is True
        assert position.uncovered_commitment == D("50000.00")

    def test_a_forecast_above_commitment_raises_no_flag(self) -> None:
        position = calculator.cost_code_position(
            approved_budget=D("1000000.00"),
            contingency=D("0.00"),
            revised_commitment_amount=D("900000.00"),
            certified_to_date=D("200000.00"),
            forecast_remaining=D("750000.00"),
        )
        assert position.estimate_at_completion == D("950000.00")
        assert position.forecast_below_commitment is False
        assert position.uncovered_commitment == D("0.00")

    def test_the_whole_position_reconciles(self) -> None:
        """Every derived figure in one position agrees with its own inputs."""
        position = calculator.cost_code_position(
            approved_budget=D("750000.00"),
            contingency=D("50000.00"),
            revised_commitment_amount=D("700000.00"),
            certified_to_date=D("310000.00"),
            forecast_remaining=D("420000.00"),
        )
        assert position.control_budget == D("800000.00")
        assert position.estimate_at_completion == D("730000.00")
        assert position.variance_at_completion == D("-70000.00")
        assert position.headroom == D("100000.00")


class TestRetentionAndAdvancePositions:
    def test_retention_outstanding_is_held_less_released(self) -> None:
        assert calculator.retention_outstanding(held=D("50000.00"), released=D("30000.00")) == D(
            "20000.00"
        )

    def test_advance_outstanding_is_paid_less_recovered(self) -> None:
        """Paid, not entitled. An entitlement nobody drew down is not a debt."""
        assert calculator.advance_outstanding(paid=D("100000.00"), recovered=D("20000.00")) == D(
            "80000.00"
        )


class TestReconciliation:
    def test_an_exact_match_passes(self) -> None:
        check = calculator.equality_check(
            key="contract_lines",
            label="Contract lines against header",
            amount=D("800000.00"),
            expected=D("800000.00"),
        )
        assert check.ok is True
        assert check.variance == D("0.00")

    def test_one_cent_out_fails(self) -> None:
        """No tolerance anywhere. A tolerance is a rounding error somebody
        decided to stop noticing."""
        check = calculator.equality_check(
            key="contract_lines",
            label="Contract lines against header",
            amount=D("800000.01"),
            expected=D("800000.00"),
        )
        assert check.ok is False
        assert check.variance == D("0.01")

    def test_a_limit_check_allows_equality(self) -> None:
        check = calculator.limit_check(
            key="certified",
            label="Certified against commitment",
            amount=D("900000.00"),
            limit=D("900000.00"),
        )
        assert check.ok is True

    def test_a_limit_check_refuses_one_cent_over(self) -> None:
        check = calculator.limit_check(
            key="certified",
            label="Certified against commitment",
            amount=D("900000.01"),
            limit=D("900000.00"),
        )
        assert check.ok is False


class TestNoFloatEverEnters:
    @pytest.mark.parametrize(
        "value",
        [D("0.00"), D("0.01"), D("123456789.99"), D("-4200.55")],
    )
    def test_money_returns_decimal(self, value: Decimal) -> None:
        result = calculator.money(value)
        assert isinstance(result, Decimal)
        assert not isinstance(result, float)

    def test_totalling_a_column_stays_exact(self) -> None:
        """Ten cents summed ten times is exactly one, not 0.9999999999999999."""
        assert calculator.total([D("0.10")] * 10) == D("1.00")
