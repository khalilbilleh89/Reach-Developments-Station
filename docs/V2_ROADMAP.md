# MVP 2 Roadmap — Reach Developments Station

Canonical delivery sequence for MVP 2 (V2). Twelve pull requests, `PR-V2-00`
through `PR-V2-11`, each merged into `main` on its own short-lived branch.

| Scope                       | Count |
| --------------------------- | ----: |
| Total planned MVP 2 PRs     |    12 |
| Complete                    |     0 |
| Current                     | PR-V2-00 |
| Remaining after the current |    11 |

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

## PR-V2-00 — Product Experience 3.0 / Premium UI Foundation 🚧

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

## PR-V2-01 — Land & Permit Workspace

- flexible ownership / title / zoning presentation
- configurable permit types
- simplified land and regulatory workflow

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
| Complete               | 0 / 12                                        |
| Current                | PR-V2-00 — Product Experience 3.0 / Premium UI Foundation |
| After PR-V2-00 merges  | 1 / 12 complete, 11 remaining                 |
| Next                   | PR-V2-01 — Land & Permit Workspace            |
