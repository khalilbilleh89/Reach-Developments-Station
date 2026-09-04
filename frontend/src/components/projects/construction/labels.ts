import type { Tone } from "@/components/ui";
import { isPositive } from "@/lib/format";

/**
 * The words and colours the construction workspace uses, written once.
 *
 * Two of these decide something a reader will act on, so they live here rather
 * than beside a table: the variance sign, and whether a figure is a cost or a
 * cash figure. Both are wrong in a specific direction if a second copy drifts.
 */

const BUDGET_LABELS: Record<string, string> = {
  draft: "Draft",
  submitted: "Awaiting approval",
  approved: "Approved",
  rejected: "Rejected",
  active: "In force",
  superseded: "Superseded",
};

const BUDGET_TONES: Record<string, Tone> = {
  draft: "neutral",
  submitted: "warning",
  approved: "info",
  rejected: "danger",
  active: "success",
  superseded: "neutral",
};

export function budgetLabel(status: string): string {
  return BUDGET_LABELS[status] ?? status;
}

export function budgetTone(status: string): Tone {
  return BUDGET_TONES[status] ?? "neutral";
}

const CONTRACT_LABELS: Record<string, string> = {
  draft: "Draft",
  submitted: "Awaiting authorisation",
  active: "Live",
  completed: "Completed",
  terminated: "Terminated",
  cancelled: "Cancelled",
};

const CONTRACT_TONES: Record<string, Tone> = {
  draft: "neutral",
  submitted: "warning",
  active: "success",
  completed: "info",
  terminated: "danger",
  cancelled: "neutral",
};

export function contractLabel(status: string): string {
  return CONTRACT_LABELS[status] ?? status;
}

export function contractTone(status: string): Tone {
  return CONTRACT_TONES[status] ?? "neutral";
}

const VARIATION_LABELS: Record<string, string> = {
  draft: "Draft",
  submitted: "Awaiting decision",
  approved: "Approved",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
};

const VARIATION_TONES: Record<string, Tone> = {
  draft: "neutral",
  submitted: "warning",
  approved: "success",
  rejected: "danger",
  withdrawn: "neutral",
};

export function variationLabel(status: string): string {
  return VARIATION_LABELS[status] ?? status;
}

export function variationTone(status: string): Tone {
  return VARIATION_TONES[status] ?? "neutral";
}

const CERTIFICATE_LABELS: Record<string, string> = {
  draft: "Draft",
  submitted: "Awaiting certification",
  certified: "Certified",
  rejected: "Rejected",
  reversed: "Reversed",
};

const CERTIFICATE_TONES: Record<string, Tone> = {
  draft: "neutral",
  submitted: "warning",
  certified: "success",
  rejected: "danger",
  reversed: "danger",
};

export function certificateLabel(status: string): string {
  return CERTIFICATE_LABELS[status] ?? status;
}

export function certificateTone(status: string): Tone {
  return CERTIFICATE_TONES[status] ?? "neutral";
}

const INVOICE_LABELS: Record<string, string> = {
  recorded: "Recorded",
  approved: "Owed",
  disputed: "Disputed",
  voided: "Voided",
};

const INVOICE_TONES: Record<string, Tone> = {
  recorded: "neutral",
  approved: "info",
  disputed: "warning",
  voided: "neutral",
};

export function invoiceLabel(status: string): string {
  return INVOICE_LABELS[status] ?? status;
}

export function invoiceTone(status: string): Tone {
  return INVOICE_TONES[status] ?? "neutral";
}

const PAYMENT_LABELS: Record<string, string> = {
  recorded: "Prepared",
  confirmed: "Paid",
  reversed: "Reversed",
};

const PAYMENT_TONES: Record<string, Tone> = {
  recorded: "warning",
  confirmed: "success",
  reversed: "danger",
};

export function paymentLabel(status: string): string {
  return PAYMENT_LABELS[status] ?? status;
}

export function paymentTone(status: string): Tone {
  return PAYMENT_TONES[status] ?? "neutral";
}

const MILESTONE_LABELS: Record<string, string> = {
  planned: "Planned",
  in_progress: "In progress",
  achieved: "Reported complete",
  certified: "Certified",
  cancelled: "Cancelled",
};

const MILESTONE_TONES: Record<string, Tone> = {
  planned: "neutral",
  in_progress: "info",
  // Reported and not yet certified is the state that matters operationally:
  // site says it is done and nothing downstream has moved yet.
  achieved: "warning",
  certified: "success",
  cancelled: "neutral",
};

export function milestoneLabel(status: string): string {
  return MILESTONE_LABELS[status] ?? status;
}

export function milestoneTone(status: string): Tone {
  return MILESTONE_TONES[status] ?? "neutral";
}

const FORECAST_LABELS: Record<string, string> = {
  draft: "Draft",
  submitted: "Awaiting approval",
  approved: "Approved",
  rejected: "Rejected",
  active: "In force",
  superseded: "Superseded",
};

export function forecastLabel(status: string): string {
  return FORECAST_LABELS[status] ?? status;
}

export function forecastTone(status: string): Tone {
  return BUDGET_TONES[status] ?? "neutral";
}

/**
 * How a variance at completion reads. **Positive is over budget.**
 *
 * Written once because the sign is the single easiest thing in this module to
 * get backwards, and a screen that reversed it would show an overrun as a
 * saving in the same colour the rest of the product uses for good news. Zero is
 * neutral: on budget is neither.
 */
export function varianceTone(
  value: string | null | undefined,
): "neutral" | "danger" | "success" {
  if (value === null || value === undefined || value === "") return "neutral";
  if (isPositive(value)) return "danger";
  return value.trimStart().startsWith("-") ? "success" : "neutral";
}

export function varianceNote(value: string | null | undefined): string {
  if (value === null || value === undefined || value === "")
    return "No forecast in force";
  if (isPositive(value)) return "Over the control budget";
  return value.trimStart().startsWith("-")
    ? "Under the control budget"
    : "On budget";
}

/** Negative headroom means a cost code is committed beyond its authorisation. */
export function headroomTone(value: string): "neutral" | "danger" {
  return value.trimStart().startsWith("-") ? "danger" : "neutral";
}

const CATEGORY_LABELS: Record<string, string> = {
  hard: "Hard",
  soft: "Soft",
  contingency: "Contingency",
  other: "Other",
};

export function categoryLabel(value: string): string {
  return CATEGORY_LABELS[value] ?? value;
}
