# MVP 2 batch 1 — Unit Master and Commercial Unit 360

Implements V2-03 and V2-04 together under
[ENGINEERING_RULES.md](ENGINEERING_RULES.md). The remaining delivery sequence
is recorded in [V2_ROADMAP.md](V2_ROADMAP.md).

## Operator workflow

Open a unit from Inventory. Its header shows internal area, gross area,
attached parking/storage and the live selling price for authorized readers.
An active sale also shows its contract price before tax, for authorized sales
readers. The overview brings together release readiness, pricing, the commercial
commitment and collections. Economics stays in the project's finance workspace;
the unit drawer no longer requests cost or margin data.

The Physical record tab records the six area components, free-add descriptive
features, document references and attached assets. New measurements are draft
revisions of the existing area schedule; the approved measurement remains
visible until a reconciled replacement is approved. Existing pricing attributes
and measured revision history remain available in the unit record.

The Pricing tab accepts a total selling price before tax in the project base
currency and a reason. No pricing configuration is needed for this path.
Save a draft, submit it, obtain a different person's approval, and activate it.
The existing role restrictions, future-effective-date guard, basis comparison,
one-active-price constraint and history remain in force. The original author
of a direct price cannot approve it even if another person submitted it.
Configured calculation and bulk pricing remain available for existing projects.

## Confirmed measurement definition

Gross area is internal + balcony + roof garden + front garden + terrace +
porches. Parking and storage never contribute. Weight factors belong to
weighted saleable area and never change this physical total.

Each area type explicitly identifies its gross component. The database allows
one active type per component per project. Internal types are backfilled from
their existing role; outdoor components require an explicit mapping, because
their labels cannot safely be guessed. Once a mapped type has measurements,
its component cannot change. Existing unclassified measurements may be mapped
explicitly, with an audit event.

All six components must be measured in the same unit. Record zero when a
component does not apply. Missing, mixed-unit or duplicate components return
an unavailable gross total and an explanation, rather than an understated sum.
Gross completeness is separate from the existing configurable release gates.

Pricing returns the live price divided by the current approved gross area,
rounded with the existing Decimal money routine. The ratio is unavailable
for incomplete/zero gross area or a price requiring repricing. Its unit is
returned explicitly, so square feet are never labelled square metres.

## API and security

- Unit detail and register responses add `gross_area` and `gross_area_unit`;
  detail also explains unavailable totals and missing components.
- Area types and measured lines add `physical_component`.
- Unit-scoped `features` and `documents` support read, create and retire.
  Retirement preserves history. Document references accept HTTP(S) URLs;
  the application does not fetch the remote files or upload attachments.
- Existing price-version creation accepts `selling_price` plus a reason.
  Direct amounts cannot be mixed with rate overrides or paid-upgrade inputs.
  `pricing_configuration_id` is nullable for explicitly recorded direct prices.
- Unit pricing adds `direct_price_currency_id`, `price_per_gross_area` and
  `gross_area_unit`. Financial read permissions still apply before serialization.
- Direct-price reservations require explicit expiry and price-lock dates.
  Re-quote accepts an optional explicit `price_locked_until`; configured
  defaults continue to apply when it is omitted on configured prices.

Inventory annotations retain project and phase boundaries, acquire project
then unit locks, recheck scope after waiting, and emit audit events. They do
not grant drawing, legal or pricing approval. Document permissions at the
linked destination remain the destination's responsibility.

Direct prices are stored in the existing pricing version/component tables as
an entered amount, with their approved inventory basis and any applicable
market comparison. Existing quote calculations still own tax, concessions,
fees and approval thresholds. Neither inventory nor the browser calculates
financial amounts. No dependency is added.

## Migration and rollback

`0013_unit_master` adds area-component mappings and unit annotations. It
preserves existing measurements. Its downgrade removes the new mapping and
annotation data: export those records first if a rollback is planned.

`0014_direct_unit_price` allows configuration-free price versions with a
database check requiring an explicit direct-entry basis. Existing calculated
versions remain associated with their configuration. Downgrade refuses while
direct price history exists. Retain the schema or restore an appropriate
pre-upgrade backup; never delete financial history to make rollback succeed.

No production database, deployment configuration or environment variable is
changed by this PR.

## Reference and following batches

Khalil's supplied `Real_Estate_Development_Tracking_System_MVP.docx` informs
the six area fields, attached-asset exclusion, free-add features, direct selling
price and separation of economics. The owner explicitly confirmed both the
gross formula and separate approval for directly entered prices. The source
document itself is not committed.

Buyer entry and reserve/sell actions, SPA signing, registry prominence and
sold-price workflow are batch 2. Payment plans and the receipt journal are
batch 3; configured construction stages are batch 4. Batch 5 integrates
management reporting and complete workflow UAT. Current sales/collections
records remain readable from Unit 360 while those experiences are developed.
