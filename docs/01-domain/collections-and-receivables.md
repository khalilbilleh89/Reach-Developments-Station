# Collections and Receivables

## Purpose

The Collections module manages the recording of payment receipts against sales
contract payment schedules and the derivation of receivable status for each
installment line.  It provides the factual collections ledger that finance
summaries and cashflow reporting will rely on.

## Scope

**In scope (implemented — MVP):**
- Payment receipt recording against a specific payment schedule line
- Overpayment prevention (total receipts cannot exceed the due amount for a line)
- Cross-contract validation (a receipt must belong to the same contract as its schedule line)
- Receivable status derivation per schedule line: `pending`, `partially_paid`, `paid`, `overdue`
- Contract-level receivables summary (total due / received / outstanding)
- REST API for recording receipts and querying receivables

**Planned but not yet implemented:**
- Receipt reversal
- Aging analysis buckets (current, 1-30, 31-60, 61-90, 90+ days)
- Automated collection alerts and escalation triggers
- Collections officer contact log

**Out of scope:**
- Payment plan schedule generation (handled by Payment Plans module)
- Revenue recognition (handled by Revenue Recognition module)
- Finance summary and cashflow forecasting (future modules)
- Legal enforcement actions (external process)

## Receipt Recording

A `PaymentReceipt` records a single cash/bank receipt applied against one
`PaymentSchedule` row.

**Input fields:**

| Field | Required | Notes |
|---|---|---|
| `contract_id` | ✅ | Must be an existing contract |
| `payment_schedule_id` | ✅ | Must belong to the same contract |
| `receipt_date` | ✅ | Date the payment was received |
| `amount_received` | ✅ | Must be > 0 |
| `payment_method` | Optional | `bank_transfer`, `cash`, `cheque`, `other` |
| `reference_number` | Optional | Bank reference or cheque number |
| `notes` | Optional | Free-text notes |

## Schedule Settlement Logic

Each payment schedule line maintains a running total of `recorded` receipts.
A line is considered settled when `total_received >= due_amount`.

Partial payments are allowed — multiple receipts may be recorded against the
same schedule line as long as the cumulative total does not exceed `due_amount`.

Overpayment is forbidden in the MVP.  The service will return HTTP 422 if a
new receipt would push `total_received` above `due_amount`.

## Receivable Status Derivation

Receivable status is derived on-the-fly from the schedule and receipts — it is
not stored redundantly in the database.

| Condition | Status |
|---|---|
| `total_received >= due_amount` | `paid` |
| `outstanding > 0` and `due_date < today` | `overdue` |
| `total_received > 0` and outstanding remains | `partially_paid` |
| No receipts and `due_date >= today` | `pending` |

The derivation order above is applied in sequence: `paid` is checked first,
then `overdue`, then `partially_paid`, then `pending`.

## Due vs Paid Formula

```
outstanding_amount = due_amount - total_received
```

Where `total_received` is the sum of all receipts with status `recorded`
(excluding reversed receipts) for that schedule line.

## API Endpoints

All endpoints are under `/api/v1/collections/`.

| Method | Path | Description |
|---|---|---|
| POST | `/receipts` | Record a payment receipt |
| GET | `/receipts/{receipt_id}` | Get a receipt by ID |
| GET | `/contracts/{contract_id}/receipts` | List all receipts for a contract |
| GET | `/contracts/{contract_id}/receivables` | Get receivables summary for a contract |

## Relationship to Other Modules

| Module | Relationship |
|---|---|
| Payment Plans | `PaymentSchedule` rows are the collection targets |
| Finance | Outstanding receivables will feed into project financial summary (future) |
| Revenue Recognition | Collected amounts will inform recognition events (future) |
| Sales | Contract must exist before any receipt can be recorded |

## Non-Goals

This module does **not**:
- Generate or modify payment schedules
- Perform revenue recognition or accounting journal entries
- Calculate cashflow forecasts
- Produce collections analytics dashboards
- Implement registration workflows

## Open Questions

- What is the late payment penalty policy — flat fee, percentage, or no penalty?
- At what point does an overdue account trigger a legal escalation process?
