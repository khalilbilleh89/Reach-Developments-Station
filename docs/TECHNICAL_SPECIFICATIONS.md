# Technical Specifications

Delivery → Technical Specifications is the project delivery guide for
sales and technical teams. Categories cover structure, finishes, sanitary fittings,
plumbing, cold/hot water, aluminium/glazing, doors/joinery, kitchen/appliances,
electrical, heating/cooling, shared facilities and other items.

Each entry states the item, project/shared-area or unit scope, optional applicable
areas or unit types, plain-language technical specification, optional buyer benefit, optional brand/model,
inclusion (included, optional upgrade, excluded or undecided), draft/confirmed state
and supporting document/revision. Applicability is descriptive, not an automatic
unit assignment or an override of a buyer's signed agreement. Search includes
applicability, source, brand and benefit; filters separate project/unit and confirmation.
Only populated sections appear: Engineered for long-term performance; Finishes for daily living; Comfort, efficiency & clean design; Outdoor living & shared facilities. No empty checklist cards or project claims are pre-populated.

Confirmation requires a decided inclusion. Supporting document/revision and applicability details are optional. It records
the technical writer's confirmation of the specification, not installation, work
certification or legal approval. Every change records actor, time and before/after
values. Version checking rejects stale edits.

## Access and deletion

Sales Advisor and Sales Operations may read this guide, as may existing Construction
readers. Sales sees only the standalone specification page and never requests the financial summary or other
cost tabs. Existing financial API permissions are unchanged. The register describes
the whole project, so whole-project membership is required; selected-phase members
receive an explicit refusal. System Administrator, Project Manager and Design /
Engineering can maintain entries (Master Administrator inherits these rights).

Delete is visible beside each entry for writers and requires a reason. Draft rows without image history
are removed; confirmed rows and rows with image history are removed from the active guide with their source
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

## Sales companion presentation — 2026-10-20

Construction retains Contracts as its default and places Technical Specifications immediately beside it. Sales has only the specification tab and defaults to confirmed items. Writers can see drafts, edit full-page and delete from the same guide. Each feature pairs the technical description with an optional recorded buyer benefit; coverage, inclusion, brand and qualifications remain visible. Source/revision and update date live in a disclosure. No source document is imported as confirmed project data. No conceptual illustrations are presented as approved renderings.

Revision 0051_specification_benefit follows 0050_project_matrices and adds buyer_benefit with an empty default, preserving existing specifications. Old clients omitting it preserve existing text on update. Audit before/after/deletion snapshots include it. Downgrade refuses while any active or retained benefit exists. It changes no financial calculation or cost access.

## Standalone Delivery page and optional images — 2026-10-29

Delivery lists Construction and then Technical Specifications as separate entries. The guide is no longer a Construction sub-tab. Existing bookmarked constructionTab=technical-specifications links still resolve to the standalone guide. Sales sees the specification entry without receiving Construction cost access.

The add/edit form accepts optional JPEG, PNG or WebP images (up to 10 MB each, 20 active images per specification). No image is required to save or confirm a specification. Images can be added later from Edit, viewed full-page, or removed with a named reason prompt. Text persistence and image uploads are separate transactions: if an upload fails, the saved record ID/version is retained and only unuploaded files are retried. The form blocks departure while saving and protects unsaved file selections.

The server decodes images, bounds pixels, strips metadata and stores normalized PNG bytes. Reads and writes enforce existing whole-project specification scope, including the owning specification. Metadata lists contain no binary bytes. Removed images and specifications with image history retain stored evidence/audit and stop serving bytes. An unused draft without images keeps its physical deletion path.

Migration 0054_specification_images follows 0053_marketing_economics; no backfill or new dependencies. Downgrade refuses any active or retained image row. Image evidence is excluded from legacy intake. No costing, financial formulas or role authority changes.

The Where it applies dropdown also offers All buildable area. Applicable areas or unit types and Supporting document/revision remain optional even for confirmed records. Empty applicability displays only the chosen scope; a missing source remains explicitly Not recorded. Migration 0054 relaxes only those constraints and refuses downgrade for records that the older mandatory-field/scope rules cannot represent.
