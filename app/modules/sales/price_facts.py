"""Signed commercial comparisons of frozen, same-currency Decimal facts."""

from decimal import ROUND_HALF_UP, Decimal


def variance_amount(reference: Decimal, agreed: Decimal) -> Decimal:
    return (agreed - reference).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def variance_fraction(reference: Decimal, agreed: Decimal) -> Decimal | None:
    if reference == 0:
        return None
    return ((agreed - reference) / reference).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def variance_percentage(reference: Decimal, agreed: Decimal) -> str | None:
    if reference == 0:
        return None
    value = ((agreed - reference) / reference * Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return ("+" if value > 0 else "") + format(value, ".2f") + "%"
