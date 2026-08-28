# MVP 1.0 Roadmap — Reach Developments Station

Canonical delivery sequence. Twelve pull requests, `PR-MVP-00` through
`PR-MVP-11`, each merged into `main` on its own short-lived branch.

| Scope                            | Count |
| -------------------------------- | ----: |
| Total planned MVP PRs            |    12 |
| Complete (PR-MVP-00, PR-MVP-01)  |     2 |
| Remaining                        |    10 |

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

## PR-MVP-03 — Inventory & Configurable Fields

- phase
- building
- floor
- unit
- areas
- features
- parking/storage/sub-assets
- separate status dimensions
- unit completeness/release controls
- constrained custom-field metadata/value system
- bulk import/update

## PR-MVP-04 — Pricing & Unit 360

- pricing configuration
- effective-dated price versions
- area pricing
- premiums
- escalation
- market comparison fields
- quote controls
- discounts/packages/allowances
- pricing approval
- price waterfall
- Unit 360 foundation

## PR-MVP-05 — Sales & Legal

- clients
- reservations/EOI
- reservation lock
- contract/SPA
- frozen sale snapshot
- sales exceptions
- legal events
- registration
- cancellation
- handover gates

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
