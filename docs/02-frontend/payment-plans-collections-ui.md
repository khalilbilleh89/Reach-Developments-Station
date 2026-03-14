# Payment Plans + Collections UI

## Overview

This document describes the frontend Payment Plans and Collections workflow introduced in PR-021.

The goal is to bridge the gap between backend payment/collection truth and a usable operational workflow for finance and sales ops users.

---

## Pages

### `/payment-plans`

**File:** `frontend/src/app/(protected)/payment-plans/page.tsx`

Landing page for payment plan review. Displays a project-scoped queue of payment plans with collection progress, overdue signals, and links to contract-level schedule detail.

- Project selector (loads from `/projects`)
- Filter controls (collection status, contract status, outstanding range)
- Payment plans table with sortable columns
- Results count

### `/payment-plans/[contractId]`

**File:** `frontend/src/app/(protected)/payment-plans/[contractId]/page.tsx`

Contract-level payment plan detail page. Used by finance and operations for the full picture of a contract's payment schedule and collection status.

Sections:
- Contract header (contract number, unit, buyer, status, date, price)
- Collections progress card (progress bar + metric row)
- Outstanding balance card (total due, collected, outstanding)
- Overdue installments panel (hidden when no overdue items)
- Full installment schedule table

### `/collections`

**File:** `frontend/src/app/(protected)/collections/page.tsx`

Collections-focused queue. Provides the same view as `/payment-plans` with a link to the payment plans list for detailed schedule review. Finance and sales ops can use this page as an alternative entry point for collections monitoring.

---

## Components

### `PaymentPlansTable`

**File:** `frontend/src/components/payment-plans/PaymentPlansTable.tsx`

Main list/queue table. Sortable on all key columns. Contract numbers link to the detail page.

Columns: Contract, Unit, Contract Status, Contract Value, Collected, Outstanding, Next Due, Overdue, Progress, Actions.

### `PaymentPlanFilters`

**File:** `frontend/src/components/payment-plans/PaymentPlanFilters.tsx`

Filter controls for the payment plans and collections list pages.

Filters: Collection Status (all / has overdue / in progress / fully paid), Contract Status, Min/Max Outstanding.

All filters are aligned with actual backend field values. Client-side filtering applied after initial API fetch.

### `PaymentPlanSummaryCard`

**File:** `frontend/src/components/payment-plans/PaymentPlanSummaryCard.tsx`

High-level contract/payment plan snapshot card. Displays contract value, total collected, outstanding balance, collection ratio, next due date, and overdue amount.

### `InstallmentScheduleTable`

**File:** `frontend/src/components/payment-plans/InstallmentScheduleTable.tsx`

Displays the full installment schedule for a contract. Combines payment schedule data with receivable status from the collections module.

Columns: #, Due Date, Scheduled Amount, Collected, Remaining, Status.

Status values (from backend receivable_status):
- **Paid** — installment fully settled
- **Partially Paid** — installment partially settled
- **Upcoming** — pending, not yet due
- **Overdue** — past due with outstanding balance

### `CollectionsProgressCard`

**File:** `frontend/src/components/payment-plans/CollectionsProgressCard.tsx`

Compact summary of collection performance. Displays total collected, outstanding, collection %, paid and overdue installment counts, and a progress bar.

### `OverdueInstallmentsPanel`

**File:** `frontend/src/components/payment-plans/OverdueInstallmentsPanel.tsx`

Highlights overdue installments clearly. Renders nothing when there are no overdue items.

Columns: #, Due Date, Amount Overdue, Days Overdue.

> Days Overdue is derived from due date vs. current date for display purposes only. It is not an accounting truth.

### `ContractPaymentHeader`

**File:** `frontend/src/components/payment-plans/ContractPaymentHeader.tsx`

Compact contract + unit + buyer context block shown at the top of the detail page.

Fields: Contract Number, Unit, Project, Buyer ID, Contract Status, Contract Date, Contract Price.

---

## API Layer

**File:** `frontend/src/lib/payment-plans-api.ts`

Centralized API wrapper. Composes backend endpoints and normalizes results into UI-friendly types.

### Functions

| Function | Responsibility |
|---|---|
| `getProjects()` | Fetch project list (re-exported from units-api) |
| `getPaymentPlans(projectId, projectName)` | Fetch payment plan queue for a project (units → contracts → receivables) |
| `getContractPaymentPlan(contractId)` | Fetch full detail for a contract (schedule + receivables) |
| `filterPaymentPlans(items, filters)` | Client-side filtering for the list page |

### Backend endpoints consumed

| Endpoint | Purpose |
|---|---|
| `GET /projects` | Project list |
| `GET /projects/{id}/units` | Unit list for project |
| `GET /sales/contracts?unit_id={id}` | Contracts for a unit |
| `GET /sales/contracts/{id}` | Contract detail by ID |
| `GET /payment-plans/contracts/{id}/schedule` | Payment schedule for a contract |
| `GET /collections/contracts/{id}/receivables` | Receivables summary for a contract |

---

## Types

**File:** `frontend/src/lib/payment-plans-types.ts`

Shared types for the payment plans and collections UI.

| Type | Description |
|---|---|
| `InstallmentStatus` | Status of a payment schedule line |
| `ReceivableStatus` | Computed receivable status from the collections module |
| `InstallmentRow` | A single row in the installment schedule table |
| `CollectionSummary` | High-level collections summary for a contract |
| `OverdueInstallment` | An overdue installment for the overdue panel |
| `PaymentPlanListItem` | Queue item for the payment plans table |
| `PaymentPlanDetail` | Full contract-level detail for the detail page |
| `PaymentPlanFiltersState` | UI filter state for the list page |

---

## Styles

**File:** `frontend/src/styles/payment-plans.module.css`

Page-level visual rules for:
- Filter bar
- List table (sortable headers, progress bar, badges)
- Status badges (paid / partially paid / due / upcoming / overdue)
- Contract status badges
- Overdue highlights
- Detail page layout (two-column grid, full-width sections)
- Summary, collections, and overdue panel cards

---

## Read-only Constraints

This UI is **read-only** against payment and collection logic:

- ❌ Does not edit payment schedules
- ❌ Does not create collection records
- ❌ Does not recalculate finance summaries
- ❌ Does not implement accounting journal behavior
- ❌ Does not add reminder automation

All financial values are sourced from the backend. No business logic calculations are performed on the frontend.

---

## Operational Limitations

- The payment plans queue requires at least one contract with receivables data to show results. Contracts without a generated schedule will not appear.
- Buyer name is not yet displayed (buyer_id is shown instead). A buyer lookup endpoint is not yet available.
- Project name is passed from the list page to enrich list items. On the detail page, project is not re-fetched (it shows blank unless passed via navigation).
- Days overdue is derived from due date vs. current date (display only) and resets each browser session.

---

## Test Coverage

| File | Coverage |
|---|---|
| `components/payment-plans/__tests__/PaymentPlansTable.test.tsx` | Table rendering, sorting, overdue display, progress bar, empty state |
| `components/payment-plans/__tests__/InstallmentScheduleTable.test.tsx` | All status labels, empty state, remaining amount display |
| `app/(protected)/payment-plans/__tests__/PaymentPlansPage.test.tsx` | Project loading, plan loading, project switching, error states |
| `app/(protected)/payment-plans/[contractId]/__tests__/PaymentPlanDetailPage.test.tsx` | Contract render, overdue panel visibility, error state, missing fields |
