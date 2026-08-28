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
