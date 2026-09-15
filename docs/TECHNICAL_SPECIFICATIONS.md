# Technical Specifications

Delivery → Construction → Technical Specifications is the project delivery guide for
sales and technical teams. Categories cover structure, finishes, sanitary fittings,
plumbing, cold/hot water, aluminium/glazing, doors/joinery, kitchen/appliances,
electrical, heating/cooling, shared facilities and other items.

Each entry states the item, project/shared-area or unit scope, explicit applicable
areas or unit types, plain-language delivery description, optional brand/model,
inclusion (included, optional upgrade, excluded or undecided), draft/confirmed state
and supporting document/revision. Applicability is descriptive, not an automatic
unit assignment or an override of a buyer's signed agreement. Search includes
applicability, source and brand; filters separate project/unit and confirmation.
Empty categories say Not yet specified. Nothing is pre-populated as a project fact.

Confirmation requires a decided inclusion and a nonblank source reference. It records
the technical writer's confirmation of the specification, not installation, work
certification or legal approval. Every change records actor, time and before/after
values. Version checking rejects stale edits.

## Access and deletion

Sales Advisor and Sales Operations may read this guide, as may existing Construction
readers. Sales sees only this tab and never requests the financial summary or other
cost tabs. Existing financial API permissions are unchanged. The register describes
the whole project, so whole-project membership is required; selected-phase members
receive an explicit refusal. System Administrator, Project Manager and Design /
Engineering can maintain entries (Master Administrator inherits these rights).

Delete is visible beside each entry for writers and requires a reason. Draft rows
are removed; confirmed rows are removed from the active guide with their source
values retained. Audit snapshots survive both. Repeated deletion returns 404.
There are no links to financial transactions or cascading deletions.

## Migration and rollback

Revision 0031_technical_specs follows 0030_unit_removal and adds one table with
project foreign key, allowed-value, nonblank and confirmation constraints. No source
records or business specifications are backfilled. Downgrade works for an empty
register and refuses while any active or retained row exists. Prefer a forward fix
after use; preserve exports and audit evidence before any operational rollback.

No dependencies, environment variables, financial formulas or Render settings change.
Follows ENGINEERING_RULES.md and DELETION_POLICY.md. Publish as Draft for independent
review; human merge requires current Full Backend and Frontend gates.
