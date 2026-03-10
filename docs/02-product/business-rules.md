# Business Rules

## Overview

This document collects cross-cutting business rules that apply across multiple modules. Module-specific rules are documented in the individual domain docs under `docs/01-domain/`.

---

## Asset Hierarchy Rules

- A Unit must belong to a Floor
- A Floor must belong to a Building
- A Building must belong to a Phase
- A Phase must belong to a Project
- Orphan records (entities without a valid parent) are not permitted
- Deleting a parent entity is only allowed if it has no active child records

---

## Unit Status Rules

Units follow a strict status lifecycle:

```
Available → Reserved → Under Contract → Registered
```

- `Available`: Unit is on the active price list and available for reservation
- `Reserved`: Unit has an active reservation — cannot be reserved by another buyer
- `Under Contract`: A signed SPA exists — unit is sold
- `Registered`: Title deed has been issued — transaction is complete

Reverse transitions are only permitted via formal cancellation workflows with appropriate authorization.

---

## Pricing Authority Rules

| Action | Authorized By |
|---|---|
| Create and edit price lists | Pricing Manager |
| Approve price list for activation | Development Director |
| Override price ≤2% below list price | Sales Manager |
| Override price ≤5% below list price | Development Director |
| Override price >5% below list price | CEO |

---

## Feasibility Approval Rules

- A feasibility scenario must be marked as approved before pricing can begin
- Only Development Director or CEO may approve a feasibility scenario
- Once approved, a scenario is locked — amendments require creating a new scenario version

---

## Payment Plan Rules

- Payment percentages across all milestones in a template must sum to exactly 100%
- A payment plan template must be approved before assignment to contracts
- Post-signing changes to a payment schedule require a formal contract amendment

---

## Collection Rules

- Receipts must be matched to specific payment schedule lines
- A schedule line is only marked as settled when fully matched
- Overdue calculation is based on calendar days from the payment due date
- Alert thresholds: 7 days overdue (first alert), 30 days overdue (escalation alert)

---

## Audit and Governance Rules

- All create, update, and delete operations must be recorded in the audit log with user, timestamp, and changed fields
- Financial figures (prices, contract values, amounts) must never be editable without creating an audit record
- Approved records (price lists, feasibility scenarios, contracts) cannot be deleted — only superseded or cancelled
