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
page.tsx (single data orchestrator)
  ├── getProjects()                         → project selector
  ├── getProjectFinanceSummary(id)          → kpis + collections + health summary (once)
  ├── getProjectCashflowSummary(id)         → cashflow + health summary (once)
  ├── getProjectSalesExceptionsSummary(id)  → exceptions + health summary (once)
  ├── getProjectRegistrationSummary(id)     → registration + health summary (once)
  └── getProjectCommissionSummary(id)       → commission (once)

Presentational child components (no fetching):
  FinanceKpiGrid           ← receives kpis, loading, error props
  CollectionsHealthCard    ← receives collections, loading, error props
  CashflowHealthCard       ← receives cashflow, loading, error props
  CommissionExposureCard   ← receives commission, loading, error props
  SalesExceptionImpactCard ← receives exceptions, loading, error props
  RegistrationFinanceSignalCard ← receives signal, loading, error props
  FinanceHealthSummary     ← receives collections, cashflow, exceptions, registration props
```

Each backend endpoint is called **exactly once per project selection**. All fetches run in parallel via `Promise.allSettled`. The page owns all data, loading, and error state; child cards are purely presentational.

---

## Commission Pending Exposure Semantics

Pending commission exposure is computed as:

```
pending_payouts = draft_payouts + calculated_payouts
```

**Cancelled payouts are explicitly excluded.** A cancelled payout is not pending — it is dead. Including cancelled payouts in the pending count would misrepresent the true exposure.

The backend `CommissionSummaryResponse` exposes `draft_payouts`, `calculated_payouts`, `approved_payouts`, and `cancelled_payouts` separately. All four fields are mapped through `CommissionExposure` and available to the UI.

---

## Section Error Handling

The page tracks a per-section error state. If one fetch fails, only that section shows an inline error message; all other sections remain unaffected. The shared `dataLoading` flag clears via `Promise.allSettled` after all fetches have settled (resolved or rejected).

The Finance Health Summary defaults all dimensions to "healthy" when section data is null (e.g., still loading or failed).

---

## Layout

- **Desktop:** 2-column responsive grid for section cards
- **Mobile:** Stacked single-column layout (≤768px breakpoint)
- Full-width sections: Finance Health Summary, Finance KPI Grid, Registration Signal
- Side-by-side pairs: Collections + Cashflow, Commission + Exceptions

---

## Known Current Limitations

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
