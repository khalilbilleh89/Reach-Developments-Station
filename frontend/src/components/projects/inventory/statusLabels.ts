import type { Tone } from "@/components/ui";

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

/**
 * The colour a status is drawn in.
 *
 * Presentation only. The tone repeats what the word already says so that a
 * register can be skimmed; it never carries meaning on its own, and it never
 * decides anything — the server owns every status on this screen and the
 * browser is only reporting the one it was given. An unmapped status is drawn
 * neutral rather than guessed at.
 */
const STATUS_TONES: Record<string, Tone> = {
  // Commercial
  unreleased: "muted",
  held: "warning",
  available: "success",
  reserved: "info",
  contract_pending: "info",
  contracted: "accent",
  returned: "warning",
  cancelled: "danger",
  withdrawn: "danger",
  // Legal
  not_started: "muted",
  no_spa: "muted",
  drafting: "neutral",
  issued: "neutral",
  buyer_signed: "info",
  fully_signed: "info",
  stamped: "info",
  lodged_submitted: "info",
  registered: "success",
  transfer_pending: "warning",
  transferred: "success",
  withdrawal_pending: "warning",
  // Collection
  current: "success",
  partially_paid: "warning",
  overdue: "danger",
  disputed: "danger",
  cleared: "success",
  // Delivery
  under_construction: "neutral",
  ready: "success",
  handover_blocked: "danger",
  handover_ready: "info",
  handed_over: "success",
};

export function statusTone(status: string): Tone {
  return STATUS_TONES[status] ?? "neutral";
}
