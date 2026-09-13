# Buyer-first sales and master-admin removal

Owner-requested Sales amendment, 12 September 2026. Governed by
[ENGINEERING_RULES.md](ENGINEERING_RULES.md) and [DELETION_POLICY.md](DELETION_POLICY.md).

## Operator flow

1. Open **Agent/Buyer**, immediately above Sales in the project menu.
2. Register the buyer and optional agent Country, Branch, Branch Leader and Agent.
   Existing buyers have the same fields in Edit buyer. Missing values stay unknown.
3. Select **Connect unit** next to the buyer. The selected buyer follows the unit
   picker into the reservation form. Master Administrator starts in the direct
   register-and-mark-sold flow and may switch to a standard reservation.
4. Saving opens the unit's transaction under **Sales**. Its **Agent** tab shows
   the four attribution fields. Authorized sales writers may correct a sale's
   attribution with a reason, including on older sales.

Agent fields describe the salesperson's team, not the buyer's nationality or
property location. They are textual business attribution, separate from the
existing advisor account used for permissions. They create no user accounts or
permission grants and do not change commission distribution. Each reservation
copies the buyer's attribution; its sale copies that snapshot. Later buyer edits
do not rewrite existing transactions. A sale-specific correction affects that
sale only and records actor, timestamp, reason and changed field names.

## Removal and cancellation

**Delete sale** appears in the record header for Master Administrator. The
confirmation names the sale and requires a reason. The DELETE endpoint retains
the original rows and audit evidence, closes the sale and associated reservation,
and excludes both from current Sales. History remains readable. An eligible
unsigned unit returns to Available; failed release gates put it on Hold. An old
draft cannot release another transaction's commitment. Retries are harmless.

**Delete reservation** also supports unfinished preparations and live reservations.
It retains their history and closes any associated draft contract. Preparations
do not release a unit held by another buyer.

Signed or collection-active contracts use the prominent **Start cancellation**
action. Existing cancellation cases, registry obligations and completed handovers
cannot be bypassed by Delete. Cancellation retains its financial approvals,
withdrawal requirements and unit-return rules; completing it returns the unit for
repricing. No receipt, refund, signature or legal withdrawal is invented or erased.
Removing sales does not remove buyers with transaction history.

## API and migration

- Client create/update/read: four optional `agent_*` fields.
- Reservation and sale reads: four optional attribution snapshot fields.
- `PUT /projects/{project_id}/sales/contracts/{sale_id}/agent`: complete attribution
  replacement plus reason; existing sale visibility and sales-writer authority.
- `DELETE /projects/{project_id}/sales/contracts/{sale_id}?reason=...`: master only,
  project/visible-unit checks and project/unit locks, retained cancellation.
- Existing reservation `/cancel` supports draft/deposit-pending removal as well.

Migration `0025_sales_agent_details` adds nullable strings to clients, reservations
and sale_contracts after `0024_merge_permits_inventory`. No inferred backfill and
no new tables or dependencies. Downgrade drops only the new fields: export their
values before rollback, or prefer rolling application code forward after use.
Historical sales and buyer records otherwise remain untouched.

Migration `0027_merge_sales_areas` joins the Sales attribution branch with
`0026_common_areas` (including `0025_prelaunch_master`). It changes no data and
does not rewrite either parent's history. Databases on either branch upgrade to
one head; tests verify both paths and model/schema agreement. Downgrading the
merge alone only separates the heads; parent rollback safeguards still apply.

## Verification and release

Behavior tests cover attribution snapshots/corrections, removal and resale,
permissions, wrong project, signed-sale cancellation, retries, audit and migration
round-trip. Frontend checks cover buyer-to-unit routing, retained correction drafts,
registration payloads, navigation and build. Tests use disposable PostgreSQL only.
Draft publication is not deployment. Independent review, exact-head Full CI and
human merge remain required by repository policy.
