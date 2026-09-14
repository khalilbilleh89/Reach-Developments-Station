# Missing units and permanent deletion

A retained removal sets `units.removed_at` and `is_active=false`. Current
inventory excludes that row, including when Activity is **Active and inactive**.
The database still reserves its project reference and floor/unit number. This
prevents creating a different identity with the same reference while historical
transactions still point to the original unit.

## Recover the existing unit

Master Administrator can open **Inventory → Removed units**, search by number
or reference, and choose **Restore**. Confirmation names the unit and requires a
reason. Restoration keeps the original UUID, measurements, prices and commercial
status, clears `removed_at`, and activates the unit. Its phase, building and floor
must be active. Cancelled sales and reservations stay in transaction history.
It does not release inventory, cancel a transaction, or create a new sale.

The server scopes discovery and restoration by project and restricts both to
Master Administrator (who has whole-project/phase access). It locks project then
unit and writes one `unit.restored` audit event. Retrying an already-restored
unit succeeds without another event. The normal removal action remains available.

## Delete from SQL permanently

**Delete permanently** is available to Master Administrator on the unit page and
the Removed units page. It calls the existing DELETE route with `permanent=true`.
The server physically deletes an eligible unit and its inventory detail rows;
its number and reference can then be used for a new unit with a different UUID.
This operation is irreversible. Its reason and original identity stay in audit.

Commercial commitments and dependent business records block permanent deletion.
The response names a safe category, such as price versions, reservations or sale
contracts. All attempted inventory detail deletions roll back. This explicit
mode never falls back to retained removal. A cancelled transaction can still
have references and therefore still block deletion.

The existing default DELETE behavior is preserved: unused units are physically
deleted; linked or committed units are removed from current registers with
history retained. Confirmation explains both cases. Direct SQL cascading deletes
are not part of either workflow.

## API and checks

- `GET /api/v1/projects/{project_id}/inventory/removed-units` supports search,
  limit (1–200) and offset. It returns identity, location, status and removal time.
- `POST /api/v1/projects/{project_id}/inventory/units/{unit_id}/restoration`
  accepts `{ "reason": "..." }` and returns the original unit.
- `DELETE /api/v1/projects/{project_id}/inventory/units/{unit_id}?permanent=true&reason=...`
  returns 204 only after physical deletion; a missing unit returns 404.

No schema migration, uniqueness relaxation, dependency addition or financial
calculation change is required. Ordinary deletion retains financial/legal history.
The explicit purge exception below is documented in `DELETION_POLICY.md`.

Regression coverage is in `tests/modules/test_inventory_recovery.py`: discovery,
restore, history preservation, duplicate diagnostics, owner authorization,
project isolation, inactive hierarchy, retry behavior, permanent SQL deletion,
reference reuse, linked-record rollback, and deletion after restoration.

## Purge a removed unit and its closed history

When a cancelled sale or reservation blocks **Delete permanently**, choose the
separate **Purge unit and linked history** action on its Removed units row. The
full page previews the exact record counts and sale/reservation references. Review
them, enter a reason, type the exact unit reference and acknowledge history erasure.
The final button permanently deletes those records from SQL, freeing the unit number
and reference. It also removes source document links, not externally stored files.
Audit events, shared clients, settings and saved reporting snapshots remain.

Active sales/reservations, confirmed receipt/refund cash and shared dependencies
block the entire operation. Close or reverse the transaction through its owning
workflow before refreshing the preview. A stale commercial status on an old removed
unit does not block an otherwise eligible purge: the source documents are checked.
If records change after preview, confirmation fails and a fresh preview is required.

- `GET /api/v1/projects/{project_id}/inventory/units/{unit_id}/purge-preview`
  returns counts, references, blockers and a content fingerprint without writes.
- `POST /api/v1/projects/{project_id}/inventory/units/{unit_id}/purge` requires
  `reason`, `confirm_reference`, `fingerprint` and `acknowledge_history_deletion: true`.
  Returns 204 after atomic erasure; repeated requests return 404. Both routes require
  Master Administrator and scope the unit to the selected project.

`tests/modules/test_inventory_purge.py` exercises the new exception in PostgreSQL.
There is no automatic purge during deployment and no database migration. Rolling
back code removes the feature but cannot recover data already purged.
