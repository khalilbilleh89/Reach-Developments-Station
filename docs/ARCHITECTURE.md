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

Reading another domain's rows is ordinary and done directly. Writing them is
not, and there is no path in collections or unit economics that does.

---

## 7. Current state (through PR-MVP-08)

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
