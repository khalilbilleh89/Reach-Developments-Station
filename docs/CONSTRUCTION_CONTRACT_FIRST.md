# Construction: signed contracts and actual payments

Owner-requested workflow change, 20 September 2026.

Construction opens on Contracts. Add a signed main/subcontractor agreement with its document reference and save to activate immediately. Existing draft or submitted agreements can also be registered as signed. No budget version, headroom or second activation approval is required. Existing allocations must reconcile; a new agreement receives one contract allocation automatically. Historical budget data and APIs remain intact for compatibility, but the construction workspace no longer exposes budget controls or forecast budget comparisons.

Finance and project managers can register signed agreements. Finance records payments already made, with date, positive amount, currency and proof reference. This records cash evidence immediately as confirmed; it does not authorize or execute a bank transfer. Invoices and certificates are optional supporting workflows. The legacy invoice-allocation and independent confirmation path remains available to API consumers.

## Amounts

The server calculates with Decimal and existing currency precision:

- Revised value excluding tax = original signed amount + approved additions - approved reductions.
- Revised value including tax = revised value excluding tax × (1 + contract tax fraction), rounded to existing money precision.
- Remaining contract balance = revised value including tax - all confirmed, unreversed contract payments.

A negative balance is an overpayment/credit. Missing tax leaves gross value and remaining balance unavailable; zero explicitly records no tax. Remaining contract balance is the unpaid agreement total, not a claim that all of it is due today. Certified entitlement, retention and invoice payable remain distinct. Direct payments do not silently settle an invoice; invoice outstanding subtracts only confirmed invoice allocations, while total paid includes all confirmed payments. Cashflow's existing payment reader includes direct payments without inventing an invoice or certificate allocation.

Additions and reductions use the existing variation ledger. Enter a positive magnitude and choose addition or reduction; the server stores the appropriate signed delta. Changes remain subject to existing independent approval/escalation and cannot take a cost-code commitment below zero or already-certified work. Original contract value and approved history are preserved.

## Corrections and audit

An unused draft contract can be deleted. Removing an unused signed/submitted entry cancels it with a reason and retains history; any linked variation, certificate, invoice or payment blocks removal. Draft variations can be deleted; submitted changes can be withdrawn; approved mistakes need an opposite variation. Confirmed payments can be reversed with a reason, including direct payments, and then no longer count as paid.

Signed registration and direct payment registration have distinct audit events. Contract, project and role checks remain server-side. No credentials, bank integration, production data or new dependency is introduced.

## Migration and rollback

`0033_contract_payments` adds a non-null boolean discriminator, default false, preserving all legacy payment behavior. Upgrade before releasing the frontend. Downgrade is allowed only while no direct-payment history exists; once used, fix forward. Reversed direct payments still count as retained history and prevent downgrade. Never delete payment records to force a rollback.

## Validation scope

Focused PostgreSQL tests cover no-budget registration, direct payments, additions, reductions, reversal, invoice-balance separation, guarded removal, migration rollback, draft conversion and overpayments. Frontend behavior tests cover the new payloads, navigation, and preserving a failed form. See the pull request for executed validation results and remaining browser review requirements.
