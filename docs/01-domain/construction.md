# Construction

## Purpose

The Construction domain tracks delivery progress for active development projects. It manages construction scopes, milestones, and progress updates, giving project teams visibility into on-site execution status.

## Owned Entities

| Entity | Description |
|---|---|
| `ConstructionScope` | A defined scope of work for a project (e.g., structural, MEP, finishes) |
| `ConstructionMilestone` | A trackable delivery milestone within a scope |
| `ConstructionProgressUpdate` | A timestamped progress update for a milestone |
| `ConstructionCostItem` | A cost line item associated with a construction scope |
| `ConstructionEngineeringItem` | An engineering/consultant deliverable tracked within a scope |

## Attached To

Construction scopes attach at the project/phase level via `project_id`.

## Responsibilities

- Create and manage construction scopes per project
- Define and track delivery milestones within each scope
- Record progress updates against milestones
- Track cost items and engineering deliverables per scope
- Provide a construction dashboard endpoint for project-level status

## Forbidden Responsibilities

- Must not create pricing records or sales contracts
- Must not perform financial aggregation calculations
- Must not modify unit status (unit status is managed by the Units domain)

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/construction/scopes` | Create a construction scope |
| `GET` | `/api/v1/construction/scopes` | List construction scopes |
| `GET` | `/api/v1/construction/scopes/{scope_id}` | Get a scope |
| `PATCH` | `/api/v1/construction/scopes/{scope_id}` | Update a scope |
| `DELETE` | `/api/v1/construction/scopes/{scope_id}` | Delete a scope |
| `POST` | `/api/v1/construction/milestones` | Create a milestone |
| `GET` | `/api/v1/construction/milestones` | List milestones |
| `GET` | `/api/v1/construction/milestones/{milestone_id}` | Get a milestone |
| `PATCH` | `/api/v1/construction/milestones/{milestone_id}` | Update a milestone |
| `DELETE` | `/api/v1/construction/milestones/{milestone_id}` | Delete a milestone |
| `POST` | `/api/v1/construction/milestones/{milestone_id}/progress-updates` | Add a progress update |
| `GET` | `/api/v1/construction/milestones/{milestone_id}/progress-updates` | List progress updates |

## Integration Points

| Module | Relationship |
|---|---|
| Projects | Construction scopes reference `project_id` |
| Settings | Construction cost items may reference settings templates (future) |
