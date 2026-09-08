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
