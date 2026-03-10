# Feasibility Engine

## Purpose

The Feasibility module provides a full proforma modelling environment for real estate development projects. It enables analysts to model development economics, run scenario comparisons, calculate investment returns, and determine project viability before committing to full development.

## Scope

**In scope:**
- Development proforma construction (revenue, costs, timing)
- IRR (Internal Rate of Return) calculation
- NPV (Net Present Value) calculation
- Break-even unit count analysis
- Scenario comparison (multiple scenarios per project)

**Out of scope:**
- Market comparable data sourcing (handled by Market Intelligence module)
- Detailed construction scheduling
- Tax modelling beyond simple profit margin

## Key Concepts

**Development Proforma:** A structured financial model that projects total revenue, total costs, gross profit, and return metrics for a development.

**IRR:** The annualised rate of return that makes the NPV of all cashflows equal to zero. The primary return metric for development feasibility.

**Break-Even Units:** The minimum number of units that must be sold at the assumed price to recover all costs and achieve the minimum target return.

**Sensitivity Analysis:** Modelling the impact on returns of varying key assumptions (e.g., price per sqm, construction cost per sqm, absorption rate).

## Business Rules

- At least one feasibility scenario must be approved before a project moves to pricing
- Each scenario is versioned — prior scenarios are retained for comparison
- A scenario is marked as the "base case" by the Development Director or Finance Manager
- IRR below the minimum threshold triggers a required approval before project proceeds
- Feasibility scenarios must pull land cost from the Land module

## Data Entities

See [`../00-overview/core-data-model.md`](../00-overview/core-data-model.md) — Feasibility section:
- `FeasibilityScenario`
- `FeasibilityAssumption`
- `FeasibilityResult`
- `CashflowPeriod`

## Workflows

1. Create feasibility scenario for a project or phase
2. Define revenue assumptions (unit count, area, price per sqm by type)
3. Define cost assumptions (land, construction, professional fees, selling costs, finance costs, contingency)
4. Define cashflow timing assumptions (construction period, sales absorption rate)
5. System calculates: GDV, total cost, gross profit, gross margin, IRR, NPV, break-even units
6. Compare scenarios and mark base case
7. Approve feasibility and proceed to pricing

## Integration Points

| Module | Relationship |
|---|---|
| Land | Land cost feeds into feasibility cost assumptions |
| Concept Planning | Unit mix and area assumptions inform revenue model |
| Pricing | Feasibility pricing assumptions inform initial price list |
| Finance | Feasibility cashflow feeds into project financial planning |

## Open Questions

- Should the system support Monte Carlo simulation for sensitivity analysis?
- What is the minimum IRR threshold — is this configurable per project or system-wide?
