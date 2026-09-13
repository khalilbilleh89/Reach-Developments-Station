# Development UI refinement — six planned PRs

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
