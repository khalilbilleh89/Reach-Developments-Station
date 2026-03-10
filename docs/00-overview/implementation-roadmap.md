# Implementation Roadmap

## Overview

This roadmap defines the phased implementation sequence for Reach Developments Station. The sequence is structured to deliver a usable business backbone early, then progressively add operational depth and intelligence capabilities.

---

## Phase 1 — MVP: Development-Commercial-Finance Backbone

**Goal:** Deliver a working system that can manage the full lifecycle from asset registration through pricing, sales, payment plans, collections, and financial summary.

**Rationale:** These modules are the minimum viable set needed for a real estate developer to run commercial operations on the platform. They cover the core workflows: knowing what you have (units), what they cost (pricing), who bought what (sales), how they will pay (payment plans), whether they are paying (collections), and what the financial picture looks like (finance).

### MVP Modules

| Module | Priority | Notes |
|---|---|---|
| Projects | P1 | Asset backbone — must be first |
| Phases | P1 | Asset backbone — must be first |
| Buildings | P1 | Asset backbone — must be first |
| Floors | P1 | Asset backbone — must be first |
| Units | P1 | Asset backbone — must be first |
| Land | P1 | Pre-development foundation |
| Feasibility | P1 | Pre-development foundation |
| Pricing | P1 | Commercial backbone |
| Sales | P1 | Commercial backbone |
| Payment Plans | P1 | Finance backbone |
| Collections | P1 | Finance backbone |
| Finance Summary | P1 | Finance backbone |

### MVP Build-First Code Structure

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

### Recommended Build Sequence Within MVP

1. Core infrastructure (`app/core/`, `app/db/`, `app/main.py`)
2. Shared utilities and schemas (`app/shared/`)
3. Asset backbone — Projects, Phases, Buildings, Floors, Units
4. Land module
5. Feasibility module
6. Pricing module
7. Sales module
8. Payment Plans module
9. Collections module
10. Finance Summary module

---

## Phase 2 — Operational Depth

**Goal:** Extend the platform to cover pre-development planning, delivery governance, cost control, and post-sale operations.

### Phase 2 Modules

| Module | Notes |
|---|---|
| Concept Planning | Unit mix scenario engine, density analysis |
| Cost Planning & Tender | Cost estimation, tender comparison, variance |
| Design & Delivery Governance | Stage gates, permits, consultant tracking |
| Price Escalation | Scheduled and triggered escalation management |
| Sales Exceptions & Incentives | Discount governance, incentive approval workflow |
| Revenue Recognition | Stage-based and milestone-based recognition |
| Registration & Conveyancing | Title transfer workflow, document checklist |
| Commissions | Agent commission tracking and payables |

### Recommended Sequence for Phase 2

1. Concept Planning (natural extension of Feasibility)
2. Cost Planning & Tender (completes the pre-development picture)
3. Design & Delivery Governance (delivery tracking)
4. Price Escalation (extends Pricing)
5. Sales Exceptions & Incentives (extends Sales)
6. Revenue Recognition (extends Finance)
7. Registration & Conveyancing (post-sale workflow)
8. Commissions (post-sale finance)

---

## Phase 3 — Intelligence and AI Layer

**Goal:** Add AI-powered analytics, market intelligence, and document intelligence to the platform.

### Phase 3 Modules

| Module | Notes |
|---|---|
| Analytics | Sales velocity, absorption, price band analysis, payment plan effects |
| Market Intelligence | Benchmark tracking, market signal engine |
| Document Intelligence | PDF ingestion, extraction, indexing, retrieval |

### Notes on Phase 3

- Analytics and Market Intelligence require Phase 1 and Phase 2 data to be populated
- Document Intelligence requires a document storage strategy (see [`../04-decisions/adr-004-document-storage-strategy.md`](../04-decisions/adr-004-document-storage-strategy.md))
- AI capabilities should be added incrementally and governed carefully

---

## What Is Explicitly Deferred

The following are **not** part of any current implementation phase:

- General ledger accounting integration
- Construction scheduling / ERP
- Property management after delivery
- Public-facing sales portal
- Mortgage processing
- Human resources and payroll

---

## Follow-Up PRs

| PR Reference | Scope |
|---|---|
| PR-REDS-ARCH-002 | Write initial overview docs content in full detail |
| PR-REDS-TECH-001 | Create first backend skeleton |
| PR-REDS-DATA-001 | Define initial database schema for core hierarchy |
| PR-REDS-MVP-001 | Implement Project / Phase / Building / Floor / Unit backbone |
