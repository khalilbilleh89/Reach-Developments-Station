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

**Modules (conceptual):** Pricing (pricing, pricing_attributes), Sales, Reservations, Payment Plans, Commissions, Sales Exceptions & Incentives

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
├── Analytics / Finance Summary  (Project / Portfolio level)
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

_The Registry module is a cross-cutting capability that intentionally spans multiple architecture layers and is modeled outside the primary nine-layer stack._

### Settings Module

- Pricing policies
- Commission policies
- Project templates
- Architecture layer: **System-level / cross-cutting** (applies across all feature modules)

---

## System Boundaries

### Cross-Layer Rules

All cross-layer logic must pass through service layers. While `docs/SYSTEM_RULES.md` generally describes direct cross-module data manipulation as *discouraged*, this architecture document tightens that rule for this platform: direct database manipulation across layers is **forbidden**.

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

---

## Currency Source-of-Truth Rules (PR-CURRENCY-002)

### Canonical Default Currency

The platform canonical default currency is `AED` (UAE Dirham).

All currency defaults — in ORM models, Pydantic schemas, and migration
backfills — must be sourced from `app.core.constants.currency.DEFAULT_CURRENCY`.
Inline string literals such as `"AED"` must not appear in model column defaults
or schema field defaults. Import the constant instead.

### Project Base Currency

Every `Project` record carries a `base_currency` field (ISO 4217, e.g. "AED").
This field is the governing currency for all financial records linked to the
project. Downstream services and aggregators should use this field when they
need to verify or group financial values for a project.

### Monetary Record Denomination Rule

Every table storing monetary amounts must carry an explicit `currency` column
(VARCHAR 10, NOT NULL, DEFAULT canonical constant). The following tables now
carry explicit currency denomination:

| Table | Column | Coverage |
|---|---|---|
| projects | base_currency | project governing currency |
| sales_contracts | currency | contract_price denomination |
| payment_schedules | currency | due_amount denomination |
| payment_receipts | currency | amount_received denomination |
| commission_payouts | currency | gross_sale_value denomination |
| commission_payout_lines | currency | amount denomination |
| feasibility_assumptions | currency | price/cost input denomination |
| feasibility_results | currency | gdv/total_cost/profit denomination |
| financial_scenario_runs | currency | npv/gross_profit denomination |
| land_parcels | currency | acquisition_price denomination (non-nullable) |
| land_valuations | currency | gdv/residual_value denomination |
| sales_exceptions | currency | base_price/discount denomination |
| construction_cost_comparison_sets | currency | comparison line denomination |
| cashflow_forecast_periods | currency | inflow/outflow denomination |

### Rules

1. **No inline currency strings** — Never hardcode `"AED"` (or any ISO code)
   as a Python default value in ORM models or schemas. Always import
   `DEFAULT_CURRENCY` from `app.core.constants.currency`.

2. **New monetary tables must include currency** — Any new table with monetary
   columns must include a `currency VARCHAR(10) NOT NULL DEFAULT 'AED'` column
   at creation time. This is not a backlog item; it is a schema creation rule.

3. **Base currency is informational for now** — In PR-CURRENCY-002, `base_currency`
   and per-record `currency` fields are source-of-truth data. Calculation
   enforcement (rejecting mixed-currency aggregation) and FX conversion are
   deferred to PR-CURRENCY-003 and later.

4. **No FX conversion in this scope** — PR-CURRENCY-002 does not introduce
   exchange rate tables, FX conversion services, or automatic normalization.
   A single-currency-per-project discipline is the intended operating model.

---

## Currency Runtime Enforcement Rules (PR-CURRENCY-003)

### Calculation Contract Denomination Rule

All monetary input dataclasses in the Calculation Engine
(`PricingInputs`, `ReturnInputs`, `LandInputs`, `CashflowInputs`) and
the Feasibility Engine (`FeasibilityInputs`) must carry an explicit
`currency` field.  Corresponding output dataclasses propagate this
field so every monetary result is unambiguously denominated.

**Rule:** Any code that calls a Calculation Engine or Feasibility Engine
composite runner must supply a `currency` value. Callers that omit
`currency` receive the platform default (`DEFAULT_CURRENCY`) but must
not silently discard the output denomination.

### Aggregation Guard Rule

Backend services and repositories must never return a single raw
monetary total that sums across records of different currencies.
Permitted approaches are:

- **Filter** — query only records matching a known base currency (e.g.
  the project's `base_currency`).
- **Group** — return a structured response where totals are keyed by
  currency (e.g. `{ "AED": 1_200_000, "USD": 500_000 }`).
- **Reject** — raise a 422 error when mixed-currency inputs are
  detected and no currency filter has been specified.

**Forbidden:** summing `SUM(amount)` or similar across rows that carry
different `currency` values and returning the result as a single scalar
without currency annotation.

### Project Base Currency Enforcement Rule

Financial summary endpoints scoped to a single project
(e.g. `GET /projects/{id}/finance`) must:

1. Read the project's `base_currency` field.
2. Include `currency` in the response payload so callers know the
   denomination of all returned monetary totals.
3. Aggregate only records denominated in that currency, or return a
   clearly grouped structure if mixed-currency records exist.

### Receivable Generation Continuity Rule

When generating receivables from a contract's payment schedule, all
installment records must share the same currency as the parent
contract.  Mismatched installment currencies must raise a 422 error
before any receivables are created.

**Rationale:** receivables feed finance summaries and portfolio
aggregations.  Silently propagating a wrong denomination into those
surfaces produces incorrect financial totals with no visible error.

### No FX Conversion in This Scope

PR-CURRENCY-003 does not introduce exchange-rate tables, FX conversion
services, or automatic normalization.  Its sole purpose is to make
unsafe arithmetic fail explicitly rather than silently.  FX conversion
is deferred to a future PR.

---

## Currency Governance Rules (PR-CURRENCY-005)

### Authoritative Supported Currency List

The backend is the single source of truth for the platform's supported
currency list.  The canonical list lives in
`app/core/constants/currency.py` as `SUPPORTED_CURRENCIES`.

**Rule:** Frontend components must not maintain their own hardcoded
currency list that could diverge from the backend.  Use the static
constants in `frontend/src/lib/currency-constants.ts` for synchronous
access (type guards, form validation), and keep that file in sync with
the backend constants in the same PR whenever the list changes.

**Backend API:** `GET /api/v1/system/currencies` exposes the
authoritative currency configuration at runtime:

```json
{
  "default_currency": "AED",
  "supported_currencies": ["AED", "JOD", "USD", "EUR"]
}
```

### Base Currency Immutability Rule

A project's `base_currency` is immutable once financial records have
been linked to it.  Attempting to change `base_currency` via
`PATCH /api/v1/projects/{id}` after any of the following records exist
will return HTTP 400:

- Scenarios (`scenarios.project_id`)
- Feasibility runs (`feasibility_runs.project_id`)
- Construction cost records (`construction_cost_records.project_id`)
- Land parcels (`land_parcels.project_id`)

**Rationale:** changing the governing currency of a project after
financial data exists would silently invalidate all monetary totals,
aggregation guards, and portfolio roll-ups for that project.

### Currency Audit Tools

Two tools are provided to detect currency anomalies in persisted data:

1. **Admin API endpoint** — `GET /api/v1/admin/currency-audit`
   Returns a structured JSON report of all detected anomalies.

2. **CLI tool** — `scripts/currency_audit.py`
   Runs the same scan and prints a human-readable summary.  Exits with
   code 0 if clean, 1 if issues are found.

#### Issue Types Detected

| Type | Description |
|---|---|
| `mismatch` | `record.currency` ≠ `project.base_currency` |
| `suspicious_default` | `record.currency` is the platform default but `project.base_currency` is not — suggests the record was not initialised with the project's currency |
| `null_currency` | `record.currency` is NULL or empty |

#### Tables Scanned

- `feasibility_assumptions` (via `feasibility_runs.project_id`)
- `construction_cost_records`
- `construction_cost_comparison_sets`
- `land_parcels`
- `financial_scenario_runs` (via `scenarios.project_id`)

### No Silent Currency Drift

Currency lists, project governing currencies, and record denominations
must all remain consistent.  The audit tools provide operational
visibility; the base currency lock and supported-currency API provide
enforcement.  Together these form the Currency Governance Layer.

---

## API Response Contract Rules (PR-CURRENCY-007)

The following rules govern all finance, portfolio, cashflow, and aging
API response schemas.  These rules are enforced at the schema layer and
must be respected in every service that produces monetary responses.

### Rule A — Portfolio-Wide Money Must Be Grouped

If a response exposes monetary totals that can aggregate across
multiple project currencies, those fields must be typed as:

```python
Dict[str, float]  # ISO 4217 currency code → amount
```

Example schemas:
- `PortfolioFinancialSummaryResponse.total_revenue_recognized`
- `TreasuryMonitoringResponse.cash_position`
- `PortfolioCollectionsSummary.overdue_balance`
- `PortfolioCostVarianceSummary.total_baseline_amount`
- `PortfolioCashflowForecastResponse.currencies`

### Rule B — Project-Scoped Money Must Include Explicit Currency

If a response is scoped to a single project (or single contract), scalar
monetary totals are permitted but the response **must** include:

```python
currency: str  # ISO 4217 currency code, from project.base_currency
```

Example schemas:
- `PortfolioProjectCard.currency`
- `ProjectRevenueSummaryResponse.currency`
- `ProjectAgingResponse.currency`
- `ContractAgingResponse.currency`
- `CashflowForecastResponse.currency`
- `ProjectFinancialSummaryEntry.currency`
- `PortfolioAbsorptionProjectCard.currency`
- `PortfolioCostVarianceProjectCard.currency`

### Rule C — Ratios Derived From Multi-Currency Money Must Be Null-Safe

If a ratio (percentage, rate, efficiency metric) is derived from
monetary totals that may span multiple currencies, the field must be:

```python
Optional[float]  # None when multi-currency makes the ratio invalid
```

Example:
- `TreasuryMonitoringResponse.liquidity_ratio` → `None` for multi-currency portfolios
- `PortfolioKPI.collection_efficiency` → `None` when currencies > 1
- `PortfolioFinancialSummaryResponse.overdue_receivables_pct` → `None` for multi-currency

### Rule D — No Anonymous Money in API Contracts

No response schema may expose a monetary field without either:
1. A grouped currency-keyed dict (`Dict[str, float]`), or
2. An explicit `currency: str` field scoping the value.

This rule applies to all schemas modified after PR-CURRENCY-007.
Any new financial response schemas must comply from creation.

### Rule E — Portfolio-Wide Currency Inventory

Portfolio-level responses should include a `currencies: List[str]` field
listing all ISO 4217 currency codes present in the aggregated data.
This allows API consumers to reason about denomination diversity
without iterating all grouped dict keys.

### Forbidden Patterns

The following patterns are forbidden in API response schemas:

```python
# ❌ Anonymous money — no currency context
total_revenue: float

# ❌ Portfolio-wide scalar — cannot be valid across currencies
portfolio_cash: float

# ❌ Ratio across currencies — mathematically invalid
cross_currency_rate: float
```

---

## Final Currency Closure Rules (PR-CURRENCY-008)

These rules complete the currency remediation program.  After this point,
the currency program is considered **complete**.  All new code must comply.

### Rule F — No Inline ISO Literals in Services, Repositories, or Helpers

Service, repository, and helper code must never use a raw ISO 4217 string
as a Python default value.  Always import and reference the constant:

```python
# ✅ Correct
from app.core.constants.currency import DEFAULT_CURRENCY
currency = payload.get("currency", DEFAULT_CURRENCY)

# ❌ Forbidden — inline literal leaks denomination assumptions
currency = payload.get("currency", "AED")
```

**Exception:** Alembic migration scripts may use literal strings for
`server_default` to maintain deterministic, immutable migration history.
Runtime code (services, schemas, repositories) must always use the constant.

### Rule G — Parent → Child Financial Workflow Currency Propagation

When a service creates child financial records (payout lines, installments,
receivables, cashflow period rows) from a parent (contract, plan, forecast),
the child records must explicitly receive the parent's currency rather than
relying on an ORM model default.

```python
# ✅ Correct — payout inherits contract currency
payout = CommissionPayout(currency=contract.currency, ...)
line = CommissionPayoutLine(currency=contract.currency, ...)

# ❌ Forbidden — relies on model default, ignores actual denomination
payout = CommissionPayout(...)   # currency silently defaults to AED
```

Applies to:
- `CommissionPayout` and `CommissionPayoutLine` ← `SalesContract.currency`
- `CashflowForecastPeriod` ← `Project.base_currency`
- `Receivable` ← `ContractPaymentSchedule.currency`
- `PaymentSchedule` ← `SalesContract.currency`

### Rule H — Denomination Must Be Preserved Through Response Assembly

Every response builder that aggregates monetary fields must propagate
denomination through to the response object.  Do not let `total_due`,
`total_commission`, or any aggregate monetary field exist without an
accompanying `currency` field.

```python
# ✅ Correct — PaymentPlanResponse includes denomination
PaymentPlanResponse(total_due=..., currency=contract.currency, ...)

# ❌ Forbidden — total_due without denomination is anonymous money
PaymentPlanResponse(total_due=...)
```

### Rule I — Mixed-Currency Ratios Must Remain Null-Safe

Any ratio, rate, or percentage derived from monetary totals that may span
multiple project currencies must be `Optional[float]` and return `None`
when the portfolio contains more than one currency denomination.

This rule is established in Rule C and restated here for completeness.

### Rule J — Payment-Plan Schedule and Response Must Use Parent Contract as Currency Source-of-Truth

When generating payment schedule rows for a sales contract, the service must
explicitly write the parent `SalesContract.currency` onto every created
`PaymentSchedule` row.  Response builders must derive `currency` from the
governing parent contract — not by inferring it from persisted child rows.

```python
# ✅ Correct — schedule rows inherit parent contract denomination
row = {
    "contract_id": contract.id,
    "currency": contract.currency,   # explicit parent propagation
    ...
}
# ✅ Correct — response builder uses contract currency as source-of-truth
return PaymentPlanResponse(currency=contract.currency, ...)

# ❌ Forbidden — trusts that child rows are already correct, hiding write-path bugs
currency = items[0].currency if items else DEFAULT_CURRENCY
```

Applies to:

- `PaymentSchedule` rows ← `SalesContract.currency` (write path)
- `PaymentPlanResponse.currency` ← `SalesContract.currency` (response assembly)
- `PaymentScheduleListResponse.currency` ← `SalesContract.currency` (list response)

This prevents a non-default-currency contract from silently producing
platform-default-denominated schedule rows and responses.

### Enforcement Summary

| Layer | Rule |
|---|---|
| Services / repositories | No inline ISO literals (`"AED"`) — use `DEFAULT_CURRENCY` |
| Child record creation | Explicit parent currency propagation required |
| Payment schedule rows | Must persist `SalesContract.currency` explicitly |
| Response assembly | Every aggregate monetary field must carry denomination |
| Payment plan responses | Currency sourced from parent contract, not child rows |
| Portfolio ratios | `Optional[float]` — `None` for multi-currency portfolios |
| API response schemas | Follow Rules A–E from PR-CURRENCY-007 |
