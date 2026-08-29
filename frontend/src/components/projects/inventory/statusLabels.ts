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
  contracted: "Contracted",
  cancelled: "Cancelled",
  returned: "Returned",
  not_started: "Not started",
  eligible: "Eligible",
  spa_in_progress: "SPA in progress",
  spa_signed: "SPA signed",
  registration_in_progress: "Registering",
  registered: "Registered",
  title_transferred: "Title transferred",
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
