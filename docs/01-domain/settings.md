# Settings

## Purpose

The Settings domain provides system-level configuration for the platform. It manages reusable policy templates that other domains reference when calculating prices, commissions, and generating new projects.

## Owned Entities

| Entity | Table | Description |
|---|---|---|
| `PricingPolicy` | `settings_pricing_policies` | Reusable pricing rules template |
| `CommissionPolicy` | `settings_commission_policies` | Reusable commission calculation template |
| `ProjectTemplate` | `settings_project_templates` | Default configuration for new projects |

## Attached To

Settings entities carry no foreign key to any project or unit. They are system-level configuration records reused across multiple projects.

## Responsibilities

- CRUD management of pricing policy templates
- CRUD management of commission policy templates
- CRUD management of project templates
- Provide configuration that other domains (pricing, commission) can reference

## Forbidden Responsibilities

- Must not own pricing calculation results or per-unit pricing records (owned by Pricing domain)
- Must not own commission payment records (owned by Commission domain)
- Must not modify project hierarchy structures

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/settings/pricing-policies` | Create a pricing policy |
| `GET` | `/api/v1/settings/pricing-policies` | List pricing policies |
| `GET` | `/api/v1/settings/pricing-policies/{policy_id}` | Get a pricing policy |
| `PATCH` | `/api/v1/settings/pricing-policies/{policy_id}` | Update a pricing policy |
| `DELETE` | `/api/v1/settings/pricing-policies/{policy_id}` | Delete a pricing policy |
| `POST` | `/api/v1/settings/commission-policies` | Create a commission policy |
| `GET` | `/api/v1/settings/commission-policies` | List commission policies |
| `GET` | `/api/v1/settings/commission-policies/{policy_id}` | Get a commission policy |
| `PATCH` | `/api/v1/settings/commission-policies/{policy_id}` | Update a commission policy |
| `DELETE` | `/api/v1/settings/commission-policies/{policy_id}` | Delete a commission policy |
| `POST` | `/api/v1/settings/project-templates` | Create a project template |
| `GET` | `/api/v1/settings/project-templates` | List project templates |
| `GET` | `/api/v1/settings/project-templates/{template_id}` | Get a project template |
| `PATCH` | `/api/v1/settings/project-templates/{template_id}` | Update a project template |
| `DELETE` | `/api/v1/settings/project-templates/{template_id}` | Delete a project template |

## Integration Points

| Module | Relationship |
|---|---|
| Pricing | References pricing policies when configuring per-unit pricing |
| Commission | References commission policies when calculating agent commission |
| Projects | References project templates when bootstrapping new projects |
