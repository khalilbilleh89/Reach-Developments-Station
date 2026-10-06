# Governance / Team

Owner-requested project contact directory, delivered under `docs/ENGINEERING_RULES.md`.

The screen answers: who is involved, what do they handle, and how do I contact them?
Governance now contains Team before Documents and Access. Operations Team and Engineering
Team are separate sections, each with Add, readable person cards and its own pagination.
Search covers name, title, scope and email across both sections. Paging displays twelve
matches at a time without limiting stored contacts. All matching contacts remain reachable.

Each contact has Name, Title, Scope of Work and Email Address. Name and team are required;
the other details can be completed later. Names and emails are not unique identifiers.
There is no member quota and no application text-length cap. Blank optional values clear
the field; a supplied email must have email syntax. Text is rendered as plain text.

## Access and persistence

Team belongs to Projects, using `team_api.py`, `team_schemas.py`, `team_service.py` and
`team_models.py`. API root: `/api/v1/projects/{project_id}/team`. GET returns the directory
and `can_manage`; POST adds a person; PATCH `/{member_id}` updates supplied fields with
the saved version; POST `/{member_id}/delete` requires version and reason.

Every active project member may read the contact directory, including phase-scoped readers.
Only administrators and whole-project project managers may maintain it. The server derives
the manage affordance. Contacts neither create accounts nor grant roles, memberships or
approval authority. Team is independent of Commercial / Agents and Access.

Writes lock the owning project before selecting the project-scoped member. Stale updates
and removals return 409. Creation, changes and removal record actor and snapshots in Audit.
Every card exposes Delete to writers. A named confirmation explains retained removal and
requires a reason. Removed rows disappear from the directory; retained rows and audit remain.
There are no linked business records to cascade. Repeated removal returns 404.

## UI behavior

Canonical PageHeader, Card, DataToolbar, Disclosure and RecordPage components compose the
directory. The full-page editor uses DraftBoundary, disabled inputs during saves and a
structured validation summary. Successful saves close before refreshing. Failed mutations
keep the form; failed reads offer Retry rather than showing an empty team. Search and section
page state stay mounted when opening an editor. New contacts can be added to either section
and existing contacts moved between teams. Scope previews expand to full text; email links
open the user's email application.

## Migration and rollback

`0040_project_team` follows `0039_project_images`, adding only `project_team_members`.
No business facts are backfilled. Model and migration constraints protect the team choice,
nonblank name, positive version and project ownership. Downgrade succeeds only before any
contact history exists, including removed contacts. Once used, roll forward; application
code can be reverted while leaving this additive table in place. Never delete retained
contacts to force a downgrade.

Feature tests cover both teams, nullable PATCH, stale versions, invalid fields, more than
200 contacts, duplicate email, role/membership/phase behavior, project substitution,
audit retention, no user/access creation, and migration roundtrip with retained refusal.
Frontend interaction tests cover search, editing, paging, deletion wiring and failed saves.
Exact executed results and browser evidence belong in the PR review package.


## Optional Job Description attachment

After saving a person, choose **Attach job description** on their card. The full-page
attachment editor accepts one current PDF or Word file (.pdf, .doc, .docx), up to 10 MiB.
The member remains valid without a file. All Team readers can download an attached file;
only existing Team writers can upload, replace or delete it. Failed uploads retain the
selection and show an error; navigation warns about an unsaved file selection.

The existing Agreements document validator checks file name, size and file signature.
This is format checking, not malware scanning. Downloads force attachment disposition,
private/no-store caching and nosniff. Directory reads return only file ID/name, never bytes.

POST `/{member_id}/job-description` receives raw bytes with filename/version query fields;
GET on that path downloads the current file. POST `/{member_id}/job-description/delete`
requires the member version and a reason. Uploads authorize before reading the bounded
body, then lock the project and re-check member scope/version before writing. Every file
change increments the member version, so stale edits cannot race an attachment change.

Migration `0044_team_job_description` adds `team_job_descriptions`, with a partial unique
index for one current attachment per member. Replacement/removal retains previous bytes,
identity and hash; Audit records the actor and metadata, never document bytes. Removing a
member retains their files but makes them inaccessible through ordinary download routes.
No existing member is backfilled or made dependent on a file. Downgrade is allowed only
while the new table is empty; once history exists, retain it and roll forward or revert
application code without dropping the additive table.
