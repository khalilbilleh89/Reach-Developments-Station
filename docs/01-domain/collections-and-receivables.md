# Collections and Receivables

## Purpose

The Collections module manages the tracking, matching, and aging of all receivables arising from sales contracts. It ensures that all payment obligations are monitored, that receipts are correctly matched to schedule lines, and that overdue accounts trigger appropriate escalation alerts.

## Scope

**In scope:**
- Payment receipt recording
- Receipt-to-schedule-line matching
- Aging analysis (current, 30, 60, 90, 90+ days overdue)
- Collection alerts and escalation triggers
- Outstanding receivables reporting

**Out of scope:**
- Payment plan schedule generation (handled by Payment Plans module)
- Revenue recognition (handled by Revenue Recognition module)
- Legal enforcement actions (external process)

## Key Concepts

**Receipt:** A payment received from a buyer, recorded with date, amount, method, and reference.

**Receipt Matching:** The process of allocating a receipt to one or more open payment schedule lines.

**Aging:** The classification of outstanding receivables by how many days they are overdue. Standard buckets: Current, 1-30 days, 31-60 days, 61-90 days, 90+ days.

**Collection Alert:** A system-generated notification triggered when a payment schedule line becomes overdue or when a defined aging threshold is crossed.

## Business Rules

- Receipts must be matched to specific payment schedule lines before they are considered settled
- Partial receipts are allowed — a line is only marked as settled when fully matched
- Aging is calculated daily against the due dates in the payment schedule
- Alerts are triggered automatically: first alert at 7 days overdue, escalation alert at 30 days overdue
- Collections officers must log contact attempts and resolution notes against overdue accounts

## Data Entities

See [`../00-overview/core-data-model.md`](../00-overview/core-data-model.md) — Collections section:
- `PaymentReceipt`
- `ReceiptAllocation`
- `AgingBucket`
- `CollectionAlert`

## Workflows

1. Payment due date arrives — schedule line becomes active target
2. Buyer makes payment — receipt recorded
3. Receipt matched to schedule line(s)
4. If unmatched or partially matched by due date — aging begins
5. Alert triggered at 7 days overdue
6. Escalation alert triggered at 30 days overdue
7. Collections officer logs contact and resolution
8. Receipt fully matched — schedule line closed

## Integration Points

| Module | Relationship |
|---|---|
| Payment Plans | Payment schedule lines are the collection targets |
| Finance | Outstanding receivables feed into project financial summary |
| Revenue Recognition | Collected amounts inform recognition events |
| Sales | Contract status may be affected by severe overdue positions |

## Open Questions

- What is the late payment penalty policy — flat fee, percentage, or no penalty?
- At what point does an overdue account trigger a legal escalation process?
