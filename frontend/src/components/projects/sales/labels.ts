/**
 * How sales and legal vocabulary is written for people.
 *
 * One place, so a reservation never reads "Deposit pending" in the register and
 * "deposit_pending" in the panel beneath it. An unknown value falls through
 * unchanged: a status the interface has not been taught is still a status
 * somebody needs to see.
 *
 * The wording of the two gates is chosen with some care. A confirmed deposit is
 * "Evidence recorded", never "Paid" or "Received", because it is a named person
 * attesting that evidence exists — PR-MVP-07 introduces the record that can say
 * money arrived, and these two must never be read as the same thing.
 */

const RESERVATION_LABELS: Record<string, string> = {
  draft: "Draft",
  deposit_pending: "Awaiting deposit",
  active: "Active",
  extended: "Extended",
  converted: "Converted to contract",
  expired: "Expired",
  cancelled: "Cancelled",
};

const SALE_LABELS: Record<string, string> = {
  draft: "Draft",
  signature_pending: "Awaiting signature",
  active: "Active",
  termination_pending: "Termination in progress",
  cancelled: "Cancelled",
};

const GATE_LABELS: Record<string, string> = {
  not_required: "Not required",
  pending: "Awaiting evidence",
  confirmed: "Evidence recorded",
  waived: "Waived",
};

const EXCEPTION_LABELS: Record<string, string> = {
  not_required: "Within thresholds",
  pending: "Approval required",
  submitted: "Awaiting decision",
  approved: "Approved",
  rejected: "Refused",
};

const ADJUSTMENT_LABELS: Record<string, string> = {
  percentage_discount: "Percentage discount",
  fixed_discount: "Fixed discount",
  seller_credit: "Seller credit",
  package_cost: "Package cost",
  upgrade_allowance: "Upgrade allowance",
  commission_support: "Commission support",
  financing_subsidy: "Financing subsidy",
  extended_terms_npv_cost: "Extended terms (NPV cost)",
  paid_upgrade: "Paid upgrade",
  payment_plan_adjustment: "Payment plan adjustment",
};

const TREATMENT_LABELS: Record<string, string> = {
  price_concession: "Reduces the contract price",
  seller_cost: "Absorbed by the seller",
  price_addition: "Increases the contract price",
};

const LEGAL_EVENT_LABELS: Record<string, string> = {
  spa_drafted: "SPA drafted",
  spa_approved: "SPA approved",
  spa_issued: "SPA issued",
  buyer_signed: "Buyer signed",
  seller_signed: "Seller signed",
  stamped: "Stamped",
  stamp_duty_recorded: "Stamp duty recorded",
  land_registry_lodged: "Lodged with registry",
  land_registry_accepted: "Accepted by registry",
  registered: "Registered",
  title_transfer_pending: "Title transfer pending",
  title_transferred: "Title transferred",
  withdrawal_started: "Withdrawal started",
  withdrawn: "Withdrawn",
};

const CANCELLATION_LABELS: Record<string, string> = {
  notice: "Notice served",
  cure: "Cure period",
  termination_pending_approval: "Awaiting financial approval",
  withdrawal_pending: "Awaiting registry withdrawal",
  ready_for_unit_return: "Ready for unit return",
  completed: "Completed",
  withdrawn: "Case withdrawn",
};

const HANDOVER_LABELS: Record<string, string> = {
  preparation: "Preparation",
  inspection_pending: "Inspection pending",
  snagging: "Snagging",
  ready: "Ready",
  handed_over: "Handed over",
  cancelled: "Cancelled",
};

const CLEARANCE_LABELS: Record<string, string> = {
  legal: "Legal",
  collection: "Collections",
  delivery: "Delivery",
};

const KYC_LABELS: Record<string, string> = {
  not_started: "Not started",
  in_progress: "In progress",
  cleared: "Cleared",
  rejected: "Rejected",
};

function lookup(table: Record<string, string>, value: string | null): string {
  if (value === null) return "—";
  return table[value] ?? value;
}

export const reservationLabel = (value: string | null) => lookup(RESERVATION_LABELS, value);
export const saleLabel = (value: string | null) => lookup(SALE_LABELS, value);
export const gateLabel = (value: string | null) => lookup(GATE_LABELS, value);
export const exceptionLabel = (value: string | null) => lookup(EXCEPTION_LABELS, value);
export const adjustmentLabel = (value: string | null) => lookup(ADJUSTMENT_LABELS, value);
export const treatmentLabel = (value: string | null) => lookup(TREATMENT_LABELS, value);
export const legalEventLabel = (value: string | null) => lookup(LEGAL_EVENT_LABELS, value);
export const cancellationLabel = (value: string | null) => lookup(CANCELLATION_LABELS, value);
export const handoverLabel = (value: string | null) => lookup(HANDOVER_LABELS, value);
export const clearanceLabel = (value: string | null) => lookup(CLEARANCE_LABELS, value);
export const kycLabel = (value: string | null) => lookup(KYC_LABELS, value);

/** The order the legal milestones are shown in, whatever order they arrived. */
export const LEGAL_SEQUENCE = [
  "spa_drafted",
  "spa_approved",
  "spa_issued",
  "buyer_signed",
  "seller_signed",
  "stamped",
  "stamp_duty_recorded",
  "land_registry_lodged",
  "land_registry_accepted",
  "registered",
  "title_transfer_pending",
  "title_transferred",
  "withdrawal_started",
  "withdrawn",
] as const;

/** The commercial inputs a person may record, in the order they are offered. */
export const ADJUSTMENT_TYPES = Object.keys(ADJUSTMENT_LABELS);

/** The two adjustment types stated as a rate rather than an amount. */
export const RATE_ADJUSTMENTS = new Set(["percentage_discount", "payment_plan_adjustment"]);
