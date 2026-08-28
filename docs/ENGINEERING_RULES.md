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

## 6. Money, rates and dates

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
- Authentication, roles and project access arrive in PR-MVP-01. Until then the
  service exposes no business data.

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
- Branch naming: `mvp/pr-NN-short-slug`.

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
