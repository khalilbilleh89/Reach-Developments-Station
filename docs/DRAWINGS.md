# Drawings

Development → Design → Drawings is a project library independent of consultant
appointments. A drawing title and either a PDF upload or Google Drive sharing link are required. Optional drawing number,
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
Each PDF is limited to 50 MB and stored as deferred binary data in PostgreSQL;
register requests never load file bytes. No new dependency or external storage.

PDF bytes are immutable. Add each new revision separately and mark the old record
Superseded when appropriate; no automatic latest-revision inference or overwrite.
Metadata changes require the expected version. Delete is visible on each writable
card, requires a reason and expected version, hides the record and retains bytes,
checksum, metadata and attributed audit events. There are no links from other
business records to drawings and no cascading financial/approval mutations.

Migration `0056_project_drawings` follows `0055_commercial_emails`, adds one table,
and requires no backfill. Downgrade succeeds only while the table is empty; even
deleted evidence prevents downgrade. After any upload, roll forward or revert the
application while retaining this additive schema. Reconcile migration ordering
with other pending PRs before merge. Governed by docs/ENGINEERING_RULES.md.

## Plans workspace — 2026-11-05

Delivery → Plans sits immediately above Construction and opens the same existing drawing library. Design → Drawings remains a compatible entry to these records; no PDF is copied or moved. Five primary disciplines are Architectural, Electrical, Mechanical, Structural and Shop Drawings. Existing General/MEP/Landscape/Interiors classifications are preserved and remain filterable/editable; they are never guessed into a new discipline. New uploads default to Architectural and ask only for title, category and PDF; optional metadata is behind More details.

Uploads inspect PDF parsing, page presence and first-page geometry before persistence, outside the project write lock, rejecting unreadable/encrypted/empty PDFs without creating a record. Upload does not rasterize the document: preview rendering is deferred until the user opens a plan. A page-specific rendering failure does not prevent retention of a readable original. The full-page viewer offers previous/next, direct page selection and fit-width/150–300% zoom with keyboard-scrollable inspection. Raster viewing does not execute PDF scripts or trigger a download; optional original downloads retain vector detail.

Migration0060_plan_categories follows0059_marketing_assets and extends only the category constraint. No backfill, permission changes or new dependencies. Downgrade refuses active or retained records in new categories. The same versioned, reasoned removal and audit rules apply in Plans.

PDFium previews use its limited image cache and encode directly from the live bitmap, avoiding redundant full-size image copies. The 4096-pixel review limit and 30-second worker timeout remain. This keeps upload validation independent of large CAD-sheet raster memory; it does not assert a fixed memory bound for arbitrary PDFs.

## Large PDFs and Drive links — 2026-11-05

Upload PDF accepts up to 50 MiB (52,428,800 bytes, labelled 50 MB), enforced in the browser, streaming API, database and isolated PDF worker. Files over the limit are refused without creating a record. The non-raster upload inspection and limited-cache preview behavior remain.

Google Drive link is an alternative source in the same form and register. HTTPS links on drive.google.com and docs.google.com are accepted; credentials, alternate hosts/ports, control characters and other protocols are rejected. The server never fetches the link. Open plan shows its details and an explicit Open plan in Google Drive action in a new tab; Drive controls access, content and sharing. No local PDF snapshot or automatic synchronization is implied. Uploaded PDFs continue to use the in-system viewer.

A plan has exactly one source, protected by a database constraint. Source bytes/URL are immutable; add another plan for a changed source. Metadata edits and reasoned removal retain their existing version, scope and audit rules for both kinds. Removed links remain as history and disappear from the register; this does not delete the external Drive file.

Migration 0063_plan_sources follows 0062_project_training, preserves old uploads and adds a nullable source URL while expanding the size constraint. Downgrade refuses any active or retained link or PDF over 10 MiB. Roll forward after these sources are recorded; do not truncate files or discard links to downgrade.
