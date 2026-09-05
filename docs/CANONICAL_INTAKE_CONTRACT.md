# The canonical intake contract

What a legacy batch is allowed to put into Reach, and what it is never allowed
to put in. This document is the target side of the cutover and nothing else: it
is derived entirely from the schema in this repository, and it names no source
column, worksheet, status vocabulary or currency, because the source workbook
has not been seen. When the source arrives, a second document maps it onto this
one. The two are deliberately separate — a mapping written before the contract
tends to become the contract.

The disposition table below covers **every one of the 91 tables** in the schema.
`tests/modules/test_cutover_intake_contract.py` fails if it does not: a new
table that nobody has classified is a table somebody may quietly start
importing.

## The one rule

> **Reach derives what Reach derives.** A value the application computes is
> never imported, even when the source has a column for it, and especially when
> the two disagree.

Outstanding balance, gross profit, closing cash position, construction spend to
date, unit-level cost allocation, current schedule snapshots — every one of
these exists in the legacy system as a number somebody typed or a formula
somebody wrote, and every one of them exists in Reach as a consequence of
inputs. Importing the number instead of the inputs produces a system that agrees
with the old spreadsheet on day one and drifts from it on day two, with no way
to tell which of the two is wrong.

The corollary is the one that costs work: if a derived figure comes out
different after the cutover, that is a **finding about the inputs**, not a
defect in the migration. Reconciliation exists to surface exactly that
difference. A migration that reproduces the old totals by importing the old
totals has reconciled nothing.

## Governance actors: the cutover operator, never a reconstructed one

A great many rows in this schema structurally require somebody to have done
something. `projects.created_by_user_id` is `NOT NULL`. An approved area
schedule must satisfy
`ck_unit_area_schedules_approved_complete` — an approver, an approval time and a
reconciled flag, or the row is refused. A confirmed receipt must satisfy
`ck_collection_receipts_confirmed_has_actor`.

There is exactly one honest way to fill those columns, and one dishonest way.

**Honest.** The named cutover operator — a real Reach user, created by an
administrator before the batch runs, who signs the manifest — is recorded as the
actor. They are not pretending to be a historical approver. They are asserting,
now, in their own name: *this row, as it stood in the legacy system, is fit to
be operated on in Reach.* That is a real decision by a real person who can be
asked about it later, and the batch's `audit_events` rows record it as a cutover
action carrying the batch correlation id, so nothing about it looks native.

**Dishonest, and prohibited.** Reconstructing a historical actor from the
source — creating a user account for a former sales manager so that a 2019
approval has a plausible name against it, or backdating `approved_at` to the
date in the workbook. That manufactures an audit trail. If the question "who
approved this price?" matters, the answer is "nobody in Reach did; it arrived
from the legacy system on the cutover date, approved by whoever the source
records", and that answer belongs in a provenance field, not in a fabricated
user row.

This is the same principle the B+ legacy commercial provenance decision applies
to sale contracts, generalised: **every row has exactly one honest provenance,
and a row that cannot state one does not land.**

## Prerequisites the batch may not create for itself

These exist before any batch runs, are created through the application by an
administrator, and are refused if a bundle tries to supply them.

| Prerequisite | Why the batch may not create it |
|---|---|
| The cutover operator's user account | A batch that creates its own actor authorises itself. |
| Any other user the bundle references | Never fabricate a user. See above. |
| `country_packs`, `country_approval_thresholds` | Jurisdiction configuration is a decision, not data. |
| `currencies` | A currency invented by an import is a currency nobody chose. |
| `reference_values` | The controlled vocabularies (`*_code` columns) are configuration. |
| `tax_rules` | Tax treatment is configuration in force at a date, not a per-row value. |
| `roles`, `user_roles` | Authorisation is never a side effect of a data load. |

`preflight` proves these are present and refuses the batch when they are not.
That is target-side preflight, and it is why preflight has a target half at all.

## Disposition of all 91 tables

### Platform — administered before any batch; never in a bundle

<!-- disposition:PLATFORM -->

| Table | Why |
|---|---|
| `roles` | Authorisation configuration. |
| `user_roles` | Authorisation configuration. |
| `user_sessions` | Runtime state; meaningless outside a live session. |
| `users` | Never fabricated. Administrators create them. |
| `user_project_access` | An access grant is a decision, not migrated data. |
| `user_phase_access` | As above. |
| `country_packs` | Jurisdiction configuration. |
| `country_approval_thresholds` | Jurisdiction configuration. |
| `currencies` | Configuration; a batch declares which it expects, never defines them. |
| `reference_values` | The controlled vocabularies behind every `*_code` column. |
| `tax_rules` | Configuration in force at a date. |
| `audit_events` | Reach writes it. The cutover writes its own batch rows here and reads nothing from the source. |

<!-- /disposition -->

### Derived — Reach produces it from governed input; importing it is fabrication

<!-- disposition:DERIVED -->

| Table | Why |
|---|---|
| `unit_status_events` | The log of transitions Reach performed. A legacy history has no Reach transitions. |
| `permit_status_events` | As above. |
| `reservation_status_events` | As above. |
| `sale_legal_events` | As above. |
| `installment_trigger_events` | Written when Reach fires a trigger. |
| `pricing_escalation_activations` | Written when Reach activates an escalation. |
| `unit_price_versions` | The governed price derivation. A legacy price was not derived here. |
| `unit_price_components` | The decomposition of a price version Reach computed. |
| `cashflow_forecast_versions` | A forecast is prepared and approved in Reach. |
| `cashflow_forecast_lines` | As above. |
| `cashflow_customer_schedule_snapshots` | A snapshot of what Reach computed. |
| `cashflow_development_movements` | Computed from receipts, invoices and payments. |
| `cashflow_financing_movements` | Computed. |
| `construction_budget_versions` | Prepared and approved in Reach. |
| `construction_budget_lines` | As above. |
| `construction_forecast_versions` | Computed from budget, certificates and variations. |
| `construction_forecast_lines` | As above. |
| `unit_economics_allocation_versions` | Reach allocates. |
| `unit_economics_allocations` | Reach allocates. |
| `unit_economics_unit_costs` | The result of an allocation run. |
| `collection_receipt_allocations` | **The allocation is Reach's.** Receipts are imported; which installment each pays is decided by the rules that will govern going forward. |
| `construction_payment_allocations` | As above, for construction payments. |
| `custom_field_definitions` | Configuration; the shape of the extension, not data in it. |
| `custom_field_options` | Configuration. |
| `land_parcel_custom_field_values` | Values for definitions that are configuration; out of scope until a definition exists to hold them. |
| `project_custom_field_values` | As above. |
| `unit_custom_field_values` | As above. |

<!-- /disposition -->

### Bundle — the canonical intake files

<!-- disposition:BUNDLE -->

| Table | Group | Why |
|---|---|---|
| `projects` | A | The root. Everything is scoped to a project. |
| `phases` | A | Physical hierarchy. |
| `buildings` | A | Physical hierarchy. |
| `floors` | A | Physical hierarchy. |
| `area_types` | A | The measurement vocabulary a schedule's values are expressed in. |
| `units` | A | The thing sold. |
| `unit_area_schedules` | A | The measured areas pricing is derived from. |
| `unit_area_values` | A | One area per type per schedule. |
| `clients` | B | The counterparty record. |
| `client_parties` | B | Who signs, and for what share. |
| `sale_contracts` | C | The commercial history. **BLOCKED** — see below. |
| `sale_contract_parties` | C | The parties frozen onto a contract. **BLOCKED**. |
| `payment_plans` | D | The signed schedule's container. **BLOCKED**. |
| `payment_plan_versions` | D | The signed schedule. **BLOCKED**. |
| `payment_plan_installments` | D | The signed schedule's lines. **BLOCKED**. |
| `collection_receipts` | C | Cash actually received. **BLOCKED**. |

<!-- /disposition -->

### Excluded — could carry source truth; deliberately not in the bundle

<!-- disposition:EXCLUDED -->

| Table | Why not |
|---|---|
| `land_parcels` | Land acquisition is history the operating system does not need to run. Add it when somebody names a report that requires it. |
| `planning_controls` | As above. |
| `permits` | Live permits are re-entered through the application, where the status machine applies. A migrated permit with no event history is a permit whose SLA clock never started. |
| `document_references` | Pointers to files the migration does not move. |
| `inventory_sub_assets` | Parking and storage. In scope only if the source ties them to sold units; unknown until the source is seen. |
| `pricing_configurations` | Pricing is configured in Reach, then derived. Importing a configuration would imply the legacy prices came out of it. |
| `pricing_area_rules` | As above. |
| `pricing_premium_rules` | As above. |
| `pricing_escalation_rules` | As above. |
| `market_benchmarks` | Reference data for pricing decisions not yet taken. |
| `reservations` | A legacy sale has no Reach reservation. This is the centre of the B+ decision, not an import. |
| `reservation_adjustments` | Adjustments to a reservation that does not exist. |
| `sale_cancellations` | A cancelled legacy sale is closed history; it changes no current obligation. |
| `sale_contract_tax_lines` | The tax decomposition of a frozen total. Part of the frozen-money problem, not separable from it. |
| `sales_project_policies` | Policy is configuration. |
| `handover_records` | Handover is a forward process. A unit already handed over carries that in `units.delivery_status`. |
| `handover_clearances` | As above. |
| `collection_actions` | Dunning history. Operationally spent. |
| `collection_disputes` | Import only if a dispute is open at cutover; unknown until the source is seen. |
| `collection_waivers` | A waiver is an approval. Never fabricated. |
| `collection_refunds` | Closed cash history. |
| `collection_restructures` | A restructure is an approved plan change; it lands as the resulting plan, not as the event. |
| `cashflow_receipt_restrictions` | An escrow restriction is a governed decision taken in Reach. |
| `cashflow_restriction_releases` | As above. |
| `construction_cost_codes` | Cost-code structure is configuration set up before the batch. |
| `construction_contracts` | Live construction contracts are re-entered where the certification chain applies. |
| `construction_contract_lines` | As above. |
| `construction_variations` | A variation is an approval. |
| `construction_variation_lines` | As above. |
| `construction_certificates` | A certificate is a formal certification event. |
| `construction_certificate_lines` | As above. |
| `construction_invoices` | Follows the certificate chain. |
| `construction_payments` | Follows the invoice chain. |
| `construction_milestones` | Milestones drive payment-plan triggers; a migrated milestone with no dependency graph fires nothing correctly. |
| `construction_milestone_dependencies` | As above. |
| `unit_economics_cost_pools` | Pool definitions are configuration. |

<!-- /disposition -->

## The unblocked bundle, in import order

Groups A and B can be specified and built now, because nothing in them depends
on the source workbook for its *shape* — only for its contents. Each file is
CSV, UTF-8, with a header row, listed in the manifest and hashed at validation.

Import order is a total order, not a suggestion: every file's references must
already exist when it is read, so a failure at step *n* leaves nothing from
steps 1..*n*-1 behind. The whole batch is one transaction.

```text
1  projects.csv
2  area_types.csv          -> projects
3  phases.csv              -> projects
4  buildings.csv           -> phases
5  floors.csv              -> buildings
6  units.csv               -> floors
7  unit_area_schedules.csv -> units
8  unit_area_values.csv    -> unit_area_schedules, area_types
9  clients.csv             -> projects
10 client_parties.csv      -> clients
```

### Conventions that apply to every file

| Concern | Rule |
|---|---|
| Encoding | UTF-8, no BOM. A BOM in the first header cell is a reject, not a silent strip. |
| Decimals | Written as plain digit strings, parsed as `Decimal`, never through `float`. A value with more decimal places than the target column refuses; it is not rounded. |
| Dates | ISO `YYYY-MM-DD`. No locale-dependent order, ever. |
| Timestamps | ISO 8601 with an explicit offset. A naive timestamp is a different claim depending on who reads it. |
| Currency | Named by ISO code and resolved against `currencies`. A code not configured is a reject. |
| Booleans | `true` / `false`, lower case. Not `Y`, `1`, `yes`. |
| Empty | An empty cell means absent. A cell containing whitespace is a reject, because it is indistinguishable from a typo. |
| Natural keys | Every file is keyed by the business identifiers below, never by a UUID. UUIDs are Reach's, generated on import. |
| Duplicates | A natural key appearing twice in one file refuses the file. |
| Unknown columns | Refuse. A column nobody mapped is a column somebody expected to be read. |

### 1. `projects.csv`

**Purpose.** The root scope. One row per project being migrated.

**Natural key.** `code` — unique across the system, upper case
(`ck_projects_code_upper`).

| Field | Required | Notes |
|---|---|---|
| `code` | yes | Upper case, non-blank, unique. |
| `name` | yes | Non-blank. |
| `developer_entity` | yes | |
| `country_pack_code` | yes | Resolved against `country_packs`. Reject if absent. |
| `base_currency_code` | yes | Resolved against `currencies`. |
| `reporting_currency_code` | yes | Resolved against `currencies`. |
| `fiscal_year_start_month` | yes | 1–12. |
| `status` | yes | One of `setup`, `predevelopment`, `active`, `on_hold`, `completed`, `cancelled`. |
| `city`, `location`, `project_type_code` | no | |
| `latitude`, `longitude` | no | Both or neither. Ranges enforced by the schema. |
| `planned_start`, `planned_completion` | no | Completion may not precede start. |

`created_by_user_id` is the cutover operator. `project_manager_user_id` is left
null unless the bundle names a user who already exists.

**Privacy.** Public-internal. No personal data.

### 2. `area_types.csv`

**Purpose.** The measurement vocabulary. A schedule's values mean nothing
without it, which is why it is imported before units.

**Natural key.** `project_code` + `code`.

| Field | Required | Notes |
|---|---|---|
| `project_code` | yes | |
| `code` | yes | Upper case. |
| `label` | yes | |
| `area_role` | yes | `internal`, `outdoor`, `ancillary`, `plot`, `gross`, `other`. |
| `unit_of_measure` | yes | |
| `weight_factor` | yes | 0–1 inclusive. |
| `required_for_release` | no | Defaults false. |
| `sort_order` | no | |

**At most one active `internal` type per project** — `uq_area_types_one_internal`
is a partial unique index and will refuse the second one at the database. The
importer checks it first so the reject names the file and row rather than
surfacing an integrity error.

**Privacy.** Public-internal.

### 3–5. `phases.csv`, `buildings.csv`, `floors.csv`

**Purpose.** The physical hierarchy. Every unit hangs off a floor.

**Natural keys.** `project_code` + `code`; then `project_code` + `phase_code` +
`code`; then `project_code` + `phase_code` + `building_code` + `code`.

Each carries `name`/`label`, a `sequence`, and the descriptive columns the
schema allows. `phases` additionally carries `status`
(`planning`/`active`/`on_hold`/`completed`/`cancelled`) and planned dates.

All three codes are upper case and non-blank. Note the composite foreign keys:
`buildings.project_id` references `phases.project_id`, so a building cannot be
attached to a phase in another project even by a malformed import.

**Privacy.** Public-internal.

### 6. `units.csv`

**Purpose.** The thing that is sold. The largest file in a typical batch and the
one whose statuses are the most consequential.

**Natural key.** `project_code` + `unit_reference`
(`uq_units_project_id_unit_reference`). `unit_number` is unique only within a
floor, so it is not the key.

| Field | Required | Notes |
|---|---|---|
| `project_code`, `phase_code`, `building_code`, `floor_code` | yes | Locates the unit. |
| `unit_reference` | yes | The natural key. |
| `unit_number` | yes | Unique within the floor. |
| `asset_class` | yes | `apartment`, `villa`, `townhouse`, `commercial`, `other`. |
| `commercial_status` | yes | **Mapping BLOCKED.** See below. |
| `legal_status` | yes | **Mapping BLOCKED.** |
| `collection_status` | yes | **Mapping BLOCKED.** |
| `delivery_status` | yes | **Mapping BLOCKED.** |
| `bedrooms`, `bathrooms`, `unit_type_code`, view/orientation/floor-band codes | no | All `*_code` values resolve against `reference_values`. |
| `has_maid_room`, `is_duplex`, `is_penthouse`, `is_corner`, `pool_access` | no | Default false. |
| `release_date`, `release_batch`, `block_reason` | no | |

**Four independent status dimensions, and the mapping is blocked.** Reach models
commercial, legal, collection and delivery status separately, each with its own
vocabulary (nine, twelve, seven and six values respectively — see the `CHECK`
constraints on `units`). A legacy system that carries one "status" column
collapses all four. Which of the four a source value speaks to, and what the
other three then are, is a question about the source. **No default is
acceptable**: defaulting `legal_status` to `no_spa` for a unit that is in fact
registered would be a false statement about a legal position.

`drawings_approved`, `legal_sale_eligible` and `pricing_approved` are gates
Reach uses to decide whether a unit may be sold. They are **not** imported as
`true` on the strength of the unit having been sold in the legacy system; that
is the derived-value rule. They are set by the same process that will govern
future sales.

**Privacy.** Public-internal.

### 7–8. `unit_area_schedules.csv`, `unit_area_values.csv`

**Purpose.** The measured areas. Pricing derives from the approved schedule, so
this is the first file where the governance-actor rule bites.

**Natural key.** `project_code` + `unit_reference` + `revision_code`; then that
plus `area_type_code`.

| Field | Required | Notes |
|---|---|---|
| `project_code`, `unit_reference` | yes | |
| `revision_code` | yes | Unique per unit. |
| `status` | yes | `draft`, `approved` or `superseded`. |
| `measurement_standard`, `plan_revision`, `source`, `measured_date` | no | |
| `notes` | no | |

An **`approved` schedule requires an approver, an approval timestamp and
`reconciled`** — `ck_unit_area_schedules_approved_complete`. The importer sets
all three from the cutover operator and the batch's own timestamp, and records
the approval as a cutover action in `audit_events`. It does not read an
approver's name from the source and it does not backdate the approval.

At most one `approved` schedule per unit (`uq_unit_area_schedules_current`).

`unit_area_values.csv` carries `raw_area` per `area_type_code`, non-negative,
one row per type per schedule.

**Privacy.** Public-internal.

### 9. `clients.csv`

**Purpose.** The counterparty. **The highest privacy class in the bundle.**

**Natural key.** `project_code` + `client_number`.

| Field | Required | Notes |
|---|---|---|
| `project_code`, `client_number` | yes | |
| `display_name` | yes | Personal data. |
| `email`, `phone`, `address` | no | Personal data. |
| `kyc_status` | yes | `not_started`, `in_progress`, `cleared`, `rejected`. |
| `privacy_consent_at`, `privacy_consent_reference` | no | |
| `preferred_language_code` | no | |

**`kyc_status` may not be imported as `cleared`** on the strength of the legacy
system saying so, unless the source carries the evidence reference that clearing
it in Reach would require. A KYC status is a compliance assertion; inheriting it
without its evidence is the same failure as inheriting an approval without its
approver. Until the source is inspected this is **BLOCKED**, and the safe
default — `not_started`, with re-clearance as an operational task — is the one
the runbook should assume it will need.

**Privacy.** Personal data. Never logged. Reject records for this file carry the
row number and `client_number` and nothing else — no name, no email, no phone.

### 10. `client_parties.csv`

**Purpose.** Who actually signs, and for what share. Carries identity documents.

**Natural key.** `project_code` + `client_number` + `share_sequence`.

| Field | Required | Notes |
|---|---|---|
| `project_code`, `client_number` | yes | |
| `party_role` | yes | `purchaser` or `joint_purchaser`. |
| `name_as_identification` | yes | Personal data. |
| `share_fraction` | yes | > 0 and ≤ 1. **Shares for one client must sum to exactly 1**, checked as `Decimal`. |
| `is_primary` | yes | Exactly one per client. |
| `nationality_code`, `residency_code` | no | |
| `tax_id`, `identity_document_type`, `identity_document_number` | no | **Special-category identifiers.** |
| `representative_name`, `poa_reference` | no | Personal data. |

**Privacy.** The most sensitive file in the bundle. Identity document numbers
and tax identifiers never appear in a log line, a reject report, an evidence
artifact or an exception message. A reject here names the row and the client
number.

## What is blocked, and on what

Nothing below is a design gap. Each is a question whose answer is in a document
nobody has produced, and inventing an answer is what this contract exists to
prevent.

| Blocked | Blocked on | Why guessing is not available |
|---|---|---|
| Groups C and D entirely (`sale_contracts`, `sale_contract_parties`, `payment_plans`, `payment_plan_versions`, `payment_plan_installments`, `collection_receipts`) | The B+ legacy commercial provenance seam, and the source | A sale contract requires `reservation_id`, `unit_price_version_id` and `reservation_quote_snapshot_json`, all `NOT NULL`. A legacy sale has none of the three. Until the seam exists, the only way to land one is to fabricate a reservation and a price version, which manufactures a pricing derivation that never happened. |
| The ten frozen money columns on `sale_contracts` | The source | `reference_price_ex_tax` through `total_contract_price` are all `NOT NULL`. A legacy contract has a total; whether the source can decompose it into discount, seller credit, seller cost, tax and buyer fees is unknown. **Unknown decomposition is not zero.** Writing zeros would state that no discount was given. |
| The four `units` status mappings | The source | Four independent dimensions, thirty-four vocabulary values between them. No default is safe. |
| `clients.kyc_status` | The source | A compliance assertion needs its evidence. |
| Whether receipt allocations are imported or re-derived | The source | If the client's ledger records which installment each receipt paid, that is a commercial fact. If Reach re-allocates under its own rules, the result may differ — and which one is authoritative after cutover is a decision, not a default. Currently classified derived; revisit when the source is seen. |
| Opening cash position | The source | Derived from receipts and restrictions. If it does not reconcile, that is the finding. |
| Every reconciliation's expected value | The source | All seven, individually. |

## Where the data lives, and what may be committed

Everything a cutover reads or writes locally lives under **`migration-work/`**,
at the repository root, and that directory is ignored. The source extract, the
canonical bundle built from it, the manifest, the reject reports, the evidence
artifacts — all of it is the client's live commercial data, and none of it
belongs in a repository, on any branch, ever. There is no branch on which a
buyer's identity document number is acceptable.

`.xlsx`, `.xls` and `.xlsm` are ignored repository-wide as well, because a
workbook dropped in the root and swept up by `git add -A` is the realistic
accident and no spreadsheet is a legitimate fixture here.

**`*.csv` is deliberately not ignored**, and the reason is worth stating so
nobody adds it later as an apparent tightening. The canonical bundle is CSV, and
the synthetic fixture — obviously fictional people, obviously fictional
projects — is committed as CSV so the importer has something to be tested
against. Ignoring the extension would silently exclude the one form of this data
that is supposed to be present, and the exclusion would be discovered by its
absence, which is the worst way to discover anything.

What may be committed: templates, schemas, this document, mapping documentation,
synthetic fixtures containing obviously fake people and projects, and code. What
may not: buyer names, emails, phone numbers, passport or identity numbers, SPA
files, bank references, receipt data, real financial values, source workbooks,
and cutover exports.

## Reject behaviour

A batch is all or nothing. A reject does not skip a row; it fails the batch,
because a partially applied migration is the state nobody can reason about.

`validate` reports every reject it can find in one pass rather than stopping at
the first, so an operator fixes a hundred problems in one sitting instead of a
hundred sittings. `apply` re-verifies the manifest hashes and refuses if a byte
has moved since validation — an operator who fixes rejects in the source and
then applies without re-validating is the failure the hash chain exists for.

A reject record carries `source_file`, `row`, a safe business `reference`,
`field`, `code`, `reason` and `severity`. **It carries no value from the
source**, because there is no field in this contract about which one can say in
advance that its contents are safe to put in a file that gets mailed around.
Fixing a reject means opening the source, where the value already is.

## What this contract does not cover

The mapping from the client's workbook onto these files. That document does not
exist and cannot be written until the workbook is seen. When it is written, it
belongs beside this one, and this one does not change to accommodate it: if the
source cannot supply something this contract requires, that is a finding about
the migration, not a reason to relax the contract.
