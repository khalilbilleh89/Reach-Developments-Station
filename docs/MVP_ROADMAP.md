# MVP 1.0 Roadmap — Reach Developments Station

Canonical delivery sequence. Twelve pull requests, `PR-MVP-00` through
`PR-MVP-11`, each merged into `main` on its own short-lived branch.

| Scope                                 | Count |
| ------------------------------------- | ----: |
| Total planned MVP PRs                 |    12 |
| Complete (PR-MVP-00 through PR-MVP-06) |     7 |
| Remaining                             |     5 |

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

## PR-MVP-07 — Collections

- receipts
- receipt confirmation
- receipt-to-installment allocations
- partial payments
- unapplied cash
- installment status logic
- aging
- collection actions
- disputes/waivers
- restructures
- refunds

## PR-MVP-08 — Unit Economics

- direct unit costs
- cost pools
- allocation versions
- land allocation
- hard-cost allocation
- soft-cost allocation
- variable selling cost
- finance-cost treatment
- sold vs unsold unit economics
- gross profit
- contribution profit
- margin
- return on cost
- project reconciliation

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
