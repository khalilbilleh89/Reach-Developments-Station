"""Five-year unlevered projections. Never changes asking prices or recorded cash."""

from decimal import ROUND_HALF_UP, Decimal, localcontext
from itertools import pairwise

from app.modules.marketing.schemas import Projection, ProjectionYear, ScenarioWrite

ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")


def rounded(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def annual_irr(flows: list[Decimal]) -> Decimal | None:
    """Unique annual IRR for conventional cash flows only; no guessed roots."""
    signs = [value > 0 for value in flows if value != 0]
    if not signs or signs[0] or sum(a != b for a, b in pairwise(signs)) != 1:
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
            rental_months = min(12, max(0, year * 12 - s.rental_delay_months))
            gross = rounded(
                area
                * s.annual_rent_per_sqm
                * (ONE + s.income_growth_percent / HUNDRED) ** (year - 1)
                * Decimal(rental_months)
                / 12
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
                    rental_months=rental_months,
                    gross_revenue=gross,
                    vacancy_amount=vacancy,
                    effective_revenue=effective,
                    expenses=expense,
                    noi=effective - expense,
                    property_value=rounded(
                        (s.current_value or price)
                        * (ONE + s.appreciation_percent / HUNDRED) ** year
                    ),
                    cashflow=effective - expense,
                    gross_yield_percent=rounded(gross / price * HUNDRED),
                    net_yield_percent=rounded((effective - expense) / initial * HUNDRED),
                    cumulative_noi=ZERO,
                    cumulative_cashflow=ZERO,
                    discounted_cashflow=ZERO,
                )
            )
        cap_value = (
            rounded(rows[5].noi / (s.exit_cap_percent / HUNDRED)) if rows[5].noi > 0 else None
        )
        years = rows[:5]
        appreciation_value = years[-1].property_value
        exit_value = appreciation_value if s.exit_method == "appreciation" else cap_value
        if exit_value is None:
            raise ValueError(
                "Cap-rate resale requires positive year-six NOI; zero is not a valuation."
            )
        selling_costs = rounded(exit_value * s.selling_cost_percent / HUNDRED)
        proceeds = exit_value - selling_costs
        years[-1].cashflow += proceeds
        flows = [-initial, *(row.cashflow for row in years)]
        irr = annual_irr(flows)
        rental_payback = None
        total_payback = None
        rental_sum = ZERO
        total_sum = ZERO
        discounted_sum = -initial
        discounted_payback = None
        for row in years:
            if (
                rental_payback is None
                and row.noi > 0
                and rental_sum < initial <= rental_sum + row.noi
            ):
                rental_payback = Decimal(row.year)
            rental_sum += row.noi
            total_sum += row.cashflow
            row.cumulative_noi = rental_sum
            row.cumulative_cashflow = total_sum - initial
            row.discounted_cashflow = rounded(
                row.cashflow / (ONE + s.discount_percent / HUNDRED) ** row.year
            )
            discounted_sum += row.discounted_cashflow
            if discounted_payback is None and discounted_sum >= 0:
                discounted_payback = row.year
            if total_payback is None and total_sum >= initial:
                total_payback = row.year
        return Projection(
            valuation_basis="Recorded unit valuation"
            if s.current_value
            else "Purchase price proxy; no current valuation supplied",
            resale_value=exit_value,
            selling_costs=selling_costs,
            acquisition_costs=initial - price - s.setup_cost,
            total_rental_income=sum((r.effective_revenue for r in years), ZERO),
            total_operating_expenses=sum((r.expenses for r in years), ZERO),
            total_noi=rental_sum,
            rental_return_percent=rounded(rental_sum / initial * HUNDRED),
            total_profit=total_sum - initial,
            present_value_of_future_cashflows=discounted_sum + initial,
            discounted_payback_year=discounted_payback,
            warnings=[
                "Projection from assumptions, not an independently verified market valuation.",
                f"Purchase paid at inception; {s.rental_delay_months} months before rent starts; "
                "annual receipts at year end.",
                "Operating costs apply during rental delay; growth runs from year one.",
                "No financing, instalment schedule, personal income or capital gains tax modelled.",
                *(
                    ["Income capitalisation unavailable: year-six NOI is non-positive."]
                    if cap_value is None
                    else []
                ),
            ],
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
            npv=discounted_sum,
            rental_payback_years=rental_payback,
            total_payback_year=total_payback,
            years=years,
        )
