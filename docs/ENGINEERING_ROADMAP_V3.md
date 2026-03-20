Reach Developments Station --- Engineering Roadmap V3
Source: Platform Truth Audit (2026-03-20) Purpose: Canonical
roadmap derived from repo + production truth audit
---
Platform Status
Current stage: Late Structural Build → Early Operational Validation
Evidence from audit:
22 backend modules
46 database tables
202+ API endpoints
53 SQLAlchemy models
1203 passing tests
12 real frontend pages
3 demo‑stubbed pages
2 backend‑only domains
20 stubbed engine files
Estimated completion:
~70% MVP operational readiness
---
Strategic Goal of Roadmap V3
Move platform from:
Engineering Infrastructure → Operational Product
Focus areas:
Remove demo layers
Expose hidden domains
Ensure financial correctness
Introduce operational maturity
---
Phase 1 --- Product Reality Fix
Goal: Replace demo UI layers with real backend integrations.
PR‑1 --- Commission UI Wiring
Connect frontend commission page to commission API.
Scope: - Replace demoCommissionRows usage - Integrate
commission-api.ts - Implement payout listing - Display calculated
commission values
Definition of Done: - Commission page loads real data - No demo banner
present
---
PR‑2 --- Cashflow UI Wiring
Scope: - Replace demoCashflowPeriods - Integrate cashflow-api.ts -
Display forecast modes
Definition of Done: - Cashflow chart uses real API responses
---
PR‑3 --- Settings UI Wiring
Scope: - Connect settings page to settings-api.ts - Enable CRUD for: -
Pricing policies - Commission policies - Project templates
Definition of Done: - Settings editable through UI
---
PR‑4 --- Remove Demo Data Layer
Scope: - Remove demo-data.ts - Remove demo imports across project
Definition of Done: - No demo data used anywhere in frontend
---
Phase 2 --- Missing Product Domains
Goal: Expose backend-only domains to product UI.
PR‑5 --- Land Module UI
Pages: /land /land/[parcelId]
Features: - Parcel registry - Land assumptions - Valuation results
---
PR‑6 --- Feasibility Module UI
Pages: /feasibility /feasibility/[runId]
Features: - Feasibility run creation - Proforma outputs - IRR / margin
summary
---
PR‑7 --- Navigation Integration
Scope: - Add Land and Feasibility to sidebar navigation
Definition of Done: - Domains visible in platform navigation
---
Phase 3 --- Financial Correctness
Goal: Ensure financial outputs are reliable.
PR‑8 --- Project Currency Ownership
Changes: Add currency field to Project model.
Migration: add_project_currency
---
PR‑9 --- Currency Propagation
Ensure currency consistency across:
pricing
receivables
collections
construction costs
---
PR‑10 --- Revenue Recognition Engine
Implement: finance/revenue_recognition.py
Capabilities: - recognized revenue schedule - IFRS‑style recognition
logic
---
PR‑11 --- Collection Aging Engine
Implement: collections/aging_engine.py
Capabilities: - aging buckets - overdue classification
---
PR‑12 --- Cashflow Portfolio Aggregation
Add: - cross‑project cashflow forecast
---
Phase 4 --- Operational Maturity
Goal: Transform system into production‑grade operating platform.
PR‑13 --- Analytics Fact Layer
Introduce: - financial summary tables - precomputed portfolio metrics
---
PR‑14 --- Portfolio Dashboards
Dashboards:
portfolio revenue
sales velocity
construction progress
---
PR‑15 --- Audit Logging
Track:
contract edits
financial changes
pricing updates
---
PR‑16 --- Role Based Permissions
Implement:
roles
module permissions
approval gates
---
PR‑17 --- Data Integrity Monitoring
Introduce:
lifecycle validation checks
financial data audits
---
PR‑18 --- Performance Optimization
Focus areas:
large project queries
dashboard aggregation
---
PR‑19 --- Production Monitoring
Introduce:
structured logging
error monitoring
health metrics
---
Final Target State
Platform becomes:
Real Estate Development Operating System
Capabilities:
land acquisition intelligence
development lifecycle management
commercial operations
financial visibility
regulatory registration tracking
