import type { Tone } from "@/components/ui";
import type { MonthBasis } from "@/lib/api";

/**
 * The words the cashflow workspace uses, written once.
 *
 * Finance and development management read this screen, not engineers. So the
 * interface says "Expected collection" and "Escrowed", never `source_kind` or
 * `flow_direction` — those are how the record is stored, not what it means.
 *
 * Three of these decide something a reader acts on, and are here rather than
 * beside a table because a second copy would drift: the month basis, whether a
 * movement counts as cash, and whether an escrow is still holding anything.
 */

const MONTH_BASIS_LABELS: Record<MonthBasis, string> = {
  actual: "Actual",
  // Not "Actual". The month a report is taken in is part spent and part still
  // expected, and calling it actual presents a part month as a finished one.
  actual_and_forecast: "Actual + Forecast",
  forecast: "Forecast",
};

const MONTH_BASIS_NOTES: Record<MonthBasis, string> = {
  actual: "This month has finished. Every figure is cash that moved.",
  actual_and_forecast:
    "This month is still running: cash that has moved, plus what is still expected before it ends.",
  forecast: "This month has not started. Every figure is expected.",
};

export function monthBasisLabel(basis: MonthBasis | string): string {
  return MONTH_BASIS_LABELS[basis as MonthBasis] ?? basis;
}

export function monthBasisNote(basis: MonthBasis | string): string {
  return MONTH_BASIS_NOTES[basis as MonthBasis] ?? "";
}

export function monthBasisTone(basis: MonthBasis | string): Tone {
  if (basis === "actual") return "neutral";
  if (basis === "actual_and_forecast") return "info";
  return "neutral";
}

const FORECAST_LABELS: Record<string, string> = {
  draft: "Draft",
  submitted: "Awaiting approval",
  approved: "Approved",
  rejected: "Rejected",
  active: "In force",
  superseded: "Superseded",
};

const FORECAST_TONES: Record<string, Tone> = {
  draft: "neutral",
  submitted: "warning",
  approved: "info",
  rejected: "danger",
  active: "success",
  superseded: "neutral",
};

export function forecastLabel(status: string): string {
  return FORECAST_LABELS[status] ?? status;
}

export function forecastTone(status: string): Tone {
  return FORECAST_TONES[status] ?? "neutral";
}

/**
 * The statuses a forecast is still open in — the backend's ``FORECAST_OPEN``.
 *
 * Stated as the set that is open, never as the ones that are closed. The
 * negative form reads identically today and quietly admits every terminal
 * status invented later, which is exactly how `rejected` came to be offered a
 * buyer-schedule refresh the server answers with a 409: a rejected version is
 * history, and history does not get re-pinned to today's schedule.
 *
 * Editing a line is narrower still — the server allows it on a draft alone,
 * because a submitted version is what somebody is reviewing.
 */
export const FORECAST_OPEN_STATUSES: ReadonlySet<string> = new Set([
  "draft",
  "submitted",
  "approved",
]);

// No component branches on the set above, and it is kept anyway: it is the half
// of the contrast that makes the other half legible. Read alone, a refreshable
// set of draft and submitted looks like an arbitrary pair; read against the open
// set it is obviously the open statuses less the one that has been signed for.

/**
 * The statuses whose sources may still be re-pinned — the backend's
 * ``FORECAST_REFRESHABLE``.
 *
 * Deliberately not the open set, and the two must not be collapsed just because
 * they nearly match. An approved version is open — a second forecast beside it
 * would be a second answer to one question — and it is *not* refreshable,
 * because the CFO approved the months a particular buyer schedule produced.
 * "Occupies the slot" and "may still be changed" are different questions, and a
 * button wired to the wrong one silently changes what somebody signed for.
 */
export const FORECAST_REFRESHABLE_STATUSES: ReadonlySet<string> = new Set([
  "draft",
  "submitted",
]);

/** Whether the buyer schedule under this version may still be re-frozen. */
export function forecastIsRefreshable(status: string): boolean {
  return FORECAST_REFRESHABLE_STATUSES.has(status);
}

/**
 * A movement's status in words a reader will not mistake for cash.
 *
 * "Recorded" is a claim one person made. It is not money that has moved, and
 * the whole maker/checker control depends on the two not looking alike on
 * screen.
 */
const MOVEMENT_LABELS: Record<string, string> = {
  recorded: "Recorded, not yet confirmed",
  confirmed: "Confirmed",
  reversed: "Reversed",
};

const MOVEMENT_TONES: Record<string, Tone> = {
  recorded: "warning",
  confirmed: "success",
  reversed: "neutral",
};

export function movementLabel(status: string): string {
  return MOVEMENT_LABELS[status] ?? status;
}

export function movementTone(status: string): Tone {
  return MOVEMENT_TONES[status] ?? "neutral";
}

const DEVELOPMENT_LABELS: Record<string, string> = {
  land_acquisition: "Land acquisition",
  land_fees: "Land fees",
  design: "Design",
  consultants: "Consultants",
  permits: "Permits",
  insurance: "Insurance",
  developer_overhead: "Developer overhead",
  marketing: "Marketing",
  commissions: "Commissions",
  tax: "Tax",
  handover: "Handover",
  other: "Other",
};

const FINANCING_LABELS: Record<string, string> = {
  equity_contribution: "Equity contribution",
  debt_drawdown: "Debt drawdown",
  guarantee_cash_release: "Guarantee cash released",
  equity_distribution: "Equity distribution",
  debt_fee: "Debt fee",
  interest_payment: "Interest payment",
  principal_repayment: "Principal repayment",
  guarantee_cash_posting: "Guarantee cash posted",
};

const SOURCE_KIND_LABELS: Record<string, string> = {
  unsold_customer: "Unsold stock",
  development: "Development",
  construction: "Construction",
  financing: "Financing",
};

/** What a forecast line or a movement is, in the language of the business. */
export function categoryLabel(category: string): string {
  return (
    DEVELOPMENT_LABELS[category] ??
    FINANCING_LABELS[category] ??
    SOURCE_KIND_LABELS[category] ??
    OTHER_CATEGORY_LABELS[category] ??
    category
  );
}

const OTHER_CATEGORY_LABELS: Record<string, string> = {
  customer_collection: "Customer collection",
  construction: "Construction",
  restriction: "Escrowed",
  release: "Escrow released",
};

export function sourceKindLabel(kind: string): string {
  return SOURCE_KIND_LABELS[kind] ?? kind;
}

export const DEVELOPMENT_CATEGORY_OPTIONS = Object.entries(DEVELOPMENT_LABELS).map(
  ([value, label]) => ({ value, label }),
);

export const FINANCING_TYPE_OPTIONS = Object.entries(FINANCING_LABELS).map(
  ([value, label]) => ({ value, label }),
);

/**
 * Which system record a drill-down row belongs to.
 *
 * Named rather than flattened to "cashflow transaction", because this module
 * consolidates records it does not own: a reader who has to correct a figure
 * needs to know whether to open Collections, Construction or this workspace.
 */
const SOURCE_TYPE_LABELS: Record<string, string> = {
  collection_receipt: "Buyer receipt",
  collection_refund: "Buyer refund",
  construction_payment: "Construction payment",
  cashflow_development_movement: "Development movement",
  cashflow_financing_movement: "Financing movement",
  cashflow_receipt_restriction: "Escrow restriction",
  cashflow_restriction_release: "Escrow release",
  payment_plan_installment: "Payment plan instalment",
  cashflow_forecast_line: "Forecast line",
};

const SOURCE_TYPE_OWNERS: Record<string, string> = {
  collection_receipt: "Collections",
  collection_refund: "Collections",
  construction_payment: "Construction",
  cashflow_development_movement: "Cashflow",
  cashflow_financing_movement: "Cashflow",
  cashflow_receipt_restriction: "Cashflow",
  cashflow_restriction_release: "Cashflow",
  payment_plan_installment: "Payment plans",
  cashflow_forecast_line: "Cashflow",
};

export function sourceTypeLabel(sourceType: string): string {
  return SOURCE_TYPE_LABELS[sourceType] ?? sourceType;
}

/** The module that owns the record, so a correction is made in the right place. */
export function sourceTypeOwner(sourceType: string): string {
  return SOURCE_TYPE_OWNERS[sourceType] ?? "—";
}

export const SOURCE_TYPE_OPTIONS = Object.entries(SOURCE_TYPE_LABELS).map(
  ([value, label]) => ({ value, label }),
);

const ROW_BASIS_LABELS: Record<string, string> = {
  actual: "Actual",
  forecast: "Forecast",
  scheduled: "Contractually due",
};

export function rowBasisLabel(basis: string): string {
  return ROW_BASIS_LABELS[basis] ?? basis;
}

export const ROW_BASIS_OPTIONS = Object.entries(ROW_BASIS_LABELS).map(
  ([value, label]) => ({ value, label }),
);

/**
 * Why an equity IRR has no answer, in words rather than a code.
 *
 * A return that cannot be computed is reported as unavailable with its reason.
 * Rendering 0% instead would be a claim about the investment.
 */
const IRR_REASON_LABELS: Record<string, string> = {
  no_negative_equity_cashflow:
    "No equity has been contributed yet, so there is nothing to earn a return on.",
  no_positive_equity_cashflow:
    "No equity has been returned yet, so there is no return to measure.",
  multiple_sign_changes:
    "The equity flows change direction more than once, so more than one rate would satisfy them.",
  no_root_in_searched_range: "No rate within a credible range balances these flows.",
};

export function irrReasonLabel(reason: string): string {
  return IRR_REASON_LABELS[reason] ?? reason;
}

const MANAGEMENT_GROUP_LABELS: Record<string, string> = {
  cash: "Cash & funding",
  returns: "Returns",
  collections: "Collections",
  construction: "Construction",
  unit_economics: "Unit economics",
};

export function managementGroupLabel(group: string): string {
  return MANAGEMENT_GROUP_LABELS[group] ?? group;
}

const ACCURACY_GROUP_LABELS: Record<string, string> = {
  customer_inflow: "Customer collections",
  construction_outflow: "Construction",
  development_outflow: "Development",
  financing: "Financing",
};

export function accuracyGroupLabel(group: string): string {
  return ACCURACY_GROUP_LABELS[group] ?? group;
}

/**
 * A reconciliation check's name, turned into a sentence.
 *
 * The names are stable identifiers with a cost code or a month appended, so the
 * suffix is kept and only the stem is translated.
 */
export function checkLabel(name: string): string {
  if (name.startsWith("construction_schedule_covers_")) {
    return `Construction schedule covers ${name.slice("construction_schedule_covers_".length)}`;
  }
  if (name.startsWith("construction_schedule_")) {
    return `Construction schedule for ${name.slice("construction_schedule_".length)}`;
  }
  if (name.startsWith("restriction_within_receipt_")) return "Escrow within its receipt";
  if (name.startsWith("releases_within_restriction_")) return "Releases within their escrow";
  if (name.startsWith("bridge_")) return `Cash bridge balances — ${name.slice("bridge_".length)}`;
  if (name.startsWith("usable_split_")) {
    return `Usable cash splits — ${name.slice("usable_split_".length)}`;
  }
  if (name.startsWith("carry_")) return `Month opens where the last closed — ${name.slice(6)}`;
  return CHECK_LABELS[name] ?? name.replace(/_/g, " ");
}

const CHECK_LABELS: Record<string, string> = {
  opening_total_splits_into_restricted_and_unrestricted:
    "Opening cash splits into restricted and unrestricted",
  construction_source_current: "Construction forecast still current",
  construction_forecast_pinned: "Pinned construction forecast still exists",
  customer_schedule_snapshot_complete: "Every governing instalment could be placed in a month",
  restrictions_backed_by_standing_customer_cash: "Every escrow is backed by standing buyer cash",
  development_maker_is_not_checker: "Development movements confirmed by a second person",
  financing_maker_is_not_checker: "Financing movements confirmed by a second person",
  release_maker_is_not_checker: "Escrow releases confirmed by a second person",
  one_denomination_throughout: "Every movement is in the project's base currency",
};

/** The module a management figure belongs to, in the product's own words. */
const SOURCE_MODULE_LABELS: Record<string, string> = {
  cashflow: "Cashflow",
  collections: "Collections",
  construction: "Construction",
  payment_plans: "Payment plans",
  unit_economics: "Unit economics",
  sales: "Sales & Legal",
};

export function sourceModuleLabel(module: string): string {
  return SOURCE_MODULE_LABELS[module] ?? module;
}
