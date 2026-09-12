# Record correction source catalogue

Base: 97e08d3af058b19e7197648891eb10fce109b40e (merged Land #292 and Sales #293).

Static inventory of mapped record classes and declared mutation routes. This includes generated history, configuration and child rows, not only user-created records. Route existence is not evidence of authorization or usable UI. See RECORD_CORRECTION_AUDIT.md for evaluated findings and the implementation plan.

Inventory: **106 mapped record classes; 279 mutation routes**. Paths are relative to each router prefix.
## access

- `User` → `users` ([model](../app/modules/access/models.py#L44)).
- `Role` → `roles` ([model](../app/modules/access/models.py#L86)).
- `UserRole` → `user_roles` ([model](../app/modules/access/models.py#L101)).
- `UserSession` → `user_sessions` ([model](../app/modules/access/models.py#L121)).
- **POST** `/login` — `login` ([route](../app/modules/access/api.py#L101)).
- **POST** `/logout` — `logout` ([route](../app/modules/access/api.py#L116)).
- **POST** `/change-password` — `change_password` ([route](../app/modules/access/api.py#L138)).
- **POST** `/users` — `create_user` ([route](../app/modules/access/api.py#L198)).
- **PATCH** `/users/{user_id}` — `update_user` ([route](../app/modules/access/api.py#L226)).
- **POST** `/users/{user_id}/reset-password` — `reset_password` ([route](../app/modules/access/api.py#L251)).

## audit

- `AuditEvent` → `audit_events` ([model](../app/modules/audit/models.py#L25)).

## cashflow

- `CashflowForecastVersion` → `cashflow_forecast_versions` ([model](../app/modules/cashflow/models.py#L237)).
- `CashflowForecastLine` → `cashflow_forecast_lines` ([model](../app/modules/cashflow/models.py#L382)).
- `CashflowCustomerScheduleSnapshot` → `cashflow_customer_schedule_snapshots` ([model](../app/modules/cashflow/models.py#L458)).
- `CashflowDevelopmentMovement` → `cashflow_development_movements` ([model](../app/modules/cashflow/models.py#L539)).
- `CashflowFinancingMovement` → `cashflow_financing_movements` ([model](../app/modules/cashflow/models.py#L639)).
- `CashflowReceiptRestriction` → `cashflow_receipt_restrictions` ([model](../app/modules/cashflow/models.py#L731)).
- `CashflowRestrictionRelease` → `cashflow_restriction_releases` ([model](../app/modules/cashflow/models.py#L817)).
- **POST** `/forecasts` — `create_forecast` ([route](../app/modules/cashflow/api.py#L222)).
- **PUT** `/forecasts/{version_id}/lines` — `set_forecast_line` ([route](../app/modules/cashflow/api.py#L262)).
- **POST** `/forecasts/{version_id}/refresh-customer-snapshot` — `refresh_customer_snapshot` ([route](../app/modules/cashflow/api.py#L294)).
- **POST** `/forecasts/{version_id}/submit` — `submit_forecast` ([route](../app/modules/cashflow/api.py#L309)).
- **POST** `/forecasts/{version_id}/approve` — `approve_forecast` ([route](../app/modules/cashflow/api.py#L323)).
- **POST** `/forecasts/{version_id}/reject` — `reject_forecast` ([route](../app/modules/cashflow/api.py#L340)).
- **POST** `/forecasts/{version_id}/discard` — `discard_forecast` ([route](../app/modules/cashflow/api.py#L364)).
- **POST** `/forecasts/{version_id}/activate` — `activate_forecast` ([route](../app/modules/cashflow/api.py#L386)).
- **POST** `/development-movements` — `record_development_movement` ([route](../app/modules/cashflow/api.py#L422)).
- **POST** `/development-movements/{movement_id}/confirm` — `confirm_development_movement` ([route](../app/modules/cashflow/api.py#L454)).
- **POST** `/development-movements/{movement_id}/reverse` — `reverse_development_movement` ([route](../app/modules/cashflow/api.py#L473)).
- **POST** `/financing-movements` — `record_financing_movement` ([route](../app/modules/cashflow/api.py#L514)).
- **POST** `/financing-movements/{movement_id}/confirm` — `confirm_financing_movement` ([route](../app/modules/cashflow/api.py#L545)).
- **POST** `/financing-movements/{movement_id}/reverse` — `reverse_financing_movement` ([route](../app/modules/cashflow/api.py#L563)).
- **POST** `/receipts/{receipt_id}/restriction` — `record_restriction` ([route](../app/modules/cashflow/api.py#L603)).
- **POST** `/restrictions/{restriction_id}/confirm` — `confirm_restriction` ([route](../app/modules/cashflow/api.py#L627)).
- **POST** `/restrictions/{restriction_id}/reverse` — `reverse_restriction` ([route](../app/modules/cashflow/api.py#L642)).
- **POST** `/restrictions/{restriction_id}/releases` — `record_release` ([route](../app/modules/cashflow/api.py#L667)).
- **POST** `/releases/{release_id}/confirm` — `confirm_release` ([route](../app/modules/cashflow/api.py#L711)).
- **POST** `/releases/{release_id}/reverse` — `reverse_release` ([route](../app/modules/cashflow/api.py#L725)).

## collections

- `CollectionReceipt` → `collection_receipts` ([model](../app/modules/collections/models.py#L153)).
- `CollectionReceiptAllocation` → `collection_receipt_allocations` ([model](../app/modules/collections/models.py#L240)).
- `CollectionAction` → `collection_actions` ([model](../app/modules/collections/models.py#L347)).
- `CollectionDispute` → `collection_disputes` ([model](../app/modules/collections/models.py#L411)).
- `CollectionWaiver` → `collection_waivers` ([model](../app/modules/collections/models.py#L477)).
- `CollectionRestructure` → `collection_restructures` ([model](../app/modules/collections/models.py#L570)).
- `CollectionRefund` → `collection_refunds` ([model](../app/modules/collections/models.py#L673)).
- **POST** `/sales/{sale_id}/receipts` — `create_receipt` ([route](../app/modules/collections/api.py#L398)).
- **POST** `/receipts/{receipt_id}/confirm` — `confirm_receipt` ([route](../app/modules/collections/api.py#L465)).
- **POST** `/receipts/{receipt_id}/reverse` — `reverse_receipt` ([route](../app/modules/collections/api.py#L488)).
- **POST** `/receipts/{receipt_id}/allocations` — `create_allocation` ([route](../app/modules/collections/api.py#L519)).
- **POST** `/allocations/{allocation_id}/reverse` — `reverse_allocation` ([route](../app/modules/collections/api.py#L545)).
- **POST** `/sales/{sale_id}/actions` — `create_action` ([route](../app/modules/collections/api.py#L576)).
- **POST** `/installments/{installment_id}/disputes` — `open_dispute` ([route](../app/modules/collections/api.py#L613)).
- **POST** `/disputes/{dispute_id}/resolve` — `resolve_dispute` ([route](../app/modules/collections/api.py#L638)).
- **POST** `/disputes/{dispute_id}/withdraw` — `withdraw_dispute` ([route](../app/modules/collections/api.py#L663)).
- **POST** `/installments/{installment_id}/waivers` — `submit_waiver` ([route](../app/modules/collections/api.py#L694)).
- **POST** `/waivers/{waiver_id}/approve` — `approve_waiver` ([route](../app/modules/collections/api.py#L721)).
- **POST** `/waivers/{waiver_id}/reject` — `reject_waiver` ([route](../app/modules/collections/api.py#L744)).
- **POST** `/waivers/{waiver_id}/revoke` — `revoke_waiver` ([route](../app/modules/collections/api.py#L769)).
- **POST** `/sales/{sale_id}/restructures` — `create_restructure` ([route](../app/modules/collections/api.py#L800)).
- **POST** `/restructures/{restructure_id}/apply` — `apply_restructure` ([route](../app/modules/collections/api.py#L862)).
- **POST** `/restructures/{restructure_id}/abandon` — `abandon_restructure` ([route](../app/modules/collections/api.py#L888)).
- **POST** `/sales/{sale_id}/refunds` — `create_refund` ([route](../app/modules/collections/api.py#L919)).
- **POST** `/refunds/{refund_id}/confirm` — `confirm_refund` ([route](../app/modules/collections/api.py#L949)).
- **POST** `/refunds/{refund_id}/reverse` — `reverse_refund` ([route](../app/modules/collections/api.py#L972)).
- **POST** `/sales/{sale_id}/collection-clearance` — `grant_clearance` ([route](../app/modules/collections/api.py#L1002)).

## commissions

- `CommissionGrant` → `commission_grants` ([model](../app/modules/commissions/models.py#L29)).
- `CommissionAllocation` → `commission_allocations` ([model](../app/modules/commissions/models.py#L106)).
- **POST** `` — `create_grant` ([route](../app/modules/commissions/api.py#L28)).
- **PUT** `/{commission_id}` — `update_grant` ([route](../app/modules/commissions/api.py#L40)).
- **POST** `/{commission_id}/allocations` — `add_allocation` ([route](../app/modules/commissions/api.py#L51)).
- **PUT** `/{commission_id}/allocations/{allocation_id}` — `update_allocation` ([route](../app/modules/commissions/api.py#L62)).
- **DELETE** `/{commission_id}/allocations/{allocation_id}` — `remove_allocation` ([route](../app/modules/commissions/api.py#L74)).
- **POST** `/{commission_id}/release` — `release` ([route](../app/modules/commissions/api.py#L85)).
- **POST** `/{commission_id}/reverse` — `reverse` ([route](../app/modules/commissions/api.py#L92)).

## construction

- `ConstructionStage` → `construction_stages` ([model](../app/modules/construction/models.py#L68)).
- `UnitStageEvent` → `unit_stage_events` ([model](../app/modules/construction/models.py#L88)).
- `CostCode` → `construction_cost_codes` ([model](../app/modules/construction/models.py#L325)).
- `BudgetVersion` → `construction_budget_versions` ([model](../app/modules/construction/models.py#L410)).
- `BudgetLine` → `construction_budget_lines` ([model](../app/modules/construction/models.py#L529)).
- `Contract` → `construction_contracts` ([model](../app/modules/construction/models.py#L593)).
- `ContractLine` → `construction_contract_lines` ([model](../app/modules/construction/models.py#L722)).
- `Variation` → `construction_variations` ([model](../app/modules/construction/models.py#L779)).
- `VariationLine` → `construction_variation_lines` ([model](../app/modules/construction/models.py#L866)).
- `Certificate` → `construction_certificates` ([model](../app/modules/construction/models.py#L921)).
- `CertificateLine` → `construction_certificate_lines` ([model](../app/modules/construction/models.py#L1049)).
- `Invoice` → `construction_invoices` ([model](../app/modules/construction/models.py#L1101)).
- `Payment` → `construction_payments` ([model](../app/modules/construction/models.py#L1237)).
- `PaymentAllocation` → `construction_payment_allocations` ([model](../app/modules/construction/models.py#L1336)).
- `Milestone` → `construction_milestones` ([model](../app/modules/construction/models.py#L1401)).
- `MilestoneDependency` → `construction_milestone_dependencies` ([model](../app/modules/construction/models.py#L1538)).
- `ForecastVersion` → `construction_forecast_versions` ([model](../app/modules/construction/models.py#L1588)).
- `ForecastLine` → `construction_forecast_lines` ([model](../app/modules/construction/models.py#L1706)).
- **POST** `/stages` — `create_stage` ([route](../app/modules/construction/api.py#L69)).
- **PATCH** `/stages/{stage_id}` — `update_stage` ([route](../app/modules/construction/api.py#L76)).
- **POST** `/units/{unit_id}/stages/{stage_id}/completion` — `record_unit_stage` ([route](../app/modules/construction/api.py#L96)).
- **POST** `/cost-codes` — `create_cost_code` ([route](../app/modules/construction/api.py#L168)).
- **PATCH** `/cost-codes/{cost_code_id}` — `update_cost_code` ([route](../app/modules/construction/api.py#L193)).
- **POST** `/cost-codes/{cost_code_id}/retire` — `retire_cost_code` ([route](../app/modules/construction/api.py#L213)).
- **POST** `/budgets` — `create_budget` ([route](../app/modules/construction/api.py#L252)).
- **PUT** `/budgets/{version_id}/lines` — `write_budget_line` ([route](../app/modules/construction/api.py#L283)).
- **POST** `/budgets/{version_id}/submit` — `submit_budget` ([route](../app/modules/construction/api.py#L310)).
- **POST** `/budgets/{version_id}/approve` — `approve_budget` ([route](../app/modules/construction/api.py#L323)).
- **POST** `/budgets/{version_id}/reject` — `reject_budget` ([route](../app/modules/construction/api.py#L336)).
- **POST** `/budgets/{version_id}/activate` — `activate_budget` ([route](../app/modules/construction/api.py#L352)).
- **POST** `/contracts` — `create_contract` ([route](../app/modules/construction/api.py#L384)).
- **PUT** `/contracts/{contract_id}` — `update_contract` ([route](../app/modules/construction/api.py#L428)).
- **PUT** `/contracts/{contract_id}/lines` — `write_contract_line` ([route](../app/modules/construction/api.py#L448)).
- **POST** `/contracts/{contract_id}/submit` — `submit_contract` ([route](../app/modules/construction/api.py#L473)).
- **POST** `/contracts/{contract_id}/activate` — `activate_contract` ([route](../app/modules/construction/api.py#L488)).
- **POST** `/contracts/{contract_id}/complete` — `complete_contract` ([route](../app/modules/construction/api.py#L504)).
- **POST** `/contracts/{contract_id}/terminate` — `terminate_contract` ([route](../app/modules/construction/api.py#L519)).
- **POST** `/contracts/{contract_id}/cancel` — `cancel_contract` ([route](../app/modules/construction/api.py#L540)).
- **POST** `/contracts/{contract_id}/variations` — `create_variation` ([route](../app/modules/construction/api.py#L583)).
- **PUT** `/variations/{variation_id}/lines` — `write_variation_line` ([route](../app/modules/construction/api.py#L621)).
- **POST** `/variations/{variation_id}/submit` — `submit_variation` ([route](../app/modules/construction/api.py#L645)).
- **POST** `/variations/{variation_id}/approve` — `approve_variation` ([route](../app/modules/construction/api.py#L660)).
- **POST** `/variations/{variation_id}/reject` — `reject_variation` ([route](../app/modules/construction/api.py#L676)).
- **POST** `/variations/{variation_id}/withdraw` — `withdraw_variation` ([route](../app/modules/construction/api.py#L696)).
- **POST** `/contracts/{contract_id}/certificates` — `create_certificate` ([route](../app/modules/construction/api.py#L741)).
- **PUT** `/certificates/{certificate_id}/lines` — `write_certificate_line` ([route](../app/modules/construction/api.py#L784)).
- **POST** `/certificates/{certificate_id}/submit` — `submit_certificate` ([route](../app/modules/construction/api.py#L806)).
- **POST** `/certificates/{certificate_id}/certify` — `certify_certificate` ([route](../app/modules/construction/api.py#L821)).
- **POST** `/certificates/{certificate_id}/reject` — `reject_certificate` ([route](../app/modules/construction/api.py#L837)).
- **POST** `/certificates/{certificate_id}/reverse` — `reverse_certificate` ([route](../app/modules/construction/api.py#L857)).
- **POST** `/contracts/{contract_id}/invoices` — `record_invoice` ([route](../app/modules/construction/api.py#L902)).
- **POST** `/invoices/{invoice_id}/approve` — `approve_invoice` ([route](../app/modules/construction/api.py#L943)).
- **POST** `/invoices/{invoice_id}/dispute` — `dispute_invoice` ([route](../app/modules/construction/api.py#L957)).
- **POST** `/invoices/{invoice_id}/resolve` — `resolve_invoice_dispute` ([route](../app/modules/construction/api.py#L974)).
- **POST** `/invoices/{invoice_id}/void` — `void_invoice` ([route](../app/modules/construction/api.py#L990)).
- **POST** `/contracts/{contract_id}/payments` — `record_payment` ([route](../app/modules/construction/api.py#L1029)).
- **PUT** `/payments/{payment_id}/allocations` — `allocate_payment` ([route](../app/modules/construction/api.py#L1069)).
- **POST** `/payments/{payment_id}/confirm` — `confirm_payment` ([route](../app/modules/construction/api.py#L1091)).
- **POST** `/payments/{payment_id}/reverse` — `reverse_payment` ([route](../app/modules/construction/api.py#L1106)).
- **POST** `/milestones` — `create_milestone` ([route](../app/modules/construction/api.py#L1144)).
- **PATCH** `/milestones/{milestone_id}` — `update_milestone` ([route](../app/modules/construction/api.py#L1182)).
- **POST** `/milestones/{milestone_id}/achieve` — `achieve_milestone` ([route](../app/modules/construction/api.py#L1203)).
- **POST** `/milestones/{milestone_id}/certify` — `certify_milestone` ([route](../app/modules/construction/api.py#L1225)).
- **POST** `/milestones/{milestone_id}/cancel` — `cancel_milestone` ([route](../app/modules/construction/api.py#L1257)).
- **PUT** `/milestones/{milestone_id}/dependencies` — `add_dependency` ([route](../app/modules/construction/api.py#L1278)).
- **POST** `/forecasts` — `create_forecast` ([route](../app/modules/construction/api.py#L1353)).
- **PUT** `/forecasts/{version_id}/lines` — `write_forecast_line` ([route](../app/modules/construction/api.py#L1387)).
- **POST** `/forecasts/{version_id}/submit` — `submit_forecast` ([route](../app/modules/construction/api.py#L1410)).
- **POST** `/forecasts/{version_id}/approve` — `approve_forecast` ([route](../app/modules/construction/api.py#L1423)).
- **POST** `/forecasts/{version_id}/reject` — `reject_forecast` ([route](../app/modules/construction/api.py#L1436)).
- **POST** `/forecasts/{version_id}/activate` — `activate_forecast` ([route](../app/modules/construction/api.py#L1452)).
- **POST** `/delivery/start` — `mark_construction_started` ([route](../app/modules/construction/api.py#L1472)).
- **POST** `/delivery/ready` — `mark_construction_ready` ([route](../app/modules/construction/api.py#L1500)).
- **POST** `/delivery/revoke-ready` — `revoke_construction_readiness` ([route](../app/modules/construction/api.py#L1523)).

## consultant_engineering

- `ConsultantEngagement` → `consultant_engagements` ([model](../app/modules/consultant_engineering/models.py#L39)).
- `ConsultantDiscipline` → `consultant_disciplines` ([model](../app/modules/consultant_engineering/models.py#L83)).
- `ConsultantDesignStage` → `consultant_design_stages` ([model](../app/modules/consultant_engineering/models.py#L114)).
- `ConsultantDeliverable` → `consultant_deliverables` ([model](../app/modules/consultant_engineering/models.py#L151)).
- **POST** `/engagements` — `create_engagement` ([route](../app/modules/consultant_engineering/api.py#L27)).
- **PUT** `/engagements/{engagement_id}` — `update_engagement` ([route](../app/modules/consultant_engineering/api.py#L37)).
- **POST** `/engagements/{engagement_id}/activate` — `activate_engagement` ([route](../app/modules/consultant_engineering/api.py#L48)).
- **POST** `/engagements/{engagement_id}/complete` — `complete_engagement` ([route](../app/modules/consultant_engineering/api.py#L55)).
- **POST** `/engagements/{engagement_id}/terminate` — `terminate_engagement` ([route](../app/modules/consultant_engineering/api.py#L62)).
- **POST** `/engagements/{engagement_id}/disciplines` — `create_discipline` ([route](../app/modules/consultant_engineering/api.py#L73)).
- **PUT** `/disciplines/{discipline_id}` — `update_discipline` ([route](../app/modules/consultant_engineering/api.py#L84)).
- **POST** `/engagements/{engagement_id}/stages` — `create_stage` ([route](../app/modules/consultant_engineering/api.py#L99)).
- **PUT** `/stages/{stage_id}` — `update_stage` ([route](../app/modules/consultant_engineering/api.py#L110)).
- **POST** `/engagements/{engagement_id}/deliverables` — `create_deliverable` ([route](../app/modules/consultant_engineering/api.py#L125)).
- **PUT** `/deliverables/{deliverable_id}` — `update_deliverable` ([route](../app/modules/consultant_engineering/api.py#L136)).

## inventory

- `Phase` → `phases` ([model](../app/modules/inventory/models.py#L231)).
- `UserPhaseAccess` → `user_phase_access` ([model](../app/modules/inventory/models.py#L285)).
- `Building` → `buildings` ([model](../app/modules/inventory/models.py#L334)).
- `Floor` → `floors` ([model](../app/modules/inventory/models.py#L377)).
- `Unit` → `units` ([model](../app/modules/inventory/models.py#L428)).
- `UnitStatusEvent` → `unit_status_events` ([model](../app/modules/inventory/models.py#L538)).
- `InventorySubAsset` → `inventory_sub_assets` ([model](../app/modules/inventory/models.py#L575)).
- `AreaType` → `area_types` ([model](../app/modules/inventory/models.py#L637)).
- `UnitAreaSchedule` → `unit_area_schedules` ([model](../app/modules/inventory/models.py#L709)).
- `UnitAreaValue` → `unit_area_values` ([model](../app/modules/inventory/models.py#L780)).
- `CustomFieldDefinition` → `custom_field_definitions` ([model](../app/modules/inventory/models.py#L816)).
- `CustomFieldOption` → `custom_field_options` ([model](../app/modules/inventory/models.py#L948)).
- `ProjectCustomFieldValue` → `project_custom_field_values` ([model](../app/modules/inventory/models.py#L996)).
- `LandParcelCustomFieldValue` → `land_parcel_custom_field_values` ([model](../app/modules/inventory/models.py#L1029)).
- `UnitCustomFieldValue` → `unit_custom_field_values` ([model](../app/modules/inventory/models.py#L1060)).
- `UnitFeature` → `unit_features` ([model](../app/modules/inventory/models.py#L1091)).
- `UnitDocument` → `unit_documents` ([model](../app/modules/inventory/models.py#L1117)).
- **DELETE** `/{project_id}/inventory/{kind}/{identifier}` — `delete_inventory_record` ([route](../app/modules/inventory/api.py#L95)).
- **POST** `/{project_id}/inventory/phases` — `create_phase` ([route](../app/modules/inventory/api.py#L137)).
- **PATCH** `/{project_id}/inventory/phases/{phase_id}` — `update_phase` ([route](../app/modules/inventory/api.py#L176)).
- **POST** `/{project_id}/inventory/buildings` — `create_building` ([route](../app/modules/inventory/api.py#L221)).
- **PATCH** `/{project_id}/inventory/buildings/{building_id}` — `update_building` ([route](../app/modules/inventory/api.py#L248)).
- **POST** `/{project_id}/inventory/floors` — `create_floor` ([route](../app/modules/inventory/api.py#L290)).
- **PATCH** `/{project_id}/inventory/floors/{floor_id}` — `update_floor` ([route](../app/modules/inventory/api.py#L318)).
- **POST** `/{project_id}/inventory/units` — `create_unit` ([route](../app/modules/inventory/api.py#L439)).
- **PATCH** `/{project_id}/inventory/units/{unit_id}` — `update_unit` ([route](../app/modules/inventory/api.py#L491)).
- **PATCH** `/{project_id}/inventory/units/{unit_id}/release-controls` — `update_release_controls` ([route](../app/modules/inventory/api.py#L515)).
- **POST** `/{project_id}/inventory/units/{unit_id}/commercial-transitions` — `transition_unit` ([route](../app/modules/inventory/api.py#L544)).
- **POST** `/{project_id}/inventory/area-types` — `create_area_type` ([route](../app/modules/inventory/api.py#L610)).
- **PATCH** `/{project_id}/inventory/area-types/{area_type_id}` — `update_area_type` ([route](../app/modules/inventory/api.py#L633)).
- **POST** `/{project_id}/inventory/units/{unit_id}/area-schedules` — `create_area_schedule` ([route](../app/modules/inventory/api.py#L698)).
- **PATCH** `/{project_id}/inventory/units/{unit_id}/area-schedules/{schedule_id}` — `update_area_schedule` ([route](../app/modules/inventory/api.py#L727)).
- **POST** `/{project_id}/inventory/units/{unit_id}/area-schedules/{schedule_id}/approve` — `approve_area_schedule` ([route](../app/modules/inventory/api.py#L761)).
- **POST** `/{project_id}/inventory/sub-assets` — `create_sub_asset` ([route](../app/modules/inventory/api.py#L824)).
- **PATCH** `/{project_id}/inventory/sub-assets/{asset_id}` — `update_sub_asset` ([route](../app/modules/inventory/api.py#L859)).
- **PATCH** `/{project_id}/access/{user_id}/phase-scope` — `set_phase_scope` ([route](../app/modules/inventory/api.py#L888)).
- **PUT** `/{project_id}/access/{user_id}/phases/{phase_id}` — `grant_phase_access` ([route](../app/modules/inventory/api.py#L939)).
- **PATCH** `/{project_id}/access/{user_id}/phases/{phase_id}` — `change_phase_access` ([route](../app/modules/inventory/api.py#L954)).
- **POST** `/{project_id}/field-definitions` — `create_field_definition` ([route](../app/modules/inventory/api.py#L1047)).
- **PATCH** `/{project_id}/field-definitions/{definition_id}` — `update_field_definition` ([route](../app/modules/inventory/api.py#L1067)).
- **PUT** `/{project_id}/custom-values` — `write_project_values` ([route](../app/modules/inventory/api.py#L1151)).
- **PUT** `/{project_id}/parcels/{parcel_id}/custom-values` — `write_parcel_values` ([route](../app/modules/inventory/api.py#L1198)).
- **PUT** `/{project_id}/inventory/units/{unit_id}/custom-values` — `write_unit_values` ([route](../app/modules/inventory/api.py#L1251)).
- **POST** `/{project_id}/inventory/import/validate` — `validate_import` ([route](../app/modules/inventory/api.py#L1298)).
- **POST** `/{project_id}/inventory/import/apply` — `apply_import` ([route](../app/modules/inventory/api.py#L1328)).
- **POST** `/{project_id}/inventory/import/workbook/validate` — `validate_workbook_import` ([route](../app/modules/inventory/api.py#L1390)).
- **POST** `/{project_id}/inventory/import/workbook/apply` — `apply_workbook_import` ([route](../app/modules/inventory/api.py#L1412)).
- **POST** `/{project_id}/inventory/units/{unit_id}/features` — `create_unit_feature` ([route](../app/modules/inventory/api.py#L1474)).
- **POST** `/{project_id}/inventory/units/{unit_id}/features/{feature_id}/retire` — `retire_unit_feature` ([route](../app/modules/inventory/api.py#L1493)).
- **POST** `/{project_id}/inventory/units/{unit_id}/documents` — `create_unit_document` ([route](../app/modules/inventory/api.py#L1523)).
- **POST** `/{project_id}/inventory/units/{unit_id}/documents/{document_id}/retire` — `retire_unit_document` ([route](../app/modules/inventory/api.py#L1549)).

## management_actions

- `ManagementAction` → `management_actions` ([model](../app/modules/management_actions/models.py#L26)).
- `ManagementActionHistory` → `management_action_history` ([model](../app/modules/management_actions/models.py#L73)).

## management_reporting

- `Snapshot` → `management_report_snapshots` ([model](../app/modules/management_reporting/models.py#L13)).
- `SnapshotProject` → `management_report_snapshot_projects` ([model](../app/modules/management_reporting/models.py#L53)).
- **POST** `/snapshots` — `capture` ([route](../app/modules/management_reporting/api.py#L16)).

## payment_plans

- `PaymentPlan` → `payment_plans` ([model](../app/modules/payment_plans/models.py#L167)).
- `PaymentPlanVersion` → `payment_plan_versions` ([model](../app/modules/payment_plans/models.py#L231)).
- `PaymentPlanInstallment` → `payment_plan_installments` ([model](../app/modules/payment_plans/models.py#L360)).
- `InstallmentTriggerEvent` → `installment_trigger_events` ([model](../app/modules/payment_plans/models.py#L474)).
- **POST** `` — `create_plan` ([route](../app/modules/payment_plans/api.py#L164)).
- **POST** `/series-preview` — `series_preview` ([route](../app/modules/payment_plans/api.py#L192)).
- **POST** `/{plan_id}/versions` — `create_version` ([route](../app/modules/payment_plans/api.py#L315)).
- **PUT** `/{plan_id}/versions/{version_id}/installments` — `write_schedule` ([route](../app/modules/payment_plans/api.py#L360)).
- **POST** `/{plan_id}/versions/{version_id}/submit` — `submit_version` ([route](../app/modules/payment_plans/api.py#L408)).
- **POST** `/{plan_id}/versions/{version_id}/approve` — `approve_version` ([route](../app/modules/payment_plans/api.py#L433)).
- **POST** `/{plan_id}/versions/{version_id}/reject` — `reject_version` ([route](../app/modules/payment_plans/api.py#L460)).
- **POST** `/{plan_id}/versions/{version_id}/activate` — `activate_version` ([route](../app/modules/payment_plans/api.py#L487)).
- **POST** `/{plan_id}/refresh-triggers` — `refresh_triggers` ([route](../app/modules/payment_plans/api.py#L517)).
- **PATCH** `/{plan_id}/installments/{installment_id}/forecast` — `set_forecast` ([route](../app/modules/payment_plans/api.py#L548)).
- **PATCH** `/{plan_id}/installments/{installment_id}/owner` — `set_owner` ([route](../app/modules/payment_plans/api.py#L576)).
- **POST** `/{plan_id}/installments/{installment_id}/manual-trigger` — `submit_manual_trigger` ([route](../app/modules/payment_plans/api.py#L628)).
- **POST** `/{plan_id}/trigger-events/{event_id}/approve` — `approve_manual_trigger` ([route](../app/modules/payment_plans/api.py#L657)).
- **POST** `/{plan_id}/trigger-events/{event_id}/reverse` — `reverse_manual_trigger` ([route](../app/modules/payment_plans/api.py#L682)).

## portfolio

- **POST** `` — `create_action` ([route](../app/modules/portfolio/action_api.py#L137)).
- **PATCH** `/{action_id}` — `update` ([route](../app/modules/portfolio/action_api.py#L181)).
- **POST** `/{action_id}/transitions` — `transition` ([route](../app/modules/portfolio/action_api.py#L189)).

## prelaunch

- **POST** `/expenses` — `record_expense` ([route](../app/modules/prelaunch/api.py#L75)).
- **POST** `/expenses/{movement_id}/confirm` — `confirm_expense` ([route](../app/modules/prelaunch/api.py#L105)).
- **POST** `/expenses/{movement_id}/reverse` — `reverse_expense` ([route](../app/modules/prelaunch/api.py#L123)).

## pricing

- `PricingConfiguration` → `pricing_configurations` ([model](../app/modules/pricing/models.py#L249)).
- `PricingAreaRule` → `pricing_area_rules` ([model](../app/modules/pricing/models.py#L377)).
- `PricingPremiumRule` → `pricing_premium_rules` ([model](../app/modules/pricing/models.py#L458)).
- `PricingEscalationRule` → `pricing_escalation_rules` ([model](../app/modules/pricing/models.py#L563)).
- `PricingEscalationActivation` → `pricing_escalation_activations` ([model](../app/modules/pricing/models.py#L681)).
- `MarketBenchmark` → `market_benchmarks` ([model](../app/modules/pricing/models.py#L749)).
- `UnitPriceVersion` → `unit_price_versions` ([model](../app/modules/pricing/models.py#L823)).
- `UnitPriceComponent` → `unit_price_components` ([model](../app/modules/pricing/models.py#L963)).
- **POST** `/{project_id}/pricing/configurations` — `create_configuration` ([route](../app/modules/pricing/api.py#L158)).
- **PATCH** `/{project_id}/pricing/configurations/{configuration_id}` — `update_configuration` ([route](../app/modules/pricing/api.py#L194)).
- **POST** `/{project_id}/pricing/configurations/{configuration_id}/submit` — `submit_configuration` ([route](../app/modules/pricing/api.py#L218)).
- **POST** `/{project_id}/pricing/configurations/{configuration_id}/return` — `return_configuration` ([route](../app/modules/pricing/api.py#L243)).
- **POST** `/{project_id}/pricing/configurations/{configuration_id}/approve` — `approve_configuration` ([route](../app/modules/pricing/api.py#L268)).
- **POST** `/{project_id}/pricing/configurations/{configuration_id}/activate` — `activate_configuration` ([route](../app/modules/pricing/api.py#L293)).
- **POST** `/{project_id}/pricing/configurations/{configuration_id}/area-rules` — `create_area_rule` ([route](../app/modules/pricing/api.py#L338)).
- **PATCH** `/{project_id}/pricing/area-rules/{rule_id}` — `update_area_rule` ([route](../app/modules/pricing/api.py#L363)).
- **POST** `/{project_id}/pricing/configurations/{configuration_id}/premium-rules` — `create_premium_rule` ([route](../app/modules/pricing/api.py#L408)).
- **PATCH** `/{project_id}/pricing/premium-rules/{rule_id}` — `update_premium_rule` ([route](../app/modules/pricing/api.py#L433)).
- **POST** `/{project_id}/pricing/configurations/{configuration_id}/escalation-rules` — `create_escalation_rule` ([route](../app/modules/pricing/api.py#L484)).
- **PATCH** `/{project_id}/pricing/escalation-rules/{rule_id}` — `update_escalation_rule` ([route](../app/modules/pricing/api.py#L509)).
- **POST** `/{project_id}/pricing/escalation-rules/{rule_id}/activate` — `activate_escalation` ([route](../app/modules/pricing/api.py#L535)).
- **POST** `/{project_id}/pricing/escalation-activations/{activation_id}/reverse` — `reverse_activation` ([route](../app/modules/pricing/api.py#L575)).
- **POST** `/{project_id}/pricing/market-benchmarks` — `create_benchmark` ([route](../app/modules/pricing/api.py#L617)).
- **PATCH** `/{project_id}/pricing/market-benchmarks/{benchmark_id}` — `update_benchmark` ([route](../app/modules/pricing/api.py#L635)).
- **POST** `/{project_id}/pricing/units/{unit_id}/price-versions` — `create_price_version` ([route](../app/modules/pricing/api.py#L814)).
- **POST** `/{project_id}/pricing/units/{unit_id}/quote-preview` — `quote_preview` ([route](../app/modules/pricing/api.py#L839)).
- **POST** `/{project_id}/pricing/price-versions/generate` — `generate_price_versions` ([route](../app/modules/pricing/api.py#L935)).
- **POST** `/{project_id}/pricing/price-versions/submit` — `bulk_submit` ([route](../app/modules/pricing/api.py#L969)).
- **POST** `/{project_id}/pricing/price-versions/approve` — `bulk_approve` ([route](../app/modules/pricing/api.py#L995)).
- **POST** `/{project_id}/pricing/price-versions/activate` — `bulk_activate` ([route](../app/modules/pricing/api.py#L1021)).
- **PATCH** `/{project_id}/pricing/price-versions/{version_id}` — `update_price_version` ([route](../app/modules/pricing/api.py#L1066)).
- **POST** `/{project_id}/pricing/price-versions/{version_id}/submit` — `submit_price_version` ([route](../app/modules/pricing/api.py#L1092)).
- **POST** `/{project_id}/pricing/price-versions/{version_id}/return` — `return_price_version` ([route](../app/modules/pricing/api.py#L1113)).
- **POST** `/{project_id}/pricing/price-versions/{version_id}/approve` — `approve_price_version` ([route](../app/modules/pricing/api.py#L1134)).
- **POST** `/{project_id}/pricing/price-versions/{version_id}/activate` — `activate_price_version` ([route](../app/modules/pricing/api.py#L1155)).

## projects

- `Project` → `projects` ([model](../app/modules/projects/models.py#L105)).
- `UserProjectAccess` → `user_project_access` ([model](../app/modules/projects/models.py#L180)).
- `LandParcel` → `land_parcels` ([model](../app/modules/projects/models.py#L229)).
- `LandMarketAssumption` → `land_market_assumptions` ([model](../app/modules/projects/models.py#L360)).
- `PlanningControl` → `planning_controls` ([model](../app/modules/projects/models.py#L382)).
- `Permit` → `permits` ([model](../app/modules/projects/models.py#L456)).
- `PermitStatusEvent` → `permit_status_events` ([model](../app/modules/projects/models.py#L542)).
- `DocumentReference` → `document_references` ([model](../app/modules/projects/models.py#L580)).
- **POST** `` — `create_project` ([route](../app/modules/projects/api.py#L154)).
- **PATCH** `/{project_id}` — `update_project` ([route](../app/modules/projects/api.py#L194)).
- **PUT** `/{project_id}/access/{user_id}` — `grant_project_access` ([route](../app/modules/projects/api.py#L252)).
- **PATCH** `/{project_id}/access/{user_id}` — `update_project_access` ([route](../app/modules/projects/api.py#L273)).
- **POST** `/{project_id}/parcels` — `create_parcel` ([route](../app/modules/projects/api.py#L322)).
- **PATCH** `/{project_id}/parcels/{parcel_id}` — `update_parcel` ([route](../app/modules/projects/api.py#L359)).
- **PUT** `/{project_id}/parcels/{parcel_id}/market-assumptions/{year}` — `write_land_market_assumption` ([route](../app/modules/projects/api.py#L400)).
- **PUT** `/{project_id}/parcels/{parcel_id}/planning-controls` — `write_planning_controls` ([route](../app/modules/projects/api.py#L449)).
- **POST** `/{project_id}/permit-types` — `create_permit_type` ([route](../app/modules/projects/api.py#L494)).
- **POST** `/{project_id}/permits` — `create_permit` ([route](../app/modules/projects/api.py#L572)).
- **PATCH** `/{project_id}/permits/{permit_id}` — `update_permit` ([route](../app/modules/projects/api.py#L603)).
- **POST** `/{project_id}/permits/{permit_id}/transitions` — `transition_permit` ([route](../app/modules/projects/api.py#L629)).
- **POST** `/{project_id}/documents` — `create_document` ([route](../app/modules/projects/api.py#L707)).
- **PATCH** `/{project_id}/documents/{document_id}` — `update_document` ([route](../app/modules/projects/api.py#L730)).

## sales

- `SalesProjectPolicy` → `sales_project_policies` ([model](../app/modules/sales/models.py#L327)).
- `Client` → `clients` ([model](../app/modules/sales/models.py#L383)).
- `ClientParty` → `client_parties` ([model](../app/modules/sales/models.py#L459)).
- `Reservation` → `reservations` ([model](../app/modules/sales/models.py#L528)).
- `ReservationAdjustment` → `reservation_adjustments` ([model](../app/modules/sales/models.py#L740)).
- `ReservationStatusEvent` → `reservation_status_events` ([model](../app/modules/sales/models.py#L817)).
- `SaleContract` → `sale_contracts` ([model](../app/modules/sales/models.py#L864)).
- `SaleContractParty` → `sale_contract_parties` ([model](../app/modules/sales/models.py#L1041)).
- `SaleContractTaxLine` → `sale_contract_tax_lines` ([model](../app/modules/sales/models.py#L1088)).
- `SaleLegalEvent` → `sale_legal_events` ([model](../app/modules/sales/models.py#L1141)).
- `SaleCancellation` → `sale_cancellations` ([model](../app/modules/sales/models.py#L1233)).
- `HandoverRecord` → `handover_records` ([model](../app/modules/sales/models.py#L1340)).
- `HandoverClearance` → `handover_clearances` ([model](../app/modules/sales/models.py#L1398)).
- **POST** `/{project_id}/sales/price-preview` — `sales_price_preview` ([route](../app/modules/sales/api.py#L134)).
- **PUT** `/{project_id}/sales/reservations/{reservation_id}/sales-price` — `change_sales_price` ([route](../app/modules/sales/api.py#L149)).
- **POST** `/{project_id}/sales/reservations/{reservation_id}/price-preview` — `reservation_price_preview` ([route](../app/modules/sales/api.py#L166)).
- **POST** `/{project_id}/sales/buyer-registrations` — `register_buyer` ([route](../app/modules/sales/api.py#L212)).
- **DELETE** `/{project_id}/sales/clients/{client_id}` — `delete_client` ([route](../app/modules/sales/api.py#L222)).
- **PUT** `/{project_id}/sales/policy` — `write_policy` ([route](../app/modules/sales/api.py#L258)).
- **POST** `/{project_id}/sales/clients` — `create_client` ([route](../app/modules/sales/api.py#L309)).
- **PATCH** `/{project_id}/sales/clients/{client_id}` — `update_client` ([route](../app/modules/sales/api.py#L341)).
- **POST** `/{project_id}/sales/clients/{client_id}/parties` — `create_party` ([route](../app/modules/sales/api.py#L399)).
- **PATCH** `/{project_id}/sales/client-parties/{party_id}` — `update_party` ([route](../app/modules/sales/api.py#L424)).
- **POST** `/{project_id}/sales/reservations` — `create_reservation` ([route](../app/modules/sales/api.py#L501)).
- **PATCH** `/{project_id}/sales/reservations/{reservation_id}` — `update_reservation` ([route](../app/modules/sales/api.py#L535)).
- **POST** `/{project_id}/sales/reservations/{reservation_id}/recalculate` — `recalculate_reservation` ([route](../app/modules/sales/api.py#L557)).
- **POST** `/{project_id}/sales/reservations/{reservation_id}/adjustments` — `create_adjustment` ([route](../app/modules/sales/api.py#L600)).
- **PATCH** `/{project_id}/sales/reservation-adjustments/{adjustment_id}` — `update_adjustment` ([route](../app/modules/sales/api.py#L625)).
- **POST** `/{project_id}/sales/reservations/{reservation_id}/requote` — `requote_reservation` ([route](../app/modules/sales/api.py#L647)).
- **POST** `/{project_id}/sales/reservations/{reservation_id}/submit-exception` — `submit_exception` ([route](../app/modules/sales/api.py#L670)).
- **POST** `/{project_id}/sales/reservations/{reservation_id}/approve-exception` — `decide_exception` ([route](../app/modules/sales/api.py#L692)).
- **POST** `/{project_id}/sales/reservations/{reservation_id}/confirm-deposit` — `confirm_deposit` ([route](../app/modules/sales/api.py#L715)).
- **POST** `/{project_id}/sales/reservations/{reservation_id}/waive-deposit` — `waive_deposit` ([route](../app/modules/sales/api.py#L737)).
- **POST** `/{project_id}/sales/reservations/{reservation_id}/activate` — `activate_reservation` ([route](../app/modules/sales/api.py#L759)).
- **POST** `/{project_id}/sales/reservations/{reservation_id}/extend` — `extend_reservation` ([route](../app/modules/sales/api.py#L781)).
- **POST** `/{project_id}/sales/reservations/{reservation_id}/expire` — `expire_reservation` ([route](../app/modules/sales/api.py#L803)).
- **POST** `/{project_id}/sales/reservations/{reservation_id}/cancel` — `cancel_reservation` ([route](../app/modules/sales/api.py#L825)).
- **POST** `/{project_id}/sales/contracts` — `create_sale` ([route](../app/modules/sales/api.py#L942)).
- **PATCH** `/{project_id}/sales/contracts/{sale_id}` — `update_sale` ([route](../app/modules/sales/api.py#L974)).
- **POST** `/{project_id}/sales/contracts/{sale_id}/submit` — `submit_sale` ([route](../app/modules/sales/api.py#L996)).
- **POST** `/{project_id}/sales/contracts/{sale_id}/confirm-first-payment` — `confirm_first_payment` ([route](../app/modules/sales/api.py#L1018)).
- **POST** `/{project_id}/sales/contracts/{sale_id}/waive-first-payment` — `waive_first_payment` ([route](../app/modules/sales/api.py#L1040)).
- **POST** `/{project_id}/sales/contracts/{sale_id}/activate` — `activate_sale` ([route](../app/modules/sales/api.py#L1058)).
- **POST** `/{project_id}/sales/contracts/{sale_id}/legal-events` — `record_legal_event` ([route](../app/modules/sales/api.py#L1101)).
- **POST** `/{project_id}/sales/legal-events/{event_id}/reverse` — `reverse_legal_event` ([route](../app/modules/sales/api.py#L1124)).
- **POST** `/{project_id}/sales/contracts/{sale_id}/cancellation` — `start_cancellation` ([route](../app/modules/sales/api.py#L1171)).
- **POST** `/{project_id}/sales/cancellations/{cancellation_id}/approve-financial-terms` — `approve_cancellation_terms` ([route](../app/modules/sales/api.py#L1193)).
- **POST** `/{project_id}/sales/cancellations/{cancellation_id}/advance` — `advance_cancellation` ([route](../app/modules/sales/api.py#L1215)).
- **POST** `/{project_id}/sales/cancellations/{cancellation_id}/complete` — `complete_cancellation` ([route](../app/modules/sales/api.py#L1237)).
- **POST** `/{project_id}/sales/contracts/{sale_id}/handover` — `create_handover` ([route](../app/modules/sales/api.py#L1280)).
- **PATCH** `/{project_id}/sales/handovers/{handover_id}` — `update_handover` ([route](../app/modules/sales/api.py#L1303)).
- **POST** `/{project_id}/sales/handovers/{handover_id}/clearances/{clearance_type}` — `grant_clearance` ([route](../app/modules/sales/api.py#L1328)).
- **POST** `/{project_id}/sales/handovers/{handover_id}/clearances/{clearance_type}/revoke` — `revoke_clearance` ([route](../app/modules/sales/api.py#L1352)).
- **POST** `/{project_id}/sales/handovers/{handover_id}/complete` — `complete_handover` ([route](../app/modules/sales/api.py#L1376)).

## settings

- `Currency` → `currencies` ([model](../app/modules/settings/models.py#L42)).
- `CountryPack` → `country_packs` ([model](../app/modules/settings/models.py#L68)).
- `TaxRule` → `tax_rules` ([model](../app/modules/settings/models.py#L108)).
- `ReferenceValue` → `reference_values` ([model](../app/modules/settings/models.py#L148)).
- `CountryApprovalThreshold` → `country_approval_thresholds` ([model](../app/modules/settings/models.py#L206)).
- **POST** `/currencies` — `create_currency` ([route](../app/modules/settings/api.py#L59)).
- **PATCH** `/currencies/{currency_id}` — `update_currency` ([route](../app/modules/settings/api.py#L77)).
- **POST** `/country-packs` — `create_country_pack` ([route](../app/modules/settings/api.py#L116)).
- **PATCH** `/country-packs/{country_pack_id}` — `update_country_pack` ([route](../app/modules/settings/api.py#L154)).
- **POST** `/country-packs/{country_pack_id}/tax-rules` — `create_tax_rule` ([route](../app/modules/settings/api.py#L197)).
- **PATCH** `/tax-rules/{tax_rule_id}` — `update_tax_rule` ([route](../app/modules/settings/api.py#L220)).
- **POST** `/reference-values` — `create_reference_value` ([route](../app/modules/settings/api.py#L271)).
- **PATCH** `/reference-values/{reference_value_id}` — `update_reference_value` ([route](../app/modules/settings/api.py#L297)).
- **PUT** `/country-packs/{country_pack_id}/approval-thresholds` — `write_approval_thresholds` ([route](../app/modules/settings/api.py#L338)).

## unit_economics

- `AllocationVersion` → `unit_economics_allocation_versions` ([model](../app/modules/unit_economics/models.py#L261)).
- `CostPool` → `unit_economics_cost_pools` ([model](../app/modules/unit_economics/models.py#L378)).
- `Allocation` → `unit_economics_allocations` ([model](../app/modules/unit_economics/models.py#L553)).
- `UnitCost` → `unit_economics_unit_costs` ([model](../app/modules/unit_economics/models.py#L646)).
- **POST** `/allocation-versions` — `create_version` ([route](../app/modules/unit_economics/api.py#L436)).
- **POST** `/allocation-versions/{version_id}/clone` — `clone_version` ([route](../app/modules/unit_economics/api.py#L462)).
- **POST** `/allocation-versions/{version_id}/pools` — `add_pool` ([route](../app/modules/unit_economics/api.py#L494)).
- **PATCH** `/allocation-versions/{version_id}/pools/{pool_id}` — `update_pool` ([route](../app/modules/unit_economics/api.py#L529)).
- **DELETE** `/allocation-versions/{version_id}/pools/{pool_id}` — `remove_pool` ([route](../app/modules/unit_economics/api.py#L556)).
- **PUT** `/allocation-versions/{version_id}/pools/{pool_id}/drivers` — `set_drivers` ([route](../app/modules/unit_economics/api.py#L579)).
- **POST** `/allocation-versions/{version_id}/calculate` — `calculate_version` ([route](../app/modules/unit_economics/api.py#L614)).
- **POST** `/allocation-versions/{version_id}/submit` — `submit_version` ([route](../app/modules/unit_economics/api.py#L648)).
- **POST** `/allocation-versions/{version_id}/approve` — `approve_version` ([route](../app/modules/unit_economics/api.py#L671)).
- **POST** `/allocation-versions/{version_id}/reject` — `reject_version` ([route](../app/modules/unit_economics/api.py#L696)).
- **POST** `/allocation-versions/{version_id}/activate` — `activate_version` ([route](../app/modules/unit_economics/api.py#L721)).
- **POST** `/units/{unit_id}/costs` — `record_unit_cost` ([route](../app/modules/unit_economics/api.py#L750)).
- **POST** `/unit-costs/{cost_id}/reverse` — `reverse_unit_cost` ([route](../app/modules/unit_economics/api.py#L782)).

