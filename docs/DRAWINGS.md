# Drawings

Development → Design → Drawings is a project library independent of consultant
appointments. Only drawing name and PDF are required. Optional drawing number,
category, building/floor/location, revision, status and notes support search and
filters. Status is a library label, not consultant acceptance or authority approval.

Full-page creation, metadata editing and review use the shared RecordPage. Back
retains register filters, and unsaved forms use DraftBoundary. Review supports
all PDF pages, fit-width and zoom; the original is available for vector detail and
printing to scale. Raster previews are limited to 4096 pixels on their longest side.
PDFium runs in a separate process with a 30-second limit; PDF scripts are never
rendered in the browser. Invalid/encrypted pages report an error with retry and
original-download fallback. Upload validation checks size, filename and PDF signature;
it does not certify drawing content, authenticity or engineering adequacy.

The API at `/api/v1/projects/{project_id}/drawings` uses existing Design readers
and editors (Project Manager and Design / Engineering). System Administrator is
read-only unless also assigned an editor role. All routes require whole-project
scope, applied in SQL. Selected-phase users cannot read files or previews. Uploads
are authorized before streaming and again under the project lock after reception.
Each PDF is limited to 10 MB and stored as deferred binary data in PostgreSQL;
register requests never load file bytes. No new dependency or external storage.

PDF bytes are immutable. Add each new revision separately and mark the old record
Superseded when appropriate; no automatic latest-revision inference or overwrite.
Metadata changes require the expected version. Delete is visible on each writable
card, requires a reason and expected version, hides the record and retains bytes,
checksum, metadata and attributed audit events. There are no links from other
business records to drawings and no cascading financial/approval mutations.

Migration `0053_project_drawings` follows `0052_design_payments`, adds one table,
and requires no backfill. Downgrade succeeds only while the table is empty; even
deleted evidence prevents downgrade. After any upload, roll forward or revert the
application while retaining this additive schema. Reconcile migration ordering
with other pending PRs before merge. Governed by docs/ENGINEERING_RULES.md.
