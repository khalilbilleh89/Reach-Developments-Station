# MVP 1.0 Roadmap — Reach Developments Station

Canonical delivery sequence. Twelve pull requests, `PR-MVP-00` through
`PR-MVP-11`, each merged into `main` on its own short-lived branch.

| Scope                                 | Count |
| ------------------------------------- | ----: |
| Total planned MVP PRs                 |    12 |
| Complete (PR-MVP-00 through PR-MVP-08) |     9 |
| Remaining                             |     3 |

Engineering PRs are counted separately and never renumber the functional
sequence:

| Engineering                | State |
| -------------------------- | ----- |
| PR-ENG-01 — Two-Speed CI   | ✅    |

Branch naming follows the roadmap:

```text
mvp/pr-00-foundation
mvp/pr-01-governance
mvp/pr-02-project-land-permits
mvp/pr-03-inventory
...
```

MVP completion requires the entire core workflow to operate **without
spreadsheet-side calculations**.

Work that hardens the product across every module at once — the design system,
accessibility, responsive behaviour — is recorded under
[Horizontal checkpoints](#horizontal-checkpoints) at the end of this document.
Those do not carry an MVP number and do not change the count of twelve.

---

## PR-MVP-00 — Repository Foundation & Engineering Constitution

Foundation only. No business domain.

Clean repository structure, anti-overengineering constitution, dependency
policy, module boundaries, FastAPI application, canonical PostgreSQL/SQLAlchemy
configuration, fresh Alembic history rooted at an empty `0000_mvp_baseline`,
liveness and readiness probes, static Next.js export served by FastAPI, design
tokens, CI, PR template, and Render build/start separation.

---

## PR-MVP-01 — Governance, Country Packs & Access

- user/account foundation
- roles
- country packs
- currencies
- tax configuration
- lookups/status dictionaries
- approval thresholds
- audit actor context

> **Sequencing correction.** This entry originally read "roles and project
> access". Project-scoped access cannot be built here: the `Project` entity does
> not exist until PR-MVP-02, so persisting it now would mean orphan
> `project_id` columns with no foreign key, or a generic resource/ACL table —
> exactly the abstraction-heavy design this rebuild exists to remove.
>
> PR-MVP-01 therefore delivers authentication, identity, the fixed role
> catalogue and role-aware API enforcement. **`user_project_access`,
> project-scoped authorization and real foreign-key integrity to Projects move
> to PR-MVP-02**, where there is something to point at. This is an integrity
> correction, not a scope reduction.

## PR-MVP-02 — Project, Land & Permits ✅

- project
- **`user_project_access` and project-scoped authorization** (deferred from
  PR-MVP-01, which had no Project to reference)
- parcel
- planning controls
- permit register
- permit dates/statuses
- blocking/critical-path indicators
- documents/references

> **Phase-scoped access is deferred to PR-MVP-03.** The MVP specification
> describes project *and phase* row-level access. `Phase` does not exist until
> PR-MVP-03, so building phase scoping now would mean a nullable `phase_id` with
> no foreign key, a placeholder Phase, or a generic `resource_type`/`resource_id`
> table — the same abstraction-first mistake the project deferral avoided in
> PR-MVP-01.
>
> PR-MVP-02 therefore delivers project-level row access with real foreign-key
> integrity. Phase-scoped narrowing can be added in PR-MVP-03 against a real
> Phase, if the product still needs it.

## PR-MVP-03 — Inventory & Configurable Fields ✅

- phase
- **phase-scoped access** (the narrowing PR-MVP-02 deferred, now against a real
  `Phase` with a real foreign key)
- building
- floor
- unit
- areas — project-configured area types, versioned unit area schedules, weight
  factors and a derived weighted saleable area
- features
- parking/storage/sub-assets
- separate status dimensions — commercial, legal, collection and delivery are
  four columns, never one `status`
- unit completeness/release controls
- constrained custom-field metadata/value system
- bulk import/update — CSV validate then apply, all-or-nothing

> **`pricing_approved` is a release gate, not a price.** A unit cannot be
> released without it, and PR-MVP-03 exposes no way to set it: the flag becomes
> writable in PR-MVP-04 when a price exists to approve. There is deliberately no
> override button and no bypass.

> **Company-scoped configurable fields are deferred.** A field definition can be
> scoped to a country pack, a project or a unit type. `company` is not offered
> because no Company entity exists — inventing one to satisfy a scope label would
> be the same abstraction-first mistake the access deferrals avoided.

## PR-MVP-04 — Pricing & Unit 360 ✅

- pricing configuration — one governed, versioned policy per project, and at
  most one of them active
- effective-dated price versions — a price is never overwritten; a change is a
  new version and the one it replaces is superseded and stays readable
- area pricing — each area type priced at the internal base rate, its own rate,
  a factor of the internal rate, or excluded
- premiums — a closed list of real unit facts, additive by default, compounding
  only when a rule asks for it, capped visibly
- escalation — configured rules activated by a named approver against recorded
  evidence, which produce new price versions rather than rewriting live ones
- market comparison fields — manually governed benchmarks, one per scope, with
  a stated area basis and a tolerance
- **`pricing_approved` becomes writable** (deferred from PR-MVP-03), and only
  by activating a price. There is no button and no override.
- Unit 360 — the unit detail evolves to carry the live price, its waterfall,
  its history and a quote preview

> **Cost, margin and profitability are not here.** Governed unit cost
> allocations arrive in PR-MVP-08, and inventing them earlier would put a
> fabricated cost inside a real margin. PR-MVP-04 builds the complete
> revenue-side model and stops there.

> **The quote preview creates nothing.** No client, no reservation, no sale, no
> stored exception. PR-MVP-05 owns the transaction that freezes any of it.
- quote controls
- discounts/packages/allowances
- pricing approval
- price waterfall
- Unit 360 foundation

## PR-MVP-05 — Sales & Legal ✅

- clients and buyer parties — project-scoped, with joint purchase as the
  ordinary case: shares are a column, and they must total exactly 1.000000
  before a unit can be committed
- reservations — the first persistent commercial commitment, freezing the quote
  pricing produced from the unit's live approved price, and holding it for the
  term of a price lock that a later list price does not void
- an explicit re-quote for a live reservation whose lock has run out: the same
  buyer and unit at today's approved price, on the record, with the standing
  approval withdrawn
- the commitment is exclusive — one live reservation and one live contract per
  unit, decided under the unit row lock with partial unique indexes behind it
- sale contracts — the SPA, its frozen price, its frozen buyer parties and the
  tax observation it was signed under, none of which a later correction moves
- sales exceptions — maker/checker against the country's own thresholds, with
  no approval engine: two role checks and one comparison of identifiers
- legal events — an append-only registry timeline; a mistake is corrected by
  another dated event beside it, never by editing or deleting the first
- cancellation — a controlled process with a money decision and, where the
  registry is involved, a withdrawal, before the unit comes back as `returned`
  with its pricing approval withdrawn
- handover — three clearances owned by three different departments, plus the
  gates a project configures for itself in six named booleans

> **The deposit and first-payment gates are attestations, not receipts.** They
> record that a named person saw evidence, and must never be counted as cash
> collected. PR-MVP-07 introduces the record that can say money arrived.

> **No payment plan, no receipt, no cost and no margin.** A reservation and a
> contract carry the terms that were agreed; scheduling the money is PR-MVP-06,
> collecting it is PR-MVP-07, and what the unit cost to build is PR-MVP-08.

## PR-MVP-06 — Payment Plans ✅

- payment-plan header, one per sale contract
- plan versions, one governing at a time
- unlimited installment rows
- fixed-date triggers
- days-after-SPA triggers
- recurring monthly and quarterly triggers
- construction-milestone trigger definitions
- handover and title-transfer triggers
- manually approved trigger events, maker/checker
- exact principal, percentage, tax, buyer-fee and buyer-total reconciliation
- plan approval and activation
- payment plan builder, project register, deal file and Unit 360 integration

> **Where the boundary sits.** PR-MVP-06 records what the buyer is contractually
> scheduled to pay, how much, when, and which event makes each amount due. It
> records nothing about money arriving: there is no receipt, no allocation, no
> paid or outstanding balance and no aging anywhere in the schema, because that
> is PR-MVP-07's truth to state.
>
> Three distinctions this PR exists to keep, and that later work must not
> collapse. A signed contract for 220,000 is not a payment plan. A plan
> scheduling 220,000 is not 220,000 collected. And a milestone **forecast** is
> not a certified milestone — a construction-milestone installment stays
> awaiting its trigger however long its forecast date has passed, enforced by a
> database CHECK as well as by the service, until PR-MVP-09 can certify it.
>
> PR-MVP-05's deposit and first-payment gates are attestations that evidence
> exists. They are never subtracted from a schedule and never read as a receipt.

## PR-ENG-01 — Two-Speed CI ✅

Horizontal engineering hardening. **Does not change the functional MVP count.**

- draft pull requests run `Backend Fast`: structural checks plus the tests the
  change can plausibly break
- pull requests marked ready for review run `Backend`: the entire suite, on the
  exact merge candidate
- explicit domain map with downstream closure, in one standard-library file
- unknown module, shared fixture, `app/core/` or access-layer change falls back
  to the full suite and says why
- selector regression tests, including a guard that no test file is unclaimed
- no migration, no dependency, no runtime behaviour change

> **Why it sits here.** At roughly fifteen hundred backend tests the full suite
> takes about forty-five minutes, and running it on every push made a one-line
> correction cost the same as a whole feature. Merge safety is unchanged: the
> full suite is still mandatory before merge, and any commit pushed after a
> pull request is marked ready re-runs it, so the green tick always belongs to
> the exact commit somebody would merge.

## PR-MVP-07 — Collections ✅

- receipt ledger, recorded and confirmed as separate facts
- receipt confirmation by Finance, maker/checker by user identifier
- receipt-to-installment allocations, split and partial
- unapplied cash, derived and reported, never absorbed
- receipt and allocation reversal
- derived installment collection status and aging, for any as-of date
- collection actions, promises kept separate from cash
- disputes and approved operational waivers
- collection restructures, carrying confirmed cash onto the replacement schedule
- refunds against a cancellation's approved amount due
- Unit collection status, collection clearance, deal file and Unit 360 integration

> **Where the boundary sits.** PR-MVP-06 records what the buyer is scheduled to
> pay. PR-MVP-07 records what actually arrived, where it was applied, what
> remains outstanding and what Collections is doing about it. The two are joined
> by allocations and by nothing else: there is no `paid_amount` on an instalment
> and no balance column anywhere in this PR, because every figure — outstanding,
> unapplied, days overdue, aging bucket, collection status — is computed from
> rows at read time.
>
> Five distinctions this PR exists to keep. A *recorded* receipt is a claim and
> moves no balance; only a confirmed one is cash. A receipt is not an
> allocation, and cash that has arrived but not been applied is reported as
> unapplied rather than quietly absorbed. A refund is money leaving and has its
> own table, never a negative receipt. A dispute never reduces a receivable, and
> an operational waiver never reduces principal, tax or buyer fees. And
> PR-MVP-05's deposit and first-payment attestations remain attestations — they
> are not converted into receipts and not subtracted from anything.
>
> The dangerous operation is the restructure. Replacing a schedule that already
> has cash against it would leave every allocation pointing at instalments that
> no longer govern the sale, so the ordinary payment-plan activation path
> refuses once cash has been confirmed, and the restructure carries the
> allocations across in the same transaction — or refuses outright if a single
> unit of cash cannot be placed.

## PR-MVP-08 — Unit Economics ✅

- governed allocation versions, one current basis per project
- cost pools by category — land, hard, soft, finance — scoped to project, phase
  or building
- land cost derived from the land register, never retyped — one canonical,
  project-wide land pool per version, enforced in the database
- five allocation methods: weighted area, raw area, unit count, revenue value
  and a per-unit custom driver
- exact Decimal allocation with a deterministic rounding residual
- stale-source detection at submission and again at activation, including the
  set of units a pool divides among
- direct unit costs and variable selling costs, recorded and reversed
- explicit finance-cost treatment: allocated or excluded, never assumed nil
- sold vs unsold unit economics on their own bases
- gross profit, contribution profit, profit after finance
- margin and return on cost, weighted at project level
- pool, version and project reconciliation
- Unit 360 integration and a sale-specific economic read

> **Where the boundary sits.** PR-MVP-04 says what a unit can be sold for and
> PR-MVP-05 what was actually agreed. PR-MVP-08 says what it costs, and keeps
> two answers apart rather than blending them: an **unsold** unit is analysed on
> today's approved price and today's active cost basis, and a **sold** one on
> the frozen contract terms and the allocation version that was governing when
> the contract was signed. Activating a new basis tomorrow moves the first and
> leaves the second exactly where it is, which is why a version has an effective
> window at all.
>
> That freeze is achieved by effective dating, not by a foreign key: nothing in
> sales, pricing, inventory or projects gained a column, and none of them
> imports this module. The date the contract became **binding** — the later of
> its two signatures, answered by sales — matched against a version's window, is
> the whole mechanism. Not the contract's draft date: a contract drafted in
> February and signed in June belongs to whichever basis was governing in June.
>
> The write side is constrained to match. A project's first cost basis may be
> back-dated, because this module arrived after sales existed. Every replacement
> takes effect today, because one dated into the past would close the standing
> version's window on a period already lived and move every contract signed in
> the overlap onto a basis that did not exist when it was signed.
>
> Three refusals define the module. Every cost pool must reconcile to its
> allocations **exactly** — not within a cent — with the rounding residual going
> to one deterministic recipient. Unlike currencies are never combined: a unit
> whose revenue is not in the project's cost currency reports both figures and
> no margin, and the project summary counts it out loud rather than dropping it.
> And an incomplete input never produces a number: a missing price, a missing
> cost basis or a stale allocation returns a status saying so, because a
> fabricated margin is worse than an absent one. A unit the basis never
> allocated to is one of those cases and not a zero-cost unit — otherwise a unit
> created after activation would report the best margin in the project, produced
> by an omission.
>
> Allocations are the one derived-looking thing this platform stores, and the
> reason is that they are not derivable twice. A version has to preserve which
> units were eligible, what driver each carried, which approved area schedule and
> which price version supplied it, and where the residual landed. Profit itself
> is still computed at read time and stored nowhere.
>
> **Not here:** no construction ledger — PR-MVP-09 owns cost codes, contracts,
> certificates and payments; no cashflow, IRR or NPV — PR-MVP-10 owns those; no
> FX; no corporate tax. A hard-cost pool is an economic forecast allocation
> input, and the screens say so.

> **PR-UX-02 lands here.** The flagship product experience — the grouped
> navigation rail, the project command centre and the record files — is a
> horizontal checkpoint taken from `main` after PR-MVP-08 and before
> construction control begins. It carries no MVP number; see
> [Horizontal checkpoints](#horizontal-checkpoints).

## PR-MVP-09 — Construction Control

- construction budget baseline
- cost codes/WBS
- vendor/contract
- variations
- progress certificates
- retention
- advance recovery
- invoices
- payments
- construction milestones
- committed/certified/invoiced/paid separation
- forecast at completion

## PR-MVP-10 — Integrated Cashflow & Management Reporting

- customer scheduled inflows
- forecast collections
- actual receipts
- refunds
- escrow/restricted cash fields
- development outflows
- financing flows
- monthly opening/inflow/outflow/closing
- cumulative cash
- funding gap
- peak deficit
- next 30/60/90-day view
- management dashboards
- drill-down
- exports
- final Unit 360 integration

Do not build advanced forecasting AI. If scenario controls are included, keep
them as simple explicit input cases — never a generic scenario engine.

## PR-MVP-11 — Migration, UAT & Go-Live

- source workbook import mapping
- import batches
- validation
- reject reporting
- trial migration
- inventory reconciliation
- GSV reconciliation
- contract reconciliation
- payment schedule reconciliation
- receipt reconciliation
- construction reconciliation
- opening cashflow reconciliation
- UAT test pack
- security hardening
- data-quality checks
- operational documentation
- cutover checklist
- launch support

---

## Horizontal checkpoints

These are not functional pull requests and do not renumber anything above. The
canonical sequence remains twelve, `PR-MVP-00` through `PR-MVP-11`. A
checkpoint touches every module that exists at the time it lands, adds no
schema, no migration and no business logic, and is named for what it hardens
rather than what it builds.

### PR-UX-01 — Product Experience & Design System

Branch `ux/pr-01-product-experience`, taken from `main` after PR-MVP-05 merged.

- one light theme; the `prefers-color-scheme` block removed and
  `color-scheme: light` declared
- a full token layer — surfaces, text, intent, spacing, radius, elevation,
  typography scale, content widths, motion
- `components/ui.tsx` replaced by `components/ui/`: Button, Badge, Card,
  SubPanel, PageHeader, SectionHeader, Tabs, TabPanel, Drawer, Field, FilterBar,
  FormActions, StickyActions, TableScroll, KeyValueGrid, Stat, Notice,
  EmptyState, Loading, Timeline, Steps, ConfirmDialog, PromptDialog, Icon
- a sticky application shell with real navigation between Projects and Settings
- Unit 360 rebuilt as a six-section drawer that opens over the register rather
  than under it
- the deal file rebuilt as a five-section drawer, with a labelled reason dialog
  in place of `window.prompt`
- registers moved to reported figures, tone-coded status badges and tabular
  numerics; every wide table scrolls inside itself
- tab groups given namespaced ids, the selected tab kept in view, and the
  application bar made to fit a phone
- `docs/UX_SYSTEM.md` added as the design system's reference

No migration, no schema change, no backend logic, no API contract change, no
new dependency of any kind, and no financial arithmetic added to the browser.

### PR-UX-02 — Flagship Product Experience & Workspace 2.0

Branch `claude/flagship-product-experience-mhgzcf`, taken from `main` after
PR-MVP-08 merged and before PR-MVP-09 begins. Records the product's
transformation from a functional MVP into a workspace: how the eleven modules
are navigated, how a project is read at a glance, and how a record is opened.

- the project-wide horizontal tab strip replaced by a grouped vertical rail —
  Overview; Development (Land, Permits, Inventory); Commercial (Pricing,
  Sales & Legal, Payment Plans, Collections); Finance (Unit Economics);
  Governance (Documents, Access) — with a first-class project switcher and a
  quiet context bar carrying breadcrumbs, project status and base currency
- the rail collapses to icons between 64rem and 75rem, becomes a focus-trapped
  drawer below 64rem, and remembers an explicit choice in `localStorage`
- navigation, sections and record tabs mirror the backend's role contracts
  (`frontend/src/lib/roles.ts` beside `app/modules/*/permissions.py`): a role
  that cannot read a module has no entry for it, and the browser never
  requests what the server would refuse — Unit Economics, internal prices, the
  collections position and the list price are each asked for only on behalf
  of a role the server answers
- a Project Overview command centre composed solely from the summary endpoints
  that already exist — inventory, pricing overview and register, sales
  register, payment plans, collections summary and unit economics summary —
  with a "needs attention" list built from server counts, no charts and no
  placeholder figures; a section a role cannot read is not requested
- the Projects landing rebuilt as a filterable register of project tiles
- tokens 2.0: a warm canvas, a cobalt accent, a dark navigation rail, a
  numeric scale for page, record, section and metric titles, and layout
  tokens for the rail, context bar and drawers; figures set in tabular sans
  with the monospace face reserved for identifiers
- a page-header, toolbar, register, form and drawer system —
  `PageHeader`, `Metric`/`MetricGroup`, `StatusDot`, `InlineMeta`,
  `Waterfall`, `DataToolbar`/`ToolbarFilter`, `FieldRow`, `FormSection`,
  `MoneyInput`, `RateInput`, drawer facts strips, `Loading` shapes — and every
  register moved onto it with a compact header, a toolbar and a fixed
  identity column
- Unit 360 redesigned: a facts strip (list price, margin, outstanding, weighted
  area — each present only for a role entitled to it), the four status
  dimensions side by side, and Overview, Areas & features, Pricing, Sales &
  legal, Collections, Economics, Release and History sections; the cost
  waterfall and the price composition drawn as server-ordered waterfalls
- the deal file redesigned: a facts strip (contract price, net of tax,
  contract date, gate), a lifecycle strip drawn from the server's statuses,
  and Commercial, Buyers, Contract, Legal, Payment plan, Collections,
  Cancellation and Handover sections; the quote drawn as a waterfall
- the payment plan builder and the collections account given facts strips;
  percentages typed as percentages and sent as fractions by string
  manipulation; money inputs denominated in the record's own currency
- settings and sign-in rebuilt on the same shell; `docs/UX_SYSTEM.md` rewritten
  as UX System 2.0
- validated in a real browser with seeded data at 1600, 1440, 1280, 1024, 768
  and 390 wide, as every role, with no page-level horizontal overflow and no
  unexpected console error

No migration, no schema change, no backend logic, no API contract change, no
new dependency of any kind, no dark theme, no FX, no construction screens, and
no financial arithmetic added to the browser.

### PR-UX-03 — Interior Product Surfaces

Branch `claude/flagship-product-experience-mhgzcf`, taken from `main` after
PR-UX-02 merged. The shell landed with PR-UX-02 and the interiors did not keep
up: inside a 2030-grade frame, most module screens were still a white card, a
title, some small numbers and a table. This closes that gap.

- a surface hierarchy — command, operational, data, attention, record — with
  card tones, and the navigation rail's own ink as a hairline over a command
  surface, so the most important block on a page belongs visibly to the same
  object as the navigation
- reported figures set like a tear sheet: large, tight, tabular, label beneath
  (`Position`, `PositionFigure`, `PositionSupport`), with ordinary metrics
  keeping the label above so a page says which of its figures is the answer
- new compositions built only from server values — `StatStrip` for register
  counts, `Breakdown` with dot leaders for the parts of a total, `Distribution`
  for an aged balance, `Meter` for a percentage the API returned, `IdentityCell`
  and `PlaceCell` for a register row's identity, `ExternalLink` for a
  destination outside the product
- a project identity plate that says the place and links the map, rather than
  printing a hundred characters of map query string as the development's name
- Project Overview recomposed as a command centre: a dominant project position
  with the cost composition beneath it, a compact attention list beside it, and
  two columns that stack independently so a long attention list never opens a
  void under the position
- Inventory rebuilt as an operating register: a compact status strip, one
  framed command row for search and filters with active filters marked, a unit
  identity anchor, a hierarchical location cell, area merged into one column,
  the four status dimensions as dots, a readiness meter drawn at the server's
  own completeness percentage, and row hover, focus, open and flagged states
- Pricing, Sales & Legal, Payment Plans, Collections and Unit Economics each
  given the command position their page exists to state; Permits given a status
  strip and a warm rail on the rows the server flagged; the deal file's quote
  and contract brought onto the same figure language
- forms given comfortable control heights and quieter labels; project tiles
  levelled; documents given a proper external-link treatment
- `docs/UX_SYSTEM.md` gains the surfaces section and the new primitives

No migration, no schema change, no backend logic, no API contract change, no new
dependency of any kind, no chart, no dark theme, no FX, and no financial
arithmetic added to the browser.
