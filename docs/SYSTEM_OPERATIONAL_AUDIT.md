# SYSTEM OPERATIONAL AUDIT

PR-AUDIT-001 — full-system operational completeness, bug, UX and workflow audit.
This file is the evidence ledger for that pull request. Every "PASS" below names
the evidence that produced it; nothing is marked PASS on the strength of a page
loading or a button existing.

```text
Baseline SHA:        1496be3795d8478749c8f9b14aa5cc2e97456ddf (main, #374)
Final head SHA:      the pull request head; see the PR's final comment for the exact SHA
                     (this document is committed in that head, so it cannot name itself)

Modules reviewed:    20 backend domains (app/modules/*) + shell/settings/portfolio
Pages reviewed:      32 routed destinations (25 project sections, 4 settings sections,
                     portfolio, projects register, home) at 1440px and 390px as
                     System Administrator; 25 project sections at 1440px for each of
                     11 further seeded roles; Overview additionally at 1280/1024px
Roles reviewed:      11 of the 12 repository roles in the browser — system_admin,
                     project_manager, design_engineering, sales_operations,
                     sales_advisor, legal, collections, finance, approver_cfo,
                     executive_viewer, auditor — plus a selected-phase
                     project_manager. master_admin was not seeded; its paths are
                     covered only by the existing PostgreSQL tests.
Workflows exercised: 30 journeys in the table below (evidence depth stated per row)

Findings:            51 total (28 fixed, 4 decisions, 19 follow-ups)
P0:                  0
P1:                  4   (4 fixed)
P2:                  35  (20 fixed, 3 decisions, 12 follow-ups)
P3:                  12  (4 fixed, 1 decision, 7 follow-ups)

Fixed in this PR:                    28
Remaining business-decision blockers: 4
Remaining structural follow-ups:      19

Desktop workflows:   Team, FAQs, Agreements, Project Images, Sales gates, refund
                     recording, Collections register/account, Marketing editors,
                     Company form — driven in Chromium at 1440px
Mobile workflows:    Team CRUD, FAQ CRUD + copy, Agreement upload/download/delete,
                     refund recording, Marketing/Company editors — driven at 390px;
                     no horizontal overflow on any of the 32 destinations at 390px

Financial reconciliation: PASS on the seeded project (figures below)
Permission isolation:     7 isolation/authorization defects fixed; 1 decision (B-02)
Migration integrity:      PASS — single head 0043_commercial_faqs; upgrade from empty
                          DB and `alembic check` clean; this PR adds no migration
Deletion lifecycle:       96 creators inventoried; guard now scans every router;
                          remaining gaps listed as follow-ups
Audit logging:            every mutation route audited (scripted scan); B-02 open
Frontend/API contract:    492 client call sites resolved against 529 routes;
                          1 live 422 (fixed), 1 enum gap (fixed)
CI V2:                    plan computed locally: System risk (shared test harness
                          file tests/deletion_baseline_gaps.json and app/main.py) →
                          complete Backend regression required
Full Backend Shadow:      see PR comment; requested once on the stable head
```

## How the audit was run

- **Environment.** Local PostgreSQL 16, Python 3.13, Node 22, the production static
  export served by FastAPI, headless Chromium through Playwright. No production data
  and no production connection were used.
- **Synthetic data.** Seeded through the application's real HTTP routes by reusing
  the PostgreSQL test fixtures in `tests/modules/conftest.py`: project "Galini Blu"
  (JOD), two phases, buildings, floors and units, approved areas, governed pricing,
  released units, two buyers, two reservations converted to contracts, two active
  20/30/50 payment plans, confirmed receipts, an allocation, a cancellation with
  CFO-approved financial terms, an active construction budget, contract and
  certified certificate, a construction forecast, land cost, and one user per role.
- **Static sweeps.** Five parallel read-only reviews (raw identifiers / dates /
  browser arithmetic; frontend↔API contract; deletion lifecycle; authorization and
  isolation; navigation, forms, pickers and states). Every finding they reported
  was re-checked against source before it entered this ledger; findings that did
  not survive verification are not listed.
- **Baseline.** The complete backend suite on the baseline SHA, four local shards:
  951 + 950 + 950 + 950 = **3,801 passed, 0 failed**.

## Financial reconciliation (seeded project, as at 29 Sep 2026)

Collections register, read in the browser and against the API:

| Figure | Screen | Reconciles to |
| --- | --- | --- |
| Outstanding | JOD 325,000.00 | 160,000.00 (SPA-0001) + 165,000.00 (SPA-0002) |
| Due now / Overdue | JOD 259,000.00 | 160,000.00 + 99,000.00 |
| Ageing buckets | 82,500 + 176,500 + 66,000 (awaiting trigger) | = 325,000.00 outstanding |
| Unapplied cash | JOD 25,000.00 | 5,000.00 (10,000 receipt, 5,000 applied) + 20,000.00 |
| Confirmed receipts, lifetime | JOD 30,000.00 | 10,000.00 + 20,000.00 |
| Refund due (SPA-0002) | JOD 18,000.00 | 20,000.00 eligible × (1 − 0.10 deduction) |
| Refund still to pay | JOD 18,000.00 | unchanged after a recorded 5,000.00 repayment: a recorded refund counts only once Finance confirms it |

The same figures appear on Overview, the register and the account; none is
computed in the browser. SPA-0002 is in `termination_pending` (notice stage), so
its receivable is still live by the documented rule in
`docs/CANCELLED_SALE_RECEIVABLE.md`; see B-01.

## Required end-to-end workflow table

Evidence depth: **B** browser-driven on the built export; **A** real HTTP routes
(seed or existing PostgreSQL tests); **S** verified source review; **R** read-only
browser inspection.

| # | Journey | Depth | Status | Findings |
| --- | --- | --- | --- | --- |
| 01 | Project create → configure → confirm | A, R | PASS | UI creation form not browser-driven in this audit |
| 02 | Currency mistake → governed correction | A, S | PASS | Existing `test_project_currency_correction.py` in the Full run; F-03 hardening |
| 03 | Land → planning → permit | A, R | FOLLOW-UP | S-08 permit removal carries no operator reason |
| 04 | Consultant / development | A, R | FOLLOW-UP | S-01 phase-scoped users; B-03 |
| 05 | Project Team create → edit → remove | B (1440, 390) | FIXED | F-03 NUL 500, F-24 unstyled controls |
| 06 | Building → floor → unit | A, R | FIXED | F-21 wrong delete-dialog dependency text |
| 07 | Unit price → release | A, R | FOLLOW-UP | S-03 rules/benchmarks/draft configuration not editable in UI |
| 08 | Buyer/client → agent attribution | A, R | FIXED | F-21 buyer/Agent delete dialogs; S-10 picker context |
| 09 | Available unit → reservation | A | FOLLOW-UP | S-04 reservation preparation fields/adjustments not editable |
| 10 | Reservation → contract | A, R | FIXED | F-07 Sales gates could never be saved |
| 11 | Contract → payment plan | A, R | FOLLOW-UP | S-10 contract picker lacks unit/buyer |
| 12 | Receipt → confirmation → allocation | A, S | FIXED | F-12, F-13 |
| 13 | Collections → ageing/reconciliation | B, A | FIXED | F-09, F-10, F-11, F-14, F-26 |
| 14 | Sale cancellation → financial approval → refund | A, B (1440, 390) | FIXED | F-08 refunds could not be recorded; B-01 |
| 15 | Cancellation → unit return → repricing → resale | A | PASS | Existing return-to-market tests in the Full run; not browser-driven |
| 16 | Commission beneficiary lifecycle | S, R | FIXED | F-19 one-click removal |
| 17 | Construction budget/cost/progress | A, R, S | BLOCKED — BUSINESS DECISION REQUIRED | F-15, F-17 fixed; B-04 |
| 18 | Unit economics reconciliation | A, R | FIXED | F-18 uncompletable custom-driver pools, F-20, F-23; S-02 |
| 19 | Project cashflow / reporting | A, R | FOLLOW-UP | S-07 version UUIDs in Portfolio/Board Pack |
| 20 | Project Images upload / view / remove | B | FIXED | F-02, F-22 |
| 21 | Agreement upload / download / edit / delete | B (1440, 390) | FIXED | F-01 lock held while streaming, F-25 |
| 22 | Commercial FAQ create / search / copy / edit / delete | B (1440, 390) | FIXED | Arabic + multiline copied byte-exact; F-24 |
| 23 | Marketing Project Bio | B (editor open 1440/390), A | FIXED | F-24 |
| 24 | Marketing rental Economics | R, A | FOLLOW-UP | S-14 |
| 25 | Marketing Branding | B (editor open 1440/390), A | FIXED | F-24 |
| 26 | Governance / access behaviour | B (11 roles + selected-phase PM), A | FOLLOW-UP | S-01, B-02, B-03 |
| 27 | Project Overview decision-making | B (1440/1280/1024/390) | FIXED | F-17, F-26 |
| 28 | Project Analysis | R, A | PASS | Fundamental section read at 1440/390 without errors |
| 29 | Record deletion / reversal / correction coverage | S, A | FIXED | F-27; S-03…S-06, S-08, S-09, S-11, S-12 |
| 30 | Mobile completion of critical workflows | B (390) | PASS | 32 destinations, no horizontal overflow; flows above completed at 390 |

## Role and permission matrix (browser, 1440px, every project section)

Sections that rendered "Not available to your role" when opened by URL. Every one
of them is also absent from that role's navigation (`visible` mirrors the server
reader sets), and no role produced a console error, a failed API call, a raw UUID
or horizontal overflow — except the selected-phase Project Manager (S-01).

| Role | Not available (by design) |
| --- | --- |
| system_admin | Consultant Engineer, Commissions (B-03) |
| project_manager | Access |
| finance, approver_cfo, executive_viewer, auditor | Access |
| sales_operations | Company, Pre-Launch, Consultant, Unit Economics, Cashflow, Access |
| sales_advisor | Company, Pre-Launch, Consultant, Commissions, Unit Economics, Cashflow, Access |
| legal, collections | Company, Pre-Launch, Consultant, Marketing ×3, Commissions, Construction, Unit Economics, Cashflow, Access |
| design_engineering | Company, Pre-Launch, Marketing ×3, every Commercial section, Unit Economics, Cashflow, Access |
| project_manager (selected phase) | see S-01: 12 whole-project sections fire 403/404 and render "Project not found" |

Server enforcement was verified independently of the UI by the authorization and
isolation review (every POST/PUT/PATCH/DELETE route has a role gate; child records
load by owner) and by the regression tests added here.

## Findings

Format per finding: area · user job · finding · severity · fix · regression
evidence · status. Reproduction detail is in each commit message.

### Fixed in this PR

**F-01 · Agreements · upload a final draft · P1 · FIXED.** The upload route took
the project row lock (`SELECT … FOR UPDATE`) and then read the request body at the
client's pace, so any agreement writer uploading slowly stalled every write to that
project (inventory, sales, team, FAQs, images, currency correction) and held a pool
connection. Authority is now checked without the lock, the read transaction ends,
the body streams, then the lock is taken and authority re-checked. Regression:
`test_upload_does_not_hold_the_project_lock_while_the_body_arrives` (fails on the
parent: another transaction's `FOR UPDATE NOWAIT` is refused mid-upload).

**F-02 · Project Images · manage the gallery · P2 · FIXED.** A Project Manager
limited to selected phases could add and remove whole-project gallery images; Team,
Agreements, Marketing and FAQs already refuse whole-project writes to that scope.
Regression: `test_selected_phase_project_manager_cannot_change_the_whole_project_gallery`.

**F-03 · Platform · enter any text · P2 · FIXED.** A NUL character in any JSON
string or query parameter (team name, FAQ question, project name, image filename…)
returned 500 from PostgreSQL. It now answers 422 "Text cannot contain the NUL
(0x00) character." from one handler in `app/main.py`; other data errors remain 500.
Regressions: `test_nul_character_is_a_validation_error_and_writes_nothing`,
`test_nul_character_in_a_filename_is_refused_not_a_server_fault`; confirmed live.

**F-04 · Inventory configuration · edit a configurable field · P2 · FIXED.**
`PATCH /projects/A/field-definitions/{id}` loaded the definition by id alone and
answered 403 for project B's definition but 404 for a random id, confirming the
identifier (Engineering Rules §4, §9). Now loaded by owner; both answer 404.
Regression: `test_another_projects_definition_answers_as_missing_not_forbidden`.

**F-05 · Pricing · custom-field premium · P2 · FIXED.** The premium validation
said "does not exist" for an unknown id and "does not apply to units of this
project" for another project's field. One message now covers every foreign or
unknown identifier; this project's own non-unit field keeps its specific message.
Regression: `test_an_unknown_definition_reads_the_same_as_one_that_does_not_apply`.

**F-06 · Settings · currency registry · P2 · FIXED.** Deactivating a currency and
creating a country pack on it were both read-then-write without the row lock, so
concurrent requests could leave an active pack on an inactive currency; a concurrent
duplicate code returned 500. The currency row is now locked in both paths and the
duplicate answers 409. Regressions: two real two-transaction tests in
`test_settings.py` (both fail on the parent: the second writer never blocks).

**F-07 · Sales · change handover/title gates · P1 · FIXED.** "Save gates" sent the
whole read model, including `project_id`, to a strict write contract: every save
was refused 422, so a project could never change its gates. Regression:
`operationalAudit.test.mjs` "Sales gates are saved with the six gates only"; browser:
PUT 200 as System Administrator.

**F-08 · Collections · pay back a cancelled buyer · P1 · FIXED.** The deal file
said "Actual repayment is recorded in Collections"; Collections said "Record a
repayment from the cancellation on the deal file". Neither offered it, and the
only creation route had no UI caller, so an approved refund could never be entered.
Collections now records a repayment against the approved, live cancellation (form
offered only when approved, not withdrawn and money is still owed; the server rule
is unchanged). A failed deal-file read hides only the form, never the register.
Regressions: three tests in `operationalAudit.test.mjs`; the existing
`collectionRemoval.test.mjs` refund tests still pass; browser: POST 201 at 1440/390.

**F-09 · Collections · review follow-up · P2 · FIXED.** A failed follow-up history
read rendered "No follow-up recorded". Now an error with Retry.

**F-10 · Collections · review disputes and waivers · P2 · FIXED.** Failed reads
rendered "No disputes" / "No waivers". Now unknown, with an error and Retry.

**F-11 · Collections · restructure a schedule · P2 · FIXED.** A failed history read
rendered "This schedule has never been restructured" and offered to raise a new
restructure beside one that might already be open. Now an error with Retry and no
raise action until history is known. Regression for F-09…F-11:
"never turn a failed read into an empty record".

**F-12 · Collections · apply cash · P2 · FIXED.** A failed suggestion read
rendered "All of this receipt is applied, or nothing is outstanding" — a false
statement about money. Now "Suggestions could not be loaded" with Retry; manual
allocation stays available.

**F-13 · Collections · apply cash · P2 · FIXED.** A refused allocation cleared the
instalment and amount the operator entered. Regression for F-12/F-13 mounts
`ReceiptPanel` and fails on the parent.

**F-14 · Collections · apply a restructure · P2 · FIXED.** The carry-forward table
printed `receipt_id.slice(0, 8)` and `installment_id.slice(0, 8)`. The preview read
now returns receipt number and instalment sequence/label (project-scoped queries)
and the table prints them. Regressions: backend assertions in
`test_collection_restructures.py`; frontend test asserts no UUID fragment renders.

**F-15 · Construction · unit stage progress · P2 · FIXED.** Completion history
printed "User <uuid>" and a raw ISO timestamp. The read now includes the recorder's
display name; the time is formatted as UTC. Regression:
`test_edit_move_clear_and_preserve_history` asserts the name.

**F-16 · Navigation · old links · P2 · FIXED.** `section=agent-buyer` links opened
the Overview although the code comments promised Buyers. Resolution now lives in
`resolveProjectSection` beside the `pricing` remap. Regression in
`operationalAudit.test.mjs`.

**F-17 · Overview · construction position · P2 · FIXED.** With no budget the
Overview said "Until a construction budget is approved and made current…", pointing
at a budget workflow the owner removed from Construction in #355
(`docs/CONSTRUCTION_CONTRACT_FIRST.md`). It now points to contracts and payments;
Management Reports no longer says "Inspect budget".

**F-18 · Unit Economics · allocate a shared cost · P1 · FIXED (trap removed).**
"Custom driver" was offered when adding a pool, but no screen can enter driver
values and calculation refuses a pool without them: the pool could be created and
never finished. The method is no longer offered for new pools; existing
custom-driver pools stay readable and removable. The driver editor is S-02.

**F-19 · Commissions · correct a draft distribution · P2 · FIXED.** "Remove
Beneficiary" deleted in one click. It now confirms, naming the beneficiary and rate.

**F-20 · Unit Economics · correct a draft cost basis · P2 · FIXED.** "Remove" on a
draft pool deleted in one click. It now confirms, naming the pool and amount.

**F-21 · Inventory / Buyers / Agents · delete unused records · P2 · FIXED.** Buyer
and Agent delete dialogs used the default text "A building or floor must be empty
first"; phase/building/floor dialogs did not name the record. Each now names the
record and states its real server dependency rule.

**F-22 · Project Images · upload several images · P2 · FIXED.** After a partial
failure every selected file stayed selected, so "Add N images" re-uploaded images
already stored (duplicates); category and file controls stayed enabled while busy.
Only refused files remain selected ("Retry 1 image"); controls lock while busy.
Regression: `projectImages.test.mjs` (fails on the parent); browser verified.

**F-23 · Unit Economics · read pool provenance · P3 · FIXED.** Construction-forecast
and manual pools were both labelled "Forecast input"; the frontend type lacked
`construction_forecast`.

**F-24 · Team, Marketing, Company, FAQs, Operations · fill a form · P2 · FIXED.**
48 inputs/selects/textareas rendered browser-default (no `.input`), unlike every
other form — visible in the 1440px Team screenshot. Now canonical.

**F-25 · Agreements · read the register · P3 · FIXED.** Draft dates printed as raw
ISO; now `businessDate`.

**F-26 · Overview · read collections position · P2 · FIXED.** At 1440px the lead
amount broke inside its digits ("JOD 325,000.0" / "0", `overflow-wrap: anywhere`);
at 1024px "Confirmed receipts, lifetime" ran under its amount. The stage figure now
scales with its own width and wraps only between code and amount; the ledger stacks
when its card is narrower than 34rem. Verified by screenshots at 1440/1280/1024/390.

**F-27 · Deletion governance · P3 · FIXED.** The creator guard named five `*_api.py`
files by hand and never scanned Management Actions' create route; six baseline gap
entries were already implemented, so those handlers could have regressed to
"missing" silently. The guard now scans every router; the newly visible handler is
recorded as the existing gap it is; the stale entries are removed.

**F-28 · Test harness · concurrency regression · P3 · FIXED.** The complete suite
on the final code failed once in
`test_two_correction_attempts_serialize_and_only_one_commits` (3,808 passed, 1
failed) and passed in isolation. Root cause: each thread built a fresh application,
and FastAPI's lazy route build silences a pydantic warning with
`warnings.catch_warnings`, which swaps process-global filters and is not
thread-safe; two first requests racing could restore each other's filters and turn
the silenced warning into a warnings-as-errors 500. Pre-existing and independent of
this PR's code. The test now walks every route once per client in the main thread
before the race, leaving only the two corrections concurrent; 5/5 local passes.

### BLOCKED — BUSINESS DECISION REQUIRED

**B-01 · Refund before termination · P2.** During the notice stage of a cancellation
(`termination_pending`, no unit return) the contract's receivable is still live and
overdue by the documented rule, while the approved refund is already due and can be
recorded. The seeded account shows JOD 99,000 overdue and JOD 18,000 owed back at the
same time. Decide whether a refund may be recorded/paid before the unit return takes
effect, or only after. Affected: collections `require_refund_authority`, deal file,
Collections account, Portfolio refund facts.

**B-02 · Global audit reads · P2.** System Administrator and Auditor read every audit
event across projects, including company bank-account snapshots (account number,
IBAN, SWIFT, tax number) and team contact emails, although the project API answers
404 outside membership. Decide whether audit reads narrow to member projects for
auditors and/or whether bank identifiers are redacted from snapshots.

**B-03 · System Administrator and two modules · P3.** System Administrator is in every
module's reader set except Consultant Engineer and Commissions (server and
navigation agree). Confirm this separation is intended.

**B-04 · Construction workflows removed from the UI · P2.** #355 made Construction
contract-first at the owner's request. Budgets, cost codes (create/edit/retire),
certificates, invoices, milestones, cost forecasts and delivery start/ready remain
full API workflows with no screen (`BudgetWorkspace.tsx` is orphaned but still
mounted by `readRecovery.test.mjs`); Overview still shows budget variance when a
legacy budget exists. Decide: retire these APIs/components, or restore screens.

### FOLLOW-UP — STRUCTURAL CHANGE REQUIRED

| ID | Sev | Problem and business impact | Recommended solution | Suggested PR title | Acceptance |
| --- | --- | --- | --- | --- | --- |
| S-01 | P2 | A selected-phase user sees 12 whole-project sections in navigation; opening them fires 403/404 and renders "Project not found" with Retry and Add buttons that cannot work (Company, Marketing ×3, Agreements, Operations, Consultant, Pre-Launch, Commissions, Construction contracts, Economics, Cashflow). | Return the caller's `phase_scope` on the project read; filter whole-project-only destinations in `visibleNavigation`; say "Needs whole-project access" instead of "Project not found". | `fix(access): show selected-phase members only what their scope can open` | Browser crawl as a selected-phase PM shows no 403/404 and no dead Add/Retry. |
| S-02 | P2 | Custom-driver pools cannot be completed from the UI (trap removed by F-18). | Server read of eligible units per pool; per-unit driver editor calling `PUT …/drivers`. | `feat(economics): enter custom driver values` | Create → enter drivers → calculate → reconcile in browser. |
| S-03 | P2 | Pricing rules, benchmarks and draft configurations cannot be corrected in UI (PATCH exists, no client); escalation activation reversal has no UI; draft configuration delete is a baseline gap. | Edit forms over the existing PATCH routes; reversal with reason. | `feat(pricing): correct draft rules and reverse an escalation` | Edit and reversal round-trip with audit. |
| S-04 | P2 | Reservation preparation fields, adjustment amounts, expiry extension, recalculation and handover scheduling have APIs but no UI. | Edit forms on the deal file. | `feat(sales): correct a reservation and schedule handover` | Each field correctable from the deal file with audit. |
| S-05 | P2 | Currency registry edits only the symbol; name and active status cannot be changed although the delete dialog advises "Use inactive status". | Rename + Deactivate/Reactivate. | `feat(settings): rename and retire a currency` | Deactivation refused while an active pack uses it (F-06 lock). |
| S-06 | P2 | Country packs, tax rules, reference values and approval thresholds are API-only. | Settings sections for each. | `feat(settings): maintain country configuration` | CRUD with audit and deletion contracts. |
| S-07 | P2 | Portfolio, Outlook and the printed Board Pack print "Version <uuid>"; the comparison can print two UUIDs. Frozen snapshots are immutable. | Server-supplied version labels on live reads; comparison renders "Version changed". | `fix(portfolio): name governing versions` | No UUID in rendered live pages; frozen packs unchanged. |
| S-08 | P2 | Permit removal records a hard-coded reason, not the operator's, although the deletion contract claims a reason. | Reason query parameter + `DeleteRecordButton`. | `fix(permits): record the operator's removal reason` | Audit event carries the entered reason. |
| S-09 | P2 | Project image removal takes no reason (Deletion Policy §2 asks one for audited records). | Reason parameter + dialog. | `fix(projects): reasoned image removal` | Audit carries reason. |
| S-10 | P2 | Pickers lack distinguishing context: payment-plan contract picker has no unit/buyer; buyer pickers show no contact and use two orders; Marketing and unit-cost unit pickers show no building/floor. | Add the fields the API already returns. | `fix(ux): contextual record pickers` | Two similar records distinguishable in each picker. |
| S-11 | P2 | Management action create has no Delete for an unused open action (cancel retains). | Draft delete or explicit retained contract. | `feat(actions): delete an unused action` | Contract row moves off `missing`. |
| S-12 | P2 | Sales client parties, parcels, project documents, construction stages, consultant disciplines/stages/deliverables and other baseline gaps (`tests/deletion_baseline_gaps.json`, 50 entries). | Per-record removal flows. | per module | Gap list shrinks. |
| S-13 | P3 | Five places slice UTC timestamps to a calendar date without saying UTC. | `eventTime()`. | `fix(format): timestamps as timestamps` | — |
| S-14 | P3 | Marketing Economics unit search refetches per keystroke; three `TableScroll`s nest a second `<table>` with duplicate captions. | Debounce; pass rows directly. | `fix(marketing): economics tables` | Valid HTML; one request per settled search. |
| S-15 | P3 | Orphan components with no importer: `SalesHistory`, `BuyerContact`, `UnitCollections`, `UnitEconomicsSection`, `QuotePreviewPanel`, `PricingTab`, `BudgetWorkspace` (B-04). Some are still mounted by tests. | Remove after B-04. | `chore(frontend): remove orphan screens` | — |
| S-16 | P3 | `approveBudget`/`approveForecast` send a reason the routes ignore. | Drop the body or accept it. | — | — |
| S-17 | P3 | Currency registry has no `denied` rendering (admin-only). | Add branch. | — | — |
| S-18 | P3 | Unauthenticated pages log a 401 for the session probe in the console. | Treat 401 on `/auth/me` as the anonymous answer silently. | — | — |
| S-19 | P3 | The Overview "Pricing" button and "Open units" both open Inventory. | Keep one. | — | — |

## Browser console and network

Across the role crawl (12 users × 32 destinations) and every flow above, the only
console errors were: expected 422 responses from deliberately invalid uploads, the
pre-login 401 session probe (S-18), and the selected-phase 403/404s (S-01). No
page error, React warning, duplicate POST or 5xx was observed.

## Validation run for this PR

- Backend baseline on `1496be3`: 3,801 passed, 0 failed (four local shards).
- Every new backend regression shown failing on the parent, then passing.
- Frontend: `node --test tests/*.test.mjs` 217 passed; `tsc --noEmit` clean;
  ESLint 0 errors; production build succeeded.
- `ruff check .`, `ruff format --check .`, `python -m compileall app scripts`,
  `git diff --check`, `python scripts/agent_preflight.py`: clean.
- Migrations: `alembic heads` single head; `alembic upgrade head` from empty and
  `alembic check`: clean. No migration added.
- The complete backend suite on the final code head, and CI results, are reported in
  the pull request, not claimed here.
