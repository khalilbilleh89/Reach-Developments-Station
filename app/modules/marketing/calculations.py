"""Five-year unlevered projections. Never changes asking prices or recorded cash."""

from decimal import ROUND_HALF_UP, Decimal, localcontext

from app.modules.marketing.schemas import Projection, ProjectionYear, ScenarioWrite

ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")


def rounded(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def annual_irr(flows: list[Decimal]) -> Decimal | None:
    """Unique annual IRR for conventional cash flows only; no guessed roots."""
    if flows[0] >= 0 or any(value < 0 for value in flows[1:]) or not any(flows[1:]):
        return None

    def residual(rate: Decimal) -> Decimal:
        return sum((value / (ONE + rate) ** year for year, value in enumerate(flows)), ZERO)

    lo, hi = Decimal("-0.999999"), ONE
    while residual(hi) > 0 and hi < Decimal("1000000"):
        hi *= 2
    if residual(lo) < 0 or residual(hi) > 0:
        return None
    for _ in range(160):
        mid = (lo + hi) / 2
        if residual(mid) > 0:
            lo = mid
        else:
            hi = mid
    return rounded((lo + hi) / 2 * HUNDRED)


def calculate(s: ScenarioWrite, area: Decimal, price: Decimal) -> Projection:
    """Annual rent and costs per sqm; end-year receipts and disposal in year five."""
    if area <= 0 or price <= 0:
        raise ValueError("A positive area and purchase price are required.")
    with localcontext() as ctx:
        ctx.prec = 50
        initial = rounded(price * (ONE + s.acquisition_cost_percent / HUNDRED) + s.setup_cost)
        rows = []
        for year in range(1, 7):
            gross = rounded(
                area
                * s.annual_rent_per_sqm
                * (ONE + s.income_growth_percent / HUNDRED) ** (year - 1)
            )
            vacancy = rounded(gross * s.vacancy_percent / HUNDRED)
            effective = gross - vacancy
            expense = rounded(
                area
                * s.annual_expense_per_sqm
                * (ONE + s.expense_growth_percent / HUNDRED) ** (year - 1)
            )
            rows.append(
                ProjectionYear(
                    year=year,
                    gross_revenue=gross,
                    vacancy_amount=vacancy,
                    effective_revenue=effective,
                    expenses=expense,
                    noi=effective - expense,
                    property_value=rounded(
                        price * (ONE + s.appreciation_percent / HUNDRED) ** year
                    ),
                    cashflow=effective - expense,
                )
            )
        cap_value = rounded(max(ZERO, rows[5].noi) / (s.exit_cap_percent / HUNDRED))
        years = rows[:5]
        appreciation_value = years[-1].property_value
        exit_value = appreciation_value if s.exit_method == "appreciation" else cap_value
        proceeds = rounded(exit_value * (ONE - s.selling_cost_percent / HUNDRED))
        years[-1].cashflow += proceeds
        flows = [-initial, *(row.cashflow for row in years)]
        irr = annual_irr(flows)
        rental_payback = None
        total_payback = None
        rental_sum = ZERO
        total_sum = ZERO
        for row in years:
            if (
                rental_payback is None
                and row.noi > 0
                and rental_sum < initial <= rental_sum + row.noi
            ):
                rental_payback = rounded(Decimal(row.year - 1) + (initial - rental_sum) / row.noi)
            rental_sum += row.noi
            total_sum += row.cashflow
            if total_payback is None and total_sum >= initial:
                total_payback = row.year
        return Projection(
            simple_payback_years=rounded(initial / years[0].noi) if years[0].noi > 0 else None,
            initial_investment=initial,
            gross_yield_percent=rounded(years[0].gross_revenue / price * HUNDRED),
            net_yield_percent=rounded(years[0].noi / initial * HUNDRED),
            monthly_potential_revenue=rounded(years[0].gross_revenue / 12),
            appreciation_value=appreciation_value,
            capital_gain=rounded(exit_value - price),
            cap_value=cap_value,
            sale_proceeds=proceeds,
            roi_percent=rounded(sum(flows, ZERO) / initial * HUNDRED),
            irr_percent=irr,
            irr_reason=None
            if irr is not None
            else "No unique conventional annual IRR within the solver range.",
            npv=rounded(
                sum(
                    (
                        value / (ONE + s.discount_percent / HUNDRED) ** year
                        for year, value in enumerate(flows)
                    ),
                    ZERO,
                )
            ),
            rental_payback_years=rental_payback,
            total_payback_year=total_payback,
            years=years,
        )
