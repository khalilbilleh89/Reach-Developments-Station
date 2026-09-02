/**
 * Names and tones for unit economics, in one place.
 *
 * The backend's vocabulary is deliberately terse — `missing_cost_basis`,
 * `weighted_area`, `variable_selling` — because it is a contract, not prose.
 * Turning it into something a finance director reads is presentation, and it
 * belongs here rather than scattered through the components that render it.
 *
 * Nothing in this file computes anything.
 */

import type {
  AllocationMethod,
  AllocationVersionStatus,
  EconomicBasis,
  PoolCategory,
  PoolScope,
  ProfitabilityStatus,
  UnitCostBasis,
  UnitCostType,
} from "@/lib/api";

type Tone = "neutral" | "info" | "success" | "warning" | "danger";

const VERSION_LABELS: Record<AllocationVersionStatus, string> = {
  draft: "Draft",
  submitted: "Submitted",
  approved: "Approved",
  active: "Current",
  superseded: "Superseded",
  rejected: "Rejected",
};

const VERSION_TONES: Record<AllocationVersionStatus, Tone> = {
  draft: "neutral",
  submitted: "info",
  approved: "info",
  active: "success",
  superseded: "neutral",
  rejected: "danger",
};

export function versionLabel(status: AllocationVersionStatus): string {
  return VERSION_LABELS[status] ?? status;
}

export function versionTone(status: AllocationVersionStatus): Tone {
  return VERSION_TONES[status] ?? "neutral";
}

const CATEGORY_LABELS: Record<PoolCategory, string> = {
  land: "Land",
  hard: "Hard",
  soft: "Soft",
  finance: "Finance",
};

export const POOL_CATEGORIES: PoolCategory[] = ["land", "hard", "soft", "finance"];

export function categoryLabel(category: PoolCategory): string {
  return CATEGORY_LABELS[category] ?? category;
}

const METHOD_LABELS: Record<AllocationMethod, string> = {
  weighted_area: "Weighted area",
  raw_area: "Raw area",
  unit_count: "Unit count",
  revenue_value: "Revenue value",
  custom_driver: "Custom driver",
};

export const ALLOCATION_METHODS: AllocationMethod[] = [
  "weighted_area",
  "raw_area",
  "unit_count",
  "revenue_value",
  "custom_driver",
];

export function methodLabel(method: AllocationMethod): string {
  return METHOD_LABELS[method] ?? method;
}

const SCOPE_LABELS: Record<PoolScope, string> = {
  project: "Whole project",
  phase: "One phase",
  building: "One building",
};

export const POOL_SCOPES: PoolScope[] = ["project", "phase", "building"];

export function scopeLabel(scope: PoolScope): string {
  return SCOPE_LABELS[scope] ?? scope;
}

/**
 * What a profitability status means, said plainly.
 *
 * Each of these is a reason a number is absent. None of them is a zero, and
 * none of them should ever be rendered as one: an operator who reads "0.0%"
 * acts on it, and an operator who reads "no approved cost basis covered this
 * sale" goes and creates one.
 */
const PROFIT_LABELS: Record<ProfitabilityStatus, string> = {
  ready: "Calculated",
  missing_revenue: "No approved price",
  missing_cost_basis: "No cost basis",
  unreconciled_cost_basis: "Cost basis incomplete",
  currency_mismatch: "Currencies differ",
};

const PROFIT_TONES: Record<ProfitabilityStatus, Tone> = {
  ready: "success",
  missing_revenue: "warning",
  missing_cost_basis: "warning",
  unreconciled_cost_basis: "danger",
  currency_mismatch: "warning",
};

export function profitabilityLabel(status: ProfitabilityStatus): string {
  return PROFIT_LABELS[status] ?? status;
}

export function profitabilityTone(status: ProfitabilityStatus): Tone {
  return PROFIT_TONES[status] ?? "neutral";
}

/** The sentence a screen shows in place of a margin it does not have. */
export const PROFIT_EXPLANATIONS: Record<ProfitabilityStatus, string> = {
  ready: "",
  missing_revenue:
    "This unit has no current approved price, so forecast profit cannot be calculated.",
  missing_cost_basis:
    "No approved allocation version governs this unit, so what it costs is unknown. " +
    "An unsold unit needs a current cost basis; a sold one needs the basis that was " +
    "governing when its contract was signed, and a basis approved afterwards is not " +
    "that one.",
  unreconciled_cost_basis:
    "This unit's cost basis cannot be used. Either the allocation version does not " +
    "add up to its cost pools, or it never allocated to this unit — a unit created " +
    "after a version was made current carries no share of its shared costs until a " +
    "new version includes it. Either way the zeros below are missing figures, not " +
    "a cost of nothing.",
  currency_mismatch:
    "Revenue and allocated cost use different currencies. Profitability is not " +
    "calculated without an approved exchange basis.",
};

const BASIS_LABELS: Record<EconomicBasis, string> = {
  forecast: "Forecast",
  sold: "Sold",
};

export function basisLabel(basis: EconomicBasis): string {
  return BASIS_LABELS[basis] ?? basis;
}

const COST_BASIS_LABELS: Record<UnitCostBasis, string> = {
  forecast: "Forecast",
  actual: "Actual",
};

export function costBasisLabel(basis: UnitCostBasis): string {
  return COST_BASIS_LABELS[basis] ?? basis;
}

const COST_TYPE_LABELS: Record<UnitCostType, string> = {
  unit_upgrade: "Unit upgrade",
  finishes: "Finishes",
  furniture_appliance: "Furniture and appliances",
  legal_registry_support: "Legal and registry support",
  rectification: "Rectification",
  other_direct: "Other direct",
  marketing: "Marketing",
  sales_commission: "Sales commission",
  branch_commission: "Branch commission",
  payment_fee: "Payment fee",
  seller_paid_legal: "Seller-paid legal",
  other_selling: "Other selling",
};

/** The direct types, in the order an operator would look for them. */
export const DIRECT_COST_TYPES: UnitCostType[] = [
  "unit_upgrade",
  "finishes",
  "furniture_appliance",
  "legal_registry_support",
  "rectification",
  "other_direct",
];

/** The selling types. Kept separate on screen because they sit below gross profit. */
export const SELLING_COST_TYPES: UnitCostType[] = [
  "marketing",
  "sales_commission",
  "branch_commission",
  "payment_fee",
  "seller_paid_legal",
  "other_selling",
];

export function costTypeLabel(type: UnitCostType): string {
  return COST_TYPE_LABELS[type] ?? type;
}

/** Green above zero, red below. A loss must never look like a small profit. */
export function profitTone(amount: string | null): Tone {
  if (amount === null) return "neutral";
  return amount.trimStart().startsWith("-") ? "danger" : "success";
}
