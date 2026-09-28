# Project image galleries

Project Overview contains three project-scoped presentation galleries: Interior,
Exterior and 3D renders. Any user who can open a project can view its active
images. The existing project-writer roles (`system_admin` and `project_manager`)
can add and remove them.

## Storage and delivery

The MVP stores image bytes in PostgreSQL in `project_images.image_data`. The ORM
defers that column, so `GET /projects/{project_id}/images` loads and returns
metadata only. Bytes are read through the dedicated authenticated route
`GET /projects/{project_id}/images/{image_id}/file`; its response is marked
`private, no-store` and `nosniff`.

Uploads use a raw request body. The server accepts JPEG, PNG and WebP signatures,
limits each image to 10 MB, and stores a trimmed basename capped at 200
characters. The declared browser MIME type is only an input convenience; stored
media type comes from the bytes.

The frontend intentionally uses `<img>` for the authenticated same-origin file
route. Next's image optimizer is a separate fetcher and cannot preserve this
session-bound access contract, so the local lint exception sits immediately
beside the element. Alternative text combines the category and stored filename.

## Isolation, removal and audit

Every metadata, file and removal lookup includes both `project_id` and
`image_id`. A valid image ID presented under another project returns 404.
Removed rows remain in the database with `removed_at` and
`removed_by_user_id`; normal lists and file reads exclude them.

Creation emits `project_image.created` and removal emits
`project_image.removed` in the same transaction as the row change. Audit data
contains project ID, category, filename, media type and removal attribution.
Image bytes are never copied into audit events.

The migration refuses to downgrade while any image history exists. Operational
rollback therefore means rolling the application forward or retaining the
schema until the rows have been handled under an approved retention process.
