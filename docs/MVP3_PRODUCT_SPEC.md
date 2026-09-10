# True MVP3 product specification

M3-01 is merged to main (`5363388`); M3-02 merged in PR #275 (`fceb047`).
M3-03 is a candidate in Draft PR #279 based on main `2e697c8`; MVP3 remains
2 / 3 merged. The M3-01 specification below remains
the frozen current-position and ten-risk contract.

## M3-03: prospective historical reporting candidate

Capture current authorized whole-project truth in one PostgreSQL repeatable-read
transaction. Retain immutable identity, scope, original-currency amounts, explicit
coverage, source versions, development facts and canonical 30/60/90-day outlooks.
Technical source failure aborts capture; business unavailability retains its reason.
Historical access requires every retained project; revocation denies the complete
document rather than transforming it into a partial report.

Retain full Action details only for open/in-progress positions and frozen status
counts for all actions. Retain only `(action ID, project ID, version)` for the
history visibility frontier. Terminal titles, owners and dates are not duplicated.
The per-action frontier is necessary because a single maximum history ID or time
does not prove transaction visibility: an earlier allocated ID can commit later.
Comparison reads append-only history with `prior.captured_at < occurred_at <=
current.captured_at` and the captured version limit, restricted to common projects.
It never reads mutable live actions to reconstruct a historical report. Repeated
completions are events, and completion is independent of risk resolution.

The frontier still grows linearly with the number of actions, but terminal detail
does not. This is a deliberate compact visibility index, not a second Action
warehouse. Board Packs reproduce captured positions through browser print; no PDF
dependency is added. Financial deltas require compatible source coverage, basis
and currency. Composition changes are disclosed separately from operating movement.

## M3-02: forward outlook and management commitments

Outlook is a read-only whole-project composition of owner batch contracts.
It accepts 30/60/90 days (default 90), UTC business dates, inclusive today
through horizon end. Open overdue actions are also included. Cashflow reports
governed monthly closing observations for intersecting months, with full
boundary months and no daily proration. Foreign denominations or stale sources
remain unavailable. Collections reports outstanding governing contractual
installments after confirmed allocations, in original currencies; undated
contingent obligations remain coverage gaps, never predicted cash.

Commercial uses the unchanged Project Analysis run-rate calculator. Construction
uses comparable governed EAC and budget excluding tax. Permits use unresolved
statutory SLA deadlines. Consultant dates belong only to the active engagement.
Item identity uses source identifiers/version/date, never labels or row numbers.

Management Actions owns only actions and append-only attributed history.
Project Manager and System Administrator write, following project management
permissions; Portfolio readers read authorized actions. Assignees need active
eligible whole-project access. Actions never change source state or move money.
The finite workflow is open → in_progress/completed/cancelled;
in_progress → open/completed/cancelled; completed/cancelled → open.
Cancel/reopen, due-date changes and reassignment after work starts require
reasons. Mutations compare expected_version under project/action locks; stale
updates return 409. No DELETE API exists. PostgreSQL also rejects history
updates/deletes. One migration adds only action/history persistence.

Experience 4.1 Portfolio adds Outlook, Exceptions and Actions. Exceptions keeps
frozen source risk severity separate from action lateness. Project Overview
links to its filtered register. Read-only roles never fetch assignee candidates.

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

## Remaining programme scope

M3-02 implements the forward outlook and action workflow described above.
M3-03 still owns governed historical snapshots, board reporting and final
acceptance/promotion. No AI, FX engine, notifications or extra roadmap PR.
