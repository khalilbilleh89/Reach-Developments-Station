# Marketing

Owner-requested Marketing menu group, alongside Development, Commercial, Delivery
and Finance. It contains Project Bio, Economics and Branding. Governed by
`docs/ENGINEERING_RULES.md` and `docs/DELETION_POLICY.md`.

## Content

Project Bio records country, area, project and location narratives with bullet
points, nearby places with duration in minutes and travel mode, amenities and a
stated ROI range. An ROI range requires a basis/period, source and as-at date.
It is not automatically promoted from a unit forecast or described as guaranteed.
Branding records a marketing name/definition, named six-digit hex colours and
font families with usage notes. It does not rename the project master record,
load external fonts or change the application's theme.

Bio and Branding are bounded, typed documents in JSONB. They contain no executable
expressions, generic configurable fields or polymorphic references. Child items
are edited/deleted together in a version-checked document save. Market observations
and rental assumptions are separate records with native numeric/date columns.

## Buyer rental economics

Two project defaults (long-term and short-term) apply to units without an override.
A unit override replaces the complete set for that mode. Deleting it resumes the
project default. No real business assumptions or screenshot figures are seeded.

Rent and operating expenses are annual amounts per square metre in both modes.
Short-term rent means potential full-occupancy annual revenue per sqm; vacancy
accounts for unoccupied nights. The user selects approved net or gross area.
Non-sqm or unavailable areas are refused rather than converted or guessed.
Purchase price is an explicit unit assumption or current active asking price ex tax.
Asking price is not an executed investment purchase price. Currency mismatch makes
the calculation unavailable; there is no FX conversion.

All calculations use backend Decimal values. Money crosses the API as strings;
percentage inputs and outputs explicitly use percent, not fractional rates.

- Annual gross rent: selected area × annual rent/sqm, compounded for annual growth.
- Vacancy deduction: gross rent × vacancy %. Effective revenue: rent less vacancy.
- Expenses: selected area × annual expense/sqm, independently compounded.
- NOI: effective revenue less operating expenses.
- Initial investment: purchase price + acquisition costs/taxes + setup/furnishing.
- Gross yield: year-one potential rent / purchase price. Net yield: year-one NOI / initial investment.
- Appreciation value: purchase price compounded at annual appreciation for five years.
- Alternative cap valuation: max(0, year-six NOI) / exit cap rate.
- Sale proceeds: **one** selected exit valuation less selling costs.
- Five-year ROI: (five annual NOIs + sale proceeds − initial investment) / initial investment.
- NPV: discounted end-year cashflows, including sale in year five, less year-zero investment.
- Annual IRR: Decimal bisection for conventional flows only; nonconventional or
  unbracketed cashflows return an explicit unavailable explanation.
- Simple payback: initial investment / positive year-one NOI (constant-income basis).
- Rental-only recovery: interpolated within five years; otherwise not reached.
- Recovery including resale: first model year when cumulative inflows cover investment.

Annual displayed money is rounded half-up to two places; totals reconcile to those
cashflows. The model is unlevered, before personal income/capital-gains taxes.
Acquisition taxes, operating costs and selling costs are explicit assumptions.
It writes no pricing, Sales, Finance Unit Economics or cashflow records.

## Market context

Indicators record geography, observed value/unit, observation period, as-at date,
source and implications. Suggested topics include interest rates, inflation,
unemployment, real GDP growth, population, tourism, housing supply, price/rental
indices and transaction volume. These are manual sourced observations, not an
automatic data feed or a causal pricing formula.

## Access, concurrency and deletion

Whole-project access is required in SQL; selected-phase members receive 404.
Readers: administrator, project manager, Finance, CFO, executive, auditor,
Sales Operations and Sales Advisor. Writers: administrator, project manager,
Finance and Sales Operations. Browser gates mirror the server allow-lists.

Mutations lock the project, check optimistic versions and retain attributed audit
snapshots. Delete is visible for created records, requires a reason/version, hides
the active record and preserves history. Repeated deletion returns 404. There is
no cascade into business records. Unit references restrict physical unit purging
while retained assumptions exist; ordinary removed-unit history remains preserved.

## Migration and rollback

`0042_marketing` follows `0041_project_agreements`, adding only three tables
and their constraints/indexes. No existing records are changed or backfilled.
Empty downgrade is supported; downgrade refuses any retained marketing rows,
including deleted ones. Prefer rolling back application code while leaving the
additive tables intact. Export and retain history before any destructive rollback.

Local formula/API/security/migration and frontend behavior tests accompany the
change. Browser walkthrough, independent review and exact-head Full CI remain
separate release gates; a draft PR is not deployment evidence.
