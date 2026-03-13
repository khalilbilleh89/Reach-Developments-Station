# Payment Plans

## Purpose

The Payment Plans module manages configurable payment plan templates and the generation of per-contract payment schedules. It enables developers to define reusable installment structures, generate individualized schedules against contract prices, and provide a structured due-schedule basis for future collections and finance reporting.

## Implementation Status

**Implemented in PR-REDS-008:**
- Payment plan template CRUD (create, read, update, list)
- Deterministic schedule generation from templates applied to contracts
- Schedule retrieval and regeneration per contract
- REST API under `/api/v1/payment-plans/`
- Database migration `0006_create_payment_plan_tables`

**Not yet implemented (future PRs):**
- Collections / receipt matching (PR-REDS-009)
- Revenue recognition (future)
- Cashflow forecasting aggregate (future)
- Registration workflows (future)

## Scope

**In scope (this module):**
- Payment plan template library (reusable plan structures)
- Template-based schedule generation per contract
- Standard installment, post-handover, and custom plan types
- Monthly and quarterly installment frequency

**Out of scope:**
- Payment collection and receipt matching (Collections module)
- Revenue recognition timing (Revenue Recognition module)
- Delinquency tracking (Collections module)
- Cashflow forecasting aggregates (Finance module)

## Key Concepts

**Payment Plan Template:** A reusable plan blueprint defining installment count, frequency, down-payment percentage, optional handover percentage, and plan type. Templates are created once and applied to multiple contracts.

**Payment Schedule:** The set of installment lines generated from a template applied to a specific contract. Due dates and due amounts are calculated deterministically from the contract price. One contract has at most one active schedule at a time.

**Schedule Line Fields:**
- `installment_number` — 0 for down payment, 1…N for regular installments, N+1 for handover
- `due_date` — computed from start date and frequency
- `due_amount` — computed from contract price and percentage allocation
- `status` — starts as `pending`; updated by Collections module (future)
- `notes` — optional label ("Down payment", "Handover", etc.)

**Plan Types:**
- `standard_installments` — even installments over a defined period
- `milestone` — tied to construction milestones (future trigger logic)
- `post_handover` — installments after handover completion
- `custom` — flexible, caller-controlled allocations

**Installment Frequency:**
- `monthly` — due date increments by 1 month
- `quarterly` — due date increments by 3 months
- `custom` — defaults to monthly; override post-generation as needed

## Business Rules

- `down_payment_percent + handover_percent` must not exceed 100%
- `number_of_installments` must be ≥ 1
- Template must be active (`is_active = true`) before schedule generation
- Contract must exist and have a positive `contract_price`
- Generated schedule `total_due` must equal `contract_price` within 2-cent rounding tolerance
- Regeneration deletes the existing schedule and replaces it; the `contract_id` in the request body must match the URL parameter
- No payment is marked as paid by this module; only `pending` rows are created

## Generation Algorithm

```
down_payment_amount = contract_price × down_payment_percent / 100
handover_amount     = contract_price × handover_percent / 100   (0 if absent)
remaining_balance   = contract_price - down_payment_amount - handover_amount

base_installment    = remaining_balance / number_of_installments  (rounded to 2 dp)
last_installment   += rounding_remainder   (ensures sum == remaining_balance)

due_dates           = [start_date + n × period  for n in 0..N-1]

lines:
  [0]      installment_number=0,   due on start_date,            amount=down_payment_amount
  [1..N]   installment_number=1…N, due on due_dates[0..N-1],     amount=installment_amounts
  [N+1]    installment_number=N+1, due one period after last,    amount=handover_amount   (if present)
```

## Data Entities

### `payment_plan_templates`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID string | Primary key |
| `name` | string(255) | Template label |
| `plan_type` | string(50) | `PaymentPlanType` enum |
| `description` | string(1000) | Optional description |
| `down_payment_percent` | numeric(5,2) | 0–100 |
| `number_of_installments` | integer | ≥ 1 |
| `installment_frequency` | string(50) | `InstallmentFrequency` enum |
| `handover_percent` | numeric(5,2) | Optional, 0–100 |
| `is_active` | boolean | Must be true for generation |
| `created_at` | datetime | Auto-set |
| `updated_at` | datetime | Auto-updated |

### `payment_schedules`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID string | Primary key |
| `contract_id` | UUID string | FK → `sales_contracts.id` (CASCADE) |
| `template_id` | UUID string | FK → `payment_plan_templates.id` (SET NULL), nullable |
| `installment_number` | integer | 0=down, 1…N=regular, N+1=handover |
| `due_date` | date | Computed from start_date + frequency |
| `due_amount` | numeric(14,2) | Computed from contract_price |
| `status` | string(50) | `PaymentScheduleStatus` enum, starts as `pending` |
| `notes` | string(1000) | Optional label |
| `created_at` | datetime | Auto-set |
| `updated_at` | datetime | Auto-updated |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/payment-plans/templates` | Create template |
| `GET` | `/api/v1/payment-plans/templates` | List templates |
| `GET` | `/api/v1/payment-plans/templates/{id}` | Get template |
| `PATCH` | `/api/v1/payment-plans/templates/{id}` | Update template |
| `POST` | `/api/v1/payment-plans/generate` | Generate schedule for contract |
| `GET` | `/api/v1/payment-plans/contracts/{id}/schedule` | Get schedule for contract |
| `POST` | `/api/v1/payment-plans/contracts/{id}/regenerate` | Replace schedule |

## Integration Points

| Module | Relationship |
|---|---|
| Sales | Contract provides `contract_price` used for schedule generation |
| Collections (future) | Schedule lines become collection targets; `status` updated by that module |
| Finance (future) | Schedule portfolio drives cashflow forecast |
| Revenue Recognition (future) | Milestone due dates can align with recognition events |

## Boundaries

This module **cannot** and **does not**:
- Mark any schedule line as paid (that is Collections' responsibility)
- Create receipt or collection records
- Apply revenue recognition logic
- Modify contract prices
- Simulate financing cashflows

## Open Questions

- Can a contract carry multiple concurrent payment plan schedules (e.g., for amended commercial terms)?
- How are post-handover installment plans tracked after project handover date is confirmed?

