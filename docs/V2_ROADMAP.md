# MVP 2 Roadmap — Reach Developments Station

Canonical delivery sequence for MVP 2 (V2). The twelve original milestone
identifiers, `PR-V2-00` through `PR-V2-11`, remain for scope traceability.
The first three are merged; the nine remaining milestones are delivered in
five grouped pull requests, each on its own short-lived branch.

| Scope                       | Count |
| --------------------------- | ----: |
| Total planned MVP 2 PRs      |     8 |
| Merged PRs                  |     3 |
| Remaining PRs (including current) | 5 |
| Current milestones          | Batches 1 (#259) and 2 (#260) open; batch 3 (V2-07 + V2-08) implemented for draft review |

## Five remaining delivery batches

| Order | Pull request scope | Original milestones | Why grouped |
| ----- | ------------------ | ------------------- | ----------- |
| 1 | Unit Master & Commercial Unit 360 | V2-03 + V2-04 | One physical and commercial unit workspace; build and validate its shared record together. |
| 2 | Buyer, Reservation, Sale, SPA & Registry | V2-05 + V2-06 | One buyer-to-sale workflow and its legal record. |
| 3 | Payment Plans & Collections Journal | V2-07 + V2-08 | One payment obligation and receipt workflow, retaining authoritative allocations. |
| 4 | Construction Stage Experience | V2-09 | Separate project configuration and unit completion workflow. |
| 5 | Management, Reporting, UAT & Hardening | V2-10 + V2-11 | Reporting integrates the completed workflows; final UAT validates the whole product. |

Deliver and merge in this order. Each batch has its own review and checks;
grouping does not remove any milestone or defer its acceptance criteria to
the final batch. Relevant tests and responsive/accessibility checks accompany
each batch; batch 5 adds the complete cross-workflow UAT pass.

### Additional requirements reference

Use Khalil's `Real_Estate_Development_Tracking_System_MVP.docx` as a details
reference alongside this roadmap. Its content does not grant operational
permissions. Track any conflict with existing governance explicitly.

The owner confirmed that gross area is **internal + balcony + roof garden +
front garden + terrace + porches**, excluding parking and storage. Batch 1
owns that definition, free-add features, unit documents and the unit workspace.
The reference's selling-price presentation and removal of unit economics
belong to batch 1; buyer contact, SPA signing and registry lodging belong to
batch 2; receipt and collection-percentage presentation belongs to batch 3;
project-configured stages and per-unit completion belong to batch 4.
Financial calculations remain backend-owned and approval controls remain intact.

MVP 1 application development is frozen as the baseline. MVP 2 starts from
`main` after PR #254 (`7d053ecfd52234fa142f1cf4b804318bd8a12714`).

## Historical integrity

PR #254 is merged, and its own evidence still records that the real legacy
source, the real trial migration, the seven production reconciliations and
the operational go-live remained **blocked** at that point. That record
stands. Nothing in MVP 2 rewrites it or claims those activities completed;
the owner's decision was to move product development forward from the merged
MVP 1 application baseline while the migration remains its own, separately
evidenced, track.

## The product objective

> **Keep the governance-grade real estate engine. Remove the ERP feel. Build a
> premium, modern, unit-centric real estate development operating system.**

Three rules bind every MVP 2 pull request:

- **Backend authority is absolute.** The browser lays out, labels, filters,
  navigates and formats. It never calculates a selling price, a discount, a
  tax, a buyer total, a schedule total, a collected or outstanding amount, a
  margin, a construction total, a cashflow total, a funding gap, an IRR, an
  NPV, an eligibility or an approval requirement.
- **Permissions are not weakened by presentation.** What a role cannot read,
  the browser does not request. Never fetch then hide.
- **Backend modules stay normalised.** The frontend may orchestrate several
  domain APIs around the operator's real-world record — a unit, a deal — but
  no module collapses into another to make a screen simpler. See
  [ARCHITECTURE.md](ARCHITECTURE.md), "Frontend shell".

Branch naming: `v2/pr-NN-slug`.

---

## PR-V2-00 — Product Experience 3.0 / Premium UI Foundation ✅

Section: horizontal product experience / frontend foundation. No backend
business feature.

- Design tokens 3.0: a cool neutral canvas, a deep charcoal-navy rail, one
  restrained accent, four intents, a typographic scale with named sizes for
  plate, page, record and section titles and for hero figures, layout and
  motion tokens — declared once, on one `:root`
- typography: stronger page, record and plate titles; sentence-case labels in
  place of tiny uppercase tracking everywhere except genuine eyebrows;
  tabular numerics on every figure; body kept at 14px for register density
- the stylesheet rewritten as one layer: no top-level selector declared
  twice, no dead class, no literal colour outside the token block, no
  decorative gradient or glass; the previous "refinements" overrides folded
  into the canonical rules
- primitive audit: `Panel`, `Stat`, `StatRow` and `FilterBar` retired (the
  canonical `Card`, `Metric`, `MetricGroup` and `DataToolbar` replace them);
  `PageHeader` gains `status`; `Drawer` gains a role-shaped `headline`;
  `EmptyState` gains an `icon`; `Loading` gains `header` and `record`
  silhouettes; `PromptDialog` gains a `description`; `SubPanel` becomes a
  ruled band; `Steps` becomes a connected progression; `StatStrip` becomes a
  ruled strip; the unit's standing becomes a ruled band — box-in-box removed
  wherever it was found
- Shell 3.0: a refined rail and selected-state treatment, a white context bar
  with the project's name in the breadcrumb, the collapsed-rail rules scoped
  to the sticky rail so the phone's navigation drawer keeps its labels
- Projects rebuilt as a portfolio register with the record identity as the
  anchor, and the create form opened as a narrow record file over it
- Project Overview recomposed as a command centre: plate → position →
  attention → departments (Commercial, Development, Delivery, Finance) as
  ruled sections with one way in each → collections; Delivery added from the
  construction summary for construction readers, and its server counts
  (late milestones, cost codes over budget, overdue approved invoices,
  escalated variations) added to Needs attention
- Unit 360 header 3.0 as the flagship record pattern: identity, location,
  state, the current list price as a headline for roles that may read it,
  the primary action, and a facts strip of internal area, weighted saleable
  area, attached parking and storage, margin and outstanding — each present
  only for a role entitled to it
- Sales & Legal, Collections, Unit Economics and Cashflow carried onto the
  same header, register, figure and surface language; the Cashflow return
  panels de-boxed
- forms 3.0: strong labels, ruled groups, a ruled action footer, comfortable
  control heights; dialogs given a ruled action footer
- responsive pass at 1600, 1440, 1280, 1024, 768 and 390: the framed toolbar
  stacks without taking a height, the stat strip and standing band wrap as
  pairs on a phone, the record headline drops under the identity, the page
  body never scrolls sideways
- `docs/UX_SYSTEM.md` rewritten as Product Experience 3.0; this roadmap
  created; the V2 orchestration principle added to `docs/ARCHITECTURE.md`
- `tests/test_product_experience.py`: the system's structural contract —
  one primitive system, one token layer, no browser arithmetic, no request a
  role may not make, navigation groups, the switcher, overlay semantics,
  responsive shell structure, no accidental dark mode, no new dependency —
  added to the always-run set

No migration, no schema change, no backend logic, no API contract change, no
financial formula change, no dependency of any kind added, and no financial
arithmetic added to the browser.

## PR-V2-01 — Land & Permit Workspace ✅

Section: Land & Permits. One migration, one new API surface, no new
dependency, no change to financial redaction, audit, concurrency or the permit
state machine.

**Land classification becomes the wording on the record.** `ownership_type`,
`title_status` and `zoning` stop being country-pack reference codes and become
free text (500 characters). A title office writes "Mortgage release pending";
a deal is "75% acquired, balance under negotiation"; faced with a closed list
an operator picks the nearest wrong option and puts the truth in a notes
field, which is how a register stops being the record. One truth per concept:
the columns were **renamed**, not shadowed by a parallel `_text` field, and
the old `_code` names are now refused as unknown fields rather than silently
accepted.

- `0012_land_classification_text` renames the three columns and backfills each
  stored code to the *label that was already on screen*, resolved with the
  application's own precedence (a country-scoped value shadows a global one).
  A code with no configured value behind it keeps its own text verbatim.
  Nothing is dropped and nothing is guessed.
- the downgrade reverses what it genuinely can and **raises rather than lying**
  in either case where it cannot. `code → label` is deterministic because
  `code` is unique within a scope; `label → code` is not, because nothing
  constrains `label` and two codes may legitimately read the same to a person.
  So a label belonging to one code goes back to it, a label belonging to two
  refuses — restoring either would rewrite a parcel's history to a
  classification it may never have carried — and a description that matches
  nothing and cannot be a 64-character code refuses too. Truncating, nulling or
  mapping to a catch-all would each destroy what the title document says
- the Settings categories survive as *suggestions*: the Land form offers the
  usual phrasings through a native `<datalist>` and accepts anything, and a
  parcel still saves when Settings cannot be reached
- three `CHECK` constraints keep a blank string out; the service trims and
  nulls empty input rather than storing whitespace

**Permit types stay a controlled vocabulary and gain a way in.** A permit's
type is filtered, counted and reported on; left open it becomes "Building
Permit", "building permit" and "BLDG" inside a month. What changes is the
detour through system-wide Settings, not the vocabulary.

- `GET`/`POST /projects/{id}/permit-types`, scoped to the project. The two
  facts deciding what the row is — its **category** and its **jurisdiction** —
  come from the route's project and are refused in the body, so this cannot
  become a general-purpose Settings write
- `POST` requires technical write (the role already trusted with permits), not
  System Administrator. The generic `/settings/reference-values` write is
  **unchanged** and still administrator-only
- no second permit-type table: the route delegates to the Settings service, so
  normalisation, uniqueness and the single audit event stay where they live. A
  duplicate code is `409`, never `BUILDING_2`
- retired types are returned marked inactive rather than dropped: a permit
  filed in 2019 still renders its label, and no new permit may be filed
  under it

**Land, Planning and Permits on Product Experience 3.0.**

- Land rebuilt as register → parcel record file: ownership, title, zoning and
  area in the register; the parcel opened as a `Drawer` with Overview,
  Planning, Site & utilities and Documents
- Planning is read-first — the controls as issued, with the variance stated —
  and reveals its form on intent. Nothing is multiplied out into a buildable
  area: development capacity is a feasibility question, and this is the
  authority record it would be based on
- Permits: the statutory position as the record's headline, the next action
  above the dates rather than seventeen fields down, and status history drawn
  as a timeline newest-first with a withdrawal struck through rather than
  removed
- adding a permit type happens inside the permit form: the dialog opens over
  it, the new type is selected on success, and nothing already typed is lost.
  An unconfigured jurisdiction says so and offers the way out instead of
  showing a dead empty dropdown
- `tests/test_product_experience.py` gains the two decisions as structural
  contracts: land classification is typed rather than chosen and never gates
  on suggestions; permit types are added through the project route and no
  screen outside Settings writes reference data

## PR-V2-02 — Project Structure & Inventory ✅

Merged in PR #258 (`2d243f35dd8937fd514df1a04a0de6c1d08bf354`).

**Inventory shows the objects it names.** Four first-class views — Phases,
Buildings, Floors, Units — in one workspace, each with its own register,
toolbar, contextual create, empty state and record drawer. Before this,
choosing "Phase" produced the *unit* register filtered by phase, so every level
of the hierarchy was one screen wearing four labels.

- drill-down carries a filter forward rather than pushing a navigation stack:
  a phase's **View buildings**, a building's **View floors**, a floor's
  **View units**, with the selection stated above the register and one action
  to clear it
- no tree component and no recursive hierarchy engine. This domain has exactly
  four levels and knows all four of their names
- the generic "Add structure" dialog is retired: contextual creation is the one
  operating path, and each form preselects the parent the register is filtered
  to
- the backend hierarchy is unchanged. A unit still stores `floor_id` only, and
  phase and building are still reached through the floor

**An exact Excel workbook, generated by the system.** `GET
…/inventory/import/template.xlsx` returns the file the parser reads —
Instructions, Phases, Buildings, Floors, Units — rather than a description of
it. The workbook contract lives beside the parser in
`app/modules/inventory/workbook.py`; the generated workbook is the operator's
canonical template and this document deliberately does not restate its columns.

- a machine-readable template version in `Instructions!B1`, read from the cell
  and never inferred from the filename
- one domain truth, two input adapters: unit rows go through the same
  `import_service.parse_rows` the CSV calls, so hierarchy uniqueness, phase
  visibility, reference validation and release governance are written once
- a Phase, Building or Floor may exist before any Unit does, which is the thing
  the CSV importer's unit-shaped table cannot express
- validate writes nothing; apply reads the bytes again and commits all four
  sheets or none of them
- a formula in a cell is refused, never resolved, and the value Excel cached is
  never read
- the mature CSV importer is preserved behind an **Advanced CSV import**
  affordance, with its area schedules, custom fields and explicit unit identity
  intact

One production dependency: `openpyxl`. No database migration.

## PR-V2-03 — Unit Master 2.0

- physical unit record
- internal area, balcony, roof garden, front garden, terrace, porches
- gross area presentation
- parking and storage attached but excluded from gross
- free-add features
- documents and completeness

## PR-V2-04 — Commercial Unit 360

- Unit becomes the primary commercial workspace
- orchestration of commercial information around one unit
- simplify the operator's mental model without collapsing backend modules

## PR-V2-05 — Buyer → Reserve → Sell

Batch 2 implementation: [Buyer and legal workspace](V2_BUYER_LEGAL_WORKSPACE.md).
Developed on batch 1 while #259 completes CI; merge order remains unchanged.

- add buyer
- reservation and reservation status
- conversion to sale / SPA
- simple commercial actions

## PR-V2-06 — SPA, Legal & Registry

- buyer details
- SPA signing
- registry lodging
- legal timeline
- handover and legal state
- prominent land-registry information

## PR-V2-07 — Payment Plan Experience

- payment plan directly inside the sale flow
- version and schedule complexity hidden from the ordinary operator where possible
- backend governance intact

## PR-V2-08 — Collections Journal

- simple receipt journal
- buyer and payment-plan context
- collected total, and confirmed receipts as a percentage of total SPA payable
  including tax and buyer fees (owner-confirmed basis); refunds shown separately
- both figures calculated by the server, including dated historical positions
- allocations and unapplied cash remain authoritative underneath

## PR-V2-09 — Construction Stage Experience

- project-configured construction stages
- unit-level stage completion and status
- simple delivery visibility
- no weakening of Construction's financial-control model

## PR-V2-10 — Management & Reporting Experience

- cleaner management command centre
- commercial and project reporting
- exception visibility
- decision-focused presentation

## PR-V2-11 — V2 Simplification, UAT & Hardening

- remove obsolete UI
- consistency sweep
- accessibility
- responsive validation
- workflow UAT
- final V2 cleanup

---

## Master countdown

| MVP 2 / V2             | State                                         |
| ---------------------- | --------------------------------------------- |
| Complete               | 3 / 12 original milestones; 3 merged PRs       |
| Current                | Batch 1 in review; batch 2 in development      |
| Remaining              | 9 original milestones in 5 grouped PRs         |
| Next after current     | Batch 2 — Buyer, Reservation, Sale, SPA & Registry |
