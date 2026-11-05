# Commercial Emails

Commercial > Emails appears immediately below FAQs. Each project has an initially
empty library with Internal Emails, Clients Emails and External Emails sections.
Templates have a category, title, subject and formatted body. Search
matches title, subject and body within the selected section.

Add and Edit open full pages. Delete is available beside each editable template,
names the template, requires a reason, checks its version under the project lock,
and retains the complete content in the audit log. There are no dependent records.
Failed saves preserve the form, and stale edits/deletes return a conflict.

Customize & copy opens a separate full-page composer for any reader. Editing this
in-memory copy does not change the saved template. Copy body, Copy subject and Copy
entire email preserve Unicode, line breaks, bold, italic, underline, strikethrough,
bullets and numbered lists. The toolbar also offers clear formatting, undo and redo.
Copy body and Copy entire email publish both HTML and plain text so rich email
composers can preserve formatting. Plain-text destinations use the text fallback.
Browsers without rich clipboard support explicitly report plain-text copying.
Clipboard failures provide manual
copy guidance. Unsaved-change protection covers both template edits and customized
drafts. Customized drafts are not persisted in browser storage or the database.
Placeholders such as [Client name] are plain text for the user to replace.

All three categories share existing Sales project-reader permissions, including
selected-phase readers. Category describes the intended email audience, not access
control. Store reusable guidance, not private correspondence or buyer records.
System/Master Administrators, whole-project Project Managers and Sales Operations
may create, edit and delete. The server enforces every mutation and project scope.
No email is sent and there is no mailbox integration, AI generation or attachment
storage. No business templates or factual claims are seeded.

## Migration and rollback

0060_email_rich_text follows 0059_marketing_assets and adds nullable body_html.
Existing body text is unchanged and treated literally, never interpreted as HTML.
The server accepts only inert text-formatting tags with no attributes, URLs, styles,
images or embedded content, and derives the searchable plain body from that HTML.
Limits are 20,000 plain characters and 100,000 HTML characters. Deleted templates'
HTML remains in the existing audit evidence. An older API client omitting body_html
preserves it when body is unchanged, and clears it when body changes; explicit null
also clears formatting. No backfill is required.

Downgrade of 0060 refuses while formatted templates remain. Roll application code
back with the additive column retained; export and explicitly resolve content before
a schema downgrade. Native editing commands retain browser undo history without a
new editor dependency; because execCommand is deprecated, browser compatibility
should be included in future browser-support reviews.

0055_commercial_emails follows 0054_specification_images. It adds commercial_emails with
project foreign key, category/length/version constraints and project index. No
backfill or existing-record change. Downgrade refuses while templates remain;
roll application code back while retaining the additive table, or explicitly
export and resolve records before schema downgrade. Do not delete live records
merely to deploy. Reconcile migration ordering if another branch merges first.

## Validation and review

Governed by ENGINEERING_RULES.md and DELETION_POLICY.md. API tests cover lifecycle,
all categories, validation, role denial, selected-phase write denial, wrong-project
access, stale edits/deletion, repeated deletion and retained audit content. Migration
tests cover roundtrip, drift and refusal to lose retained templates. Frontend tests
cover customization, exact copy output, clipboard failure, category/search filtering
and draft retention. Independent review and successful exact-head CI are required
before human merge; publishing a draft PR does not deploy the feature.
