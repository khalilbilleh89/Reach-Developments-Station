# PR-COM-SALES-01 draft handoff

Governed by [Engineering Rules](ENGINEERING_RULES.md).
Base: `ccd8e772137f9fb3ffd97c932694a2b6b86a342c` (merged #289).
The PR and final handoff identify the exact candidate SHA; this document is part
of that candidate. The owner authorized isolated draft implementation during
post-merge CI. Main's Phase expectation failures are isolated in PR #290.
Independent review, exact-head Full and human merge remain separate gates.

## Product and read contracts

- Current Sales contains preparing/live Reservations, excluding each source
  represented by a draft/live Sale, plus draft/live Sales. Distinct preparation
  records for the same Unit remain distinct. Row identity is kind plus UUID.
- History includes all Reservation and Sale lifecycle states, including converted,
  expired and cancelled records. It shows frozen reference, agreed price and
  variance. Legal/collection columns are explicitly current Unit facts, not
  historical events. Source and successor are never summed as revenue.
- Search and pagination happen in SQL after project, phase and buyer-owner scope.
  The legacy dashboard register and legacy history API remain compatible.
- Unit options require an active available Unit, no committed Reservation/Sale,
  canonical release eligibility and a current approved Pricing basis. Search
  supports Unit reference/number, phase and building. Candidate pages default to
  30, maximum 50; release/pricing rules inspect only that bounded page. A page
  with no eligible options can still have a next cursor, explicitly explained.
- Creation repeats the eligibility/version checks under project then Unit locks.
  Activation keeps its buyer-share, deposit, exception, quote and commitment gates.
  Drafts alone do not reserve a Unit; competing drafts cannot both activate.
- Sales owns New Reservation, eligible Unit selection, buyer, price preview and
  preparation. Inventory no longer imports either commercial creation form.
  Transaction rows open Reservation/Sale; Unit inspection is secondary. Sale
  detail uses its frozen Unit reference without an Inventory detail request.
  Payment Plans remain attached to Sale. Route tests prove immediate-parent and
  register return, including successful creation without reopening an empty form.

## Price model and financial integrity

Migration `0021_sales_negotiated_price` follows `0020_management_reporting`.
It adds nullable explicit intent and optional request-key/fingerprint fields to
Reservation, the unique project/request key, and the two managed adjustment types.
There is no Unit price column duplication, historical backfill or dependency change.

`agreed_price_target_ex_tax` records the decision even at list. Keeping intent
separate from net output avoids losing it when the balancing adjustment is zero.
Pricing derives named `negotiated_price_discount` / `negotiated_price_premium`
after existing percentage adjustments and reconciles net exactly to the target.
Sales retains and zeros these rows as direction changes, with audit evidence;
generic adjustment POST/PATCH cannot manage them. Existing cash-discount totals
include the reduction, while gross includes the separately named premium.
Seller credits, paid upgrades and seller costs keep their original meanings.

Ordinary preparation edits use the frozen reference/version; explicit requote
advances it, preserves the target and withdraws stale approval. Historical null
intent retains legacy behavior. Conversion copies the frozen price snapshot.
Tax and approval thresholds use the existing quote engine. Buyer fees, taxes,
net seller economics, Collections and Payment Plan totals remain distinct.

Signed amount = agreed net minus frozen reference. Fraction = amount/reference,
rounded to six decimals. Money uses two decimals; rounding is Decimal HALF_UP.
The backend also formats the signed percentage to two decimal places. A zero
reference returns null percentage. Currency mismatch is refused; no FX or browser
financial arithmetic. Negotiation never writes Inventory's governed list price.

| Reference | Agreed | Signed amount | Fraction | Percentage |
|---:|---:|---:|---:|---:|
| 100000 | 100000 | 0.00 | 0.000000 | 0.00% |
| 100000 | 95000 | -5000.00 | -0.050000 | -5.00% |
| 100000 | 105000 | +5000.00 | 0.050000 | +5.00% |
| 150000 | 143000 | -7000.00 | -0.046667 | -4.67% |
| 0 | 100 | +100.00 | unavailable | unavailable |

The integration golden sets a 10% review threshold then negotiates 20% below
reference: exception status becomes pending and activation is refused. At-list,
below-list and above-list requote cases increase the governed reference by 25000,
retain agreed target, then compare Sale snapshot fields to Reservation exactly.
Another golden adds a percentage concession and seller cost while preserving
143000.25 net and 141000.25 effective seller revenue. Unit-options reads before
and after negotiation prove the Inventory reference remains unchanged.

## Safety and owner integration

Existing DraftBoundary guards preparation and editing. Failed preview/buyer/save
reads retain entered work. Stale 403/409 writes refresh eligibility and require
deliberate acceptance; no automatic write replay. 422 uses structured validation.
Late preview responses cannot overwrite the current input. Synchronous submit
guards plus Reservation's project-scoped request key protect duplicate preparation.
Same actor/key/payload recovers the created Reservation; mismatched payload is 409.

Master's register-buyer operation remains the existing atomic Reservation-to-Sale
path and never invents receipts, signatures or title events. The Sales UI supplies
agreed price and expected version. Its ordinary selector does not offer privileged
release overrides; existing reason-gated API authority remains. Existing-reservation
conversion refuses an attempted price replacement. No new direct Sale path exists.

## Validation and remaining acceptance

- Sales/Pricing, approval, price-lock, concurrency, security and owner regression:
  **109 passed** in the first combined run.
- Final negotiated-price, owner registration and security run: **42 passed**
  (overlaps the first run). Includes new hidden-phase and explicit owner price tests.
- Frontend: **56 passed**, including stale preview, draft retention, synchronous
  duplicate prevention, Sales boundary and creation return-context coverage.
- Production build and full ESLint passed after the final form recovery changes.
- Sales/Inventory/Pricing concurrency and migration rollback protection: **34
  passed**. Includes negotiated competing drafts, actual separate PostgreSQL
  connections/locks, and preservation after refused downgrade.
- Unit Economics profitability/history, Payment Plan money/lifecycle,
  Collections SPA progress and product UI guards: **192 passed, 1 failed**.
  The only failure was the missing Sales primary-cell wrapping class. Restoring
  that existing class fixed it; the targeted guard rerun **passed**. No financial
  regression failed. Test run counts overlap and are not a distinct-test total.
- Full Ruff check/format (430 files), compileall, dependency consistency and
  whitespace checks passed. Alembic current and heads report only
  `0021_sales_negotiated_price`; schema drift check reports no operations.

Browser acceptance at 1600, 1440, 1024, 768 and **390 is pending**. CUA fails before
executing browser code: “failed to write kernel assets: The system cannot find
the path specified. (os error 3)”. No screenshots or operator acceptance are
claimed. Required follow-up is both below/above-list journeys, keyboard/focus,
Back/Forward, selected Unit identity, local Retry and phone usability. Real Sales,
Finance/Collections and Project Management operator UAT follows narrow UX-13.

## Deployment and rollback

Deploy backend and frontend together after migration upgrade/head/current/check,
independent review and successful exact-head Full plus Frontend. No environment
variables, Render configuration, dependencies or production data were changed.
Empty-database downgrade/upgrade and schema agreement are covered. Downgrade
refuses once any target or managed negotiation record exists. Retain the schema
and use a reviewed forward correction; never discard commercial decisions to
make an old application version run. Do not roll back to an old Sales writer
that cannot preserve negotiated intent. This PR remains Draft and is not merged.

## Changed files

- `app/db/migrations/versions/0021_sales_negotiated_price.py`
- `app/modules/pricing/schemas.py`
- `app/modules/pricing/service.py`
- `app/modules/sales/api.py`
- `app/modules/sales/models.py`
- `app/modules/sales/price_facts.py`
- `app/modules/sales/registration.py`
- `app/modules/sales/schemas.py`
- `app/modules/sales/service.py`
- `app/modules/sales/workspace.py`
- `docs/ARCHITECTURE.md`
- `docs/COM_SALES_01_ACCEPTANCE.md`
- `docs/COM_SALES_01_PLAN.md`
- `docs/OWNER_INVENTORY_SALES.md`
- `docs/UX_MVP_FINISH_2026_09_11.md`
- `frontend/src/components/projects/inventory/UnitWorkspace.tsx`
- `frontend/src/components/projects/sales/ChangeSalesPrice.tsx`
- `frontend/src/components/projects/sales/labels.ts`
- `frontend/src/components/projects/sales/NewReservation.tsx`
- `frontend/src/components/projects/sales/PriceComparison.tsx`
- `frontend/src/components/projects/sales/RegisterBuyerSaleForm.tsx`
- `frontend/src/components/projects/sales/RequoteForm.tsx`
- `frontend/src/components/projects/sales/ReservationForm.tsx`
- `frontend/src/components/projects/sales/SaleOverview.tsx`
- `frontend/src/components/projects/sales/SalesGates.tsx`
- `frontend/src/components/projects/sales/SalesPriceInput.tsx`
- `frontend/src/components/projects/sales/salesRoutes.ts`
- `frontend/src/components/projects/sales/SaleWorkspace.tsx`
- `frontend/src/components/projects/SalesTab.tsx`
- `frontend/src/lib/api/index.ts`
- `frontend/src/lib/api/types.ts`
- `frontend/tests/ownerControls.test.mjs`
- `frontend/tests/recordRoutes.test.mjs`
- `frontend/tests/salesWorkspace.test.mjs`
- `scripts/ci_backend_smoke.py`
- `tests/modules/test_sales_buyer_registration.py`
- `tests/modules/test_sales_concurrency.py`
- `tests/modules/test_sales_negotiated_price.py`
- `tests/modules/test_sales_security.py`
- `tests/test_migrations.py`
