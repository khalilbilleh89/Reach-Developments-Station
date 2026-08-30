/**
 * Domain types mirroring the API's response schemas.
 *
 * Declared once. Pages import from here rather than restating shapes, so a
 * contract change surfaces in one place.
 *
 * Money and rates arrive as strings, deliberately: a JSON number is a float,
 * and a float is never an acceptable carrier for a financial value. They are
 * displayed and echoed back as strings, never parsed into a number.
 */

export interface Role {
  key: string;
  label: string;
}

export interface CurrentUser {
  id: string;
  email: string;
  display_name: string;
  is_active: boolean;
  must_change_password: boolean;
  roles: Role[];
}

export interface AdminUser {
  id: string;
  email: string;
  display_name: string;
  is_active: boolean;
  must_change_password: boolean;
  last_login_at: string | null;
  created_at: string;
  role_keys: string[];
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Currency {
  id: string;
  code: string;
  name: string;
  symbol: string | null;
  minor_units: number;
  is_active: boolean;
}

export interface CountryPack {
  id: string;
  country_code: string;
  name: string;
  locale: string;
  timezone: string;
  default_currency_id: string;
  area_unit: string;
  fiscal_year_start_month: number;
  is_active: boolean;
}

export interface TaxRule {
  id: string;
  country_pack_id: string;
  tax_code: string;
  label: string;
  applies_to: string;
  calculation_basis: string;
  /** An explicit fraction of one: "0.160000" is 16 per cent. */
  rate_fraction: string;
  valid_from: string;
  valid_to: string | null;
  is_active: boolean;
}

export interface ReferenceValue {
  id: string;
  country_pack_id: string | null;
  category: string;
  code: string;
  label: string;
  description: string | null;
  sort_order: number;
  is_active: boolean;
}

export interface ApprovalThresholds {
  country_pack_id: string;
  discount_review_rate_fraction: string | null;
  discount_review_amount: string | null;
  pricing_requires_finance_approval: boolean;
  pricing_requires_commercial_approval: boolean;
  minimum_margin_rate_fraction: string | null;
  custom_plan_min_down_payment_rate_fraction: string | null;
  custom_plan_max_duration_months: number | null;
  custom_plan_max_post_handover_rate_fraction: string | null;
  custom_plan_max_npv_cost_rate_fraction: string | null;
  receipt_reversal_requires_dual_control: boolean;
  refund_requires_dual_control: boolean;
  construction_variation_review_amount: string | null;
  forecast_reset_variance_rate_fraction: string | null;
}

export interface AuditEvent {
  id: string;
  occurred_at: string;
  actor_user_id: string | null;
  actor_display_name: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  reason: string | null;
  source: string;
  correlation_id: string;
  before_data: Record<string, unknown> | null;
  after_data: Record<string, unknown> | null;
}

// --------------------------------------------------------------------------
// Projects, land, planning, permits and documents (PR-MVP-02)
// --------------------------------------------------------------------------

export interface ProjectSummary {
  id: string;
  code: string;
  name: string;
  developer_entity: string;
  country_pack_id: string;
  city: string | null;
  location: string | null;
  latitude: string | null;
  longitude: string | null;
  project_type_code: string | null;
  status: string;
  base_currency_id: string;
  reporting_currency_id: string;
  fiscal_year_start_month: number;
  planned_start: string | null;
  planned_completion: string | null;
  project_manager_user_id: string | null;
  created_at: string;
  updated_at: string;
  parcel_count: number;
  permit_count: number;
  blocking_permit_count: number;
  critical_path_permit_count: number;
  overdue_permit_count: number;
}

export interface ProjectDetail extends ProjectSummary {
  country_code: string | null;
  base_currency_id: string;
  reporting_currency_id: string;
  base_currency_code: string | null;
  reporting_currency_code: string | null;
  project_manager_display_name: string | null;
  planned_duration_days: number | null;
}

export interface ProjectAccess {
  id: string;
  project_id: string;
  user_id: string;
  email: string;
  display_name: string;
  role_keys: string[];
  is_active: boolean;
  phase_scope: string;
  granted_at: string;
  revoked_at: string | null;
}

export interface LandParcel {
  id: string;
  project_id: string;
  plot_number: string;
  land_area: string;
  area_unit: string;
  title_deed_number: string | null;
  cadastral_reference: string | null;
  ownership_type_code: string | null;
  ownership_share_fraction: string | null;
  acquisition_date: string | null;
  seller: string | null;
  title_status_code: string | null;
  zoning_class_code: string | null;
  frontage: string | null;
  road_access: string | null;
  topography: string | null;
  geotechnical_status: string | null;
  contamination_status: string | null;
  flood_drainage_status: string | null;
  archaeology_heritage_status: string | null;
  power_available: boolean | null;
  water_available: boolean | null;
  sewer_available: boolean | null;
  stormwater_available: boolean | null;
  telecom_available: boolean | null;
  utility_notes: string | null;
  easements: string | null;
  encroachments: string | null;
  constraints_notes: string | null;
  is_active: boolean;
  /** Null when the caller is not cleared to see development cost. */
  purchase_price: string | null;
  acquisition_fees: string | null;
  financials_visible: boolean;
  base_currency_code: string | null;
}

export interface PlanningControl {
  id: string;
  project_id: string;
  parcel_id: string;
  permitted_uses: string | null;
  site_coverage_rate_fraction: string | null;
  far_ratio: string | null;
  maximum_gfa: string | null;
  maximum_floors: number | null;
  maximum_height: string | null;
  front_setback: string | null;
  side_setback: string | null;
  rear_setback: string | null;
  parking_requirement: string | null;
  minimum_plot_area: string | null;
  minimum_frontage: string | null;
  density: string | null;
  exclusions: string | null;
  variance_required: boolean;
  variance_notes: string | null;
}

export interface Permit {
  id: string;
  project_id: string;
  parcel_id: string | null;
  permit_code: string;
  permit_type_code: string;
  authority: string;
  authority_reference: string | null;
  prerequisite_permit_id: string | null;
  owner_user_id: string | null;
  consultant: string | null;
  status: string;
  status_effective_date: string;
  planned_submission_date: string | null;
  forecast_submission_date: string | null;
  actual_submission_date: string | null;
  accepted_for_review_date: string | null;
  comments_received_date: string | null;
  resubmission_date: string | null;
  planned_issue_date: string | null;
  forecast_issue_date: string | null;
  issue_date: string | null;
  expiry_date: string | null;
  renewal_date: string | null;
  statutory_sla_days: number | null;
  conditions: string | null;
  is_blocking: boolean;
  is_critical_path: boolean;
  next_action: string | null;
  escalation_owner_user_id: string | null;
  notes: string | null;
  /** Derived by the backend at read time; never stored. */
  days_in_stage: number;
  sla_days_remaining: number | null;
  sla_overdue: boolean;
  submission_variance_days: number | null;
  issue_variance_days: number | null;
  prerequisite_satisfied: boolean;
  expired_flag: boolean;
  fee_amount: string | null;
  financials_visible: boolean;
  base_currency_code: string | null;
}

export interface PermitRegister {
  permits: Permit[];
  total: number;
  blocking_count: number;
  critical_path_count: number;
  sla_overdue_count: number;
}

export interface PermitStatusEvent {
  id: string;
  permit_id: string;
  from_status: string;
  to_status: string;
  effective_date: string;
  reason: string | null;
  notes: string | null;
  changed_by_user_id: string;
  changed_at: string;
}

export interface DocumentReference {
  id: string;
  project_id: string;
  parcel_id: string | null;
  permit_id: string | null;
  title: string;
  document_type_code: string;
  reference_number: string | null;
  external_url: string;
  notes: string | null;
  is_active: boolean;
}

// --------------------------------------------------------------------------- //
// Inventory (PR-MVP-03)
// --------------------------------------------------------------------------- //

/** Amounts and measures arrive as strings: a JSON number is a float. */
export type Phase = {
  id: string;
  project_id: string;
  code: string;
  name: string;
  sequence: number;
  status: string;
  planned_start: string | null;
  planned_completion: string | null;
  notes: string | null;
  is_active: boolean;
};

export type Building = {
  id: string;
  project_id: string;
  phase_id: string;
  code: string;
  name: string;
  zone: string | null;
  block: string | null;
  entrance_wing: string | null;
  sequence: number;
  is_active: boolean;
};

export type Floor = {
  id: string;
  project_id: string;
  building_id: string;
  code: string;
  label: string;
  level_number: number | null;
  sequence: number;
  is_active: boolean;
};

export type AreaLine = {
  area_type_id: string;
  code: string;
  label: string;
  area_role: string;
  unit_of_measure: string;
  raw_area: string;
  weight_factor: string;
  weighted_area: string;
};

export type UnitSummary = {
  id: string;
  project_id: string;
  unit_reference: string;
  unit_number: string;
  floor_id: string;
  floor_code: string | null;
  building_id: string | null;
  building_code: string | null;
  phase_id: string | null;
  phase_code: string | null;
  asset_class: string;
  unit_type_code: string | null;
  bedrooms: number | null;
  internal_area: string | null;
  weighted_saleable_area: string | null;
  weighted_saleable_area_unit: string | null;
  parking_count: number;
  storage_count: number;
  commercial_status: string;
  legal_status: string;
  collection_status: string;
  delivery_status: string;
  is_complete: boolean;
  completeness_percent: number;
  release_eligible: boolean;
  release_blockers: string[];
  is_active: boolean;
};

export type Unit = UnitSummary & {
  bathrooms: number | null;
  has_maid_room: boolean;
  is_duplex: boolean;
  is_penthouse: boolean;
  furnishing_specification_code: string | null;
  floor_band_code: string | null;
  orientation_code: string | null;
  view_class_code: string | null;
  is_corner: boolean;
  pool_access: boolean;
  accessibility_code: string | null;
  garden_class_code: string | null;
  plot_coverage_fraction: string | null;
  sequence: number;
  drawings_approved: boolean;
  legal_sale_eligible: boolean;
  pricing_approved: boolean;
  release_date: string | null;
  release_batch: string | null;
  block_reason: string | null;
  missing_requirements: string[];
  area_lines: AreaLine[];
  area_schedule_id: string | null;
  area_revision_code: string | null;
};

export type UnitRegister = {
  units: UnitSummary[];
  total: number;
  available_count: number;
  held_count: number;
  unreleased_count: number;
};

export type UnitStatusEvent = {
  id: string;
  unit_id: string;
  dimension: string;
  from_status: string;
  to_status: string;
  effective_date: string;
  reason: string | null;
  notes: string | null;
  changed_at: string;
};

export type SubAsset = {
  id: string;
  project_id: string;
  asset_reference: string;
  asset_type: string;
  subtype_code: string | null;
  floor_id: string | null;
  linked_unit_id: string | null;
  area: string | null;
  transfer_mode: string;
  notes: string | null;
  is_active: boolean;
};

export type AreaType = {
  id: string;
  project_id: string;
  code: string;
  label: string;
  area_role: string;
  unit_of_measure: string;
  weight_factor: string;
  required_for_release: boolean;
  sort_order: number;
  is_active: boolean;
};

export type AreaSchedule = {
  id: string;
  project_id: string;
  unit_id: string;
  revision_code: string;
  status: string;
  measurement_standard: string | null;
  plan_revision: string | null;
  source: string | null;
  measured_date: string | null;
  reconciled: boolean;
  notes: string | null;
  lines: AreaLine[];
  weighted_saleable_area: string | null;
  weighted_saleable_area_unit: string | null;
};

export type PhaseAccess = {
  id: string;
  project_id: string;
  user_id: string;
  phase_id: string;
  phase_code: string | null;
  phase_name: string | null;
  is_active: boolean;
  granted_at: string;
  revoked_at: string | null;
};

export type CustomFieldOption = {
  id: string;
  code: string;
  label: string;
  sort_order: number;
  is_active: boolean;
};

export type CustomValue = {
  definition_id: string;
  field_key: string;
  display_label: string;
  data_type: string;
  unit_of_measure: string | null;
  help_text: string | null;
  required: boolean;
  required_for_release: boolean;
  is_editable: boolean;
  options: CustomFieldOption[];
  value: string | number | boolean | null;
};

export type ImportIssue = {
  row: number;
  column: string | null;
  severity: "error" | "warning";
  message: string;
};

export type ImportReport = {
  mode: string;
  applied: boolean;
  total_rows: number;
  create_count: number;
  update_count: number;
  valid_rows: number;
  invalid_rows: number;
  error_count: number;
  warning_count: number;
  issues: ImportIssue[];
  issues_truncated: boolean;
};

/* -------------------------------------------------------------------------- *
 * Pricing (PR-MVP-04)
 *
 * Every monetary figure arrives as a string. A JSON number is a float, and a
 * float is not an acceptable carrier for a price — the browser formats these,
 * it never computes with them.
 * -------------------------------------------------------------------------- */

export type PricingStatus = "draft" | "submitted" | "approved" | "active" | "superseded";

export interface PricingConfiguration {
  id: string;
  project_id: string;
  version_number: number;
  name: string;
  status: PricingStatus;
  pricing_currency_id: string;
  base_internal_rate: string;
  premium_stacking_default: string;
  maximum_premium_fraction: string | null;
  offer_valid_days: number | null;
  price_lock_days: number | null;
  reservation_expiry_days: number | null;
  default_payment_plan_adjustment_fraction: string | null;
  tax_treatment_code: string;
  valid_from: string;
  valid_to: string | null;
  submitted_at: string | null;
  approved_at: string | null;
  activated_at: string | null;
  superseded_at: string | null;
  change_reason: string | null;
}

export interface PricingAreaRule {
  id: string;
  pricing_configuration_id: string;
  area_type_id: string;
  pricing_method: string;
  rate_per_area: string | null;
  internal_rate_factor: string | null;
  sort_order: number;
  is_active: boolean;
}

export interface PricingPremiumRule {
  id: string;
  pricing_configuration_id: string;
  code: string;
  label: string;
  source_kind: string;
  match_code: string | null;
  method: string;
  percentage_fraction: string | null;
  amount: string | null;
  eligible_base: string;
  stacking_method: string | null;
  sequence: number;
  is_active: boolean;
}

export interface PricingEscalationRule {
  id: string;
  pricing_configuration_id: string;
  code: string;
  label: string;
  trigger_type: string;
  scope_type: string;
  phase_id: string | null;
  unit_type_code: string | null;
  threshold_date: string | null;
  threshold_fraction: string | null;
  adjustment_method: string;
  adjustment_percentage_fraction: string | null;
  adjustment_amount: string | null;
  cumulative: boolean;
  sequence: number;
  is_active: boolean;
}

export interface EscalationActivation {
  id: string;
  pricing_escalation_rule_id: string;
  effective_date: string;
  evidence_value: string | null;
  evidence_date: string | null;
  evidence_reference: string;
  reason: string;
  approved_at: string;
  is_active: boolean;
  reversal_reason: string | null;
}

export interface MarketBenchmark {
  id: string;
  project_id: string;
  phase_id: string | null;
  unit_type_code: string | null;
  area_basis: string;
  benchmark_price_per_area: string;
  currency_id: string;
  comparison_date: string;
  source_name: string;
  source_reference: string | null;
  tolerance_fraction: string;
  notes: string | null;
  is_active: boolean;
}

export interface PriceComponent {
  id: string;
  sequence: number;
  component_type: string;
  code: string;
  label: string;
  quantity: string | null;
  unit_of_measure: string | null;
  basis_amount: string | null;
  rate: string | null;
  factor: string | null;
  calculated_amount: string;
  override_amount: string | null;
  final_amount: string;
  override_reason: string | null;
}

export interface PriceVersion {
  id: string;
  project_id: string;
  unit_id: string;
  version_number: number;
  pricing_configuration_id: string;
  unit_area_schedule_id: string;
  status: PricingStatus;
  currency_id: string;
  valid_from: string;
  valid_to: string | null;
  base_area_value: string;
  scope_adjustment_total: string;
  premium_total: string;
  premium_cap_adjustment: string;
  escalation_total: string;
  paid_upgrade_total: string;
  reference_price_ex_tax: string;
  internal_area_snapshot: string | null;
  weighted_area_snapshot: string | null;
  price_per_internal_area: string | null;
  price_per_weighted_area: string | null;
  market_benchmark_price_snapshot: string | null;
  market_deviation_fraction: string | null;
  market_flag: string;
  change_reason: string | null;
  created_at: string;
}

export interface PriceVersionDetail extends PriceVersion {
  components: PriceComponent[];
  basis_snapshot_json: Record<string, unknown>;
}

export interface UnitPricing {
  unit_id: string;
  unit_reference: string;
  unit_type_code: string | null;
  pricing_approved: boolean;
  repricing_required: boolean;
  has_active_configuration: boolean;
  active_price: PriceVersionDetail | null;
  history: PriceVersion[];
}

export interface PriceRegisterRow {
  unit_id: string;
  unit_reference: string;
  unit_number: string;
  unit_type_code: string | null;
  commercial_status: string;
  pricing_approved: boolean;
  repricing_required: boolean;
  version_id: string | null;
  version_number: number | null;
  status: string | null;
  reference_price_ex_tax: string | null;
  internal_area_snapshot: string | null;
  weighted_area_snapshot: string | null;
  price_per_internal_area: string | null;
  price_per_weighted_area: string | null;
  market_flag: string | null;
  market_deviation_fraction: string | null;
}

export interface PriceRegister {
  rows: PriceRegisterRow[];
  total: number;
  priced: number;
  not_priced: number;
  repricing_required: number;
}

export interface PricingOverview {
  configuration: PricingConfiguration | null;
  currency_id: string | null;
  base_internal_rate: string | null;
  active_escalations: number;
  units_total: number;
  units_priced: number;
  units_not_priced: number;
  units_repricing_required: number;
}

export interface QuoteTaxLine {
  tax_code: string;
  label: string;
  rate_fraction: string;
  calculation_basis: string;
  amount: string;
}

export interface QuotePreview {
  unit_id: string;
  unit_reference: string;
  version_number: number;
  approved_reference_price_ex_tax: string;
  paid_upgrade_price: string;
  payment_plan_price_adjustment: string;
  payment_plan_adjustment_fraction: string;
  gross_quoted_price_ex_tax: string;
  cash_discount: string;
  seller_credit: string;
  net_contract_price_ex_tax: string;
  seller_package_cost: string;
  upgrade_allowance_cost: string;
  commission_support: string;
  financing_subsidy: string;
  extended_terms_npv_cost: string;
  seller_cost_total: string;
  effective_net_revenue_preview: string;
  tax_status: string;
  tax_treatment_code: string;
  taxes: QuoteTaxLine[];
  tax_total: string;
  buyer_paid_fees: string;
  total_buyer_payable_preview: string;
  offer_valid_days: number | null;
  price_lock_days: number | null;
  reservation_expiry_days: number | null;
  approval_required: boolean;
  approval_reason: string | null;
  threshold_rate_fraction: string | null;
  threshold_amount: string | null;
  required_role: string | null;
}
