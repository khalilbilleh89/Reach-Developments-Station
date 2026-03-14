# Sales Workflow UI

## Overview

PR-020 introduces a structured, guided sales workflow UI.  The interface connects unit inspection (PR-019) to contract readiness in a way that reflects commercial reality — pricing, approved exceptions, and contract state are all part of the same story.

PR-020A hardens the initial implementation with reliable project context propagation, batched exception loading, bounded concurrency, and aligned readiness semantics.

---

## Page Structure

### `/sales` — Sales Queue

**File:** `frontend/src/app/(protected)/sales/page.tsx`

Landing page for the sales workflow.  Displays a filterable queue of all units in the selected project, enriched with commercial readiness information.

Sections:
- **Project selector** — switch between projects
- **Sales filters** — narrow the queue by status, type, exception, readiness, and price range
- **Sales candidates table** — unit queue with inline pricing, exception, and readiness columns

Each row navigates to `/sales/[unitId]?projectId={selectedProjectId}`.  The `projectId` query parameter is always included so the detail page can load project-scoped data correctly.

---

### `/sales/[unitId]?projectId=` — Unit Sales Workflow

**File:** `frontend/src/app/(protected)/sales/[unitId]/page.tsx`

Guided workflow page for a specific unit.  Presents the full commercial picture in one view.

Sections:
- **Unit Summary** — number, type, status, area, final price, price/sqm
- **Commercial Readiness** — derived status badge + checklist of backend facts
- **Contract Action** — contract creation availability or existing contract details
- **Approved Exceptions** — approved sales exceptions for this unit
- **Payment Plan Preview** — summary of the linked payment schedule (read-only)

**Project context requirement:** This page reads `projectId` from the `?projectId=` query parameter (set by the sales queue).  Without a valid `projectId`, the approved exception panel will be empty and an informational warning is displayed.  The API layer guards against empty `projectId` and will not issue a malformed backend request.

---

## Components

| Component | File | Responsibility |
|-----------|------|----------------|
| `SalesFilters` | `components/sales/SalesFilters.tsx` | Filter controls for the sales queue |
| `SalesCandidatesTable` | `components/sales/SalesCandidatesTable.tsx` | Sortable, linked unit queue |
| `SalesReadinessCard` | `components/sales/SalesReadinessCard.tsx` | Readiness badge and checklist |
| `SalesUnitSummary` | `components/sales/SalesUnitSummary.tsx` | Compact unit summary card |
| `ApprovedExceptionPanel` | `components/sales/ApprovedExceptionPanel.tsx` | Approved exceptions display |
| `ContractActionPanel` | `components/sales/ContractActionPanel.tsx` | Contract state and action entry |
| `PaymentPlanPreview` | `components/sales/PaymentPlanPreview.tsx` | Read-only payment schedule summary |

---

## Library Files

| File | Responsibility |
|------|----------------|
| `lib/sales-types.ts` | Shared TypeScript types for the sales workflow |
| `lib/sales-api.ts` | Centralized API wrapper; composes backend endpoints |
| `styles/sales-workflow.module.css` | Layout and visual rules |

---

## Backend Dependencies

The sales workflow UI composes data from these backend endpoints:

| Endpoint | Purpose |
|----------|---------|
| `GET /projects` | Project list for the project selector |
| `GET /phases`, `/buildings`, `/floors`, `/units` | Unit hierarchy traversal |
| `GET /pricing/unit/{unitId}` | Calculated unit price |
| `GET /sales-exceptions/projects/{projectId}` | Exception list (**fetched once per project**, indexed by unit_id) |
| `GET /sales/contracts?unit_id={unitId}` | Contract list for unit |
| `GET /payment-plans/contracts/{contractId}/schedule` | Payment schedule |

All composition and normalization happens in `lib/sales-api.ts`.  Components receive stable UI-friendly types and perform no backend interaction directly.

---

## Readiness Logic

Commercial readiness is derived in `sales-api.ts → deriveReadiness()` from backend facts only.  No frontend business calculations are applied.

| Status | Condition |
|--------|-----------|
| `under_contract` | Unit status is `under_contract` OR an active contract exists |
| `blocked` | Unit status is `registered` (terminal state) |
| `missing_pricing` | No pricing available from backend |
| `needs_exception_approval` | At least one **pending** (non-approved) exception exists |
| `ready` | Unit is `available` or `reserved`, pricing exists, no active contract, no pending exceptions |

All five statuses are reachable and are reflected in the filter UI, readiness badge, and checklist.

---

## Contract Action Logic

Contract action state is derived in `sales-api.ts → deriveContractAction()`.

| Kind | Condition |
|------|-----------|
| `available` | No contract; unit is `available` or `reserved` |
| `already_active` | Contract exists with status `active` |
| `already_draft` | Contract exists with status `draft` |
| `unavailable` | Contract is `cancelled`/`completed`, or unit not in actionable state |

---

## Exception Loading

- **Queue page**: `fetchProjectExceptionsByUnit()` is called **once** per project and returns a `Map<unitId, SalesExceptionItem[]>`.  This map is reused during unit enrichment — no per-unit exception requests.
- **Detail page**: `fetchUnitExceptions()` uses the `projectId` from the URL query parameter.  If `projectId` is empty, `[]` is returned immediately without issuing a request.
- Only exceptions with `approval_status === "approved"` are passed to the `ApprovedExceptionPanel`.  Pending exceptions inform the readiness status but are not displayed in the panel.

---

## Concurrency & Performance

`getSalesCandidates()` enriches each unit with pricing and contract data.  To avoid request storms on large projects:
- Project exceptions are fetched **once** (see above).
- Pricing and contract enrichment runs with a concurrency limit of **5 concurrent requests** (`ENRICHMENT_CONCURRENCY = 5`) via a simple worker pool.

---

## Current Action Limitations

This PR is **read-only** for all backend mutations.  Specifically:

- **Contract creation** is not triggered from the frontend in this PR.  The `ContractActionPanel` shows readiness and existing contract details only.
- **Exception approval** is not possible from the frontend.  Only approved exceptions are displayed in `ApprovedExceptionPanel`.
- **Payment plan editing** is not available.  The `PaymentPlanPreview` is a summary only.
- **Pricing edits** are not available from the sales workflow.

---

## Testing

Test files:

- `components/sales/__tests__/SalesCandidatesTable.test.tsx`
- `components/sales/__tests__/SalesReadinessCard.test.tsx`
- `app/(protected)/sales/__tests__/SalesPage.test.tsx`
- `app/(protected)/sales/[unitId]/__tests__/SalesWorkflowDetailPage.test.tsx`

Coverage:
- Sales queue renders correctly
- Filters change visible results
- Readiness states display correctly (including `needs_exception_approval`)
- Detail page reads `projectId` from search params and passes to API
- Detail page shows warning when `projectId` is absent
- Navigation from queue includes `?projectId=` query param
- Table sort header click reverses sort direction
- Approved exception panel renders safely (with and without exceptions)
- Contract action panel reflects available / active / draft / unavailable states
- Payment plan preview renders summary and handles null gracefully
- Unit detail page handles missing optional data (null pricing, no exceptions)
- API errors surface correct error state

---

## Architecture Notes

- The sales workflow UI does **not** perform any pricing calculations.
- All financial values are sourced from the backend pricing engine.
- Exception approval decisions are made exclusively by the backend.
- The `projectId` is passed explicitly via query parameter from the queue to the detail page — it is **not** inferred automatically from exception records.
- Stale response guards (`isCurrent` flag) are used in async data fetching effects to prevent state updates from superseded requests.
