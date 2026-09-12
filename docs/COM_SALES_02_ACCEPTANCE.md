# PR-COM-SALES-02 acceptance

Governed by [Engineering Rules](ENGINEERING_RULES.md). Based on main d14430301edb1a7369ac5b92770082a0b7d2db0f, the merged PR #291.

New Reservation opens a browse-first SalesUnitPicker. Native option buttons show location, recorded type/area and the existing exact-money formatter/currency resolver. Search remains server-backed with a 200ms debounce, immediate old-result hiding and obsolete-response invalidation. Load more appends unique unit IDs. Empty candidate batches follow the server cursor until an eligible result or exhaustion; they never become a premature empty-inventory claim. Retry retains search and loaded options. Change unit remounts the picker to reread eligibility. ReservationForm and RegisterBuyerSaleForm keep their existing selected option and write contracts.

## Validation

- Frontend: 64 executable tests passed; full ESLint and production Next.js build passed.
- Added coverage: browse-first, rich details/exact selection, append/deduplication, final batch, search/late-response race, retry with retained rows/search, sparse batches, both empty states, owner/standard forwarding and refreshed selection.
- Ruff check and format passed (430 files); compileall app/scripts and pip check passed.
- Existing negotiated-price, buyer-registration and Sales-security tests were attempted: 43 setup errors from PostgreSQL connection timeouts. Docker Desktop's Linux engine was unavailable. No backend test pass is claimed. Rerun these suites, plus relevant eligibility/requote regression, on working disposable PostgreSQL before acceptance.
- Synthetic component browser checks at 390, 768, 1024 and 1440px: no horizontal document overflow; long names wrap; prices, search and Load more remain usable. Keyboard Tab gives a visible outline and Enter selects the option. Search hides old rows while loading; progressive loading retains rows and removes the final load button. No browser console errors observed.
- The synthetic fixture and generated development helper files are excluded from the change. These checks are not real-project operator acceptance or a completed reservation transaction. Full-shell selected-summary and real-project owner/reservation journeys remain pending.

## Screenshots (synthetic inventory)

[390px](com-sales-02/picker-390.png) · [768px](com-sales-02/picker-768.png) · [1024px](com-sales-02/picker-1024.png) · [1440px](com-sales-02/picker-1440.png)

## Impact and release

No dependencies, API/type/schema changes, migration, financial calculation, authorization, Render configuration or environment changes. All displayed money is the Sales response reference_price_ex_tax with the existing currency resolver. No client-side eligibility or Inventory writes. Roll back by reverting this frontend change.

Keep Draft for independent review. Exact-head CI is separately reported by GitHub. Full Backend and Frontend gates and human merge remain required under Engineering Rules. After deployment, validate on real released/priced units: initial browse, unit/building/phase searches, load more, select, governed currency/list price, standard reservation, owner flow, Change unit eligibility refresh and unchanged registers.
