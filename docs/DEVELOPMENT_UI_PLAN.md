# Development visual redesign — white theme

## Superseding visual redesign — white theme

The first six PRs delivered functional refinements but did not meet the owner's
visual expectations. The owner approved a substantial concept and explicitly
requires white navigation and content surfaces, dark readable typography and
restrained blue accents. This is a two-PR implementation, not another six-PR stack.

1. `eng/visual-01-white-workspaces`: white shared shell and summary surfaces,
   distinct display typography, one expanded desktop navigation hierarchy,
   Overview entry composition, Land property dossiers with an optional schedule,
   and Inventory hierarchy browsing/property cards. Based on main after #320/#325.
2. `eng/visual-02-development-delivery`, initially targets PR1: Permits, Consultant, Pre-Launch, record-page
   consistency and complete visual regression. Retarget PR2 to main only after
   the whole candidate is locally validated; PR2 becomes combined delivery.

Keep intermediate CI deferred. The narrow final frontend CI classifier now
recognizes only `eng/visual-02-development-delivery` for this same-repository
main PR and the complete allowed UI diff; the previous exception branch expires. Do not skip unrelated backend CI
or alter protections. No backend application tests for this approved UI scope.
Human review and merge remain required. Close PR1 only after verified inclusion
and human merge of PR2. No fabricated images, floor plans, geometry or figures.

Visual acceptance requires actual component screenshots at desktop/mobile,
navigation and role checks, readable empty/populated/error states, exact monetary
strings and preserved full-page editing/deletion/unsaved guards. A green build
alone is not evidence of visual completion.

### New delivery evidence

- PR1 #327 at b82d0e3: white shared shell, Overview, Land dossiers and Inventory.
- PR2: approval cards with optional schedule, consultant discipline/deliverable/history cards and a recorded-sequence timeline, expense-entry ledger with category summary and retained schedule.
- Browser checks used actual React components with labeled sample records. Land was inspected with white sidebar/ContextBar, dossier navigation and schedule. Stock floor selection, Overview, approval schedule, all consultant tabs and expense actions were inspected. Land, approval, consultant programme and expense entries were checked at 390px; inspected pages had no document-level horizontal overflow. Sample-only preview routes were removed before production validation.
- 118 frontend tests pass, including financial redaction, exact parcel selection, actual stock floor selection and server-sourced expense totals/confirmation eligibility. 39 isolated CI-routing checks pass; these are not backend application tests.
- No deployment or production record mutation has occurred. Independent acceptance, real role/API integration and post-deployment browser verification remain explicit gates. Local fixture screenshots prove presentation, not full production integration.

The sections below retain the earlier roadmap and its evidence for history.

Based on the signed-in Pyla Pearl review of 13 September 2026. Governing policies:
[ENGINEERING_RULES.md](ENGINEERING_RULES.md), [DELETION_POLICY.md](DELETION_POLICY.md)
and [UX_PAGE_AUDIT.md](UX_PAGE_AUDIT.md).

| PR | Scope | Acceptance focus |
| --- | --- | --- |
| 1 — Visual foundation | Selected-tab contrast, long-value containment and compact shared record headers. | Selected workspace, record and analysis tabs stay readable on hover and keyboard focus. Long values stay inside their columns. |
| 2 — Land | Refine register and all five parcel tabs: identity, acquisition breakdown, planning, utilities, documents and analytics. | Source units and precision preserved; reviewed constraints are distinct from confirmed status; mobile content is readily reachable. |
| 3 — Inventory and units | Clarify Stock vs Units; connect phases, buildings and floors; improve common areas, setup, import and the four unit tabs. | Actual inventory powers visual navigation; scope survives drilldowns; release blockers link to their owning records. |
| 4 — Permits | Register, application timeline, next actions and history. | Status/date inconsistencies are explained for review without silently changing workflow state. |
| 5 — Consultant Engineer | Focused agreement, programme, disciplines, deliverables and history views; full-page record forms. | Missing deliverables do not imply completion; stages with no dates remain an undated sequence. |
| 6 — Overview and Pre-Launch | Compact overview, four analysis tabs, actionable incomplete states, expense summary and register hierarchy. | Scope labels explain inventory counts; unconfirmed expenses remain distinct from cash; currencies never mix. |

The count is a delivery estimate. New backend work discovered while reconciling
source scopes may need its own focused PR rather than being hidden in visual work.
Maps, plans and property imagery require real source assets; no fabricated site
geometry or invented inventory will be presented as project evidence.

## Foundation scope

The initial patch confines hover text treatment to inactive tabs so a selected
workspace tab retains its inverse foreground. It also gives key/value grid items
a zero minimum width and reduces shared record header/fact padding. It does not
change values, API contracts, record actions, routes or business rules.

No record-creation or deletion flow is introduced or modified. Existing deletion
contracts and retained financial/legal history remain in force.

## Review gates

User-approved stack: PR 1 targets `eng/development-ui-stack`; each subsequent
implementation PR starts from and targets its predecessor. A seventh consolidated
delivery PR targets main. Intermediate PRs remain Draft and use local frontend
checks; frontend GitHub CI is deferred to the completed candidate. The user approved
no backend tests for this frontend-only stack. `scripts/ci_development_ui.mjs`
checks the complete diff for the same-repository `eng/development-ui-delivery`
PR against main. Only frontend source/tests, this plan, and the explicitly named
CI workflow, classifier and workflow-routing tests qualify. Backend, API,
migration, dependency and unrelated changes use normal CI. A failed scope check
does not grant an exemption. Intermediate feature bases remain outside CI triggers.
Main pushes keep Full Backend and Frontend; repository protections stay intact.
Any changed final candidate requires revalidation. Obtain
independent review before Ready; merge remains a human action under the engineering
rules. Check populated, empty and incomplete states at desktop, panel and mobile
widths, including selected/hover/focus tab states. Preserve Back behavior, register
filters, authorization, unsaved-change protection and deletion controls.

## Implementation and review evidence

Implementation stack: #318 foundation → #319 Land → #321 Inventory → #322 Permits
→ #323 Consultant Engineer → #324 Overview and Pre-Launch. Each draft targets its
predecessor. Consolidated delivery includes all six; do not merge them separately.
112 frontend tests, focused lint and production build passed at the sixth head.
CI scope tests are added on the delivery branch and validated separately from
backend application tests; no backend application tests ran for this UI scope.

Signed-in production review covered all six modules and their existing tabs.
Changed local components were checked with explicitly labeled sample data:
Land's five views, Stock cards/schedule and Import draft navigation, permit
cards/detail/history, Consultant programme/history/full-page editing, Pre-Launch
filtering and unsaved editing, and incomplete Feasibility at mobile width.
These fixtures are not production data and are not shipped. Populated analytics,
role-specific API integration and independent review remain delivery limitations.
No project imagery, site geometry, monetary trend or dated milestone was invented.
Financial analysis retains the existing currency-separated monthly cash view;
additional imagery/charts need appropriate source data and a focused follow-up.

White redesign delivery: #328 targets main and includes #327 at b82d0e3. Full frontend lint and production build passed. Final frontend CI is triggered by this documentation commit after retargeting; draft status remains until independent acceptance.

## Architectural property pass (supersedes the previous delivery exception)

After reviewing public real-estate product examples, the owner authorized a creative implementation focused on Inventory and Land. Branch eng/architectural-property-workspace starts from main after merged #328. Deliver as one PR; there is no dependent stack needed for this contained pass.

Inventory now starts with a building/floor schematic, selectable full-record links, commercial/delivery colour lenses and a dynamic text legend. Equal-width tiles carry no physical layout or area-proportional meaning; floors follow register order. Counts and groups explicitly cover the current filtered page. Property cards and schedule remain available. All prices use existing currency/visibility/stale-price handling.

Land has a compact search/view toolbar, architectural parcel identity, readable area typography and a lighter acquisition/planning context. Mobile navigation becomes one scrollable row; all links remain accessible. No fabricated site plan, geographic shape, stock photography or API data is introduced.

The frontend-only CI exception now applies solely to this exact same-repository branch targeting main, using the complete allowlisted diff. Earlier delivery branches no longer qualify. No backend application tests or changes, dependencies, endpoints, schema or financial formula changes. Full-page records, removal, history and unsaved-change handling are retained. Independent review precedes merge.

Architectural pass validation: 120 frontend tests, full ESLint, production Next.js build and 39 isolated CI routing checks passed. Desktop/multi-building and 390px mobile sample previews inspected; no document overflow on Land/Inventory. Temporary sample routes removed. Final GitHub CI runs when the completed draft is opened.

## Development briefing follow-up — 13 September 2026

Single PR from main after #329: `eng/development-briefing`.

- Overview pairs compact project entry cards with a white development diary. It reads existing permit targets and role-gated active consultant work, sorts recorded dates, retains past targets for review, and labels planned, forecast and due dates distinctly. Failed reads expose retry and denied reads remain explicit.
- Permit approval cards highlight only the current workflow family; earlier steps are not represented as completed. On-hold, withdrawn and expired records have no active step.
- Programme stages include their assigned deliverables, revisions and due dates. Authorized updates reuse the existing full-page editor and retain agreement/history boundaries.
- White theme, existing role gates, money handling and deletion workflows remain in place. No new API, dependency, database change, record creation or fake business data.

Validation: 124 frontend tests, full ESLint and production Next.js build passed. Desktop and narrow-phone sample previews inspected; deliverable editor identity and Back checked. Temporary sample routes removed before build. 39 isolated CI workflow tests passed; no backend application tests run.

CI: the existing complete-diff, same-repository frontend-only PR exception is restricted to this exact branch. The previous architectural branch no longer qualifies. Forks, unrelated paths and main pushes retain normal CI. This is a draft for independent review under ENGINEERING_RULES.md; no deployment claim.

## Blue accents and icons — 13 September 2026

Follow-up to merged #330, one PR on `eng/development-blue-icons`. Restore hidden Development page glyphs; give sidebar icons blue tiles and selected icons a solid blue treatment. Add explicit labelled Land/Consultant tab icons and Overview entry/diary icons using the existing SVG set. Pale blue highlights diary headers, parcel identity, building headers, record facts and secondary buttons. Main reading surfaces remain white; status colours and danger actions retain their meaning.

Optional tab icons preserve text, accessible names and keyboard behavior. No icon dependency, inferred icon labels, API, records or financial calculations added. Desktop Overview/Permits and narrow-phone Consultant previews inspected; phone page width equals scroll width. Sample routes removed. Existing frontend tests (124) and isolated CI-routing tests (39) passed. Final lint/build and GitHub results are recorded in the PR.

The same-repository, complete-diff frontend-only PR exception now applies only to this branch; merged briefing branch, main pushes, forks and unrelated paths retain normal CI. Draft review policy remains unchanged.

## Property presentation — roadmap phase 1

One PR from main after #331: `eng/property-presentation`.

- Inventory adds a building selector across the building stack and property cards. Stable phase/building IDs keep identically named locations distinct. Selecting a building resets the floor selection. All building/floor counts explicitly cover the current register page; Schedule continues to show the complete loaded page.
- Property cards separate commercial and delivery badges, add labelled bedroom/bathroom/parking icons, show recorded outlook and balcony measurements, and retain exact launch prices and price-access gates. Unknown quantities remain unknown; zero stays zero. White reading surfaces, pale blue context, green success and red blockers carry specific meanings.
- Parcel cards group title/ownership, acquisition and planning into distinct readable sections. Existing full-page opening, financial visibility and source fields remain unchanged.
- Mobile building and floor selectors scroll horizontally, keeping properties near the top. Desktop and phone sample previews shown and inspected; no document-level horizontal overflow. No stock photography, fabricated plans or new media fields.

Validation: 126 frontend tests and 39 isolated CI-routing tests passed. New tests cover building identity/filter persistence, schedule scope, separate status tones and unknown versus zero quantities. Lint/build and final-head GitHub evidence recorded in the PR. Sample routes removed before build. No backend application tests run.

CI exception remains exact-branch, same-repository and full-diff scoped; previous branches, main pushes and unrelated paths use normal CI. Draft requires independent review under ENGINEERING_RULES.md. Next roadmap phases: Development workspace, then remaining-platform consistency.
