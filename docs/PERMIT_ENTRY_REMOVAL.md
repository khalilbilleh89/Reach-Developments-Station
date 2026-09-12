# Permit entry and removal

Add permit opens a full-page editor. Identity, current status and effective date,
scope, owners, application details, dates, fee, conditions and management flags
can be supplied in one save. An optional new permit type is created in the same
transaction; failed permit validation does not leave a registered type behind.
The current status records an existing fact, not a new authority approval.
Subsequent changes continue through the audited status-transition endpoint.

System and Master Administrators can delete a permit after confirmation. Removal
is soft deletion: the permit disappears from active registers, summaries and
current reporting projections, but its row, status events, audit and document
references remain. Document files are not deleted. An active dependent permit
must have its prerequisite cleared first. Deleted codes can be reused; identifiers
and historical references remain distinct. Historical monetary facts still count
for currency-change safeguards.

API additions: optional `initial_status` and `new_permit_type` on permit creation;
`GET /api/v1/projects/{project_id}/permit-assignees` for active project members and
the current author; administrator-only
`DELETE /api/v1/projects/{project_id}/permits/{permit_id}` returning 204.
Removed permit reads and mutations return 404.

Migration 0023 adds nullable `deleted_at` and replaces the permit-code unique
constraint with a unique index scoped to active rows. Upgrade retains every row.
Back up before downgrade. Downgrade refuses duplicate codes created by reuse;
resolve/export those records with owner approval before retrying. Otherwise,
downgrade restores the original unique constraint and drops the marker, so
retained permits become visible again. Do not silently discard retained records.

No production deployment or data removal is performed by opening this draft PR.
Independent review and exact-head Full Backend/Frontend checks remain required.
