# MVP 1.0 Roadmap — Reach Developments Station

Canonical delivery sequence. Twelve pull requests, `PR-MVP-00` through
`PR-MVP-11`, each merged into `main` on its own short-lived branch.

| Scope                                 | Count |
| ------------------------------------- | ----: |
| Total planned MVP PRs                 |    12 |
| Complete (PR-MVP-00 through PR-MVP-05) |     6 |
| Remaining                             |     6 |

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

## PR-MVP-06 — Payment Plans

- payment-plan header
- unlimited installment rows
- plan versions
- fixed-date triggers
- relative-date triggers
- recurring triggers
- milestone triggers
- handover/title triggers
- total % / amount reconciliation
- plan approval

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
