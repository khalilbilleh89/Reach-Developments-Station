# Finance Summary — Project Financial Dashboard

## Overview

The Finance Summary module provides a read-only, project-level aggregation layer
that consolidates data from Sales Contracts, Payment Receipts, and the Unit
Registry into a single financial snapshot.

This module does **not** create, modify, or delete any financial records.

---

## Problem Addressed

The platform generates financial data across multiple modules (sales contracts,
payment plans, collections) but previously had no unified service to answer
project-level financial questions such as:

- What is the total contracted revenue of the project?
- How much money has been collected from buyers?
- What is the outstanding receivable balance?
- What is the collection ratio?
- How many units are sold vs available?

---

## API Endpoint

```
GET /api/v1/finance/projects/{project_id}/summary
```

### Response Schema

```json
{
  "project_id": "string",
  "total_units": 100,
  "units_sold": 42,
  "units_available": 58,
  "total_contract_value": 185000000.00,
  "total_collected": 34000000.00,
  "total_receivable": 151000000.00,
  "collection_ratio": 0.184,
  "average_unit_price": 4404761.90
}
```

### Field Definitions

| Field | Type | Description |
|---|---|---|
| `project_id` | string | UUID of the project |
| `total_units` | integer | Total units in the project hierarchy |
| `units_sold` | integer | Units with status `under_contract` or `registered` |
| `units_available` | integer | Units with status `available` |
| `total_contract_value` | float | `SUM(contract_price)` across all project contracts |
| `total_collected` | float | `SUM(amount_received)` across all recorded receipts |
| `total_receivable` | float | `total_contract_value - total_collected` |
| `collection_ratio` | float | `total_collected / total_contract_value` (0.0 when no contracts) |
| `average_unit_price` | float | `AVG(contract_price)` across all project contracts (0.0 when none) |

### HTTP Status Codes

| Code | Meaning |
|---|---|
| 200 | Summary returned successfully |
| 404 | Project not found |

---

## Architecture

```
GET /api/v1/finance/projects/{id}/summary
        │
        ▼
FinanceSummaryService          (app/modules/finance/service.py)
        │   validates project exists
        │   computes derived metrics
        ▼
FinanceSummaryRepository       (app/modules/finance/repository.py)
        │   read-only SQL aggregation queries
        │   SUM, COUNT, AVG via GROUP BY
        ▼
ORM Models (read-only)
  ├── SalesContract.contract_price
  ├── PaymentReceipt.amount_received
  └── Unit.status
```

### Aggregation Logic

**Total Contract Value**

```sql
SELECT COALESCE(SUM(sales_contracts.contract_price), 0)
FROM sales_contracts
JOIN units ON units.id = sales_contracts.unit_id
JOIN floors ON floors.id = units.floor_id
JOIN buildings ON buildings.id = floors.building_id
JOIN phases ON phases.id = buildings.phase_id
WHERE phases.project_id = :project_id
```

**Total Collected**

```sql
SELECT COALESCE(SUM(payment_receipts.amount_received), 0)
FROM payment_receipts
JOIN sales_contracts ON sales_contracts.id = payment_receipts.contract_id
JOIN units ON units.id = sales_contracts.unit_id
JOIN floors ON floors.id = units.floor_id
JOIN buildings ON buildings.id = floors.building_id
JOIN phases ON phases.id = buildings.phase_id
WHERE phases.project_id = :project_id
  AND payment_receipts.status = 'recorded'
```

**Units Sold** (`under_contract` + `registered`)

```sql
SELECT COUNT(units.id)
FROM units
JOIN floors ON floors.id = units.floor_id
JOIN buildings ON buildings.id = floors.building_id
JOIN phases ON phases.id = buildings.phase_id
WHERE phases.project_id = :project_id
  AND units.status IN ('under_contract', 'registered')
```

---

## Scope Boundaries

This module is **read-only**. It does not:

- Insert or modify any financial records
- Alter contract prices or receipt amounts
- Trigger payment schedule generation
- Modify the project hierarchy or unit status

---

## Non-Goals

This module does not implement:

- NPV / IRR calculations
- Revenue recognition accounting
- Cashflow forecasting
- Investor waterfall models

These features will be introduced in future finance modules.
