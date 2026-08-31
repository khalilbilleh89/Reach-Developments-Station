# Engineering Rules — Reach Developments Station

Permanent engineering policy for MVP 1.0. **Every future PR must reference this
file.** Rules here are not suggestions; changing one is a reviewed decision, not
a drive-by edit.

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

## 10a. Two-speed CI

Continuous integration runs at two speeds, and GitHub's own draft state is the
switch. Nothing else selects it: no label, no slash command, no bot, no comment
parser.

```text
Draft               Backend Fast   structural checks, then the tests this
                                   change can plausibly break
Ready for review    Backend        structural checks, then every test
```

The reason is arithmetic. At roughly fifteen hundred backend tests the full
suite takes around forty-five minutes, and running it on every push turned a
one-line correction into a forty-five-minute wait. A wait long enough to walk
away from is a wait that stops being read, which is how a team ends up merging
on a stale green tick.

**Fast CI is not weaker CI.** It answers a narrower question — *did I break the
area this change can reasonably affect?* — and the broad question is still
asked, in full, before anything merges. What changed is *when* the exhaustive
proof happens, never *whether*.

### What each speed runs

Both keep every structural check, because they are cheap and catch a great
deal: `pip check`, `ruff check .`, `ruff format --check .`,
`python -m compileall app`, `alembic upgrade head`, `alembic check`. Both run
against a real `postgres:16`. Fast means fewer relevant tests; it never means a
different database, because row locks, partial unique indexes and `NUMERIC`
are the behaviour under test.

Only the pytest scope differs. `Backend Fast` runs what
`scripts/ci_backend_tests.py` selects. `Backend` runs `pytest -q` — no
selection, no `--maxfail`, no markers, no excluded concurrency tests.

### How the fast selection is made

The selector is explicit and lives in one small standard-library file. Three
rules and nothing more:

- **A domain owns a family of test files.** The map was built by reading the
  real names in `tests/`, not inferred.
- **A change flows downstream, never up.** Sales sits on pricing, so a pricing
  change runs sales; a sales change does not re-run pricing. Sales' own tests
  already prove its use of pricing's public contract. This asymmetry is where
  the time is saved.
- **Anything unrecognised runs everything.** A new module, a shared fixture,
  `app/core/`, the access layer, a migration no domain claims — all fall back
  to the full suite and print the reason. The selector fails safe, never open.

A changed or newly added test file always runs, whatever else was selected. A
small always-run backbone — configuration, health, migrations, static export,
UX copy, authentication, authorization, audit, API shape and the selector's own
tests — runs on every fast build, about a hundred and twenty tests in eighty
seconds.

Adding a domain is two lines: a `DOMAIN_TEST_PREFIXES` entry and, if anything
consumes it, a `DOWNSTREAM` edge. A guard test fails if any test file in the
repository belongs to no domain, so the map cannot rot quietly.

### The workflow this implies

```text
open the pull request as a draft
  ↓
Backend Fast + Frontend            minutes, not tens of minutes
  ↓
independent review, fixes, repeat
  ↓
mark ready for review
  ↓
Backend (full) + Frontend          on the exact merge candidate
  ↓
merge
```

- **A draft is an iteration state and is never a merge candidate.** It does not
  run the full suite and must not be merged.
- **Ready for review is a merge-candidate state.** The full suite is mandatory.
- **Any commit pushed after a pull request is ready re-runs the full job.** The
  green tick therefore belongs to the exact commit somebody would merge, never
  to an older one. Never merge on a full run whose head SHA is not the PR's
  current head.
- If substantial iteration resumes, convert back to draft to get the fast cycle
  again.

Locally the same idea applies: run the affected domain's tests and the linters
while implementing, and the full suite once before declaring the work final.
The authoritative proof is the exact-head `Backend` run on GitHub.

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
- No long-lived `develop` branch. No environment branches.
- Squash merge normal feature PRs. Delete merged branches.
- Branch naming: `mvp/pr-NN-short-slug` for roadmap PRs, `eng/pr-NN-short-slug`
  for horizontal engineering work that adds no functional scope.
- **Open the pull request as a draft.** Draft is the iteration state and runs
  `Backend Fast`; marking it ready for review is what asks for the full
  regression. See §10a.

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
- [ ] The pull request is marked ready for review, and the `Backend` full
      suite is green **on its current head SHA** — not on an earlier commit.
- [ ] `ruff check .` and `ruff format --check .` pass.
- [ ] `python -m compileall app` passes.
- [ ] `pip check` reports no broken requirements.
- [ ] `pytest -q` passes against PostgreSQL.
- [ ] Migrations apply forward and reverse cleanly.
- [ ] `npm run lint` and `npm run build` pass.
- [ ] CI is green.
- [ ] The PR template is filled in, including dependency and contract impact.
- [ ] No secret, credential or production connection string is in the diff.
- [ ] Financial rules in section 6 are respected wherever money is touched.
- [ ] Documentation affected by the change has been updated in the same PR.
