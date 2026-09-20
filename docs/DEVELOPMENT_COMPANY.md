# Development Company

Company appears immediately above Land under Development.
The selected company's page has Company Information and Bank Details.
Projects may hold multiple companies; each company may hold multiple bank accounts.

All descriptive fields are optional, including company name and every bank field.
Blank text is stored as null. PATCH omission preserves a value; explicit null clears it.
Account numbers, IBAN and SWIFT are text, preserving leading zeroes and entered formatting.
No jurisdiction-specific format or completeness requirement is imposed.

Company fields: legal name, trading name, registration number, tax/VAT number,
legal form, country of registration, registered address, contact person, email,
phone, website, authorized signatory and notes.

Bank fields: beneficiary name, beneficiary bank, account number, IBAN, SWIFT code,
bank address, correspondent bank and correspondent bank SWIFT.

## Access and removal

Whole-project membership is required. Master/System Administrators bypass membership.
Project financial readers may read; administrators, project managers and Finance
may create, edit and delete. Phase-only membership cannot read or change these
project-wide bank details. The UI gates requests before loading.

Every company and bank account exposes Delete with a named, reasoned confirmation.
Removal retains the row and audit record and hides the record from active lists.
A company with active bank accounts cannot be removed until those accounts are removed.
Repeated removal and edits to removed records return 404. Every mutation locks the
project before checking the parent or child; identifiers are always parent-scoped.
No transaction, payment, balance or financial calculation is introduced.

The existing Project developer-entity text remains independent: this feature does
not silently rewrite existing legal, sales, or project records.

## Migration and rollback

0033_project_company adds project_companies and company_bank_accounts after
0032_building_units. Existing data is untouched. Empty tables can downgrade;
any retained company or account row blocks downgrade, including removed rows.
After use, roll forward; do not drop recorded banking information to roll back code.

Full-page entry reuses RecordPage and protects dirty forms. Failed saves retain
the draft. Successful saves and deletions reload the register.

## Validation

PostgreSQL tests cover empty/partial entry, multiple accounts, leading zeroes,
clearing values, role denial, phase/project/company isolation, dependent accounts,
repeat removal, retained audit, migration roundtrip and guarded downgrade.
Frontend tests cover optional fields, failed-save draft retention, account rendering
and request gating. Browser checks use synthetic data on an isolated local database.
Repository policy: docs/ENGINEERING_RULES.md and docs/DELETION_POLICY.md.
