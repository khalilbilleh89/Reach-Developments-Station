# Reach Developments Station

**Real Estate Development Operating System**

Reach Developments Station is a purpose-built operating system for real estate developers. It spans the full development lifecycle — from land underwriting and concept planning through feasibility, pricing, sales, payment plans, collections, finance, registration, and reporting.

---

## Platform Purpose

This platform is **not** a generic CRM or spreadsheet replacement. It is a domain-specific operating system designed to manage the complexity of multi-project, multi-phase real estate development businesses.

The system is built around a master asset hierarchy:

```
Project → Phase → Building → Floor → Unit
```

All domain modules — pricing, sales, payment plans, collections, finance — attach to this backbone.

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

## System Backbone Summary

The platform is built around the asset hierarchy `Project → Phase → Building → Floor → Unit`. Domain modules are organized into layers:

| Layer | Modules |
|---|---|
| Master Data | Projects, Phases, Buildings, Floors, Units, Land |
| Pre-Development | Concept Planning, Feasibility, Cost Planning |
| Delivery Governance | Design & Delivery Governance |
| Commercial | Pricing, Price Escalation, Sales & Contracts, Sales Exceptions |
| Finance | Payment Plans, Collections & Receivables, Revenue Recognition, Finance Summary |
| Post-Sale | Registration & Conveyancing, Commissions |
| Intelligence | Analytics, Market Intelligence, Document Intelligence |

---

## MVP Module Summary

The first implementation phase focuses on the essential backbone:

- **Asset Hierarchy**: Projects, Phases, Buildings, Floors, Units
- **Pre-Development**: Land, Feasibility
- **Commercial**: Pricing, Sales
- **Finance**: Payment Plans, Collections, Finance

See [`docs/02-product/module-scope-mvp.md`](docs/02-product/module-scope-mvp.md) for the full MVP scope definition.

See [`docs/03-technical/backend-architecture.md`](docs/03-technical/backend-architecture.md) for the full target backend structure.

---

## Current Runtime Status

| Property | Value |
|---|---|
| Backend API | ✅ Deployed and live on Render |
| Deployment target | [Render](https://render.com) |
| ASGI entrypoint | `app.main:app` |
| Start command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Scope | Backend / API-first — no frontend UI |
| Liveness endpoint | `GET /health` |
| Root endpoint | `GET /` returns service name, env, and status |

> **Note:** The root path `/` returns a simple JSON status response. All domain APIs are served under `/api/v1/`.
>
> See [`infrastructure/render/render.yaml`](infrastructure/render/render.yaml) and [`docs/03-technical/deployment-architecture.md`](docs/03-technical/deployment-architecture.md) for full deployment details.

---

## Setup Orientation

This repository uses Python (FastAPI). A local development environment can be set up using a virtual environment:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Copy `.env.example` to `.env` and configure variables before starting the server.

---

## Architecture Docs Are Authoritative

All structural and architectural decisions are documented in `/docs`. Read the documentation before making implementation changes. Key starting points:

- [`docs/00-overview/vision-and-scope.md`](docs/00-overview/vision-and-scope.md) — What this platform is and is not
- [`docs/00-overview/system-architecture.md`](docs/00-overview/system-architecture.md) — Business and technical architecture
- [`docs/03-technical/backend-architecture.md`](docs/03-technical/backend-architecture.md) — Code structure and module organization
- [`docs/04-decisions/`](docs/04-decisions/) — Architecture Decision Records

