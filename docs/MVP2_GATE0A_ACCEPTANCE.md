# MVP 2 Gate 0A acceptance

Authority: [MVP2_GATE0A_PRODUCT_SPEC.md](MVP2_GATE0A_PRODUCT_SPEC.md). Delivery:
[MVP2_GATE0A_ROADMAP.md](MVP2_GATE0A_ROADMAP.md). Gate 0A is 2 / 3 merged while
G0A-03 is the Draft final promotion candidate to main. True MVP 3 is NOT STARTED.

G0A-01 acceptance requires evidence that an operator can use the simplified navigation,
configure a project without a mandatory Settings detour, see a truthful backend Land
acquisition total, recognize an issued permit as obtained, and record a Pre-Launch
expense which a separate authorized person confirms exactly once into Cashflow.

Required regression areas are navigation, contextual normalized configuration and its
authorization/uniqueness, ReferenceValue consumers, Decimal Land behavior and redaction,
statutory permit history, Pre-Launch category/permission/maker-checker lifecycle,
whole-project scope, actual-cash inclusion/reversal, concurrent confirmation, audit,
cross-domain independence, migration round-trip, Smoke selection, frontend lint/build,
keyboard dialogs/drawers and responsive widths 1600, 1440, 1280, 1024, 768 and 390.

G0A-01 does not pass or complete Consultant Engineer, Commission Distribution,
Fundamental Analysis, Financial Analysis or Technical Analysis. Final integrated Gate 0A
acceptance remains G0A-03 work, and historical MVP 2 UAT Pending/Partial evidence is not
rewritten.

## G0A-02 evidence areas

Independent review must verify Consultant Engineer agreement history and one-active
enforcement, normalized free-entry disciplines, contiguous stage ordering, truthful dates,
deliverable submitted/accepted distinction, whole-project permissions, audit, competing
transactions, downgrade refusal with retained history, responsive presentation, and no
financial or construction side effects.

It must separately verify active-sale provenance, contract price/currency snapshots, manual
commission base, Decimal totals, beneficiary rates against base, exact reconciliation,
maker/checker release, immutable release and retained reversal, cross-project protection,
concurrency, downgrade safety, and unchanged Sale, Pricing, Unit Economics, Cashflow,
Collections, Construction, Payment Plan, and physical-unit truth. These are acceptance areas,
not a claim that final Gate 0A acceptance has passed; G0A-03 remains final.

## G0A-02 independent review correction evidence

The correction exposes Draft Agreement selection and activation, agreement edit and
completion/termination, historical agreements, discipline edits, design-stage dates/status
and Move Up/Down, and deliverable submission/acceptance metadata. The selected agreement
owns the displayed child registers; historical agreements expose read-only controls.
Commission drafts expose term edits and beneficiary edit/removal, with server reconciliation
reloaded after mutation. Human percentages use the existing string conversion helpers.

The PostgreSQL review contracts are in `test_consultant_engineering_review.py` and
`test_commissions_review.py`. They compare full persisted rows across every unrelated
table, exercise same-project cross-engagement refusal, independently competing transactions,
retained-data downgrade refusal with unchanged revision/data, selected-phase refusal,
and actor/entity/project audit evidence. Release locks and rechecks the authoritative
sale; later cancellation leaves released history intact for explicit reversal.

Browser validation of the production export uses controlled API responses to exercise
the operator actions and stale-write request fields, Escape/focus return, and both screens
at 1600, 1440, 1280, 1024, 768 and 390px without page overflow. This is browser workflow
evidence; PostgreSQL state assertions are separate. Final CI counts and durations belong
to the PR's exact correction head. Independent acceptance remains pending.


## G0A-03 integrated acceptance evidence (2026-09-08)

This is new candidate evidence, not a rewrite of the historical MVP 2 UAT above.
G0A-01 and G0A-02 are merged; this third PR remains subject to independent review.
Only the independently approved exact candidate's merge to main completes Gate 0A.
True MVP 3 remains NOT STARTED. Historical PR #264's insufficient early closure
claim is superseded by the final Gate 0 + Gate 0A acceptance boundary.

The PostgreSQL journey in `tests/modules/test_project_analysis_uat.py` uses owning
APIs and a synthetic project: country/currency, project hierarchy, approved six-
component 120 sqm gross area, direct-price governance, reservation, signed and
activated 150,000 contract, governing schedule, confirmed receipt and allocation,
construction certification/invoice/payment, consultant deliverable acceptance,
commission release and all three Analysis reads. Land 90,000 + 10,000 is 100,000;
Permit goes through its real statutory transitions to issued. No fixture import
replaces these domain writes.

Financial reconciliation in the transaction's original currency:

| Fact | Expected |
| --- | ---: |
| Activated contract value | 150,000 |
| Confirmed customer receipt | 30,000 |
| Recorded but unconfirmed receipt, excluded | 10,000 |
| Confirmed Pre-Launch expense, counted once | 8,000 |
| Confirmed Construction payment | 12,000 |
| Project actual outflow | 20,000 |
| Net actual cash movement | 10,000 |
| Commission base / granted rate / total | 150,000 / 10% / 15,000 |
| Branch / salesperson / Cyprus branch / support allocations | 7,500 / 4,500 / 1,500 / 1,500 |

Separate checkers confirm cash and release commission. Consultant acceptance and
commission release leave cash unchanged. A full persisted-row snapshot excludes
only the commission's own rows and audit events when testing commission isolation;
Analysis reads leave all domain rows and audit events unchanged. A later owning-
API feature write appears on the next Technical read. Design acceptance does not
complete construction; a separate construction completion event changes that count.

Focused Analysis tests cover Decimal denominators (40/100; 20/40; 10/60), a
three-month [4,5,6] absorption rate of 5 and 30/5 = 6 months, zero/negative/short-
history refusal, unavailable historical inventory, UTC month boundaries,
activation/cancellation truth, explicit advisor and branch provenance, mixed
currencies, Unknown groups, comparable view premiums and missing-area refusal.
A cash test covers business dates versus later confirmation and retained historical
standing after reversal. Populated and empty GET reads do not write data.

The API matrix checks all 11 configured roles across three sections. System Admin,
Project Manager, Finance, CFO, Executive and Auditor may read all three; Sales
Operations may read Fundamental; Design Engineering may read Technical. Sales
Advisor, Legal and Collections may not read Analysis. Whole-project membership is
required: selected-phase access is refused with 403 and foreign-project reads with
404. No response embeds buyers, contact details or legal documents. The same
section visibility matrix was exercised in the built browser.

Browser acceptance used the exported production frontend served by the application
against a separate synthetic PostgreSQL database. Eighteen surfaces at each of
1600, 1440, 1280, 1024, 768 and 390 pixels passed 108 checks: Projects, Overview,
Land, Permits, Pre-Launch, Consultant, Inventory, Sales, Payments, Collections,
Commissions, Construction, Settings, the three Analysis sections, Unit 360 and
Sale/SPA. Checks covered one page h1, labelled form controls and no page-level
horizontal overflow (wide tables retain local scrolling). Desktop and 390px
screenshots were visually inspected. No JavaScript page errors were recorded.

A real browser operator created a currency, country configuration and project from
the project drawer without a Settings detour, retaining entered project fields.
Keyboard checks exercise dialog focus containment, Escape dismissal and focus
return. Project-switch testing holds a Project A Analysis response until after
client-side navigation to Project B, then releases it and verifies that A's data
cannot appear. Injected 403 and 500 responses show refusal and failure instead of
fabricated empty metrics. Unknown source coverage is separately labelled.

Migration boundaries: Analysis adds no schema or Alembic revision. Promotion
includes the accumulated G0A-02 `0017_consultant_commissions` revision above deployed
main's `0016_prelaunch_utilities`. The deployed-path test downgrades an otherwise
empty G0A-02 schema to 0016 while retaining existing project, inventory, pricing, reservation, activated sale,
governing schedule and confirmed-receipt source rows,
then upgrades to head, checks drift and compares those rows unchanged. Existing
fresh-install round-trip and retained-history downgrade refusal tests remain the
schema gates. Production data was not accessed. A software rollback must retain
the schema: destructive downgrade with consultant/commission history is refused.

Local command results and exact GitHub candidate/CI links are recorded in the Draft
PR handoff. Backend Fast and Frontend must pass on that exact head. Full is reserved
for the independently reviewed Ready candidate under the existing CI policy.
There are no dependency, deployment, workflow, queue, cache or analysis-storage changes.


Final integration also corrects two historical migration-test assumptions without
editing shipped migrations: the Utilities refusal test releases fixture read locks
before DDL and asserts the starting revision is retained; the Construction 0015
round-trip compares current metadata only after returning to head. Its intermediate
revision/table assertions and clean downgrade remain intact.
