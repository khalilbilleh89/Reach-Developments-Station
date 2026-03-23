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

A construction scope can attach at the project, phase, or building level. The scope model carries three optional foreign keys — `project_id`, `phase_id`, and `building_id` — with the constraint that **at least one must be set**. This allows scopes to be defined at whatever granularity is appropriate (whole-project, per-phase, or per-building).

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

> The table below lists the primary endpoints. See the FastAPI auto-generated docs (`/docs`) for the complete, authoritative endpoint reference.

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/construction/projects/{project_id}/dashboard` | Project-level construction dashboard |
| `POST` | `/api/v1/construction/scopes` | Create a construction scope |
| `GET` | `/api/v1/construction/scopes` | List scopes (filterable by `project_id`, `phase_id`, `building_id`) |
| `GET` | `/api/v1/construction/scopes/{scope_id}` | Get a scope |
| `PATCH` | `/api/v1/construction/scopes/{scope_id}` | Update a scope |
| `DELETE` | `/api/v1/construction/scopes/{scope_id}` | Delete a scope |
| `POST` | `/api/v1/construction/milestones` | Create a milestone |
| `GET` | `/api/v1/construction/milestones` | List milestones |
| `GET` | `/api/v1/construction/milestones/{milestone_id}` | Get a milestone |
| `PATCH` | `/api/v1/construction/milestones/{milestone_id}` | Update a milestone |
| `DELETE` | `/api/v1/construction/milestones/{milestone_id}` | Delete a milestone |
| `POST` | `/api/v1/construction/milestones/{milestone_id}/cost` | Update milestone cost (planned/actual) |
| `POST` | `/api/v1/construction/milestones/{milestone_id}/progress-updates` | Add a progress update |
| `GET` | `/api/v1/construction/milestones/{milestone_id}/progress-updates` | List progress updates |
| `GET` | `/api/v1/construction/progress-updates/{update_id}` | Get a progress update |
| `DELETE` | `/api/v1/construction/progress-updates/{update_id}` | Delete a progress update |
| `POST` | `/api/v1/construction/scopes/{scope_id}/engineering-items` | Add an engineering item |
| `GET` | `/api/v1/construction/scopes/{scope_id}/engineering-items` | List engineering items |
| `PATCH` | `/api/v1/construction/engineering-items/{item_id}` | Update an engineering item |
| `DELETE` | `/api/v1/construction/engineering-items/{item_id}` | Delete an engineering item |
| `POST` | `/api/v1/construction/scopes/{scope_id}/cost-items` | Add a cost item |
| `GET` | `/api/v1/construction/scopes/{scope_id}/cost-items` | List cost items |
| `GET` | `/api/v1/construction/scopes/{scope_id}/cost-summary` | Aggregated cost summary |
| `GET` | `/api/v1/construction/scopes/{scope_id}/cost` | Milestone-level cost variance overview |
| `GET` | `/api/v1/construction/cost-items/{cost_item_id}` | Get a cost item |
| `PATCH` | `/api/v1/construction/cost-items/{cost_item_id}` | Update a cost item |
| `DELETE` | `/api/v1/construction/cost-items/{cost_item_id}` | Delete a cost item |

## Integration Points

| Module | Relationship |
|---|---|
| Projects | Construction scopes reference `project_id` |
| Settings | Construction cost items may reference settings templates (future) |
