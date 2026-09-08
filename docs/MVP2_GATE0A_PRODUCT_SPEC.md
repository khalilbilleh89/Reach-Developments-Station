# MVP 2 Gate 0A — product specification

Gate 0A is the outstanding part of the MVP 2 operator iteration. It was previously
misclassified in this repository as MVP 3. True MVP 3 has not started.

Business authority is `Real_Estate_Development_Tracking_System_MVP (3).docx`, pages
31–32, “Updated Version Gate 0A – Comments and Changes (First Sections)”. The newer
30-page `(4)` document ends at Gate 0 and is not Gate 0A authority.

The final operator navigation is Development: Land, Permits, Pre-Launch, Consultant
Engineer, Inventory; Commercial: Sales, Payment Plans, Collections, Commissions.
G0A-01 exposes only implemented destinations: Land, Permits, Pre-Launch, Inventory;
Sales, Payment Plans, Collections. Pricing remains domain authority behind Unit 360,
and SPA/legal workflows remain inside Sales.

## G0A-01 contracts

- New Project owns the contextual operator journey for selecting CountryPack and
  Currency. System Administrator may create them without leaving the form; other
  project creators may select but do not gain global configuration authority.
- CountryPack, Currency and ReferenceValue remain normalized backend truth. Generic
  Reference Data is absent from ordinary Settings. Existing active values continue to
  resolve; project type permits free entry/suggestions and permit type creation remains
  contextual.
- Land exposes backend Decimal `total_acquisition_cost` only when purchase price and
  acquisition fees are both known. Otherwise it is null with an explicit incomplete
  basis. Financial redaction applies to inputs and result.
- Permit state `issued` remains statutory truth and is presented as Obtained / Issued.
- Pre-Launch is a narrow Development-facing facade over Cashflow Development
  Movements. It creates no expense table, ledger, cash calculation or duplicate audit.
  Project Manager and Finance may record only allow-listed, unconfirmed development
  expenses through the facade. Whole-project cash access is required. A different
  Finance user or Approver/CFO confirms; the recorder cannot confirm. Reversal retains
  history. Only confirmed rows reach actual cash once.
- `utilities` is a governed Development Movement category. Construction, financing,
  escrow and commission-distribution activity cannot enter through Pre-Launch.

The backend owns money, lifecycle, authorization, category validation, totals and cash
inclusion. React formats and displays returned Decimal strings; it performs no money
arithmetic. Product Experience 3.0 remains the design system and no dependency is added.

## Later Gate 0A scopes

G0A-02 owns Consultant Engineer and Commission Distribution. G0A-03 owns Fundamental,
Financial and Technical Analysis plus integrated acceptance and hardening. They are not
implemented or advertised by G0A-01.

## G0A-02 contracts

Consultant Engineer is independent project-level design-management truth. It records
historical main-consultant engagements (with one structurally enforced active agreement),
free-entry normalized disciplines, safely ordered design stages, and referenced
deliverables whose submitted and accepted states remain distinct. It requires whole-project
access and creates no construction, cashflow, sale, pricing, or Unit Economics record.

Commission Distribution starts only from an active authoritative SaleContract. It snapshots
the contract price, currency and unit, accepts a manually chosen positive base no greater
than that price, and calculates all money on the server with Decimal half-up currency
rounding. Beneficiary rates apply directly to the commissionable base and must sum exactly
to the granted rate and amount before a different Finance/CFO actor can release. Released
rows are immutable; reversal retains history. This ledger never posts cash and never changes
Pricing, SaleContract terms, Payment Plans, Collections, Construction, or Unit Economics.


## G0A-03 canonical analysis contracts

Project Analysis is a derived, GET-only read layer inside Project Overview. It owns
no tables, cached dashboard, transactional fact, audit event or migration. Source
domains never depend on Analysis. No dependency, BI engine, model, FX, or browser
financial formula is introduced.

Each section carries project, UTC as-of, bounded period (default 12 calendar months
including the current partial month, maximum 732 days), filters, project currency,
source basis and current snapshot date. Values distinguish available, partial and
unavailable, with reason and sample/denominator. Missing facts are not zero.

Fundamental uses SaleContract UTC activation dates and cancellation timestamps,
not reservation dates or record creation dates. Monthly activations, cancellations,
net absorption and gross contracted price (including source tax/fees) remain separate.
Standing activated contracts in the period drive rankings; a termination pending
contract remains standing until cancellation. SaleContract stores explicit branch
and advisor assignments. Unknown assignments remain visible; neither creators,
client owners nor Commission beneficiaries substitute for them. Rank by count,
then value only when all compared sales share a currency, then business label.

Current eligible inventory is active primary Unit stock with canonical commercial
state available/reserved/contract_pending/contracted/returned. Held, unreleased,
withdrawn and inactive stock is excluded. Returned units require repricing before
remarketing. Live Sales reservation/contract commitments define the numerator;
expired-but-unclosed reservations still hold their unit. Penetration is committed
eligible units / eligible units * 100. Remaining is denominator minus numerator.
Commercial, legal and delivery dimensions remain separate, with total record count.
Historical inventory is not reconstructed from today's status: position/forecast
are unavailable for a past as-of; classification tables explicitly use today's
snapshot and are marked partial in historical reads.

Run-rate sellout estimate = remaining eligible units / (net activation-minus-cancelled
sales in the last three complete UTC calendar months / 3). Project creation establishes
observation coverage. Fewer than three complete observed months, missing inventory,
or zero/negative absorption with remaining stock produces unavailable. Actual sellout
with a known inventory denominator produces zero remaining/zero months. No confidence
or predictive certainty is claimed. Percentages and estimates use Decimal half-up
to two decimal places; monetary source precision is retained.

Type/view demand uses Unit.unit_type_code and Unit.view_class_code, including unknown
buckets. Demand share is standing period sales / all such sales on eligible stock;
within-type penetration is type sales / type eligible inventory. These denominators
are shown separately. Features and notes are never parsed as view classes.

Observed view premium compares the same property type's other explicitly recorded
views: (view sum contract value / sum gross area) / (baseline equivalent) - 1, times
100. It uses the current approved six-component physical gross area, not parking,
storage or weighted pricing area. Missing/nonpositive areas, unlike area units,
absent cohorts or mixed currencies withhold the premium. It is a descriptive
observation with both sample sizes, not a market valuation.

Financial consumes the existing Cashflow source collector with no forecast version,
then includes only actual receipts/refunds, Development Movements, Construction
Payments and Financing Movements standing at cutoff. Business dates choose months;
confirmation/reversal timestamps decide whether the source stood at cutoff. Cash
keeps its original source currency; each denomination has its own monthly series.
Pre-Launch is one Development Movement and counts once. Commission release, consultant
agreements, invoices/certificates, schedules, attestations and escrow restrictions
are not cash. Refunds and financing are shown separately and included in net cash.
Contract value less receipts is not an overdue balance. Phase/building filters narrow
sales only; cash remains explicitly whole project and is never allocated artificially.

Technical shows current approved area ranges/averages and measurement coverage,
property types, recorded features, attachments, statutory Permit status, retained
Consultant context and latest physical construction completions. Whole-project
permit/design context stays distinct from filtered units. These are recorded product
facts, with no claim of buyer-issued specification provenance. Empty registers are
not a technical score or fabricated percentage.

Whole-project membership is mandatory. Fundamental allows Project Manager, Sales
Operations, Finance, CFO, Executive Viewer and Auditor. Financial excludes Sales
Operations; Technical adds Design/Engineering to Financial readers. System Admin
follows existing system access policy. Selected-phase users are refused, and Sales
Advisor/Legal/Collections receive no automatic Analysis access. No buyer PII is
returned. Overview only requests the enabled selected section, with project/section/
period-keyed request lifetime, distinct denied/failed/missing-source states and no polling.
