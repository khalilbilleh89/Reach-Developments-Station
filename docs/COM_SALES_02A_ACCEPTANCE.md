# PR-COM-SALES-02A acceptance

Governed by [Engineering Rules](ENGINEERING_RULES.md). Base: current main `97e08d3af058b19e7197648891eb10fce109b40e`, including merged #293.

## Behavior

New Reservation always presents a labelled Unit button. Initially closed, it exposes a connected document-flow panel on activation. Search and compact selectable rows live inside the panel; Load more appends unique units. The existing Sales read contract, debounce, sparse-batch progression and stale-response protection remain authoritative. No Inventory read, eligibility duplication, backend change or new dependency.

An exhausted empty query labels the persistent trigger **No available units** and shows release/approved-price guidance. Search-zero stays inside the open panel with its input available. Failure retains the selector and offers **Retry**, without claiming empty inventory.

Enter/Space use native button activation. Opening focuses search; Escape stops propagation, closes the panel and restores trigger focus. Trigger reactivation and selection also close it. No fake combobox or outside-click/portal framework. On selection, NewReservation presents the selected reference/type/floor and exact governed price in a matching trigger, with phase/building/recorded area below. Both this trigger and the existing Change selected unit path preserve DraftBoundary protection and remount a fresh, open picker. Existing reservation and owner forms are unchanged.

## Evidence

- Full frontend suite: **72 passed**, including updated browse/search/load/retry/race/selection tests and five new closed/empty/failure/keyboard/selected-trigger cases.
- Full ESLint and final changed-file lint passed. Production TypeScript/Next.js build passed after removing stale development-generated preview types; the final export contains only the normal application routes.
- Real browser, actual NewReservation/SalesUnitPicker/ReservationForm, synthetic Sales responses: open and zero-inventory layouts at **390, 768, 1024 and 1440px**. No horizontal document overflow, clipped dropdown or unreadable prices; long reference/location text wraps. Internal list scroll and Load more remain usable.
- Tab reaches the trigger with visible focus; Enter and Space open, search gains focus, Tab/Enter selects, Escape returns focus. Search-zero retains the input; load-more appends six options and disappears on exhaustion. Failure/Retry recovers options. No browser console errors observed.
- Dirty reservation: selected trigger opens the existing discard confirmation; Stay retains the draft, Discard changes opens a refreshed picker with search focus. Selected summary also inspected at 390px.
- These are synthetic component acceptance checks, not live Pyla Pearl data validation or a completed real reservation. The temporary fixture and development-generated helper files are excluded. No backend regression claim for this frontend-only change; applicable GitHub CI remains the release evidence.

## Screenshots

| Width | Open selector | Zero eligible units |
| --- | --- | --- |
| 390px | [Open](com-sales-02a/dropdown-open-390.png) | [Empty](com-sales-02a/dropdown-empty-390.png) |
| 768px | [Open](com-sales-02a/dropdown-open-768.png) | [Empty](com-sales-02a/dropdown-empty-768.png) |
| 1024px | [Open](com-sales-02a/dropdown-open-1024.png) | [Empty](com-sales-02a/dropdown-empty-1024.png) |
| 1440px | [Open](com-sales-02a/dropdown-open-1440.png) | [Empty](com-sales-02a/dropdown-empty-1440.png) |

[Selected unit and existing form at 390px](com-sales-02a/dropdown-selected-390.png).

## Impact and remaining acceptance

No dependency, API, shared domain type, schema, migration, financial formula, authorization, PII, audit, Render or environment change. Exact reference_price_ex_tax/currency_id still use existing string-money formatting and currency resolution. Missing measurements/type stay missing. Optional Inventory navigation is omitted to keep scope narrow. Roll back by reverting this frontend PR.

Keep Draft for independent review and applicable CI. After deployment, check real eligible and zero-eligible projects, exact unit/building/phase searches, loading, normal reservation and owner journeys, selected currency/reference price and refreshed Change unit eligibility. Pyla Pearl eligibility investigation remains separate.
