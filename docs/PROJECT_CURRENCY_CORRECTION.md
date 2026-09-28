# Project base-currency correction

A base-currency correction fixes a denomination that was entered incorrectly. It does not perform foreign-exchange conversion: every monetary number remains exactly the same. The command is restricted to System Administrators, requires the caller to identify the base currency they observed, records a reason, and requires an explicit no-conversion acknowledgement.

The Projects domain owns the command, locks the project row, and commits one transaction. Each affected domain owns a narrow correction function for its own tables. Those functions flush into the caller's transaction and never commit independently. Any validation or write failure rolls back the project, every participating domain, and the audit event together.

## Reviewed currency fields

| Owner | Table and field | Meaning | Correction behavior |
| --- | --- | --- | --- |
| Cashflow | `cashflow_forecast_versions.currency_id` | Project-base forecast | Relabel |
| Cashflow | `cashflow_development_movements.currency_id` | Project-base cash movement | Relabel |
| Cashflow | `cashflow_financing_movements.currency_id` | Project-base cash movement | Relabel |
| Collections | `collection_receipts.currency_id` | Frozen from a sale | Relabel only when that sale descends from a corrected direct price |
| Collections | `collection_refunds.currency_id` | Frozen from a sale | Relabel only when that sale descends from a corrected direct price |
| Commissions | `commission_grants.currency_id` | Frozen from a sale | Relabel only when that sale descends from a corrected direct price |
| Construction | `construction_budget_versions.currency_id` | Project-base budget | Relabel |
| Construction | `construction_contracts.currency_id` | Project-base contract | Relabel |
| Construction | `construction_forecast_versions.currency_id` | Project-base forecast | Relabel |
| Construction | `construction_payments.currency_id` | Contract-inherited payment | Relabel |
| Marketing | `marketing_rental_scenarios.currency_id` | Explicit sourced rental assumption | Preserve |
| Payment Plans | `payment_plan_versions.currency_id` | Frozen from a sale | Relabel only when that sale descends from a corrected direct price |
| Pricing | `pricing_configurations.pricing_currency_id` | Explicit pricing policy | Preserve |
| Pricing | `market_benchmarks.currency_id` | Explicit external observation | Preserve |
| Pricing | `unit_price_versions.currency_id` | Direct project-base price or configured price | Relabel direct prices only; preserve configured prices |
| Projects | `projects.base_currency_id` | Governing project denomination | Replace with the corrected currency |
| Projects | `projects.reporting_currency_id` | Explicit or old-base-following reporting choice | Follow only when equal to the old base |
| Sales | `reservations.currency_id` | Frozen from the selected price | Relabel only for a corrected direct-price chain |
| Sales | `reservations.deposit_currency_id` | Frozen from the reservation | Relabel only for a corrected direct-price chain |
| Sales | `sale_contracts.currency_id` | Frozen from the reservation | Relabel only for a corrected direct-price chain |
| Sales | `sale_contract_tax_lines.currency_id` | Frozen from the sale | Relabel only for a corrected direct-price chain |
| Sales | `sale_legal_events.currency_id` | Explicit append-only legal fee evidence | Preserve |
| Unit Economics | `ue_current_cost_settings.currency_id` | Project-base live input | Relabel and advance the revision |
| Unit Economics | `unit_economics_allocation_versions.currency_id` | Project-base allocation | Relabel |
| Unit Economics | `unit_economics_unit_costs.currency_id` | Project-base unit cost | Relabel |

The executable `FIELD_POLICIES` inventory mirrors this table. Before any correction, the service compares it with SQLAlchemy metadata. A newly added project-scoped currency column therefore disables correction until its owner and semantics have been reviewed.

The project reporting currency follows the correction only when it still equals the mistaken base currency. A deliberately different reporting currency is preserved. Sales-owned quote snapshots are updated only inside corrected direct-price chains, and only currency identifier values change.

## Concurrency and audit

`expected_base_currency_id` provides optimistic conflict detection and `SELECT ... FOR UPDATE` serializes attempts on the same project. After one correction commits, another request based on the old value receives a conflict and changes nothing.

One `project_currency.corrected` audit event records the actor, reason, old and new identifiers, whether reporting currency followed, corrected row counts, the explicit fields that were preserved, and `amounts_unchanged: true`. No amount, rate, quantity, date, or reference is recalculated by this workflow.
