# Operations Commission

The Commissions tab contains Sales Commissions (the existing percentage-based workflow) and Operations Commission (fixed entries). Existing sales grants, allocations, release checks and calculations are unchanged.

Each operations entry links an existing active project client and records one beneficiary / recipient name, a required reason, and a positive fixed amount. Add further entries for additional beneficiaries. No sale is required. Creation captures the project base currency; edits preserve the stored denomination. Amounts use Decimal / NUMERIC(18,2); overprecision, non-finite and nonpositive inputs are rejected. This register records commissions, not approval or payment; it does not enter cashflow, sales percentages, portfolio release figures or Unit Economics.

Existing commission reader/preparer roles and whole-project scope apply. Client choices expose only identity and reference, not contact or identity-document details. Client display is a saved snapshot; the stable client ID is the relationship. A retired client can remain on its original entry, but cannot be selected for a new entry.

Add/edit/detail use full pages with unsaved draft protection. Delete requires a reason and the current version; it hides the entry but retains its original identity, amount, client reference and audit history. Linked buyers cannot be physically deleted, including after retained commission deletion. Concurrent stale edits/removal fail with 409. Repeated deletion returns 404.

Migration 0070_operations_commissions follows 0069_company_profile and adds only its own table. No backfill. Empty downgrade is safe; any retained row blocks downgrade. Roll back application code while keeping the additive schema if records exist. Never run a destructive rollback on business data.
