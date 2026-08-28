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
