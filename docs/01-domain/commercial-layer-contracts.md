# Commercial Layer Contracts

## Purpose

This document defines the canonical domain responsibilities for the four
commercial modules — **Pricing**, **Sales**, **Finance**, and **Registry** —
and enforces the platform's unit-centric architecture rule.

It is the normative reference produced by the PR-D2 commercial-layer contract
review.  All future development in these modules must comply with the rules
below.

---

## Core Hierarchy (never modified without architectural review)

```
Project
 └ Phase
     └ Building
         └ Floor
             └ Unit   ← commercial origin point
```

Every commercial record originates at the **Unit** level.  Records attached
directly to a Project — bypassing the unit hierarchy — are a contract violation.

---

## Canonical Ownership Map

| Domain         | Owned entities                              | Attached to     |
|----------------|---------------------------------------------|-----------------|
| **Pricing**    | UnitPricingAttributes, UnitPricing          | Unit            |
| **Sales**      | Buyer, Reservation, SalesContract           | Unit            |
| **Payment Plans** | PaymentPlanTemplate (reusable blueprint) | _(no project FK)_ |
|                | PaymentSchedule (installment lines)         | Contract        |
| **Finance**    | _(no ORM models — read-only aggregation)_   | downstream only |
| **Registry**   | RegistrationCase, Milestones, Documents     | Unit + Contract |

---

## Module Responsibilities

### Pricing

**Owns:** pricing engine inputs and formal per-unit price records.

**Rules:**

- `UnitPricingAttributes` and `UnitPricing` both carry a `unit_id` FK to
  `units.id`.  No direct FK to `projects` exists.
- `PricingService` is the sole writer of pricing records.
- `PricingService` must not create `Reservation` or `SalesContract` rows.
- `PricingService` must not import from `finance` or `registry` modules.
- The project-level price summary (`calculate_project_price_summary`) is a
  read-only aggregation that traverses the hierarchy join; it does not bypass
  units.

### Sales

**Owns:** buyer records, reservations, and sales contracts.

**Rules:**

- `Reservation.unit_id` and `SalesContract.unit_id` are FKs to `units.id`.
  Sales records must never be attached directly to `projects`.
- `SalesService` consumes pricing data from the pricing domain
  (`UnitPricingAttributesRepository`); it does not redefine pricing formulas.
- `SalesService` must not calculate finance KPIs or write payment plan rows.
- `SalesService` must not import from `finance` or `registry` modules.

### Payment Plans

**Owns:** reusable plan templates and per-contract installment schedules.

**Rules:**

- `PaymentPlanTemplate` is a reusable blueprint with no FK to any project.
- `PaymentSchedule.contract_id` is a FK to `sales_contracts.id`.
  Schedule rows must never be attached directly to projects.
- Plan generation starts from a contract context; the contract is the
  commercial object that owns the repayment schedule.

### Finance

**Owns:** read-only project-level financial summaries.

**Rules:**

- `finance/models.py` is intentionally empty.  Finance does not own commercial
  ORM records.  It is a pure aggregation domain.
- `FinanceSummaryService` reads `SalesContract.contract_price` and
  `PaymentReceipt.amount_received` via joins through the unit hierarchy.
- `FinanceSummaryService` must not create or mutate any commercial record.
- `FinanceSummaryService` must not import `PricingService` or any pricing
  write path.
- Finance summaries are downstream outputs; pricing and sales are upstream
  sources of truth.

### Registry

**Owns:** post-sale legal transfer cases, milestones, and document checklists.

**Rules:**

- `RegistrationCase` stores both `unit_id` (FK to `units.id`) and
  `sale_contract_id` (FK to `sales_contracts.id`), making every case traceable
  to its commercial contract.
- `RegistrationCase` also stores a denormalized `project_id` for efficient
  list queries.  This field is **validated server-side**: `RegistryService`
  derives the actual project by traversing `Unit → Floor → Building →
  Phase → Project` and rejects any create request whose supplied `project_id`
  does not match.  Clients cannot record a case against an arbitrary project.
- `RegistryService` must not create pricing records or perform finance
  calculations.
- `RegistryService` must not import from the `pricing` module.
- Registry is a participant/case-management domain, not a commercial math
  domain.

---

## Forbidden Designs

The following patterns are architecture violations:

| Pattern | Reason |
|---|---|
| `UnitPricing.project_id` FK | Pricing must attach to unit, not project |
| `SalesContract.project_id` FK | Sales must attach to unit, not project |
| `Reservation.project_id` FK | Sales must attach to unit, not project |
| `PaymentSchedule.project_id` FK | Payment schedule attaches to contract |
| Finance service creating `SalesContract` rows | Finance is read-only |
| Finance service calling `PricingService` | Finance consumes, not owns, pricing |
| Registry service writing `UnitPricing` rows | Registry is participant/case domain |
| `RegistrationCase.project_id` accepted without validation | Hierarchy bypass — must validate via unit join |

---

## Enforcement

Contract rules are locked by automated tests in:

```
tests/architecture/test_commercial_layer_contracts.py
```

Run with:

```bash
pytest tests/architecture/test_commercial_layer_contracts.py
```

The test suite covers:

- ORM foreign-key topology (no direct project FKs in pricing/sales/payment schedules)
- Service-layer isolation (no cross-domain mutations)
- Registry `project_id` validation against unit hierarchy
- Finance read-only guarantee (no contract mutation)
- Cross-domain import guards (pricing/registry/finance import hygiene)
