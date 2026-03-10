# Land Underwriting

## Purpose

The Land module manages the acquisition and valuation of land parcels associated with a development project. It captures the financial and legal characteristics of land, supports residual land value calculations, and records the cost basis for feasibility modelling.

## Scope

**In scope:**
- Land parcel registration and attribute management
- Acquisition cost and timeline tracking
- Market valuation and residual land value calculation
- Land cost breakdown (purchase, due diligence, transfer costs)

**Out of scope:**
- Land surveys and topographic modelling
- Environmental impact assessments
- Legal conveyancing for land acquisition

## Key Concepts

**Residual Land Value (RLV):** The maximum a developer should pay for land, calculated by deducting all development costs and profit requirements from the projected gross development value (GDV).

**GDV (Gross Development Value):** The total expected revenue from the development if all units were sold at target prices.

**Land Cost Basis:** The all-in cost of acquiring a land parcel, including purchase price, transfer fees, due diligence costs, and holding costs.

## Business Rules

- Each land parcel must be associated with a Project
- A land parcel can have multiple valuations over time (historic valuations are retained)
- The Residual Land Value must be calculated before a project proceeds to full feasibility
- Land cost must feed into the feasibility module as a cost input

## Data Entities

See [`../00-overview/core-data-model.md`](../00-overview/core-data-model.md) — Land section:
- `LandParcel`
- `LandValuation`
- `LandCost`

## Workflows

1. Register land parcel against a project
2. Record acquisition details (price, date, ownership status)
3. Run residual land value calculation (inputs from concept planning / feasibility)
4. Record final land cost for feasibility input

## Integration Points

| Module | Relationship |
|---|---|
| Projects | Land parcels belong to a project |
| Concept Planning | Unit mix and density inputs drive GDV for RLV calculation |
| Feasibility | Land cost is a required cost input |

## Open Questions

- Should the system support multiple land parcels per project (assembled sites)?
- What is the required methodology for valuation (comparable sales, income approach)?
