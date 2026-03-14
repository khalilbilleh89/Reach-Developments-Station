# Project Dashboard UI

## Status

Introduced in **PR-018**, hardened in **PR-018A**.

## Overview

The project dashboard provides the central operational view of a project's financial and sales performance. It aggregates data from multiple backend summary endpoints into a single page, giving real estate developers an immediate health snapshot of their project every morning.

The dashboard reads exclusively from backend summary endpoints. No financial calculations are performed client-side. `dashboard-api.ts` acts as the **normalization boundary** between the backend API contract and the frontend UI model.

## Directory Structure

```
frontend/src/
├── lib/
│   ├── api-client.ts               # Base fetch wrapper (auth header injection)
│   ├── auth.ts                     # Token management helpers
│   ├── dashboard-api.ts            # Dashboard query functions + normalization layer
│   └── format-utils.ts             # Shared formatCurrency() helper
├── styles/
│   └── dashboard.module.css        # Dashboard layout and card styles
├── app/
│   └── (protected)/
│       └── dashboard/
│           └── page.tsx            # Dashboard page (project selector + sections)
└── components/
    └── dashboard/
        ├── DashboardGrid.tsx           # Responsive 2-column grid layout
        ├── MetricCard.tsx              # Reusable stat card
        ├── ProjectSelector.tsx         # Project dropdown selector
        ├── FinancialSummaryGrid.tsx    # Financial metrics section
        ├── RegistrationProgressCard.tsx # Registration progress + bar
        ├── CashflowSnapshot.tsx        # Cashflow position section
        ├── SalesExceptionImpact.tsx    # Sales exception metrics
        └── __tests__/
            ├── MetricCard.test.tsx
            ├── ProjectSelector.test.tsx
            ├── FinancialSummaryGrid.test.tsx
            └── DashboardPage.test.tsx
```

## Data Sources and API Contracts

### Project list — `GET /api/v1/projects`

Backend returns `ProjectList { items: ProjectResponse[], total: int }`.
`getProjects()` unwraps the envelope and returns `Project[]`.

| Backend field | UI field |
|---|---|
| `id` | `id` |
| `name` | `name` |
| `code` | `code` |
| `status` | `status` |

### Financial summary — `GET /api/v1/finance/projects/{id}/summary`

Backend returns `ProjectFinanceSummaryResponse`. Fields are passed through directly.

| Backend field | Description |
|---|---|
| `project_id` | Project identifier |
| `total_units` | Total unit inventory |
| `units_sold` | Units with an active sale contract |
| `units_available` | Remaining unsold units |
| `total_contract_value` | Sum of all contract values |
| `total_collected` | Sum of all payments received |
| `total_receivable` | Outstanding balance to collect |
| `collection_ratio` | Fraction collected (0–1) |
| `average_unit_price` | Mean contract price per unit |

### Registration progress — `GET /api/v1/registration/projects/{id}/summary`

Backend returns `RegistrationSummaryResponse`. `getRegistrationSummary()` normalizes field names.

| Backend field | UI field | Notes |
|---|---|---|
| `registration_cases_completed` | `registered` | Completed registration cases |
| `registration_cases_open` | `in_progress` | Open/in-progress cases |
| `sold_not_registered` | `pending` | Sold units with no case opened yet |
| `registration_cases_open + completed` | `total_cases` | Total cases opened |
| `registration_completion_ratio × 100` | `registration_progress_pct` | Percentage (0–100) |

### Cashflow snapshot — `GET /api/v1/cashflow/projects/{id}/cashflow-summary`

Backend returns `CashflowForecastSummaryResponse`. `getCashflowSummary()` normalizes field names.

| Backend field | UI field |
|---|---|
| `closing_balance` | `current_cash_position` |
| `total_expected_inflows` | `expected_inflows` |
| `total_expected_outflows` | `expected_outflows` |
| `total_net_cashflow` | `net_position` |

### Sales exception impact — `GET /api/v1/sales-exceptions/projects/{id}/summary`

Backend returns `SalesExceptionSummary`. Fields are passed through directly.

| Backend field | Description |
|---|---|
| `total_exceptions` | Count of all exceptions |
| `pending_exceptions` | Awaiting approval |
| `approved_exceptions` | Approved exceptions |
| `rejected_exceptions` | Rejected exceptions |
| `total_discount_amount` | Cumulative discount value |
| `total_incentive_value` | Cumulative incentive value |

## Components

### `MetricCard`

Reusable stat card. Props: `title`, `value`, `subtitle?`, `trend?`, `icon?`. Purely presentational.

### `ProjectSelector`

Dropdown that fetches the project list on mount and notifies the parent via `onSelect` when the user switches projects. Auto-selects the first project on initial load.

### `FinancialSummaryGrid`

Displays: Total Revenue, Units Sold (with available count), Collections Received, Receivables Outstanding, Average Unit Price. Values formatted as compact currency (e.g. AED 1.5M).

### `RegistrationProgressCard`

Displays: Total Cases, Registered, In Progress, Pending, and a progress bar showing registration completion percentage.

### `CashflowSnapshot`

Displays: Current Cash Position (closing balance), Expected Inflows, Expected Outflows, Net Position. Net position includes a trend indicator. Negative values format compactly (e.g. AED -1.5M).

### `SalesExceptionImpact`

Displays: Total Exceptions (with approved/pending breakdown), Total Discount Amount, Total Incentive Value. Gives commercial visibility over all exceptions regardless of status.

### `DashboardGrid`

Simple responsive grid: 2 columns on desktop, 1 column on mobile (≤768 px). Uses `fullWidth` class for sections that span both columns.

## API Client

`lib/api-client.ts` provides a thin `apiFetch<T>()` wrapper that:

- reads `NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8000/api/v1`)
- attaches the stored Bearer token from `localStorage` (via `auth.ts`)
- throws a typed error on non-OK responses

## Design Principles

- **Backend is the source of truth.** No financial calculations are performed in the frontend.
- **Normalization at the API boundary.** `dashboard-api.ts` maps backend field names to UI-friendly names so components never read undefined fields.
- **Graceful degradation.** Each section handles loading, error, and empty states independently.
- **Isolated sections.** Each dashboard card fetches its own data — a failure in one section does not block others.
- **Consistent currency formatting.** `formatCurrency()` compacts both positive and negative values symmetrically.

## Non-goals

This dashboard does not implement:

- Unit pricing screens (PR-019)
- Sales workflow UI (PR-020)
- Payment plan / collections UI (PR-021)
- Full finance analytics with charts (PR-022)

