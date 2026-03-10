# System Architecture

## Business Architecture Overview

Reach Developments Station is organized around a **master asset hierarchy** that reflects how real estate development businesses structure their portfolios:

```
Project → Phase → Building → Floor → Unit
```

Every domain module in the system attaches to one or more levels of this backbone. This hierarchy is the central organizing principle of the entire platform.

---

## Master Asset Hierarchy

| Level | Description |
|---|---|
| **Project** | The top-level development (e.g., a mixed-use masterplan or a standalone residential tower) |
| **Phase** | A delivery phase within a project (e.g., Phase 1 — North Tower, Phase 2 — South Tower) |
| **Building** | A physical or legal structure within a phase |
| **Floor** | A floor or level within a building |
| **Unit** | An individual sellable or leasable unit (apartment, villa, townhouse, retail unit, etc.) |

This hierarchy supports both simple single-building projects and complex multi-phase masterplan developments.

---

## Domain Module List

The system is organized into the following domain modules:

### Pre-Development
| Module | Purpose |
|---|---|
| Land | Land underwriting, valuation, residual land value |
| Concept Planning | Scenario planning, unit mix, density analysis |
| Feasibility | Proforma, IRR, NPV, break-even, scenario comparison |
| Cost Planning & Tender | Cost estimation, tender comparison, variance tracking |
| Design & Delivery Governance | Stage gates, permits, consultant coordination |

### Asset Registry
| Module | Purpose |
|---|---|
| Projects | Top-level development registry |
| Phases | Phase definition and status |
| Buildings | Building registry |
| Floors | Floor registry |
| Units | Unit master data, type, status, area, pricing link |

### Commercial
| Module | Purpose |
|---|---|
| Pricing | Base pricing, premium rules, override governance |
| Price Escalation | Scheduled and triggered price escalation |
| Sales & Contracts | Reservation, SPA, contract management |
| Sales Exceptions & Incentives | Discount and incentive approval workflow |
| Commissions | Agent and broker commission tracking |

### Finance
| Module | Purpose |
|---|---|
| Payment Plans | Plan templates, schedule generation, cashflow impact |
| Collections & Receivables | Receipt matching, aging, alerts |
| Revenue Recognition | Stage-based and milestone-based recognition |
| Finance Summary | Cross-project financial dashboard |

### Post-Sale
| Module | Purpose |
|---|---|
| Registration & Conveyancing | Title transfer workflow, document checklist |

### Intelligence (Future)
| Module | Purpose |
|---|---|
| Analytics | Sales velocity, absorption rates, price band analysis |
| Market Intelligence | Benchmark tracking, market signals |
| Document Intelligence | Document ingestion, extraction, and retrieval |

---

## How Modules Attach to the Backbone

```
Project
├── Land                     (attaches at Project level)
├── Concept Planning         (attaches at Project / Phase level)
├── Feasibility              (attaches at Project / Phase level)
├── Cost Planning            (attaches at Project / Phase / Building level)
├── Design & Delivery        (attaches at Phase / Building level)
│
├── Phase
│   ├── Building
│   │   ├── Floor
│   │   │   └── Unit
│   │   │       ├── Pricing          (attaches at Unit level)
│   │   │       ├── Sales            (attaches at Unit level)
│   │   │       ├── Payment Plans    (attaches at Sale level)
│   │   │       ├── Collections      (attaches at Payment Plan level)
│   │   │       ├── Revenue Recog.   (attaches at Sale / Milestone level)
│   │   │       └── Registration     (attaches at Sale / Unit level)
│
└── Analytics / Finance Summary  (attaches at Project / Portfolio level)
```

---

## Architecture Layers

The system is organized into the following conceptual layers:

### Layer 1 — Master Data
Projects, Phases, Buildings, Floors, Units, Land parcels. This is the structural foundation that all other modules reference.

### Layer 2 — Business Rule Engines
Rule-based calculation and governance engines for:
- Pricing (base price + premium rules + overrides)
- Payment plan generation (template-based schedule creation)
- Feasibility (proforma, IRR, NPV, break-even)
- Sales exception governance (discount approval thresholds)
- Collection aging and alert rules

### Layer 3 — Transactions
Operational transaction records:
- Sales reservations and contracts
- Payment receipts and matching
- Tender submissions and award records
- Stage gate approvals and permit records
- Registration workflow events

### Layer 4 — Analytics & Reporting
Aggregated views and financial summaries:
- Sales velocity and absorption
- Revenue recognition reporting
- Project financial summary (cashflow, cost vs. revenue)
- Portfolio dashboard

### Layer 5 — Document Intelligence (Future)
AI-assisted document processing:
- PDF ingestion and text extraction
- Data extraction and indexing
- Retrieval-augmented queries

---

## Technology Architecture

The backend starts as a **modular monolith** built with:

- **Language**: Python
- **Framework**: FastAPI
- **Database**: PostgreSQL (via SQLAlchemy ORM)
- **Migrations**: Alembic
- **Deployment**: Render

The modular monolith approach is intentional — see [`../04-decisions/adr-001-domain-architecture.md`](../04-decisions/adr-001-domain-architecture.md) for the rationale.

The full recommended backend code structure is documented in [`../03-technical/backend-architecture.md`](../03-technical/backend-architecture.md).
