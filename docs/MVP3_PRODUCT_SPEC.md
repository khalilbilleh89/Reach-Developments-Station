# MVP 3 — Development Operations & Management Intelligence

Canonical MVP 3 product specification alongside [ARCHITECTURE.md](ARCHITECTURE.md)
and [ENGINEERING_RULES.md](ENGINEERING_RULES.md). Frozen by the owner's PR-ENG-04
request on 2026-09-07. This document specifies future product work; PR-ENG-04
implements governance and CI only. Product progress starts at **0 / 5**.

## Source and authority

Business source: Khalil's second MVP feedback document,
`Real_Estate_Development_Tracking_System_MVP (1).docx`, specifically **Updated
Version Gate 0A — Comments and Changes (First Sections)**. The owner supplied
this version on 2026-09-07 after the original file was found to contain Gate 0
only. Reviewed file SHA-256:
`56dc07237c0fcf1c729312ac5f95638e4b122fc301faf90d6e3bb049e01079ca`.
The source is business reference material, not authorization to change financial
controls or deploy. The owner's frozen decisions below resolve its ambiguity.

Authority order for interpreting MVP 3:

1. Repository code on the branch being reviewed (the observable implementation).
2. `docs/ARCHITECTURE.md`.
3. `docs/ENGINEERING_RULES.md`.
4. `docs/MVP3_PRODUCT_SPEC.md`.
5. `docs/MVP3_ROADMAP.md`.
6. `docs/MVP3_ACCEPTANCE.md`.
7. `CLAUDE.md`.
8. Khalil's second Gate 0A source document.
9. Implementation conversation/handover.

Code establishes what exists; it does not authorize an architectural violation.
If implementation conflicts with Architecture or Engineering Rules, those rules
win unless explicitly amended in a reviewed PR. Later explicit owner decisions
must be recorded as amendments, not inferred from source examples.

## Mission and retained architecture

MVP 3 completes the missing pre-development workflow and management-intelligence
layer while simplifying the operator experience.

Land → Permits → Pre-Launch → Consultant Engineer → Inventory → Sales →
Payment Plans → Collections → Commissions → Construction → Cashflow →
Management Analysis.

The Unit remains the central operational record once inventory exists. Keep
FastAPI, PostgreSQL, Next.js, the modular monolith, one database, one API, Render
deployment and Product Experience 3.0. No new application architecture, warehouse,
message bus, generic workflow/configuration engine or duplicate ledger.

## Gate 0A request mapped to platform ownership

| Khalil requested | Architectural delivery | Product PR |
| --- | --- | --- |
| Development navigation: Land, Permits, Pre-Launch, Consultant Engineer, Inventory | Existing shell, with two contextual workspaces; domain authority stays intact | V3-01 shell; V3-02 workspaces |
| Simple pre-launch amount/date/description/notes entries for authorities and utilities | Development-facing UX over existing Cashflow Development Movements | V3-02 |
| Consultant agreement and Architect/MEP/Structural/QS/Supervision design stages | New operational consultant-engineering domain; existing document references | V3-02 |
| Manually chosen commission base, grant and named beneficiary percentages | New distribution ledger; no profitability/cash ledger | V3-03 |
| Remove Pricing destination; call Sales & Legal simply Sales | Navigation/deep-link changes around retained PriceVersion and SPA/legal services | V3-01 |
| Configure country/currency while creating the project; remove generic Reference Data | Contextual setup using normalized CountryPack, Currency and ReferenceValue | V3-01 |
| See purchase price plus fees in Land | Backend Decimal-derived acquisition consideration | V3-01 |
| Make an obtained permit obvious | Obtained / Issued presentation of the precise statutory state | V3-01 |
| Fundamental, financial and technical analysis | Narrow backend read/derived services consuming existing authoritative contracts | V3-04 |

## 1. Pre-Launch: one existing cash source

Pre-Launch is the Development-facing UX over governed **Cashflow Development
Movements**, already owned by `app/modules/cashflow`. It is not a second expense
or cash ledger. Examples include authority reimbursements, utility connection
fees, pre-launch expenses, permits, consultants, insurance, marketing and
development overhead. Use the existing category/direction vocabulary; any
necessary extension must be explicit and must not admit construction/customer
cash already owned elsewhere.

Present amount, payment date, description/reference and notes in that workflow.
Recorded is not paid; a confirmed movement is cash. Preserve confirmation,
maker/checker, reversal, audit, currency, effective date and project/phase scope.
A Development-facing navigation entry never grants Finance's mutation rights.
No new expense table. The Cashflow ledger alone supplies actual outflows.

## 2. Consultant Engineer: operational domain

This is genuinely new business state, not a renamed construction certificate.
It owns the main consultant engagement/agreement and reference, scope,
disciplines, design stages, deliverables, planned/forecast/actual dates,
status, document references and design progress/history. Architect, MEP,
Structural, QS and Supervision are source examples, not a hardcoded catalogue.

Agreement value may be displayed with its currency and basis. It is not a paid
amount. Actual consultant payments remain Cashflow Development Movements. Link
or display authoritative payment records without writing a second cash truth.
Keep project/phase permissions, date validation, reasoned corrections and actor/
timestamp history. Consultant design progress and physical construction progress
remain distinct; neither silently certifies work or releases payment.

## 3. Commissions: distribution only

For each sold unit, record a sold-price snapshot with sale provenance, a manually
entered commissionable base, granted commission rate, calculated granted amount,
manually named beneficiaries, each beneficiary rate and calculated amount.
The manually entered base may differ from the sold price; the distinction must
be visible. Use Decimal calculations on the backend and the sale's currency.

Beneficiary rates are percentages **of the commissionable sale base**, not
100% shares of a commission pool. Example, base and sold snapshot both 150,000:

| Entry | Rate of base | Amount |
| --- | ---: | ---: |
| Granted commission | 10% | 15,000 |
| Branch | 5% | 7,500 |
| Sales Person | 3% | 4,500 |
| Cyprus Branch | 1% | 1,500 |
| Support Team | 1% | 1,500 |

Release invariants: sum of beneficiary rates equals the granted rate; sum of
beneficiary amounts equals the granted amount. Reject unreconciled release.
The implementation must state currency precision and a deterministic rounding/
residual policy and test exact reconciliation; floating-point tolerance is not
a substitute. A zero/negative/invalid base or rate must receive explicit domain
validation, not implicit browser arithmetic.

Likely entities: Commission and CommissionAllocation. Lifecycle: Draft → Released
→ Reversed; no physical delete. Released provenance/distributions stay auditable;
correction does not overwrite released history. Release/reversal permissions and
conflict handling must be explicit in V3-03 and tested before integration review.
No slab/tier engine, payroll or automated payout engine.

### Structural economics boundary

Commissions must never write or mutate Unit Economics, direct unit costs,
PriceVersion, contracted sale amount, pricing adjustments, profit or margin.
The economics effect may already be accounted for; this module distributes it.
Regression tests must compare those source records/totals before and after
create, release and reversal, including rejected and concurrent operations.
Actual cash is not implied by a released distribution. No duplicate financial
effect may reach either economics or cashflow through this module.

## 4. Unit pricing and Sales language

Remove Pricing from ordinary project navigation, not from the backend. Preserve
PriceVersion, separate approvals, activation, price history, direct selling
price, repricing governance, frozen sale provenance and backend price/gross
calculation. Existing Pricing deep links must redirect to an appropriate Unit/
Inventory workflow without granting access or stranding governance actions.

Rename Sales & Legal to **Sales** in operator navigation. SPA, legal events,
signatures, registry lodging, registration, cancellation and handover remain
inside that workflow. This is language, not a status or permission change.

## 5. Project setup and domain configuration

Normal operators should not need to visit Settings before creating a project.
New Project establishes identity, jurisdiction/country, base currency, reporting
currency, fiscal basis and programme. Reuse normalized CountryPack and Currency;
do not duplicate their records/fields as competing Project truth. Contextual
creation/selection must retain authorization, uniqueness, active-reference and
locked-project-basis invariants. A UI simplification does not give ordinary
operators unrestricted global configuration administration.

Remove generic Reference Data from ordinary Settings navigation. Preserve
ReferenceValue where domains need it; permit types already have a contextual
Permits path. Preserve historic referenced values and in-use restrictions.
Do not infer hard-delete permission from the source's request to simplify or
remove a screen. No replacement generic configuration engine.

## 6. Land and permits

Expose Purchase Price + Acquisition Fees = **Total Acquisition Cost**.
Existing `LandParcel.purchase_price` and `acquisition_fees` remain inputs; total
is backend Decimal-derived, not another editable stored fact. Label it
acquisition consideration, not market valuation. State currency and missing-input
basis explicitly; an unknown component must not masquerade as a confirmed zero.

Preserve the precise permit state machine and its history. Successful truth such
as `issued` remains authoritative. Use Obtained / Issued or Obtained ✓ so the
operator recognizes success; no generic Completed state replacing legal truth.

## 7. Analysis contracts shared by all three areas

Fundamental, Financial and Technical Analysis are backend-derived read layers.
No financial/business arithmetic in React. Each figure carries project, date/
as-of, filters, source and denominator where applicable, plus currency for money.
Screen, drilldown and exports use the same basis. Unavailable, denied, incomplete
and zero are distinct. Avoid mixed-currency addition and undisclosed FX assumptions.
Respect field/project/phase permissions before requesting or returning sources.
Prefer narrow read services over one giant analytics module or duplicate tables.

### Fundamental Analysis

Include total inventory, released, available, reserved, contracted, cancelled/
returned, sell-through, monthly contracted units/value, average selling price,
branch and salesperson/advisor performance, property/unit-type demand, bedroom
mix, view demand and price/gross by useful supported physical attributes.

Use the existing commercial/legal histories and frozen sale values; disclose
cohort, active/cancelled treatment, net-versus-tax-inclusive value and denominator.
Sell-through must name its released-inventory denominator. Missing buyer/advisor/
attribute coverage is not a zero performance result. No claims of causal demand
or price premiums from descriptive groups alone.

Provide deterministic, explainable penetration/sell-through forecasting, such as
trailing three-month contracted-unit velocity. Disclose observation window,
inventory population, cancellations, zero/insufficient-history behavior and
projection assumptions. No AI model in MVP 3; a projection is not contracted sales.

### Financial Analysis

Combine authoritative Sales, Collections, Construction and Cashflow contracts:
monthly contracted value, confirmed collections/customer actual receipts,
development and construction actual outflows, forecast outflows, unrestricted
cash, funding gap, 30/60/90-day funding requirement and collection coverage.
Contracted value is not cash. Confirmed receipts and customer actual inflows are
views of the same source, not two inflows to sum. Refunds, restricted cash,
forecast versions and date cutoffs remain explicit. No new financial ledger.

### Technical Analysis

Use unit-type mix, internal/gross areas, balcony/garden/terrace mix, parking/
storage coverage, key features, consultant design stage, outstanding deliverables,
permit-linked technical position and construction-stage distribution. Gross
retains the six-component MVP 2 definition, excluding parking/storage. State
coverage and units of measure. Do not invent a generic Technical Score or infer
statutory approval, certification or delivery clearance from a physical checklist.

## Delivery and exclusions

The five product scopes and the sole temporary branch-workflow authority are in
[MVP3_ROADMAP.md](MVP3_ROADMAP.md). Acceptance criteria are established now in
[MVP3_ACCEPTANCE.md](MVP3_ACCEPTANCE.md), all initially PENDING.

PR-ENG-04 creates no product routes, module, UI feature, migration or dependency.
MVP 3 defaults to no new dependencies; no pandas, warehouse, xdist or chart package.
A chart dependency requires demonstrated insufficiency of native Product
Experience components and explicit owner approval. Production remains on main.
