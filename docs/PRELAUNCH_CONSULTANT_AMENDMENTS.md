# Pre-Launch and Consultant Engineer amendments

Owner request, 12 September 2026. Governed by `ENGINEERING_RULES.md`.

Master Administrator / Boss may explicitly confirm their own Pre-Launch expense.
Ordinary users still require a different authorised Finance/CFO confirmer. System
Administrator is not Master Administrator. The same rule applies when a permitted
Pre-Launch category is confirmed through Cashflow. Other development categories,
financing and releases retain their existing database separation requirements.
Recording an expense does not confirm it automatically.

The locked confirmation service retains both actor identifiers and the
`master_self_confirmed` authority marker in the confirmation audit. A database
trigger checks active Master authority when the marker is first set. Checks
restrict the exception to Pre-Launch categories and an attributed confirmation;
the trigger protects that authority history after confirmation. Later role
removal does not invalidate historical cash or prevent an authorised reversal.
Reconciliation recognises the retained exception. No live user roles are changed.

The top category table uses the Cashflow service's Decimal aggregation over the
same scoped rows as the expense register. Recorded and confirmed amounts remain
separate. Total expenses is their sum, not a cash measure. Share is confirmed
category amount / confirmed total × 100, rounded to two decimals; a zero total
returns 0.00%. Removed and reversed records contribute zero. Existing project
currency and whole-project access restrictions apply; there is no FX conversion.
All ten allowed categories remain visible, including zero categories.

Consultant agreements in draft or active status expose Edit agreement. The
existing update endpoint accepts the same identity, reference, date, scope and
notes fields for active agreements. It keeps agreement ID, status, programme and
deliverables, checks `expected_updated_at` under the project lock, validates dates,
and records before/after audit data. Completed and terminated agreements stay
read-only. Existing editor permissions and project scope still apply.

## Migration and rollback

`0025_prelaunch_master` follows `0024_merge_permits_inventory`. It adds a false
authority marker to existing records and replaces only the development movement
separation check with the constrained exception plus trigger. No financial amounts
or business records are rewritten or removed.

Downgrade succeeds when no Master self-confirmation is retained. Once used, it
refuses even if the expense was reversed: restoring the old rule would invalidate
history. Preserve those records and roll forward with a correction. Do not delete
confirmation history to force a downgrade. Deploy backend/migration and frontend
together. This branch does not change Render configuration or production data.
