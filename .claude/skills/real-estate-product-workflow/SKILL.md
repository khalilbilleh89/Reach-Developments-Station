---
name: real-estate-product-workflow
description: Understand what a Reach record means to the business before changing it — projects, land, permits, inventory, pricing, sales, payment plans, collections, commissions, construction, cashflow, analysis and management actions. Use when a request is phrased in the owner's language ("how do I sell a unit", "release all of these", "this is too complex") or when a change crosses two domains.
---

# What the records mean

Reach models how a developer actually sells and builds. Getting the vocabulary
wrong produces a screen that is beautiful and false. Before changing a flow,
know which record the change belongs to and who owns it.

## Read before you change a workflow

| Source | What it owns |
| --- | --- |
| `docs/ARCHITECTURE.md` | The module map and how the domains relate |
| `docs/ENGINEERING_RULES.md` §3, §6 | Module boundaries; money, status dimensions, derived values, financial and legal deletion |
| `docs/UX_SYSTEM.md` §7, §8 | Unit 360, record files, and what each workspace leads with |
| `docs/DELETION_POLICY.md` and `docs/deletion_contracts.json` | What may be deleted, what must be reversed, and existing gaps |
| `app/modules/<domain>/models.py` and `permissions.py` | The authoritative record shape and who may act on it |
| The domain's own doc in `docs/` | e.g. `INVENTORY_LAUNCH.md`, `OWNER_INVENTORY_SALES.md`, `PAYMENT_INSTALLMENT_VAT.md`, `SALES_AGENT_BUYER.md`, `V2_UNIT_WORKSPACE.md`, `LAND_ANALYTICS.md`, `PERMIT_DATE_STATUS.md` |

`app/modules/` is the list of domains: access, audit, cashflow, collections,
commissions, construction, consultant_engineering, inventory,
management_actions, management_reporting, payment_plans, portfolio, prelaunch,
pricing, project_analysis, projects, sales, settings, unit_economics.

## The spine

**Project** → **Phase** → **Building** → **Floor** → **Unit**. A unit belongs to
a floor *or* directly to a building, never both. Inventory keeps Phases,
Buildings, Floors and Units as first-class views, each showing its own objects.

A unit has a permanent `id` and an editable, audited `unit_reference`. Correcting
the label must never disturb identity — that is why they are two columns.

Alongside the spine: **land parcels** (tenure separate from acquisition;
acquisition is a cost basis, not a valuation), **permits**, **common areas** and
**sub-assets** — parking and storage are separate assets, excluded from gross
area.

## The commercial chain, and what each link means

`docs/ENGINEERING_RULES.md` §6 states it: **a contract says what was agreed, a
schedule says what is due and when, a receipt says money arrived.** Merging any
two of them loses a fact somebody is accountable for.

| Record | Module | Means |
| --- | --- | --- |
| `UnitPriceVersion` | pricing | The authorised asking price, versioned. Components, area rules, premiums, escalations and benchmarks sit behind it |
| `Reservation` | sales | A hold, with adjustments and append-only status events. It can expire, be cancelled, or convert |
| `SaleContract` | sales | What was agreed: net price ex tax, parties, tax lines, legal events, cancellation |
| `PaymentPlan` → `PaymentPlanVersion` → `PaymentPlanInstallment` | payment_plans | What is due and when. Instalments may be trigger-driven. **A scheduled instalment is not a receipt** |
| `CollectionReceipt` → `CollectionReceiptAllocation` | collections | Money that arrived, and the separate, reversible human decision to apply it to an obligation |
| `CollectionRefund` | collections | Money leaving — its own record, never a negative receipt |
| `CollectionDispute`, `Waiver`, `Restructure`, `Action` | collections | Why an obligation is not being met as agreed |
| Commission grant, rate, base, beneficiary distribution, release | commissions | Each retains its original meaning; a release check is not a payment |
| `HandoverRecord`, `HandoverClearance` | sales | Delivery to the buyer, gated on clearance |

Cash that has arrived and has not been applied is **reported, not absorbed**.
An unapplied balance is somebody's money sitting in the company's account.

## Four status dimensions, never one

A unit carries **commercial**, **legal**, **collection** and **delivery** status
as four independent columns. They are never collapsed into one `status` and
never derived from one another: a unit can be contracted, registered, overdue
and under construction at the same time, and each fact belongs to a different
team.

Inventory owns the four columns and the append-only events behind them. The
domain that knows the fact decides the value and *asks* inventory to apply it,
through a named contract — never by writing the column. Unit 360 shows all four
in its header through `UnitStanding`.

Status changes are append-only events with actor, timestamp, and — for a
reversal or cancellation — a reason.

## Construction and cashflow

Cost codes → budget versions → contracts → variations → certificates → invoices
→ payments, with milestones and forecast versions beside them. Cost control
excludes tax and leads with completion variance; payable includes tax and has
its own surface. Forecast-cutoff certified work must never be presented as
today's certified figure. Dispute, retention, variation and approval semantics
are load-bearing.

Cashflow leads with unrestricted cash, with total and restricted cash alongside,
and keeps basis and forecast status visible. A missing or stale forecast must
stay apparent.

## Deletion, reversal and the difference

Every user-created record needs a visible, working, server-authorised **Delete**
— configuration choices and child rows included (`AGENTS.md`,
`docs/DELETION_POLICY.md`).

But **financial and legal transactions are not physically deleted**. They are
voided, cancelled, reversed or superseded, each recording user, timestamp and
reason. Offering a lifecycle action in place of deleting an unused draft is not
compliance; offering deletion where evidence must be retained is worse.

The one exception is the owner-approved unit-history purge in
`app/modules/inventory/purge.py`. It is narrow, explicitly confirmed, and not a
precedent for anything.

## Working from what the owner said

Requests arrive in the owner's language, not the schema's. Translate before
designing:

- *"How do I sell a unit?"* — which record does the operator create, from which
  screen, and what does each of the four dimensions read afterwards?
- *"Release all of these"* — a bulk affordance over an existing per-record
  operation. It does not get its own rules, its own permissions, or a new state.
- *"I need it less complex"* — usually means the form asks for facts the
  operator does not have yet. Removing a field is a product decision; deriving
  it in the browser is not an option (`docs/ENGINEERING_RULES.md` §6: derived
  values are derived, by the server).

When two readings would produce materially different records, **ask the owner**,
in their vocabulary. When only the presentation differs, decide and say so.

## Before you call a workflow change done

- The record you changed still means what its module says it means.
- No dimension was derived from another, and no column was written by a module
  that does not own it.
- The creation path and the removal (or reversal) path both work, are
  authorised on the server, and are scoped to the project and phase.
- `docs/deletion_contracts.json` and the PR template reflect the change.
- Backend tests for the affected domains pass against PostgreSQL —
  `scripts/ci_backend_tests.py` maps files to domains, and a shared-risk change
  runs wider. Never substitute SQLite or skip a database test.
- The documentation the change affects was updated in the same PR
  (`docs/ENGINEERING_RULES.md` §12).

Open as **Draft** and stop for independent review. A human merges.
