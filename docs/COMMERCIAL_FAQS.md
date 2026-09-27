# Commercial FAQs

Commercial > FAQs keeps a separate reusable question-and-answer library for each project.
The library starts empty. No business answers or customer records are imported.

- Add FAQ and Edit use a full page with a question and multiline plain-text answer.
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

## Schema and rollback

Migration 0039_commercial_faqs follows 0038_commission_beneficiaries and adds one table
with project foreign key, project index, text limits and a positive version. No backfill.
Downgrade refuses while FAQ rows remain. Prefer rolling back application code while
retaining the additive table. Export and explicitly resolve FAQs before schema downgrade;
ordinary deletion retains the full audit evidence. Never remove records merely to deploy.

## Review

Governed by ENGINEERING_RULES.md and DELETION_POLICY.md. No dependencies added, no
financial calculations changed, no production database used. Focused API tests cover
lifecycle, audit, stale writes, denied roles, phase/project isolation, validation and
migration forward/reverse/retained-data behavior. Frontend tests exercise copy, failure,
search and draft retention. Independent review and exact-head Full CI precede human merge.
