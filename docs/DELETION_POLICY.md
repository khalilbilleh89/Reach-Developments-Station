# Deletion is part of creation

Every user-created record needs a discoverable Delete action on its register row or record
page. This includes project configuration, reference choices, hierarchy, child records,
drafts and imported records. An Add/Edit feature is incomplete without its removal flow.

## Required behavior

1. Show Delete to the authorized role next to the record. Identify the record in confirmation.
2. Explain whether removal is permanent or retains history; require a reason for audited records.
3. Authorize on the server and enforce project and phase scope. UI visibility is not security.
4. Lock the owning scope while checking references and removing the record. Reject dependent
   records with a useful explanation; do not silently erase children or financial/legal evidence.
5. Permit deletion of unused configuration and removable drafts. For posted/approved records,
   retain evidence and expose the supported reversal/cancellation/retirement flow explicitly.
   Such a lifecycle action is not a substitute for deleting an unused draft.
6. Record who removed what, when and why. Keep enough identity in the audit event after removal.
7. Refresh the list and selection after success; retain the confirmation and explain errors.
8. Test removal, permissions, scope isolation, dependencies, repeat requests, audit retention
   and affected totals where applicable.

## Enforcement

`AGENTS.md` makes this a standing agent instruction. The PR template requires removal evidence.
`tests/test_deletion_contracts.py` inventories record-creation handlers and fails when a new
handler lacks a reviewed deletion contract. `docs/deletion_contracts.json` records existing
coverage and gaps. This structural guard complements behavior tests; it cannot prove that a
button works and must not be described as doing so.

Audit and reporting outputs derived from other records are not ordinary editable records.
Do not add destructive history deletion merely to satisfy a checkbox. Document their retention
contract and the removal path for their source records.
