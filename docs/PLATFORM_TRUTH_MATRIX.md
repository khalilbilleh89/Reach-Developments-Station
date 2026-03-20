# Reach Developments Station — Platform Truth Matrix

**Generated:** 2026-03-20  
**Source:** [PLATFORM_TRUTH_AUDIT.md](PLATFORM_TRUTH_AUDIT.md)

---

## Module-Level Truth Matrix

| Domain | Repo Presence | Data Model | API | Service Logic | Frontend | Production Truth | Analytics Readiness | Final Status |
|--------|--------------|------------|-----|---------------|----------|-----------------|--------------------:|-------------|
| **Auth** | ✅ 22 modules present | 3 models (User, Role, UserRole) | 3 endpoints | Implemented (JWT, hashing, roles) | Login page | Repo-present but unverified | N/A | **Implemented** |
| **Projects** | ✅ | 3 models (Project, AttrDef, AttrOption) | 13 endpoints | Implemented (hierarchy, attributes) | ✅ List + detail pages | Repo-present but unverified | Partially ready | **Strong** |
| **Phases** | ✅ | 1 model (Phase) | 7 endpoints | CRUD + sequencing | ✅ via project detail | Repo-present but unverified | Partially ready | **Strong** |
| **Buildings** | ✅ | 1 model (Building) | 6 endpoints | CRUD + validation | ✅ via project detail | Repo-present but unverified | Partially ready | **Strong** |
| **Floors** | ✅ | 1 model (Floor) | 6 endpoints | CRUD + sequencing | ✅ via project detail | Repo-present but unverified | Partially ready | **Strong** |
| **Units** | ✅ | 2 models (Unit, DynamicAttrValue) | 15 endpoints | Implemented (status rules, pricing adapter) | ✅ Units & Pricing page | Repo-present but unverified | Partially ready | **Strong** |
| **Pricing** | ✅ | 2 models (UnitPricingAttributes, UnitPricing) | 7 endpoints | Implemented (engine-coordinated) | ✅ via units page | Repo-present but unverified | Partially ready | **Strong** |
| **Pricing Attributes** | ✅ | 1 model (UnitQualitativeAttributes) | ❌ No api.py | CRUD only | ✅ via units page | Repo-present but unverified | Partially ready | **Partial** |
| **Sales** | ✅ | 3 models (Buyer, Reservation, SalesContract) | 14 endpoints | Implemented (lifecycle mgmt) | ✅ Sales page + detail | Repo-present but unverified | Partially ready | **Strong** |
| **Reservations** | ✅ | 1 model (UnitReservation) | 7 endpoints | Implemented (state machine) | ✅ via sales workflow | Repo-present but unverified | Partially ready | **Strong** |
| **Payment Plans** | ✅ | 2 models (Template, Schedule) | 11 endpoints | Implemented (engine-coordinated) | ✅ Payment Plans page | Repo-present but unverified | Partially ready | **Strong** |
| **Collections** | ✅ | 1 model (PaymentReceipt) | 4 endpoints | Implemented (concurrency-safe) | ✅ Collections page | Repo-present but unverified | Not ready (aging stub) | **Implemented but production-unverified** |
| **Receivables** | ✅ | 1 model (Receivable) | 5 endpoints | Implemented (cent-based) | ✅ Finance/Receivables page | Repo-present but unverified | Partially ready | **Strong** |
| **Finance** | ✅ | ❌ No models | 1 endpoint | Implemented (aggregation) | ✅ Finance dashboard | Production-visible but data-invalid (possible zero values) | Partially ready | **Partial** |
| **Commission** | ✅ | 4 models (Plan, Slab, Payout, PayoutLine) | 10 endpoints | **Implemented** (577 lines, slab calc) | ❌ Static demo data | **Contradicted by production evidence** | Partially ready | **Contradicted by production evidence** |
| **Cashflow** | ✅ | 2 models (Forecast, Period) | 5 endpoints | **Implemented** (357 lines, 3 modes) | ❌ Static demo data | **Contradicted by production evidence** | Partially ready | **Contradicted by production evidence** |
| **Sales Exceptions** | ✅ | 1 model (SalesException) | 7 endpoints | CRUD + approval | ✅ via finance dashboard | Repo-present but unverified | Partially ready | **Implemented but production-unverified** |
| **Registry** | ✅ | 3 models (Case, Milestone, Document) | 10 endpoints | Implemented (conveyancing) | ✅ Registry page | Repo-present but unverified | Partially ready | **Strong** |
| **Construction** | ✅ | 5 models (Scope, Milestone, Progress, Engineering, Cost) | 25 endpoints | Implemented (dashboard aggregation) | ✅ Construction page | Repo-present but unverified | Partially ready | **Strong** |
| **Land** | ✅ | 3 models (Parcel, Assumptions, Valuation) | 8 endpoints | Implemented (underwriting) | ❌ No page, no nav entry | **Contradicted by production evidence** | Not ready | **Repo-present but unverified in production** |
| **Feasibility** | ✅ | 3 models (Run, Assumptions, Result) | 8 endpoints | Implemented (engine-coordinated) | ❌ No page, no nav entry | **Contradicted by production evidence** | Not ready | **Repo-present but unverified in production** |
| **Settings** | ✅ | 3 models (PricingPolicy, CommissionPolicy, ProjectTemplate) | 15 endpoints | Implemented (single-default) | ❌ Static demo data | **Contradicted by production evidence** | N/A | **Contradicted by production evidence** |

---

## Data Chain Truth Matrix

| Chain | Description | Structural | API | Frontend | Production | Final Status |
|-------|-------------|-----------|-----|----------|------------|-------------|
| **A** | Project → Phase → Building → Floor → Unit | ✅ | ✅ | ✅ | Unverified | **End-to-end structural but production-unverified** |
| **B** | Unit → Pricing Attributes → Calculation → Readiness | ✅ | ✅ | ✅ | Unverified | **End-to-end structural but production-unverified** |
| **C** | Unit → Reservation → Contract → Sold Status | ✅ | ✅ | ✅ | Unverified | **End-to-end structural but production-unverified** |
| **D** | Contract → Payment Plan → Installments → Receivables → Receipts | ✅ | ✅ | ✅ | Unverified | **Partially implemented** (aging/alerts/matching stubbed) |
| **E** | Contracts + Collections → Finance Summary | Partial | ✅ | ✅ | Possibly zero values | **Partially implemented** (no revenue recognition) |
| **F** | Payment Schedules + Collections → Cashflow | ✅ | ✅ | ❌ Demo | Contradicted | **Structurally present but operationally broken** |
| **G** | Contract → Commission Plan/Slab → Payout → Audit Trail | ✅ | ✅ | ❌ Demo | Contradicted | **Structurally present but operationally broken** |

---

## Engine Implementation Matrix

| Engine | File | Status | Referenced | Lines |
|--------|------|--------|-----------|-------|
| Pricing calculation | pricing/engines/pricing_engine.py | ✅ **Implemented** | pricing/service.py | 103 |
| Feasibility calculation | feasibility/engines/feasibility_engine.py | ✅ **Implemented** | feasibility/service.py | 151 |
| Schedule generation | payment_plans/template_engine.py | ✅ **Implemented** | payment_plans/service.py | 185 |
| Unit status machine | units/status_rules.py | ✅ **Implemented** | units/service.py | 46 |
| Unit pricing adapter | units/pricing_adapter.py | ⚠️ **Partial** | units/service.py | 59 |
| Aging analysis | collections/aging_engine.py | ❌ **Stubbed** | None | 7 |
| Collection alerts | collections/alerts.py | ❌ **Stubbed** | None | 8 |
| Receipt matching | collections/receipt_matching.py | ❌ **Stubbed** | None | 6 |
| Land valuation | land/valuation_engine.py | ❌ **Stubbed** | None | 6 |
| Residual calculator | land/residual_calculator.py | ❌ **Stubbed** | None | 6 |
| Break-even | feasibility/break_even_engine.py | ❌ **Stubbed** | None | 6 |
| IRR calculation | feasibility/irr_engine.py | ❌ **Stubbed** | None | 6 |
| Proforma engine | feasibility/proforma_engine.py | ❌ **Stubbed** | None | 6 |
| Schedule generator | payment_plans/schedule_generator.py | ❌ **Stubbed** | None | 7 |
| Cashflow impact | payment_plans/cashflow_impact.py | ❌ **Stubbed** | None | 6 |
| Pricing engine (dup) | pricing/pricing_engine.py | ❌ **Stubbed** | None | 7 |
| Override rules | pricing/override_rules.py | ❌ **Stubbed** | None | 9 |
| Premium rules | pricing/premium_rules.py | ❌ **Stubbed** | None | 6 |
| Cashflow forecast | finance/cashflow_forecast.py | ❌ **Stubbed** | None | 6 |
| Financial summary | finance/project_financial_summary.py | ❌ **Stubbed** | None | 11 |
| Revenue recognition | finance/revenue_recognition.py | ❌ **Stubbed** | None | 6 |
| Contract rules | sales/contract_rules.py | ❌ **Stubbed** | None | 6 |
| Reservation rules | sales/reservation_rules.py | ❌ **Stubbed** | None | 8 |
| Phase rules | phases/rules.py | ❌ **Stubbed** | None | 6 |
| Project rules | projects/rules.py | ❌ **Stubbed** | None | 6 |

**Implemented: 4 | Partial: 1 | Stubbed: 20**

---

## Frontend Wiring Matrix

| Frontend Page | Backend Module(s) | API Wrapper | Wired | Status |
|---------------|-------------------|-------------|-------|--------|
| /dashboard | finance, sales_exceptions, registry, cashflow, commission | dashboard-api.ts | ✅ Real | Implemented |
| /projects | projects, phases, buildings, floors | projects-api.ts + hierarchy APIs | ✅ Real | Implemented |
| /construction | construction | construction-api.ts | ✅ Real | Implemented |
| /units-pricing | units, pricing, pricing_attributes | units-api.ts | ✅ Real | Implemented |
| /sales | sales, reservations | sales-api.ts | ✅ Real | Implemented |
| /payment-plans | payment_plans | payment-plans-api.ts | ✅ Real | Implemented |
| /collections | payment_plans, collections | payment-plans-api.ts | ✅ Real | Implemented |
| /finance | finance, sales_exceptions, registry, cashflow, commission | finance-dashboard-api.ts | ✅ Real | Implemented |
| /finance/receivables | receivables | receivables-api.ts | ✅ Real | Implemented |
| /registry | registry | registry-api.ts | ✅ Real | Implemented |
| /commission | commission | ❌ Uses demo-data.ts | ❌ Static | **Stubbed** |
| /cashflow | cashflow | ❌ Uses demo-data.ts | ❌ Static | **Stubbed** |
| /settings | settings | settings-api.ts exists but unused | ❌ Hardcoded | **Stubbed** |
| /land | land | N/A | N/A | **Missing** |
| /feasibility | feasibility | N/A | N/A | **Missing** |

---

## Summary Statistics

| Metric | Count |
|--------|-------|
| Backend modules | 22 |
| Database tables | 46 |
| API endpoints | 202+ |
| Implemented services | 15 (with real logic) + 7 (CRUD) |
| Implemented engines | 4 |
| Stubbed engine files | 20 |
| Frontend pages | 17 total: 12 real, 3 stubbed, 2 missing |
| Migration files | 30 (0001-0031, no 0015) |
| Test files | 73 |
| Passing tests | 1,203 |
| Demo data file | 1 (demo-data.ts with 4 datasets) |
