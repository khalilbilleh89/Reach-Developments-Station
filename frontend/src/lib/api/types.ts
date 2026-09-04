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

export type PricingStatus =
  | "draft"
  | "submitted"
  | "approved"
  | "active"
  | "superseded";

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
  currency_id: string | null;
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

/* --------------------------------------------------------------------------
 * Sales and legal (PR-MVP-05)
 *
 * Two shapes for a buyer and two for a party, because the API decides what a
 * caller may see before it serialises anything: a reader who may not see a
 * passport number receives a response on which the field does not exist. The
 * optional properties below are that decision arriving in the browser, not a
 * hint that the browser should hide something.
 * ------------------------------------------------------------------------ */

export interface SalesPolicy {
  project_id: string;
  handover_requires_collection_clearance: boolean;
  handover_requires_legal_clearance: boolean;
  handover_requires_delivery_clearance: boolean;
  handover_requires_title_transfer: boolean;
  title_transfer_requires_collection_clearance: boolean;
  reservation_requires_deposit_confirmation: boolean;
}

export interface SalesClient {
  id: string;
  project_id: string;
  client_number: string;
  display_name: string;
  kyc_status: string;
  preferred_language_code: string | null;
  owner_advisor_user_id: string | null;
  is_active: boolean;
  created_at: string;
  /** Present only for the roles whose work needs it. */
  email?: string | null;
  phone?: string | null;
  address?: string | null;
  privacy_consent_at?: string | null;
  privacy_consent_reference?: string | null;
  notes?: string | null;
}

export interface ClientParty {
  id: string;
  client_id: string;
  party_role: string;
  name_as_identification: string;
  nationality_code: string | null;
  residency_code: string | null;
  share_fraction: string;
  is_primary: boolean;
  is_active: boolean;
  /** Present only for the roles whose work needs it. */
  tax_id?: string | null;
  identity_document_type?: string | null;
  identity_document_number?: string | null;
  representative_name?: string | null;
  poa_reference?: string | null;
}

export interface ShareReconciliation {
  total_share_fraction: string;
  reconciled: boolean;
}

export interface ReservationAdjustment {
  id: string;
  reservation_id: string;
  adjustment_type: string;
  treatment: string;
  rate_fraction: string | null;
  amount: string | null;
  reason: string | null;
  requested_by_user_id: string;
  created_at: string;
}

export interface ReservationStatusEvent {
  id: string;
  reservation_id: string;
  from_status: string;
  to_status: string;
  effective_date: string;
  reason: string | null;
  actor_user_id: string;
  created_at: string;
}

export interface Reservation {
  id: string;
  project_id: string;
  reservation_number: string;
  unit_id: string;
  client_id: string;
  unit_price_version_id: string;
  status: string;
  reservation_date: string;
  expires_on: string;
  price_locked_until: string;
  sales_channel_code: string | null;
  sales_branch_code: string | null;
  advisor_user_id: string | null;
  deposit_required_amount: string | null;
  deposit_currency_id: string | null;
  deposit_gate_status: string;
  deposit_confirmation_reference: string | null;
  deposit_confirmed_by_user_id: string | null;
  deposit_confirmed_at: string | null;
  deposit_waiver_reason: string | null;
  currency_id: string;
  reference_price_ex_tax: string;
  paid_upgrade_amount: string;
  payment_plan_adjustment_amount: string;
  gross_quoted_price_ex_tax: string;
  cash_discount_amount: string;
  seller_credit_amount: string;
  net_contract_price_ex_tax: string;
  seller_cost_total: string;
  effective_net_revenue_preview: string;
  tax_total: string;
  buyer_fee_total: string;
  total_buyer_payable: string;
  exception_approval_required: boolean;
  exception_approval_status: string;
  exception_reason: string | null;
  exception_required_role: string | null;
  exception_submitted_by_user_id: string | null;
  exception_submitted_at: string | null;
  exception_approved_by_user_id: string | null;
  exception_approved_at: string | null;
  exception_decision_reason: string | null;
  activated_at: string | null;
  converted_at: string | null;
  closed_at: string | null;
  closure_reason: string | null;
  created_at: string;
}

export interface ReservationDetail {
  reservation: Reservation;
  adjustments: ReservationAdjustment[];
  events: ReservationStatusEvent[];
  quote_snapshot: Record<string, unknown>;
  closure_required: boolean;
}

export interface SaleParty {
  id: string;
  sale_contract_id: string;
  client_party_id: string | null;
  party_role: string;
  name_as_identification: string;
  nationality_code: string | null;
  residency_code: string | null;
  share_fraction: string;
  tax_id?: string | null;
  identity_document_type?: string | null;
  identity_document_number?: string | null;
  representative_name?: string | null;
  poa_reference?: string | null;
}

export interface SaleTaxLine {
  id: string;
  sale_contract_id: string;
  tax_rule_id: string | null;
  tax_code: string;
  label: string;
  rate_fraction: string;
  calculation_basis: string;
  taxable_amount: string;
  tax_amount: string;
  currency_id: string;
  valid_on: string;
}

export interface SaleContract {
  id: string;
  project_id: string;
  sale_number: string;
  spa_number: string | null;
  reservation_id: string;
  unit_id: string;
  client_id: string;
  unit_price_version_id: string;
  currency_id: string;
  contract_date: string;
  status: string;
  reference_price_ex_tax: string;
  gross_quoted_price_ex_tax: string;
  cash_discount_amount: string;
  seller_credit_amount: string;
  net_contract_price_ex_tax: string;
  seller_cost_total: string;
  effective_net_revenue_snapshot: string;
  tax_total: string;
  buyer_fee_total: string;
  total_contract_price: string;
  sales_channel_code: string | null;
  sales_branch_code: string | null;
  advisor_user_id: string | null;
  first_payment_required_amount: string | null;
  first_payment_gate_status: string;
  first_payment_evidence_reference: string | null;
  first_payment_confirmed_by_user_id: string | null;
  first_payment_confirmed_at: string | null;
  first_payment_waiver_reason: string | null;
  submitted_at: string | null;
  submitted_by_user_id: string | null;
  activated_at: string | null;
  activated_by_user_id: string | null;
  cancelled_at: string | null;
  created_at: string;
}

export interface LegalEvent {
  id: string;
  sale_contract_id: string;
  event_type: string;
  event_date: string;
  authority_reference: string | null;
  document_reference: string | null;
  fee_amount: string | null;
  currency_id: string | null;
  notes: string | null;
  reverses_event_id: string | null;
  reversal_reason: string | null;
  entered_by_user_id: string;
  created_at: string;
}

export interface LegalTimeline {
  events: LegalEvent[];
  effective_event_ids: string[];
  legal_status: string;
}

export interface SaleCancellation {
  id: string;
  sale_contract_id: string;
  initiated_by_party: string;
  initiation_date: string;
  notice_date: string | null;
  cure_deadline: string | null;
  reason_code: string | null;
  reason: string;
  status: string;
  termination_date: string | null;
  forfeiture_amount: string | null;
  refund_due_amount: string | null;
  financial_approval_required: boolean;
  financial_approved_by_user_id: string | null;
  financial_approved_at: string | null;
  legal_withdrawal_required: boolean;
  legal_withdrawal_status: string;
  unit_return_date: string | null;
  remarketing_required: boolean;
  created_by_user_id: string;
  created_at: string;
}

export interface HandoverClearance {
  id: string;
  handover_id: string;
  clearance_type: string;
  status: string;
  evidence_reference: string | null;
  reason: string | null;
  cleared_by_user_id: string | null;
  cleared_at: string | null;
  revoked_by_user_id: string | null;
  revoked_at: string | null;
  revocation_reason: string | null;
  created_at: string;
}

export interface HandoverRecord {
  id: string;
  sale_contract_id: string;
  readiness_date: string | null;
  inspection_date: string | null;
  snag_status: string | null;
  snag_notes: string | null;
  client_notice_date: string | null;
  scheduled_handover_date: string | null;
  handover_date: string | null;
  keys_reference: string | null;
  meter_readings_json: Record<string, unknown> | null;
  acceptance_document_reference: string | null;
  notes: string | null;
  status: string;
  created_at: string;
}

export interface HandoverDetail {
  handover: HandoverRecord;
  clearances: HandoverClearance[];
  blockers: string[];
}

export interface SaleDetail {
  sale: SaleContract;
  parties: SaleParty[];
  tax_lines: SaleTaxLine[];
  legal: LegalTimeline;
  cancellation: SaleCancellation | null;
  handover: HandoverDetail | null;
  quote_snapshot: Record<string, unknown>;
}

export interface SalesRegisterRow {
  unit_id: string;
  unit_reference: string;
  unit_number: string;
  commercial_status: string;
  legal_status: string;
  delivery_status: string;
  client_id: string | null;
  client_display_name: string | null;
  reservation_id: string | null;
  reservation_number: string | null;
  reservation_status: string | null;
  reservation_expires_on: string | null;
  closure_required: boolean;
  sale_id: string | null;
  sale_number: string | null;
  spa_number: string | null;
  sale_status: string | null;
  contract_date: string | null;
  currency_id: string | null;
  net_contract_price_ex_tax: string | null;
  cash_discount_amount: string | null;
  total_contract_price: string | null;
  sales_branch_code: string | null;
  advisor_user_id: string | null;
  next_legal_step: string | null;
  handover_status: string | null;
}

export interface SalesRegisterTotals {
  units: number;
  available: number;
  reserved: number;
  contract_pending: number;
  contracted: number;
  returned: number;
  active_reservations: number;
  active_contracts: number;
  open_cancellations: number;
  contracted_value: string | null;
  currency_id: string | null;
  mixed_currency: boolean;
}

export interface SalesRegister {
  rows: SalesRegisterRow[];
  totals: SalesRegisterTotals;
  total: number;
}

// --------------------------------------------------------------------------- //
// Payment plans (PR-MVP-06)
// --------------------------------------------------------------------------- //

/**
 * A sale's payment schedule.
 *
 * Nothing here says what has been collected. An instalment is what the buyer
 * contracted to pay and when it falls due; whether money arrived is PR-MVP-07's
 * to state, and there is deliberately no field on any of these types that could
 * be mistaken for it.
 */
export interface PaymentPlan {
  id: string;
  project_id: string;
  sale_contract_id: string;
  plan_number: string;
  name: string;
  notes: string | null;
  /**
   * When the first receipt against this plan was confirmed, or null.
   *
   * Once it is set, the ordinary activation of a replacement schedule refuses:
   * the allocations already made point at the instalments being replaced. The
   * builder reads this to say so rather than showing a dead button.
   */
  collections_started_at: string | null;
  created_by_user_id: string;
  created_at: string;
  updated_at: string;
}

export type PlanVersionStatus =
  | "draft"
  | "submitted"
  | "approved"
  | "active"
  | "superseded"
  | "rejected";

export type TriggerType =
  | "fixed_date"
  | "days_after_spa"
  | "recurring_monthly"
  | "recurring_quarterly"
  | "construction_milestone"
  | "handover"
  | "title_transfer"
  | "manual_approved_event";

/** Where an instalment stands against its own trigger — never against payment. */
export type TriggerStatus = "scheduled" | "awaiting_trigger" | "triggered";

export interface PaymentPlanVersion {
  id: string;
  project_id: string;
  payment_plan_id: string;
  version_number: number;
  status: PlanVersionStatus;
  effective_date: string;
  currency_id: string;
  contract_value_covered: string;
  tax_total_snapshot: string;
  buyer_fee_total_snapshot: string;
  total_buyer_payable_snapshot: string;
  allocation_mode: "percentage" | "amount";
  charge_allocation_mode: "pro_rata" | "manual";
  reservation_treatment: "included_in_schedule" | "reference_only";
  origin_type: "custom" | "copied_plan";
  source_version_id: string | null;
  change_reason: string | null;
  created_by_user_id: string;
  created_at: string;
  submitted_by_user_id: string | null;
  submitted_at: string | null;
  approved_by_user_id: string | null;
  approved_at: string | null;
  rejected_by_user_id: string | null;
  rejected_at: string | null;
  rejection_reason: string | null;
  activated_by_user_id: string | null;
  activated_at: string | null;
  superseded_at: string | null;
}

export interface InstallmentTriggerEvent {
  id: string;
  installment_id: string;
  event_date: string;
  evidence_reference: string;
  reason: string;
  status: "submitted" | "approved" | "reversed";
  submitted_by_user_id: string;
  submitted_at: string;
  approved_by_user_id: string | null;
  approved_at: string | null;
  reversed_by_user_id: string | null;
  reversed_at: string | null;
  reversal_reason: string | null;
}

export interface PlanInstallment {
  id: string;
  payment_plan_version_id: string;
  sequence: number;
  label: string;
  trigger_type: TriggerType;
  trigger_reference: string | null;
  offset_days: number | null;
  recurrence_index: number | null;
  /** What the contract says. Set for date-based triggers. */
  contractual_due_date: string | null;
  /** What somebody expects for a contingent trigger. Never makes it due. */
  forecast_due_date: string | null;
  /** Set only once the trigger has genuinely occurred. */
  actual_due_date: string | null;
  grace_days: number;
  principal_amount: string;
  principal_fraction: string;
  tax_amount: string;
  fee_amount: string;
  total_scheduled_amount: string;
  trigger_status: TriggerStatus;
  owner_user_id: string | null;
  /**
   * Every attestation ever made about this instalment, newest first. Carried on
   * the row so an approver opening a hundred-row schedule makes one request,
   * not a hundred.
   */
  trigger_events: InstallmentTriggerEvent[];
}

/** Server-derived. The browser renders this and never sums a column itself. */
export interface PlanReconciliation {
  installment_count: number;
  scheduled_principal_total: string;
  contract_value_covered: string;
  principal_delta: string;
  scheduled_fraction_total: string;
  fraction_delta: string;
  scheduled_tax_total: string;
  tax_total_snapshot: string;
  tax_delta: string;
  scheduled_fee_total: string;
  buyer_fee_total_snapshot: string;
  fee_delta: string;
  scheduled_buyer_total: string;
  total_buyer_payable_snapshot: string;
  buyer_total_delta: string;
  is_reconciled: boolean;
  /** Said in words: which figure is wrong, and by how much. */
  blocking_reasons: string[];
}

export interface PlanVersionDetail {
  version: PaymentPlanVersion;
  installments: PlanInstallment[];
  reconciliation: PlanReconciliation;
  /**
   * The soonest scheduled and forecast dates still to come on this version,
   * derived on the server. Every surface that summarises a schedule reads
   * these rather than sorting the dates itself, so none of them can present a
   * date already past as what falls due next.
   */
  next_scheduled_date: string | null;
  next_forecast_date: string | null;
}

export interface PaymentPlanDetail {
  plan: PaymentPlan;
  sale_id: string;
  sale_number: string;
  spa_number: string | null;
  sale_status: string;
  unit_id: string;
  unit_reference: string;
  client_display_name: string;
  currency_id: string;
  /**
   * The version being worked on: the one in preparation if there is one,
   * otherwise the standing one. This is the editing workspace, and it is not
   * a claim about what governs the sale.
   */
  current: PlanVersionDetail | null;
  /**
   * The version actually governing the sale, or null before the first
   * activation. A revision can be in preparation for weeks while this
   * schedule keeps falling due, so anything that reports what the buyer owes
   * reads this one.
   */
  active: PlanVersionDetail | null;
  active_version_id: string | null;
  versions: PaymentPlanVersion[];
}

export interface PlanRegisterRow {
  plan_id: string;
  plan_number: string;
  sale_id: string;
  sale_number: string;
  spa_number: string | null;
  unit_id: string;
  unit_reference: string;
  client_display_name: string;
  version_id: string | null;
  version_number: number | null;
  version_status: PlanVersionStatus | null;
  effective_date: string | null;
  currency_id: string;
  contract_value_covered: string;
  installment_count: number;
  scheduled_principal_total: string | null;
  is_reconciled: boolean;
  /**
   * The soonest scheduled date still to come, and the soonest forecast date
   * still to come. Both look forward only: PR-MVP-06 cannot say whether a date
   * already past was paid, so surfacing one would read as arrears.
   */
  next_scheduled_date: string | null;
  next_forecast_date: string | null;
  awaiting_trigger_count: number;
  approved_by_user_id: string | null;
  /**
   * The best settled version of this plan — standing, else approved, else the
   * most recent superseded one. Named separately because opening a draft
   * revision must not withdraw an agreed schedule from the plans worth
   * copying.
   */
  copy_source_version_id: string | null;
  copy_source_version_number: number | null;
  copy_source_status: PlanVersionStatus | null;
  /**
   * A revision being prepared alongside the version this row describes. Named,
   * not costed: it governs nothing, so it contributes no figure to the row and
   * none of the project's operational counts.
   */
  revision_version_id: string | null;
  revision_version_number: number | null;
  revision_status: PlanVersionStatus | null;
}

export interface PlanRegister {
  rows: PlanRegisterRow[];
  total: number;
}

export interface SeriesRow {
  recurrence_index: number;
  label: string;
  due_date: string;
}

export interface SeriesPreview {
  rows: SeriesRow[];
}

export interface TriggerRefreshResult {
  triggered: PlanInstallment[];
  still_awaiting: PlanInstallment[];
}

/* --------------------------------------------------------------------------
 * Collections — PR-MVP-07
 *
 * Every money field is a string, because the API sends Decimals as JSON
 * strings and a JavaScript number cannot hold a buyer's balance without
 * eventually losing a cent. Nothing here is computed in the browser:
 * `outstanding`, `overdue_days`, `bucket`, `unapplied_amount` and
 * `derived_collection_status` all arrive already decided.
 * ----------------------------------------------------------------------- */

export type ReceiptStatus = "recorded" | "confirmed" | "reversed";
export type AllocationStatus = "active" | "superseded" | "reversed";
export type DisputeStatus = "open" | "resolved" | "withdrawn";
export type WaiverType = "collection_hold" | "grace_extension";
export type WaiverStatus = "submitted" | "approved" | "rejected" | "revoked";
export type RestructureStatus = "open" | "applied" | "abandoned";
export type RefundStatus = "recorded" | "confirmed" | "reversed";

export type AgingBucket =
  | "awaiting_trigger"
  | "current"
  | "1_30"
  | "31_60"
  | "61_90"
  | "91_plus";

export type InstallmentCollectionStatus =
  | "awaiting_trigger"
  | "scheduled"
  | "due"
  | "partially_paid"
  | "paid"
  | "overdue"
  | "disputed"
  | "cancelled";

export type CollectionActionType =
  | "call"
  | "email"
  | "meeting"
  | "reminder"
  | "formal_notice"
  | "promise_to_pay"
  | "legal_referral"
  | "follow_up"
  | "other";

export interface ReceiptAllocation {
  id: string;
  receipt_id: string;
  installment_id: string;
  payment_plan_version_id: string;
  amount: string;
  status: AllocationStatus;
  created_at: string;
  reversal_reason: string | null;
  superseded_by_restructure_id: string | null;
}

export interface Receipt {
  id: string;
  sale_contract_id: string;
  receipt_number: string;
  currency_id: string;
  amount: string;
  receipt_date: string;
  status: ReceiptStatus;
  bank_reference: string | null;
  external_reference: string | null;
  notes: string | null;
  recorded_at: string;
  recorded_by_user_id: string;
  confirmed_at: string | null;
  confirmed_by_user_id: string | null;
  reversed_at: string | null;
  reversal_reason: string | null;
  /** `amount` less every active allocation. Derived server-side. */
  unapplied_amount: string;
  /** Only a confirmed receipt is cash. A recorded one moves no balance. */
  counts_as_cash: boolean;
  allocations: ReceiptAllocation[];
}

export interface SuggestedAllocation {
  installment_id: string;
  sequence: number;
  label: string;
  due_date: string | null;
  outstanding: string;
  amount: string;
}

export interface CollectionInstallmentRow {
  installment_id: string;
  sequence: number;
  label: string;
  trigger_type: string;
  trigger_status: string;
  due_date: string | null;
  grace_days: number;
  scheduled: string;
  paid: string;
  outstanding: string;
  overdue_days: number;
  bucket: AgingBucket;
  status: InstallmentCollectionStatus;
  /** A flag, never a replacement for the numbers beside it. */
  is_disputed: boolean;
  has_active_waiver: boolean;
  waived_until: string | null;
  owner_user_id: string | null;
}

export interface CollectionSaleSummary {
  sale_id: string;
  currency_id: string;
  as_of: string;
  active_payment_plan_id: string | null;
  active_payment_plan_version_id: string | null;
  scheduled_total: string;
  confirmed_receipts_total: string;
  allocated_total: string;
  unapplied_cash: string;
  outstanding_total: string;
  due_total: string;
  overdue_total: string;
  oldest_overdue_days: number;
  installments_total: number;
  installments_paid: number;
  installments_partial: number;
  installments_overdue: number;
  installments_awaiting_trigger: number;
  open_disputes: number;
  active_waivers: number;
  next_action_date: string | null;
  derived_collection_status: string;
  /** Due and paid, side by side. Never netted into one figure. */
  refund_due_total: string;
  refund_confirmed_total: string;
  refund_outstanding: string;
  collection_clearance_status: string | null;
  clearance_blockers: string[];
  installments: CollectionInstallmentRow[];
}

export interface CollectionRegisterRow {
  sale_id: string;
  sale_number: string;
  spa_number: string | null;
  unit_id: string;
  unit_number: string;
  client_display_name: string;
  currency_id: string;
  summary: CollectionSaleSummary;
}

export interface AgingRow {
  sale_id: string;
  sale_number: string;
  unit_number: string;
  client_display_name: string;
  currency_id: string;
  installment: CollectionInstallmentRow;
}

/** Every money figure for one denomination. Nothing here crosses currencies. */
export interface CollectionCurrencyTotals {
  currency_id: string;
  accounts: number;
  outstanding_total: string;
  due_total: string;
  overdue_total: string;
  unapplied_cash: string;
  /** Lifetime, and named so: never subtract it from an outstanding balance. */
  confirmed_receipts_total: string;
  buckets: Record<string, string>;
}

/**
 * The project strip.
 *
 * There is deliberately no project-wide money field. A project can sell in more
 * than one currency, and one "outstanding" figure for such a project could only
 * be produced by adding unlike numbers — wrong by the exchange rate, on a strip
 * an executive reads at a glance. The counts stay project-wide, because a count
 * of accounts is not money.
 */
export interface CollectionProjectSummary {
  as_of: string;
  accounts: number;
  accounts_overdue: number;
  accounts_disputed: number;
  accounts_cleared: number;
  currencies: CollectionCurrencyTotals[];
}

export interface CollectionAction {
  id: string;
  sale_contract_id: string;
  installment_id: string | null;
  action_type: CollectionActionType;
  action_at: string;
  notes: string;
  /** A promise is not cash and is never added to a collected total. */
  promised_amount: string | null;
  promised_date: string | null;
  next_action_date: string | null;
  created_at: string;
  created_by_user_id: string;
}

export interface CollectionDispute {
  id: string;
  sale_contract_id: string;
  installment_id: string;
  status: DisputeStatus;
  reason: string;
  opened_at: string;
  opened_by_user_id: string;
  resolved_at: string | null;
  resolved_by_user_id: string | null;
  resolution: string | null;
}

export interface CollectionWaiver {
  id: string;
  sale_contract_id: string;
  installment_id: string;
  waiver_type: WaiverType;
  waived_until: string;
  reason: string;
  status: WaiverStatus;
  submitted_at: string;
  submitted_by_user_id: string;
  approved_at: string | null;
  approved_by_user_id: string | null;
  rejected_at: string | null;
  rejection_reason: string | null;
  revoked_at: string | null;
  revocation_reason: string | null;
}

export interface CollectionRestructure {
  id: string;
  sale_contract_id: string;
  payment_plan_id: string;
  restructure_number: string;
  source_version_id: string;
  replacement_version_id: string;
  status: RestructureStatus;
  reason: string;
  requested_at: string;
  requested_by_user_id: string;
  applied_at: string | null;
  applied_by_user_id: string | null;
  abandoned_at: string | null;
  abandonment_reason: string | null;
}

export interface CarryLine {
  receipt_id: string;
  installment_id: string;
  amount: string;
}

export interface RestructurePreview {
  restructure_id: string;
  source_version_id: string;
  replacement_version_id: string;
  replacement_status: string;
  ready_to_apply: boolean;
  blockers: string[];
  /** Must equal the cash currently allocated. Shown so conservation is visible. */
  carried_total: string;
  unapplied_total: string;
  confirmed_receipts_total: string;
  superseding: number;
  lines: CarryLine[];
}

export interface RestructureApplyResult {
  restructure: CollectionRestructure;
  summary: CollectionSaleSummary;
}

export interface CollectionRefund {
  id: string;
  sale_contract_id: string;
  cancellation_id: string;
  refund_number: string;
  currency_id: string;
  amount: string;
  refund_date: string;
  status: RefundStatus;
  bank_reference: string | null;
  notes: string | null;
  recorded_at: string;
  recorded_by_user_id: string;
  confirmed_at: string | null;
  confirmed_by_user_id: string | null;
  reversed_at: string | null;
  reversal_reason: string | null;
}

export interface CollectionClearance {
  sale_id: string;
  status: string | null;
  blockers: string[];
}

/* ------------------------------------------------------------------------- */
/* Unit economics (PR-MVP-08)                                                 */
/* ------------------------------------------------------------------------- */

export type AllocationVersionStatus =
  | "draft"
  | "submitted"
  | "approved"
  | "active"
  | "superseded"
  | "rejected";

export type FinanceTreatment = "allocated" | "excluded";

export type PoolCategory = "land" | "hard" | "soft" | "finance";

export type PoolSourceKind = "project_land" | "manual";

export type PoolScope = "project" | "phase" | "building";

export type AllocationMethod =
  | "weighted_area"
  | "raw_area"
  | "unit_count"
  | "revenue_value"
  | "custom_driver";

export type UnitCostType =
  | "unit_upgrade"
  | "finishes"
  | "furniture_appliance"
  | "legal_registry_support"
  | "rectification"
  | "other_direct"
  | "marketing"
  | "sales_commission"
  | "branch_commission"
  | "payment_fee"
  | "seller_paid_legal"
  | "other_selling";

export type UnitCostBasis = "forecast" | "actual";

export type UnitCostStatus = "active" | "reversed";

/**
 * Why a unit's profit could not be calculated, or `ready` when it could.
 *
 * Never absent and never silently zero: a fabricated margin is worse than a
 * missing one, because nobody checks a number that looks finished.
 */
export type ProfitabilityStatus =
  | "ready"
  | "missing_revenue"
  | "missing_cost_basis"
  | "unreconciled_cost_basis"
  | "currency_mismatch";

export type RevenueSource = "approved_price" | "sale_contract";

/** Which side of the sold line a unit is analysed on. */
export type EconomicBasis = "forecast" | "sold";

export interface AllocationVersion {
  id: string;
  project_id: string;
  version_number: number;
  currency_id: string;
  status: AllocationVersionStatus;
  finance_treatment: FinanceTreatment;
  effective_from: string;
  effective_to: string | null;
  change_reason: string;
  source_version_id: string | null;
  calculated_at: string | null;
  created_at: string;
  created_by_user_id: string;
  submitted_at: string | null;
  submitted_by_user_id: string | null;
  approved_at: string | null;
  approved_by_user_id: string | null;
  rejected_at: string | null;
  rejected_by_user_id: string | null;
  rejection_reason: string | null;
  activated_at: string | null;
  activated_by_user_id: string | null;
  superseded_at: string | null;
}

export interface CostPool {
  id: string;
  allocation_version_id: string;
  pool_number: string;
  name: string;
  category: PoolCategory;
  source_kind: PoolSourceKind;
  amount: string;
  scope_kind: PoolScope;
  phase_id: string | null;
  building_id: string | null;
  allocation_method: AllocationMethod;
  area_type_id: string | null;
  notes: string | null;
}

export interface UnitAllocation {
  unit_id: string;
  unit_reference: string;
  driver_value: string;
  driver_share: string;
  allocated_amount: string;
  source_area_schedule_id: string | null;
  source_price_version_id: string | null;
  is_rounding_recipient: boolean;
}

export interface PoolAllocationSummary {
  pool_id: string;
  pool_number: string;
  name: string;
  category: PoolCategory;
  allocation_method: AllocationMethod;
  scope_kind: PoolScope;
  pool_amount: string;
  eligible_units: number;
  driver_total: string;
  allocated_total: string;
  variance: string;
}

export interface AllocationReconciliation {
  reconciled: boolean;
  source_cost_total: string;
  allocated_cost_total: string;
  variance: string;
  pool_count: number;
  allocation_count: number;
  unreconciled_pools: string[];
}

export interface CalculationPreview {
  version: AllocationVersion;
  pools: PoolAllocationSummary[];
  source_cost_total: string;
  allocated_cost_total: string;
  variance: string;
  reconciled: boolean;
  stale_sources: string[];
}

export interface AllocationVersionDetail {
  version: AllocationVersion;
  pools: CostPool[];
  reconciliation: AllocationReconciliation;
  stale_sources: string[];
}

export interface UnitCost {
  id: string;
  unit_id: string;
  sale_contract_id: string | null;
  currency_id: string;
  cost_type: UnitCostType;
  cost_class: string;
  basis: UnitCostBasis;
  amount: string;
  effective_date: string;
  reference: string | null;
  notes: string | null;
  status: UnitCostStatus;
  created_at: string;
  reversed_at: string | null;
  reversal_reason: string | null;
}

export interface WaterfallStep {
  key: string;
  label: string;
  amount: string;
  is_subtotal: boolean;
}

/**
 * One unit's whole economic position.
 *
 * Every figure arrives decided. Nothing on this interface is recomputed in the
 * browser: two implementations of a margin are two answers waiting to disagree
 * in front of a finance director.
 */
export interface UnitEconomics {
  unit_id: string;
  unit_reference: string;
  unit_number: string;
  commercial_status: string;
  basis: EconomicBasis;
  revenue_source: RevenueSource | null;
  revenue_source_id: string | null;
  revenue_currency_id: string | null;
  cost_currency_id: string;

  allocation_version_id: string | null;
  allocation_version_number: number | null;
  allocation_effective_from: string | null;

  land_cost: string;
  hard_cost: string;
  soft_cost: string;
  direct_cost: string;
  variable_selling_cost: string;
  seller_cost: string;
  allocated_finance_cost: string;
  deal_finance_cost: string;

  revenue: string | null;
  development_cost: string | null;
  commercial_cost: string | null;
  finance_cost: string | null;
  total_cost: string | null;
  gross_profit: string | null;
  gross_margin_fraction: string | null;
  contribution_profit: string | null;
  contribution_margin_fraction: string | null;
  profit_after_finance: string | null;
  margin_fraction: string | null;
  return_on_cost_fraction: string | null;

  profitability_status: ProfitabilityStatus;
  below_margin_threshold: boolean | null;
  threshold_fraction: string | null;
}

export interface UnitEconomicsDetail {
  economics: UnitEconomics;
  waterfall: WaterfallStep[];
  unit_costs: UnitCost[];
}

export interface ProjectEconomics {
  currency_id: string;
  unit_count: number;
  comparable_unit_count: number;
  sold_count: number;
  unsold_count: number;
  negative_profit_count: number;
  below_threshold_count: number;
  incomplete_count: number;
  currency_mismatch_count: number;
  threshold_fraction: string | null;

  revenue_total: string;
  development_cost_total: string;
  commercial_cost_total: string;
  finance_cost_total: string;
  total_cost_total: string;
  gross_profit_total: string;
  contribution_profit_total: string;
  profit_total: string;
  margin_fraction: string | null;
  return_on_cost_fraction: string | null;

  active_version: AllocationVersion | null;
}

// --------------------------------------------------------------------------- //
// Construction (PR-MVP-09)
// --------------------------------------------------------------------------- //

export type CostCategory = "hard" | "soft" | "contingency" | "other";

export interface CostCode {
  id: string;
  code: string;
  name: string;
  cost_category: CostCategory;
  package: string | null;
  parent_cost_code_id: string | null;
  phase_id: string | null;
  building_id: string | null;
  notes: string | null;
  is_active: boolean;
}

export interface BudgetVersion {
  id: string;
  version_number: number;
  status: string;
  effective_date: string;
  change_reason: string;
  source_version_id: string | null;
  currency_code: string | null;
  created_at: string;
  submitted_at: string | null;
  approved_at: string | null;
  rejected_at: string | null;
  rejection_reason: string | null;
  activated_at: string | null;
  superseded_at: string | null;
}

export interface BudgetLine {
  cost_code_id: string;
  cost_code: string;
  cost_code_name: string;
  cost_category: string;
  baseline_amount: string;
  approved_budget_amount: string;
  contingency_amount: string;
  control_budget: string;
  revised_commitment: string;
  /** Negative where a cost code is committed beyond its authorisation. */
  headroom: string;
  funding_source: string | null;
  notes: string | null;
}

export interface BudgetDetail extends BudgetVersion {
  lines: BudgetLine[];
  total_baseline: string;
  total_approved_budget: string;
  total_contingency: string;
  total_control_budget: string;
}

export interface ConstructionContract {
  id: string;
  contract_number: string;
  contract_type: string;
  vendor_name: string;
  status: string;
  currency_code: string | null;
  original_contract_value_ex_tax: string;
  approved_variation_delta: string;
  revised_commitment: string;
  certified_to_date: string;
  advance_entitlement_amount: string;
  retention_rate_fraction: string;
  planned_start_date: string | null;
  planned_completion_date: string | null;
  actual_start_date: string | null;
  actual_completion_date: string | null;
}

/** One contract line, carrying only what that line actually owns.
 *
 * No revised or certified figure: two lines may name the same cost code, and
 * nothing allocates a variation or a certificate back to one of them, so a
 * line-level figure could only be the cost code's total repeated. Those live on
 * `ContractDetail.cost_code_position`.
 */
export interface ContractLine {
  id: string;
  sequence: number;
  description: string;
  cost_code_id: string;
  cost_code: string;
  original_amount_ex_tax: string;
  notes: string | null;
}

/** One cost code's position on one contract — the grain these figures are true at. */
export interface ContractCostCodePosition {
  cost_code_id: string;
  cost_code: string;
  cost_code_name: string;
  original_amount_ex_tax: string;
  approved_variation_delta: string;
  revised_commitment: string;
  certified_to_date: string;
}

export interface ContractDetail extends ConstructionContract {
  vendor_registration_reference: string | null;
  vendor_tax_reference: string | null;
  vendor_contact_reference: string | null;
  payment_terms: string | null;
  tax_rate_fraction: string;
  notes: string | null;
  lines: ContractLine[];
  cost_code_position: ContractCostCodePosition[];
  approved_invoice_payable: string;
  disputed_invoice_payable: string;
  confirmed_paid: string;
  invoice_outstanding: string;
  retention_held: string;
  retention_released: string;
  retention_outstanding: string;
  advance_paid: string;
  advance_recovered: string;
  advance_outstanding: string;
}

export interface Variation {
  id: string;
  contract_id: string;
  contract_number: string;
  variation_number: string;
  description: string;
  cause: string | null;
  instruction_reference: string | null;
  requested_date: string;
  time_impact_days: number | null;
  funding_source: string | null;
  status: string;
  total_value_ex_tax: string;
  /** Decided on the server, on the absolute value of the change. */
  requires_escalation: boolean;
  review_amount: string | null;
  approved_at: string | null;
  rejected_at: string | null;
  rejection_reason: string | null;
  withdrawn_at: string | null;
  withdrawal_reason: string | null;
}

export interface VariationLine {
  id: string;
  sequence: number;
  cost_code_id: string;
  cost_code: string;
  description: string;
  value_delta_ex_tax: string;
}

export interface VariationDetail extends Variation {
  lines: VariationLine[];
}

export interface Certificate {
  id: string;
  contract_id: string;
  contract_number: string;
  certificate_number: string;
  period_start: string;
  period_end: string;
  certificate_date: string;
  status: string;
  certifier_name: string | null;
  evidence_reference: string | null;
  current_work_value_ex_tax: string;
  tax_amount: string;
  retention_release_amount: string;
  retention_held_amount: string;
  advance_recovery_amount: string;
  other_deductions_amount: string;
  /** The waterfall's result, computed by the server in one place. */
  net_due: string;
  uninvoiced_net_due: string;
  certified_at: string | null;
  rejection_reason: string | null;
  reversal_reason: string | null;
}

export interface CertificateLine {
  cost_code_id: string;
  cost_code: string;
  current_work_value_ex_tax: string;
  previously_certified: string;
  cumulative_certified: string;
  revised_commitment: string;
  notes: string | null;
}

export interface CertificateDetail extends Certificate {
  lines: CertificateLine[];
}

export interface ConstructionInvoice {
  id: string;
  contract_id: string;
  contract_number: string;
  certificate_id: string | null;
  invoice_number: string;
  invoice_type: string;
  invoice_date: string;
  due_date: string | null;
  status: string;
  amount_ex_tax: string;
  tax_amount: string;
  net_payable: string;
  allocated: string;
  outstanding: string;
  dispute_reason: string | null;
  void_reason: string | null;
  approved_at: string | null;
}

export interface PaymentAllocation {
  invoice_id: string;
  invoice_number: string;
  amount: string;
}

export interface ConstructionPayment {
  id: string;
  contract_id: string;
  contract_number: string;
  payment_reference: string;
  payment_date: string;
  value_date: string | null;
  amount: string;
  status: string;
  currency_code: string | null;
  bank_reference: string | null;
  proof_reference: string | null;
  allocated: string;
  unallocated: string;
  confirmed_at: string | null;
  reversed_at: string | null;
  reversal_reason: string | null;
  allocations: PaymentAllocation[];
}

export interface ConstructionMilestone {
  id: string;
  code: string;
  name: string;
  milestone_type: string;
  phase_id: string | null;
  building_id: string | null;
  scope_label: string | null;
  planned_date: string | null;
  forecast_date: string | null;
  actual_achieved_date: string | null;
  certified_date: string | null;
  progress_fraction: string | null;
  status: string;
  delay_days: number | null;
  evidence_reference: string | null;
  linked_certificate_id: string | null;
  depends_on: string[];
}

export interface MilestoneCertified {
  milestone: ConstructionMilestone;
  triggered_installment_count: number;
  triggered_plan_count: number;
}

/** What a payment plan may point a `construction_milestone` trigger at.
 *
 * Deliberately carries no amount, no contract and no vendor: the person
 * choosing it is scheduling a buyer's instalment, not reading the build's cost.
 */
export interface MilestoneTriggerOption {
  code: string;
  name: string;
  scope_label: string | null;
  planned_date: string | null;
  forecast_date: string | null;
  is_certified: boolean;
  certified_date: string | null;
}

export interface ForecastVersion {
  id: string;
  version_number: number;
  status: string;
  as_of_date: string;
  budget_version_id: string;
  budget_version_number: number | null;
  change_reason: string;
  source_version_id: string | null;
  currency_code: string | null;
  created_at: string;
  submitted_at: string | null;
  approved_at: string | null;
  rejected_at: string | null;
  rejection_reason: string | null;
  activated_at: string | null;
  superseded_at: string | null;
}

export interface ForecastLine {
  cost_code_id: string;
  cost_code: string;
  cost_code_name: string;
  control_budget: string;
  revised_commitment: string;
  certified_to_date: string;
  forecast_remaining_amount_ex_tax: string;
  estimate_at_completion: string;
  /** Positive is over budget. The convention never reverses between screens. */
  variance_at_completion: string;
  forecast_below_commitment: boolean;
  uncovered_commitment: string;
  note: string | null;
}

export interface ForecastDetail extends ForecastVersion {
  lines: ForecastLine[];
  total_control_budget: string;
  total_certified: string;
  total_forecast_remaining: string;
  total_estimate_at_completion: string;
  total_variance_at_completion: string;
}

/** The cost side. Every figure excludes tax, without exception. */
export interface CostControlPosition {
  original_baseline: string;
  current_approved_budget: string;
  approved_contingency: string;
  control_budget: string;
  original_commitment: string;
  approved_variation_delta: string;
  revised_commitment: string;
  /** Everything certified as of now. Moves the moment a certificate is signed. */
  certified_to_date: string;
  /** What the active forecast's estimate rests on, frozen at its own cutoff. */
  forecast_certified_as_of: string | null;
  forecast_remaining: string | null;
  estimate_at_completion: string | null;
  variance_at_completion: string | null;
}

/** The cash side. Every figure includes tax, without exception. */
export interface PayablePosition {
  approved_invoice_payable: string;
  disputed_invoice_payable: string;
  confirmed_paid: string;
  invoice_outstanding: string;
  retention_outstanding: string;
  advance_paid: string;
  advance_recovered: string;
  advance_outstanding: string;
}

export interface ConstructionControls {
  open_variations: number;
  escalated_variations: number;
  over_budget_cost_codes: number;
  forecast_below_commitment_cost_codes: number;
  late_milestones: number;
  achieved_uncertified_milestones: number;
  overdue_approved_invoices: number;
  has_active_budget: boolean;
  has_active_forecast: boolean;
}

export interface ConstructionSummary {
  currency_code: string | null;
  budget_version_number: number | null;
  forecast_version_number: number | null;
  forecast_as_of: string | null;
  cost_control: CostControlPosition;
  payable: PayablePosition;
  controls: ConstructionControls;
}

export interface ReconciliationCheck {
  key: string;
  label: string;
  ok: boolean;
  amount: string | null;
  expected: string | null;
  variance: string | null;
  detail: string | null;
}

export interface ConstructionReconciliation {
  ok: boolean;
  checks: ReconciliationCheck[];
}

export interface DeliveryResult {
  to_status: string;
  unit_count: number;
  unit_ids: string[];
}

// --------------------------------------------------------------------------- //
// Cashflow and management reporting (PR-MVP-10)
// --------------------------------------------------------------------------- //

/**
 * Money and rates arrive as strings and stay strings.
 *
 * The backend serialises every figure as a decimal string on purpose: a cash
 * position put through a JavaScript float comes back subtly different from the
 * one the ledger will enforce, and the difference appears in the least
 * significant place — which is exactly where a reconciliation looks. These
 * aliases are documentation, not enforcement, but they mark every field the
 * browser may format and must never do arithmetic on.
 */
export type MoneyStr = string;
export type RateStr = string;

/** Where a month sits relative to the date a report was taken. */
export type MonthBasis = "actual" | "actual_and_forecast" | "forecast";

export type CashflowForecastStatus =
  | "draft"
  | "submitted"
  | "approved"
  | "active"
  | "superseded"
  | "rejected";

export type CashflowMovementStatus = "recorded" | "confirmed" | "reversed";

export type FlowDirection = "inflow" | "outflow";

export type ForecastSourceKind =
  | "unsold_customer"
  | "development"
  | "construction"
  | "financing";

export type DevelopmentCategory =
  | "land_acquisition"
  | "land_fees"
  | "design"
  | "consultants"
  | "permits"
  | "insurance"
  | "developer_overhead"
  | "marketing"
  | "commissions"
  | "tax"
  | "handover"
  | "other";

export type FinancingType =
  | "equity_contribution"
  | "debt_drawdown"
  | "guarantee_cash_release"
  | "equity_distribution"
  | "debt_fee"
  | "interest_payment"
  | "principal_repayment"
  | "guarantee_cash_posting";

/** What every reporting response says about itself before its figures. */
export interface CashflowBasis {
  project_id: string;
  as_of_date: string;
  currency_code: string | null;
  forecast_version_id: string | null;
  forecast_version_number: number | null;
  forecast_as_of_date: string | null;
  from_month: string | null;
  to_month: string | null;
}

export interface CashflowStaleness {
  is_stale: boolean;
  construction_is_stale: boolean;
  pinned_construction_version_number: number | null;
  active_construction_version_number: number | null;
  customer_schedule_is_stale: boolean;
  snapshot_plan_version_count: number;
  governing_plan_version_count: number;
}

export interface CashflowCheck {
  name: string;
  passed: boolean;
  expected: MoneyStr | null;
  actual: MoneyStr | null;
  detail: string;
}

export interface CashflowPosition {
  total_cash: MoneyStr;
  restricted_cash: MoneyStr;
  unrestricted_cash: MoneyStr;
  /** Null where nothing is forecast to go out: a ratio against zero is undefined. */
  forecast_collection_coverage: RateStr | null;
  coverage_numerator: MoneyStr;
  coverage_denominator: MoneyStr;
}

export interface CashflowFundingWindow {
  days: number;
  from_date: string;
  to_date: string;
  opening_unrestricted_cash: MoneyStr;
  usable_inflows: MoneyStr;
  outflows: MoneyStr;
  net_movement: MoneyStr;
  /** The deepest point inside the window, which is what has to be funded. */
  minimum_projected_unrestricted_cash: MoneyStr;
  closing_projected_unrestricted_cash: MoneyStr;
  funding_requirement: MoneyStr;
}

export interface CashflowPeakDeficit {
  minimum_unrestricted_cash: MoneyStr;
  peak_funding_deficit: MoneyStr;
  peak_deficit_month: string | null;
}

export interface CashflowReturns {
  npv_basis: string;
  discount_rate_per_period: RateStr;
  net_present_value: MoneyStr;
  net_project_cashflow: MoneyStr;
  equity_irr_basis: string;
  /** Null with a reason beside it, never zero. */
  equity_irr_per_period: RateStr | null;
  equity_irr_unavailable_reason: string | null;
  equity_contributed: MoneyStr;
  equity_distributed: MoneyStr;
  equity_net: MoneyStr;
}

export interface CashflowSummary {
  basis: CashflowBasis;
  position: CashflowPosition;
  peak_deficit: CashflowPeakDeficit;
  funding_windows: CashflowFundingWindow[];
  returns: CashflowReturns;
  has_active_forecast: boolean;
  staleness: CashflowStaleness | null;
}

export interface CashflowMonthlyPosition {
  period_month: string;
  basis: MonthBasis;
  opening_total_cash: MoneyStr;
  customer_scheduled_due: MoneyStr;
  customer_actual_receipts: MoneyStr;
  customer_forecast_receipts: MoneyStr;
  financing_actual_inflows: MoneyStr;
  financing_forecast_inflows: MoneyStr;
  development_actual_outflows: MoneyStr;
  development_forecast_outflows: MoneyStr;
  construction_actual_payments: MoneyStr;
  construction_forecast_payments: MoneyStr;
  customer_refunds: MoneyStr;
  financing_actual_outflows: MoneyStr;
  financing_forecast_outflows: MoneyStr;
  total_inflows: MoneyStr;
  total_outflows: MoneyStr;
  net_cashflow: MoneyStr;
  closing_total_cash: MoneyStr;
  opening_restricted_cash: MoneyStr;
  newly_restricted_customer_cash: MoneyStr;
  escrow_releases: MoneyStr;
  closing_restricted_cash: MoneyStr;
  opening_unrestricted_cash: MoneyStr;
  usable_inflows: MoneyStr;
  unrestricted_outflows: MoneyStr;
  closing_unrestricted_cash: MoneyStr;
  funding_gap: MoneyStr;
}

export interface CashflowMonthly {
  basis: CashflowBasis;
  months: CashflowMonthlyPosition[];
}

/**
 * One transaction behind a figure, named by the module that owns it.
 *
 * `source_type` is deliberately specific — a collection receipt, a construction
 * payment, a payment-plan instalment — because cashflow consolidates records it
 * does not own, and relabelling them all as "cashflow transaction" would hide
 * where a correction has to be made.
 */
export interface CashflowSourceRow {
  source_type: string;
  source_id: string;
  period_month: string;
  business_date: string;
  amount: MoneyStr;
  flow_direction: string;
  category: string;
  basis: string;
  status: string;
  display_reference: string;
}

export interface CashflowDrilldown {
  basis: CashflowBasis;
  total: MoneyStr;
  rows: CashflowSourceRow[];
}

export interface CashflowForecastVersion {
  id: string;
  version_number: number;
  status: CashflowForecastStatus;
  currency_code: string | null;
  as_of_date: string;
  forecast_start_month: string;
  forecast_end_month: string;
  opening_unrestricted_cash: MoneyStr;
  opening_restricted_cash: MoneyStr;
  opening_total_cash: MoneyStr;
  discount_rate_per_period: RateStr;
  construction_forecast_version_id: string | null;
  construction_forecast_version_number: number | null;
  source_version_id: string | null;
  change_reason: string;
  installments_in_snapshot: number;
}

export interface CashflowForecastLine {
  id: string;
  period_month: string;
  flow_direction: FlowDirection;
  category: string;
  source_kind: ForecastSourceKind;
  amount: MoneyStr;
  phase_id: string | null;
  construction_cost_code_id: string | null;
  construction_cost_code: string | null;
  note: string | null;
}

/** One frozen buyer instalment. No buyer name: a cash report does not need one. */
export interface CashflowScheduleSnapshot {
  installment_id: string;
  payment_plan_version_id: string;
  sale_contract_id: string;
  unit_id: string | null;
  amount: MoneyStr;
  contractual_due_date: string | null;
  forecast_due_date: string | null;
  actual_due_date: string | null;
  chosen_forecast_date: string;
  trigger_type: string;
  trigger_status: string;
}

export interface CashflowForecastDetail extends CashflowForecastVersion {
  lines: CashflowForecastLine[];
  customer_schedule: CashflowScheduleSnapshot[];
  staleness: CashflowStaleness;
  construction_reconciliation: CashflowCheck[];
}

export interface CashflowDevelopmentMovement {
  id: string;
  movement_reference: string;
  category: DevelopmentCategory;
  amount: MoneyStr;
  currency_code: string | null;
  movement_date: string;
  value_date: string | null;
  phase_id: string | null;
  status: CashflowMovementStatus;
  counterparty_reference: string | null;
  invoice_reference: string | null;
  bank_reference: string | null;
  evidence_reference: string | null;
  notes: string | null;
  /** Recording is a claim. This is what says the money actually moved. */
  counts_as_cash: boolean;
}

export interface CashflowFinancingMovement {
  id: string;
  movement_reference: string;
  movement_type: FinancingType;
  flow_direction: FlowDirection;
  amount: MoneyStr;
  currency_code: string | null;
  movement_date: string;
  value_date: string | null;
  status: CashflowMovementStatus;
  counterparty_reference: string | null;
  facility_reference: string | null;
  bank_reference: string | null;
  evidence_reference: string | null;
  notes: string | null;
  counts_as_cash: boolean;
}

export interface CashflowRelease {
  id: string;
  restriction_id: string;
  release_date: string;
  amount: MoneyStr;
  certification_reference: string | null;
  evidence_reference: string | null;
  status: CashflowMovementStatus;
  /** Confirmed *and* freeing an escrow that still holds something. */
  counts_as_released: boolean;
  /** Whether that escrow currently holds anything, so a screen can say why. */
  restriction_counts: boolean;
}

export interface CashflowRestriction {
  id: string;
  receipt_id: string;
  receipt_number: string | null;
  receipt_amount: MoneyStr | null;
  restricted_amount: MoneyStr;
  released_amount: MoneyStr;
  outstanding_restricted: MoneyStr;
  reason: string;
  source_reference: string | null;
  status: CashflowMovementStatus;
  /** Confirmed *and* backed by a receipt that still stands. */
  counts_as_restricted: boolean;
  /** False is what a reader needs when a confirmed escrow stops counting. */
  receipt_stands: boolean;
  releases: CashflowRelease[];
}

export interface CashflowVariance {
  forecast_amount: MoneyStr;
  actual_amount: MoneyStr;
  variance_amount: MoneyStr;
  /** Null against a zero forecast: a percentage of nothing is not a number. */
  variance_rate: RateStr | null;
}

export interface CashflowAccuracyRow {
  period_month: string;
  category_group: string;
  variance: CashflowVariance;
}

export interface CashflowAccuracy {
  basis: CashflowBasis;
  rows: CashflowAccuracyRow[];
}

export interface CashflowReconciliation {
  basis: CashflowBasis;
  checks: CashflowCheck[];
  failed_count: number;
}

export interface CashflowManagementMetric {
  key: string;
  label: string;
  value: string | null;
  unit: string;
  /** The module that owns this figure. Kept so a total names its source. */
  source_module: string;
  drilldown_source_type: string | null;
}

export interface CashflowManagementGroup {
  group: string;
  metrics: CashflowManagementMetric[];
}

export interface CashflowManagement {
  basis: CashflowBasis;
  groups: CashflowManagementGroup[];
}
