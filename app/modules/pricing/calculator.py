"""The pricing arithmetic, and nothing else.

This module has no database session, no actor, no transaction and no imports
from any other domain. Inputs in, a priced result out. That is deliberate: the
one thing a price must be is reproducible, and a calculation that can also read
a row is a calculation whose answer depends on when you asked.

It is also not a framework. There is no expression language, no rule evaluator
and no plug-in point — just the fixed set of contributions a real estate list
price is made of, computed in a stated order:

    base area value            internal area at the base rate, plus each
                               attached area at its own rate or factor
    + scope adjustments        phase, building and unit-type premiums
    + premiums                 features, sub-assets, measured areas, fields
    - premium cap adjustment   when premiums exceed the configured ceiling
    + escalation               activated, evidenced price movements
    + paid upgrades            options the buyer is paying for
    ---------------------------------------------------------------
    = reference price ex tax

Two invariants hold for every result this module produces, and both are tested:

* every intermediate figure appears as a component line — nothing is folded
  into a total without saying so, including the cap, which appears as its own
  negative line rather than as premiums quietly showing less;
* the component lines sum to ``reference_price_ex_tax`` exactly. Money is
  quantised once per line, to the scale the money column stores, so the total
  is the sum of the printed figures and not a rounder number beside them.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from app.db.base import MONEY_EXPONENT
from app.modules.pricing.models import (
    ADJUSTMENT_PERCENTAGE,
    AREA_METHOD_EXCLUDED,
    AREA_METHOD_FACTOR,
    AREA_METHOD_FIXED_RATE,
    AREA_METHOD_INTERNAL_BASE,
    COMPONENT_BASE_ATTACHED,
    COMPONENT_BASE_INTERNAL,
    COMPONENT_ESCALATION,
    COMPONENT_FEATURE_PREMIUM,
    COMPONENT_PAID_UPGRADE,
    COMPONENT_PREMIUM_CAP,
    COMPONENT_SCOPE_ADJUSTMENT,
    COMPONENT_SUB_ASSET_PREMIUM,
    ELIGIBLE_BASE_AREAS,
    PREMIUM_ASSET_SOURCES,
    PREMIUM_METHOD_PER_AREA,
    PREMIUM_METHOD_PER_ASSET,
    PREMIUM_METHOD_PERCENTAGE,
    STACKING_COMPOUND,
)

ZERO = Decimal("0")

#: Source kinds whose premium is a characteristic of the unit itself, as opposed
#: to something countable attached to it. Only the component label differs; the
#: arithmetic is identical.
_SCOPE_SOURCES = frozenset({"phase", "building", "unit_type"})


def money(amount: Decimal) -> Decimal:
    """Quantise to the scale the money column stores.

    Half-up, and applied once per component line rather than after every
    multiplication. Rounding each product would make the total drift from the
    figures a reader can see; never rounding would store an amount the column
    cannot hold, which changes the moment it is read back.
    """
    return amount.quantize(MONEY_EXPONENT, rounding=ROUND_HALF_UP)


# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class AreaInput:
    """One measured area of the unit, with the rule that prices it."""

    area_type_id: uuid.UUID
    code: str
    label: str
    unit_of_measure: str
    raw_area: Decimal
    pricing_method: str
    rate_per_area: Decimal | None = None
    internal_rate_factor: Decimal | None = None
    area_rule_id: uuid.UUID | None = None
    sort_order: int = 0


@dataclass(frozen=True, slots=True)
class PremiumInput:
    """One premium rule that has already been matched against the unit.

    Matching happens in the service, where the unit is. By the time a premium
    reaches here it is a decided contribution: this rule applies, this many
    times, against this much area.
    """

    premium_rule_id: uuid.UUID
    code: str
    label: str
    source_kind: str
    method: str
    percentage_fraction: Decimal | None = None
    amount: Decimal | None = None
    eligible_base: str = "base_with_adjustments"
    stacking_method: str = "additive"
    sequence: int = 0
    #: How many of the counted thing there are, or how much area to multiply.
    quantity: Decimal = Decimal("1")
    quantity_unit: str | None = None


@dataclass(frozen=True, slots=True)
class EscalationInput:
    """One activated escalation that reaches this unit."""

    activation_id: uuid.UUID
    code: str
    label: str
    adjustment_method: str
    adjustment_percentage_fraction: Decimal | None = None
    adjustment_amount: Decimal | None = None
    cumulative: bool = False
    sequence: int = 0


@dataclass(frozen=True, slots=True)
class UpgradeInput:
    """An option the buyer is paying for, priced into the list price."""

    code: str
    label: str
    amount: Decimal


@dataclass(frozen=True, slots=True)
class PricingInput:
    """Everything one price calculation needs, and nothing it does not."""

    base_internal_rate: Decimal
    areas: tuple[AreaInput, ...] = ()
    premiums: tuple[PremiumInput, ...] = ()
    escalations: tuple[EscalationInput, ...] = ()
    upgrades: tuple[UpgradeInput, ...] = ()
    maximum_premium_fraction: Decimal | None = None


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class Component:
    """One line of the waterfall."""

    sequence: int
    component_type: str
    code: str
    label: str
    calculated_amount: Decimal
    quantity: Decimal | None = None
    unit_of_measure: str | None = None
    basis_amount: Decimal | None = None
    rate: Decimal | None = None
    factor: Decimal | None = None
    area_rule_id: uuid.UUID | None = None
    premium_rule_id: uuid.UUID | None = None
    escalation_activation_id: uuid.UUID | None = None


@dataclass(slots=True)
class PricingResult:
    """A priced unit, with every figure that produced it."""

    components: list[Component] = field(default_factory=list)
    base_area_value: Decimal = ZERO
    scope_adjustment_total: Decimal = ZERO
    premium_total_uncapped: Decimal = ZERO
    premium_cap_adjustment: Decimal = ZERO
    premium_total: Decimal = ZERO
    escalation_total: Decimal = ZERO
    paid_upgrade_total: Decimal = ZERO
    reference_price_ex_tax: Decimal = ZERO


# --------------------------------------------------------------------------- #
# Calculation
# --------------------------------------------------------------------------- #


def _area_amount(area: AreaInput, base_internal_rate: Decimal) -> tuple[Decimal, Decimal | None]:
    """The money one measured area contributes, and the rate it was priced at."""
    if area.pricing_method == AREA_METHOD_EXCLUDED:
        return ZERO, None
    if area.pricing_method == AREA_METHOD_INTERNAL_BASE:
        rate = base_internal_rate
    elif area.pricing_method == AREA_METHOD_FIXED_RATE:
        rate = area.rate_per_area if area.rate_per_area is not None else ZERO
    elif area.pricing_method == AREA_METHOD_FACTOR:
        factor = area.internal_rate_factor if area.internal_rate_factor is not None else ZERO
        # Quantised before it multiplies, not after. The rate is published on
        # the line, and a line that reads "20 sqm x 750.00" must produce the
        # amount printed beside it; keeping eight decimals in the rate would
        # make the visible multiplication wrong by a few fils.
        rate = money(base_internal_rate * factor)
    else:  # pragma: no cover - the closed set is enforced by a CHECK constraint
        raise ValueError(f"Unknown area pricing method: {area.pricing_method}")
    return money(area.raw_area * rate), rate


def _base_components(source: PricingInput, sequence: int) -> tuple[list[Component], Decimal, int]:
    """Price every measured area, internal first, then the attached ones."""
    components: list[Component] = []
    total = ZERO
    ordered = sorted(
        source.areas,
        key=lambda area: (
            area.pricing_method != AREA_METHOD_INTERNAL_BASE,
            area.sort_order,
            area.code,
        ),
    )
    for area in ordered:
        if area.pricing_method == AREA_METHOD_EXCLUDED:
            continue
        amount, rate = _area_amount(area, source.base_internal_rate)
        internal = area.pricing_method == AREA_METHOD_INTERNAL_BASE
        components.append(
            Component(
                sequence=sequence,
                component_type=COMPONENT_BASE_INTERNAL if internal else COMPONENT_BASE_ATTACHED,
                code=area.code,
                label=area.label,
                quantity=area.raw_area,
                unit_of_measure=area.unit_of_measure,
                rate=rate,
                factor=area.internal_rate_factor,
                calculated_amount=amount,
                area_rule_id=area.area_rule_id,
            )
        )
        total += amount
        sequence += 1
    return components, total, sequence


def _premium_amount(premium: PremiumInput, basis: Decimal) -> Decimal:
    """The money one matched premium contributes against a stated basis."""
    if premium.method == PREMIUM_METHOD_PERCENTAGE:
        fraction = premium.percentage_fraction or ZERO
        return money(basis * fraction)
    amount = premium.amount or ZERO
    if premium.method in (PREMIUM_METHOD_PER_AREA, PREMIUM_METHOD_PER_ASSET):
        return money(amount * premium.quantity)
    return money(amount)


def _premium_components(
    source: PricingInput,
    *,
    base_area_value: Decimal,
    scope_total: Decimal,
    sequence: int,
) -> tuple[list[Component], Decimal, int]:
    """Every feature and sub-asset premium, in a deterministic order.

    Additive is the default, and it means what it says: each percentage is a
    percentage of the same stated base, so 5% and 3% add 8% of that base and not
    8.15% of a base that grew in between. A rule that wants the second answer
    has to ask for ``compound``, and compounded rules are applied in ``sequence``
    order so the answer does not depend on how the rows came back.
    """
    components: list[Component] = []
    total = ZERO
    running = base_area_value + scope_total
    ordered = sorted(source.premiums, key=lambda premium: (premium.sequence, premium.code))
    for premium in ordered:
        if premium.eligible_base == ELIGIBLE_BASE_AREAS:
            basis = base_area_value
        else:
            basis = base_area_value + scope_total
        if premium.method == PREMIUM_METHOD_PERCENTAGE and premium.stacking_method == (
            STACKING_COMPOUND
        ):
            # Compounding is the one case where order is load-bearing: this
            # premium is a percentage of the price as already premiumed.
            basis = running
        amount = _premium_amount(premium, basis)
        components.append(
            Component(
                sequence=sequence,
                component_type=(
                    COMPONENT_SUB_ASSET_PREMIUM
                    if premium.source_kind in PREMIUM_ASSET_SOURCES
                    else COMPONENT_FEATURE_PREMIUM
                ),
                code=premium.code,
                label=premium.label,
                quantity=(
                    premium.quantity
                    if premium.method in (PREMIUM_METHOD_PER_AREA, PREMIUM_METHOD_PER_ASSET)
                    else None
                ),
                unit_of_measure=premium.quantity_unit,
                basis_amount=basis if premium.method == PREMIUM_METHOD_PERCENTAGE else None,
                rate=premium.amount,
                factor=premium.percentage_fraction,
                calculated_amount=amount,
                premium_rule_id=premium.premium_rule_id,
            )
        )
        total += amount
        running += amount
        sequence += 1
    return components, total, sequence


def _scope_components(
    source: PricingInput, *, base_area_value: Decimal, sequence: int
) -> tuple[list[Component], Decimal, int]:
    """Phase, building and unit-type adjustments, priced off the area value.

    They are separated from feature premiums because they answer a different
    question — where the unit is and what kind it is, rather than what it looks
    at — and because the premium cap applies to features, not to the scope
    adjustment that helps define the base the cap is measured against.
    """
    components: list[Component] = []
    total = ZERO
    ordered = sorted(source.premiums, key=lambda premium: (premium.sequence, premium.code))
    for premium in ordered:
        if premium.source_kind not in _SCOPE_SOURCES:
            continue
        amount = _premium_amount(premium, base_area_value)
        components.append(
            Component(
                sequence=sequence,
                component_type=COMPONENT_SCOPE_ADJUSTMENT,
                code=premium.code,
                label=premium.label,
                basis_amount=(
                    base_area_value if premium.method == PREMIUM_METHOD_PERCENTAGE else None
                ),
                rate=premium.amount,
                factor=premium.percentage_fraction,
                calculated_amount=amount,
                premium_rule_id=premium.premium_rule_id,
            )
        )
        total += amount
        sequence += 1
    return components, total, sequence


def _escalation_components(
    source: PricingInput, *, priced_before: Decimal, sequence: int
) -> tuple[list[Component], Decimal, int]:
    """Activated escalations, cumulative ones stacking on what came before.

    A cumulative escalation is a percentage of the price as already escalated; a
    non-cumulative one is a percentage of the price before any escalation. Both
    are legitimate commercial policies and they give different numbers, so the
    rule states which it is rather than the implementation deciding.
    """
    components: list[Component] = []
    total = ZERO
    running = priced_before
    ordered = sorted(
        source.escalations, key=lambda escalation: (escalation.sequence, escalation.code)
    )
    for escalation in ordered:
        if escalation.adjustment_method == ADJUSTMENT_PERCENTAGE:
            basis = running if escalation.cumulative else priced_before
            fraction = escalation.adjustment_percentage_fraction or ZERO
            amount = money(basis * fraction)
        else:
            basis = None
            amount = money(escalation.adjustment_amount or ZERO)
        components.append(
            Component(
                sequence=sequence,
                component_type=COMPONENT_ESCALATION,
                code=escalation.code,
                label=escalation.label,
                basis_amount=basis,
                rate=escalation.adjustment_amount,
                factor=escalation.adjustment_percentage_fraction,
                calculated_amount=amount,
                escalation_activation_id=escalation.activation_id,
            )
        )
        total += amount
        running += amount
        sequence += 1
    return components, total, sequence


def calculate(source: PricingInput) -> PricingResult:
    """Price one unit from explicit inputs.

    Deterministic in the strong sense: the same ``PricingInput`` gives the same
    ``PricingResult``, including the order and sequence numbers of the component
    lines, on any machine and at any time.
    """
    result = PricingResult()
    sequence = 1

    base_components, base_total, sequence = _base_components(source, sequence)
    result.components.extend(base_components)
    result.base_area_value = base_total

    scope_components, scope_total, sequence = _scope_components(
        source, base_area_value=base_total, sequence=sequence
    )
    result.components.extend(scope_components)
    result.scope_adjustment_total = scope_total

    feature_source = PricingInput(
        base_internal_rate=source.base_internal_rate,
        premiums=tuple(
            premium for premium in source.premiums if premium.source_kind not in _SCOPE_SOURCES
        ),
    )
    premium_components, premium_total, sequence = _premium_components(
        feature_source, base_area_value=base_total, scope_total=scope_total, sequence=sequence
    )
    result.components.extend(premium_components)
    result.premium_total_uncapped = premium_total

    # The cap is a visible line, not a silent smaller number. An operator who
    # configured 25,000 of premiums and sees 20,000 applied is entitled to see
    # the 5,000 that was refused and why.
    cap_adjustment = ZERO
    if source.maximum_premium_fraction is not None:
        eligible = base_total + scope_total
        ceiling = money(eligible * source.maximum_premium_fraction)
        if premium_total > ceiling:
            cap_adjustment = ceiling - premium_total
            result.components.append(
                Component(
                    sequence=sequence,
                    component_type=COMPONENT_PREMIUM_CAP,
                    code="PREMIUM_CAP",
                    label="Premium cap adjustment",
                    basis_amount=eligible,
                    factor=source.maximum_premium_fraction,
                    calculated_amount=cap_adjustment,
                )
            )
            sequence += 1
    result.premium_cap_adjustment = cap_adjustment
    result.premium_total = premium_total + cap_adjustment

    priced_before_escalation = base_total + scope_total + result.premium_total
    escalation_components, escalation_total, sequence = _escalation_components(
        source, priced_before=priced_before_escalation, sequence=sequence
    )
    result.components.extend(escalation_components)
    result.escalation_total = escalation_total

    upgrade_total = ZERO
    for upgrade in sorted(source.upgrades, key=lambda option: option.code):
        amount = money(upgrade.amount)
        result.components.append(
            Component(
                sequence=sequence,
                component_type=COMPONENT_PAID_UPGRADE,
                code=upgrade.code,
                label=upgrade.label,
                calculated_amount=amount,
            )
        )
        upgrade_total += amount
        sequence += 1
    result.paid_upgrade_total = upgrade_total

    result.reference_price_ex_tax = (
        base_total + scope_total + result.premium_total + escalation_total + upgrade_total
    )
    return result


def total_of(
    components: list[Component], *, overrides: dict[int, Decimal] | None = None
) -> Decimal:
    """The sum of a component list, taking any override in place of the calculation.

    Used to re-derive a price after a unit-level override, so the stored total
    and the stored lines can never disagree: there is one addition, over the
    same final amounts a reader sees.
    """
    overrides = overrides or {}
    total = ZERO
    for component in components:
        total += overrides.get(component.sequence, component.calculated_amount)
    return total
