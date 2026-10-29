# Commercial FAQs

Commercial > FAQs keeps a separate reusable question-and-answer library for each project.
The library starts empty. Answers are entered manually or imported from the project's Excel template.

- Add FAQ and Edit use a full page with a question and multiline plain-text answer.
- Aligned responsive cards show question headers, answer previews and consistent Copy/Edit/Delete
  actions. Long answers expand in place; Copy always includes the complete saved answer.
- Search matches both questions and answers. Copy answer copies only the saved answer,
  preserving line breaks and Unicode. If clipboard access fails, the screen explains
  how to select and copy the text manually; it never reports a false success.
- Unsaved text remains in memory with the standard dirty-form guard. Failed saves retain
  the draft. Version checks refuse stale edits and stale deletion.
- Sales readers assigned to the project may read general project FAQs, including
  selected-phase readers. FAQs are general project guidance, never buyer-specific data.
- System/Master Administrators, whole-project Project Managers and Sales Operations
  may create, edit and delete. Server permissions decide can_edit and every mutation.
- Delete is visible on each editable register entry, names the question, requires a reason,
  takes the project lock, checks the version, and retains full text in the audit trail.
  No dependent records exist and no buyer, contract or financial records are changed.

## Excel template and bulk import

Choose **Import from Excel**, download the template, fill **Question** and **Answer** on
the FAQs sheet, upload, validate, then import. The full-page workflow retains the selected
file on errors, reports Excel row numbers, and prevents repeat submission after success.
Return to the register refreshes the list and retains the previous search.

The template is bound to this project. Both fields are required, using the same limits as
manual entry (500/20,000 characters). Blank rows are ignored; multiline Unicode text is
preserved. Duplicate questions (case-insensitive, trimmed) in the file or project block
the entire batch. Existing answers are never overwritten. Edit those records individually.

The server authorizes the same whole-project FAQ writers before reading the upload.
Workbooks are capped at 5 MB, 64 MB expanded and 1,000 records. The existing archive guard
rejects invalid/macro packages; formulas, cell errors, wrong project/version, changed
headers and extra populated columns are refused. Validation creates no records. Apply
reparses and rechecks current questions under the same project lock used by manual writes,
then creates ordinary audited FAQs in one transaction. Any failure rolls back the batch.
Imported cards retain the existing versioned, reasoned Delete action and audit history.

Endpoints: GET `/projects/{project_id}/faqs/import/template` and POST
`/projects/{project_id}/faqs/import/{validate|apply}`. The existing Sales import report and
frontend upload page are reused. No new schema, dependency or stored import job is introduced.

## Schema and rollback

Migration 0043_commercial_faqs follows 0042_marketing and adds one table
with project foreign key, project index, text limits and a positive version. No backfill.
Downgrade refuses while FAQ rows remain. Prefer rolling back application code while
retaining the additive table. Export and explicitly resolve FAQs before schema downgrade;
ordinary deletion retains the full audit evidence. Never remove records merely to deploy.

## Review

Governed by ENGINEERING_RULES.md and DELETION_POLICY.md. No dependencies added, no
financial calculations changed, no production database used. Focused API tests cover
lifecycle, audit, stale writes, denied roles, phase/project isolation, validation and
migration forward/reverse/retained-data behavior. Frontend tests exercise copy, failure,
search, expansion, import validation and draft retention. Import tests cover atomicity,
duplicate/replay checks, project/role scope, workbook bounds and deletion audit retention.
Independent review and exact-head risk-based CI precede human merge.
