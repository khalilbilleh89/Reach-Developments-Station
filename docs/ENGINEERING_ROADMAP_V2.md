# Reach Developments Station — Engineering Roadmap V2

**Created:** 2026-03-20
**Based on:** Platform Audit (see [PLATFORM_AUDIT.md](./PLATFORM_AUDIT.md))
**Focus:** Structural work only — major domain completion, not minor bugs or UI polish

---

## Executive Summary

The platform has achieved **83% completion of Phase 1 (MVP)** and **50% of Phase 2 (Operational Depth)**. All 18 frontend pages are wired to real APIs. The core data flow chain (Unit → Pricing → Contract → Payment Plan → Installments → Collections → Finance) is functional end-to-end.

The primary gaps are:
1. **17 stub engine files** that need implementation or removal
2. **4 partially implemented modules** (Collections, Finance, Land, Feasibility)
3. **7 missing domains** from the documented roadmap
4. **Frontend pages missing** for Land and Feasibility modules

---

## Sprint Plan

### Sprint 1 — Complete MVP Financial Core (P0)

**Goal:** Eliminate all stubs in the financial backbone. Collections and Finance are critical for operational use.

#### 1.1 Collections Engine Completion

| Task | File | Description |
|------|------|-------------|
| Implement aging engine | `collections/aging_engine.py` | Classify receivables into aging buckets (current, 30d, 60d, 90d, 90d+) |
| Implement receipt matching | `collections/receipt_matching.py` | Auto-match receipts to installments by contract, amount, date |
| Implement collection alerts | `collections/alerts.py` | Generate alerts for overdue receivables with escalation tiers |
| Wire aging to API | `collections/api.py` | Enhance `GET /collections/aging-summary` to use real engine |
| Add tests | `tests/collections/` | Engine unit tests + API integration tests |

**Acceptance:** `GET /collections/aging-summary` returns real aging buckets computed from receivable data.

#### 1.2 Finance Engine Completion

| Task | File | Description |
|------|------|-------------|
| Implement financial summary engine | `finance/project_financial_summary.py` | Multi-dimensional summary: by phase, by building, by status, with ratios |
| Implement revenue recognition | `finance/revenue_recognition.py` | Stage-based (percentage of completion) and milestone-based recognition |
| Implement cashflow forecast engine | `finance/cashflow_forecast.py` | Complement existing cashflow module with finance-specific projections |
| Enhance finance API | `finance/api.py` | Add endpoints: `/finance/project-summary/{id}/by-phase`, `/finance/revenue-recognition/{id}` |
| Add tests | `tests/finance/` | Engine unit tests + API integration tests |

**Acceptance:** Finance summary includes multi-dimensional breakdown and revenue recognition output.

---

### Sprint 2 — Complete Pre-Development Modules (P1)

**Goal:** Make Land and Feasibility modules fully operational with frontend pages.

#### 2.1 Land Valuation Engine

| Task | File | Description |
|------|------|-------------|
| Implement valuation engine | `land/valuation_engine.py` | Comparable sales, income capitalization, cost approach methods |
| Implement residual calculator | `land/residual_calculator.py` | RLV = GDV − Total Development Costs − Developer Profit |
| Wire engines to service | `land/service.py` | Integrate engines into `create_valuation()` |
| Build Land frontend page | `frontend/src/app/(protected)/land/` | Parcels list, detail, assumptions, valuations |
| Build Land API client | `frontend/src/lib/land-api.ts` | API functions for parcels, assumptions, valuations |
| Add Land types | `frontend/src/lib/land-types.ts` | TypeScript interfaces matching backend schemas |
| Add tests | `tests/land/` | Engine unit tests + valuation scenarios |

**Acceptance:** Land page shows parcels with automated valuations (RLV and comparable sales).

#### 2.2 Feasibility Sub-Engines

| Task | File | Description |
|------|------|-------------|
| Implement proforma engine | `feasibility/proforma_engine.py` | Detailed pro forma with line-item cost breakdown |
| Implement IRR engine | `feasibility/irr_engine.py` | True IRR calculation using Newton-Raphson or bisection method |
| Implement break-even engine | `feasibility/break_even_engine.py` | Sales velocity break-even, cost break-even, price break-even |
| Implement scenario runner | `feasibility/scenario_runner.py` | Base/bull/bear scenario execution with parameter variation |
| Build Feasibility frontend page | `frontend/src/app/(protected)/feasibility/` | Runs list, assumptions editor, results dashboard |
| Build Feasibility API client | `frontend/src/lib/feasibility-api.ts` | API functions for runs, assumptions, calculate, results |
| Add Feasibility types | `frontend/src/lib/feasibility-types.ts` | TypeScript interfaces matching backend schemas |
| Add tests | `tests/feasibility/` | Engine unit tests + scenario validation |

**Acceptance:** Feasibility page allows creating runs, editing assumptions, executing calculations, and viewing results with IRR and break-even analysis.

---

### Sprint 3 — Stub Cleanup & Engine Consolidation (P1)

**Goal:** Remove or implement all remaining stub files. Consolidate engine architecture.

#### 3.1 Pricing Engine Consolidation

| Task | File | Description |
|------|------|-------------|
| Implement premium rules | `pricing/premium_rules.py` | Configurable premium evaluation (floor bands, view categories, corner detection) |
| Implement override rules | `pricing/override_rules.py` | Authorization thresholds for manual price overrides |
| Remove or delegate legacy stub | `pricing/pricing_engine.py` | Replace 6-line stub with import delegation to `engines/pricing_engine.py` |
| Add tests | `tests/pricing/` | Premium rule unit tests, override authorization tests |

#### 3.2 Payment Plan Engine Consolidation

| Task | File | Description |
|------|------|-------------|
| Implement cashflow impact | `payment_plans/cashflow_impact.py` | Calculate projected cashflow impact of a payment plan |
| Remove or delegate schedule generator | `payment_plans/schedule_generator.py` | Stub superseded by `template_engine.py` — remove or delegate |
| Add tests | `tests/payment_plans/` | Cashflow impact unit tests |

**Acceptance:** Zero stub engine files remaining. All engines are either implemented or removed.

---

### Sprint 4 — Revenue Recognition & Price Escalation (P2)

**Goal:** Add revenue recognition and price escalation as distinct domains.

#### 4.1 Revenue Recognition Module

| Task | Description |
|------|-------------|
| Design revenue recognition model | Percentage-of-completion + milestone-based methods |
| Create database migration | `recognition_entries` table with contract_id, method, recognized_amount, period |
| Implement recognition engine | `finance/revenue_recognition.py` — full implementation |
| Add API endpoints | `GET /finance/revenue-recognition/{project_id}`, `POST /finance/revenue-recognition/calculate` |
| Build frontend section | Revenue recognition panel in Finance dashboard |
| Add tests | Engine + API + integration |

#### 4.2 Price Escalation Module

| Task | Description |
|------|-------------|
| Design escalation model | Scheduled (time-based) and triggered (threshold-based) escalation |
| Create `price_escalation` module | `app/modules/price_escalation/` with models, api, service, repository |
| Create database migration | `price_escalation_rules`, `price_escalation_events` tables |
| Implement escalation engine | Apply escalation rules to unit pricing |
| Wire to pricing module | Escalation feeds into pricing engine as an adjustment |
| Build frontend page | Escalation rules management UI |
| Add tests | Engine + API + integration |

---

### Sprint 5 — Concept Planning & Cost Control (P2)

**Goal:** Add pre-development planning tools.

#### 5.1 Concept Planning Module

| Task | Description |
|------|-------------|
| Create `concept_planning` module | `app/modules/concept_planning/` |
| Design data model | Concept scenarios, unit mix analysis, density parameters |
| Create database migration | `concept_scenarios`, `unit_mix_options`, `density_analysis` tables |
| Implement scenario engine | Unit mix optimization, density analysis |
| Build frontend page | Scenario editor, comparison view |
| Add tests | Engine + API |

#### 5.2 Cost Planning & Tender Module

| Task | Description |
|------|-------------|
| Create `cost_planning` module | `app/modules/cost_planning/` |
| Design data model | Cost estimates, tender packages, bid comparisons, variance tracking |
| Create database migration | `cost_estimates`, `tender_packages`, `tender_bids`, `cost_variances` tables |
| Implement cost engines | Estimate calculation, bid comparison, variance tracking |
| Wire to construction module | Cost plan feeds into construction cost tracking |
| Build frontend page | Cost planning dashboard, tender management |
| Add tests | Engine + API + integration with construction |

---

### Sprint 6 — Design Governance & Operational Depth (P3)

**Goal:** Add delivery governance capabilities.

#### 6.1 Design & Delivery Governance Module

| Task | Description |
|------|-------------|
| Create `design_governance` module | `app/modules/design_governance/` |
| Design data model | Stage gates, permits, consultant assignments, design reviews |
| Create database migration | `design_stage_gates`, `permits`, `consultant_assignments` tables |
| Implement governance engine | Stage gate validation, permit tracking |
| Wire to construction module | Governance gates must pass before construction milestones |
| Build frontend page | Stage gate dashboard, permit tracker |
| Add tests | Workflow + API |

---

### Sprint 7 — Analytics & Intelligence Layer (P3)

**Goal:** Add data-driven analytics capabilities.

#### 7.1 Analytics Module

| Task | Description |
|------|-------------|
| Create `analytics` module | `app/modules/analytics/` |
| Implement analytics engines | Sales velocity, absorption rate, price band analysis, payment plan effect analysis |
| Build aggregation queries | Project-level and portfolio-level analytics |
| Build frontend dashboards | Analytics dashboard with charts and KPIs |
| Add tests | Engine + query efficiency |

#### 7.2 Market Intelligence Module

| Task | Description |
|------|-------------|
| Create `market_intelligence` module | `app/modules/market_intelligence/` |
| Design data model | Market benchmarks, comparable projects, signals |
| Implement market signal engine | Benchmark comparison, trend detection |
| Build frontend page | Market intelligence dashboard |
| Add tests | Engine + data flow |

---

## Deferred (Not in Scope)

Per the original roadmap, the following remain explicitly deferred:

- General ledger accounting integration
- Construction scheduling / ERP
- Property management after delivery
- Public-facing sales portal
- Mortgage processing
- Human resources and payroll
- Document Intelligence (AI/PDF) — requires document storage strategy (ADR-004)

---

## Success Metrics

| Milestone | Target | Measure |
|-----------|--------|---------|
| Sprint 1 complete | Zero financial stubs | All collections + finance engines implemented |
| Sprint 2 complete | Full pre-dev pipeline | Land and Feasibility fully functional with UI |
| Sprint 3 complete | Zero stub files | All 17 stub engine files implemented or removed |
| Sprint 4 complete | Revenue compliance | Revenue recognition engine operational |
| Sprint 5 complete | Pre-dev tools | Concept planning and cost control live |
| Sprint 6 complete | Delivery governance | Stage gates and permits tracked |
| Sprint 7 complete | Intelligence layer | Analytics dashboards operational |

---

## Architecture Principles (Unchanged)

These principles from the original architecture must be maintained throughout:

1. **Single backend service** — no microservices split
2. **Modular monolith** — each domain in `app/modules/{domain}/`
3. **Domain separation** — enforced by architecture tests
4. **Unit-centric financial model** — all financial data traces back to unit
5. **Repository pattern** — no direct DB access in services
6. **Deterministic engines** — pure functions, no side effects, testable
7. **Frontend-backend contract alignment** — TypeScript types mirror Pydantic schemas

---

*This roadmap prioritizes structural completion over feature expansion. Focus on eliminating stubs, implementing missing engines, and building frontend pages for backend-only modules before adding entirely new domains.*
