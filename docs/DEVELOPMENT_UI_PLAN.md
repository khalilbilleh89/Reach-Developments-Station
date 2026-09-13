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
no backend tests for this frontend-only stack. Final scoped CI routing remains to
be implemented and verified before delivery; unrelated CI and protections stay intact.
Any changed final candidate requires revalidation. Obtain
independent review before Ready; merge remains a human action under the engineering
rules. Check populated, empty and incomplete states at desktop, panel and mobile
widths, including selected/hover/focus tab states. Preserve Back behavior, register
filters, authorization, unsaved-change protection and deletion controls.
