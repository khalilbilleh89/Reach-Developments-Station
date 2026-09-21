# Agent registry and buyer attribution

Agents are project-owned Sales records, independent of buyers, units and sales.
The Agent/Buyer area has an Agent roster and buyer register. Create an Agent
with a name and optional Country, Branch and Branch Leader; duplicate names are
permitted and UUIDs distinguish them. The roster supports editing and active
status. It does not grant an application login, change the buyer's advisor, or
compute commissions.

Buyer registration and editing offer an optional Agent dropdown. The selected
UUID must belong to the same project and be active; **No agent** is valid. The
current Agent's details are copied when a reservation is created, and that
snapshot and ID are copied into the sale. Later edits to the Agent or buyer do
not rewrite earlier transactions. A sale-specific correction selects an active
Agent (or No agent), requires a reason, and updates only that sale's snapshot.
It does not modify the buyer, reservation, or another sale.

Historic `agent_*` strings remain readable. Migration `0036_sales_agents` adds
the roster and nullable project-scoped `agent_id` on clients, reservations and
sale contracts, with no inferred ID or name-based backfill. A legacy buyer with
no Agent ID can still pass its existing text into a new reservation; deliberately
choosing No agent clears the buyer's legacy default, not past snapshots.
Inactive Agents remain readable in existing assignments but cannot be newly
selected for a buyer, reservation, or correction. If a buyer's current Agent is
deactivated, choose an active replacement or No agent before starting a new
reservation.

An unused Agent can be deleted with a reason; the deletion is audited. Once
assigned to any buyer or sale, the Agent cannot be hard-deleted even after the
live link is cleared: deactivate it instead. Database project-scoped foreign
keys protect current references and assignment audit events preserve historical
use. The migration downgrade refuses to discard populated roster data.

The previous buyer-first sales and owner-removal flow remains unchanged:
connecting a buyer to a unit creates a reservation/sale, and signed or
collection-active contracts must use governed cancellation rather than Delete.
See [DELETION_POLICY.md](DELETION_POLICY.md) and
[RECORD_CORRECTION_CATALOGUE.md](RECORD_CORRECTION_CATALOGUE.md).
