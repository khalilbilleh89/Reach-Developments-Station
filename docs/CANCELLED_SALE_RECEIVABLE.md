# A cancelled sale leaves the active receivable

Owner-requested correction. Governed by
[ENGINEERING_RULES.md](ENGINEERING_RULES.md) §6 and
[ARCHITECTURE.md](ARCHITECTURE.md) §7.

## What the owner reported

When a purchase is cancelled, the original contractual receivable should no
longer sit in the normal active-sale reconciliation as though the developer
still expects to collect the purchase price.

## What was happening

Collections already marked every instalment of a cancelled contract
`cancelled`, and already kept its future instalments out of the forecast
cashflow. The money did not follow the label. `InstallmentView` still carried
the full shortfall in `outstanding`, still counted the days past the grace
boundary and still named an aging band, so a terminated contract went on
contributing to:

- `outstanding_total`, `due_total` and `overdue_total` on the account;
- `oldest_overdue_days` and `installments_overdue`;
- the project strip's per-currency totals and its aging bands;
- the aging report's rows;
- the portfolio and management-reporting overdue figures that total the same
  register.

The row said cancelled and the figures beside it said collectible.

## The rule

An instalment is an **active receivable** only while the contract behind it is
live as at the reporting date. A cancellation is the only thing that ends the
obligation: a dispute, a waiver or a restructure is a reason an obligation is
not being met, not a reason it stopped existing.

Two names on the row carry the distinction, and every consumer inherits them:

| Field | Means | After cancellation |
| --- | --- | --- |
| `outstanding` | What the schedule was short | Unchanged |
| `receivable` | The part still collectible | `0.00` |

`due_amount` and `overdue_amount` follow `receivable`. `scheduled`, `paid`,
`overdue_days` and `bucket` are left exactly as they were, because how the
account stood when it was unwound is part of the record of the unwinding.
`scheduled − paid = outstanding` still holds on every row.

Retained without change: the contract price, the payment plan and its
instalments, every receipt and allocation, the cancellation record with its
forfeiture and refund due, the refund transactions and the audit history.
Nothing is rewritten and nothing is erased; the transaction's economic
classification is what changed.

## As at, not now

The cutoff is the one Collections already uses — the date the unit return took
effect, not the date somebody typed the cancellation in. A March read of a June
cancellation still shows March's live receivable, because the contract was live
in March. This behaviour is unchanged and is covered by the existing
as-of consistency tests.

## The clearance interlock

Until now a cancelled contract was held out of collection clearance by arrears
that should never have been in the figures. Removing them would have let the
absence of a balance read as a clear account, so cancellation is now a blocker
in its own right: *this contract has been cancelled*. An account with nothing
outstanding because the contract ended is not an account that was cleared.

## API

`CollectionInstallmentRow` gains `receivable` (money string) beside the existing
`outstanding`. Additive; no field changed type or meaning, and no existing field
was removed. The server sends both so that no screen derives one from the other
— the browser performs no financial arithmetic here, as everywhere else.

## Scope

No schema change, no migration, no backfill, no new permission and no new
dependency. `ledger.py`, `service.py` and `schemas.py` in `collections`, plus
the frontend type. No other module was touched: the register, the project
summary, the aging report, the portfolio risk figures, the cashflow read
contract and management reporting all total the same derivation and were
corrected by correcting it.

## Verification

Regression coverage asserts both halves at every level — that a live contract's
receivable, demand, arrears and ageing are unaffected, and that a cancelled
one's go to nothing on the account, the register, the project strip and the
aging report while its schedule, receipts and per-row shortfall stay intact.
The clearance refusal is covered on both the read and the write path.

Draft publication is not deployment. Independent review, exact-head Full CI and
a human merge remain required by repository policy.
