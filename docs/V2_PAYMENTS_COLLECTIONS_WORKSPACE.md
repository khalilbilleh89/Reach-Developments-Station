# MVP 2 batch 3 — Payment plans and collections journal

Implements V2-07 and V2-08 under [ENGINEERING_RULES.md](ENGINEERING_RULES.md),
using Khalil's supplied MVP document as a requirements reference.
Built on batch 2 (#260). Merge #259, then #260, then this batch. Its draft
targets the batch 2 branch so reviewers see only this batch's changes.
The current workflow runs only for PRs targeting main. Rebase and retarget
after the preceding batch merges, complete independent review, and require
green Backend and Frontend on the final head before a human merges.

## Operator workflow

From a unit's Sales & legal tab or the sale's Payment plan tab, Collections
can create the SPA schedule or open its existing builder. Simple instalments
show label, due date and percentage or principal amount. Event triggers,
relative dates and grace periods are expandable; existing non-default terms
keep those controls visible. Tax/fee allocation remains explicit. Saving
uses the server's reconciliation. Collections submits; a separate CFO
approves and activates. Existing versions, revisions, history and restructure
controls remain available, and the governing version remains the summary's
source while a revision is prepared.

The unit's Collections tab opens the sale's receipt journal directly.
Collections records amount, date, bank reference and notes; Finance confirms
the receipt. The journal also offers the existing allocation and reversal
actions to their authorized roles. A failed receipt submission preserves the
entered values. Receipts stay visible before a schedule becomes active.
The project Collections account opens on Receipt journal for today's position;
historical reports open on Position with the existing historical controls.

## Confirmed percentage definition

The owner confirmed: confirmed receipts divided by total SPA payable,
including tax and buyer fees, multiplied by 100. The denominator is the sale's
frozen `total_contract_price`, copied from reservation `total_buyer_payable`.
The numerator uses the existing dated ledger's confirmed receipts. Recorded
receipts do not count; reversed receipts cease counting from their reversal.
Historical reads reconstruct that day's effective confirmation state.

Unapplied confirmed cash counts in the percentage but does not reduce an
instalment's outstanding balance. Refunds remain separate and do not reduce
the gross confirmed-receipts numerator. Overpayments can exceed 100%; a
zero payable returns null and displays Not applicable. Decimal arithmetic
rounds the percentage half-up to two decimal places. No FX conversion or
browser financial arithmetic is introduced. Percentage is not a settlement
or clearance decision.

Collection summary responses add `spa_total_payable` (money string) and
`collected_percentage` (decimal percentage string or null). Existing fields
and cash/clearance calculations retain their meanings. One shared frontend
progress component displays these server fields in unit, sale and account
contexts. No schema migration, backfill or new dependency is required.

## Validation and remaining gates

Regression coverage includes percentage rounding, zero/overpayment,
confirmation/reversal, dated reads, refunds and an SPA with tax and buyer fees.
Existing receipt, allocation, refund, payment-plan lifecycle/reconciliation
and product-experience tests are included in the focused regression run.
Browser validation uses synthetic records: schedule preparation, separate CFO
approval/activation, receipt recording, Finance confirmation, allocation and
failed-submission input preservation. Eleven roles are checked at six widths.
Actual run outcomes are recorded in the pull request. Local checks do not
replace independent review and final exact-head GitHub CI.
