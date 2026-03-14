# Project Dashboard UI

## Status

Introduced in **PR-018**.

## Overview

The project dashboard provides the central operational view of a project's financial and sales performance. It aggregates data from multiple backend summary endpoints into a single page, giving real estate developers an immediate health snapshot of their project every morning.

The dashboard reads exclusively from backend summary endpoints. No financial calculations are performed client-side.

## Directory Structure

```
frontend/src/
├── lib/
│   ├── api-client.ts               # Base fetch wrapper (auth header injection)
│   ├── auth.ts                     # Token management helpers
│   └── dashboard-api.ts            # Dashboard query functions
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

## Data Sources

| Section | Endpoint |
|---------|----------|
| Project list | `GET /api/v1/projects` |
| Financial summary | `GET /api/v1/finance/projects/{id}/summary` |
| Registration progress | `GET /api/v1/registration/projects/{id}/summary` |
| Cashflow snapshot | `GET /api/v1/cashflow/projects/{id}/cashflow-summary` |
| Sales exception impact | `GET /api/v1/sales-exceptions/projects/{id}/summary` |

## Components

### `MetricCard`

Reusable stat card. Props: `title`, `value`, `subtitle?`, `trend?`, `icon?`. Purely presentational.

### `ProjectSelector`

Dropdown that fetches the project list on mount and notifies the parent via `onSelect` when the user switches projects. Auto-selects the first project on initial load.

### `FinancialSummaryGrid`

Displays: Total Revenue, Units Sold, Collections Received, Receivables Outstanding, Average Unit Price. Values formatted as compact currency (e.g. AED 1.5M).

### `RegistrationProgressCard`

Displays: Total Cases, Registered, In Progress, Pending, and a progress bar showing registration completion percentage.

### `CashflowSnapshot`

Displays: Current Cash Position, Expected Inflows, Expected Outflows, Net Position. Net position includes a trend indicator.

### `SalesExceptionImpact`

Displays: Total Exceptions, Total Discount Amount, Average Discount %. Gives commercial visibility over approved manual exceptions.

### `DashboardGrid`

Simple responsive grid: 2 columns on desktop, 1 column on mobile (≤768 px). Uses `fullWidth` class for sections that span both columns.

## API Client

`lib/api-client.ts` provides a thin `apiFetch<T>()` wrapper that:

- reads `NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8000/api/v1`)
- attaches the stored Bearer token from `localStorage`
- throws a typed error on non-OK responses

## Design Principles

- **Backend is the source of truth.** No financial calculations are performed in the frontend.
- **Graceful degradation.** Each section handles loading, error, and empty states independently.
- **Isolated sections.** Each dashboard card fetches its own data — a failure in one section does not block others.

## Non-goals

This dashboard does not implement:

- Unit pricing screens (PR-019)
- Sales workflow UI (PR-020)
- Payment plan / collections UI (PR-021)
- Full finance analytics with charts (PR-022)
