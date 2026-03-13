# Feasibility Calculation Specification

**Module:** `app/modules/feasibility`
**PR:** PR-REDS-005 — Implement Feasibility Engine Foundation
**Status:** Implemented

---

## 1. Purpose

The feasibility engine enables structured development economics analysis per project scenario.
Each feasibility run represents one scenario (e.g., base case, upside, downside, investor)
and stores input assumptions and calculated output results independently.

---

## 2. Inputs

All inputs are stored in the `feasibility_assumptions` table and provided via the
`FeasibilityAssumptionsCreate` schema.

| Field                       | Type    | Unit       | Constraint        | Description                                      |
|-----------------------------|---------|------------|-------------------|--------------------------------------------------|
| `sellable_area_sqm`         | float   | sqm        | > 0               | Total sellable floor area                        |
| `avg_sale_price_per_sqm`    | float   | currency   | > 0               | Average achieved sale price per sqm              |
| `construction_cost_per_sqm` | float   | currency   | > 0               | All-in construction cost per sqm                 |
| `soft_cost_ratio`           | float   | ratio (0–1)| 0 ≤ x ≤ 1        | Soft costs as a proportion of construction cost  |
| `finance_cost_ratio`        | float   | ratio (0–1)| 0 ≤ x ≤ 1        | Finance costs as a proportion of construction cost |
| `sales_cost_ratio`          | float   | ratio (0–1)| 0 ≤ x ≤ 1        | Sales costs as a proportion of GDV               |
| `development_period_months` | integer | months     | ≥ 1               | Total development period (used for context only in this PR) |

---

## 3. Outputs

All outputs are computed deterministically and stored in the `feasibility_results` table.

| Field                | Type  | Unit     | Description                                           |
|----------------------|-------|----------|-------------------------------------------------------|
| `gdv`                | float | currency | Gross Development Value                               |
| `construction_cost`  | float | currency | Total construction cost                               |
| `soft_cost`          | float | currency | Soft costs (professional fees, permits, etc.)         |
| `finance_cost`       | float | currency | Finance / interest costs                              |
| `sales_cost`         | float | currency | Sales and marketing costs                             |
| `total_cost`         | float | currency | Sum of all cost components                            |
| `developer_profit`   | float | currency | Residual profit after all costs                       |
| `profit_margin`      | float | ratio    | Developer profit as a proportion of GDV               |
| `irr_estimate`       | float | ratio    | Simple return-on-cost proxy (see note below)          |

---

## 4. Formulas

All formulas are implemented in `app/modules/feasibility/engines/feasibility_engine.py`.

```
gdv                = sellable_area_sqm × avg_sale_price_per_sqm
construction_cost  = sellable_area_sqm × construction_cost_per_sqm
soft_cost          = construction_cost × soft_cost_ratio
finance_cost       = construction_cost × finance_cost_ratio
sales_cost         = gdv × sales_cost_ratio
total_cost         = construction_cost + soft_cost + finance_cost + sales_cost
developer_profit   = gdv − total_cost
profit_margin      = developer_profit / gdv          (returns 0 when gdv = 0)
irr_estimate       = developer_profit / total_cost   (returns 0 when total_cost = 0)
```

---

## 5. Units and Rounding

- All monetary values are stored as `Numeric(20, 2)` in the database (2 decimal places).
- Ratios (`profit_margin`, `irr_estimate`) are stored as `Numeric(10, 6)`.
- The engine operates on native Python `float`. Rounding is applied at persistence time by the database column type.
- Currency units are not enforced at the engine level; the caller is responsible for ensuring consistent currency across inputs.

---

## 6. Scenario Types

Defined in `app/shared/enums/finance.FeasibilityScenarioType`:

| Value       | Description                                   |
|-------------|-----------------------------------------------|
| `base`      | Standard expected-case scenario               |
| `upside`    | Optimistic scenario (higher prices, lower cost)|
| `downside`  | Pessimistic / stress scenario                 |
| `investor`  | Investor-return focused scenario              |

---

## 7. API Endpoints

All endpoints are prefixed with `/api/v1/feasibility`.

| Method | Path                               | Description                                      |
|--------|------------------------------------|--------------------------------------------------|
| POST   | `/runs`                            | Create a new feasibility run for a project       |
| GET    | `/runs`                            | List runs (optionally filtered by `project_id`)  |
| GET    | `/runs/{id}`                       | Get a run by ID                                  |
| PATCH  | `/runs/{id}`                       | Update run metadata (name, type, notes)          |
| POST   | `/runs/{id}/assumptions`           | Create or replace assumptions for a run          |
| GET    | `/runs/{id}/assumptions`           | Get the current assumptions for a run            |
| POST   | `/runs/{id}/calculate`             | Execute calculation and persist results          |
| GET    | `/runs/{id}/results`               | Get calculated results for a run                 |

---

## 8. Assumptions

- One set of assumptions per run (upsert replaces existing).
- One result record per run (recalculation replaces existing result).
- All assumption fields are required before calculation can be triggered.
- A `development_period_months` field is stored for context. It does not affect the current formulas but is reserved for future time-value calculations.

---

## 9. Non-Goals for This PR

The following are explicitly **out of scope** for this PR:

- Net Present Value (NPV)
- Discounted Cash Flow (DCF) model
- True Internal Rate of Return using monthly cashflow projections
- Debt drawdown schedules or loan-to-cost ratios
- Revenue absorption curves
- Equity waterfall calculations
- Payment plan effects on cashflow
- Revenue recognition schedules
- Project financial dashboard integration
- Bulk scenario import / export

These features are planned for future enhancement PRs.
