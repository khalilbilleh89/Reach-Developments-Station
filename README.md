# Reach Developments Station

Real estate development **tracking and financial control system**.

The operational centre of the product is the individual **property unit**. Its
financial spine is **project cashflow**. The system exists to provide one
editable, auditable source of truth for projects, land and permits; inventory;
pricing; sales and legal contracts; payment plans; collections; unit economics;
construction control; consolidated cashflow; and management reporting.

---

## MVP boundaries

This repository is a **clean rebuild**. `main` was intentionally demolished; the
previous application survives only as legacy Git history and is reference
material at most. Nothing from it is restored.

**In scope for MVP 1.0:** the twelve pull requests in
[docs/MVP_ROADMAP.md](docs/MVP_ROADMAP.md).

**Out of scope:** anything that turns this into a general "Developer Operating
System". No AI subsystems, no strategy or scenario engines, no generic workflow
or rules engines, no microservices. The full forbidden list lives in
[docs/ENGINEERING_RULES.md](docs/ENGINEERING_RULES.md).

## Roadmap position

| Scope                    | Status |
| ------------------------ | -----: |
| Total planned MVP PRs    |     12 |
| Completed                |      5 |
| Remaining                |      7 |

Current: **PR-MVP-04 — Pricing & Unit 360**.
Next: **PR-MVP-05 — Sales & Legal**.

The system has authentication, the fixed role catalogue, country configuration,
an append-only audit trail, projects with land, planning controls, permits and
documents, a full inventory register — phases, buildings, floors, units,
versioned area schedules, sub-assets, release controls and constrained
configurable fields — and governed pricing: a versioned pricing policy, area
rules, premiums, escalation, market benchmarks, and effective-dated unit price
versions with a component-by-component waterfall behind every figure.

A price is never overwritten. Changing one creates a new version; the one it
replaces is superseded and stays readable. Finance prepares, an Approver / CFO
approves and activates, and activating a price is the only thing in the system
that sets a unit's `pricing_approved` release gate — which inventory withdraws
again the moment a priced fact about the unit changes.

There is still **no sale in the system**. No clients, no reservations, no
contracts, no payment plans, no receipts and no collections. There is also no
unit cost, no margin and no profitability: governed cost allocations arrive in
PR-MVP-08, and an invented cost inside a real margin would be worse than no
margin at all.

---

## Architecture

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

One repository, one backend, one frontend, one database, one Render web service,
one migration history, one API namespace. Full detail in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

**Stack:** Python 3.13 · FastAPI · SQLAlchemy 2.x · Alembic · Psycopg 3 ·
Argon2id · PostgreSQL 16 · Node.js 22 · Next.js (App Router, static export) ·
TypeScript.

**Authentication** is server-side opaque sessions in an HttpOnly,
`SameSite=Strict` cookie — no JWT, no auth framework, no token in
`localStorage`. Authorization is explicit checks against eleven fixed roles;
there is no permission table and no policy language.

## Repository structure

```text
.
├── app/                        FastAPI modular monolith
│   ├── main.py                 application factory, middleware, error mapping, static mount
│   ├── api/health.py           liveness and readiness probes
│   ├── core/                   configuration, database, correlation, error types
│   ├── db/
│   │   ├── base.py             the one declarative base
│   │   └── migrations/         Alembic history (root: 0000_mvp_baseline)
│   └── modules/
│       ├── access/             identity, sessions, fixed roles, user administration
│       ├── settings/           currencies, country packs, tax rules, lookups, thresholds
│       ├── projects/           projects, access, land, planning, permits, documents
│       ├── inventory/          phases, buildings, floors, units, areas, custom fields
│       ├── pricing/            pricing policy, price versions, premiums, benchmarks
│       └── audit/              append-only governance history
├── frontend/                   Next.js static export
│   ├── src/app/                login, projects workspace, settings shell, design tokens
│   ├── src/components/         UI pieces, project workspace tabs, settings sections
│   └── src/lib/api/            the only place the browser calls the API
├── docs/                       architecture, roadmap, engineering rules, deployment
├── scripts/                    Render build and start commands
├── tests/                      backend test suite
└── .github/                    CI workflow and pull request template
```

---

## Local backend setup

Requires Python 3.13 and a reachable PostgreSQL 16.

```bash
python3.13 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
pip install -r requirements-dev.txt

cp .env.example .env        # then edit DATABASE_URL
```

Run the API:

```bash
uvicorn app.main:app --reload
```

- Liveness: <http://localhost:8000/api/v1/health/live>
- Readiness: <http://localhost:8000/api/v1/health/ready>
- OpenAPI: <http://localhost:8000/docs> — development only; withheld in production

Create the first administrator once the schema exists:

```bash
python -m app.modules.access.bootstrap_admin
```

The password is prompted for, never passed as an argument or read from the
environment. The command refuses to run while an active System Administrator
already exists.

The backend runs without a frontend build. If `frontend/out` is absent it logs a
warning and serves the API only.

## Local frontend setup

Requires Node.js 22.

```bash
cd frontend
npm ci
npm run dev      # development server on http://localhost:3000
```

Production export (this is what FastAPI serves):

```bash
cd frontend
npm run lint
npm run build    # writes frontend/out/
```

With `frontend/out/` present, `uvicorn app.main:app` serves the site at `/` and
the API at `/api/v1/*`.

---

## Database migrations

The database URL comes from `app/core/config.py`; `alembic.ini` deliberately
carries no `sqlalchemy.url`.

```bash
alembic upgrade head        # apply
alembic current             # show applied revision
alembic history             # show the history
alembic check               # models and schema still agree
alembic downgrade base      # reverse to an empty database
```

`alembic check` reports any difference between the models and the database the
migrations produce. CI runs it after `alembic upgrade head` and fails on drift;
it never generates a revision automatically. When it reports a difference, write
the migration by hand or autogenerate one locally and read every line of it.

Create a new revision with an explicit, ordered revision id:

```bash
alembic revision -m "add project tables" --rev-id "0001_project_land"
```

Automatic table creation at startup is never used. All schema changes go through
Alembic.

## Testing

Backend tests require a reachable PostgreSQL database. They fail rather than
skip when one is missing.

```bash
export DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/reach_station_test"

ruff check .                # lint
ruff format --check .       # formatting
python -m compileall app    # compile
pip check                   # dependency tree
alembic upgrade head        # schema
alembic check               # no drift between models and schema
pytest -q                   # tests
```

Frontend:

```bash
cd frontend
npm run lint
npm run build
```

CI runs exactly these checks on every pull request into `main`
(`.github/workflows/ci.yml`). It never deploys.

---

## Render deployment

Render runs the two scripts in `scripts/`:

```bash
./scripts/render-build.sh    # Build command  — installs deps, builds the frontend
./scripts/render-start.sh    # Start command  — migrates, then starts Uvicorn
```

**The build stage never connects to PostgreSQL.** Migrations run at start, so a
database outage is a deployment-readiness failure rather than a source-build
failure. Configuration, environment variables, runtime pinning and the
post-merge verification checklist are in
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

---

## Branch and pull request workflow

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

Branch naming follows the roadmap: `mvp/pr-00-foundation`,
`mvp/pr-01-governance`, `mvp/pr-02-project-land-permits`, …

- `main` is always deployable.
- No direct development on `main`; never rewrite or force-push it.
- No long-lived `develop` branch, no environment branches.
- Squash merge, then delete the branch.

Every PR uses [`.github/pull_request_template.md`](.github/pull_request_template.md)
and must declare dependency, contract, migration and security impact.

---

## Canonical documents

| Document | Purpose |
| -------- | ------- |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Product and runtime architecture, module boundaries, governing principles |
| [docs/MVP_ROADMAP.md](docs/MVP_ROADMAP.md) | The twelve MVP pull requests and their contents |
| [docs/ENGINEERING_RULES.md](docs/ENGINEERING_RULES.md) | Dependency policy, clean-code rules, money/date rules, API and migration conventions, definition of done |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Render configuration, build/start separation, verification, rollback |
