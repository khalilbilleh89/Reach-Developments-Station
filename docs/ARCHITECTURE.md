# Architecture — Reach Developments Station

Canonical architecture document for MVP 1.0. Every roadmap PR is expected to fit
inside this shape or to change this document explicitly as part of its review.

---

## 1. What this product is

A real estate development **tracking and financial control system**.

- Its operational centre is the individual **property unit**.
- Its financial spine is **project cashflow**.

It provides one editable, auditable source of truth for projects, land and
permits; phase/building/floor/unit inventory; pricing and price history; clients,
reservations and sales contracts; sales exceptions and concessions; custom
payment plans; installments; receipts and allocations; collections and aging;
unit economics; construction budgets, certificates, invoices and payments;
consolidated project cashflow; and management reporting and audit history.

It is deliberately **not** a broad "Developer Operating System".

---

## 2. Product architecture

```text
Project Control
│
├── Project / Land / Permits
├── Inventory
├── Pricing
├── Sales / Legal
├── Payment Plans
├── Collections
├── Unit Economics
├── Construction
├── Cashflow
└── Reporting
```

## 3. Core hierarchy

```text
Project
└── Phase
    └── Building
        └── Floor
            └── Unit
```

The **Unit** is the primary commercial operating record.
The **Project Cashflow** is the financial spine.

## 4. Information layers

```text
Configuration
Master Data
Transactions
Calculations
Reporting
```

Each layer reads downward, never upward. Reporting never becomes a place where
new business truth is invented; it renders what the transaction and calculation
layers already hold.

---

## 5. Runtime architecture

```text
Browser
   │
   ▼
Single Render Web Service
   │
   ├── FastAPI API            /api/v1/*
   │
   ├── Static Next.js export  /*
   │
   └── PostgreSQL connection
```

There is exactly one of each:

| Concern            | Count | Notes                                          |
| ------------------ | ----: | ---------------------------------------------- |
| GitHub repository  |     1 | this repository                                |
| Backend app        |     1 | FastAPI modular monolith under `app/`          |
| Frontend app       |     1 | Next.js static export under `frontend/`        |
| PostgreSQL database|     1 | Render PostgreSQL                              |
| Render web service |     1 | serves both API and static frontend            |
| Migration history  |     1 | Alembic, rooted at `0000_mvp_baseline`         |
| API namespace      |     1 | `/api/v1`                                      |

No other infrastructure is justified at MVP stage. See
[ENGINEERING_RULES.md](ENGINEERING_RULES.md) for the full forbidden list.

---

### Frontend shell

The frontend is a static export served from `frontend/out`: no server
components, no server actions, no dynamic route segments. An open project and
its section travel in the query string — `/projects/?project=<id>&section=<key>`,
`/settings/?section=<key>` — because project identifiers are runtime data and
a dynamic segment would need them at build time.

Since PR-UX-02 the shell is a grouped vertical rail with a project switcher, a
context bar carrying breadcrumbs and the project's status and base currency,
and a working surface that never scrolls sideways; PR-V2-00 rebuilt its
presentation as Product Experience 3.0 without changing that structure. Records — a unit, a deal, a
payment plan, a collections account — open as files over the register that led
to them. The pieces live in `frontend/src/components/shell/` (`AppShell`,
`AppSidebar`, `ProjectSwitcher`, `ContextBar`, `navigation.ts`) and the
primitives in `frontend/src/components/ui/`; `docs/UX_SYSTEM.md` is the
reference.

Two rules bind the shell to the backend. Visibility mirrors the permission
sets in `app/modules/*/permissions.py` through `frontend/src/lib/roles.ts`: a
role with no right to a module has no navigation entry for it, no section for
it and no request to it — the browser never fetches what it may not show and
hides it afterwards. And the browser never calculates: every price, tax,
margin, total, allocation and approval requirement on screen is a value the
API returned on that request, and `frontend/src/lib/format.ts` only formats
the server's decimal strings.

**The V2 frontend principle (from PR-V2-00).** Backend modules remain
normalised; the frontend may orchestrate several domain APIs around the
operator's real-world record or workflow. Unit 360 is the case in point: one
record file reads inventory, pricing, sales, collections and unit economics —
each through its own module's contract, each only on behalf of a role that
module's permissions answer — and composes them around the unit the operator
is actually looking at. That composition lives in the frontend and is
presentation; it creates no cross-module dependency on the server, moves no
calculation into the browser, and does not make the frontend a monolith: each
module's screen still speaks only to its module, and the orchestrating record
is a thin layer of `useAnswer` calls over the same contracts. Where a screen
needs a figure no module returns, the owning module grows the figure; the
orchestrator never derives it. `docs/UX_SYSTEM.md` (Product Experience 3.0)
is the reference, and `tests/test_product_experience.py` reads the sources to
hold the line.

## 6. Backend module shape

A domain normally starts with exactly four files:

```text
app/<domain>/
├── models.py     SQLAlchemy models
├── schemas.py    Pydantic request/response contracts
├── service.py    domain logic and transaction boundaries
└── api.py        route handlers: validate, authorize, orchestrate
```

`repository.py` is **optional**. Add it only when persistence complexity or
reusable query logic genuinely warrants it — never as default boilerplate.

### Dependency direction

```text
app/core
   ↑
domain modules
   ↑
API composition
```

- `app/core` must never import a business domain.
- A domain may use core configuration, core database/session infrastructure and
  shared primitive helpers.
- A domain must not manipulate another domain's persistence internals.

Forbidden:

```python
# sales/service.py
collections_row.amount_paid = ...  # reaching into another domain's models
```

Preferred:

```python
# sales/service.py
collections_service.record_allocation(...)  # a small public contract
```

Create that contract **when the cross-domain interaction actually appears**, not
in advance. No circular imports.

The business domains stack in one direction, and it is never reversed:

```text
inventory  ↑  pricing  ↑  sales  ↑  payment_plans  ↑  collections
                               ↑  unit_economics
                  payment_plans  ↑  construction  ↑  unit_economics
```

`payment_plans` reads sales through its public service contract — a completed
handover, an effective title-transfer event — to resolve the triggers that make
an instalment due. Sales does not import payment plans, and `sale_contracts`
carries no column pointing at one: a sale's governing schedule is found through
`payment_plans.sale_contract_id`, so the upstream domain gains no dependency on
the downstream one. Where a screen needs both, the frontend composes the two
responses.

`collections` sits at the end of the chain and writes into three domains above
it, always through a named contract and never into a column:

```text
collections → inventory.apply_collection_status              the unit's collection dimension
collections → sales.apply_collection_clearance               the handover gate
collections → sales.revoke_collection_clearance              when the ledger reopens
collections → payment_plans.mark_collections_started         the boundary marker
collections → payment_plans.activate_restructured_version    the carried-forward schedule
```

None of the three imports collections. The one column any of them gained is
`payment_plans.collections_started_at`, and it lives there rather than in a
collections table because the rule it guards is one payment plans enforces:
once cash has been confirmed against a schedule, the ordinary activation path
refuses to swap its instalments out, because the allocations already made point
at the rows being replaced. `activate_restructured_version` is the single way
past that guard, it is deliberately not an HTTP route, and the only caller is
the restructure — which carries every allocation across in the same transaction
or refuses outright.

`unit_economics` reads four domains and writes into none of them:

```text
unit_economics → projects        the land register, for the land cost pool
unit_economics → inventory       units, scope, and the approved area schedule
unit_economics → pricing         the current approved price, as revenue and as a driver
unit_economics → sales           frozen contract terms, frozen seller costs and
                                 the date the contract became binding
```

The interesting part is what is *not* there. A sold unit must keep the cost
allocation basis that governed when its contract was signed, and the obvious way
to arrange that — a `sale_contracts.unit_economics_version_id` — would make sales
depend on a module that arrived four PRs later. So the link is effective dating
instead: an allocation version carries a window, and the sale's own economic date
selects the version whose window contains it, permanently. No upstream table
gained a column, nothing calls back into sales, and there is no event or plugin
mechanism doing it quietly. It is the same principle as an effective-dated price,
applied to cost.

That date is **not** `contract_date`, which is stamped when the contract is
*drafted*. Between drafting and signature a project's cost basis can be replaced,
and freezing on the draft date would hand a deal a basis that had already been
superseded by the time the parties signed. Sales owns the lifecycle, so sales
owns the answer.

Two contracts sales gained, both readers:

```text
frozen_seller_costs(sale)          the commercial / finance split of the seller
                                   costs the contract froze
economic_contract_date(session,    the date the contract became binding on both
                       sale)       parties — the later of the two signatures
                                   that `activate_sale` already insists on, or
                                   None where the contract is not yet signed
```

Both live in sales because sales owns what they read: the quote snapshot for the
first, the legal timeline for the second. A second domain learning the shape of
somebody else's JSON, or deciding for itself which milestone makes a contract
binding, is a dependency nobody declared.

A sale that returns `None` has no sold economics at all — not today's basis, and
not the draft date's. A proposal is not a deal.

Effective dating cuts both ways, so the write side is constrained to match. The
*first* version on a project may be back-dated, because PR-MVP-08 arrived after
sales existed and those contracts need a baseline. Every later one takes effect
today: a replacement dated in the past would, on activation, close the standing
version's window on a date already lived, and every contract signed in the
overlap would silently change cost basis.

`construction` sits above payment plans and below unit economics, and it is the
only domain that both reads a contract and is read through one:

```text
construction → inventory.apply_delivery_status                  not_started → under_construction → ready
construction → payment_plans.plans_awaiting_milestone           which schedules wait on a milestone code
construction → payment_plans.apply_construction_milestone_certification
                                                                the instalments a certification makes due
unit_economics → construction.hard_cost_estimate_at_completion  the governed hard cost, and its forecast id
unit_economics → construction.hard_cost_estimate_of             what a *pinned* forecast says today
```

Payment plans does not import construction, and no instalment column is written
outside that contract. The direction is the point: construction is the only
module that can say what certification *is*, and payment plans is the only
module that owns a buyer's due date. A milestone reported complete by site
cannot reach a schedule — only a formal certification can, and the date written
is the certified date rather than today.

Delivery status is the same shape in the other direction. Construction owns
`not_started → under_construction → ready` and nothing above it: the handover
states belong to sales, and construction's write path refuses a unit that has
already reached one. Every move goes through inventory's contract, so the
append-only status event exists whoever asked for the change, and a bulk action
validates every unit before applying any of them — a building left in two states
is worse than a refusal.

Unit economics reads construction rather than the reverse, and it reads a
*snapshot*. A cost pool sourced from a forecast stores the amount **and** the
forecast version it came from, and that pin is what stops a later forecast
appearing to rewrite a basis units were already sold against: the derived amount
is refreshed only while the version is a draft, and a superseded pin makes the
basis stale — refused at submission and again at activation — rather than
silently re-derived. Construction never writes a cost pool, never reads an
allocation, and never learns what a unit earns.

Reading another domain's rows is ordinary and done directly. Writing them is
not, and there is no path in collections, unit economics or construction that
does.

---

## 7. Current state (through PR-MVP-09)

```text
app/
├── main.py                  application factory, middleware, error mapping, static mount
├── api/health.py            liveness and readiness
├── core/config.py           environment configuration, database URL normalisation
├── core/correlation.py      per-request correlation identity
├── core/database.py         the one engine, the one session factory
├── core/errors.py           service error types, mapped to status codes in one place
├── core/patching.py         PATCH change-set semantics (omitted vs explicit null)
├── db/base.py               the one declarative base, money/rate column types
└── modules/
    ├── access/              identity, sessions, fixed roles, user administration
    ├── settings/            currencies, country packs, tax rules, lookups, thresholds
    ├── projects/            projects, project access, land, planning, permits, documents
    ├── inventory/           phases, buildings, floors, units, areas, configurable fields
    ├── pricing/             pricing policy, price versions, premiums, escalation, benchmarks
    ├── sales/               clients, reservations, contracts, legal events, cancellation, handover
    ├── payment_plans/       payment schedules, versions, instalments, triggers
    ├── collections/         receipts, allocations, aging, disputes, waivers, restructures, refunds
    ├── construction/        cost codes, budgets, contracts, variations, certificates,
    │                        invoices, payments, milestones, forecasts
    ├── unit_economics/      cost pools, allocation versions, unit costs, profitability
    └── audit/               append-only governance history
```

The `projects` module carries a fifth file beside the usual four:

```text
app/modules/projects/
├── models.py
├── schemas.py
├── permissions.py    the project security boundary
├── service.py
└── api.py
```

`permissions.py` earns its place because project-scoped authorization is a
first-class concern every nested route depends on, and encoding it separately in
each route is how one route ends up missing it. It is four small functions and
one dependency — not a policy engine, and not a generic RBAC framework.

`inventory` carries three extra files, each for a concern that would otherwise
be spread across every route that touches it:

```text
app/modules/inventory/
├── models.py
├── schemas.py
├── permissions.py       the phase security boundary and the release-field gate
├── custom_fields.py     definition, option and value handling for configurable fields
├── import_service.py    CSV parse, validate and apply
├── service.py
└── api.py
```

`custom_fields.py` and `import_service.py` are separated because each is a
self-contained problem with its own vocabulary — not because a file grew long.
Neither is generic: the first handles a fixed list of data types against three
named entities, and the second parses one documented column set.

`pricing` carries two extra files for the same kind of reason:

```text
app/modules/pricing/
├── models.py
├── schemas.py
├── permissions.py    who may price, who may approve, who may only look
├── calculator.py     the pricing arithmetic, with no session and no actor
├── service.py
└── api.py
```

`calculator.py` earns its place by having no database at all. It takes explicit
`Decimal` inputs and returns a priced result with every component line; it
cannot query, cannot authorise and cannot write. That is what makes a price
reproducible: a calculation that could also read a row is a calculation whose
answer depends on when you asked. It is not a framework — there is no expression
language, no rule evaluator and no plug-in point, only the fixed set of
contributions a real estate list price is made of.

`permissions.py` holds the one rule this module adds to the platform: the person
who prepares a price is not the person who approves it, and a System
Administrator is not an approver. Phase visibility is imported from inventory
rather than restated, because a unit's price must be exactly as visible as the
unit.

`sales` carries the same fifth file, for three separations rather than one:

```text
app/modules/sales/
├── models.py
├── schemas.py
├── permissions.py    who may sell, who may approve, who may see a passport number
├── service.py
└── api.py
```

Maker is not checker, administration is not business authority, and one
department cannot clear another's concern. Phase visibility is again imported
from inventory: a sale must be exactly as visible as the unit it is a sale of.
Personal data is decided in this file, before serialisation — a caller who may
not read a buyer's identity documents gets a response on which those fields do
not exist, which is a different thing from a response that blanks them.

`payment_plans` carries a sixth file, and it is the one that makes the module
testable:

```text
app/modules/payment_plans/
├── models.py
├── schemas.py
├── permissions.py    Collections prepares, the CFO sanctions, nobody does both
├── schedule.py       Decimal allocation, calendar arithmetic, reconciliation
├── service.py
└── api.py
```

`schedule.py` holds pure functions over values — no session, no request, no
permission check, no audit write. Splitting a contract across twenty
instalments, adding a calendar month to 31 January, and deciding whether a
schedule reconciles are arithmetic questions, and keeping them in a module with
no infrastructure means each one can be tested on its own and each failure names
the arithmetic rather than a route.

Two disciplines run through it. Every amount is a `Decimal` quantised to the
platform's monetary scale — a float is a wrong answer about money. And the
rounding residual from splitting a total is allocated to a named line rather
than dropped, so the stored rows add up to the contract exactly; a schedule
whose percentages come to 0.95 allocates 95% and reports the shortfall, and is
never quietly rounded up until it reconciles.

### The three truths, and why they stay apart

```text
PR-MVP-05  Contract truth              what was agreed, at what frozen price
PR-MVP-06  Scheduled receivable truth  what is due, when, and what makes it due
PR-MVP-07  Cash collection truth       what actually arrived
```

A signed contract for 220,000 is not a payment plan. A plan scheduling 220,000
is not 220,000 collected. A milestone forecast is not a certified milestone, and
a confirmed PR-MVP-05 payment gate is not a receipt.

`payment_plan_installments` therefore carries no `paid_amount`, no
`balance_due`, no `receipt_id` and no `days_overdue`, and its `trigger_status`
closed set is `scheduled` / `awaiting_trigger` / `triggered` — states of the
trigger, never of payment. A construction-milestone instalment cannot hold an
actual due date while it awaits its trigger, and that is a database CHECK rather
than a service rule, because the service is one refactor from being bypassed and
the constraint is not.

`collections` carries the same sixth file for the same reason:

```text
app/modules/collections/
├── models.py
├── schemas.py
├── permissions.py    Collections records, Finance confirms, never the same person
├── ledger.py         aging arithmetic, derived status, restructure carry-forward
├── service.py
└── api.py
```

`ledger.py` takes `as_of` as a parameter and never reaches for today, which is
what makes "what was the aging on 31 August?" an answerable question rather than
a report somebody has to have snapshotted in advance. It has no branch that
reads `forecast_due_date` at all — a construction milestone whose expected date
passed three months ago is awaiting its trigger, not ninety days overdue, and
the absence of the branch is a stronger guarantee than a branch that declines to
take it.

`construction` carries seven files, and the seventh is the one worth naming:

```text
app/modules/construction/
├── models.py
├── schemas.py
├── permissions.py    preparer, technical, certifier, finance, checker, approver
├── calculator.py     the money arithmetic, with no session and no actor
├── service.py        the governed transitions and the locks that serialise them
├── read.py           response assembly: every derived figure, computed once
└── api.py
```

`read.py` exists because the alternative is worse. Seventy-two routes each
assembling their own totals is seventy-two chances for two screens to disagree
about what "certified to date" means on the same contract. Every derived figure
a construction response carries — a headroom, a waterfall, a variance, a
position — is built in exactly one function there, and the API layer only calls
it.

`unit_economics` carries a sixth file for the third time, and the pattern is now
the rule rather than a coincidence:

```text
app/modules/unit_economics/
├── models.py
├── schemas.py
├── permissions.py    Finance proposes, a second person approves, never the same one
├── calculator.py     allocation arithmetic, reconciliation, the profit layers
├── service.py
└── api.py
```

`calculator.py` has no session and no actor. It divides a pool across a set of
drivers so the parts sum to the whole **exactly** at the money column's scale —
with the rounding residual going to one deterministic recipient rather than being
spread, dropped or absorbed by whichever line came last — and it applies the
profit layers in one fixed order. A ratio whose denominator is not positive comes
back as nothing, never as zero: an undefined margin and a zero margin are
different facts, and only one of them is a number to act on.

Two things about that module are worth stating because they look like exceptions
and are not. **Allocations are stored** while every other total in this platform
is derived, because an allocation is not derivable twice: reproducing a
historical one would need the areas and prices as they were, and today's would
answer a different question. **Profit is not stored** — no `units.margin`, no
project totals table — because it is derivable from rows that are, and a stored
margin stops agreeing with its own inputs the first time one of them moves.

PR-MVP-07 adds a fourth truth to the three above:

```text
PR-MVP-07  Cash truth                  what arrived, where it went, what is left
```

and keeps it apart from the others with the same discipline. A *recorded*
receipt is a claim and moves no balance; only a Finance-confirmed one is cash. A
receipt is not an allocation, so cash that has arrived and not been applied is
reported as unapplied rather than absorbed. A refund is money leaving and has
its own table — never a negative receipt, because a signed amount would make
every `SUM` over receipts ambiguous and would misstate PR-MVP-10's cashflow the
day it is written.

Nothing in the module stores a balance. There is no `outstanding_amount`, no
`unapplied_amount` and no `project_total_overdue`: outstanding, unapplied, days
overdue, aging bucket and collection status are all computed from rows at read
time, because a stored total becomes the wrong one the first time a write path
forgets it.

### Inventory integrity

Membership is proved by the database, not by the service layer. Every level of
the hierarchy carries `UNIQUE (id, project_id)`, and every child points at its
parent with a composite foreign key:

```sql
FOREIGN KEY (building_id, project_id) REFERENCES buildings (id, project_id)
```

A floor therefore cannot be attached to a building in a different project, even
if a request supplies a valid identifier for each. The same pattern runs from
`Phase` down to `UnitAreaValue`.

Cross-row invariants that a CHECK cannot express are partial unique indexes:
one primary internal area type per project, one approved area schedule per unit,
one active custom-field definition per scope.

`Unit` deliberately carries no `phase_id` or `building_id`. A unit belongs to a
floor; its phase is reached through the floor and building. Denormalising it
would create a second answer to the same question, and the two would diverge.

### Authentication

Server-side opaque sessions, not JWT:

```text
Browser
  → same-origin FastAPI          (one service, one origin, no CORS)
  → HttpOnly SameSite=Strict cookie carrying a random token
  → SHA-256 digest of that token stored in PostgreSQL
  → authenticated User
```

The raw token exists only in the browser cookie. Passwords are hashed with
Argon2id. There is no permission table and no policy language: authorization is
explicit role checks against the eleven fixed system roles.

### Project access

`user_project_access` arrived in PR-MVP-02, keyed to a real `Project` with a real
foreign key. It answers exactly one question — may this user open this project —
and carries no role, no resource type and no permission string. Roles stay in the
fixed catalogue; a global role decides what someone may do *inside* a project,
never which projects exist for them.

A System Administrator reaches every project without a membership row. Everyone
else needs an active one, and a project they may not see reports **404** rather
than 403: a 403 would confirm that an identifier names something real.

### Phase access

PR-MVP-03 completed the narrowing PR-MVP-02 deferred. A membership row carries a
`phase_scope` of `all` or `selected`; a `selected` member sees only the phases
granted to them in `user_phase_access`, which points at a real `Phase` with a
real foreign key. Rows that existed before phases did default to `all`, so the
migration changes nobody's access.

Narrowing is applied in SQL, in one place, as a join from `Unit` through `Floor`
and `Building` to `phase_id` — never by fetching a project's inventory and
filtering it in Python. Anything beneath an ungranted phase answers **404**, on
reads and writes alike.

Only a System Administrator administers phase access. A Project Manager runs a
project; they do not decide who may see it.

### Configurable fields

Custom fields are metadata, not programming. A definition names a data type from
a fixed list, an optional option set, and where it applies; there is no formula,
no expression, no query and no executable content anywhere in the model. Values
are stored in three separate tables — one each for `Project`, `LandParcel` and
`Unit` — with real foreign keys, rather than one polymorphic
`entity_type`/`entity_id` table that no database constraint can protect.

A field may be marked sensitive and given the roles that may see it. That
filtering happens before serialisation, so a hidden field is absent from the API
response rather than hidden by the browser.

### Pricing

A **pricing configuration** is a project's governed commercial policy: the
internal rate, how each area type contributes, the premiums, the escalation
rules, the premium ceiling and the quote controls. It is versioned and follows
one lifecycle — draft, submitted, approved, active, superseded — and a partial
unique index allows exactly one active configuration per project. Approved is
not live; active is. The two are separate states because sanctioning a policy
and switching a development onto it are separate decisions.

A **unit price version** is one priced decision about one unit, frozen at the
moment it was made. It records the configuration, the approved area schedule,
the raw areas, the features, the sub-asset counts and the configurable values
the calculation saw. Nothing recalculates it afterwards: inventory keeps moving,
and the version does not. A price change is a new version; the one it replaces
is superseded and stays readable for ever. One active price per unit, again by
partial unique index.

The version's **effective date is a calculation input**, resolved once when the
price is generated and immutable from then on. It decides which escalations were
in force, so a date that could be edited afterwards — on the draft, or supplied
again at activation — would leave a price whose components describe one day and
whose row claims another. Changing the effective date means generating a new
version, and that date must fall inside the validity window of the configuration
that produced it.

What the version freezes is the **pricing basis**: the facts the arithmetic
reads. It is deliberately the same set inventory withdraws `pricing_approved`
for, plus the hierarchy premiums match on, the approved measurement, the priced
sub-assets and the configurable values. The unit's reference, number and asset
class are labels, kept in a separate descriptive snapshot for the auditor and
never compared — inventory does not treat renaming A-101 to A1-101 as a change
of unit, and a fingerprint that disagreed would refuse the very approval
inventory had just declared valid.

Every price is decomposed into **component lines** — the area, the rate, the
factor, the basis, what the rules produced and what a person overrode — and the
lines sum to the stored total exactly. A total that cannot be taken apart is the
spreadsheet cell this system exists to replace.

**Maker and checker are different people.** Finance, a Project Manager or an
administrator prepares; only an Approver / CFO approves and activates; and the
submitter may never approve their own work. A System Administrator deliberately
does not inherit financial approval: the ability to configure a system is not
the authority to sanction what it charges, and a role that silently contained
every other role would make the separation decorative.

**Activation is the only writer of `pricing_approved`.** The gate PR-MVP-03
created with no writer now has exactly one, and no button, PATCH or override
anywhere else. Inventory withdraws it again when a priced fact about the unit
changes — a floor, a feature code, an approved measurement, a linked parking
bay, a configurable value — so a unit whose basis has moved stops being
releasable until it is priced again. The historical price is never deleted: it
is what the unit was offered at.

Inventory does that withdrawal itself, because `pricing_approved` is an
inventory column. Pricing reads inventory; inventory does not import pricing,
and the one flag that spans them stays on the side that owns it rather than
buying a circular dependency.

**Escalation is configured here and activated by a person.** Only a date trigger
could be evaluated from data this system already holds; absorption, certified
construction progress and a market index belong to transactions that do not
exist until later PRs. Rather than fake those sources, an approver activates
against recorded evidence — and activation never reprices anything on its own.
It makes the escalation available to the *next* version generated, which is then
approved and activated like any other.

**Market comparison is one recorded observation, not a feed.** A benchmark is
entered by a person with a date, a source, an area basis and a tolerance; a unit
is compared against exactly one of them by a stated precedence (unit type in
this phase, then unit type, then phase, then project), and a second equally
specific active benchmark is refused. Currencies must match — there is no FX
table in this MVP, and a deviation computed across an ungoverned rate would look
like a fact.

The observation is **frozen into the version** rather than followed by
reference, and the classification is re-derived from the version's own final
amount whenever that amount moves — an override included. A "within tolerance"
chip beside a price a person pushed a third above the benchmark is a false
signal on the screen an approver decides from; and a benchmark revised next
quarter must not silently restate what last quarter's approver was shown.

**Configuration cannot silently mean nothing.** Every premium source is checked
against the same catalogue the units themselves are checked against, so a rule
naming a view class that was never configured is refused rather than saved and
never matched. A custom-field premium reads a boolean field or one named option
of an option field — the only two unambiguous readings — and any other data type
is refused, because "above three metres" is a comparison and a comparison is an
expression language. An escalation rule carries the fact its own trigger is
about and none of the others, in the service and in a CHECK constraint; a
sales-percentage escalation cannot be activated on evidence below its own
threshold. And `internal_base` may only name the project's actual internal area,
with a partial unique index behind the rule, because every "per internal area"
figure in the system divides by whatever that rule points at.

### Sales and legal

A **client** is a buyer, scoped to the project they are buying in. There is no
portfolio-wide customer master: deduplication, merge, consent scope and
cross-project visibility are real problems that deserve a PR about them, and
scoping to the project keeps the security question the one already answered
("can you see this project?"). The sensitive fields live on the **buyer
parties** rather than the client, so the commercial summary a project manager
needs can be served without the identity documents they do not.

Joint purchase is the ordinary case, so shares are a column. All active shares
must total exactly `1.000000` at the RATE scale before a unit can be committed:
two buyers at forty per cent each is a contract that sells eighty per cent of a
flat to nobody.

A **reservation** is the first persistent commercial commitment. It freezes the
quote pricing produced from the unit's live approved price — typed columns for
the figures somebody will be asked about, and the whole calculation beside them
in `quote_snapshot_json` so the waterfall is still explainable line by line in
two years. Nothing recalculates it after activation; that is what freezing
means. Recording or revising a commercial input re-runs the quote and withdraws
any approval that was standing, because an exception sanctioned against a
twelve per cent discount says nothing about a twenty per cent one.

A **sale contract** copies the reservation's frozen quote unchanged, and at
submission it also copies the buyer parties and the tax observation it was
agreed under into immutable snapshot rows. The client master will be corrected
later and a tax rate will move next quarter; a signed contract must keep saying
what it said.

**A commitment is exclusive, and the unit row decides it.** One live
reservation and one live contract per unit, and never one of each: the invariant
spans two tables and is serialised through the single unit row every operation
takes `FOR UPDATE` before deciding. Partial unique indexes on `status IN
('active','extended')` and `status IN ('signature_pending','active',
'termination_pending')` are the backstop, not the mechanism.

**A price lock is a promise, and the two questions it raises are different.**
Before a reservation commits anything, the quote it holds must still be the
price the unit is offered at: a draft cut from a superseded version is not
something to hold a flat with. Once it has committed, that question stops
mattering and another takes its place. Finance putting a new list price live the
following Wednesday is commercial repricing — it decides what the unit is
offered at tomorrow, and says nothing about what this buyer already agreed.
Refusing the contract because the frozen version is no longer today's active
price would make the lock mean nothing.

What still blocks the contract is the unit ceasing to be the unit. Pricing owns
the comparison of a version's frozen basis against current inventory, and
exposes it as one read-only public contract; a locked price is not permission to
sell a materially different flat under last month's geometry.

**An expired lock has one explicit way out.** A live reservation whose lock has
run out cannot proceed to contract and cannot be edited either — a real position
with no exit except cancelling a genuine commitment or silently repricing the
buyer, which is the thing the lock exists to prevent. `requote_reservation` is
the third option: the same buyer, the same unit, the same recorded adjustments,
re-run against today's approved price, on the record with a reason. The unit
stays reserved and the standing approval is withdrawn, because an exception
sanctioned against last month's number says nothing about this month's. It is
the only route to a committed reservation's commercial terms; everything else
about them stays frozen.

**A transition cannot be dated later than it happened.** Every sales operation
changes current state the moment it runs, so an effective date in the future
would produce a unit contracted today whose own history says the contract begins
next week. Backdating stays allowed where the chronology rules permit it. There
is no scheduler and no pending status here, so a future date is not a promise
this module could keep, and it is refused rather than accepted.

**Sales never writes another module's columns.** Unit status moves through
inventory's `apply_sales_commercial_status`, `apply_legal_status` and
`apply_delivery_status` — non-committing contracts that validate the transition,
record the status event and write the audit entry, leaving the transaction
boundary to the caller. Prices come from pricing's quote service, and codes are
validated by settings. Nothing in `sales/` reads another domain's tables and
forms a second opinion about its state.

**The legal timeline is append-only.** Fourteen canonical milestones, a small
explicit prerequisite map, and no route that edits or deletes an event. A
mistake is corrected by another dated, attributed event carrying
`reverses_event_id`; both rows stay, and the unit's legal status is derived from
whichever events still stand. "We believed the title had transferred until the
14th" is itself a fact somebody will need.

The reversal key carries the sale and the project alongside the identifier.
Pointing at an identifier alone would prove only that some event exists
somewhere; a legal record should not depend on the service for something
PostgreSQL can express, so a correction that reaches across contracts is refused
by the database.

**Approval is two role checks and a comparison.** A quote breaches the country's
configured thresholds or it does not; if it does, exactly one office may
sanction it, the person who submitted it may not be the person who approves it,
and a System Administrator is not that office. There is no approval engine, no
rule table and nothing configurable about who signs.

**A gate is an attestation, not a receipt.** A confirmed deposit and a confirmed
first payment record that a named person saw evidence, with a reference to it.
They are never counted as cash: PR-MVP-07 owns receipts, and the naming here —
in the columns, the API and the interface copy — is chosen so the two cannot be
confused.

**A cancelled unit comes back as `returned`, not `available`.** Between "we are
cancelling" and "the unit is back" sit a money decision the CFO signs and, where
the registry is involved, a recorded withdrawal. The unit's pricing approval is
withdrawn on the way through, so somebody has to price it again and pass
inventory's release gate before the next buyer sees it.

**Handover needs three departments' answers.** Legal clears legal, Collections
clears collections, and delivery belongs to the people who built the thing;
Sales Operations completes the handover and signs none of the three. Which
clearances apply is the project's own configuration — six named booleans in
`sales_project_policies`, not a condition language that could express anything
and be audited for nothing.

### Construction control

**Six separate truths, and none of them is derived from another.** What was
authorised (budget), what was signed (commitment), what was formally certified
as done (certification), what the vendor claims (invoice), what has left the
bank (payment) and what it will finish at (forecast). A single "spent" figure
would have to pick one and hide the other five, and every one of them is the
right answer to a different person's question.

**A forecast's cutoff is the formal certification, never the certificate's own
date.** A valuation dated 31 August is signed off on 5 September, because
somebody has to read it first, and a forecast taken as at 31 August could not
have contained work nobody had certified yet. Cutting off on the document date
would let a backdated form enlarge a forecast months after Finance approved it,
which is the opposite of what naming an as-of date is for. One helper states the
bound — the first instant after the cutoff, in UTC — and both readers use it, so
"as at" cannot come to mean two things in one module.

**Certified to date is today's figure; the estimate at completion is not.** The
first answers "what has been certified?" and must move the moment a certificate
is signed. The second is the standing forecast's answer, and it stays on the
basis that forecast was approved against: the work certified by its own cutoff
plus what it said was still to come. Refreshing the certified half of a
completion estimate while leaving the remainder alone counts the new work twice,
so the frozen basis is carried beside the live one rather than left to be
inferred by subtraction.

**A historical basis is read from timestamps, never from today's status.** A
certificate certified on 20 August and withdrawn on 15 September *was* certified
on 31 August, and the forecast taken as at 31 August was approved with it
inside. Asking the status column would delete it from that basis retrospectively
and move an estimate somebody signed, so a historical cutoff asks the two facts
that cannot change — it had been certified by the cutoff, and it had not yet been
reversed by it. The live position still asks the status column, because "what has
been certified?" is a question about now and a withdrawn certificate is not an
answer to it. One predicate holds both readings so the forecast basis and the
unit-economics cost basis cannot disagree about the same date.

**A forecast is measured against an authorisation somebody actually gave.** A
draft budget is a working paper, a submitted one is a question, and a rejected
one is a refusal; none of the three can be the denominator of a variance.
Approved, active and superseded can — a replaced authorisation was still an
authorisation, and refusing it would make every forecast unreadable the moment
the next budget was activated. The check is re-proved at submission and at
activation rather than trusted from when the draft was opened.

**A contract line carries only what that line owns.** Two lines may name one
cost code, and nothing in the model allocates a variation or a certificate back
to one line rather than the other, because no such business rule exists: a
variation moves a cost code and certification is valued against a cost code. A
line-level "revised commitment" could therefore only be the code's total,
repeated — two lines each showing 650,000 read as 1,300,000 committed. Those
figures are reported once, at the cost-code grain that owns them.

**Cost is stated excluding tax; cash is stated including it.** The two never
share a row or a heading. Tax is recoverable in most of the jurisdictions this
product serves, so a cost figure carrying it overstates the build — and a screen
that put certified-ex-tax beside paid-including-tax would invite a subtraction
whose answer means nothing.

**A positive variance at completion is over budget.** One convention,
everywhere, derived on the server and never re-derived in the browser. The sign
is the single easiest thing in this module to get backwards, and a screen that
reversed it would print an overrun in the colour the rest of the product uses
for good news.

**Retention and advance are cash timing, never cost reductions.** Retention
withheld does not reduce what the work cost; it delays when the money moves. A
release can only ever come out of retention actually held, and an advance can
only be recovered against advance cash actually paid — money that never left the
bank cannot be taken back out of a valuation.

**Status never moves money.** Terminating a contract does not remove its
commitment; a variation does. Disputing an invoice does not reduce what is owed;
it blocks payment while the argument runs. An obligation that vanished the
moment somebody objected to it would make the ledger a record of opinions.

**A maker is never the checker, by identifier.** Budget, contract, variation,
certificate, invoice and payment each have two people, and the second is
compared by user id rather than by role: a user holding both Finance and
Approver / CFO is still one pair of eyes. The System Administrator reads
everything and signs nothing.

**A partial view of a project total is refused, not filtered.** A phase-scoped
reader who opened a budget would be shown "the project's budget" with the hidden
phases quietly removed — a number that is neither the project's nor their own,
with nothing on screen to say so. Every whole-project financial surface requires
whole-project access; the technical records that genuinely belong to one phase
stay available.

**And a technical record reaches only the phases it belongs to.** That is the
other half of the same rule, and the half with teeth: milestones are addressed by
identifier and certifying one makes buyers' instalments fall due, so a register
that filtered on ``project_id`` alone would let a Phase A engineer reach a Phase B
milestone by supplying its id — not a display bug but an unauthorised financial
act one request away. The narrowing is in the SQL, in one predicate the register,
the lookup, the dependency edges and the payment-plan trigger options all share;
a hidden record answers 404 rather than 403, because a refusal that confirms the
identifier is real is itself the disclosure. A milestone scoped to neither a phase
nor a building belongs to the whole development, and needs whole-project access to
create, widen into, or certify.

**Nothing is deletable.** Governed history is superseded, reversed, voided or
withdrawn — each with a reason on the record. There is no DELETE route anywhere
in the module.

### Cashflow and management reporting

**Cashflow consolidates cash it does not own.** Payment plans owns what a buyer
is scheduled to pay, collections owns what arrived, construction owns what was
paid to contractors, sales owns the contract. Not one of those rows is copied
here; they are read through named contracts each source module publishes, and
the source modules import nothing of cashflow. What this module owns outright is
the cash nothing else records — consultants, permits, insurance, equity, debt —
and the governed statement of when Finance expects the rest of it to move.

```text
  payment_plans.cashflow_schedule_rows            instalments of the schedules
                                                  governing at a stated cutoff
  payment_plans.cashflow_governing_version_ids    which plan versions those were
  collections.cashflow_receipt_rows               confirmed buyer cash, gross
  collections.cashflow_refund_rows                confirmed money returned
  collections.cashflow_unapplied_cash             confirmed cash not yet applied
  construction.cashflow_payment_rows              confirmed construction cash
  construction.cashflow_forecast_position         remaining cost by cost code
```

**Six different cash questions, and none of them collapses into another.** What
the schedules say becomes due; what Finance expects to collect; what actually
arrived; how much of it is restricted; what has actually been spent; and what is
expected to be spent. A single "cash" figure would have to pick one and hide the
other five.

**Nothing becomes cash except a cash transaction.** A land valuation, a
construction certificate, an approved invoice, a unit's cost allocation and a
buyer's instalment are none of them evidence that money moved. Recording a
movement is a claim; a second person confirming it is the cash.

**Received and usable are different balances.** A restriction takes buyer money
out of the spendable pool without taking it out of the bank, and a release puts
it back — availability moves, project cash does not. Reporting a release as an
inflow, which is tempting because it makes usable cash rise, would show the
project collecting the same money twice. The funding gap is measured on
unrestricted cash, because escrowed buyer money cannot pay a contractor.

**Cash arrives once.** A confirmed receipt is already counted as cash that
arrived. If the instalments it will eventually be applied to also stay in the
forward forecast at full value, the same money is counted twice — so the forecast
offsets confirmed unapplied cash against the remaining schedule, deterministically
and for forecast purposes only. Nothing is written and no allocation is created:
the operator's filing backlog is theirs, and a forecast is not permitted to clear
it with an accounting entry.

**A governed forecast pins its sources and stays reproducible.** It names the
construction forecast whose remaining cost it schedules and freezes the buyer
schedule it was built on, and both are re-proved at submission and again at
activation. A source that moved makes the version stale and it is refused, never
silently rebased: substituting a newer source under an approver changes what they
are approving, and the newer source being more accurate does not make the
substitution honest.

**The construction schedule reconciles exactly, and coverage is asked
separately.** Construction says how much is left on each cost code; cashflow says
when. If the months do not total the remaining cost, the two documents disagree
about the project and a tolerance would be a decision to stop noticing by how
much. Whether a code appears at all is a *different* question from whether its
months add up, and it has to be asked on its own: reading an absent code as a
schedule of zero agrees exactly with a code that has nothing left to spend, so a
build with one fully certified trade and one entirely forgotten trade reconciles
green either way. An explicit zero is a preparer's decision; a missing cost code
is nobody's.

**Buyer cash that cannot be placed in a month blocks governance.** An instalment
with no contractual, forecast or actual date is not an instalment worth nothing —
the money is contractually owed and the snapshot simply has no month to put it
in. Inventing one would place cash on no evidence, so it is left out and the
version is silently short of it. That gap is a refusal at submission and again at
activation, naming the instalments, rather than a note somebody may read.

**A month is one of three things, never one of two.** A closed month is settled
history and reports its actuals. A future month is expectation and reports its
forecast. The month a report is taken in is *both* — cash that has moved, plus
what is still expected before it ends — and it says so, as
`basis = actual_and_forecast`. Reporting it as actual-only produces a real number
made of real transactions that omits every payment still due, so a project read
on the third of the month shows a funding cliff that disappears on the fourth.
One rule decides which rows belong: a dated forecast row answers on its own date,
a month-grained forecast line for the current month is the remainder of that
month, and the same rule serves the bridge, the funding windows, the drill-down,
the NPV and the equity IRR. Returns does not get a second interpretation — a
project whose bridge and whose IRR disagree about what is actual has two answers
and no way to tell which one a decision was taken on.

**An opening balance is a statement about one moment, and the series begins
there.** The transactions of the months before it are not additional to it; they
are what produced it. Running the bridge backwards from a governed opening
balance replays them through a figure that already contains them, and the error
grows with how much history a project has — so the oldest and most valuable
projects would report the worst numbers. A request for a month before the anchor
is refused with the anchor named; the pre-opening transactions stay in the
drill-down and in the modules that own them.

**A funding requirement starts from the money in the bank and reads the worst
point, not the last one.** Each 30/60/90-day window opens on the *unrestricted*
cash actually held at the cutoff, projects movements through the literal date
window a day at a time, and reports the deepest trough inside it. Netting
expected inflows against expected outflows without the opening balance tells a
project sitting on ten million that it must raise five; reading the closing
position instead of the trough tells a company that a payment on day ten funded
by a receipt on day twenty is affordable.

**An escrow cannot outlive the transfer behind it.** A restriction is a claim
over one receipt and stands exactly as long as that receipt does. Left standing
over a reversed receipt it subtracts its own amount from a balance that no longer
exists, and the harm doubles: the reversal removes the cash, and the escrow goes
on holding a share of what is left. Both are asked of the same cutoff — a receipt
confirmed in August and reversed in September *was* cash in August, and the
escrow over it *was* holding it. The escrow's own record answers the same way as
the cash report: `counts_as_restricted` needs the receipt as well as the
confirmation, and a release needs the whole chain above it, so the register and
the position cannot say different things about one amount of money. What is
never rewritten is the persisted status — the restriction really was confirmed —
which is why the reconciliation goes on naming it as a correction somebody owes.

**A hand-written forecast is not exempt from cash happening once.** The platform
already enforces this for buyer receipts: money that arrived leaves the forward
schedule by exactly its amount. A forecast line is the same. A September line of
1,000,000 is the spend expected *for September, at the moment the forecast was
cut*; pay 300,000 of it on the 10th and a live report is 300,000 gone and 700,000
to go, never 300,000 and 1,000,000 — which claims 1,300,000 on no evidence, and
lands the error on the funding requirement. Matching is by grain and never looser:
construction at the cost code the certificate attributes the payment to,
development at the category and at the phase where the line names one, financing
at the movement type and its direction. Cash that moved *before* the cutoff is
already inside the figure and is not subtracted twice. A remainder never goes
negative: spending more than was forecast does not create expected cash, and the
overrun belongs to the accuracy report rather than to a forecast that quietly
grew to absorb it. The governed line is untouched throughout — the forecast file
still states what was approved, because that is what accuracy is measured
against.

**A forecast opens in the month it was taken in.** The opening balances are cash
held at the start of the horizon, and every report rolls them forward through what
has moved since. A horizon opening in a *later* month would state a balance for a
month that has not happened while the current position quoted it as money in the
bank today; one opening *earlier* would leave a stretch of unexamined history
between the balance and the cutoff. Requiring the start month to be the as-of
date's month removes both without a second date field to keep in step, and gives
the current month its three clean terms: opening balance, month-to-date actual,
and the forecast remainder still ahead.

**Return states its basis.** Project NPV discounts operating and development
cash and excludes every financing flow, because equity is how a project was
funded and not what it earned. Equity IRR uses the investor's signs, reversed
from the project's — feeding project-direction cash into an IRR gives the right
magnitude with the wrong sign. IRR refuses with a named reason rather than
answering 0%, 999% or NaN, and never appears without absolute figures beside it.

**Bank cash is project cash.** There is no per-phase account, so a phase-scoped
reader is refused every project cash surface rather than shown a filtered total —
any per-phase balance would be an allocation the business does not have.

### Deferred by design

**Company-scoped custom fields wait for a Company entity.** A definition may be
scoped to a country pack, a project or a unit type. Inventing a Company table to
satisfy a scope label would be the abstraction-first mistake this rebuild exists
to avoid.

**Unit cost, margin and profitability wait for PR-MVP-08.** PR-MVP-04 builds the
complete revenue side and stops. Combining an approved price with a governed
cost allocation is what produces a margin; doing it before those allocations
exist would mean inventing the cost, and an invented cost inside a real margin
is worse than no margin at all.

**The quote preview creates nothing.** No client, no reservation, no sale, no
stored exception — it is arithmetic on a screen. What it does insist on is the
distinction a spreadsheet always loses: a *price concession* reduces what the
buyer contracts to pay, and a *seller cost* does not. A furniture package the
seller absorbs leaves the contract price where it is and reduces net revenue.
PR-MVP-05 owns the transaction that freezes it, and carries that distinction
into the contract snapshot intact.

**The payment plan, the receipt and the refund wait for their own PRs.** A
reservation and a contract carry the terms that were agreed. Scheduling the
money is PR-MVP-06, collecting it is PR-MVP-07, and a refund actually paid is a
payment transaction that belongs there — which is why a cancellation records a
refund *due* and has no field in which to claim one was made.

No construction or cashflow domain exists. PR-MVP-08's hard-cost pool is an
economic forecast allocation input and says so on screen; the budget baseline,
cost codes, contracts, certificates and payments are PR-MVP-09's, and when they
arrive they may supply a *new* allocation version rather than rewriting an old
one. Domains arrive on the schedule in [MVP_ROADMAP.md](MVP_ROADMAP.md).

---

## 8. Governing principles

- **Stable identifiers.** Core entities carry surrogate keys. Human-readable
  references (project code, unit number, SPA number, receipt reference) are
  separate attributes, never identity.
- **Separate status dimensions.** Commercial, legal, collection and delivery
  statuses are distinct fields, never collapsed into one `status` column.
- **Configuration over hard-coded market rules.** Country, currency, tax and
  threshold behaviour is data, not `if country == "AE"`.
- **Rows and events over repeated financial columns.** Never
  `installment_1_amount, installment_2_amount, …`.
- **Effective-dated financial versions.** Prices, plans and allocations are
  versioned with validity, not overwritten.
- **Baseline / forecast / commitment / actual stay distinct.** Four different
  facts, four different fields.
- **Drill-down from every KPI to source transactions.** No number exists that a
  user cannot trace to the rows behind it.
- **Country-aware configuration.** Multi-country from the data model outward.
- **Auditability.** Financial and legal records are voided, cancelled, reversed
  or superseded — with user, timestamp and reason — never physically deleted.
- **Reconciliation before reporting.** A report that has not been reconciled is
  not a report.

---

## 9. Deliberate non-architecture

The following are **not** part of this system and must not be introduced without
a concrete operational need and explicit approval:

microservices · Redis · Celery · Kafka · message queues · event buses · service
meshes · GraphQL · separate frontend hosting · separate calculation services ·
multiple databases · data warehouses · vector databases · background-worker
infrastructure · generic workflow engines · rules engines · strategy engines ·
scenario engines · AI subsystems · generic plugin architecture · abstract event
sourcing · CQRS · Kubernetes.

The previous application became substantially overengineered. The rebuild does
not repeat that.
