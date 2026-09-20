# Current unit costs and profit

Construction → Unit cost analysis and Unit Economics → Current costs & profit
show the same live server calculation. No budget or allocation-version activation
is required. The approved historical allocation workflow remains available under
Approved basis & unit costs and is not rewritten by this report.

Finance records one project input set: the approved gross-built measurement type,
supplemental soft cost, additional shared cost, shared finance cost, commission
provision percentage, and profit-tax percentage. Blank is unknown; explicit zero
means none. Inputs are audited, revision-checked, and deletable with a reason.
Deleting inputs does not remove source records or historical financial evidence.

## Area and allocation

Choose a gross-role area type containing surveyed internal plus covered built
areas, excluding open gardens and plot area. Each active unit needs a positive
value on its approved schedule. A separate measurement used only for construction
should have a zero pricing weight to avoid counting it again in saleable pricing.
Sqft converts to sqm with the exact factor 0.09290304. Pricing weights never affect
this allocation. Shared costs use each unit's gross-built area divided by the
total gross-built area of all active units, including sold and unsold units.

If any active unit lacks a positive measurement, shared allocations are unavailable
for the entire project. The denominator never silently excludes that unit.
Each pool is allocated with Decimal arithmetic and a deterministic cent residual,
so unit amounts reconcile exactly. Group ratios divide group costs by group area.

## Cost sources and profit

- Hard and contracted soft costs: active, completed and terminated construction
  contracts, including approved variation additions and reductions. Draft and
  cancelled contracts and unapproved changes do not contribute. Completion or
  termination does not erase the standing commitment. New consultancy contracts
  auto-classify as soft; existing contract lines keep their recorded categories.
- Land: complete active-parcel purchase price plus acquisition charges. Missing
  parcel costs remain unknown; an incomplete sum is never labelled the total.
- Soft, additional and finance inputs: only amounts outside the source contracts,
  land register, and recorded unit costs. Nonrecoverable taxes, where applicable,
  belong in explicitly recorded additional costs; sales VAT is not profit tax.
- Unit costs: active actual direct costs attributable to the unit/current deal;
  actual selling costs belong to the current sale. Unsold forecasts are used only
  for cost types without applicable actuals. Reversed entries are excluded.
- Commissions: one current-sale draft/released grant total, otherwise recorded
  unit commissions, otherwise the project provision rate. Beneficiary
  distributions never add another copy. A grant overrides manual commission rows
  with an explicit report notice. Draft grants are labelled provisions.
- Seller costs: reconciled frozen commercial and finance costs from the sale,
  counted separately from its net contract price.
- Payments, invoices and certificates settle/evidence commitments; they do not
  add the contract value a second time.

Total unit cost = allocated hard + land + soft + additional + finance + recorded
unit costs + seller costs + commissions. Construction cost per sqm uses hard cost
only; total cost per sqm uses all those components.

Revenue is the current signed sale's net price excluding VAT, or the approved
asking price for an unsold unit. An asking price invalidated by inventory changes
requires reapproval before it can contribute revenue or profit. These bases are labelled; signed and forecast
revenue subtotals remain separate. Currency mismatches prevent comparable totals.

Pre-tax profit = revenue − total unit cost. Estimated profit tax = max(pre-tax
profit, 0) × the project's entered profit-tax rate. Net profit = pre-tax profit −
estimated tax. No rate is assumed; net profit stays unavailable until entered.
This is a management estimate, with no statutory adjustments or loss-offset
calculation. Building, floor and project tax/net figures sum unit results.

## Ownership and safety

`unit_economics/current_costs.py` owns the calculation and consumes named read
contracts from construction, land, inventory and commissions. The browser only
renders decimal strings. Economics readers with whole-project access may read;
only Finance may write/delete. Phase-selected readers cannot read the shared
project cost pool. Migration 0034 creates inputs only, with no financial backfill;
it refuses downgrade while input rows remain. Removal retains audited before-images.

The budget CI regression now asserts that a signed commitment beyond a historical
budget activates successfully and leaves the historical budget unchanged.
