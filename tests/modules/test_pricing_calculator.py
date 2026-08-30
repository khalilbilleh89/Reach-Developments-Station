"""The pricing arithmetic, tested without a database.

Every case here is a rule somebody could otherwise only check by reading a
spreadsheet: what a factor-priced balcony contributes, what "additive" means
next to "compound", what a premium cap does to the line it removes, and whether
a column of figures adds up to the total printed beneath it.

No session, no fixtures, no HTTP. If one of these fails, the number is wrong —
not the plumbing.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.modules.pricing.calculator import (
    AreaInput,
    EscalationInput,
    PremiumInput,
    PricingInput,
    UpgradeInput,
    calculate,
)

RATE = Decimal("1500.00")


def _area(code: str, raw: str, method: str, **extra: object) -> AreaInput:
    return AreaInput(
        area_type_id=uuid.uuid4(),
        code=code,
        label=code.title(),
        unit_of_measure="sqm",
        raw_area=Decimal(raw),
        pricing_method=method,
        **extra,  # type: ignore[arg-type]
    )


def _premium(code: str, method: str, **extra: object) -> PremiumInput:
    return PremiumInput(
        premium_rule_id=uuid.uuid4(),
        code=code,
        label=code.title(),
        source_kind=extra.pop("source_kind", "view_class"),  # type: ignore[arg-type]
        method=method,
        **extra,  # type: ignore[arg-type]
    )


def _reconciles(result: object) -> bool:
    """Every stored total is the sum of the lines a reader can see."""
    return (
        sum(
            component.calculated_amount
            for component in result.components  # type: ignore[attr-defined]
        )
        == result.reference_price_ex_tax
    )  # type: ignore[attr-defined]


# --------------------------------------------------------------------------- #
# Base areas
# --------------------------------------------------------------------------- #


def test_internal_area_alone_is_area_times_rate() -> None:
    """Given 100 sqm at 1,500, then the price is 150,000 and says why."""
    result = calculate(
        PricingInput(base_internal_rate=RATE, areas=(_area("INT", "100.0000", "internal_base"),))
    )

    assert result.reference_price_ex_tax == Decimal("150000.00")
    line = result.components[0]
    assert (line.quantity, line.rate, line.calculated_amount) == (
        Decimal("100.0000"),
        RATE,
        Decimal("150000.00"),
    )
    assert _reconciles(result)


def test_an_attached_area_can_carry_its_own_rate() -> None:
    """A terrace priced at 700 is 700, whatever the internal rate is."""
    result = calculate(
        PricingInput(
            base_internal_rate=RATE,
            areas=(
                _area("INT", "100.0000", "internal_base"),
                _area("TER", "20.0000", "fixed_rate_per_area", rate_per_area=Decimal("700.00")),
            ),
        )
    )

    assert result.base_area_value == Decimal("164000.00")
    assert result.components[1].calculated_amount == Decimal("14000.00")


def test_an_attached_area_can_be_a_factor_of_the_internal_rate() -> None:
    """Given half the internal rate, then the line reads 20 x 750 and adds up.

    The derived rate is quantised before it multiplies, so the multiplication a
    reader can see produces the amount printed beside it.
    """
    result = calculate(
        PricingInput(
            base_internal_rate=RATE,
            areas=(
                _area("INT", "100.0000", "internal_base"),
                _area(
                    "BAL",
                    "20.0000",
                    "factor_of_internal_rate",
                    internal_rate_factor=Decimal("0.500000"),
                ),
            ),
        )
    )

    balcony = result.components[1]
    assert balcony.rate == Decimal("750.00")
    assert balcony.quantity * balcony.rate == balcony.calculated_amount
    assert result.reference_price_ex_tax == Decimal("165000.00")


def test_an_excluded_area_contributes_nothing_and_no_line() -> None:
    """A measured plot is not a sold area, and a zero line would imply it was."""
    result = calculate(
        PricingInput(
            base_internal_rate=RATE,
            areas=(
                _area("INT", "100.0000", "internal_base"),
                _area("PLOT", "400.0000", "excluded"),
            ),
        )
    )

    assert [component.code for component in result.components] == ["INT"]
    assert result.reference_price_ex_tax == Decimal("150000.00")


# --------------------------------------------------------------------------- #
# Premiums
# --------------------------------------------------------------------------- #


def _with_base(*premiums: PremiumInput, cap: str | None = None) -> object:
    return calculate(
        PricingInput(
            base_internal_rate=RATE,
            areas=(_area("INT", "100.0000", "internal_base"),),
            premiums=premiums,
            maximum_premium_fraction=Decimal(cap) if cap else None,
        )
    )


def test_a_percentage_premium_is_a_percentage_of_a_stated_base() -> None:
    result = _with_base(_premium("VIEW", "percentage", percentage_fraction=Decimal("0.050000")))

    line = result.components[1]  # type: ignore[attr-defined]
    assert line.basis_amount == Decimal("150000.00")
    assert line.calculated_amount == Decimal("7500.00")


def test_a_fixed_premium_is_the_amount_it_says() -> None:
    result = _with_base(
        _premium("CORNER", "fixed", source_kind="corner", amount=Decimal("10000.00"))
    )

    assert result.reference_price_ex_tax == Decimal("160000.00")  # type: ignore[attr-defined]


def test_a_per_area_premium_multiplies_the_area_it_reads() -> None:
    result = _with_base(
        _premium(
            "ROOF",
            "per_area",
            source_kind="area_type",
            amount=Decimal("150.00"),
            quantity=Decimal("30.0000"),
        )
    )

    assert result.components[1].calculated_amount == Decimal("4500.00")  # type: ignore[attr-defined]


def test_a_per_asset_premium_multiplies_the_count() -> None:
    """Two covered bays at 7,500 is 15,000, and the line shows the two."""
    result = _with_base(
        _premium(
            "PARK",
            "fixed_per_asset",
            source_kind="parking",
            amount=Decimal("7500.00"),
            quantity=Decimal("2"),
        )
    )

    line = result.components[1]  # type: ignore[attr-defined]
    assert (line.quantity, line.rate, line.calculated_amount) == (
        Decimal("2"),
        Decimal("7500.00"),
        Decimal("15000.00"),
    )


def test_percentages_stack_additively_by_default() -> None:
    """Given 5% and 3% of one base, then the answer is 8% of that base.

    Not 8.15%. Compounding by accident is the arithmetic error that makes a
    price list impossible to reproduce by hand, and it is the reason the default
    is stated rather than emergent.
    """
    result = _with_base(
        _premium("VIEW", "percentage", percentage_fraction=Decimal("0.050000"), sequence=1),
        _premium("CORNER", "percentage", percentage_fraction=Decimal("0.030000"), sequence=2),
    )

    assert result.premium_total == Decimal("12000.00")  # type: ignore[attr-defined]
    assert result.reference_price_ex_tax == Decimal("162000.00")  # type: ignore[attr-defined]


def test_a_rule_that_asks_to_compound_compounds() -> None:
    """5% then 3% of the premiumed price is 157,500 then 4,725."""
    result = _with_base(
        _premium("VIEW", "percentage", percentage_fraction=Decimal("0.050000"), sequence=1),
        _premium(
            "CORNER",
            "percentage",
            percentage_fraction=Decimal("0.030000"),
            stacking_method="compound",
            sequence=2,
        ),
    )

    assert [line.calculated_amount for line in result.components[1:]] == [  # type: ignore[attr-defined]
        Decimal("7500.00"),
        Decimal("4725.00"),
    ]


def test_the_premium_cap_appears_as_its_own_line() -> None:
    """Given 25,000 of premiums against a 20,000 ceiling, then 5,000 is refused visibly.

    Showing 20,000 with no explanation would leave an operator unable to tell a
    capped price from a mis-configured one.
    """
    result = _with_base(
        _premium("A", "fixed", amount=Decimal("15000.00"), sequence=1),
        _premium("B", "fixed", amount=Decimal("10000.00"), sequence=2),
        cap="0.100000",
    )

    cap_line = result.components[-1]  # type: ignore[attr-defined]
    assert cap_line.component_type == "premium_cap_adjustment"
    assert cap_line.calculated_amount == Decimal("-10000.00")
    assert result.premium_total_uncapped == Decimal("25000.00")  # type: ignore[attr-defined]
    assert result.premium_total == Decimal("15000.00")  # type: ignore[attr-defined]
    assert _reconciles(result)


def test_premiums_under_the_cap_produce_no_cap_line() -> None:
    result = _with_base(_premium("A", "fixed", amount=Decimal("1000.00")), cap="0.100000")

    assert all(
        line.component_type != "premium_cap_adjustment"
        for line in result.components  # type: ignore[attr-defined]
    )
    assert result.premium_cap_adjustment == Decimal("0")  # type: ignore[attr-defined]


# --------------------------------------------------------------------------- #
# Escalation, upgrades and reconciliation
# --------------------------------------------------------------------------- #


def _escalation(code: str, **extra: object) -> EscalationInput:
    return EscalationInput(
        activation_id=uuid.uuid4(),
        code=code,
        label=code.title(),
        adjustment_method=extra.pop("adjustment_method", "percentage"),  # type: ignore[arg-type]
        **extra,  # type: ignore[arg-type]
    )


def test_an_escalation_moves_the_priced_total() -> None:
    result = calculate(
        PricingInput(
            base_internal_rate=RATE,
            areas=(_area("INT", "100.0000", "internal_base"),),
            escalations=(_escalation("Q2", adjustment_percentage_fraction=Decimal("0.020000")),),
        )
    )

    assert result.escalation_total == Decimal("3000.00")
    assert result.reference_price_ex_tax == Decimal("153000.00")


def test_cumulative_and_non_cumulative_escalations_give_different_answers() -> None:
    """Both are legitimate policies, so the rule says which rather than the code.

    Non-cumulative: each 2% is 2% of 150,000. Cumulative: the second is 2% of
    153,000. Three thousand against three thousand and sixty — small, and
    exactly the kind of difference nobody can reconcile after the fact.
    """
    flat = calculate(
        PricingInput(
            base_internal_rate=RATE,
            areas=(_area("INT", "100.0000", "internal_base"),),
            escalations=(
                _escalation("A", adjustment_percentage_fraction=Decimal("0.020000"), sequence=1),
                _escalation("B", adjustment_percentage_fraction=Decimal("0.020000"), sequence=2),
            ),
        )
    )
    compounded = calculate(
        PricingInput(
            base_internal_rate=RATE,
            areas=(_area("INT", "100.0000", "internal_base"),),
            escalations=(
                _escalation("A", adjustment_percentage_fraction=Decimal("0.020000"), sequence=1),
                _escalation(
                    "B",
                    adjustment_percentage_fraction=Decimal("0.020000"),
                    cumulative=True,
                    sequence=2,
                ),
            ),
        )
    )

    assert flat.escalation_total == Decimal("6000.00")
    assert compounded.escalation_total == Decimal("6060.00")


def test_a_fixed_escalation_is_an_amount() -> None:
    result = calculate(
        PricingInput(
            base_internal_rate=RATE,
            areas=(_area("INT", "100.0000", "internal_base"),),
            escalations=(
                _escalation(
                    "FIXED",
                    adjustment_method="fixed",
                    adjustment_amount=Decimal("2500.00"),
                ),
            ),
        )
    )

    assert result.reference_price_ex_tax == Decimal("152500.00")


def test_a_paid_upgrade_is_its_own_line() -> None:
    result = calculate(
        PricingInput(
            base_internal_rate=RATE,
            areas=(_area("INT", "100.0000", "internal_base"),),
            upgrades=(
                UpgradeInput(code="KITCHEN", label="Upgraded kitchen", amount=Decimal("8000.00")),
            ),
        )
    )

    assert result.paid_upgrade_total == Decimal("8000.00")
    assert result.components[-1].component_type == "paid_upgrade"


def test_everything_together_still_reconciles_exactly() -> None:
    """The whole waterfall, added up, equals the total. To the fil.

    This is the invariant the register depends on: a component list a reader can
    add up and a total that agrees with them, with no rounding residue hiding in
    the difference.
    """
    result = calculate(
        PricingInput(
            base_internal_rate=Decimal("1333.33"),
            areas=(
                _area("INT", "97.3300", "internal_base"),
                _area(
                    "BAL",
                    "13.7700",
                    "factor_of_internal_rate",
                    internal_rate_factor=Decimal("0.333333"),
                ),
                _area("TER", "9.1100", "fixed_rate_per_area", rate_per_area=Decimal("411.11")),
            ),
            premiums=(
                _premium("VIEW", "percentage", percentage_fraction=Decimal("0.037000"), sequence=1),
                _premium(
                    "PARK",
                    "fixed_per_asset",
                    source_kind="parking",
                    amount=Decimal("7333.33"),
                    quantity=Decimal("3"),
                    sequence=2,
                ),
            ),
            escalations=(_escalation("E1", adjustment_percentage_fraction=Decimal("0.017000")),),
            upgrades=(UpgradeInput(code="U", label="Upgrade", amount=Decimal("1111.11")),),
            maximum_premium_fraction=Decimal("0.150000"),
        )
    )

    assert _reconciles(result)
    assert result.reference_price_ex_tax == sum(
        (
            result.base_area_value,
            result.scope_adjustment_total,
            result.premium_total,
            result.escalation_total,
            result.paid_upgrade_total,
        ),
        Decimal("0"),
    )


def test_the_same_inputs_always_give_the_same_lines_in_the_same_order() -> None:
    """Determinism is the property that makes a price reproducible at all."""
    source = PricingInput(
        base_internal_rate=RATE,
        areas=(
            _area("BAL", "20.0000", "factor_of_internal_rate", internal_rate_factor=Decimal("0.5")),
            _area("INT", "100.0000", "internal_base"),
        ),
        premiums=(
            _premium("B", "fixed", amount=Decimal("100.00"), sequence=2),
            _premium("A", "fixed", amount=Decimal("200.00"), sequence=1),
        ),
    )

    first = calculate(source)
    second = calculate(source)

    assert [line.code for line in first.components] == ["INT", "BAL", "A", "B"]
    assert [line.code for line in second.components] == [line.code for line in first.components]
    assert [line.sequence for line in first.components] == [1, 2, 3, 4]


def test_an_unknown_area_method_is_refused_rather_than_priced_at_zero() -> None:
    """A method the calculator does not understand is a bug, not a free area."""
    with pytest.raises(ValueError, match="Unknown area pricing method"):
        calculate(
            PricingInput(base_internal_rate=RATE, areas=(_area("INT", "100.0000", "make_it_up"),))
        )
