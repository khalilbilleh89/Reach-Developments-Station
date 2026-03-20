# Reach Developments Station — Roadmap From Truth Audit

**Generated:** 2026-03-20  
**Source:** [PLATFORM_TRUTH_AUDIT.md](PLATFORM_TRUTH_AUDIT.md) and [PLATFORM_TRUTH_MATRIX.md](PLATFORM_TRUTH_MATRIX.md)

---

## Roadmap Principles

This roadmap is derived exclusively from the truth audit findings. It separates work into three categories:

1. **Structural Completion** — missing or partial core domains
2. **Operational Truth** — broken summaries, hardcoded currency, demo/static surfaces, invalid financial outputs
3. **Expansion Domains** — concept planning, tender, analytics, AI

Priority ordering follows the audit's evidence-based assessment of impact.

---

## Wave 1 — Finance Truth & Operational Integrity

**Objective:** Make financial outputs commercially trustworthy.

### PR-W1.1 — Finance Summary Hardening

| Field | Value |
|-------|-------|
| **PR Code** | PR-W1.1 |
| **Title** | Harden finance summary with multi-period breakdowns and revenue recognition |
| **Objective** | Extend the 1-endpoint finance module to produce trustworthy, multi-period financial summaries |
| **Why this wave** | Finance truth is the #1 priority — zero monetary values in production undermine trust |
| **Major scope** | Implement `project_financial_summary.py` engine; add period-level breakdown endpoint; add revenue recognition logic from `revenue_recognition.py` stub; add project-level currency field |
| **Exclusions** | Portfolio-level analytics; star-schema reporting; tax calculations |
| **Dependencies** | Contracts and collections data must exist in production |
| **Definition of done** | Finance summary returns non-zero values for projects with contracts; revenue recognition produces recognized vs deferred breakdown; tests cover edge cases (zero contracts, over-collection) |

### PR-W1.2 — Currency Propagation

| Field | Value |
|-------|-------|
| **PR Code** | PR-W1.2 |
| **Title** | Add project-level currency and propagate to all financial domains |
| **Objective** | Establish project as the currency source-of-truth; propagate to pricing, sales, receivables, collections |
| **Why this wave** | Currency inconsistency blocks reliable financial aggregation and analytics |
| **Major scope** | Add `currency` field to Project model (migration); update pricing, receivables, collections services to inherit project currency; update frontend formatCurrency to use project currency |
| **Exclusions** | Multi-currency conversion; FX rate management |
| **Dependencies** | None |
| **Definition of done** | Project has currency field; child records inherit project currency; frontend displays correct currency per project; no hardcoded "AED" in demo pages |

---

## Wave 2 — Demo/Static Elimination

**Objective:** Wire all stubbed frontend pages to their fully implemented backends.

### PR-W2.1 — Commission Frontend Wiring

| Field | Value |
|-------|-------|
| **PR Code** | PR-W2.1 |
| **Title** | Wire commission page to backend API, remove demo data |
| **Objective** | Replace static `demoCommissionRows` with real API calls to commission backend |
| **Why this wave** | Commission backend is fully implemented (577 lines); frontend is the only blocker |
| **Major scope** | Create `commission-api.ts` wrapper; update commission/page.tsx to call list_project_plans, list_project_payouts, get_project_summary endpoints; remove demo banner; add project selector |
| **Exclusions** | New commission calculation features; commission report export |
| **Dependencies** | PR-W1.2 (currency propagation for display) |
| **Definition of done** | Commission page shows real data from backend; demo banner removed; empty state handled; project selector works |

### PR-W2.2 — Cashflow Frontend Wiring

| Field | Value |
|-------|-------|
| **PR Code** | PR-W2.2 |
| **Title** | Wire cashflow page to backend API, remove demo data |
| **Objective** | Replace static `demoCashflowPeriods` with real API calls to cashflow backend |
| **Why this wave** | Cashflow backend is fully implemented (357 lines, 3 forecast modes); frontend is the only blocker |
| **Major scope** | Create `cashflow-api.ts` wrapper (or use existing); update cashflow/page.tsx to call list_project_forecasts, get_forecast, list_forecast_periods; remove demo banner; add forecast creation form |
| **Exclusions** | Advanced cashflow analytics; what-if scenarios |
| **Dependencies** | PR-W1.2 (currency propagation) |
| **Definition of done** | Cashflow page shows real forecasts; demo banner removed; empty state handled; can create new forecast |

### PR-W2.3 — Settings Frontend Wiring

| Field | Value |
|-------|-------|
| **PR Code** | PR-W2.3 |
| **Title** | Wire settings page to backend API, remove hardcoded data |
| **Objective** | Replace hardcoded org settings with real settings API calls |
| **Why this wave** | Settings backend has 15 endpoints; `settings-api.ts` wrapper already exists but is unused |
| **Major scope** | Update settings/page.tsx to call list_pricing_policies, list_commission_policies, list_project_templates; add CRUD forms for policies; remove inline hardcoded data |
| **Exclusions** | Organization-level settings (company name, region); user preferences |
| **Dependencies** | None |
| **Definition of done** | Settings page shows real policies from backend; CRUD operations work; hardcoded data removed |

---

## Wave 3 — Collections Completion

**Objective:** Complete the collections domain with aging, alerts, and receipt matching.

### PR-W3.1 — Collections Aging Engine

| Field | Value |
|-------|-------|
| **PR Code** | PR-W3.1 |
| **Title** | Implement receivables aging analysis engine |
| **Objective** | Implement `aging_engine.py` to calculate aging buckets (Current, 1-30, 31-60, 61-90, 90+ days) |
| **Why this wave** | Collections aging is critical for financial reporting; stub exists but no logic |
| **Major scope** | Implement aging calculation from receivable due dates; add aging summary endpoint; add aging display to collections and finance pages |
| **Exclusions** | Automated collection actions; legal escalation workflows |
| **Dependencies** | Receivables must be generated for contracts |
| **Definition of done** | Aging engine produces correct bucket distributions; aging endpoint returns summary; tests cover boundary dates |

### PR-W3.2 — Collection Alerts & Receipt Matching

| Field | Value |
|-------|-------|
| **PR Code** | PR-W3.2 |
| **Title** | Implement collection alerts and receipt matching |
| **Objective** | Implement `alerts.py` (overdue thresholds) and `receipt_matching.py` (match payments to receivables) |
| **Why this wave** | Completes the collections lifecycle from aging through alerts to resolution |
| **Major scope** | Alert rules (7-day, 30-day thresholds); receipt-to-receivable matching logic; update collections page |
| **Exclusions** | Email/SMS notification delivery; payment gateway integration |
| **Dependencies** | PR-W3.1 (aging engine) |
| **Definition of done** | Alerts fire at configured thresholds; receipts automatically matched to open receivables; tests cover edge cases |

---

## Wave 4 — Land Productization

**Objective:** Make Land Intelligence a user-facing domain.

### PR-W4.1 — Land Frontend Pages

| Field | Value |
|-------|-------|
| **PR Code** | PR-W4.1 |
| **Title** | Build Land Intelligence frontend pages and add to navigation |
| **Objective** | Create frontend pages for land parcel management, assumptions, and valuations |
| **Why this wave** | Land backend (8 endpoints, 3 models) is fully implemented but invisible to users |
| **Major scope** | Create `land-api.ts` wrapper; create /land page with parcel grid; create parcel detail page with assumptions and valuations tabs; add Land to sidebar navigation |
| **Exclusions** | Map integration; GIS overlays; market comparables |
| **Dependencies** | None |
| **Definition of done** | Land appears in sidebar; parcels listable/creatable; assumptions and valuations manageable; empty state handled |

### PR-W4.2 — Land Valuation Engine Completion

| Field | Value |
|-------|-------|
| **PR Code** | PR-W4.2 |
| **Title** | Implement valuation engine and residual calculator |
| **Objective** | Replace stub `valuation_engine.py` and `residual_calculator.py` with real calculation engines |
| **Why this wave** | Service currently calculates inline; engine formalization improves testability and maintainability |
| **Major scope** | Implement RLV = GDV - Total Development Costs - Developer Profit formula in engine; add sensitivity analysis; add valuation comparison endpoints |
| **Exclusions** | Third-party valuation data import; market comparables database |
| **Dependencies** | PR-W4.1 (frontend pages) |
| **Definition of done** | Valuation engine produces correct RLV; tests cover multiple scenarios; frontend displays calculated values |

---

## Wave 5 — Feasibility Completion

**Objective:** Make Feasibility a user-facing domain.

### PR-W5.1 — Feasibility Frontend Pages

| Field | Value |
|-------|-------|
| **PR Code** | PR-W5.1 |
| **Title** | Build Feasibility Study frontend pages and add to navigation |
| **Objective** | Create frontend pages for feasibility run management, assumptions input, and results display |
| **Why this wave** | Feasibility backend (8 endpoints, engine) is fully implemented but invisible to users |
| **Major scope** | Create `feasibility-api.ts` wrapper; create /feasibility page with run grid; create run detail with assumptions form and results display; add Feasibility to sidebar navigation |
| **Exclusions** | Monte Carlo simulation; market-driven assumptions |
| **Dependencies** | None |
| **Definition of done** | Feasibility appears in sidebar; runs listable/creatable; assumptions editable; calculation triggerable; results displayed |

### PR-W5.2 — Feasibility Advanced Engines

| Field | Value |
|-------|-------|
| **PR Code** | PR-W5.2 |
| **Title** | Implement break-even, IRR, and proforma engines |
| **Objective** | Replace stub engines with real implementations for advanced feasibility analysis |
| **Why this wave** | Core engine exists; advanced engines extend capability for professional-grade feasibility |
| **Major scope** | Implement `break_even_engine.py` (minimum unit count for cost coverage); implement proper `irr_engine.py` (NPV-based IRR from cashflow projections); update proforma_engine.py |
| **Exclusions** | Scenario comparison; sensitivity charts; Monte Carlo |
| **Dependencies** | PR-W5.1 (frontend), PR-W1.2 (currency) |
| **Definition of done** | Break-even and IRR calculations produce correct results; integrated into feasibility results display |

---

## Wave 6 — Pricing & Sales Readiness Hardening

**Objective:** Complete remaining pricing/sales engines and rules.

### PR-W6.1 — Pricing Override & Premium Rules

| Field | Value |
|-------|-------|
| **PR Code** | PR-W6.1 |
| **Title** | Implement price override authorization and premium rule evaluation |
| **Objective** | Replace stub `override_rules.py` (authorization thresholds) and `premium_rules.py` (configurable premiums) |
| **Why this wave** | Pricing engine works but override governance and configurable premium rules are missing |
| **Major scope** | Override authorization (≤2% Sales Manager, ≤5% Director, >5% CEO); configurable premium rule sets from settings |
| **Exclusions** | Dynamic pricing; market-based pricing; time-based promotions |
| **Dependencies** | PR-W2.3 (Settings for configurable policies) |
| **Definition of done** | Override requests validated against authorization thresholds; premium rules evaluatable from configuration |

### PR-W6.2 — Sales Contract & Reservation Rules

| Field | Value |
|-------|-------|
| **PR Code** | PR-W6.2 |
| **Title** | Implement sales contract and reservation business rules |
| **Objective** | Replace stub `contract_rules.py` and `reservation_rules.py` with enforceable business rules |
| **Why this wave** | Sales lifecycle works but lacks formal business rule enforcement |
| **Major scope** | Contract creation/activation/cancellation rules; reservation expiry logic; one-active-reservation guard formalization |
| **Exclusions** | Legal document generation; e-signature integration |
| **Dependencies** | None |
| **Definition of done** | Business rules enforced on contract and reservation state changes; tests cover rule violations |

---

## Wave 7 — Commission Live Verification

**Objective:** Verify commission calculations produce correct results in production.

### PR-W7.1 — Commission End-to-End Verification

| Field | Value |
|-------|-------|
| **PR Code** | PR-W7.1 |
| **Title** | Commission calculation verification and production data validation |
| **Objective** | Verify that commission plans, slabs, and payouts produce correct results with production data |
| **Why this wave** | Commission backend is fully implemented; after PR-W2.1 wires frontend, verification needed |
| **Major scope** | Integration tests with realistic scenarios; production payout reconciliation endpoint; commission report export |
| **Exclusions** | Payout integration with payroll systems |
| **Dependencies** | PR-W2.1 (Commission frontend wiring) |
| **Definition of done** | Commission calculations verified against manual calculations; integration tests cover marginal and cumulative modes; report exportable |

---

## Wave 8 — Cashflow Truth Validation

**Objective:** Validate cashflow forecasts against actual collection data.

### PR-W8.1 — Cashflow Forecast Validation & Reconciliation

| Field | Value |
|-------|-------|
| **PR Code** | PR-W8.1 |
| **Title** | Cashflow forecast validation against actuals and portfolio aggregation |
| **Objective** | Add variance analysis (forecast vs actual) and cross-project cashflow aggregation |
| **Why this wave** | After PR-W2.2 wires frontend, forecasts need validation and portfolio-level views |
| **Major scope** | Forecast vs actual variance tracking; implement `cashflow_impact.py` for payment plan impact analysis; add portfolio-level cashflow aggregation endpoint |
| **Exclusions** | What-if scenario modeling; external cash position integration |
| **Dependencies** | PR-W2.2 (Cashflow frontend wiring), PR-W1.2 (currency) |
| **Definition of done** | Variance analysis shows forecast accuracy; portfolio cashflow aggregatable across projects |

---

## Wave 9 — Revenue Recognition & Price Escalation

**Objective:** Implement accounting-grade revenue recognition and price escalation.

### PR-W9.1 — Revenue Recognition Engine

| Field | Value |
|-------|-------|
| **PR Code** | PR-W9.1 |
| **Title** | Implement revenue recognition from stub |
| **Objective** | Replace `revenue_recognition.py` stub with IFRS/IAS-aligned revenue recognition logic |
| **Why this wave** | Finance truth requires recognized vs deferred revenue breakdown |
| **Major scope** | Percentage-of-completion recognition; contract-based recognition rules; recognized/deferred revenue per contract and per project |
| **Exclusions** | Full IFRS 15 compliance; audit trail for recognition events |
| **Dependencies** | PR-W1.1 (Finance summary hardening) |
| **Definition of done** | Revenue recognition produces recognized and deferred amounts per contract; integrated into finance summary |

### PR-W9.2 — Price Escalation Engine

| Field | Value |
|-------|-------|
| **PR Code** | PR-W9.2 |
| **Title** | Implement price escalation logic |
| **Objective** | Add time-based or milestone-based price escalation for unsold inventory |
| **Why this wave** | Sales readiness requires price escalation for inventory management |
| **Major scope** | Escalation rules engine; scheduled price increases; escalation audit trail |
| **Exclusions** | Market-driven dynamic pricing; competitor analysis |
| **Dependencies** | PR-W6.1 (Pricing rules) |
| **Definition of done** | Price escalation rules configurable; escalation events logged; tests cover escalation scenarios |

---

## Wave 10 — Concept Planning & Cost Planning

**Objective:** New expansion domains for project lifecycle.

### PR-W10.1 — Concept Planning Module

| Field | Value |
|-------|-------|
| **PR Code** | PR-W10.1 |
| **Title** | Build concept planning module for pre-feasibility stage |
| **Objective** | Create a concept planning domain for initial project ideation before feasibility |
| **Why this wave** | Expansion domain — fills gap between land acquisition and feasibility |
| **Major scope** | Concept models (site brief, massing study, product mix); CRUD API; frontend page |
| **Exclusions** | 3D visualization; BIM integration |
| **Dependencies** | PR-W4.1 (Land), PR-W5.1 (Feasibility) |
| **Definition of done** | Concept plans creatable and linkable to land parcels; transitions to feasibility runs |

### PR-W10.2 — Cost Planning & Tender Module

| Field | Value |
|-------|-------|
| **PR Code** | PR-W10.2 |
| **Title** | Build cost planning and tender management module |
| **Objective** | Formalize construction cost planning and tender/procurement management |
| **Why this wave** | Construction module exists but lacks formal cost planning and tender workflows |
| **Major scope** | Cost plan models; tender package management; bid comparison; award tracking |
| **Exclusions** | E-procurement; vendor portal; invoice management |
| **Dependencies** | Construction module |
| **Definition of done** | Cost plans creatable per scope; tender packages manageable; bid comparison functional |

---

## Wave 11 — Design & Delivery Governance

**Objective:** Governance frameworks for design review and delivery milestones.

### PR-W11.1 — Design & Delivery Governance Module

| Field | Value |
|-------|-------|
| **PR Code** | PR-W11.1 |
| **Title** | Build design review and delivery governance workflows |
| **Objective** | Add design stage-gate reviews and delivery milestone governance |
| **Why this wave** | Connects feasibility→construction lifecycle with governance checkpoints |
| **Major scope** | Stage-gate models; review workflows; approval chains; delivery milestones |
| **Exclusions** | Document management system; BIM model reviews |
| **Dependencies** | PR-W10.1 (Concept planning) |
| **Definition of done** | Stage-gate reviews trackable; approvals enforceable; milestone governance active |

---

## Wave 12 — Analytics

**Objective:** Build reporting and analytics layer on the operational platform.

### PR-W12.1 — Analytics Foundation

| Field | Value |
|-------|-------|
| **PR Code** | PR-W12.1 |
| **Title** | Build analytics layer with dimensional reporting |
| **Objective** | Create pre-aggregated analytics views for executive reporting |
| **Why this wave** | Only after operational truth is established (Waves 1-9) should analytics be built |
| **Major scope** | Project financial dashboard; portfolio analytics; sales funnel analysis; collections aging reports; cashflow variance reports |
| **Exclusions** | BI tool integration; data warehouse; ML/AI predictions |
| **Dependencies** | Waves 1-9 (operational truth established) |
| **Definition of done** | Project-level financial dashboard with real data; portfolio-level aggregation; sales funnel visualization |

---

## Wave 13 — Market Intelligence & Document Intelligence

**Objective:** Advanced intelligence features.

### PR-W13.1 — Market Intelligence

| Field | Value |
|-------|-------|
| **PR Code** | PR-W13.1 |
| **Title** | Build market intelligence module |
| **Objective** | Integrate market data for pricing benchmarks, area analysis, and demand indicators |
| **Why this wave** | Expansion domain — requires stable operational platform first |
| **Major scope** | Market data models; pricing benchmark comparisons; area-level analytics |
| **Exclusions** | Real-time data feeds; automated pricing adjustments |
| **Dependencies** | PR-W12.1 (Analytics foundation) |
| **Definition of done** | Market benchmarks viewable per project; pricing comparison available |

### PR-W13.2 — Document Intelligence

| Field | Value |
|-------|-------|
| **PR Code** | PR-W13.2 |
| **Title** | Build document intelligence and management module |
| **Objective** | Add document management, generation, and AI-assisted document analysis |
| **Why this wave** | Expansion domain — requires stable registry and contract workflows first |
| **Major scope** | Document storage; template-based generation; OCR/AI extraction for registration documents |
| **Exclusions** | Full DMS; version control; collaborative editing |
| **Dependencies** | Registry module, Sales module |
| **Definition of done** | Documents attachable to contracts/cases; templates generate contracts; basic AI extraction functional |

---

## Roadmap Summary

| Wave | Theme | PRs | Priority Basis |
|------|-------|-----|---------------|
| 1 | Finance truth | W1.1, W1.2 | Finance must be trustworthy first |
| 2 | Demo elimination | W2.1, W2.2, W2.3 | 3 pages showing fake data despite working backends |
| 3 | Collections completion | W3.1, W3.2 | Financial lifecycle gap — aging/alerts missing |
| 4 | Land productization | W4.1, W4.2 | Backend-only domain invisible to users |
| 5 | Feasibility completion | W5.1, W5.2 | Backend-only domain invisible to users |
| 6 | Pricing/Sales hardening | W6.1, W6.2 | Business rule enforcement missing |
| 7 | Commission verification | W7.1 | Backend live but unverified with production data |
| 8 | Cashflow validation | W8.1 | Forecast accuracy unproven |
| 9 | Revenue recognition & escalation | W9.1, W9.2 | Accounting-grade outputs required |
| 10 | Concept & cost planning | W10.1, W10.2 | New expansion domains |
| 11 | Design governance | W11.1 | Lifecycle governance |
| 12 | Analytics | W12.1 | Built on operational truth |
| 13 | Intelligence | W13.1, W13.2 | Advanced features |
