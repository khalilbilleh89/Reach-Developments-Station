# Deletion coverage audit

Remaining remediation is tracked in [GitHub issue #303](https://github.com/khalilbilleh89/Reach-Developments-Station/issues/303).

Source audit of `main` at `2c0c735`, plus the Inventory fixes in this change.
This inventories named record creators and endpoints returning HTTP 201, their removal routes, and UI source locations. It is not browser verification or a claim of complete system-wide remediation.

79 creation/event handlers: 12 have removal coverage recorded, 62 remain gaps, and 5 create retained evidence.

Rows with existing cancellation, reversal or retirement remain gaps when unused/draft Delete is absent. Imports use the corresponding record deletion paths; nested row replacement and access revocation also remain subject to the standing policy.

| Record handler | Coverage | Behavior / remaining work |
| --- | --- | --- |
| `access.create_user` | missing | User deactivation exists; unused-account Delete is missing. Never erase audit actor identity. |
| `cashflow.create_forecast` | missing | Forecast discard / posted movement reversals exist; record-specific draft Delete coverage is missing. |
| `cashflow.record_development_movement` | missing | Forecast discard / posted movement reversals exist; record-specific draft Delete coverage is missing. |
| `cashflow.record_financing_movement` | missing | Forecast discard / posted movement reversals exist; record-specific draft Delete coverage is missing. |
| `cashflow.record_release` | missing | Forecast discard / posted movement reversals exist; record-specific draft Delete coverage is missing. |
| `cashflow.record_restriction` | missing | Forecast discard / posted movement reversals exist; record-specific draft Delete coverage is missing. |
| `collections.create_action` | missing | Posted receipts/refunds/allocations have reversal workflows; draft and action Delete coverage is missing. |
| `collections.create_allocation` | missing | Posted receipts/refunds/allocations have reversal workflows; draft and action Delete coverage is missing. |
| `collections.create_receipt` | missing | Posted receipts/refunds/allocations have reversal workflows; draft and action Delete coverage is missing. |
| `collections.create_refund` | missing | Posted receipts/refunds/allocations have reversal workflows; draft and action Delete coverage is missing. |
| `collections.create_restructure` | missing | Posted receipts/refunds/allocations have reversal workflows; draft and action Delete coverage is missing. |
| `collections.open_dispute` | missing | Posted receipts/refunds/allocations have reversal workflows; draft and action Delete coverage is missing. |
| `collections.submit_waiver` | missing | Posted receipts/refunds/allocations have reversal workflows; draft and action Delete coverage is missing. |
| `commissions.add_allocation` | implemented | Existing draft allocation removal; released grants use reversal. |
| `commissions.create_grant` | missing | Released grants reverse; unused grant Delete is missing. |
| `construction.add_dependency` | missing | Several records cancel, retire, reverse or void; unused and draft Delete coverage is incomplete. |
| `construction.create_budget` | missing | Several records cancel, retire, reverse or void; unused and draft Delete coverage is incomplete. |
| `construction.create_certificate` | missing | Several records cancel, retire, reverse or void; unused and draft Delete coverage is incomplete. |
| `construction.create_contract` | missing | Several records cancel, retire, reverse or void; unused and draft Delete coverage is incomplete. |
| `construction.create_cost_code` | missing | Several records cancel, retire, reverse or void; unused and draft Delete coverage is incomplete. |
| `construction.create_forecast` | missing | Several records cancel, retire, reverse or void; unused and draft Delete coverage is incomplete. |
| `construction.create_milestone` | missing | Several records cancel, retire, reverse or void; unused and draft Delete coverage is incomplete. |
| `construction.create_stage` | missing | Several records cancel, retire, reverse or void; unused and draft Delete coverage is incomplete. |
| `construction.create_variation` | missing | Several records cancel, retire, reverse or void; unused and draft Delete coverage is incomplete. |
| `construction.record_invoice` | missing | Several records cancel, retire, reverse or void; unused and draft Delete coverage is incomplete. |
| `construction.record_payment` | missing | Several records cancel, retire, reverse or void; unused and draft Delete coverage is incomplete. |
| `construction.record_unit_stage` | missing | Several records cancel, retire, reverse or void; unused and draft Delete coverage is incomplete. |
| `consultant_engineering.create_deliverable` | missing | Engagement termination exists; draft engagement and child Delete are missing. |
| `consultant_engineering.create_discipline` | missing | Engagement termination exists; draft engagement and child Delete are missing. |
| `consultant_engineering.create_engagement` | missing | Engagement termination exists; draft engagement and child Delete are missing. |
| `consultant_engineering.create_stage` | missing | Engagement termination exists; draft engagement and child Delete are missing. |
| `inventory.add_inventory_option` | implemented | Unused choice; project configurer; unit, asset, custom-field and pricing references protected. |
| `inventory.create_area_schedule` | implemented | Draft measurement only; approved revisions retained; administrator. |
| `inventory.create_area_type` | implemented | Unused area type; administrator; measurements and pricing protected. |
| `inventory.create_building` | implemented | Empty building; administrator; dependencies block deletion. |
| `inventory.create_field_definition` | missing | Retirement exists for features/documents/fields; visible Delete and complete removal coverage remain missing for this record. |
| `inventory.create_floor` | implemented | Empty floor; administrator; dependencies block deletion. |
| `inventory.create_phase` | implemented | Unused phase; administrator; child records block deletion. |
| `inventory.create_sub_asset` | implemented | Unlinked asset or an unpriced, unreleased unit; administrator. |
| `inventory.create_unit` | implemented | No sales commitment or retained references; administrator. |
| `inventory.create_unit_document` | missing | Retirement exists for features/documents/fields; visible Delete and complete removal coverage remain missing for this record. |
| `inventory.create_unit_feature` | missing | Retirement exists for features/documents/fields; visible Delete and complete removal coverage remain missing for this record. |
| `inventory.transition_unit` | retained | Immutable unit status event. Correct the unit through its permitted status transitions; retain the event trail. |
| `management_reporting.capture` | retained | Immutable reporting snapshot; deletion would erase issued evidence. Correct source data and capture a new snapshot. |
| `payment_plans.create_plan` | missing | Governed versions and triggered installments retain history; removable-draft Delete is missing. |
| `payment_plans.create_version` | missing | Governed versions and triggered installments retain history; removable-draft Delete is missing. |
| `payment_plans.submit_manual_trigger` | retained | Manual trigger event has approval/reversal; retain issued event evidence. |
| `prelaunch.record_expense` | implemented | Existing retained draft removal; confirmed expenses use reversal. |
| `pricing.activate_escalation` | retained | Escalation activation has an explicit reversal; retain pricing event evidence. |
| `pricing.create_area_rule` | missing | Configuration/rule/benchmark/price-version Delete is missing; approved price evidence must be retained. |
| `pricing.create_benchmark` | missing | Configuration/rule/benchmark/price-version Delete is missing; approved price evidence must be retained. |
| `pricing.create_configuration` | missing | Configuration/rule/benchmark/price-version Delete is missing; approved price evidence must be retained. |
| `pricing.create_escalation_rule` | missing | Configuration/rule/benchmark/price-version Delete is missing; approved price evidence must be retained. |
| `pricing.create_premium_rule` | missing | Configuration/rule/benchmark/price-version Delete is missing; approved price evidence must be retained. |
| `pricing.create_price_version` | missing | Configuration/rule/benchmark/price-version Delete is missing; approved price evidence must be retained. |
| `pricing.generate_price_versions` | missing | Bulk-created price versions need the same draft Delete as individually created versions; missing. |
| `projects.create_document` | missing | Delete is missing on current main. Permit retained deletion is in separate PR #300, not yet present in this audit base. |
| `projects.create_parcel` | missing | Delete is missing on current main. Permit retained deletion is in separate PR #300, not yet present in this audit base. |
| `projects.create_permit` | missing | Delete is missing on current main. Permit retained deletion is in separate PR #300, not yet present in this audit base. |
| `projects.create_permit_type` | missing | Delete is missing on current main. Permit retained deletion is in separate PR #300, not yet present in this audit base. |
| `projects.create_project` | missing | Delete is missing on current main. Permit retained deletion is in separate PR #300, not yet present in this audit base. |
| `projects.transition_permit` | retained | Immutable permit status history; correct the current status through a permitted transition. |
| `sales.create_adjustment` | missing | Review retention and source-record removal. |
| `sales.create_client` | implemented | Unused buyer only; administrator; contracts and payments protected. |
| `sales.create_handover` | missing | Review retention and source-record removal. |
| `sales.create_party` | missing | Review retention and source-record removal. |
| `sales.create_reservation` | missing | Review retention and source-record removal. |
| `sales.create_sale` | missing | Review retention and source-record removal. |
| `sales.record_legal_event` | missing | Review retention and source-record removal. |
| `sales.register_buyer` | missing | Single-save buyer registration also creates a contract. Buyer deletion alone does not remove this combined draft; contract removal coverage is missing. |
| `sales.start_cancellation` | missing | Review retention and source-record removal. |
| `settings.create_country_pack` | missing | Deactivation exists; unused configuration Delete is missing; code-based references require protection. |
| `settings.create_currency` | missing | Deactivation exists; unused configuration Delete is missing; code-based references require protection. |
| `settings.create_reference_value` | missing | Deactivation exists; unused configuration Delete is missing; code-based references require protection. |
| `settings.create_tax_rule` | missing | Deactivation exists; unused configuration Delete is missing; code-based references require protection. |
| `unit_economics.add_pool` | implemented | Existing editable-version pool removal. |
| `unit_economics.clone_version` | missing | Unit costs reverse; editable allocation-version Delete is missing. |
| `unit_economics.create_version` | missing | Unit costs reverse; editable allocation-version Delete is missing. |
| `unit_economics.record_unit_cost` | missing | Unit costs reverse; editable allocation-version Delete is missing. |
