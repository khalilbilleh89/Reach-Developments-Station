# Sales Workflow UI

## Overview

PR-020 introduces a structured, guided sales workflow UI.  The interface connects unit inspection (PR-019) to contract readiness in a way that reflects commercial reality — pricing, approved exceptions, and contract state are all part of the same story.

---

## Page Structure

### `/sales` — Sales Queue

**File:** `frontend/src/app/(protected)/sales/page.tsx`

Landing page for the sales workflow.  Displays a filterable queue of all units in the selected project, enriched with commercial readiness information.

Sections:
- **Project selector** — switch between projects
- **Sales filters** — narrow the queue by status, type, exception, readiness, and price range
- **Sales candidates table** — unit queue with inline pricing, exception, and readiness columns

Each row links to the guided unit-level sales workflow at `/sales/[unitId]`.

---

### `/sales/[unitId]` — Unit Sales Workflow

**File:** `frontend/src/app/(protected)/sales/[unitId]/page.tsx`

Guided workflow page for a specific unit.  Presents the full commercial picture in one view.

Sections:
- **Unit Summary** — number, type, status, area, final price, price/sqm
- **Commercial Readiness** — derived status badge + checklist of backend facts
- **Contract Action** — contract creation availability or existing contract details
- **Approved Exceptions** — all approved sales exceptions for this unit
- **Payment Plan Preview** — summary of the linked payment schedule (read-only)

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
| `GET /sales-exceptions/projects/{projectId}` | Exception list (filtered by unit) |
| `GET /sales/contracts?unit_id={unitId}` | Contract list for unit |
| `GET /payment-plans/contracts/{contractId}/schedule` | Payment schedule |

All composition and normalization happens in `lib/sales-api.ts`.  Components receive stable UI-friendly types and perform no backend interaction directly.

---

## Readiness Logic

Commercial readiness is derived in `sales-api.ts → deriveReadiness()` from backend facts only.  No frontend business calculations are applied.

| Status | Condition |
|--------|-----------|
| `under_contract` | Unit status is `under_contract` OR an active contract exists |
| `blocked` | Unit status is `registered` |
| `missing_pricing` | No pricing available from backend |
| `ready` | Unit is `available` or `reserved`, pricing exists, no active contract |

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

## Current Action Limitations

This PR is **read-only** for all backend mutations.  Specifically:

- **Contract creation** is not triggered from the frontend in this PR.  The `ContractActionPanel` shows readiness and existing contract details only.
- **Exception approval** is not possible from the frontend.  Only approved exceptions (status `approved`) are displayed.
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
- Readiness states display correctly
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
- The project context at `/sales/[unitId]` is resolved from the exception records themselves (each exception carries `project_id`), so the unit-level URL does not need to encode project context.
- Stale response guards (`isCurrent` flag) are used in async data fetching effects to prevent state updates from superseded requests.
