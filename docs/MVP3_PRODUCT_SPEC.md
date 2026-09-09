# True MVP3 product specification

## M3-01: current Portfolio management

A read-only owner/developer composition above existing domains. Portfolio owns no
transaction, ledger, table, snapshot, cache or background job. No migration or new
dependency is expected. It does not reconstruct arbitrary historical inventory.

Four GET APIs: `/api/v1/portfolio/overview`, `/projects`, `/risks`, and
`/projects/{project_id}` under that same Portfolio prefix. The frontend is one
top-level Portfolio area, outside project context, using the merged UX-04
Product Experience primitives. Overview, Projects, Risks and a management
summary link to existing source workspaces rather than duplicating them.

## Access and source ownership

Readers: system_admin, executive_viewer, approver_cfo, finance, project_manager,
auditor. System Admin retains established whole-system access. Others need active
whole-project membership. Selected-phase memberships contribute no project,
money, risk, pagination total or error metadata. The authorized project SQL
relation constrains source queries before rows enter application memory.

Owner-domain batch contracts avoid project-times-domain query growth. Portfolio
does not reach into transactional source models or recompute Cashflow or
Construction formulas. Measure one versus twenty projects and EXPLAIN grouped reads.

## Frozen financial contracts

- Inventory owns `analysis_eligible`. Active primary available, reserved,
  contract_pending, contracted and returned units qualify; sub-assets and excluded
  stock do not. Committed units are the distinct union of authoritative committed
  reservations and sale contracts, intersected with eligible units.
- Active sold follows Project Analysis. Standing contract value retains source
  currency and gross contract price. UTC activation/cancellation dates determine
  absorption. Portfolio penetration is sum committed / sum eligible * 100, with
  Decimal and exposed numerator/denominator; zero denominator is unavailable.
- Run rate follows Project Analysis's three complete UTC calendar months. A stall
  requires observed history, remaining eligible inventory and nonpositive net
  absorption; no arbitrary target for positive but slow sales.
- Collections retains original-currency confirmed gross receipts, separate refunds,
  unapplied confirmed cash and overdue outstanding. Allocations are not receipts.
  Unconfirmed receipts do not contribute. Unknown schedules or incomparable
  allocation denominations do not create a false overdue figure.
- Cashflow owns the opening anchor, actual total/restricted/unrestricted cash,
  financing, development, construction and governed forecast. Safe denominations
  must reconcile exactly to the owner. Any incompatible source invalidates the
  entire cash balance and cash-dependent risk evaluation with
  `cashflow_currency_mismatch`; no conversion, relabelling, row omission or partial
  balance. Collections still reports each original receipt currency.
- Construction owns control budget, revised commitment and EAC/version identity.
  Ex-tax commitment and gross cash-paid bases stay separate. Missing budgets or
  forecasts are unavailable. Comparisons require compatible currencies/bases.
- Land acquisition requires every purchase-price and fee component. Unknown is not
  zero. Released Commission is non-cash operational information and never affects
  cash, contracts, Construction or Unit Economics. Consultant engagement/design
  facts are independent of financial and physical construction truth.

No governed FX exists. Monetary totals use currency buckets with contributing and
missing project counts. Missing source is unavailable, incomplete aggregation is
partial. No risk observed is never presented as healthy when coverage is missing.

## Frozen risk catalogue

| Code | Severity | Predicate |
| --- | --- | --- |
| ACTUAL_CASH_DEFICIT | high | Safe actual unrestricted cash < 0 |
| FORECAST_CASH_DEFICIT | high | Valid governed peak deficit > 0 |
| CONSTRUCTION_COST_EXCEEDANCE | high | Comparable EAC > control budget |
| COLLECTIONS_OVERDUE | attention | Governed overdue outstanding > 0 |
| UNAPPLIED_CONFIRMED_CASH | attention | Confirmed unapplied cash > 0 |
| UNRESOLVED_BLOCKING_PERMIT | high | Currently unresolved owner blocker |
| OVERDUE_PERMIT | attention | Unresolved nonblocking owner overdue item |
| CONSULTANT_STAGE_OVERDUE | attention | Open active-engagement stage past forecast/planned date |
| CONSULTANT_DELIVERABLE_OVERDUE | attention | Existing unresolved active-engagement deliverable past due |
| COMMERCIAL_STALL | attention | Remaining eligible stock and 3 observed complete months, net <= 0 |

Each risk has project identity, severity, reason, value, threshold/basis,
observation date, coverage and source drilldown. Sort by severity, stable project
code/id and stable risk id. There is no composite score or generic rules engine.
Resolved/issued permits and historical Consultant engagements do not become
current blockers. No invented criticality for Consultant deliverables.

## Deferred

M3-02 owns new forward management outlook and actions, owners, due dates and
workflow. M3-03 owns governed historical snapshots, board reporting and final
acceptance/promotion. No AI, FX engine, notifications or extra roadmap PR.
