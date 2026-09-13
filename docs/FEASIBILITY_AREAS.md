# Overview Feasibility and Inventory Common Areas

Owner request, 12 September 2026: add Feasibility beside Fundamental, Financial and
Technical, and add the missing shared measurements under Inventory → Common Areas.
Governed by `docs/ENGINEERING_RULES.md` and `docs/DELETION_POLICY.md`.

## Source entry

Common Areas holds disjoint measured rows: common building area, garage, community,
and roads/pavements. Each row carries a name, area in m², and a drawing/schedule
reference. Common rows may be allocated to an active apartment in the same project.
Record each allocation instead of also recording the whole-project total. A category
with no rows is unknown; add an explicit zero row when the category does not apply.
Names are unique within the project to discourage duplicate source entry.

The full-page editor supports Add and Edit. Each row offers Delete with a reason.
Project managers and Design/Engineering, plus administrators, can maintain these
measurements. Whole-project membership is required. All changes take the project
lock, re-check scope, and retain before/after source values in audit. Deletion removes
the current measurement, retains its audit trail, and recalculates subsequent reads.
The restrictive apartment foreign key prevents deleting a unit still referenced by
an allocation; remove/reassign that measurement first. No financial or legal rows
are modified or cascaded.

## Calculation definitions

These are application area definitions, not local statutory GFA or permitted density.
Apartment population is all active units with property class `apartment`, including
sold and unreleased inventory. It is not the remaining stock count. The report does
not reconstruct historic measurements from the observation-period controls.

| Measurement | Formula |
| --- | --- |
| Apartment covered excluding balcony | Approved internal area |
| Apartment covered including balcony | Internal + balcony |
| Buildable | Apartment internal + project common |
| Apartment total | Covered including balcony + terrace + allocated common |
| Building | Covered areas of all active units + common + garage |
| Grand total | Building + all private outdoor components + community + roads/pavements |
| Private outdoors in grand total | Terrace + roof garden + front garden + porches |
| Project apartment averages | Relevant apartment total / active apartment count |

For an apartment-only project, average common area uses project common / apartment
count even before allocation. Average total uses (covered + terrace + project common)
/ apartment count. This reports a mean, without assigning it to individual units.
Bedroom/type totals require all positive common area to be allocated to active
apartments. No equal or pro-rata unit allocation is silently invented.

Building excludes open terraces, gardens and external community/road areas. Grand
total is a sum of disjoint measured components across levels, not the land footprint.
Parking/storage attachments are not added again to garage or apartment areas.
Apartment total intentionally differs from existing Inventory Gross; the latter sums
six private components and excludes common areas. Existing price-per-Gross and area
schedule approval rules are unchanged.

Mixed property projects retain apartment totals and all-unit building/grand totals;
apartment buildable efficiency is unavailable because project common area cannot be
assumed exclusively apartment common. Project-level shared totals are unavailable
under a phase/building filter; no project-wide total is silently copied into a subset.

Ratios disclose their numerator, denominator and formula: internal/buildable,
covered/buildable, covered/building, common/buildable, and balcony/covered.
Covered/buildable can exceed 100% because balconies are excluded from its denominator.
Ratios need complete measurements and a positive denominator. No threshold or
regulatory compliance judgement is inferred.

Measurements and arithmetic use Decimal. sqm/m2/m² and sqft/ft2/ft² are recognized;
1 ft² = 0.09290304 m². Unsupported units, duplicate components and missing approved
measurements produce an unavailable total with coverage, not a zero or partial sum.
Areas are displayed at four decimals; percentages at two, half-up, after aggregation.
Small displayed rounding differences between independently rounded group totals are
possible; computations use full-precision input conversions.

## API and migration

- GET/POST `/api/v1/projects/{project_id}/inventory/common-areas`
- PUT/DELETE `/api/v1/projects/{project_id}/inventory/common-areas/{area_id}`
- GET `/api/v1/projects/{project_id}/analysis/feasibility`

Feasibility shares Technical Analysis roles and existing whole-project authorization.
It is GET-only; no stored report, audit writes or new infrastructure. Source reads
are project scoped and use bulk unit/schedule reads.

Migration `0026_common_areas` adds only `inventory_common_areas`, with numeric, category,
allocation and project/unit constraints. No source backfill. Downgrade refuses a
populated table: export its measurements and remove them through the audited API
before downgrade, or roll forward. Audit survives downgrade. This revision follows `0025_prelaunch_master` on the current migration chain.

## Verification

`tests/modules/test_feasibility.py` covers known totals, averages, bedroom grouping,
zero/missing/duplicate measurements, conversion, mixed classes, source CRUD, role
denials, phase/project isolation, linked unit protection, read-only audit behavior,
and migration roundtrip/populated refusal. Full CI and independent review remain
required before main promotion. This feature does not alter Render configuration.
