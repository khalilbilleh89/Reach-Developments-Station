# Sales and Contracts

## Purpose

The Sales module manages the commercial transaction lifecycle from unit reservation through to signed sales contract. It tracks the sales pipeline, manages buyer records, enforces unit availability rules, and coordinates with payment plans, collections, and registration modules.

## Scope

**In scope (implemented in PR-REDS-007):**
- Buyer registration and profile management
- Unit reservation (provisional hold)
- Sales contract creation and management
- Reservation-to-contract conversion
- Reservation expiry and cancellation
- Contract cancellation

**Out of scope (future PRs):**
- Payment collection (handled by Collections module — PR-REDS-009)
- Payment plan schedule generation (handled by Payment Plans module — PR-REDS-008)
- Title transfer and registration (handled by Registration module)
- Discount and incentive governance (handled by Sales Exceptions module)
- Commission assignment to sales agents

## Key Concepts

**Buyer:** A commercial party (individual or entity) linked to one or more reservations and contracts. Stores identity information including name, email, phone, and optional nationality.

**Reservation:** A provisional hold on a unit placed by a qualified buyer. Reservations have an expiry date. A unit can only have **one active reservation** at a time.

**Sales Contract (SPA):** A signed Sale and Purchase Agreement between the developer and the buyer. A contract locks the unit and agreed price. A unit can only have **one active or draft contract** at a time.

## Status Model

### Reservation Statuses

| Status | Description |
|---|---|
| `active` | Reservation is live and blocking the unit |
| `cancelled` | Reservation was cancelled before conversion |
| `expired` | Reservation passed its expiry date without conversion |
| `converted` | Reservation was successfully converted to a contract |

### Contract Statuses

| Status | Description |
|---|---|
| `draft` | Contract created but not yet formally executed |
| `active` | Contract is formally active |
| `cancelled` | Contract was cancelled |
| `completed` | Contract has been fully executed (future use) |

## Business Rules

- A unit can only have one active reservation at a time
- Reservations require pricing attributes to be set on the unit before creation
- A contract cannot coexist with another active or draft contract for the same unit
- Contract numbers must be globally unique
- When a reservation is converted to a contract, the reservation status transitions to `converted`
- Only `active` reservations can be cancelled or converted
- Only `draft` or `active` contracts can be cancelled or updated

## REST API

Base path: `/api/v1/sales`

### Buyers

| Method | Path | Description |
|---|---|---|
| `POST` | `/buyers` | Register a new buyer |
| `GET` | `/buyers` | List all buyers |
| `GET` | `/buyers/{id}` | Get a buyer by ID |

### Reservations

| Method | Path | Description |
|---|---|---|
| `POST` | `/reservations` | Create a reservation |
| `GET` | `/reservations` | List reservations (filterable by unit_id, buyer_id) |
| `GET` | `/reservations/{id}` | Get a reservation by ID |
| `PATCH` | `/reservations/{id}` | Update an active reservation |
| `POST` | `/reservations/{id}/cancel` | Cancel an active reservation |
| `POST` | `/reservations/{id}/convert-to-contract` | Convert a reservation to a contract |

### Contracts

| Method | Path | Description |
|---|---|---|
| `POST` | `/contracts` | Create a contract |
| `GET` | `/contracts` | List contracts (filterable by unit_id, buyer_id) |
| `GET` | `/contracts/{id}` | Get a contract by ID |
| `PATCH` | `/contracts/{id}` | Update a draft or active contract |
| `POST` | `/contracts/{id}/cancel` | Cancel a draft or active contract |

## Data Entities

### Buyer

| Field | Type | Notes |
|---|---|---|
| `id` | string (UUID) | Primary key |
| `full_name` | string | Required |
| `email` | string | Required |
| `phone` | string | Required |
| `nationality` | string | Optional |
| `notes` | string | Optional |

### Reservation

| Field | Type | Notes |
|---|---|---|
| `id` | string (UUID) | Primary key |
| `unit_id` | string (FK) | References `units.id` |
| `buyer_id` | string (FK) | References `buyers.id` |
| `reservation_date` | string | ISO date |
| `expiry_date` | string | ISO date |
| `status` | enum | `active`, `cancelled`, `expired`, `converted` |
| `notes` | string | Optional |

### SalesContract

| Field | Type | Notes |
|---|---|---|
| `id` | string (UUID) | Primary key |
| `unit_id` | string (FK) | References `units.id` |
| `buyer_id` | string (FK) | References `buyers.id` |
| `reservation_id` | string (FK, nullable) | References `reservations.id` |
| `contract_number` | string | Globally unique |
| `contract_date` | string | ISO date |
| `contract_price` | decimal | Required, must be > 0 |
| `status` | enum | `draft`, `active`, `cancelled`, `completed` |
| `notes` | string | Optional |

## Integration Points

| Module | Relationship |
|---|---|
| Units | Unit existence validated before reservation/contract creation |
| Pricing | Pricing attributes must exist on a unit before it can be reserved |
| Payment Plans (PR-008) | Contract triggers payment plan schedule generation |
| Collections (PR-009) | Deposits and installments tracked against contract |
| Registration | Contract triggers registration workflow (future) |

## Module Boundaries

The Sales module:
- **reads** unit records to validate existence
- **reads** pricing attributes to confirm a unit is priced before reservation
- **does NOT** modify pricing formulas
- **does NOT** generate payment schedules
- **does NOT** process collections or receipts
- **does NOT** calculate commissions or incentives

## Workflows

### Standard Reservation Workflow
1. Register buyer (`POST /sales/buyers`)
2. Confirm unit has pricing set (`GET /pricing/unit/{id}/attributes`)
3. Create reservation (`POST /sales/reservations`)
4. Reservation holds unit (only one active at a time)

### Reservation-to-Contract Conversion
1. Existing active reservation in place
2. `POST /sales/reservations/{id}/convert-to-contract` with contract payload
3. Reservation status → `converted`
4. Contract created with `reservation_id` linkage

### Direct Contract Creation
1. `POST /sales/contracts` (no prior reservation required)
2. Contract created in `draft` status

### Cancellation
- `POST /sales/reservations/{id}/cancel` → status `cancelled`
- `POST /sales/contracts/{id}/cancel` → status `cancelled`

