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

## Explicit owner-approved unit history purge

The owner has requested an exception for removed units with closed sales and
reservations. **Inventory → Removed units → Purge unit and linked history** is
a separate Master Administrator operation. It previews record counts and transaction
references, requires the exact unit reference, a reason and an acknowledgment of
irreversible history deletion. Ordinary Delete and Delete permanently retain their
existing protections.

Only cancelled sales and cancelled, expired or converted reservations are eligible.
Confirmed receipts/refunds must first be reversed through Collections. An explicit
ownership map includes inventory details, prices, closed sale/reservation history,
payment schedules, collection history, commission entries and unit progress/costs.
It does not expand through arbitrary foreign keys. Shared dependencies block the
entire purge; audit events, clients, project configuration and saved reports remain.
Database locks and a fresh full-record fingerprint prevent confirming stale contents.
All deletions and the `unit.purged` audit event commit together or roll back together.
The reason, identity, transaction references and record counts remain in audit.

This is a narrow, owner-approved cross-domain maintenance exception implemented in
`app/modules/inventory/purge.py`, not a general cascade policy or domain write API.
