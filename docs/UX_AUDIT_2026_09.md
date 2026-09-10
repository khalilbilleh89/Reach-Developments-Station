# Operational UX audit — September 2026

Baseline: main `1d0edfe`, including merged PR #279. Governing references:
[Engineering Rules](ENGINEERING_RULES.md), [Architecture](ARCHITECTURE.md),
[UX System](UX_SYSTEM.md). This review focuses on everyday corrections,
record lifecycle, trustworthy feedback, and completing a task without knowing
the database model.

## Findings and priority

P1 means a user can make a consequential wrong decision or lose important work.
P2 means a repeatable obstacle, misleading state, or avoidable operational effort.
These are source-confirmed findings unless explicitly described as browser
observations. The descriptions below preserve the audit baseline. All 17 corrections are now implemented in this candidate; validation and remaining limits are recorded at the end.

### 1. Unit removal is an unexplained checkbox — P1, corrected in this branch

**Trigger:** open Unit → Property → Edit unit and clear “Unit is active.”
The control sits among property features. It does not explain how this differs
from putting a unit on hold, returning it to unreleased, cancelling a sale, or
removing a mistaken entry. The register has no activity filter or inactive badge.

More seriously, `inventory.service.update_unit` accepts `is_active` without a
commercial commitment guard. The audit records the actor and changed value, but
not an operator-entered removal reason. Portfolio eligibility and technical
analysis exclude inactive units, so this can alter management populations while
the unit still has commercial records. This is a confirmed code path; a sold-unit
deactivation scenario was not executed against production.

**Correction:** provide an explicit “Deactivate unit” workflow with reason,
impact preview, activity badge, inactive filter and “Reactivate.” First define
and enforce backend rules for reserved/contracted units and concurrent sale
creation. Keep holds and contractual cancellations in their existing owners.
Do not introduce a physical delete that can erase financial/legal history.
If deletion of an accidental unused draft is desired, prove absence of all
dependent records and retained references before designing that separate action.

Evidence: `inventory/UnitWorkspace.tsx` (`UNIT_FIELDS`),
`InventoryTab.tsx` (filters and register), `app/modules/inventory/service.py`
(`update_unit`, `analysis_eligible`), `app/modules/inventory/batch.py`.

### 2. Unit type duplicates identity and unexpectedly blocks release — P1, corrected in this branch

**Trigger:** create a unit with its asset class and bedrooms, leaving the
“optional” configured unit-type code empty. Completeness previously demanded
“Unit type” before release. Operators must know an internal vocabulary even
though they have already described the property.

**Change:** remove unit type from normal unit creation, editing, register,
record summary and physical identity; retain asset class and bedrooms/bathrooms.
Remove the unconditional unit-type completeness requirement. Pricing register
identity uses the unit number instead of the classification code.

Compatibility boundary: existing stored types, import contracts, custom fields,
pricing rules/benchmarks and analysis cohorts remain readable and functional.
This is not a schema deletion or a silent rewrite of historic pricing bases.
Any project-specific required custom fields still apply. Fully retiring these
dependencies requires a separate migration and commercial-rule mapping decision.

### 3. Inactive or indistinguishable floor choices — P2, corrected in this branch

**Trigger:** add a unit from an unfiltered inventory containing multiple buildings.
The floor selector displays only floor code and label; “01 — First floor” can
occur in several buildings. The supplied list is not filtered by `is_active`,
although creation rejects an inactive floor on the backend.

**Correction:** display Phase / Building / Floor, offer active destinations only,
and keep the current drill-down preselection. Show a route to create a floor
when the active destination list is empty.

Evidence: `inventory/StructureViews.tsx` (`UnitForm`), `InventoryTab.tsx`
(`floorsForNewUnit`), inventory `create_unit`.

### 4. Units beyond the first 200 cannot be browsed — P1, corrected in this branch

**Trigger:** operate a development with more than 200 matching units. Inventory,
Sales and the retained Pricing route request a fixed limit without an offset
or next-page control. Inventory/Pricing tell the user to narrow filters. A count
does not let someone inspect every unit or discover an unknown reference.

**Correction:** add deterministic server pagination with filter/position
preservation on return from a record. Keep whole-population financial totals
separate from page counts. Test 201+ records and duplicate sort labels.

Evidence: `InventoryTab.tsx` (`PAGE`, `loadRegister`), `SalesTab.tsx` and
`PricingTab.tsx` (`limit: "200"`). Pricing is a compatibility route, not an
ordinary sidebar destination; Inventory and Sales are everyday blockers.

### 5. Inventory failure fabricates a zero-unit position — P1, corrected in this branch

**Trigger:** the units request fails. `loadRegister` installs a register containing
zero totals and an empty array alongside an error. This can put “0 units” and an
empty-state explanation on a failed data source.

**Correction:** retain an explicit failed state, suppress totals/empty-state
claims, and provide Retry. Previously loaded results may remain only if clearly
marked stale and not substituted for the new filter's result.

Evidence: `InventoryTab.tsx`, `loadRegister` catch and Position rendering.

### 6. Failed lookup requests masquerade as no available choices — P2, corrected in this branch

**Trigger:** a supporting request fails while the main register succeeds.
Inventory hides hierarchy failures; Documents hides type/attachment lookup
failures; Payment Plans replaces failed contract discovery with no schedulable
contracts; Access ignores a failed candidate-directory request; Unit Economics
leaves failed scope pickers empty.

**Consequence:** the operator cannot tell “none exist” from “could not load,” and
may enter a broader scope than intended or assume no work remains.

**Correction:** independent lookup error states with Retry; preserve the readable
register and disable only operations requiring the missing lookup. Distinguish
denied from failed. Optional land vocabulary suggestions may appropriately fail
quietly because valid free text still works; mandatory selections may not.

Evidence: `InventoryTab.tsx:loadHierarchy`, `DocumentsTab.tsx` lookup effect,
`PaymentPlansTab.tsx:load`, `AccessTab.tsx` directory effect,
`UnitEconomicsTab.tsx` pool-scope lookup.

### 7. Expense entry loses its draft on failed save — P1, corrected in this branch

**Trigger:** fill a Pre-Launch expense and submit while the API returns an error.
The parent closes/unmounts `ExpenseDialog` before awaiting `prelaunch.record`.
The error appears outside the form and the entered draft is gone.

**Correction:** keep the dialog and input values until successful persistence;
display the error there and permit retry. Apply the same success-only close rule
to the reversal reason dialog.

Evidence: `PreLaunchTab.tsx`, `adding` and `reversing` callbacks.

### 8. Pricing approval records words the approver never supplied — P1, corrected in this branch

**Trigger:** approve a price version or pricing configuration. The handler sends
the literal reason “Reviewed against feasibility.” It creates a specific review
claim from a button click without collecting that statement.

**Correction:** prompt for the approver's actual rationale, show the relevant
price/version/basis, and retain maker/checker checks. Do not populate audit
evidence with invented explanations.

Evidence: `inventory/UnitWorkspace.tsx:movePrice`,
`pricing/ConfigurationPanel.tsx` approval action.

### 9. Cashflow funding amounts collide on desktop — P1, corrected; browser reproduced

**Trigger:** the local fixture reports JOD 11,980,000.00 in each funding window at
1440px. Three `span-4` columns each render a lead-sized amount. The amounts
overlap neighboring amounts; document width grows to 1453px.

**Correction:** allow wider/fewer columns or use the compact financial-number
treatment; preserve exact digits and currency. Verify large positive/negative
amounts across the responsive widths. Do not fix by clipping or rounding money.

Evidence: `cashflow/CashflowOverview.tsx:FundingWindows`;
local screenshot `.local-tools/ux-audit/1440-cashflow.png`.

### 10. Consultant termination is a one-click consequential action — P2, corrected in this branch

**Trigger:** click “Terminate agreement” on an active consultant engagement.
The screen immediately invokes the transition, without a consequence summary
or confirmation. A button adjacent to routine completion can close the wrong
agreement.

**Correction:** a named confirmation showing agreement identity, current state,
effect on editing and retained deliverables; collect a reason if supported by
the domain contract. Preserve backend governance and history.

Evidence: `ConsultantEngineerTab.tsx`, active engagement actions.

### 11. Failed history/document loads look like no evidence exists — P1, corrected in this branch

**Trigger:** permit-history or parcel-document requests fail. Their handlers
replace the result with `[]`. The UI can then tell the user there is no history
or supporting evidence rather than that it could not be read.

**Correction:** show unavailable with Retry, independently of the main record.
Never use an empty collection as the error state for legal evidence.

Evidence: `PermitsTab.tsx:loadHistory`, `LandTab.tsx:openParcel`.

### 12. Release defaults to the wrong calendar date near midnight — P2, corrected in this branch

**Trigger:** use the Unit Release form in Riyadh shortly after midnight.
Its date comes from UTC `toISOString`, so it can default to yesterday locally.
The repository already has a local-calendar `todayISO` helper used elsewhere.

**Correction:** use that shared helper; validate a timezone-boundary example.
This concerns the form default, not conversion of stored business dates.

Evidence: `inventory/unit/UnitRelease.tsx:today`, `lib/format.ts:todayISO`.

### 13. Property corrections cannot move a unit to the right floor — P2, corrected in this branch

**Trigger:** a unit is created on the wrong floor. The API permits a scoped move
while unreleased, but the ordinary unit edit fields contain no floor selector.
The user can correct its text identity but cannot correct its actual hierarchy.

**Correction:** expose “Move to another floor” for unreleased units with explicit
destination context and consequence messaging. Retain phase access checks and
the backend status restriction. Do not recommend deleting/recreating the unit.

Evidence: `inventory/UnitWorkspace.tsx:UNIT_FIELDS`, inventory `update_unit`.

### 14. Legacy pricing copy contradicts direct selling-price entry — P2, corrected in this branch

**Trigger:** visit the retained Pricing route without an active configuration.
Its empty state says no unit can be priced until a configuration exists, while
Unit → Pricing deliberately supports direct selling-price entry without one.

**Correction:** explain the two supported modes accurately and route ordinary
users to the unit price workflow. Keep configuration requirements specific to
configuration-based generation.

Evidence: `PricingTab.tsx` no-configuration state;
`inventory/unit/SellingPriceForm.tsx` description and API call.

### 15. Commission detail uses a different navigation model — P2, corrected in this branch

**Trigger:** open a commission, then refresh or try to share its current record.
Selection is local component state and opens a Drawer; Units, Sales and Payment
Plans use durable record URLs with register return context.

**Correction:** give commission records durable identity/selection in navigation
and preserve the originating register position. Do not classify the existing
read-only permissions as a defect.

Evidence: `CommissionsTab.tsx:selected`, Drawer `onClose`;
`ui/RecordWorkspace.tsx`, `shell/recordRoutes.ts`.

### 16. Editing can be discarded by ordinary record navigation — P2, corrected in this branch

**Trigger:** type changes in the generic property edit form and navigate away
using the record's tabs or back-to-register link. Draft values live in component
state; the form and record navigation do not coordinate a dirty-state guard.

**Correction:** guard navigation only when changed data exists; allow an explicit
discard and leave unchanged forms frictionless. Cover browser navigation and
in-app tabs with a concrete interaction test before claiming universal protection.

Evidence: `projects/EditForm.tsx` local state and `ui/RecordWorkspace.tsx` links/tabs.

### 17. Cost-basis detail errors have no local recovery path — P2, corrected in this branch

**Trigger:** selecting a Unit Economics version causes its detail request to fail.
The effect awaits `loadDetail` without a catch and the action follow-up chains
another detail load without local recovery.

**Correction:** own detail loading/error/stale state separately, show Retry in
the selected version panel, and preserve the chosen version and draft inputs.

Evidence: `UnitEconomicsTab.tsx`, `loadDetail` effect and `after` callback.

## Implementation and acceptance evidence

All 17 findings have a candidate correction. This is Draft implementation evidence,
not independent review, production UAT, or a claim that remote CI has passed.

| Finding | Implemented behavior | Verification |
| --- | --- | --- |
| 1. Unit removal | Explicit deactivate/reactivate actions, entered reason, activity badge/filter. Deactivation requires unreleased status under lock; reactivation requires active hierarchy and clears pricing approval. | PostgreSQL lifecycle, commitment rejection and concurrent status-change tests; actual browser deactivate/reactivate. |
| 2. Unit type | Removed from normal creation/edit/identity and release completeness; asset class and bedrooms remain. | No-type release regression; actual creation and six-width browser checks. |
| 3. Floor choices | Full phase/building/floor labels; active hierarchy destinations only. | Source checks and actual move workflow. |
| 4. Large registers | Inventory, Sales and Pricing have URL-backed 200-row pagination, loading controls and stale-response protection. | Actual 201-unit PostgreSQL paging regression; browser 201-row fixture, refresh and Previous. |
| 5. Inventory errors | Failure shows Retry instead of a fabricated zero position. | Browser-injected 503 and successful retry. |
| 6. Lookup errors | Separate error/retry states for hierarchy, document choices, users, contracts and allocation choices; dependent submission is blocked. | Browser fault/retry checks for hierarchy, documents, users and contracts; allocation source review. |
| 7. Expense drafts | Failed save retains the dialog, entered values and error. | Browser-injected failed save. |
| 8. Approval rationale | Price and configuration approvals collect and send the approver's entered rationale. | Source review and frontend validation; no claim of a full business-role approval browser journey. |
| 9. Cashflow layout | Funding windows use full-width columns so exact financial amounts fit. | Production export at 1600/1440/1280/1024/768/390px; no document overflow. |
| 10. Termination | Confirmation names the agreement and consultant and explains the consequence. | Browser confirmation and cancellation preserve active agreement. |
| 11. Legal evidence | Permit history and land documents distinguish failures from empty results, with Retry. | Source review and frontend validation. |
| 12. Release date | Default uses the local calendar date helper. | Source review and frontend validation. |
| 13. Move unit | Explicit correction dialog for unreleased units, using the existing scoped floor update API. | Actual move and restoration on isolated QA data. |
| 14. Pricing copy | Explains direct selling-price entry separately from rule-based generation requirements. | Source review and frontend validation. |
| 15. Commission navigation | Selected commission is encoded in the URL and survives reload and Back; inaccessible selection is explained. | Authorized browser journey, reload and Back. |
| 16. Unsaved edits | Changed generic property forms prompt before links/tabs; unload protection and Navigation API traversal protection are included. | Browser Stay/Discard on tabs and browser Back in Chromium. |
| 17. Economics detail | Version detail owns loading/error/retry state and ignores stale responses. | Source review and frontend validation. |

Validation for this candidate:

- PostgreSQL: 97 lifecycle, release, concurrency and economics-history tests passed;
  the additional real 201-unit paging regression passed separately (98 total).
- Product-experience and UX-copy source checks: 103 passed in the combined run;
  the remaining structural check passed after preserving the canonical standing
  component markup (104 total). Assertions were not weakened.
- Frontend lint, production build and TypeScript checks passed.
- Ruff check/format, application compile and dependency consistency checked before commit.
- Targeted browser results and cashflow screenshots are in
  [the evidence directory](evidence/ux-audit-2026-09/). Tests used an isolated
  seeded PostgreSQL application and synthetic records, never production.
- No CI workflows, shared test fixtures, dependencies or database migrations changed.

## Scope and limits

Source review covered Inventory/hierarchy/Unit 360, Pricing, Sales, Payment Plans,
Collections, Commissions, construction, Unit Economics, Cashflow, Land, Permits,
Pre-Launch, Consultant Engineer, Documents, Access and shared form navigation.
Browser acceptance is targeted as listed above; it is not exhaustive role coverage,
a screen-reader certification, cross-browser certification or production UAT.
Browser Back protection uses the Navigation API where supported; cross-document
navigation also has the browser unload guard. Chromium was the tested browser.

Sales and legacy Pricing search are explicitly page-local. Commission detail
still uses its existing drawer, with durable URL selection. Historical unit-type
values and rule/import/report dependencies are retained; the database concept has
not been destructively removed. Units are deactivated, never hard-deleted.
Financial formulas, historical snapshots and production data remain unchanged.

Branch: `codex/ux-audit-unit-simplification`, based on main `1d0edfe`.
The candidate must remain Draft for independent review and the applicable CI lane.
Only a human merges; local results do not substitute for exact-head remote gates.
