# Development workspace and owner unit removal

The Development sections (Overview, Land, Permits, Pre-Launch, Consultant Engineer
and Inventory) share a scoped visual treatment and a permission-aware section
navigation. Record pages retain their contextual Back links, full-page layout and
unsaved-change handling. Other modules keep their current visual treatment.

Unit details use concise metric labels, explanatory notes and exact decimal-string
area formatting. The owner deletion confirmation identifies the unit and explains
the impact on current Inventory and Sales before a reason is submitted.

## Master Administrator removal

Only the actual `master_admin` role can remove a unit. A System Administrator or
an account with several operational roles cannot obtain this override. The existing
Inventory DELETE endpoint enforces this rule on the server as well as in the UI.

An unused unit is physically deleted with its removable physical child records.
When a unit has a commercial commitment or retained references, removal records
`removed_at` and sets `is_active` false instead. Inventory pages and counts exclude
removed units; current Sales transactions exclude the same units in SQL. Sales
history remains available. Removal is one committed owner decision, with project,
unit reference, actor, timestamp and reason in the audit trail. Retrying retained
removal does not duplicate the event. Removed units cannot be edited/reactivated
through ordinary Inventory forms and cannot be selected for a new sale.

This action is not legal cancellation, repayment, or a ledger reversal. Existing
contracts, receipts, obligations and legal evidence are retained with their original
values and statuses. Buyer records are not deleted. Linked historical records can
continue to prevent physical deletion of a containing floor or building.

## Migration and rollback

`0030_unit_removal` follows `0029_merge_installment_tax` and adds one nullable
timestamp. Upgrade rewrites no business history. Downgrade is supported before
any retained unit removal; after use it refuses, preventing removed stock from
silently reappearing. Retain the schema and roll forward after removal history exists.

Governed by `docs/ENGINEERING_RULES.md` and `docs/DELETION_POLICY.md`. No production
or development dependencies are added. Removal, permissions, wrong-project scope,
register/history consistency, idempotency, measurements and migration rollback have
dedicated PostgreSQL tests. The UI role and scoped API call have a frontend test.
