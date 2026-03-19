# Registry

## Purpose

The Registry domain manages the post-sale legal transfer workflow for individual units. It tracks registration cases from initiation through title deed issuance, manages document checklists, and records milestone completion.

## Owned Entities

| Entity | Description |
|---|---|
| `RegistrationCase` | A single legal transfer case tied to a unit and its sale contract |
| `RegistrationMilestone` | A workflow step within a registration case (e.g., document submission, authority approval) |
| `RegistrationDocument` | A document required or uploaded as part of a case |

## Attached To

| Entity | Attachment Point |
|---|---|
| `RegistrationCase` | `unit_id` → `units.id` (FK) |
| `RegistrationCase` | `sale_contract_id` → `sales_contracts.id` (FK) |
| `RegistrationCase` | `project_id` — denormalized for list queries; validated server-side against unit hierarchy |

## Responsibilities

- Create and manage registration cases per sold unit
- Track milestone completion within each case
- Maintain document checklists per case
- Provide per-project registry summary (`GET /api/v1/registry/projects/{id}/summary`)
- Validate that the supplied `project_id` matches the unit's actual project (traversed via `Unit → Floor → Building → Phase → Project`)

## Forbidden Responsibilities

- Must not create pricing records or perform pricing calculations
- Must not import from the `pricing` module
- Must not perform finance aggregation calculations
- Must not modify sales contracts or payment schedules

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/registry/cases` | Create a new registration case |
| `GET` | `/api/v1/registry/cases/{case_id}` | Get a registration case |
| `GET` | `/api/v1/registry/cases/by-sale/{sale_contract_id}` | Get case by sale contract |
| `PATCH` | `/api/v1/registry/cases/{case_id}` | Update a registration case |
| `GET` | `/api/v1/registry/projects/{project_id}/cases` | List cases for a project |
| `GET` | `/api/v1/registry/projects/{project_id}/summary` | Project-level registry summary |
| `GET` | `/api/v1/registry/cases/{case_id}/milestones` | List milestones for a case |
| `PATCH` | `/api/v1/registry/cases/{case_id}/milestones/{milestone_id}` | Update a milestone |
| `GET` | `/api/v1/registry/cases/{case_id}/documents` | List documents for a case |
| `PATCH` | `/api/v1/registry/cases/{case_id}/documents/{document_id}` | Update a document record |

## Architecture Notes

The canonical API route prefix is `/api/v1/registry/*`. A backward-compatible alias
`/api/v1/registration/*` is served by the backend for legacy clients but is hidden from
the OpenAPI schema. New code must use `/api/v1/registry/*`.

## Integration Points

| Module | Relationship |
|---|---|
| Sales | `RegistrationCase` references `SalesContract` |
| Units | `RegistrationCase` references `Unit` |
| Finance | Finance dashboard reads registry summary for registration signal |
