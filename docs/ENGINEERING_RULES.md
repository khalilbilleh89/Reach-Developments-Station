# Engineering Rules — Reach Developments Station

Permanent engineering policy for MVP 1.0. **Every future PR must reference this
file.** Rules here are not suggestions; changing one is a reviewed decision, not
a drive-by edit.

Every record-creating feature must implement its deletion flow in the same change.
The mandatory checklist and retained-history rules are in [DELETION_POLICY.md](DELETION_POLICY.md).
This applies to configuration choices and child rows as well as primary records.

Record workflows must use full pages. Side drawers and side inspectors are prohibited,
including on mobile. Small centered confirmations and short forms remain allowed.
See [UX_PAGE_AUDIT.md](UX_PAGE_AUDIT.md) for the audited flows and acceptance checks.

---

## 1. Anti-overengineering constitution

Use a **modular monolith**.

Forbidden unless a later PR provides a concrete operational need and explicit
approval:

microservices · Redis · Celery · Kafka · message queues · event buses · service
meshes · GraphQL · separate frontend hosting · separate calculation services ·
multiple databases · data warehouses · vector databases · background-worker
infrastructure · generic workflow engines · rules engines · strategy engines ·
scenario engines · AI subsystems · generic plugin architecture · abstract event
sourcing · CQRS · Kubernetes.

**Do not create infrastructure for hypothetical future requirements.**

Governing principle:

> Build the smallest system that correctly represents the real business.
> Optimise for correctness → traceability → usability → maintainability →
> simplicity.

---

## 2. Dependency policy

Dependencies are liabilities until proven useful.

### Backend

`requirements.txt` and `requirements-dev.txt` are the canonical, exactly pinned
source of truth. `pyproject.toml` carries tooling configuration only.

Current production set — FastAPI, Uvicorn, SQLAlchemy, Alembic, Psycopg 3,
Pydantic Settings — and nothing else.

Do not introduce ORM wrappers, dependency-injection frameworks, generic
repository frameworks, task queues, caching libraries, financial calculation
libraries, pandas, numpy, authentication frameworks, permission libraries,
logging platforms or monitoring SaaS SDKs unless the PR at hand actually
requires them.

### Frontend

The normal Next.js / React / TypeScript toolchain, and nothing else.
`package-lock.json` is committed.

Do not add Axios, Redux, Zustand, MobX, React Query, chart libraries, component
frameworks, form libraries, validation libraries, date libraries, icon libraries
or animation libraries until native `fetch`, React and browser capabilities have
demonstrably failed.

### Every PR must declare

```text
Production Dependencies Added:
Development Dependencies Added:
Dependencies Removed:
Why each new dependency is necessary:
Why existing framework/native functionality is insufficient:
```

Default expectation: `Production Dependencies Added: None`.

Unused dependencies are forbidden. `pip check` runs in CI.

---

## 3. Module boundaries

```text
app/core
   ↑
domain modules
   ↑
API composition
```

- `app/core` must never import a business domain.
- A domain must not manipulate another domain's persistence internals. Call a
  small public service contract instead.
- Create that contract when the interaction appears — not in advance.
- No circular imports.

A domain normally starts as `models.py`, `schemas.py`, `service.py`, `api.py`.
`repository.py` is optional: add it only for meaningful persistence complexity
or genuinely reusable query logic.

Do not introduce generic base services or repositories until repeated code
proves they are necessary.

---

## 4. Backend clean-code rules

- Explicit Python typing for public functions.
- Small, cohesive modules.
- Domain logic must not live in route handlers. Handlers validate, authorize and
  orchestrate only.
- No business calculations in Pydantic schemas.
- No global mutable application state.
- No hidden database writes.
- Transaction boundaries must be explicit. Sessions do not autocommit and do not
  autoflush; services commit or roll back deliberately.
- No `Base.metadata.create_all()` for production schema management.
- All schema changes go through Alembic.
- Database constraints should protect critical invariants.
- Keep constraint names short. PostgreSQL truncates identifiers at 63
  characters, and a truncated name no longer matches the metadata, so
  autogenerate reports drift for ever afterwards.
- Load a record scoped by its owner, never by its own identifier alone.
  `select(Child).where(Child.id == child_id, Child.parent_id == parent_id)` is
  what stops one tenant's identifier being substituted into another's path;
  fetching by primary key and checking the parent afterwards is the shape that
  lets it through.
- A row-level access rule belongs in the SQL that selects the rows. Fetching
  everything and filtering in Python puts data the caller may not see into
  memory, into the query plan, and one refactor away from the response.
- An invariant a database constraint cannot express (one that spans rows, such
  as "no two active tax rules for a code overlap") is decided by reading and
  then writing, which two concurrent transactions can both win. Lock the row
  that owns the invariant — `select(Owner).where(...).with_for_update()` — before
  the read, and hold it through the write and commit. Pick the narrowest owner
  the check never looks past; a row lock is the tool, not a queue, a cache or an
  advisory-lock scheme.
- A `with_for_update()` query needs `.execution_options(populate_existing=True)`
  to be worth taking. Without it SQLAlchemy takes the lock and then returns the
  copy already in the identity map, so the decision is still made against the
  stale read the lock existed to prevent.
- Take locks in one order across the whole codebase — currently project, then
  permit. PostgreSQL takes a key-share lock on the parent row when a child row
  writes a foreign key, so a path that locked the child first would deadlock
  against one doing the reverse. A new lock joins the order; it does not start
  its own.
- A guard is only as safe as the writes it guards against. If a rule reads
  "this may not change once X exists", the write that first establishes X must
  take the same lock the rule does — otherwise the guard can read "no X yet"
  while another transaction is committing the first one. Lock on the field
  being named, not on whether it is currently null: the case analysis is where
  the hole comes back.
- Declare a uniqueness rule exactly once. `unique=True` on a column *and* a
  `UniqueConstraint` over the same column is two declarations of one rule:
  PostgreSQL silently keeps whichever it reads first, so the surviving name is
  not the one the convention promised and autogenerate then sees drift.
- Avoid unnecessary inheritance; prefer composition over framework abstractions.
- Exactly one engine and one session factory per process, both in
  `app/core/database.py`. No module creates its own engine.

---

## 5. Frontend clean-code rules

- Business calculations belong in backend services. The frontend renders backend
  truth.
- API access must be centralised under `frontend/src/lib/api/`. Do not call
  backend URLs from arbitrary components. *(This directory does not exist yet:
  PR-MVP-00 has no data screens. It is created by the first PR that calls an
  API.)*
- TypeScript `any` requires written justification.
- No duplicate domain types across pages.
- Components have one clear responsibility. No giant all-purpose page components.
- No global state library until local/context state demonstrably fails.
- Accessibility basics are mandatory: semantic elements, labelled controls,
  visible focus, sensible heading order, adequate contrast.
- Responsive layout is mandatory.
- Loading, error and empty states are mandatory once real APIs exist.

---

## 6. Money, rates, dates and data modelling

### Money

**Never use floating-point values for money.**

- Database: PostgreSQL `NUMERIC` with precision appropriate to multi-currency
  real-estate transactions.
- Python: `decimal.Decimal`.
- Never `float`, never `REAL`, never `DOUBLE PRECISION`.

### Rates and percentages

Rates must carry explicit scale and units. A bare `5` is forbidden, because it
does not say whether it means `5%`, `0.05`, or 5 basis points. Name and document
the unit in both the column and the schema.

### Dates

- Persist timestamps in **UTC**.
- Business dates — contract date, due date, permit date, handover date — stay
  date-based where time of day is irrelevant.

### Stable identity

Core entities use stable surrogate identifiers. Human-readable references —
project code, unit number, SPA number, receipt reference — are separate
attributes and never identity.

### Transactions over repeated columns

Model installments, receipts, allocations, price versions, certificates,
payments, approvals and status changes as **rows/events**.

Never:

```text
installment_1_amount
installment_2_amount
installment_3_amount
```

### Separate status dimensions

Commercial, legal, collection and delivery status are four columns. They are
never collapsed into one `status`, and never derived from one another: a unit can
be contracted, registered, overdue and under construction at the same time, and
each of those facts belongs to a different team.

Each dimension has exactly one owner, and the owner is the module that can
answer for it. Inventory owns the four columns and the append-only events behind
them; the domain that knows the facts decides the value and asks inventory to
apply it, through a named contract and never by writing the column. From
PR-MVP-07 the collection dimension is driven by the receipts ledger, so a unit
can no longer read `cleared` beside a balance that is outstanding.

### Cash is not a schedule, and a claim is not cash

Three records, three meanings, and merging any two of them loses a fact
somebody is accountable for:

- a **contract** says what was agreed;
- a **schedule** says what is due and when;
- a **receipt** says money arrived — and only once somebody independent of the
  person who recorded it has confirmed that it did.

Money leaving is its own record, never a negative row in the record for money
arriving: a signed amount makes every total over that table ambiguous.

Applying cash to an obligation is a separate decision from receiving it, made by
a person and reversible. Cash that has arrived and has not been applied is
reported, not absorbed — an unapplied balance is somebody's money sitting in the
company's account, and the system that hides it is the system that discovers it
years later when the buyer asks.

Status changes are recorded as append-only events with actor, timestamp and —
where the transition is a reversal or a cancellation — a reason.

### Configurable fields are metadata, not programming

A configurable field names a data type from a fixed list, an optional option set
and where it applies. It never carries an executable formula, JavaScript, Python,
SQL, an expression, a lookup query, arbitrary JSON or rich text that something
later evaluates. If a requirement needs computation, it needs code and a
migration, not a field.

Values are stored per entity in real tables with real foreign keys — never one
polymorphic `entity_type`/`entity_id` table that no constraint can protect.

### Derived values are derived

A number the system can compute is computed, not stored as independent truth and
not made editable. A weighted area, a completeness percentage or a total that a
user can type is a number that will disagree with its own inputs.

### Financial and legal deletion

Financial and legal transactions are **not physically deleted** during normal
operations. Use controlled `void`, `cancel`, `reverse` or `supersede` operations,
each recording user, timestamp and reason.

The owner-approved, explicitly confirmed purge of a removed unit's closed linked
history is the narrow exception described in `DELETION_POLICY.md`. Its dedicated
maintenance operation may delete the listed domains' owned rows in one transaction;
ordinary domain services and deletion workflows keep the rules above.

---

## 7. API conventions

`/api/v1` is reserved. All JSON APIs live beneath it.

Conventional REST semantics:

```text
GET    /api/v1/projects
POST   /api/v1/projects
GET    /api/v1/projects/{project_id}
PATCH  /api/v1/projects/{project_id}
```

- Do not invent RPC-style endpoints when resource semantics work.
- `PATCH` bodies are read with `exclude_unset=True`, so an absent key and an
  explicit `null` are different requests and must stay different all the way
  into the service: absent leaves the column alone, `null` clears it. A `null`
  aimed at a column that cannot hold one is a `422`, never a silent `200` that
  changed nothing. When a cleared value feeds a validation rule, re-run that
  rule against the values the row will actually hold.
- Do not return database objects directly. Pydantic response schemas define the
  public contract.
- Do not leak raw exception strings, stack traces, connection strings, hostnames
  or credentials to clients.

### Error responses

One shape, everywhere — FastAPI's native error body:

```json
{ "detail": "Human-readable, non-sensitive message." }
```

- `4xx` — raise `HTTPException` with a safe `detail`.
- `404` — the whole `/api/v1` namespace is reserved by a catch-all registered
  after every router and before the static mount. An unmatched API path returns
  `{"detail": "Not Found."}`, never the frontend's 404 HTML page. Any new router
  must be included *before* that guard.

  A known consequence: the guard matches every method, so calling an existing
  path with an unsupported method returns `404` rather than `405`. Both are the
  JSON contract, and the alternative is HTML leaking out of the namespace, so
  the trade is deliberate.
- `422` — FastAPI's request validation body, unchanged.
- `5xx` — the global handler in `app/main.py` returns
  `{"detail": "Internal server error."}` and logs the full exception
  server-side.

Diagnostics belong in server logs. Clients get facts they are entitled to.

> **Deferred:** interactive API docs (`/docs`, `/redoc`) are currently public.
> That is acceptable while the API exposes only health probes. PR-MVP-01
> introduces authentication and must revisit docs exposure at the same time.

---

## 8. Migration rules

- Fresh history, rooted at `0000_mvp_baseline`. No V1 migration is ever copied
  in.
- All schema changes go through Alembic. Never `create_all()` at startup.
- Migrations run at **deploy start**, not at build (see
  [DEPLOYMENT.md](DEPLOYMENT.md)).
- The database URL comes from `app.core.config`. `alembic.ini` carries no
  `sqlalchemy.url`.
- Revision ids are explicit and ordered:

  ```bash
  alembic revision -m "add project tables" --rev-id "0001_project_land"
  ```

- Every migration must be tested forward **and** backward before merge.
- Destructive changes must be called out in the PR and must state a rollback
  procedure.
- **Never edit a revision that has already shipped to production.** Revisions
  through `0002_project_land_permits` are deployed; from there migrations are
  incremental, and a correction is a new revision, never a rewrite of an old one.
- A migration changes only what its PR is for. `alembic revision --autogenerate`
  will happily fold in unrelated drift it noticed elsewhere in the schema —
  read the generated file and delete anything that is not this change.
- **CI runs `alembic check` after `alembic upgrade head`** and fails when the
  models and the migrated schema disagree. It never generates a revision
  automatically: a drift report is a request to write a migration, not a licence
  for CI to invent one. When drift is a naming difference, rename the constraint
  in place — `ALTER TABLE … RENAME CONSTRAINT` — rather than dropping and
  recreating it.

---

## 9. Security baseline

- No secret is ever committed. `.env.example` holds placeholders only.
- `DATABASE_URL` is required in production; there is no production default.
- `APP_DEBUG` must be false in production. Configuration refuses to start
  otherwise.
- Health and error responses never expose hostnames, usernames, passwords,
  connection strings or stack traces.
- CI uses a throwaway PostgreSQL service container and never points at Render
  production PostgreSQL.
- Row-level narrowing is applied **in SQL**, never by fetching everything and
  filtering in Python. A filter parameter can only narrow what a caller may
  already see; it can never widen it.
- A record a caller may not see answers **404**, never 403. A 403 confirms that
  an identifier names something real, which is precisely what an enumerator
  wants.
- Field-level visibility is applied **before serialisation**. A field hidden
  from a role is absent from the response body, not hidden by the browser.

---

## 10. Testing expectations

Tests protect business behaviour, not implementation trivia.

- Prefer `Given / When / Then` against real real-estate workflows.
- Avoid tests whose only purpose is asserting that a mocked method was called.
- There is **no coverage target**. Coverage percentage is not a product goal.
- High-risk financial and transactional logic receives deeper coverage than
  trivial display components.
- Database tests fail loudly when PostgreSQL is unavailable. They never skip
  silently — a skipped database test in CI is worse than a red build.
- Warnings are errors (`filterwarnings = ["error"]`). A new deprecation is a
  task, not background noise.

---

## 10a. Risk-based module CI

CI scope is determined by code risk, not pull-request size or Draft/Ready state.
The required statuses remain **PR Quality**, **Backend**, and **Frontend**.

- **Module:** one changed product domain, the invariant pack, that domain's
  tests, and direct consumer tests/contracts.
- **Cross-domain:** every intentionally changed domain plus each one's direct
  consumers and cross-domain contracts. Selection is one hop, not transitive.
- **System:** foundational core, access, database/session, dependency, pytest,
  migration-environment, or shared test-harness behavior. Complete regression
  is required and may use the eight-way shard helper.

An ordinary migration runs migration graph/convergence, upgrade-to-head, drift,
canonical intake, deletion/retention and changed-domain checks. It does not by
itself mean System. A change to `app/db/migrations/env.py` does.

An unregistered `app/modules/<name>/` path fails the plan immediately with the
registration required in `scripts/ci_backend_tests.py`; it does not silently
spend a Full run. Routine module registration in `app/main.py` is not System.

The required Backend aggregate always reports. Docs-only and frontend-only
changes take its no-backend success path without PostgreSQL. Main pushes use the
same plan over the merged before/after diff. Newer runs cancel obsolete work for
the same PR. Frontend remains always-on and includes lint, its complete tests,
and production build.

`.github/workflows/full-backend-shadow.yml` provides an explicit complete suite
for manual dispatch or the `ci:full` label. It publishes JUnit, logs, totals,
duration and slowest tests, remains visibly red on failure, and is not a required
Backend dependency. Agents never add `ci:full` merely to be safe; they explain
the blast radius that warrants it.

Ordinary Backend targets at most ten minutes, warns above fifteen, and times out
around twenty. Frontend targets at most three minutes. System Full may take
longer because it is rare by design. See [CI_STRATEGY.md](CI_STRATEGY.md).

---

## 11. Pull request discipline

```text
main
  ↓
short-lived PR branch
  ↓
pull request
  ↓
review + checks
  ↓
squash merge
  ↓
delete PR branch
```

- `main` is always deployable.
- No direct development on `main`. Never rewrite or force-push `main`.
- No long-lived `develop` branch. No environment branches. The reviewed temporary
  integration exception is defined only in [MVP2_GATE0A_ROADMAP.md](MVP2_GATE0A_ROADMAP.md).
- Squash merge normal feature PRs. Delete merged branches.
- Branch naming: `mvp/pr-NN-short-slug` for roadmap PRs, `eng/pr-NN-short-slug`
  for horizontal engineering work that adds no functional scope.
- **Open the pull request as a draft.** Draft is the iteration state. Draft and
  Ready run the same risk plan for the same diff; readiness never widens CI.

### Review contract and truthful evidence

Every PR uses `.github/pull_request_template.md`; do not replace it with a generated
commit summary. Inspect repository reality before proposing a new implementation.
Explain root cause, scope, non-goals, cohesion and applicable impacts precisely;
concise answers are welcome. Non-applicability requires a reason.

- PR template = authoring contract.
- PR Quality workflow = deterministic delivery-contract enforcement.
- CI = implementation/test evidence.
- GitHub ruleset = merge enforcement (owner configuration after merge).

Passing PR Quality does not prove the code is correct. Passing Backend/Frontend
does not make a poor or misleading PR description acceptable. Both are required.
Drafts may report pending validation but must explain their core design and scope.
Ready PRs must complete the contract, resolve declarations and explain limitations.

A test, build, migration, browser review, deployment check or manual validation may
be claimed as passed only if that exact check actually ran successfully against the
reported code. Name the command/test family and result. If PostgreSQL is unavailable,
say that integration tests did not run locally and CI is still required; never turn
missing evidence into "Backend: pass" or "Fully tested". PR Quality can check the
representation, not verify that an author's claims are true. Independent review and
exact-head CI remain required. Agents never merge; a human merges.

See [AGENT_AUTOMATION.md](AGENT_AUTOMATION.md) for the validator's limits, local usage
and the manual ruleset activation step.

### Size discipline

- One roadmap PR = one reviewable change.
- If a PR cannot be described in the template's **Scope** section in a few
  lines, it is too large — split it.
- Do not smuggle unrelated refactors into a feature PR.
- Do not smuggle functional scope into an infrastructure PR.

---

## 12. Definition of done

A PR is done when all of the following hold:

- [ ] Scope matches its roadmap entry; nothing extra was smuggled in.
- [ ] Independent review and the applicable §10a risk gate passed on the exact
      head SHA. System-risk candidates include required Full regression.
- [ ] `ruff check .` and `ruff format --check .` pass.
- [ ] `python -m compileall app` passes.
- [ ] `pip check` reports no broken requirements.
- [ ] Applicable PostgreSQL tests pass; System-risk candidates require every Full shard.
- [ ] Migrations apply forward and reverse cleanly.
- [ ] `npm run lint` and `npm run build` pass.
- [ ] CI is green.
- [ ] The PR template is filled in truthfully, including dependency and contract impact,
      and the PR Quality check passes for the current description and head.
- [ ] No secret, credential or production connection string is in the diff.
- [ ] Financial rules in section 6 are respected wherever money is touched.
- [ ] Documentation affected by the change has been updated in the same PR.
