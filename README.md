# Reach Developments Station

**Real Estate Development Operating System**

Reach Developments Station is a purpose-built operating system for real estate developers. It spans the full development lifecycle — from land underwriting and concept planning through feasibility, pricing, sales, payment plans, collections, finance, registry, construction, and reporting.

---

## System Overview

The platform manages the full commercial and operational lifecycle of a real estate development business:

- **Asset management** — projects, phases, buildings, floors, units
- **Pre-development** — land underwriting, feasibility analysis
- **Commercial** — pricing engine, sales contracts, payment plans, collections
- **Finance** — project financial summaries, cashflow, commissions
- **Post-sale** — registry (title transfer workflow), construction progress tracking
- **Configuration** — system-level pricing and commission policies, project templates

---

## Architecture

The platform runs as a **single-service architecture** on Render:

```
Render Web Service
 ├── FastAPI backend       /api/v1/*
 ├── Next.js frontend      /* (static export served by FastAPI)
 └── PostgreSQL database
```

The asset hierarchy is the central organizing principle of the entire system:

```
Project → Phase → Building → Floor → Unit
```

All commercial domain modules — pricing, sales, payment plans, collections, finance, registry — attach to this backbone.

---

## Module Overview

| Layer | Modules |
|---|---|
| Asset Registry | Projects, Phases, Buildings, Floors, Units |
| Pre-Development | Land, Feasibility |
| Commercial | Pricing, Sales & Contracts, Sales Exceptions, Payment Plans, Collections & Receivables |
| Finance | Finance Summary, Cashflow, Commissions |
| Post-Sale | Registry (title transfer), Construction (delivery tracking) |
| Configuration | Settings (pricing policies, commission policies, project templates) |

### API Routes (all under `/api/v1/`)

| Domain | Route Prefix |
|---|---|
| Projects | `/api/v1/projects` |
| Pricing | `/api/v1/pricing` |
| Sales | `/api/v1/sales` |
| Payment Plans | `/api/v1/payment-plans` |
| Finance | `/api/v1/finance` |
| Registry | `/api/v1/registry` |
| Construction | `/api/v1/construction` |
| Settings | `/api/v1/settings` |

---

## Repository Structure

```
reach-developments-station/
├── README.md
├── .gitignore
├── docs/                          # Architecture and planning documentation (authoritative)
│   ├── 00-overview/               # Platform vision, architecture, data model, roadmap
│   ├── 01-domain/                 # Domain module definitions
│   ├── 02-product/                # Product scope and business rules
│   ├── 03-technical/              # Technical architecture and coding standards
│   ├── 04-decisions/              # Architecture Decision Records (ADRs)
│   └── reference/                 # Source document index and findings summary
├── app/                           # Backend application (Python / FastAPI)
│   ├── main.py
│   ├── core/                      # Shared infrastructure (config, db, security)
│   ├── shared/                    # Cross-cutting utilities, schemas, enums
│   ├── modules/                   # Domain modules
│   └── db/                        # Database base, migrations, seed data
├── frontend/                      # Next.js frontend (static export)
├── tests/                         # Test suite
├── scripts/                       # Developer utility scripts
└── infrastructure/                # Deployment configuration
```

---

## Documentation Map

| Folder | Contents |
|---|---|
| `docs/00-overview/` | Vision and scope, system architecture, core data model, implementation roadmap |
| `docs/01-domain/` | Domain module definitions covering the full real estate development lifecycle |
| `docs/02-product/` | User roles, MVP module scope, business rules, workflows |
| `docs/03-technical/` | Backend architecture, database design, API design, security, deployment, coding standards |
| `docs/04-decisions/` | Architecture Decision Records capturing key architectural choices |
| `docs/reference/` | Source document index and key findings summary |

> **The documentation in `/docs` is authoritative.** All implementation decisions should be traceable to these docs.

---

## Local Development

### Backend

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # configure DATABASE_URL and other variables
alembic upgrade head
uvicorn app.main:app --reload
```

**Bootstrap / Admin seed:** On startup, if `ADMIN_EMAIL` and `ADMIN_PASSWORD` are set in `.env`, the application automatically creates an initial administrator account (idempotent — safe to restart). Set `APP_ENV=test` to skip bootstrap during test runs. See [`docs/03-technical/startup-bootstrap.md`](docs/03-technical/startup-bootstrap.md) for full startup and bootstrap documentation.

### Frontend

```bash
cd frontend
npm install
npm run dev        # development server at http://localhost:3000
```

Set `NEXT_PUBLIC_API_URL` in `frontend/.env.local` to point at the backend:

```
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

---

## Deployment

The platform deploys as a **single Render web service**:

- **Build command:** `cd frontend && npm ci && npm run build && cd .. && pip install -r requirements.txt && alembic upgrade head`
- **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Database:** PostgreSQL (attached Render managed database)

The Next.js frontend is compiled to a static export (`frontend/out/`) and served directly by FastAPI alongside the API.

See [`docs/03-technical/deployment-architecture.md`](docs/03-technical/deployment-architecture.md) for full deployment details.

---

## Testing

```bash
# Run the full test suite
pytest

# Run architecture boundary tests only
pytest tests/architecture/test_commercial_layer_contracts.py -v

# Lint (install ruff if not already present: pip install ruff)
ruff check .
ruff format .
```

---

## Current Runtime Status

| Property | Value |
|---|---|
| Backend API | ✅ Live on Render |
| Frontend | ✅ Next.js static export served by FastAPI |
| Deployment target | [Render](https://render.com) — single web service |
| ASGI entrypoint | `app.main:app` |
| Start command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Liveness endpoint | `GET /health` |
| Root endpoint | `GET /` serves the Next.js frontend (or JSON status when frontend build is absent) |

See [`infrastructure/render/render.yaml`](infrastructure/render/render.yaml) and [`docs/03-technical/deployment-architecture.md`](docs/03-technical/deployment-architecture.md) for full deployment details.

---

## Architecture Docs Are Authoritative

All structural and architectural decisions are documented in `/docs`. Read the documentation before making implementation changes. Key starting points:

- [`docs/00-overview/vision-and-scope.md`](docs/00-overview/vision-and-scope.md) — What this platform is and is not
- [`docs/00-overview/system-architecture.md`](docs/00-overview/system-architecture.md) — Business and technical architecture
- [`docs/03-technical/backend-architecture.md`](docs/03-technical/backend-architecture.md) — Code structure and module organization
- [`docs/03-technical/startup-bootstrap.md`](docs/03-technical/startup-bootstrap.md) — Startup sequence, bootstrap, admin seed, health endpoints
- [`docs/04-decisions/`](docs/04-decisions/) — Architecture Decision Records

