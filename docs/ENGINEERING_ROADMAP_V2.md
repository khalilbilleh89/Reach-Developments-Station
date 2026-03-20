# Reach Developments Station — Engineering Roadmap V2

**Created:** 2026-03-20
**Based on:** Platform Audit (see [PLATFORM_AUDIT.md](./PLATFORM_AUDIT.md))
**Focus:** Structural work only — major domain completion, not minor bugs or UI polish

---

## Audit Limitation

This roadmap is based on a repository structural audit. It does **not** incorporate:
- Production runtime validation
- Production database data correctness
- UI bug fixes
- Deployed environment verification

A deeper follow-up audit should be performed after merging this roadmap to validate production truth.

---

## Executive Summary

The platform has achieved approximately **83% completion of Phase 1 (MVP)** and **50% of Phase 2 (Operational Depth)** at the repository code level. 15 of 18 frontend pages are wired to real backend APIs; 3 pages (`/commission`, `/cashflow`, `/settings`) display static demo data despite having fully implemented backend services.

The primary gaps are:
1. **3 frontend pages using demo data** instead of calling implemented backend services
2. **17 stub engine files** that need implementation or removal
3. **5 partially implemented modules** (Collections, Finance, Land, Feasibility, Settings)
4. **7 missing domains** from the documented roadmap
5. **Frontend pages missing** for Land and Feasibility modules
6. **Unverified production truths** — finance summaries, currency propagation, and live data integrity

---

## Priority Order

The roadmap is ordered to address **structural truth and operational credibility first**, followed by domain completion, and finally new capabilities.

| # | Priority | Domain | Goal |
|---|----------|--------|------|
| 1 | P0 | Finance truth / summary validation | Verify finance summary produces correct values with real data |
| 2 | P0 | Project currency propagation | Ensure currency flows consistently from settings → pricing → contracts → finance |
| 3 | P0 | Demo/static data elimination | Wire commission, cashflow, and settings pages to real backend APIs |
| 4 | P0 | Collections completion | Implement aging engine, receipt matching, alerts |
| 5 | P1 | Land module productization | Build frontend page and sidebar entry for existing backend |
| 6 | P1 | Land valuation engine completion | Implement valuation engine and residual calculator |
| 7 | P1 | Feasibility completion | Implement sub-engines (IRR, break-even, scenarios) and build frontend page |
| 8 | P1 | Pricing / sales readiness hardening | Implement premium rules, override rules; consolidate pricing engine stubs |
| 9 | P1 | Commission live-data verification | Verify commission calculation produces correct values in production |
| 10 | P1 | Cashflow truth validation | Verify cashflow forecasting produces correct values in production |
| 11 | P2 | Revenue recognition | Implement revenue recognition engine and API |
| 12 | P2 | Price escalation | Build price escalation module |
| 13 | P2 | Concept planning | Build concept planning module |
| 14 | P2 | Cost planning & tender | Build cost planning module |
| 15 | P3 | Design & delivery governance | Build design governance module |
| 16 | P3 | Analytics | Build analytics module |
| 17 | P3 | Market intelligence | Build market intelligence module |
| 18 | P3 | Document intelligence | Build document intelligence (deferred per ADR-004) |

---

## Sprint Plan

### Sprint 1 — Finance Truth & Demo Data Elimination (P0)

**Goal:** Establish financial credibility. Eliminate demo/static pages. Validate that finance summaries produce correct values.

#### 1.1 Finance Summary Validation

| Task | File | Description |
|------|------|-------------|
| Validate finance summary with real contract data | `finance/service.py` | Verify `get_project_summary()` correctly aggregates unit counts, contract values, collected amounts |
| Implement financial summary engine | `finance/project_financial_summary.py` | Multi-dimensional summary: by phase, by building, by status, with ratios |
| Verify currency propagation | Settings → Pricing → Contracts → Finance | Ensure currency from pricing policies flows through to financial summaries |
| Add validation tests | `tests/finance/` | Tests verifying monetary values are correct end-to-end |

#### 1.2 Demo Data Elimination

| Task | File | Description |
|------|------|-------------|
| Wire commission page to real API | `frontend/src/app/(protected)/commission/page.tsx` | Replace `demo-data.ts` imports with calls to `/commission/*` backend endpoints |
| Wire cashflow page to real API | `frontend/src/app/(protected)/cashflow/page.tsx` | Replace `demo-data.ts` imports with calls to `/cashflow/*` backend endpoints |
| Wire settings page to real API | `frontend/src/app/(protected)/settings/page.tsx` | Replace hardcoded data with calls to `/settings/*` backend endpoints for policies/templates |
| Remove or isolate demo-data.ts | `frontend/src/lib/demo-data.ts` | Remove file once all consumers are wired to real APIs |

**Acceptance:** Zero pages displaying "Demo Preview — static data only". Finance summary returns correct monetary values.

---

### Sprint 2 — Collections & Financial Engine Completion (P0)

**Goal:** Complete the financial backbone. Collections and Finance engines are critical for operational use.

#### 2.1 Collections Engine Completion

| Task | File | Description |
|------|------|-------------|
| Implement aging engine | `collections/aging_engine.py` | Classify receivables into aging buckets (current, 30d, 60d, 90d, 90d+) |
| Implement receipt matching | `collections/receipt_matching.py` | Auto-match receipts to installments by contract, amount, date |
| Implement collection alerts | `collections/alerts.py` | Generate alerts for overdue receivables with escalation tiers |
| Add tests | `tests/collections/` | Engine unit tests + API integration tests |

#### 2.2 Finance Engine Completion

| Task | File | Description |
|------|------|-------------|
| Implement revenue recognition | `finance/revenue_recognition.py` | Stage-based (percentage of completion) and milestone-based recognition |
| Implement cashflow forecast engine | `finance/cashflow_forecast.py` | Complement existing cashflow module with finance-specific projections |
| Enhance finance API | `finance/api.py` | Add endpoints: `/finance/projects/{project_id}/summary/by-phase`, `/finance/projects/{project_id}/revenue-recognition` |
| Add tests | `tests/finance/` | Engine unit tests + API integration tests |

**Acceptance:** Collections aging engine produces real aging buckets. Finance summary includes revenue recognition output.

---

### Sprint 3 — Land & Feasibility Productization (P1)

**Goal:** Make Land and Feasibility modules fully operational with frontend pages.

#### 3.1 Land Module Productization

| Task | File | Description |
|------|------|-------------|
| Build Land frontend page | `frontend/src/app/(protected)/land/` | Parcels list, detail, assumptions, valuations |
| Build Land API client | `frontend/src/lib/land-api.ts` | API functions for parcels, assumptions, valuations |
| Add Land types | `frontend/src/lib/land-types.ts` | TypeScript interfaces matching backend schemas |
| Add Land to sidebar navigation | `frontend/src/components/shell/NavConfig.ts` | Add `/land` route to nav items |
| Implement valuation engine | `land/valuation_engine.py` | Comparable sales, income capitalization, cost approach methods |
| Implement residual calculator | `land/residual_calculator.py` | RLV = GDV − Total Development Costs − Developer Profit |
| Wire engines to service | `land/service.py` | Integrate engines into `create_valuation()` |
| Add tests | `tests/land/` | Engine unit tests + valuation scenarios |

#### 3.2 Feasibility Completion

| Task | File | Description |
|------|------|-------------|
| Build Feasibility frontend page | `frontend/src/app/(protected)/feasibility/` | Runs list, assumptions editor, results dashboard |
| Build Feasibility API client | `frontend/src/lib/feasibility-api.ts` | API functions for runs, assumptions, calculate, results |
| Add Feasibility types | `frontend/src/lib/feasibility-types.ts` | TypeScript interfaces matching backend schemas |
| Add Feasibility to sidebar navigation | `frontend/src/components/shell/NavConfig.ts` | Add `/feasibility` route to nav items |
| Implement proforma engine | `feasibility/proforma_engine.py` | Detailed pro forma with line-item cost breakdown |
| Implement IRR engine | `feasibility/irr_engine.py` | True IRR calculation using Newton-Raphson or bisection method |
| Implement break-even engine | `feasibility/break_even_engine.py` | Sales velocity break-even, cost break-even, price break-even |
| Implement scenario runner | `feasibility/scenario_runner.py` | Base/bull/bear scenario execution with parameter variation |
| Add tests | `tests/feasibility/` | Engine unit tests + scenario validation |

**Acceptance:** Land and Feasibility pages visible in sidebar. Parcels show automated valuations. Feasibility runs produce IRR and break-even analysis.

---

### Sprint 4 — Stub Cleanup & Engine Consolidation (P1)

**Goal:** Remove or implement all remaining stub files. Consolidate engine architecture.

#### 4.1 Pricing Engine Consolidation

| Task | File | Description |
|------|------|-------------|
| Implement premium rules | `pricing/premium_rules.py` | Configurable premium evaluation (floor bands, view categories, corner detection) |
| Implement override rules | `pricing/override_rules.py` | Authorization thresholds for manual price overrides |
| Remove or delegate legacy stub | `pricing/pricing_engine.py` | Replace 6-line stub with import delegation to `engines/pricing_engine.py` |
| Add tests | `tests/pricing/` | Premium rule unit tests, override authorization tests |

#### 4.2 Payment Plan Engine Consolidation

| Task | File | Description |
|------|------|-------------|
| Implement cashflow impact | `payment_plans/cashflow_impact.py` | Calculate projected cashflow impact of a payment plan |
| Remove or delegate schedule generator | `payment_plans/schedule_generator.py` | Stub superseded by `template_engine.py` — remove or delegate |
| Add tests | `tests/payment_plans/` | Cashflow impact unit tests |

#### 4.3 Production Verification

| Task | Description |
|------|-------------|
| Verify commission calculations in production | Confirm payout calculation produces correct values with real contract data |
| Verify cashflow forecasting in production | Confirm forecast modes produce correct period bucketing with real data |

**Acceptance:** Zero stub engine files remaining. All engines are either implemented or removed. Commission and cashflow verified with production data.

---

### Sprint 5 — Revenue Recognition & Price Escalation (P2)

**Goal:** Add revenue recognition and price escalation as distinct domains.

#### 5.1 Revenue Recognition Module

| Task | Description |
|------|-------------|
| Design revenue recognition model | Percentage-of-completion + milestone-based methods |
| Create database migration | `recognition_entries` table with contract_id, method, recognized_amount, period |
| Implement recognition engine | `finance/revenue_recognition.py` — full implementation |
| Add API endpoints | `GET /finance/projects/{project_id}/revenue-recognition`, `POST /finance/projects/{project_id}/revenue-recognition/calculate` |
| Build frontend section | Revenue recognition panel in Finance dashboard |
| Add tests | Engine + API + integration |

#### 5.2 Price Escalation Module

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

### Sprint 6 — Concept Planning & Cost Control (P2)

**Goal:** Add pre-development planning tools.

#### 6.1 Concept Planning Module

| Task | Description |
|------|-------------|
| Create `concept_planning` module | `app/modules/concept_planning/` |
| Design data model | Concept scenarios, unit mix analysis, density parameters |
| Create database migration | `concept_scenarios`, `unit_mix_options`, `density_analysis` tables |
| Implement scenario engine | Unit mix optimization, density analysis |
| Build frontend page | Scenario editor, comparison view |
| Add tests | Engine + API |

#### 6.2 Cost Planning & Tender Module

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

### Sprint 7 — Design Governance & Intelligence Layer (P3)

**Goal:** Add delivery governance and data-driven analytics capabilities.

#### 7.1 Design & Delivery Governance Module

| Task | Description |
|------|-------------|
| Create `design_governance` module | `app/modules/design_governance/` |
| Design data model | Stage gates, permits, consultant assignments, design reviews |
| Create database migration | `design_stage_gates`, `permits`, `consultant_assignments` tables |
| Implement governance engine | Stage gate validation, permit tracking |
| Wire to construction module | Governance gates must pass before construction milestones |
| Build frontend page | Stage gate dashboard, permit tracker |
| Add tests | Workflow + API |

#### 7.2 Analytics Module

| Task | Description |
|------|-------------|
| Create `analytics` module | `app/modules/analytics/` |
| Implement analytics engines | Sales velocity, absorption rate, price band analysis, payment plan effect analysis |
| Build aggregation queries | Project-level and portfolio-level analytics |
| Build frontend dashboards | Analytics dashboard with charts and KPIs |
| Add tests | Engine + query efficiency |

#### 7.3 Market Intelligence Module

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
| Sprint 1 complete | Financial credibility | Zero demo pages; finance summary validated with real data |
| Sprint 2 complete | Financial backbone | Collections aging + finance engines implemented |
| Sprint 3 complete | Full pre-dev pipeline | Land and Feasibility fully functional with UI |
| Sprint 4 complete | Zero stub files | All 17 stub engine files implemented or removed |
| Sprint 5 complete | Revenue compliance | Revenue recognition engine operational |
| Sprint 6 complete | Pre-dev tools | Concept planning and cost control live |
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
8. **Route convention consistency** — new endpoints follow existing patterns (e.g. `/finance/projects/{project_id}/...`)

---

*This roadmap prioritizes structural truth and operational credibility first, followed by domain completion, and finally new capabilities. It is based on a repository structural audit and does not incorporate production runtime validation — a deeper follow-up audit is required for production truth.*
