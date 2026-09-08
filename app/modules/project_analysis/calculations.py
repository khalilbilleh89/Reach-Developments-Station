"""Small Decimal calculations, with explicit unavailable denominators."""

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from app.modules.project_analysis.schemas import Forecast, Ratio


def rounded(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def ratio(numerator: int | None, denominator: int | None, basis: str) -> Ratio:
    known = numerator is not None and denominator is not None and denominator > 0
    return Ratio(
        numerator=numerator,
        denominator=denominator,
        percentage=rounded(Decimal(numerator) * 100 / Decimal(denominator)) if known else None,
        source_basis=basis,
        sample_size=denominator or 0,
        availability="available" if known else "unavailable",
        reason=None if known else "No known positive denominator.",
    )


def shift_month(day: date, offset: int) -> date:
    index = day.year * 12 + day.month - 1 + offset
    return date(index // 12, index % 12 + 1, 1)


def forecast(as_of: date, remaining: int | None, net: list[int], observed: int) -> Forecast:
    average = Decimal(sum(net)) / Decimal(3) if observed == 3 else None
    reason = (
        "No eligible inventory denominator or historical inventory cannot be reconstructed."
        if remaining is None
        else "No remaining eligible inventory; sellout reached."
        if remaining <= 0
        else "Three complete months of recorded project history are required."
        if observed < 3
        else "Net absorption is zero or negative; a sellout estimate is indeterminate."
        if average <= 0
        else None
    )
    return Forecast(
        source_basis=(
            "Remaining eligible units / average net activated-minus-cancelled sales"
            " over the last 3 complete UTC calendar months. No predictive "
            "certainty."
        ),
        window_from=shift_month(as_of, -3),
        window_to=shift_month(as_of, 0) - timedelta(days=1),
        observed_months=observed,
        monthly_net_absorption=net,
        sample_size=observed,
        remaining_units=remaining,
        average_monthly_absorption=rounded(average) if average is not None else None,
        estimated_months_to_sell=Decimal("0")
        if remaining == 0
        else rounded(Decimal(remaining) / average)
        if reason is None
        else None,
        availability="available" if reason is None or remaining == 0 else "unavailable",
        reason=reason,
    )
