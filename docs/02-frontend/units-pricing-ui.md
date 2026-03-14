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
2. Fetches all units for the selected project via `getUnitsByProject()`, which walks the full asset hierarchy (Project → Phases → Buildings → Floors → Units) to correctly scope results by project.
3. Fetches pricing data for each unit in parallel — 404 "not priced" responses are gracefully handled (shown as `—`); unexpected errors (5xx, auth, network) surface as an error state rather than silently treating units as unpriced.
4. Applies all active filters (status, unit type, min price, max price) client-side before rendering the table.
5. Uses a stale response guard (cleanup flag) so rapid project switches do not overwrite the current state with stale results.

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
4. Missing pricing or attributes (404 responses) display gracefully without breaking the layout.
5. Unexpected pricing errors are propagated and shown as an error message.
6. A back-link returns the user to `/units-pricing`.

---

## Components

### `UnitFilters`

**File:** `frontend/src/components/units/UnitFilters.tsx`

Controlled filter bar for the units listing.

| Filter | Type | Backend enum values |
|---|---|---|
| Status | Select | `available`, `reserved`, `under_contract`, `registered` |
| Unit Type | Select | `studio`, `one_bedroom`, `two_bedroom`, `three_bedroom`, `four_bedroom`, `penthouse`, `villa`, `townhouse`, `retail`, `office` |
| Min Price (AED) | Number input | Applied client-side against `final_unit_price` |
| Max Price (AED) | Number input | Applied client-side against `final_unit_price` |

Option values match backend enum values exactly. Human-friendly labels (e.g. "1 Bedroom", "Under Contract") are produced by the `unitTypeLabel()` and `unitStatusLabel()` helpers in `units-types.ts`.

A "Reset" button appears when any filter is active.

---

### `UnitsTable`

**File:** `frontend/src/components/units/UnitsTable.tsx`

Sortable table of unit inventory.

**Columns:** Unit, Type, Area (sqm), Status, Final Price, Price/sqm, Outdoor Area, Actions.

**Sorting:** Client-side on unit number, type, area, status, or final price (ascending/descending toggle). Sortable column headers render as `<button>` elements for full keyboard accessibility.

**Status badge colours:**

| Status | Colour |
|---|---|
| `available` | Green |
| `reserved` | Yellow |
| `under_contract` | Blue |
| `registered` | Purple |

**Price / sqm** uses `pricing.unit_area` (the backend pricing engine's resolved area, which is `gross_area` when set and `internal_area` otherwise) rather than raw `unit.internal_area`, keeping the display consistent with how `final_unit_price` was derived.

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

| Function | Endpoints used | Notes |
|---|---|---|
| `getProjects()` | `GET /projects` | Returns project list |
| `getUnitsByProject(projectId)` | `GET /phases?project_id=`, `GET /buildings?phase_id=`, `GET /floors?building_id=`, `GET /units?floor_id=` | Walks the full hierarchy to scope units by project |
| `getUnitById(unitId)` | `GET /units/{unitId}` | Single unit detail |
| `getUnitPricing(unitId)` | `GET /pricing/unit/{unitId}` | Returns `null` only on 404/not-found; propagates other errors |
| `getUnitPricingAttributes(unitId)` | `GET /pricing/unit/{unitId}/attributes` | Returns `null` only on 404/not-found; propagates other errors |
| `getUnitPricingDetail(unitId)` | Parallel fetch of unit + pricing + attributes | Used by detail page |

**Project scoping:** `getUnitsByProject()` walks the hierarchy Project → Phases → Buildings → Floors → Units using the available backend filter params at each level (`project_id`, `phase_id`, `building_id`, `floor_id`). This ensures the unit list is truly scoped to the selected project.

**Error handling:** `getUnitPricing()` and `getUnitPricingAttributes()` distinguish "not found / not configured" responses (404, "not found" in message) from unexpected errors (5xx, network, auth). Only the former returns `null`; the latter is rethrown so pages can show a proper error state.

---

### `frontend/src/lib/units-types.ts`

Shared TypeScript types:

- `UnitStatus` — `"available" | "reserved" | "under_contract" | "registered"` (mirrors backend `UnitStatus` enum)
- `UnitType` — `"studio" | "one_bedroom" | "two_bedroom" | "three_bedroom" | "four_bedroom" | "villa" | "townhouse" | "retail" | "office" | "penthouse"` (mirrors backend `UnitType` enum)
- `unitStatusLabel(status)` — maps a status enum value to a human-readable label (e.g. `"under_contract"` → `"Under Contract"`)
- `unitTypeLabel(type)` — maps a type enum value to a human-readable label (e.g. `"one_bedroom"` → `"1 Bedroom"`)
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
| `src/components/units/__tests__/UnitFilters.test.tsx` | Filter rendering, onChange callbacks with real enum values, reset behaviour, correct option sets |
| `src/components/units/__tests__/UnitsTable.test.tsx` | Row rendering, status/type label display, pricing display, sorting (via button), empty state, action callback |
| `src/app/(protected)/units-pricing/__tests__/UnitsPricingPage.test.tsx` | Project loading, unit loading, all-filter application, project switching, pricing error propagation, error/empty states |
| `src/app/(protected)/units-pricing/[unitId]/__tests__/UnitPricingDetailPage.test.tsx` | Detail page loading, price display, attributes, missing pricing, error state, back link |

All test fixtures use real backend enum values (`one_bedroom`, `under_contract`, etc.).

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

1. **No server-side status/type filtering** — the listing page fetches all units for the project and applies status/type/price filters client-side. For large projects, server-side filtering would reduce payload size.
2. **No pagination** — the hierarchy walk loads up to 500 units per floor. For very large projects, server-side pagination at the unit level should be added.
3. **Pricing not always available** — units without pricing attributes configured will show `—` in pricing columns rather than an error.
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
