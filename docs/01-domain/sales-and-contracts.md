# Sales and Contracts

## Purpose

The Sales module manages the full commercial transaction lifecycle from unit reservation through to signed sales contract. It tracks the sales pipeline, manages customer records, enforces unit availability rules, and coordinates with payment plans, collections, and registration modules.

## Scope

**In scope:**
- Customer registration and profile management
- Unit reservation (provisional hold)
- Sales contract generation and management
- Reservation expiry and release logic
- Sales pipeline tracking and reporting
- Commission assignment to sales agents

**Out of scope:**
- Payment collection (handled by Collections module)
- Payment plan schedule generation (handled by Payment Plans module)
- Title transfer and registration (handled by Registration module)
- Discount and incentive governance (handled by Sales Exceptions module)

## Key Concepts

**Reservation:** A provisional hold on a unit placed by a qualified customer. Reservations have an expiry date and require a reservation deposit. A unit can only have one active reservation at a time.

**Sales Contract (SPA):** A signed Sale and Purchase Agreement between the developer and the customer. A contract locks the unit price, the agreed payment plan, and triggers downstream workflows (payment plan generation, collections, registration).

**Pipeline:** The aggregate view of all reservations and contracts — showing units at each stage of the sales process.

## Business Rules

- A unit can only have one active reservation at a time
- Reservations automatically expire if not converted to contract within the defined period (configurable per project)
- A unit's status changes: Available → Reserved → Under Contract → Registered
- A contract cannot be created without an approved price (from Pricing module)
- Cancellation rules and refund policies must be defined at the project level before sales begin

## Data Entities

See [`../00-overview/core-data-model.md`](../00-overview/core-data-model.md) — Sales section:
- `Customer`
- `Reservation`
- `SalesContract`
- `SalesException`
- `Incentive`

## Workflows

1. Register customer
2. Check unit availability
3. Create reservation (unit status → Reserved)
4. Collect reservation deposit (triggers collection entry)
5. Convert reservation to contract (SPA signing)
6. Contract activation (unit status → Under Contract)
7. Payment plan generation triggered
8. Registration workflow initiated (upon collection milestones)

## Integration Points

| Module | Relationship |
|---|---|
| Units | Unit availability and status updates |
| Pricing | Contract price referenced from active price list |
| Payment Plans | Contract triggers payment plan schedule generation |
| Collections | Deposits and installments tracked against contract |
| Registration | Contract triggers registration workflow |
| Commissions | Agent commission assigned at contract level |
| Sales Exceptions | Discount and incentive requests linked to contract |

## Open Questions

- What is the reservation deposit policy — is it fixed or a percentage of contract price?
- What happens to a reservation deposit if a reservation expires?
