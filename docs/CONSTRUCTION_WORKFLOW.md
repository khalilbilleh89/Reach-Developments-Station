# Construction contract and payment workflow

A signed agreement starts with its contract total, retention rate, advance entitlement and stated tax rate. Save and activate is immediate for a construction preparer. Existing drafts can be activated from the first contract page. No budget or manual contract lines are required.

## Existing agreements

A reconciled legacy allocation is preserved. When an unused draft has incomplete allocations, registering the signed agreement replaces those draft allocations with the authoritative signed total and retains their before-image in audit. Linked records block replacement. Submitted contracts without allocations use the same atomic registration path.

## Certificates and invoices

The contract's Certificates tab creates a draft valuation with one period work amount, retention release, advance recovery, other deductions, tax and evidence reference. The server uses the sole contract allocation automatically. Legacy contracts with multiple allocations require choosing the existing scope; their allocations are not silently redistributed.

Enter work for the current period, not cumulative work already certified. Retention is calculated from the contract rate. A different authorized technical user certifies submitted work. Physical milestone completion remains a separate fact and workflow. Draft certificates have Delete; posted evidence has rejection/reversal with dependency checks.

The Invoices & payments tab records advance, progress, retention-release and final invoices. Advance claims are bounded by the agreed entitlement; other invoices name a certified valuation and cannot exceed its remaining authorization. Invoice approval still requires a different Finance/CFO user. Delete voids retained invoices and refuses paid evidence until its payment is reversed.

## Actual payments and reconciliation

Record payment already made remains an immediate, evidenced cash entry. Selecting an approved invoice atomically settles that invoice by the entered amount. Cross-contract, unapproved, disputed and overpaid selections are refused before any payment is saved. Leaving the invoice blank retains the existing direct-contract behavior.

An advance invoice settlement increases paid advance. Later certificates recover that advance; entitlement alone does not count as paid cash. Reversing a payment restores the invoice outstanding amount, and an advance with recovered cash cannot be reversed prematurely. The UI displays server-reported retained, recovered, paid and outstanding figures separately. Contract balance is not the same as invoices currently due.

All monetary inputs and outputs remain decimal strings. No schema migration or new dependencies. No source invoice, bank information or real project records are included in fixtures.
