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
