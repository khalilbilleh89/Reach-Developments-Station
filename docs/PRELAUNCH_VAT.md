# Pre-Launch expense VAT

Owner request: 18 October 2026. Governing policy: `ENGINEERING_RULES.md`.

Add expense accepts **Amount excluding VAT** and optional **VAT (%)**. A blank
percentage means zero VAT. The read-only preview shows VAT and Total including VAT
from the Cashflow service. For example, 1,000.00 at an entered 5% gives VAT 50.00
and total 1,050.00. The percentage is supplied by the operator; this feature does
not determine tax applicability or recoverability.

`amount_ex_vat` and `vat_rate_percent` retain the inputs on the existing development
movement. `amount` remains the gross payable/cash value. VAT is net × percent / 100,
rounded half up to two decimal places; gross is net plus that rounded VAT. Money
uses Decimal, project base currency, and the existing 18-digit/two-decimal money
range. Percentage permits 0–100 with up to four decimal places. A check constraint
requires a complete, nonnegative-rate breakdown and matching gross amount.

Preview, create and unconfirmed correction share one calculation. The frontend
never calculates money and will not submit until the preview matches the current
input. It ignores late results, retains failed drafts and permits preview retry.
Tax fields also participate in optimistic expected-state comparisons, so a changed
tax breakdown invalidates confirmation/removal even if the gross total is equal.
The existing project lock, actor permissions, Boss exception and audit remain.

The register and schedule display net, percentage, VAT and total. Recorded,
confirmed, category, cashflow and downstream financial totals continue to use the
single gross movement. Confirmation adds it once; reversal removes it from current
cash. The financial system gains no separate VAT cash movement or duplicate cost.

Historical movements retain their original gross and null tax inputs. Their UI
says **VAT breakdown not recorded**, rather than inventing tax-free treatment.
Editing can preserve that legacy total. Choosing Enter VAT breakdown clears the
unknown gross input so the operator explicitly enters net; it cannot accidentally
be treated as net and taxed a second time. Once a breakdown exists, corrections
must retain the explicit net/rate form (zero VAT remains available).

## Migration and retained removal

`0048_prelaunch_vat` follows `0045_inventory_masterplans`, adds two nullable columns
and one check, and leaves every existing amount unchanged. Empty/legacy-only
downgrade is supported. Retained VAT breakdowns, including zero-rate, removed or
reversed entries, block downgrade to avoid losing evidence; roll forward instead.

Existing Remove (unconfirmed, reasoned retained removal) and Reverse (confirmed)
remain available. Both retain VAT inputs and audit. The preview creates no record.
No new record lifecycle, library dependency, infrastructure or environment setting
is introduced. Deploy the migration/backend and frontend together after review.
