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

---

## 7. Current state (through PR-MVP-01)

```text
app/
├── main.py                  application factory, middleware, error mapping, static mount
├── api/health.py            liveness and readiness
├── core/config.py           environment configuration, database URL normalisation
├── core/correlation.py      per-request correlation identity
├── core/database.py         the one engine, the one session factory
├── core/errors.py           service error types, mapped to status codes in one place
├── db/base.py               the one declarative base
└── modules/
    ├── access/              identity, sessions, fixed roles, user administration
    ├── settings/            currencies, country packs, tax rules, lookups, thresholds
    └── audit/               append-only governance history
```

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

### Deferred by design

Project-scoped access (`user_project_access`) waits for PR-MVP-02, when a real
`Project` exists to key it to. No orphan identifiers are created in advance.

No real-estate domain exists yet beyond this control layer. Domains arrive on the
schedule in [MVP_ROADMAP.md](MVP_ROADMAP.md).

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
