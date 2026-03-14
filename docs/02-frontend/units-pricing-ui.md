# Units & Pricing UI

**PR-019** — Units/Pricing UI layer for the Reach Developments Station platform.

---

## Overview

This document covers the frontend units and pricing inspection workflow introduced in PR-019.

The feature allows commercial teams to:

- Browse the full unit inventory for a project
- Inspect unit-level pricing in detail
- Compare units quickly by area, price, and status
- Understand pricing composition (base price, premiums, final price)

---

## Pages

### `/units-pricing`

**File:** `frontend/src/app/(protected)/units-pricing/page.tsx`

Main units listing page.

**Behaviour:**
1. Loads the project list on mount and auto-selects the first project.
2. Fetches all units for the selected project via `getUnitsByProject()`.
3. Fetches pricing data for each unit in parallel — pricing failures are tolerated; units without pricing data display `—`.
4. Renders a filterable/sortable `UnitsTable`.
5. Clicking "View" on any row navigates to the unit detail page.

**Empty / loading / error states:**
- Loading spinner while projects or units are fetching.
- Error message if the API call fails.
- Empty state if no project is available.
- "No units found" state inside the table if filters narrow the result to zero.

---

### `/units-pricing/[unitId]`

**File:** `frontend/src/app/(protected)/units-pricing/[unitId]/page.tsx`

Unit-level pricing detail page.

**Behaviour:**
1. Fetches unit detail, calculated price, and pricing attributes in parallel via `getUnitPricingDetail()`.
2. Renders a full-width `UnitPricingSummaryCard` at the top.
3. Below, renders `UnitAttributesPanel` and `UnitPricingBreakdown` side-by-side.
4. Missing pricing or attributes display gracefully without breaking the layout.
5. A back-link returns the user to `/units-pricing`.

---

## Components

### `UnitFilters`

**File:** `frontend/src/components/units/UnitFilters.tsx`

Controlled filter bar for the units listing.

| Filter | Type | Notes |
|---|---|---|
| Status | Select | Maps to backend `UnitStatus` enum |
| Unit Type | Select | Maps to backend `UnitType` enum |
| Min Price (AED) | Number input | Applied client-side against `final_unit_price` |
| Max Price (AED) | Number input | Applied client-side against `final_unit_price` |

A "Reset" button appears when any filter is active.

---

### `UnitsTable`

**File:** `frontend/src/components/units/UnitsTable.tsx`

Sortable table of unit inventory.

**Columns:** Unit, Type, Area (sqm), Status, Final Price, Price/sqm, Outdoor Area, Actions.

**Sorting:** Client-side on unit number, type, area, status, or final price (ascending/descending toggle).

> Pricing formulas are NOT computed in the table. All pricing values are sourced from the backend pricing engine.

---

### `UnitPricingSummaryCard`

**File:** `frontend/src/components/units/UnitPricingSummaryCard.tsx`

Compact pricing snapshot for a single unit. Displays total price, price/sqm, internal area, outdoor area, and commercial status. Reusable in both list and detail page contexts.

---

### `UnitPricingBreakdown`

**File:** `frontend/src/components/units/UnitPricingBreakdown.tsx`

Pricing composition display. Shows:

- Base Unit Price
- Floor Premium (if non-zero)
- View Premium (if non-zero)
- Corner Premium (if non-zero)
- Size Adjustment (if non-zero)
- Custom Adjustment (if non-zero)
- Total Premiums
- **Final Selling Price**

Fields are conditionally rendered — only shown if non-zero and available from the backend. The component does not fabricate or recalculate any pricing math.

---

### `UnitAttributesPanel`

**File:** `frontend/src/components/units/UnitAttributesPanel.tsx`

Displays the physical and commercial attributes of a unit: number, type, status, internal area, gross area, balcony, terrace, roof garden, and front garden areas. Optional area fields are hidden when null.

---

## API Layer

### `frontend/src/lib/units-api.ts`

Centralized API wrapper for units and pricing endpoints.

| Function | Endpoint | Notes |
|---|---|---|
| `getProjects()` | `GET /projects` | Returns project list |
| `getUnitsByProject(projectId, filters?)` | `GET /units?limit=500` | Client-side status/type filtering |
| `getUnitById(unitId)` | `GET /units/{unitId}` | Single unit detail |
| `getUnitPricing(unitId)` | `GET /pricing/unit/{unitId}` | Returns null on 404/error |
| `getUnitPricingAttributes(unitId)` | `GET /pricing/unit/{unitId}/attributes` | Returns null on 404/error |
| `getUnitPricingDetail(unitId)` | Parallel fetch of unit + pricing + attributes | Used by detail page |

> The backend `/units` endpoint filters by `floor_id` only; project-level filtering is not natively supported. The current implementation loads all units (`limit=500`) and relies on client-side filtering for status and type. A future enhancement should add server-side project filtering when the backend supports it.

---

### `frontend/src/lib/units-types.ts`

Shared TypeScript types:

- `UnitStatus` — union of all valid unit statuses
- `UnitType` — union of all valid unit types
- `UnitListItem` — unit as returned by list endpoint
- `UnitDetail` — full unit detail (alias of `UnitListItem` currently)
- `UnitPricingAttributes` — stored pricing parameters
- `UnitPrice` — calculated price result from the engine
- `UnitPricingDetail` — combined detail + pricing for the detail page
- `UnitFiltersState` — UI filter state shape
- `Project` — project summary

---

## Styles

**File:** `frontend/src/styles/units-pricing.module.css`

Page-level layout and visual rules covering:

- Filter bar and filter group layout
- Units table (responsive, striped rows, sortable headers)
- Status badge variants (available / reserved / sold / blocked / under_offer)
- Pricing summary card
- Pricing breakdown panel
- Unit attributes grid
- Detail page two-column layout (stacks to single column on mobile)
- Loading, empty, and error states

---

## Tests

| Test file | Covers |
|---|---|
| `src/components/units/__tests__/UnitFilters.test.tsx` | Filter rendering, onChange callbacks, reset behaviour |
| `src/components/units/__tests__/UnitsTable.test.tsx` | Row rendering, pricing display, sorting, empty state, action callback |
| `src/app/(protected)/units-pricing/__tests__/UnitsPricingPage.test.tsx` | Project loading, unit loading, filtering, project switching, error/empty states |
| `src/app/(protected)/units-pricing/[unitId]/__tests__/UnitPricingDetailPage.test.tsx` | Detail page loading, price display, attributes, missing pricing, error state, back link |

---

## Backend Dependencies

This UI layer reads from the following backend API endpoints. It does **not** modify any backend data.

| Endpoint | Module |
|---|---|
| `GET /api/v1/projects` | `projects` |
| `GET /api/v1/units` | `units` |
| `GET /api/v1/units/{unitId}` | `units` |
| `GET /api/v1/pricing/unit/{unitId}` | `pricing` |
| `GET /api/v1/pricing/unit/{unitId}/attributes` | `pricing` |

---

## Current Limitations

1. **No project-level unit filter on the backend** — units are fetched without a `project_id` filter because the `/units` endpoint does not currently support it. All units are loaded and client-side filtering is applied.
2. **No pagination** — the listing page loads up to 500 units. For large projects, server-side pagination should be added.
3. **Pricing not always available** — units without pricing attributes configured will show `—` in the pricing columns rather than an error.
4. **No inline premium breakdown per row** — the table shows only the final price. The full breakdown is available on the detail page.

---

## Non-goals (this PR)

- ❌ Creating or editing pricing rules
- ❌ Approving sales exceptions
- ❌ Creating sales contracts
- ❌ Editing payment plans
- ❌ Bulk editing of unit data
- ❌ Recalculating pricing in the frontend

This PR is read-only inspection of backend pricing truth.
