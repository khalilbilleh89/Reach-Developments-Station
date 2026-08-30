/**
 * How a unit's four status dimensions are written for people.
 *
 * Shared between the register and the detail panel so one unit never reads
 * "Not started" in a table and "not_started" in the panel beneath it. An unknown
 * value falls through unchanged rather than being hidden: a status the interface
 * has not been taught is still a status somebody needs to see.
 */
const STATUS_LABELS: Record<string, string> = {
  unreleased: "Unreleased",
  available: "Available",
  held: "Held",
  reserved: "Reserved",
  contract_pending: "Contract pending",
  contracted: "Contracted",
  cancelled: "Cancelled",
  returned: "Returned",
  withdrawn: "Withdrawn",
  not_started: "Not started",
  // The legal vocabulary PR-MVP-05 settled. ``no_spa`` is what PR-MVP-03
  // provisionally called ``not_started``: the same fact, named for the
  // document whose absence it describes.
  no_spa: "No SPA",
  drafting: "SPA drafting",
  issued: "SPA issued",
  buyer_signed: "Buyer signed",
  fully_signed: "Fully signed",
  stamped: "Stamped",
  lodged_submitted: "Lodged with registry",
  registered: "Registered",
  transfer_pending: "Transfer pending",
  transferred: "Title transferred",
  withdrawal_pending: "Withdrawal pending",
  current: "Current",
  partially_paid: "Part paid",
  overdue: "Overdue",
  disputed: "Disputed",
  cleared: "Cleared",
  under_construction: "Under construction",
  ready: "Ready",
  handover_blocked: "Handover blocked",
  handover_ready: "Handover ready",
  handed_over: "Handed over",
};

export function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

/** The four dimensions, written the way the product talks about them. */
export const DIMENSION_LABELS: Record<string, string> = {
  commercial: "Commercial",
  legal: "Legal",
  collection: "Collection",
  delivery: "Delivery",
};
