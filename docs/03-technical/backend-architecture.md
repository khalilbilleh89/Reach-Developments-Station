# Backend Architecture

## Overview

The backend for Reach Developments Station starts as a **modular monolith** built with Python and FastAPI.

---

## Why a Modular Monolith

The modular monolith is the correct starting architecture for this system for the following reasons:

1. **Easier to build**: A single deployable unit reduces operational complexity and eliminates the distributed systems problems (network latency, service discovery, distributed transactions) that microservices introduce.

2. **Easier to reason about**: Module boundaries are enforced through code structure and import discipline, not network contracts. This makes the system easier to understand and debug for a solo or small team.

3. **Easier to refactor**: Because the system is new and domain understanding will evolve, the modular monolith makes it easy to move code between modules without coordinating deployments.

4. **Avoids premature complexity**: Microservices are an operational scaling solution, not an architecture quality solution. The correct time to consider microservices is when specific modules need to scale independently — not at day one.

5. **Maintains module discipline**: Each module has its own `api.py`, `models.py`, `schemas.py`, `service.py`, and `repository.py`. This enforces clean separation without the overhead of separate services.

---

## Technology Stack

| Component | Technology |
|---|---|
| Language | Python 3.11+ |
| Web Framework | FastAPI |
| ORM | SQLAlchemy (async) |
| Database | PostgreSQL |
| Migrations | Alembic |
| Validation | Pydantic v2 |
| Authentication | JWT (python-jose) |
| Testing | pytest + httpx |
| Deployment | Render |

---

## Full Target Backend Structure

This is the **full target architecture** — not the day-one coding load. See the MVP build-first structure below for what to build first.

```
reach-developments-station/
├── app/
│   ├── main.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── logging.py
│   │   ├── security.py
│   │   ├── database.py
│   │   ├── exceptions.py
│   │   └── dependencies.py
│   │
│   ├── shared/
│   │   ├── enums/
│   │   │   ├── project.py
│   │   │   ├── sales.py
│   │   │   ├── finance.py
│   │   │   └── registration.py
│   │   │
│   │   ├── schemas/
│   │   │   ├── pagination.py
│   │   │   ├── common.py
│   │   │   └── money.py
│   │   │
│   │   ├── utils/
│   │   │   ├── dates.py
│   │   │   ├── money.py
│   │   │   ├── percentages.py
│   │   │   └── area.py
│   │   │
│   │   └── services/
│   │       ├── audit_service.py
│   │       └── file_storage_service.py
│   │
│   ├── modules/
│   │   ├── projects/
│   │   │   ├── api.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   ├── repository.py
│   │   │   └── rules.py
│   │   │
│   │   ├── phases/
│   │   │   ├── api.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   ├── repository.py
│   │   │   └── rules.py
│   │   │
│   │   ├── buildings/
│   │   │   ├── api.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   └── repository.py
│   │   │
│   │   ├── floors/
│   │   │   ├── api.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   └── repository.py
│   │   │
│   │   ├── units/
│   │   │   ├── api.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   ├── repository.py
│   │   │   ├── pricing_adapter.py
│   │   │   └── status_rules.py
│   │   │
│   │   ├── land/
│   │   │   ├── api.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   ├── repository.py
│   │   │   ├── valuation_engine.py
│   │   │   └── residual_calculator.py
│   │   │
│   │   ├── concept_planning/
│   │   │   ├── api.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   ├── scenario_engine.py
│   │   │   └── unit_mix_engine.py
│   │   │
│   │   ├── feasibility/
│   │   │   ├── api.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   ├── proforma_engine.py
│   │   │   ├── irr_engine.py
│   │   │   ├── break_even_engine.py
│   │   │   └── scenario_runner.py
│   │   │
│   │   ├── cost_planning/
│   │   │   ├── api.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   ├── cost_library.py
│   │   │   ├── estimate_engine.py
│   │   │   ├── tender_comparison.py
│   │   │   └── variance_engine.py
│   │   │
│   │   ├── design_delivery/
│   │   │   ├── api.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   ├── stage_gate_rules.py
│   │   │   └── permit_tracker.py
│   │   │
│   │   ├── pricing/
│   │   │   ├── api.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   ├── pricing_engine.py
│   │   │   ├── premium_rules.py
│   │   │   ├── override_rules.py
│   │   │   └── escalation_engine.py
│   │   │
│   │   ├── sales/
│   │   │   ├── api.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   ├── reservation_rules.py
│   │   │   ├── contract_rules.py
│   │   │   ├── exceptions_engine.py
│   │   │   └── commission_engine.py
│   │   │
│   │   ├── payment_plans/
│   │   │   ├── api.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   ├── template_engine.py
│   │   │   ├── schedule_generator.py
│   │   │   └── cashflow_impact.py
│   │   │
│   │   ├── collections/
│   │   │   ├── api.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   ├── receipt_matching.py
│   │   │   ├── aging_engine.py
│   │   │   └── alerts.py
│   │   │
│   │   ├── finance/
│   │   │   ├── api.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   ├── revenue_recognition.py
│   │   │   ├── cashflow_forecast.py
│   │   │   └── project_financial_summary.py
│   │   │
│   │   ├── registration/
│   │   │   ├── api.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   ├── workflow_rules.py
│   │   │   └── document_checklist.py
│   │   │
│   │   ├── analytics/
│   │   │   ├── api.py
│   │   │   ├── sales_velocity.py
│   │   │   ├── absorption.py
│   │   │   ├── price_band_analysis.py
│   │   │   ├── payment_plan_effects.py
│   │   │   └── dashboards.py
│   │   │
│   │   ├── market_intelligence/
│   │   │   ├── api.py
│   │   │   ├── indicators.py
│   │   │   ├── benchmark_tracker.py
│   │   │   └── signal_engine.py
│   │   │
│   │   └── documents/
│   │       ├── api.py
│   │       ├── models.py
│   │       ├── schemas.py
│   │       ├── service.py
│   │       ├── ingestion.py
│   │       ├── extraction.py
│   │       ├── indexing.py
│   │       └── retrieval.py
│   │
│   └── db/
│       ├── migrations/
│       ├── seed/
│       └── base.py
│
├── tests/
│   ├── projects/
│   ├── units/
│   ├── land/
│   ├── feasibility/
│   ├── pricing/
│   ├── sales/
│   ├── payment_plans/
│   ├── collections/
│   ├── finance/
│   └── registration/
│
├── scripts/
│   ├── seed_demo_data.py
│   ├── run_local.sh
│   └── export_openapi.py
│
├── infrastructure/
│   ├── render/
│   │   └── render.yaml
│   ├── docker/
│   │   └── Dockerfile
│   └── github/
│       └── workflows/
│           ├── ci.yml
│           └── deploy.yml
│
└── docs/
```

---

## MVP Build-First Code Structure

**Start with this. Do not build the full tree above on day one.**

```
app/
├── main.py
├── core/
├── shared/
├── modules/
│   ├── projects/
│   ├── phases/
│   ├── buildings/
│   ├── floors/
│   ├── units/
│   ├── land/
│   ├── feasibility/
│   ├── pricing/
│   ├── sales/
│   ├── payment_plans/
│   ├── collections/
│   └── finance/
└── db/
```

---

## Module Internal Structure

Each module follows the same internal structure:

| File | Responsibility |
|---|---|
| `api.py` | FastAPI router with endpoint definitions |
| `models.py` | SQLAlchemy ORM models |
| `schemas.py` | Pydantic request/response schemas |
| `service.py` | Business logic layer — orchestrates rules and repository |
| `repository.py` | Database access layer — queries and persistence |
| `rules.py` | Business rule enforcement (where applicable) |
| `*_engine.py` | Calculation engine (pricing engine, proforma engine, etc.) |

---

## Module Dependency Rules

To maintain modularity discipline:

- Modules must not import from each other's `models.py` directly
- Cross-module communication goes through the `service.py` layer
- Shared types (enums, money types, common schemas) live in `app/shared/`
- Shared infrastructure (database session, config, security) lives in `app/core/`
- Circular module dependencies are not permitted

---

## API Design Principles

- All endpoints use REST conventions
- All responses use consistent envelope schemas (defined in `app/shared/schemas/common.py`)
- Pagination is supported on all list endpoints (see `app/shared/schemas/pagination.py`)
- All monetary amounts are represented as integers (smallest currency unit) in the database and as formatted strings in API responses
- Authentication is JWT-based
- Authorization is RBAC (role and permission checked in FastAPI dependencies)

See [`api-design.md`](api-design.md) for full API design standards.

---

## Runtime Entry Point

### Canonical ASGI path

```
app.main:app
```

This resolves to the `app` FastAPI instance defined in `app/main.py`.

### Why not a root `main.py`?

The application code lives inside the `app/` package. A root-level `main.py` would sit outside the package boundary and would conflict with the module import path. The `app/` prefix is **required** for the ASGI server to locate the module correctly.

### Implications for Render and local startup

Always use the fully-qualified path:

```bash
# Local development
uvicorn app.main:app --reload

# Production (Render)
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Using `uvicorn main:app` (without the `app.` prefix) will cause a startup failure:

```
Error loading ASGI app. Could not import module "main".
```

See [`deployment-architecture.md`](deployment-architecture.md) for the full deployment reference.
