# Returning a cancelled unit to market

There are two distinct paths for the same physical Unit ID.

- A mistaken, unsigned/test Sale can be removed by Master Administrator. The old
  Sale and Reservation are retained as cancelled evidence; the existing Sales
  removal flow checks Inventory release blockers and moves the Unit to Available
  when safe, or Held when a gate fails. A new buyer starts a new Reservation.
- A genuinely cancelled contract completes the governed cancellation first.
  The Unit becomes Returned and its old price approval is invalidated. Returned
  is not offered by Sales > New Reservation. Pricing must prepare, approve and
  activate a **new** current price version. Release date, active status and
  commercial block are checked by Inventory's `release_blockers`. Sales
  Operations then explicitly chooses **Return to market** in Sales > Commercial
  stock, gives a reason, and Sales asks Inventory to record Returned → Available
  and its status event. Only then is the Unit offered for a fresh Reservation.

The action locks the project and Unit, requires a completed cancellation on a
cancelled Sale for that project/Unit, rejects a live commitment, and checks the
current Sales quote as well as release blockers. A repeated request or a
different project's Unit is refused. It does not reopen or reuse the old Sale,
Reservation or price version, and does not move any plan, receipt, refund or
commission. Old transactions, financial and legal evidence remain attached to
their original identifiers. No schema migration or Commission payment workflow
is involved.
