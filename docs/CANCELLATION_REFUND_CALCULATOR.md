# Cancellation refund calculator

Sales cancellation terms are calculated from cash the developer currently holds for
the sale. The operator chooses an exact deduction fraction; the browser displays the
server response and performs no money arithmetic.

## Cash contract

`collections.read.eligible_cancellation_cash` is the narrow, read-only boundary from
Sales into Collections. It uses the platform's current-standing predicate and returns:

```text
eligible collected cash = standing confirmed receipts - standing confirmed refunds
```

Recorded or reversed receipts do not count. Confirmed cash counts even when it is not
allocated to an instalment. Standing confirmed refunds are subtracted so previously
repaid cash cannot become refundable twice. Every included row must use the contract
currency; there is no FX conversion and mixed-currency data fails closed.

The read contract imports Collections models and core standing rules only. It does not
import Sales service, so `sales.service -> collections.read` does not create the existing
`collections.service -> sales.service` cycle.

## Formula and persistence

The canonical API rate is a Decimal fraction from 0 through 1. Using the repository's
`money()` helper and `MONEY_EXPONENT` (`0.01`, `ROUND_HALF_UP`):

```text
deduction amount = money(eligible collected cash * deduction rate)
refund due       = money(eligible collected cash - deduction amount)
```

The calculated deduction is stored in the existing `forfeiture_amount`; the calculated
refund is stored in the existing `refund_due_amount`. The basis, rate, deduction, refund,
currency, actor and time are retained in append-only cancellation audit events. No schema
migration or backfill is required.

## Preview, approval, and concurrency

The preview is informational. Opening a cancellation locks the project, rereads current
cash, and rejects an expected basis that became stale. Until financial approval, reads
and advancement checks use current cash. Financial approval is the freeze point: under
the same project-first lock it rereads cash, rejects a stale reviewed basis, persists the
derived amounts, and audits exactly what the checker approved.

Receipt confirmation and reversal take that project lock before changing standing cash.
Once cancellation terms are approved they are refused, preventing an approved liability
from silently diverging. If receipt confirmation wins first, approval sees the new basis
and requires renewed review; if approval wins first, receipt confirmation is refused.

`CollectionRefund` remains the only evidence that money actually left the company. A
Sales cancellation records and approves liability; it never marks that liability paid.
