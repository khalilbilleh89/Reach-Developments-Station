# Finance Dashboard UI

**PR:** PR-022  
**Route:** `/finance`  
**Type:** Frontend — executive financial visibility layer

---

## Overview

The Finance Dashboard provides a consolidated, project-level financial posture screen for finance leadership, management, and commercial heads. It replaces the former placeholder at `/finance` with a fully functional decision-grade view.

This page **displays and organizes backend truth**. It does not recreate financial logic in the browser.

---

## Page Structure

```
/finance
├── Project selector
├── Finance Health Summary        ← interpretive display-state badges
├── Finance KPI Grid              ← headline financial metrics
├── Collections Health Card       ← receivables / collections posture
├── Cashflow Health Card          ← cashflow forecast posture
├── Commission Exposure Card      ← commission burden / payout exposure
├── Sales Exception Impact Card   ← discount / incentive impact
└── Registration Finance Signal   ← commercial vs legal completion gap
```

---

## Files

| File | Responsibility |
|------|---------------|
| `frontend/src/app/(protected)/finance/page.tsx` | Main finance dashboard page |
| `frontend/src/components/finance/FinanceSectionGrid.tsx` | Responsive 2-column section layout |
| `frontend/src/components/finance/FinanceKpiGrid.tsx` | Headline finance KPI card grid |
| `frontend/src/components/finance/CollectionsHealthCard.tsx` | Collections performance and receivables |
| `frontend/src/components/finance/CashflowHealthCard.tsx` | Cashflow forecast posture |
| `frontend/src/components/finance/CommissionExposureCard.tsx` | Commission burden and payout exposure |
| `frontend/src/components/finance/SalesExceptionImpactCard.tsx` | Discount / incentive impact |
| `frontend/src/components/finance/RegistrationFinanceSignalCard.tsx` | Registration completion signal |
| `frontend/src/components/finance/FinanceHealthSummary.tsx` | High-level interpretive status badges |
| `frontend/src/lib/finance-dashboard-api.ts` | Centralized API wrapper |
| `frontend/src/lib/finance-dashboard-types.ts` | Shared TypeScript types |
| `frontend/src/styles/finance-dashboard.module.css` | Page layout and card styling |

---

## Backend Dependencies

| Section | Backend Endpoint |
|---------|----------------|
| Finance KPIs | `GET /finance/projects/{id}/summary` |
| Collections Health | `GET /finance/projects/{id}/summary` (same call, different fields) |
| Cashflow Health | `GET /cashflow/projects/{id}/cashflow-summary` |
| Commission Exposure | `GET /commission/projects/{id}/summary` |
| Sales Exception Impact | `GET /sales-exceptions/projects/{id}/summary` |
| Registration Signal | `GET /registration/projects/{id}/summary` |
| Project Selector | `GET /projects` |

All backend data is fetched via `apiFetch` in `finance-dashboard-api.ts`. No financial calculations are performed in the frontend.

---

## Display-Only Derivation Rules

The `FinanceHealthSummary` component derives display state from backend-returned metrics. These are **presentational derivations only** — not financial recalculations.

| Condition | Display State |
|-----------|--------------|
| `collection_ratio >= 0.5` | Collections healthy |
| `collection_ratio < 0.5 AND >= 0.25` | Collections — watch |
| `collection_ratio < 0.25` | Collections critical |
| `net_cashflow >= 0` | Cashflow positive |
| `net_cashflow < 0` | Cashflow negative |
| `pending_exceptions == 0` | Exceptions clear |
| `pending_exceptions > 0` | Exceptions pending |
| `sold_not_registered == 0` | Registration on track |
| `sold_not_registered > 0` | Registration lag |

No IRR, NPV, or other financial calculations are performed in the browser.

---

## Data Flow

```
page.tsx
  ├── getProjects()                       → project selector
  ├── getProjectFinanceSummary(id)        → KPIs + Collections + Health Summary
  ├── getProjectCashflowSummary(id)       → Cashflow + Health Summary
  ├── getProjectSalesExceptionsSummary(id) → Exceptions + Health Summary
  └── getProjectRegistrationSummary(id)   → Registration + Health Summary

FinanceKpiGrid
  └── getProjectFinanceSummary(id)

CollectionsHealthCard
  └── getProjectFinanceSummary(id)

CashflowHealthCard
  └── getProjectCashflowSummary(id)

CommissionExposureCard
  └── getProjectCommissionSummary(id)

SalesExceptionImpactCard
  └── getProjectSalesExceptionsSummary(id)

RegistrationFinanceSignalCard
  └── getProjectRegistrationSummary(id)
```

Note: `getProjectFinanceSummary` is called twice per project selection — once by the page (for health summary derivation) and once by `FinanceKpiGrid` / `CollectionsHealthCard`. Each component manages its own fetch lifecycle independently.

---

## Section Error Handling

Each section manages its own loading and error states. If one section's API call fails, it renders an inline error message without crashing the rest of the dashboard. The Finance Health Summary defaults all sections to "healthy" when data is null.

---

## Layout

- **Desktop:** 2-column responsive grid for section cards
- **Mobile:** Stacked single-column layout (≤768px breakpoint)
- Full-width sections: Finance Health Summary, Finance KPI Grid, Registration Signal
- Side-by-side pairs: Collections + Cashflow, Commission + Exceptions

---

## Known Current Limitations

- `getProjectFinanceSummary` is fetched both by the page (for health summary) and by the individual section cards. A future optimization could hoist and cache this response.
- No chart-based visualization — metrics are displayed as numeric cards only. Advanced charts are deferred to a later PR.
- No export/download functionality — out of scope for this PR.
- Commission section requires the `/commission/projects/{id}/summary` endpoint to be available. If it returns an error, the section shows an inline error message.

---

## Tests

| Test File | Coverage |
|-----------|---------|
| `src/components/finance/__tests__/FinanceKpiGrid.test.tsx` | KPI card rendering, loading/error states, zero values, projectId changes |
| `src/components/finance/__tests__/FinanceHealthSummary.test.tsx` | All health status derivations, null props handling |
| `src/app/(protected)/finance/__tests__/FinanceDashboardPage.test.tsx` | Page rendering, project selection, section rendering, error handling, project switching |

---

## Non-Goals (This PR)

- ❌ Spreadsheet / PDF export
- ❌ New backend finance endpoints
- ❌ Advanced chart analytics (bar charts, line charts, etc.)
- ❌ Editing contracts, collections, or payment plans
- ❌ Accounting workflows
- ❌ IRR / NPV calculations
- ❌ Client-side financial recalculation
