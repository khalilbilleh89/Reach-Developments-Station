# Inventory launch scope

Owner-requested scope, 12 September 2026. Governing policy: [ENGINEERING_RULES.md](ENGINEERING_RULES.md).

Inventory maintains phases, buildings, floors, unit features, measured areas and
launch list prices. A unit has Overview, Property, Pricing and Release tabs.
Release offers only release as Available; server eligibility, permissions and
append-only history remain authoritative. Removing completeness cards does not
remove release validation.

Sales > Commercial stock owns the manual uncommitted status controls, legal
eligibility, holds, four status dimensions, status history and delivery detail.
Reservations, buyer registration, contracts and collections continue through
their existing Sales workspaces. Unit records and existing transaction history
are preserved; this is a UI ownership change, not a database migration.

Direct launch price drafts no longer require a change reason. Existing reasons
remain stored. Approval rationale and maker/checker rules are unchanged.

`GET /projects/{project_id}/inventory/launch-values` returns paginated current
launch prices and totals across the complete matching inventory selection.
Inventory supplies a SQL selection narrowed by project/phase permissions and
the same physical filters used by its register. Pricing computes the values.
Readers must have live-price access; legal-only roles are refused. Totals are
separate per currency and exclude missing prices and prices requiring review.
The population includes previously released inventory and is labelled as such;
these are potential list values, not contracted revenue or remaining-stock value.

No production data changes, migrations or new dependencies are required.

## Property editing

Identity, Features and Additional fields each own a local Edit/Save/Cancel form.
Each form exposes only its section's fields, sends changed fields through the
existing PATCH contract, and retains inputs on validation failure. Navigation
uses the existing unsaved-change guard. The broad top-level Edit unit action is
replaced by the local section actions.

Physical measurements appear once; editing starts or resumes a draft revision,
and approval is available beside that revision. Approved history and computed
Net/Gross values remain read-only. Additional features, plans/specifications,
and parking/storage each have their own editor; their creation forms are hidden
until Edit is pressed. Read-only users can inspect attachments without receiving
write controls. A failed Property read has a retry instead of rendering stale
editable fields.
