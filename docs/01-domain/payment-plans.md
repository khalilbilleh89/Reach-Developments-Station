# Payment Plans

## Purpose

The Payment Plans module manages the full lifecycle of configurable payment plan templates and the generation of per-contract payment schedules. It enables developers to offer multiple payment structures, generate individualized payment schedules, and project cashflow impact across the portfolio.

## Scope

**In scope:**
- Payment plan template library (reusable plan structures)
- Template-based schedule generation per contract
- Multiple trigger types: time-based, construction milestone-based, sales milestone-based
- Cashflow impact projection from payment plan portfolio

**Out of scope:**
- Payment collection and receipt matching (handled by Collections module)
- Revenue recognition timing (handled by Revenue Recognition module)

## Key Concepts

**Payment Plan Template:** A reusable plan structure defining the sequence, timing trigger, and percentage of each payment milestone. Templates are created at the project or company level and applied to contracts.

**Milestone:** A single payment event in a plan — defined by its trigger (date, construction stage, or sales event), percentage of total price, and label.

**Payment Schedule:** The instance of a payment plan template applied to a specific contract — with actual dates and amounts calculated from the contract price.

**Trigger Types:**
- **Time-based:** Payment due on a fixed date or after a defined period
- **Construction milestone-based:** Payment due when a defined construction stage is reached (e.g., "Foundation Complete", "Handover")
- **Sales milestone-based:** Payment due upon a sales event (e.g., "On Signing")

## Business Rules

- All payment plan percentages within a template must sum to exactly 100%
- A payment schedule is generated automatically when a contract is activated
- Payment plan templates must be approved before being assigned to contracts
- Post-signing changes to a payment schedule require a formal contract amendment
- Cashflow projections must reflect actual payment schedule dates, not just template assumptions

## Data Entities

See [`../00-overview/core-data-model.md`](../00-overview/core-data-model.md) — Payment Plans section:
- `PaymentPlanTemplate`
- `PaymentPlanMilestone`
- `ContractPaymentPlan`
- `PaymentScheduleLine`

## Workflows

1. Define payment plan template (milestone labels, triggers, percentages)
2. Approve template for use
3. Assign template to contract at point of contract creation
4. System generates payment schedule (dates and amounts calculated from contract price)
5. Payment schedule lines feed into Collections module for tracking
6. System aggregates all schedule lines into cashflow projection

## Integration Points

| Module | Relationship |
|---|---|
| Sales | Contract creation triggers payment plan assignment |
| Collections | Payment schedule lines become collection targets |
| Finance | Payment schedule portfolio drives cashflow forecast |
| Revenue Recognition | Milestone triggers can align with recognition events |

## Open Questions

- Can multiple payment plans be offered for the same project simultaneously?
- How are post-handover installment plans handled (buyer retains plan after handover)?
