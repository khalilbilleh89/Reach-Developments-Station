/**
 * feasibility-assumptions.ts — Client-side validation helpers for feasibility
 * assumptions form inputs.
 *
 * The form represents ratio fields as percentages (0–100). The backend expects
 * decimal values in [0, 1]. This utility validates the raw form strings using
 * the same rules the backend enforces so invalid input is caught before
 * submission. Backend validation remains the final source of truth.
 */

/**
 * Raw string values as they exist in the assumptions form.
 * Ratio fields are expressed as percentages (e.g. "10" means 10% → 0.10).
 */
export interface AssumptionsFormInputs {
  sellableArea: string;
  avgSalePrice: string;
  constructionCost: string;
  /** Soft cost as a percent value (0–100). */
  softCostRatio: string;
  /** Finance cost as a percent value (0–100). */
  financeCostRatio: string;
  /** Sales cost as a percent value (0–100). */
  salesCostRatio: string;
  devPeriod: string;
}

/** Field-keyed error messages; only fields that fail validation have an entry. */
export interface AssumptionsFieldErrors {
  sellableArea?: string;
  avgSalePrice?: string;
  constructionCost?: string;
  softCostRatio?: string;
  financeCostRatio?: string;
  salesCostRatio?: string;
  devPeriod?: string;
}

export interface AssumptionsValidationResult {
  valid: boolean;
  errors: AssumptionsFieldErrors;
}

/**
 * Validate all feasibility assumptions form fields.
 *
 * Rules (mirrors backend FeasibilityAssumptionsCreate constraints):
 *  - sellable_area_sqm          > 0 (finite)
 *  - avg_sale_price_per_sqm     > 0 (finite)
 *  - construction_cost_per_sqm  > 0 (finite)
 *  - soft_cost_ratio            0 to 100 (percent input; backend expects 0–1)
 *  - finance_cost_ratio         0 to 100 (percent input; backend expects 0–1)
 *  - sales_cost_ratio           0 to 100 (percent input; backend expects 0–1)
 *  - development_period_months  finite integer ≥ 1
 *
 * Returns a result with `valid: true` and an empty errors object when all
 * fields pass, or `valid: false` with per-field error messages when any field
 * fails.
 */
export function validateFeasibilityAssumptions(
  inputs: AssumptionsFormInputs,
): AssumptionsValidationResult {
  const errors: AssumptionsFieldErrors = {};

  const sellableAreaVal = Number(inputs.sellableArea);
  const avgSalePriceVal = Number(inputs.avgSalePrice);
  const constructionCostVal = Number(inputs.constructionCost);
  const softCostRawVal = Number(inputs.softCostRatio);
  const financeCostRawVal = Number(inputs.financeCostRatio);
  const salesCostRawVal = Number(inputs.salesCostRatio);
  const devPeriodVal = Number(inputs.devPeriod);

  if (!Number.isFinite(sellableAreaVal) || sellableAreaVal <= 0) {
    errors.sellableArea = "Invalid value for sellable area sqm.";
  }
  if (!Number.isFinite(avgSalePriceVal) || avgSalePriceVal <= 0) {
    errors.avgSalePrice = "Invalid value for avg sale price per sqm.";
  }
  if (!Number.isFinite(constructionCostVal) || constructionCostVal <= 0) {
    errors.constructionCost = "Invalid value for construction cost per sqm.";
  }
  if (
    !Number.isFinite(softCostRawVal) ||
    softCostRawVal < 0 ||
    softCostRawVal > 100
  ) {
    errors.softCostRatio = "Soft cost ratio must be between 0 and 100.";
  }
  if (
    !Number.isFinite(financeCostRawVal) ||
    financeCostRawVal < 0 ||
    financeCostRawVal > 100
  ) {
    errors.financeCostRatio = "Finance cost ratio must be between 0 and 100.";
  }
  if (
    !Number.isFinite(salesCostRawVal) ||
    salesCostRawVal < 0 ||
    salesCostRawVal > 100
  ) {
    errors.salesCostRatio = "Sales cost ratio must be between 0 and 100.";
  }
  if (
    !Number.isFinite(devPeriodVal) ||
    !Number.isInteger(devPeriodVal) ||
    devPeriodVal < 1
  ) {
    errors.devPeriod =
      "Development period must be a whole number of months (≥ 1).";
  }

  return { valid: Object.keys(errors).length === 0, errors };
}

/**
 * Parse validated form inputs into the assumptions payload expected by the
 * backend (ratio fields converted from percent to decimal).
 *
 * Only call this after `validateFeasibilityAssumptions` returns `valid: true`.
 */
export function parseFeasibilityAssumptionsPayload(
  inputs: AssumptionsFormInputs,
): {
  sellable_area_sqm: number;
  avg_sale_price_per_sqm: number;
  construction_cost_per_sqm: number;
  soft_cost_ratio: number;
  finance_cost_ratio: number;
  sales_cost_ratio: number;
  development_period_months: number;
} {
  return {
    sellable_area_sqm: Number(inputs.sellableArea),
    avg_sale_price_per_sqm: Number(inputs.avgSalePrice),
    construction_cost_per_sqm: Number(inputs.constructionCost),
    soft_cost_ratio: Number(inputs.softCostRatio) / 100,
    finance_cost_ratio: Number(inputs.financeCostRatio) / 100,
    sales_cost_ratio: Number(inputs.salesCostRatio) / 100,
    development_period_months: Number(inputs.devPeriod),
  };
}
