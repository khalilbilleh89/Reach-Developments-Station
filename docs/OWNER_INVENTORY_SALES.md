# Owner inventory and sales controls

## Owner access

The existing Master Administrator role includes system-administrator rights and
owner approval overrides. In Settings > Users, an administrator can edit users,
including their own roles. Saving one's own permissions refreshes the session.
This change does not grant Master Administrator to any live account automatically.

## Correct and delete records

Inventory forms allow corrections to phase/building/floor codes and unit inputs.
Administrators can move buildings between phases and floors between buildings
inside one project. Master Administrators can correct a unit's floor after release.
UUIDs and frozen sale terms do not change. Hierarchy moves invalidate affected
units' pricing approval, so the current location must be reviewed before repricing.

Administrator-only Delete controls require confirmation and a recorded reason.
Delete units before their empty floors, and floors before their empty buildings.
Unused buyers and their parties can also be deleted. Referential constraints
protect pricing, reservations, contracts, financial and legal history; deletion of
a referenced record fails atomically. Deletion is permanent, not a recycle bin.
Deactivation remains subject to the existing lifecycle rules. No bulk deletion or
automatic deletion of live data is included.

Buyer contact, KYC and party details have edit forms. Existing permissions and
server-side personal-data filtering still apply. Approved area measurements are
corrected through a new revision, preserving the original evidence.

## Area and price definitions

- Net Area = Internal Area + Balcony Area.
- Gross Area = Net Area + Roof Garden + Terrace + Front Garden + Porches.
- Price per sqm = Unit Price / Gross Area (not the inverse).

These facts and the formulas remain visible in the unit header across tabs. Area
facts use the current approved measurement revision. Record an explicit zero for
each component that does not apply. Missing, duplicate or mixed-unit measurements
are not silently treated as zero. Net can be known even when outdoor components
are incomplete. Price per area is unavailable for unknown or zero Gross Area.

An unsold unit uses its active list price excluding tax. A commercially committed
unit uses its frozen agreed sale price excluding tax, in that price's currency,
divided by its current approved Gross Area. Rates use existing decimal money
rounding; the UI labels the actual area unit. This display does not change tax,
contract totals, receipts, weighted pricing calculations or historical sale terms.

## Register a buyer and mark sold

The primary buyer-first entry is now **Agent/Buyer > Register a buyer > Connect
unit**, above Sales in the menu. Country, Branch, Branch Leader and Agent are
recorded on the buyer and copied to the unit transaction. See
[SALES_AGENT_BUYER.md](SALES_AGENT_BUYER.md) for agent corrections and the
Master Administrator sale/reservation removal paths.

Master Administrators can choose **Owner: register buyer & mark sold** after
selecting an eligible unit in Sales > New Reservation. Select an existing buyer or register a new sole
purchaser, enter a reason, and optionally the sale date. Existing buyers retain
their named-party shares; those shares must total a whole unit.

One transaction registers the buyer, prepares/activates the existing reservation,
and creates/submits the sale. The owner action can waive a pending deposit gate
and override release/exception approval gates with the recorded reason. It never
fabricates a payment, receipt, signature or legal registration. The unit becomes
**Sold · SPA pending** and the legal state remains separate. Actual SPA signatures
and subsequent activation still use the existing legal workflow.

A current approved price is required for a new reservation. An existing reservation
can convert only for its own buyer and under its existing locked-price conditions.
Stale prices, invalid shares, another buyer's reservation, an existing sale or an
inactive unit are refused. Failure rolls back the buyer and all intermediate
changes. Project/unit locking prevents simultaneous buyers acquiring the unit.

The Sales preparation form accepts an agreed price and expected list version.
Its selected units obey ordinary release/current-price eligibility. Existing
privileged API release overrides remain permission- and reason-gated, but are
not offered through this ordinary selector. An existing reservation cannot be
silently assigned a different agreed price during owner conversion. Inventory's
Sales & legal tab provides inspection and existing transaction links.

## Inventory status

- **Available**: available for a new commitment.
- **Reserved**: a hold or an active reservation; holds retain the "on hold" label.
- **Sold**: committed sale awaiting SPA, or contracted. "SPA pending" is visible
  until the legal workflow advances.

Unreleased, cancelled and other operational states remain distinct. Inventory
counts and filters group Reserved and Sold consistently without replacing the
underlying legal or commercial lifecycle states.

## Deployment and rollback

The original owner-controls change required no dependencies, migrations,
backfills or environment changes. The subsequent Sales workspace requires
migration 0021; see COM_SALES_01_ACCEPTANCE.md for its guarded rollback.
Deploy backend and frontend together. Roll back code using the prior release;
database records use existing schema and remain valid. A code rollback cannot
restore intentionally deleted records; restore from a verified backup if needed.
After deployment, verify owner permissions, measurement formulas, a test buyer
registration, grouped stock filters and protected-deletion errors before use.
