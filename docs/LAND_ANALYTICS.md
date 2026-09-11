# Land acquisition and analytics

Development → Land → select a parcel. Acquisition inputs are editable in the parcel form; **Analytics** follows Documents.

## Acquisition inputs

All amounts use the project's base currency. Purchase Price is the percentage base:

- Taxes = Purchase Price × entered tax percentage.
- Agent, Legal and Registration are entered amounts; each displayed percentage = amount ÷ Purchase Price × 100.
- Other / previously recorded fees retains the existing `acquisition_fees` value. Do not repeat an itemized fee here. When splitting a legacy lump sum, reduce this field explicitly to avoid counting the same fee twice.
- Total Acquisition Cost = Purchase Price + Taxes + Other Fees + Agent + Legal + Registration.

New itemized fields default to zero to preserve existing recorded totals. Clearing a field means unknown, not zero; an incomplete acquisition cost is labelled accordingly. No jurisdictional tax rate is supplied or inferred.

## Analytics

- Purchase cost per sqm = Purchase Price ÷ Land Area.
- Purchase cost per buildable sqm = Purchase Price ÷ recorded Maximum GFA (Planning).
- All-in counterparts use Total Acquisition Cost as numerator.
- Land cost as % of GDV = cost ÷ Expected GDV × 100, showing both purchase and all-in bases.

Expected GDV is an optional, user-entered estimate **for this parcel**, not an inferred whole-development total. Areas recorded in sqft are converted to sqm using 0.09290304. Missing/zero denominators produce unavailable results, never a fabricated zero. Maximum GFA is assumed to use the parcel's area unit, as in the existing planning record.

Annual entries contain a year and a signed market-change percentage. The earliest entered year starts from Purchase Price. Each later entered year compounds the previous calculated value, rounded to currency cents at each step. Missing years are not extrapolated. Editing an earlier percentage recalculates later estimates; the audit records each write. For example, 1,000,000 with +10% then −5% gives 1,100,000 then 1,045,000. Inputs support −100% to +1,000%; estimates outside the supported money range are unavailable. These are owner-entered assumptions, not observed market values or valuations. Acquisition fees do not appreciate, and market estimates never feed acquisition-cost allocation.

Financial visibility and write permissions follow the existing project roles and project access. Financial fields are redacted for restricted readers. Recorded itemized acquisition costs are included in the existing unit-economics cost pool and management acquisition totals.

## Migration and rollback

Migration `0021_land_analytics` adds nullable/default-zero financial columns and one annual-assumptions table. Existing purchase prices and acquisition fees are unchanged. Existing custom fields are not migrated into these inputs; new custom definitions cannot use the native column names.

Deploy the migration before the application that reads these fields. Before rollback, back up the database and export new fee/GDV inputs and annual assumptions. Downgrading to `0020_management_reporting` drops these new columns and the annual table, but preserves original purchase prices and acquisition fees. Do not downgrade a live database merely to test rollback. The migration round-trip test runs only on the disposable test database.
