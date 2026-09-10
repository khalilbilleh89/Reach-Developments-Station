# UX audit follow-up — 10 September 2026

Baseline: main `f4e8f9e895c5b9f91c102a88a868260e6597f7e2` (merged #280).
Governing references: [Engineering Rules](ENGINEERING_RULES.md),
[Architecture](ARCHITECTURE.md), [UX System](UX_SYSTEM.md).
The owner selected four bounded PRs, with independent review between slices.
The PR-UX-07 label below identifies this September audit follow-up; it does not
reclassify the earlier PRs that used the same UX sequence number.

## Agreed sequence

| PR | Scope | Acceptance boundary |
| --- | --- | --- |
| PR-UX-07 — Sales Workspace & Contextual Navigation | Transaction-first Sales links; correct Sale/Reservation actions; Sales → Unit → Back; Sale → Payment Plan → Back; immediate parents and register origin; mobile project identity; visible primary actions. | Current register API and existing roles. No global Sales search or transaction history. |
| PR-UX-08 — Form Safety & Trustworthy UI State | Dirty forms, reason-dialog retention, Collections stale requests, loading/error/retry consistency, action eligibility, structured validation. | Preserve edits and present trustworthy request outcomes. |
| PR-UX-09 — Search, History & Durable Workspace State | Server-side Sales search, complete transaction history, Audit pagination/filtering beyond 100, URL state and reset behavior for Actions/Outlook/Collections/Reporting. | Complete query coverage and durable workspace state. |
| PR-UX-10 — Operational Polish & Accessibility Acceptance | Business language, density/action hierarchy, titles/headings, skip navigation, field accessibility, responsive/operator acceptance and full journey QA. | Cross-workflow acceptance; no implied screen-reader or production certification from earlier checks. |

## PR-UX-07 candidate

Sales keeps the existing unit-backed commercial register and server totals, but
its first column now opens the current sale or reservation. The buyer accompanies
that primary action; **View unit** is explicit and secondary. Available units
without a current transaction expose **Reserve** in that first column. Advisor
ownership restrictions still suppress inaccessible transaction links. Reservation
workspaces and related Unit actions use Reservation labels.

Record URLs retain a same-project register `return` and a flat `trail` of parent
record URLs. Back consumes the nearest parent; the separate register link returns
directly to the origin. Parent tabs survive refresh and copied URLs. Re-entering
an ancestor through a related-record link unwinds its previous position instead
of creating a cycle. Eight parents are retained; deeper journeys discard the
oldest parents while keeping the original register. Malformed, external,
cross-project and mismatched-module context falls back safely. Existing register
session storage restores row focus, page scroll and table scroll when available;
the navigation itself requires neither storage nor browser history.

Ordinary links and post-create redirects share the same URL builder. Creation
from Sales, Unit, Sale and Payment Plans therefore retains its origin/parent.
The mobile context bar keeps the project name visible and allows long names to
wrap. Below 768px record tabs scroll with the page so a taller project bar cannot
cover them. The primary Sales action fits without horizontal scrolling.

## Engineering acceptance evidence

Production static export served by the local FastAPI application with synthetic
PostgreSQL data. Browser acceptance and pytest use separate databases.
These are engineering observations, not independent review or owner UAT sign-off.

| Check | Observed result |
| --- | --- |
| Sales → Unit → Back | Original Sales URL, search and commercial filter restored; focus returned to the View unit link. |
| Sale → Payment Plan → Back | Returned to the same sale with its Payment plan tab selected, retaining the Sales origin. |
| Sale → Payment Plan → Unit → Back | Back returned to Payment Plan; its Sale parent and Sales origin remained available. |
| Reload nested record URL | Parent and origin survived refresh on mobile. |
| Project switch from nested record | Switched to the new project's register, with no previous record, origin or trail. |
| Sales pagination | 206-unit fixture; page two (offset 200) restored to 201–206 of 206 with row focus and page scroll. |
| Deep table scroll and keyboard | Enter opened UX07-150; Back restored table y=14400.7998, page y=344.79999 and the originating link focus. |
| Reservation | Primary action opened RES-000002 with Reservation workspace labeling. |
| Reserve and post-create | First-column Reserve opened the form on mobile; preparing synthetic RES-000003 retained the filtered Sales origin. |
| Advisor restriction | Another advisor's reservation showed an ownership explanation and View unit, with no transaction link. |
| Responsive | Sales primary action and project identity visible at 320, 375, 390, 768, 1024 and 1440px; no document horizontal overflow. A long project name remained visible at 320px; mobile record tabs used static positioning. |

Evidence: [screenshots and measured state](evidence/ux07-sales-contextual-navigation/).
Navigation behavior has ten native Node tests covering the actual routing modules,
including direct/legacy links, post-create links, unsafe context, project changes,
cycle prevention and bounded trails. `npm test` runs them; `npm run build` runs
them automatically through `prebuild`, including the existing Frontend CI job.
No dependency or CI workflow changes are required.

Local verification:

- Native Node routing tests: 10 passed.
- Frontend ESLint and production webpack build, including TypeScript: passed.
- PostgreSQL-backed Product Experience, UX copy and static serving checks:
  107 initially passed; the remaining missing-class guard passed after the Sales
  cell styling was added. All 14 affected stylesheet, record architecture and UX
  copy checks passed in the follow-up run. No guards were removed or weakened.
- Ruff check/format, application/scripts compilation and dependency consistency:
  passed.

The first pytest run reset the shared synthetic QA fixtures. The saved fixture
dump was restored and reporting snapshots were recreated (new synthetic snapshot
IDs); the restored data has 23 projects, 96 actions and three snapshots. Browser
acceptance and subsequent tests were moved to distinct task-specific databases.
No production data or credentials are included in this candidate.

## Review and deferred work

Keep this candidate Draft for independent review and Backend Fast/Frontend CI.
Ready status requires accepted review; a human merge requires exact-head Full
Backend and Frontend, per Engineering Rules §10a. No merge or deployment is
authorized by local checks. Historical Partial/Pending acceptance remains intact.

Global search and complete transaction history remain PR-UX-09. Forms and stale
request handling remain PR-UX-08. This targeted Chromium acceptance is not the
full role/browser/accessibility matrix scheduled for PR-UX-10. No API, schema,
authorization, financial formula, currency or rounding behavior changed.

## PR-UX-08 candidate — Form Safety & Trustworthy UI State

This slice follows merged PR #281. It does not add Sales search/history, change
financial calculations, change authorization, or expand API/schema contracts.

- Explicit draft boundaries cover Reservation, Buyer, SPA details, payment
  schedule, receipt entry, Sales gates and management-action editors. Shared
  form and reason dialogs protect Cancel, Escape and backdrop exits. Drawer
  close, tabs, project links and browser unload/traversal use the same guard.
  Pristine forms leave directly; drafts remain in memory, never browser storage.
  Controls are disabled while saving, and failed requests retain entered values.
- Sale and Payment Plan reasons close after persistence succeeds. Conflicts
  offer a current-record refresh that keeps the typed reason. Receipt reversal
  follows the same persistence-before-close rule.
- Collections position/register and aging have separate request lifecycles.
  Project/date/filter changes immediately hide prior results. Effect cleanup
  rejects late success and failure; retries and filter round trips start fresh.
- Failed session lookup offers Retry; only 401 takes the user to sign-in.
  Shared management readers expose Retry. Sales auxiliary failures no longer
  discard a successful register response. Initial record failures can retry.
- A contracted/released unit cannot present an enabled Deactivate action.
  A payment schedule with unsaved edits cannot be submitted for approval.
  Existing server eligibility and role rules remain authoritative.
- ApiError retains structured validation paths. Buyer, Reservation, management
  Action and schedule editors retain errors, identify fields/rows and focus the
  first matching invalid control with accessible error association.

Engineering browser evidence uses a production static export and synthetic
`reach_ux08_uat`, cloned from the previous isolated UX fixture. Test-only fault
injection lives outside the repository and is not shipped. The PostgreSQL pytest
suite uses a separate throwaway database. The local database service stopped
partway through the first verification attempt; it was restarted and checks
were rerun. No production data or business records were used.

Observed engineering acceptance:

| Journey | Result |
| --- | --- |
| Pristine expense Cancel | Closed without a discard prompt. |
| Edited expense Escape / Cancel | Stay retained text; Discard closed the editor. |
| Reservation waiver returns 409 | Reason stayed visible with the error and Refresh current record. |
| Refresh then retry waiver | Reason remained unchanged; successful persistence closed the dialog. |
| Buyer create returns structured 422 | Friendly Buyer name error, input retained, first-invalid focus and aria-invalid. |
| Buyer draft → Collections / another project | Discard confirmation; Stay preserved draft; confirmed project switch completed. |
| Collections 500 | Explicit failure and Retry; recovered to actual account totals. |
| Slow 2027 request followed by 2026 request | Old amounts hidden while pending; late 2027 result did not overwrite 2026/193-day account data. |
| Receipt draft → Drawer Close / Position tab | Stay retained bank reference; confirmed Cancel discarded it. |
| Mobile receipt discard at 390px | Stay and Discard remained visible and operable; no document horizontal overflow. |
| Draft schedule → another tab | Confirmation protected changes; Discard restored the saved row label. |
| Schedule write returns structured 422 | Row-specific label error, input retained and aria-invalid focus; Submit disabled while dirty. |
| Session lookup 503 | Retry screen, no sign-in redirect; Retry restored the existing session. |

Screenshots: [UX08 evidence](evidence/ux08-form-safety/).
Native Node tests exercise the actual API error decoder and request-reader hook,
including reordered responses, retry, filter round trips and role-off/403 states.
Independent review, exact-head Full CI and owner UAT are separate gates. Historical
Partial/Pending rows remain unchanged; cross-workflow accessibility acceptance
stays in PR-UX-10.

## PR-UX-09 candidate — Search, History & Durable Workspace State

This slice follows merged PR-UX-08 (#282). PR-UX-10 remains separate. It follows
[Engineering Rules](ENGINEERING_RULES.md); independent review and owner acceptance
remain pending. No historical Partial/Pending UAT row is promoted by this work.

### Implemented behavior

- Current Sales search runs on the server across the authorized project result
  set, before pagination and totals. It matches unit reference/number, the current
  buyer, reservation, sale and SPA. A literal `%` is not a wildcard. The displayed
  reservation is deterministically the holding reservation, otherwise the newest
  preparing reservation. Older attempts remain in History.
- Transaction History lists reservations and contracts separately, including
  converted, expired and cancelled records and transactions on inactive units.
  Type, status, phase, created-date (UTC) and reference/buyer search filter the
  SQL query before its count and pagination. Stable ordering uses creation time,
  identifier and transaction type. History does not calculate pipeline totals.
- Advisor buyer ownership and phase restrictions apply in SQL before matching
  or counting transactions. Another advisor's buyer/deal is neither searchable
  nor exposed in current Sales rows. Authorized unit inventory remains visible.
- Audit retains the server total and pages through the full authorized history.
  Search covers action code, object type, actor name and reason. Exact action,
  object, actor (by selecting a displayed actor) and UTC date filters are composed
  on the server. Read failures have Retry; events show readable action text,
  original action codes and UTC timestamps.
- Actions filters, page and open action use the URL. Clear filters removes a
  linked source as well as the other removable filters. The Exceptions section's
  overdue-only context remains explicit and permanent.
- Outlook keeps project, horizon, source, page and inspected observation in the
  URL. Clear filters selects all sources and projects and resets the horizon/page.
- Collections keeps view, as-at date, search, status, aging bucket, special filter
  and selected account in the URL. Clearing filters restores today's date.
  Account identity remains mounted through register refreshes, preserving the
  existing account editor lifecycle.
- Reporting retains register project/scope/page through capture, record views,
  comparisons and the return link. Register links retain scroll/focus when
  browser storage is available. Equivalent query parameter orderings share the
  same restoration key; navigation itself does not require storage.

### Contract and dependency impact

Additive `GET /projects/{project_id}/sales/history` (API v1 prefix applies), with
`kind`, `status`, `search`, `phase_id`, `created_from`, `created_to`, `limit` and
`offset`. Its response is `{items, total}`; default page size 50, maximum 200.
`search` is added to existing Sales register and Audit reads, limited to 200
characters. Existing register response shapes remain unchanged. Advisor-only
current transaction exposure is tightened to the existing buyer reader boundary.

No database migration, financial formula, FX, rounding, lifecycle transition,
production dependency, development dependency, or CI workflow change. Existing
Sales/Audit test ownership automatically includes the added coverage.

### Engineering acceptance

Production static export served by FastAPI, with synthetic PostgreSQL fixtures.
Browser acceptance used `reach_ux09_uat`; pytest used `reach_ux09_test`. The browser
copy needed the already-existing management-reporting migration before Reporting
could load. That migration was applied only to this isolated copy. Fixture-only
history rows and one management snapshot were created; no production data used.

| Journey | Observed result |
| --- | --- |
| Complete Sales search | From the first 200 of 206 units, searching UX278-029 returned the previously unlisted final unit. Unit → Back retained the search. |
| Historical pagination | All 108 fixture transactions were reachable, including 101–108. An expired-state filter paged through all 105 expired reservations. |
| Cancelled sale | Exact SPA search found the cancelled sale; opening it showed Cancelled and Back returned to its filtered History. |
| Actions | Clear filters removed the linked source and project. A fresh load of the copied URL restored the open action and selected status. |
| Audit | Full total 432, page three 101–150, and server search returned older reservation events from September 8. |
| Outlook | A fresh load retained the 30-day horizon, All observations source and inspected observation. |
| Collections | A fresh load retained the September 9 as-at date, Rana search and selected account. |
| Reporting | A project-filtered synthetic capture retained its register context through Board Pack and the return link. |
| Responsive | At 375px, History had no document horizontal overflow (360px content width with scrollbar), usable date labels and filters; changing status reset offset 100 to the first page. |

Screenshots: [UX09 evidence](evidence/ux09-search-history/).
Native Node behavior tests: 19 passed. Initial PostgreSQL search/history/Audit
suite: 14 passed. Broader regression and exact candidate CI results are recorded
in the PR. Full operator/browser/accessibility acceptance remains PR-UX-10.
