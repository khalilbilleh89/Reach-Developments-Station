# Marketing attachments

Branding includes a logo register accepting PNG and JPEG. Materials appears directly
below Branding and holds categorized images, videos and document references. Each
entry has a title, required free-text category and optional notes. Categories are
labels, not separately managed records. Search, category/type filters and paging
run on the server.

Images accept PNG/JPEG up to 10 MiB and 20 million pixels. The server decodes and
normalizes them to PNG, stripping metadata; downloads therefore use a PNG filename.
PDF references accept up to 10 MiB and are download-only. MP4 videos accept up to
50 MiB and support authenticated byte-range playback. Container validation does
not guarantee that a browser supports the video's codec; downloading remains
available. HTTPS links, including Google Drive links, support larger files and
other video formats. External resources are never fetched by the server and keep
their provider's sharing permissions. Link titles, categories and notes remain
editable; replacing a file or URL requires deleting the old entry and adding one.

The existing Marketing reader/writer roles and whole-project scope apply to every
operation, including file access. Upload authorization is checked before reading
the body and checked again when committing. The project lock serializes creation
and changes. Limits are 20 active logos and 500 active materials per project.

Uploads are retained in PostgreSQL with a SHA-256 digest. Payloads are deferred
from ordinary list queries and excluded from audit snapshots and JSON responses.
This requires backup/storage capacity planning, especially for video; Drive links
avoid storing video bytes in the application database. PDF signature checks and
MP4 container checks are format validation, not malware scanning.

Every item has a visible Delete action requiring a reason and expected version.
Deletion hides it from lists and prevents subsequent file access while preserving
the bytes and audit history. Deleting a link never deletes the remote resource.

Migration 0058 adds only marketing_assets and needs no backfill. Downgrade is
allowed only while the table is empty; even deleted history blocks removal.
Rollback a deployed application without dropping this table once evidence exists.

Coverage: tests/modules/test_marketing_assets.py exercises lifecycle, scope,
validation, range downloads, stale versions, audit retention and migration drift.
frontend/tests/marketing.test.mjs covers editor validation and preserved drafts.
