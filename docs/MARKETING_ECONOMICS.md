# Unit investment analysis — calculation version 2

The five-year holding period starts at acquisition/analysis inception. Purchase,
acquisition and furnishing costs occur at time zero. Rental delay is 0–60 whole
months; year n earns rent for min(12, max(0, 12*n-delay)) months. Rent is prorated
after calendar-year growth. Operating costs apply throughout ownership, including
the delay. This annual unlevered model does not model mortgage or instalment XIRR.

Current valuation is an optional unit-specific amount with its own source and
date, in the scenario currency. It anchors appreciation at inception; absent a
valuation, purchase price is an explicitly labelled proxy. Acquisition cost stays
independent. Enter a valuation appropriate to the analysis start: an old date is
not automatically rolled forward. An asking price or an author-entered source is
not an independently verified appraisal. No project facts or market data are seeded.

Annual gross yield = potential rent / purchase price. Net yield on cost = NOI /
initial investment. Five-year rental return = sum(NOI) / initial investment and
is not annualised. Rental yields exclude resale. The annual table exposes rent,
costs, NOI, yields, cumulative NOI, appreciation value, cash and discounted cash.

At year five choose one exit: compound the valuation/purchase proxy, or capitalise
year-six NOI at the exit cap rate. Non-positive year-six NOI makes capitalisation
unavailable, not a zero-value property. Appreciation in the annual table remains
a separate illustration when capitalisation is selected. Selling costs are rounded
first; net sale = gross sale - selling costs. Only one resale enters cash flow.

Total profit = five-year NOI + net sale - initial investment. ROI divides profit
by initial investment. Present value is the discounted future cash-flow sum; NPV
subtracts initial investment. This is investment value under the selected discount
rate, not certified current market value. Annual discounted cash flows are rounded
half-up to cents before summation, so the displayed bridge reconciles exactly.
All computation is server Decimal; API amounts are exact strings.

IRR solves NPV=0 on the same annual cash flows. One negative-to-positive sign
transition, ignoring zeros, admits a unique root, including initial operating
losses. Multiple transitions return unavailable rather than a guessed root. The
solver is bounded above and greater than -99.9999%. Rental, total and discounted
payback use year-end receipts. Constant first-year NOI simple payback is a separate
illustration, not a recovery forecast beyond five years. Payback means first
recovery, not a promise that later cash balances cannot become negative.

The response includes exact input snapshots, scenario id/version, approved area
schedule id and the used asking-price version id. Purchase overrides do not cite
an unused price version. Project defaults are shared assumptions, not unit-specific
evidence. Source/date and valuation evidence/date remain visible. These references
enable review but do not certify evidence quality. Macro observations do not
automatically change a unit forecast. Financing, personal income/capital gains tax,
instalment schedules and independent market-evidence verification remain outside
this model; acquisition taxes and expected operating/disposal costs must be entered.

Existing authorization, audit, versioning and retained Delete apply to the added
fields. Old clients preserve omitted new inputs; explicit nulls clear all three
valuation fields together. Migration 0053 refuses downgrade if any active or
retained row contains valuation or delay information. No source history is erased.

Method references: [RICS DCF guidance](https://www.rics.org/profession-standards/rics-standards-and-guidance/sector-standards/valuation-standards/discounted-cash-flow-valuation)
and [Microsoft periodic NPV/IRR definitions](https://support.microsoft.com/en-au/excel/go-with-the-cash-flow-calculate-npv-and-irr-in-excel).
These support explicit timing and valuation methods; this implementation is not
represented as a RICS-certified professional valuation.
