# Pricing Engine

## Purpose

The Pricing module manages all aspects of unit pricing for a development. It supports base price management, premium rule application, price list governance, override approvals, and feeds final prices into sales and feasibility modules.

## Scope

**In scope:**
- Price list creation and management per phase
- Base price assignment per unit
- Premium rule engine (floor, view, corner, orientation, type premiums)
- Price override governance (with approval workflow)
- Price list versioning and activation control

**Out of scope:**
- Price escalation (handled by Price Escalation module)
- Discount and incentive governance (handled by Sales Exceptions module)
- Market price benchmarking (handled by Market Intelligence module)

## Key Concepts

**Price List:** A versioned set of unit prices for a phase, effective from a specific date. Only one price list can be active at any time per phase.

**Base Price:** The starting price for a unit before any premium adjustments. May be expressed as a total price or a price per square metre.

**Premium Rule:** A configurable rule that adds or subtracts a percentage or fixed amount from a unit's base price based on unit attributes (floor level, view type, orientation, corner unit, etc.).

**Price Override:** A manually approved deviation from the calculated price for a specific unit. Requires authorization based on the magnitude of the override.

**Final Price:** The calculated price after base price + all applicable premium adjustments. The Final Price is what appears in a Sales Contract.

## Business Rules

- A price list must be approved before units can be reserved against it
- Premium rules are applied in a defined order to avoid compounding errors
- Price overrides must be authorized: ≤2% deviation by Sales Manager, ≤5% by Development Director, >5% by CEO
- A unit's final price cannot be changed after a contract is signed without generating a formal amendment
- Historic price lists are retained for audit purposes

## Data Entities

See [`../00-overview/core-data-model.md`](../00-overview/core-data-model.md) — Pricing section:
- `PriceList`
- `UnitPrice`
- `PremiumRule`
- `PriceOverride`
- `EscalationEvent`

## Workflows

1. Create price list for a phase
2. Define base prices for all units (bulk import or individual assignment)
3. Configure premium rules for the price list
4. System calculates final prices for all units
5. Review and approve price list
6. Activate price list (units become available for reservation)
7. Process override requests through approval workflow

## Integration Points

| Module | Relationship |
|---|---|
| Feasibility | Feasibility pricing assumptions inform initial price list |
| Units | Prices are assigned to units |
| Sales | Active price list prices are referenced in reservations and contracts |
| Price Escalation | Escalation events update the active price list |

## Open Questions

- Should the system support per-unit or per-sqm pricing (or both)?
- How are mixed-use developments handled (residential vs. retail pricing)?
