# Agreements — final client purchase drafts

Agreements is a standalone project section under Commercial, outside Development.
It answers: which final agreement drafts must a client sign to complete a purchase?
Each row has an agreement name, signing company, draft creation date and uploaded file.
The signing company is entered as text so each agreement can name its actual counterparty.
No company is guessed or automatically substituted from the project developer.

Add agreement opens a full page. All four fields are required. PDF and Word (.pdf,
.doc, .docx) files up to 10 MiB upload atomically with their metadata. The register
lists entries in creation order. Download uses an authorized same-origin request.
Edit changes name, company and business date. Document bytes are immutable: add a
new entry and delete the old entry to replace a final draft. Delete requires a
reason, removes the entry from the register and retains its bytes and audit history.
These are project templates, not signed buyer contracts or signature attestations;
there is no link to a sale and no effect on legal, commercial, payment or cash state.

## Access and persistence

Whole-project access is required; selected-phase users receive 404 for every route.
Sales readers may list/download. System Administrator, Project Manager, Sales
Operations and Legal may add, edit and delete; Master Administrator retains the
existing effective-role behavior. Membership is checked in SQL before loading data.
Project locks serialize mutations; expected_version prevents stale edits/deletions.
Files are returned as attachment/octet-stream with nosniff and private/no-store.
File extensions and container signatures are checked; no content is executed or
rendered inline and this is not a malware-scanning or legal-validation service.
Filename path separators/control characters, empty uploads and excessive sizes are
refused. The raw request is bounded while streaming, before storing bytes.

`project_agreements` owns metadata and PostgreSQL bytea documents, reusing the one
existing database with no new dependencies or filesystem/object-store infrastructure.
Deferred document loading keeps binary content out of register queries and responses.
This increases database/backup size by the stored documents. Audit stores metadata,
SHA-256 and actor/reason, never the document body. No original business files are imported.
Migration 0041 follows 0040 and adds only this table. Empty rollback is supported;
once any agreement exists, including deleted entries, rollback refuses to erase it.
Keep the schema and roll forward; revert application code only if needed.

## API

- GET /api/v1/projects/{project_id}/agreements
- POST same path: raw bytes, with name/signing_company/draft_created_on/filename query fields
- PUT /{agreement_id}: complete metadata with expected_version
- GET /{agreement_id}/document
- POST /{agreement_id}/delete: reason and expected_version

The page uses RecordPage, DraftBoundary, TableScroll and the shared reason dialog.
Loading, denied, failed, empty, upload/save failure and download failure remain distinct.
