# PR-COM-SALES-01 implementation plan

Status: implemented draft; independent review and browser acceptance pending.
The owner explicitly authorized isolated draft implementation during main CI.
Post-merge main shard 4 reported two obsolete Phase expectations from #289;
these are being corrected separately, ahead of Sales promotion.
Construction Contract #288 and owner controls #289 are merged.
Observed base: ccd8e772137f9fb3ffd97c932694a2b6b86a342c.
Branch: feature/sales-owned-transactions.
Main CI: https://github.com/khalilbilleh89/Reach-Developments-Station/actions/runs/34626373415

Governed by [Engineering Rules](ENGINEERING_RULES.md). The owner proposal is
PR-COM-SALES-01, Sales-Owned Unit Selection & Negotiated Price Variance.

## Product boundary

Inventory owns the Unit and governed reference/list price. Sales owns the buyer,
transaction and negotiated price. Sales selects an eligible Unit through its own
read surface, consuming Inventory/Pricing facts without duplicating them.
Operators complete Reservation, SPA and Payment Plan journeys within Sales.
The approved reference price and agreed price may differ; the backend derives
variance from frozen inputs. Sales never overwrites Inventory's list price.

## Integration with merged owner controls

PR #289 adds a Master-only buyer-registration operation and Inventory entry point.
Move the commercial UI entry point into Sales under this owner's explicit product
boundary. Preserve the operation's existing reservation-to-sale lifecycle,
recorded override reasons and Master authorization; no new direct Sale creation.
Include its ordinary and existing-reservation paths in price and concurrency
regressions. It must not silently reset an explicitly agreed reservation price.
Document any narrow request extension needed for the Sales preparation workspace.
The new ordinary unit selector does not offer privileged release overrides.
Owner inventory corrections, protected catalogue deletion and physical-area facts
remain outside this PR. Inventory's existing actual-price-per-area presentation
must not overwrite the governed list price or become Sales' historical reference.

## Findings at the base (addressed by this draft)

- SalesTab loads inventory.phases and uses a one-row-per-Unit register.
- UnitWorkspace imports ReservationForm and offers commercial creation.
- ProjectCommandCenter also consumes sales.register; changing that endpoint's
  meaning would affect its current counts. Give the Sales workspace a dedicated
  transaction endpoint and preserve the existing dashboard contract.
- transaction_history already supplies a SQL-scoped, paginated UNION of
  Reservations and SaleContracts. Reuse that query pattern without aggregating
  historical and active prices together.
- create_reservation permits multiple preparation records, locking project then
  Unit and refusing existing commitments. Activation additionally enforces active,
  available, release eligibility, quote validity, buyer shares and approval gates.
  The selector must share these unit-level guards; reservation-specific gates
  remain on the later activation operation.
- Pricing quote_preview always reads the active price. Existing ordinary
  recalculation can therefore change the reference. Price editing must explicitly
  distinguish the frozen reference from the explicit requote operation.
- SaleContract already stores reference_price_ex_tax, net_contract_price_ex_tax
  and reservation_quote_snapshot_json. No new historical reference lookup needed.
- ReservationAdjustment has type, treatment, shape and uniqueness constraints.
  Adding negotiated types requires updating both type and treatment checks.
- Local migration head currently 0020_management_reporting; verify against main
  again before naming the new revision. Migration integrity/CI ownership mapping
  and test HEAD_REVISION must be updated alongside the new migration.

## Implemented decisions

1. Dedicated Sales transactions endpoint: one row per SaleContract, plus each
   Reservation not already represented by its successor SaleContract. Distinct
   competing preparation records on a Unit stay distinct. Default current view
   includes preparation and live transactions; closed transactions are available
   through history. History retains both source and successor records.
2. Sales-owned unit-options endpoint: search and bounded pagination in SQL,
   phase-scoped access before reading rows, compact unit identity and governed
   price. Shared unit-level eligibility guard called again under write locks.
   Validate release/current pricing basis as well as absence of commitments.
3. Agreed price is an explicit intent, distinct from the derived quote result.
   Nullable Reservation.agreed_price_target_ex_tax persists intent even when the
   adjustment is zero. Historical records with no explicit intent keep their
   existing semantics; there is no historical intent backfill.
4. Fixed negotiated discount/premium records are server-managed, retained/zeroed
   with audit when direction changes. Generic adjustment POST and PUT must both
   reject access to these records. Do not relabel them as credits or upgrades.
5. Derive the negotiated delta from the quote without the previous negotiated
   adjustment; apply it after existing percentage calculation to avoid changing
   the percentage basis and missing the exact target. Re-run tax and existing
   approval thresholds, and assert net equals the explicit target exactly.
6. Any explicit target is preserved when other quote inputs are recalculated;
   show the individual inputs and resulting balancing adjustment honestly.
   Seller costs retain their existing meaning and do not change contract price.
7. Frozen reference price and currency drive ordinary price editing and reads.
   Only legitimate explicit requote advances the reference/version; preserve the
   target, recompute variance and withdraw obsolete exception approval.
8. Preview and creation carry expected price-version identity so a stale list
   selection is refused rather than silently replaced. Preview responses are
   discarded if their request no longer matches the selected unit/entered price.
9. Signed variance uses Decimal money rounding and six-decimal RATE rounding:
   amount = net - reference; fraction = amount / reference. A zero reference has
   no defined percentage, so return null with an explanation, never divide by
   zero or invent 0%. No browser financial arithmetic or FX.
10. A synchronous UI guard and optional project-scoped creation_request_id protect
    Reservation creation. The same actor/key/payload returns the existing record;
    changed payload or actor is refused. Project locking serializes the lookup
    and creation. Distinct keys still permit legitimate competing drafts.
    The UI never automatically replays a failed or uncertain write.

## Workspace and recovery

Full Sales preparation workspace: Unit search/select, commercial price and
authoritative preview, buyer find/create, reservation terms, Prepare Reservation.
Existing DraftBoundary and register URL context remain the primitives. Unit is
a secondary reference, not the row destination. Remove Inventory creation flow.
Reservation/Sale/history expose frozen reference, actual price and signed variance.
Keep tax, total contract value, Payment Plan and Collections facts separate.

Local read Retry must preserve the full draft. Price preview failure invalidates
the displayed preview without clearing price. A 403/409 refreshes eligibility but
does not replay save. A 422 retains fields and shows structured validation errors.
Return navigation and browser history must work at all five requested widths.

## Validation and delivery

Golden cases: 100000/100000, 100000/95000, 100000/105000, 150000/143000,
threshold-crossing 100000/80000, explicit at-list and below-list requotes,
historic price stability, competing activation, same-currency refusal,
generic-adjustment bypass rejection, stale approval withdrawal, exact conversion.

Run focused Sales/Pricing/Inventory concurrency and permissions, migration
forward/backward/drift, Unit Economics, Payment Plans and affected Collections
regressions. Run frontend behavior, route/draft safety, lint/build, Ruff,
compileall app scripts, dependency consistency and whitespace checks.

Browser acceptance: 1600, 1440, 1024, 768, 390; lower and higher price journeys,
failure retention, Back/Forward, keyboard labels/focus. CUA initialization still
fails before executing browser code with a missing kernel-assets path; browser
acceptance must remain explicitly pending until the tool recovers.

Deliver one Draft PR with exact SHA, changed files, migration and evidence.
Stop for independent review. Do not mark Ready or merge. Full backend shards and
Frontend on the accepted exact head remain required before human merge.
