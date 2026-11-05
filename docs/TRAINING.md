# Training

Creative > Training is a project-owned library of training sessions and their material.
Each entry requires a title, execution date (a business date without a timezone),
category and description. Categories are free-text labels with suggestions from
existing active entries, not separate configuration records. The register sorts
by execution date newest first and supports title/description/category search,
category/type filters and pagination.

One material belongs to each entry: an HTTPS Drive/video/reference link, an MP4
upload up to 50 MB, or a PDF upload up to 10 MB. Link destinations are not fetched
by the server, and opening them requires the source owner's sharing permission.
Uploaded MP4 containers receive bounded format checks and support authenticated
byte ranges for playback; codec compatibility depends on the browser. PDFs are
downloaded as attachments. There is no transcoding or external embed execution.

Whole-project readers can view entries. Project managers and system
administrators can create, edit and delete. Selected-phase access cannot read a
whole-project training record or its bytes. Metadata edits require the expected
version. Full-page entry and detail views use existing unsaved-change protection.
The original file/link is immutable; replacement uses retained deletion and a new
entry. Delete requires a reason and version, hides the item and denies subsequent
file access while retaining metadata, bytes, hashes and audit history. No other
records reference training entries. Up to 500 active entries are allowed per project.

`/api/v1/projects/{project_id}/training` provides the register; `/links` and
`/upload` create records; `/{id}` updates metadata; `/{id}/file` reads uploaded
content; `/{id}/delete` performs retained removal. All mutation checks lock the
project before inspecting/changing entries. The Projects module owns persistence;
it reuses Marketing's public `file_payload` validator without accessing Marketing
records. No production dependencies or financial calculations change.

Migration `0061_project_training` follows `0060_plan_categories`. Upgrade adds one
table and does not modify existing data. Downgrade is allowed only when the new
table is empty, including retained/deleted entries; once used, roll back application
code while retaining the additive schema. Never erase records to enable rollback.

Governed by docs/ENGINEERING_RULES.md and docs/DELETION_POLICY.md.
