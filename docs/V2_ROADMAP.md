# MVP 2 Roadmap — Reach Developments Station

Canonical delivery sequence for MVP 2 (V2). Twelve pull requests, `PR-V2-00`
through `PR-V2-11`, each merged into `main` on its own short-lived branch.

| Scope                       | Count |
| --------------------------- | ----: |
| Total planned MVP 2 PRs     |    12 |
| Complete                    |     1 |
| Current                     | PR-V2-01 |
| Remaining after the current |    10 |

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

## PR-V2-01 — Land & Permit Workspace 🚧

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
  when a description cannot be a 64-character code — truncating, nulling or
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

## PR-V2-02 — Project Structure & Inventory

- real Phase → Building → Floor → Unit navigation
- cleaner hierarchy management
- improved exact-template import workflow

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
- collected total, and collected as a percentage of selling price — both the
  server's figures
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
| Complete               | 1 / 12                                        |
| Current                | PR-V2-01 — Land & Permit Workspace            |
| After PR-V2-01 merges  | 2 / 12 complete, 10 remaining                 |
| Next                   | PR-V2-02 — Project Structure & Inventory      |
