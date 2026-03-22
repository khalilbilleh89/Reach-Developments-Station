# Developer Operating System Architecture

## Platform Purpose

Reach Developments Station is a **Real Estate Development Operating System** that supports the full lifecycle of development decision-making and execution.

The platform enables developers to:

- evaluate land and development opportunities
- model development scenarios
- run financial feasibility analysis
- structure and manage projects
- execute commercial sales
- monitor financial performance
- manage portfolio intelligence

---

## Platform Architecture

The platform follows a **single-service architecture**.

### Core Stack

| Component | Technology |
|---|---|
| Backend | FastAPI |
| Frontend | Next.js (static export) |
| Database | PostgreSQL |
| Deployment | Render (single web service) |

### Deployment Structure

```
Render Web Service
 ├── FastAPI Backend        /api/v1/*
 ├── Static Next.js Frontend   /* (served by FastAPI catch-all)
 └── PostgreSQL Database
```

### Forbidden Infrastructure Changes

The following architectural changes are **not allowed**:

- ❌ microservices
- ❌ additional backend services
- ❌ separate frontend hosting
- ❌ multiple databases

PRs must not introduce infrastructure complexity.

---

## Developer Lifecycle Model

The platform covers the complete real estate development lifecycle:

```
Land Evaluation
    ↓
Development Scenario Modelling
    ↓
Feasibility & Investment Analysis
    ↓
Concept Design
    ↓
Project Structuring
    ↓
Construction & Delivery
    ↓
Commercial Sales
    ↓
Financial Control
    ↓
Portfolio Intelligence
```

---

## Architecture Layers

The platform is organized into nine architecture layers. Each layer has a defined scope and must not cross into adjacent layer responsibilities.

### Layer 1 — Land Intelligence

Covers land underwriting, site evaluation, residual land value calculation, and acquisition decision support.

**Modules:** Land

### Layer 2 — Development Scenario Engine

Covers unit mix planning, density analysis, and scenario comparison before a formal project is created.

**Modules:** Concept Planning, Scenario Engine

### Layer 3 — Feasibility & Investment Engine

Covers financial proforma, IRR, NPV, break-even, and investment return analysis.

**Modules:** Feasibility

### Layer 4 — Concept Design Layer

Covers building massing, unit type definition, and area schedule generation.

**Modules:** Concept Planning, Design & Delivery Governance

### Layer 5 — Project Structuring Engine

Covers formal project creation, the master asset hierarchy, cost planning, and tender management.

**Modules:** Projects, Phases, Buildings, Floors, Units, Cost Planning & Tender

### Layer 6 — Construction & Delivery Engine

Covers construction scope, milestone tracking, progress reporting, and stage gate governance.

**Modules:** Construction, Design & Delivery Governance

### Layer 7 — Commercial Sales Engine

Covers pricing, sales reservations, contracts, payment plans, commissions, and sales exceptions.

**Modules:** Pricing, Sales, Payment Plans, Commissions, Sales Exceptions & Incentives

### Layer 8 — Financial Control Engine

Covers collections, receivables, revenue recognition, cashflow forecasting, and financial alerts.

**Modules:** Finance, Collections & Receivables, Revenue Recognition, Cashflow

### Layer 9 — Portfolio Intelligence Engine

Covers cross-project analytics, portfolio dashboards, and market intelligence.

**Modules:** Analytics, Finance Summary, Market Intelligence

---

## Master Platform Engines

Three core engines underpin the platform and must remain centralized.

### Calculation Engine

All derived financial metrics must pass through the Calculation Engine.

Responsibilities:

- IRR and NPV calculations
- break-even analysis
- unit-level pricing computations
- revenue aggregation
- cashflow projections

**Forbidden:**

- ❌ duplicating formulas inside individual modules
- ❌ module-specific calculation engines

### Scenario Engine

All development options and scenario management must pass through the Scenario Engine.

Responsibilities:

- unit mix scenarios
- feasibility scenario variants
- scenario-to-project conversion

**Forbidden:**

- ❌ scenario logic embedded inside UI components
- ❌ scenario branching logic duplicated across modules

### Dynamic Schema Engine

All dynamic platform flexibility must pass through the Dynamic Schema Engine.

Responsibilities:

- configurable unit types
- flexible payment plan templates
- configurable project settings

**Forbidden:**

- ❌ hardcoded schema structures inside modules

---

## Master Asset Hierarchy

The system is built around a master asset hierarchy that reflects real estate development structures:

```
Project
 └── Phase
      └── Building
           └── Floor
                └── Unit
```

This hierarchy is the structural backbone of the entire platform. All modules attach to one or more levels of this hierarchy.

### Module Attachment Points

```
Project
├── Land                     (Project level)
├── Concept Planning         (Project / Phase level)
├── Feasibility              (Project / Phase level)
├── Cost Planning            (Project / Phase / Building level)
├── Design & Delivery        (Phase / Building level)
│
├── Phase
│   ├── Building
│   │   ├── Floor
│   │   │   └── Unit
│   │   │       ├── Pricing          (Unit level)
│   │   │       ├── Sales            (Unit level)
│   │   │       ├── Payment Plans    (Sale level)
│   │   │       ├── Collections      (Payment Plan level)
│   │   │       ├── Revenue Recog.   (Sale / Milestone level)
│   │   │       └── Registry         (Sale / Unit level)
│   │   │
│   │   └── Construction             (Project / Phase / Building level)
│
└── Analytics / Finance Summary  (Project / Portfolio level)
└── Settings                     (System-level; no project FK)
```

---

## Module Responsibilities

### Land Module

- Site identification and evaluation
- Residual land value calculation
- Land underwriting assumptions

### Feasibility Module

- Financial proforma generation
- IRR, NPV, break-even analysis
- Scenario comparison

### Projects Module

- Project creation and registry
- Phase, Building, Floor, and Unit management
- Asset hierarchy integrity

### Pricing Module

- Base price management
- Premium rule computation
- Price override governance
- Price escalation

### Sales Module

- Reservation and SPA management
- Contract lifecycle
- Sales reporting

### Payment Plans Module

- Plan template management
- Payment schedule generation
- Cashflow impact modeling

### Finance Module

- Collections and receivables tracking
- Revenue recognition
- Project financial dashboard
- Portfolio analytics
- Risk alerts
- Cashflow forecasting

### Construction Module

- Scope and milestone management
- Progress reporting

### Registry Module

- Title transfer workflow
- Post-sale document management

### Settings Module

- Pricing policies
- Commission policies
- Project templates

---

## System Boundaries

### Cross-Layer Rules

All cross-layer logic must pass through service layers. Direct database manipulation across layers is **forbidden**.

**Forbidden cross-layer behavior:**

- ❌ Feasibility engine modifying sales records
- ❌ Sales module calculating IRR or NPV
- ❌ Pricing module modifying feasibility assumptions
- ❌ Construction module modifying financial calculations
- ❌ Land module creating projects automatically

### Module Isolation Rules

Each module must manage its own domain logic.

Modules interact through APIs or service interfaces, not through direct cross-module data manipulation.

---

## Engineering Guardrails

### Financial Calculation Guardrails

- All financial calculations must use the Calculation Engine.
- No financial formula duplication is permitted across modules.
- Unit-level data is the origin of all commercial and financial calculations.

### Scenario Logic Guardrails

- All scenario management must use the Scenario Engine.
- Scenario logic must not be embedded inside UI components.

### Schema Guardrails

- All configurable platform behavior must use the Dynamic Schema Engine.
- Hardcoded schema structures inside modules are not permitted.

### Data Hierarchy Guardrails

- The `Project → Phase → Building → Floor → Unit` hierarchy must not be modified without architectural review.
- All operational workflows depend on this structure.

### Assumptions Governance

All feasibility and pricing assumptions must be visible within the system, including:

- value
- source
- last updated date
- editor

Assumptions must be tagged with a status: `Confirmed`, `Benchmark`, `Estimated`, or `Pending Verification`.

The system must never hide assumptions inside formulas.

---

## UI Architecture Principles

- Scenario logic must not be embedded inside UI components.
- All derived metrics displayed in the UI must originate from the Calculation Engine.
- UI components must consume data through API service layers.
- Financial dashboards must not recalculate values client-side.

---

## Scenario-to-Project Conversion

Development scenarios managed in the Scenario Engine can be promoted to formal projects in the Project Structuring Engine.

Conversion flow:

```
Scenario (Scenario Engine)
    ↓
Feasibility Validation (Feasibility & Investment Engine)
    ↓
Formal Project Creation (Project Structuring Engine)
    ↓
Unit Registry Populated (Master Asset Hierarchy)
    ↓
Operational Workflows Activated (Sales, Finance, Construction)
```

This conversion must be managed through the Scenario Engine's conversion service and must not be replicated inside individual modules.

---

## API Architecture

All domain API routes are served under the `/api/v1` prefix.

Each domain module owns a dedicated router prefix and OpenAPI tag group.

Existing API endpoints must not be modified without a dedicated PR.

---

## Related Documents

- [`../00-overview/system-architecture.md`](../00-overview/system-architecture.md) — Master asset hierarchy and domain module list
- [`../03-technical/backend-architecture.md`](../03-technical/backend-architecture.md) — Backend code structure
- [`../03-technical/frontend-architecture.md`](../03-technical/frontend-architecture.md) — Frontend architecture
- [`../03-technical/database-architecture.md`](../03-technical/database-architecture.md) — Database architecture
- [`../SYSTEM_RULES.md`](../SYSTEM_RULES.md) — Mandatory system architecture rules
