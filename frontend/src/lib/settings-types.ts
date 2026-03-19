/**
 * settings-types.ts — TypeScript types for the Settings domain.
 *
 * These types mirror the Pydantic schemas defined in
 * app/modules/settings/schemas.py and the enumerations in
 * app/shared/enums/settings.py.
 *
 * PricingPriceMode values:
 *   "fixed" | "percentage" | "excluded"
 *
 * CommissionCalculationMode values:
 *   "marginal" | "cumulative"
 */

// ---------------------------------------------------------------------------
// Enum-like string literals
// ---------------------------------------------------------------------------

/** Governs how an optional-feature price (parking, storage) is applied. */
export type PricingPriceMode = "fixed" | "percentage" | "excluded";

/** Calculation strategy for commission pool distribution. */
export type CommissionCalculationMode = "marginal" | "cumulative";

// ---------------------------------------------------------------------------
// PricingPolicy
// ---------------------------------------------------------------------------

/** Mirrors PricingPolicyCreate */
export interface PricingPolicyCreate {
  name: string;
  description?: string | null;
  is_default?: boolean;
  currency?: string;
  base_markup_percent?: number;
  balcony_price_factor?: number;
  parking_price_mode?: PricingPriceMode;
  storage_price_mode?: PricingPriceMode;
  is_active?: boolean;
}

/** Mirrors PricingPolicyUpdate (all fields optional) */
export interface PricingPolicyUpdate {
  name?: string;
  description?: string | null;
  is_default?: boolean;
  currency?: string;
  base_markup_percent?: number;
  balcony_price_factor?: number;
  parking_price_mode?: PricingPriceMode;
  storage_price_mode?: PricingPriceMode;
  is_active?: boolean;
}

/** Mirrors PricingPolicyResponse */
export interface PricingPolicy {
  id: string;
  name: string;
  description: string | null;
  is_default: boolean;
  currency: string;
  base_markup_percent: number;
  balcony_price_factor: number;
  parking_price_mode: PricingPriceMode;
  storage_price_mode: PricingPriceMode;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/** Mirrors PricingPolicyList */
export interface PricingPolicyList {
  total: number;
  items: PricingPolicy[];
}

// ---------------------------------------------------------------------------
// CommissionPolicy
// ---------------------------------------------------------------------------

/** Mirrors CommissionPolicyCreate */
export interface CommissionPolicyCreate {
  name: string;
  description?: string | null;
  is_default?: boolean;
  pool_percent?: number;
  calculation_mode?: CommissionCalculationMode;
  is_active?: boolean;
}

/** Mirrors CommissionPolicyUpdate (all fields optional) */
export interface CommissionPolicyUpdate {
  name?: string;
  description?: string | null;
  is_default?: boolean;
  pool_percent?: number;
  calculation_mode?: CommissionCalculationMode;
  is_active?: boolean;
}

/** Mirrors CommissionPolicyResponse */
export interface CommissionPolicy {
  id: string;
  name: string;
  description: string | null;
  is_default: boolean;
  pool_percent: number;
  calculation_mode: CommissionCalculationMode;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/** Mirrors CommissionPolicyList */
export interface CommissionPolicyList {
  total: number;
  items: CommissionPolicy[];
}

// ---------------------------------------------------------------------------
// ProjectTemplate
// ---------------------------------------------------------------------------

/** Mirrors ProjectTemplateCreate */
export interface ProjectTemplateCreate {
  name: string;
  description?: string | null;
  default_pricing_policy_id?: string | null;
  default_commission_policy_id?: string | null;
  default_currency?: string;
  is_active?: boolean;
}

/** Mirrors ProjectTemplateUpdate (all fields optional) */
export interface ProjectTemplateUpdate {
  name?: string;
  description?: string | null;
  default_pricing_policy_id?: string | null;
  default_commission_policy_id?: string | null;
  default_currency?: string;
  is_active?: boolean;
}

/** Mirrors ProjectTemplateResponse */
export interface ProjectTemplate {
  id: string;
  name: string;
  description: string | null;
  default_pricing_policy_id: string | null;
  default_commission_policy_id: string | null;
  default_currency: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/** Mirrors ProjectTemplateList */
export interface ProjectTemplateList {
  total: number;
  items: ProjectTemplate[];
}
